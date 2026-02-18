#!/usr/bin/env python3
"""Deploy a CSS style pack to WordPress via the REST API.

Workflow:
1. Load WP credentials from the skills .env file.
2. Resolve the canonical site URL (handles www -> non-www redirects that drop auth).
3. Verify admin-level REST API authentication.
4. Ensure the Code Snippets plugin is installed and active.
5. Create (or update) a front-end PHP snippet that outputs the CSS via wp_head.
6. Verify the CSS is rendering on the live front-end.
7. Optionally clean up previously-installed helper plugins.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENV_SEARCH_PATHS = [
    Path.home() / ".claude" / "skills" / ".env",
    Path.home() / ".agents" / "skills" / ".env",
    Path.home() / ".env",
]

SNIPPET_NAME_PREFIX = "WSD Style Pack"
CODE_SNIPPETS_SLUG = "code-snippets"
STYLE_BLOCK_ID = "ttt-timeless-wisdom-css"


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def load_env(extra_path: Optional[str] = None) -> Dict[str, str]:
    """Read KEY=VALUE lines from the first .env file found."""
    paths = list(ENV_SEARCH_PATHS)
    if extra_path:
        paths.insert(0, Path(extra_path))

    for p in paths:
        if p.is_file():
            env: Dict[str, str] = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
            if "WP_APP_USERNAME" in env and "WP_APP_PASSWORD" in env:
                print(f"[credentials] Loaded from {p}")
                return env
    raise SystemExit(
        "No WordPress credentials found. Ensure WP_APP_USERNAME and "
        "WP_APP_PASSWORD are set in one of:\n"
        + "\n".join(f"  - {p}" for p in paths)
    )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def wp_request(
    url: str,
    *,
    auth: str,
    method: str = "GET",
    data: Optional[dict] = None,
    timeout: int = 30,
) -> Any:
    """Send an authenticated request to the WordPress REST API."""
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", auth)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def wp_request_safe(
    url: str,
    *,
    auth: str,
    method: str = "GET",
    data: Optional[dict] = None,
    timeout: int = 30,
) -> Tuple[Optional[Any], Optional[str]]:
    """Like wp_request but returns (result, error) instead of raising."""
    try:
        result = wp_request(url, auth=auth, method=method, data=data, timeout=timeout)
        return result, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return None, f"HTTP {e.code}: {body[:300]}"
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# URL resolution  (handles www -> non-www redirect that drops auth headers)
# ---------------------------------------------------------------------------

def resolve_canonical_url(site_url: str) -> str:
    """Follow redirects manually to find the canonical URL.

    WordPress often redirects www -> non-www (or vice-versa). When the host
    changes, Python's urllib drops the Authorization header, causing 401 errors.
    We detect this upfront and use the final canonical URL for all API calls.
    """
    site_url = site_url.rstrip("/")
    if not site_url.startswith(("http://", "https://")):
        site_url = "https://" + site_url

    api_url = f"{site_url}/wp-json/wp/v2/"

    try:
        # Use a no-redirect opener to inspect the first hop
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise urllib.error.HTTPError(
                    newurl, code, msg, headers, fp
                )

        opener = urllib.request.build_opener(
            NoRedirect, urllib.request.HTTPSHandler
        )
        req = urllib.request.Request(api_url, method="GET")
        req.add_header("User-Agent", "wordpress-style-director/2.0")
        resp = opener.open(req, timeout=15)
        return site_url  # No redirect, original is fine
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 307, 308):
            location = e.headers.get("Location", "") if e.headers else ""
            if not location:
                location = str(e.url) if hasattr(e, "url") else ""
            if location:
                parsed = urllib.parse.urlparse(location)
                canonical = f"{parsed.scheme}://{parsed.netloc}"
                if canonical.rstrip("/") != site_url.rstrip("/"):
                    print(f"[url] Redirect detected: {site_url} -> {canonical}")
                    return canonical
        return site_url
    except Exception:
        return site_url


# ---------------------------------------------------------------------------
# WordPress REST API operations
# ---------------------------------------------------------------------------

def verify_auth(api_base: str, auth: str) -> Dict[str, Any]:
    """Verify authentication and return user info. Raises on failure."""
    url = f"{api_base}/wp-json/wp/v2/users/me?context=edit"
    try:
        user = wp_request(url, auth=auth)
        roles = user.get("roles", [])
        name = user.get("name", "unknown")
        print(f"[auth] Authenticated as '{name}' (roles: {roles})")
        if "administrator" not in roles:
            print("[auth] WARNING: User is not an administrator. Deployment may fail.")
        return user
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        raise SystemExit(f"[auth] Authentication failed: HTTP {e.code} - {body}")


def detect_theme(api_base: str) -> str:
    """Detect active theme from the front-end HTML."""
    try:
        req = urllib.request.Request(f"{api_base}/")
        req.add_header("User-Agent", "wordpress-style-director/2.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        themes = re.findall(r"wp-content/themes/([^/\"']+)", html)
        if themes:
            from collections import Counter
            theme = Counter(themes).most_common(1)[0][0]
            print(f"[theme] Active theme: {theme}")
            return theme
    except Exception:
        pass
    return "unknown"


def detect_theme_type(api_base: str) -> str:
    """Detect whether the active theme is a classic or block (FSE) theme.

    Block themes output global-styles-inline-css with user customizations.
    Classic themes ignore the global styles 'css' field.
    """
    try:
        req = urllib.request.Request(f"{api_base}/")
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Block themes output global-styles with user CSS; classic themes use Customizer
        # A reliable signal: block themes have wp-site-blocks in the HTML
        if "wp-site-blocks" in html:
            return "block"
    except Exception:
        pass
    return "classic"


def ensure_code_snippets(api_base: str, auth: str) -> bool:
    """Ensure Code Snippets plugin is installed and active. Returns True on success."""
    plugins_url = f"{api_base}/wp-json/wp/v2/plugins"

    # Check if already installed
    plugins, err = wp_request_safe(plugins_url, auth=auth)
    if plugins and isinstance(plugins, list):
        for p in plugins:
            if CODE_SNIPPETS_SLUG in p.get("plugin", ""):
                if p.get("status") == "active":
                    print(f"[plugin] Code Snippets already active")
                    return True
                # Activate it
                plugin_url = f"{plugins_url}/{urllib.parse.quote(p['plugin'], safe='')}"
                result, err = wp_request_safe(
                    plugin_url, auth=auth, method="PUT", data={"status": "active"}
                )
                if result:
                    print(f"[plugin] Code Snippets activated")
                    return True
                print(f"[plugin] Failed to activate: {err}")
                return False

    # Install and activate
    print(f"[plugin] Installing Code Snippets...")
    result, err = wp_request_safe(
        plugins_url,
        auth=auth,
        method="POST",
        data={"slug": CODE_SNIPPETS_SLUG, "status": "active"},
    )
    if result:
        print(f"[plugin] Code Snippets installed and activated")
        return True
    print(f"[plugin] Installation failed: {err}")
    return False


def find_existing_snippet(api_base: str, auth: str, name_prefix: str) -> Optional[int]:
    """Find an existing Code Snippets snippet by name prefix or auto-deployed tag."""
    url = f"{api_base}/wp-json/code-snippets/v1/snippets"
    snippets, err = wp_request_safe(url, auth=auth)
    if not snippets or not isinstance(snippets, list):
        return None
    for s in snippets:
        name = s.get("name", "")
        tags = s.get("tags", [])
        # Match by name prefix or by the 'auto-deployed' tag
        if name.startswith(name_prefix) or "auto-deployed" in tags:
            return s["id"]
    return None


def deploy_snippet(
    api_base: str,
    auth: str,
    css_content: str,
    site_name: str,
    style_block_id: str = STYLE_BLOCK_ID,
) -> int:
    """Create or update a Code Snippets PHP snippet that outputs CSS via wp_head.

    Returns the snippet ID on success, raises on failure.
    """
    snippet_name = f"{SNIPPET_NAME_PREFIX} – {site_name}" if site_name else SNIPPET_NAME_PREFIX

    # Build PHP code that hooks into wp_head
    php_code = (
        "add_action('wp_head', function() {\n"
        "?>\n"
        f'<style id="{style_block_id}">\n'
        f"{css_content}\n"
        "</style>\n"
        "<?php\n"
        "}, 999);"
    )

    # Check for existing snippet to update
    existing_id = find_existing_snippet(api_base, auth, SNIPPET_NAME_PREFIX)

    if existing_id:
        print(f"[deploy] Updating existing snippet #{existing_id}...")
        url = f"{api_base}/wp-json/code-snippets/v1/snippets/{existing_id}"
        result, err = wp_request_safe(
            url,
            auth=auth,
            method="PUT",
            data={
                "name": snippet_name,
                "desc": f"Auto-deployed CSS style pack for {site_name}",
                "code": php_code,
                "scope": "front-end",
                "active": True,
                "priority": 10,
            },
        )
        if result:
            print(f"[deploy] Snippet #{existing_id} updated and active")
            return existing_id
        print(f"[deploy] Update failed: {err}")
        raise SystemExit(f"Failed to update snippet: {err}")

    # Create new snippet
    print(f"[deploy] Creating new snippet...")
    url = f"{api_base}/wp-json/code-snippets/v1/snippets"
    result, err = wp_request_safe(
        url,
        auth=auth,
        method="POST",
        data={
            "name": snippet_name,
            "desc": f"Auto-deployed CSS style pack for {site_name}",
            "code": php_code,
            "scope": "front-end",
            "active": True,
            "priority": 10,
            "tags": ["css", "style", "auto-deployed"],
        },
    )
    if result:
        # Code Snippets API may return a dict or a list; normalise
        item = result[0] if isinstance(result, list) else result
        if isinstance(item, dict) and item.get("id"):
            snippet_id = item["id"]
            print(f"[deploy] Snippet #{snippet_id} created and active")
            return snippet_id

    raise SystemExit(f"[deploy] Failed to create snippet: {err}")


def verify_frontend(
    site_url: str,
    style_block_id: str = STYLE_BLOCK_ID,
    css_markers: Optional[List[str]] = None,
) -> bool:
    """Verify the CSS is rendering on the live front-end."""
    if css_markers is None:
        css_markers = ["--ttt-bg", "--wsd-bg"]

    try:
        req = urllib.request.Request(f"{site_url}/?wsd_verify=1")
        req.add_header("Cache-Control", "no-cache, no-store")
        req.add_header("Pragma", "no-cache")
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[verify] Could not fetch front-end: {e}")
        return False

    checks = {
        "Style block present": style_block_id in html,
    }
    for marker in css_markers:
        checks[f"CSS marker '{marker}'"] = marker in html

    print("[verify] Front-end checks:")
    all_pass = True
    for check, result in checks.items():
        status = "PASS" if result else "FAIL"
        if not result:
            all_pass = False
        print(f"  [{status}] {check}")

    return all_pass


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_helper_plugins(api_base: str, auth: str) -> None:
    """Remove temporary helper plugins that may have been installed in past runs."""
    slugs_to_remove = [
        "simple-custom-css/simple-custom-css",
        "insert-headers-and-footers/ihaf",
    ]
    plugins_url = f"{api_base}/wp-json/wp/v2/plugins"
    plugins, _ = wp_request_safe(plugins_url, auth=auth)
    if not plugins or not isinstance(plugins, list):
        return

    for p in plugins:
        plugin_id = p.get("plugin", "")
        if plugin_id in slugs_to_remove:
            plugin_url = f"{plugins_url}/{urllib.parse.quote(plugin_id, safe='')}"
            # Deactivate
            wp_request_safe(plugin_url, auth=auth, method="PUT", data={"status": "inactive"})
            # Delete
            wp_request_safe(plugin_url, auth=auth, method="DELETE")
            print(f"[cleanup] Removed {p.get('name', plugin_id)}")


# ---------------------------------------------------------------------------
# Main deploy orchestration
# ---------------------------------------------------------------------------

def deploy(
    css_file: str,
    wp_url: str,
    site_name: str = "",
    env_file: Optional[str] = None,
    skip_verify: bool = False,
    cleanup: bool = True,
    css_markers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Full deployment pipeline. Returns a result dict."""

    # 1. Load credentials
    env = load_env(env_file)
    username = env["WP_APP_USERNAME"]
    password = env["WP_APP_PASSWORD"]
    auth = _auth_header(username, password)

    # 2. Resolve canonical URL (handle www redirects)
    canonical = resolve_canonical_url(wp_url)
    print(f"[url] Canonical URL: {canonical}")

    # 3. Verify authentication
    user = verify_auth(canonical, auth)

    # 4. Detect theme
    theme = detect_theme(canonical)
    theme_type = detect_theme_type(canonical)
    print(f"[theme] Type: {theme_type}")

    # 5. Read CSS
    css_path = Path(css_file)
    if not css_path.is_file():
        raise SystemExit(f"CSS file not found: {css_file}")
    css_content = css_path.read_text(encoding="utf-8")
    print(f"[css] Loaded {len(css_content)} chars from {css_path.name}")

    # 6. Ensure Code Snippets plugin
    if not ensure_code_snippets(canonical, auth):
        raise SystemExit("Could not install/activate Code Snippets plugin")

    # 7. Deploy the CSS snippet
    # Extract CSS variable prefix for verification markers
    if css_markers is None:
        # Auto-detect markers from the CSS content
        var_matches = re.findall(r"(--[\w-]+):", css_content)
        if var_matches:
            css_markers = list(dict.fromkeys(var_matches))[:3]  # First 3 unique vars
        else:
            css_markers = []

    snippet_id = deploy_snippet(canonical, auth, css_content, site_name)

    # 8. Verify on front-end
    verified = False
    if not skip_verify:
        verified = verify_frontend(canonical, css_markers=css_markers)
        if verified:
            print("[verify] CSS is LIVE on the site!")
        else:
            print("[verify] WARNING: CSS may not be rendering yet (could be cached)")

    # 9. Cleanup old helper plugins
    if cleanup:
        cleanup_helper_plugins(canonical, auth)

    return {
        "success": True,
        "canonical_url": canonical,
        "theme": theme,
        "theme_type": theme_type,
        "snippet_id": snippet_id,
        "css_length": len(css_content),
        "verified": verified,
        "user": user.get("name", ""),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy a CSS style pack to WordPress via the REST API"
    )
    parser.add_argument(
        "--css-file",
        required=True,
        help="Path to the CSS file to deploy (e.g. additional-css-combined.css)",
    )
    parser.add_argument(
        "--wp-url",
        required=True,
        help="WordPress site URL (e.g. https://example.com or www.example.com)",
    )
    parser.add_argument(
        "--site-name",
        default="",
        help="Site name for labeling the snippet",
    )
    parser.add_argument(
        "--env-file",
        default="",
        help="Path to .env file with WP_APP_USERNAME and WP_APP_PASSWORD",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip front-end verification after deployment",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Do not remove old helper plugins",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = deploy(
        css_file=args.css_file,
        wp_url=args.wp_url,
        site_name=args.site_name,
        env_file=args.env_file or None,
        skip_verify=args.skip_verify,
        cleanup=not args.no_cleanup,
    )
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
