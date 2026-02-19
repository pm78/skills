#!/usr/bin/env python3
"""Publish the latest draft article from Notion My Articles to WordPress."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import mimetypes
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

NOTION_API_BASE = "https://api.notion.com/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_WORDPRESS_SITE = "https://lesnewsducoach.com"
DEFAULT_MY_ARTICLES_DB_ID = "1dc11393-09f8-8049-82eb-e18d8d012f96"
DEFAULT_SITE_KEY = "lesnewsducoach"
DEFAULT_IMAGE_MODEL = "gpt-image-1"
DEFAULT_IMAGE_SIZE = "1536x1024"
DEFAULT_IMAGE_QUALITY = "high"
DEFAULT_SITES_CONFIG = str((Path(__file__).resolve().parents[1] / "config" / "wp_sites.json"))
DEFAULT_BRAND_PROFILES_DIR = str(
    (Path(__file__).resolve().parents[2] / "brand-guidelines" / "assets" / "profiles")
)
DEFAULT_UNCATEGORIZED_KEYS = {
    "non-classe",
    "uncategorized",
    "sans-categorie",
    "no-category",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish latest Draft article from Notion My Articles to WordPress"
    )
    parser.add_argument("--notion-token", default=os.getenv("NOTION_TOKEN", ""))
    parser.add_argument(
        "--articles-db-id",
        default=os.getenv("MY_ARTICLES_DB_ID", DEFAULT_MY_ARTICLES_DB_ID),
    )
    parser.add_argument(
        "--publications-db-id",
        default=os.getenv("PUBLICATIONS_DB_ID", ""),
        help="Optional Notion Publications DB ID for per-site publication logs",
    )
    parser.add_argument(
        "--site",
        default=os.getenv("WP_SITE_KEY", ""),
        help="Target site key from config/wp_sites.json (for example: lesnewsducoach, thrivethroughtime)",
    )
    parser.add_argument(
        "--sites-config",
        default=os.getenv("WP_SITES_CONFIG", DEFAULT_SITES_CONFIG),
        help="Path to site registry JSON",
    )
    parser.add_argument(
        "--default-site-key",
        default=os.getenv("DEFAULT_SITE_KEY", DEFAULT_SITE_KEY),
        help="Fallback site key when no --site and no Notion target site",
    )
    parser.add_argument(
        "--brand-profile",
        default=os.getenv("WP_BRAND_PROFILE", ""),
        help="Optional brand profile id override used for illustration style alignment",
    )
    parser.add_argument(
        "--brand-profiles-dir",
        default=os.getenv("BRAND_PROFILES_DIR", DEFAULT_BRAND_PROFILES_DIR),
        help="Directory containing brand-guidelines profile JSON files",
    )
    parser.add_argument(
        "--wordpress-site",
        default="",
    )
    parser.add_argument(
        "--wp-username",
        default="",
    )
    parser.add_argument(
        "--wp-app-password",
        default="",
    )
    parser.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument(
        "--image-model",
        default=os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL),
    )
    parser.add_argument(
        "--image-size",
        default=os.getenv("OPENAI_IMAGE_SIZE", DEFAULT_IMAGE_SIZE),
    )
    parser.add_argument(
        "--image-quality",
        default=os.getenv("OPENAI_IMAGE_QUALITY", DEFAULT_IMAGE_QUALITY),
    )
    parser.add_argument("--skip-illustration", action="store_true")
    parser.add_argument("--draft-status", default="draft")
    parser.add_argument("--published-status", default="published")
    parser.add_argument("--partially-published-status", default="partially_published")
    parser.add_argument("--platform-name", default="")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def require(value: str, label: str) -> str:
    value = (value or "").strip()
    if not value:
        raise SystemExit(f"Missing required value: {label}")
    return value


def normalize_site_key(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value


def normalize_lookup_key(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    folded = unicodedata.normalize("NFKD", raw)
    without_marks = "".join(ch for ch in folded if not unicodedata.combining(ch))
    cleaned = re.sub(r"&", " and ", without_marks)
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned


def unique_non_empty(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def find_wp_term_by_any_key(
    term_index: Dict[str, Dict[str, Any]],
    raw: Any,
) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, int):
        return term_index.get(str(raw))

    candidate = str(raw).strip()
    if not candidate:
        return None
    if candidate.isdigit():
        by_id = term_index.get(str(int(candidate)))
        if by_id:
            return by_id

    return term_index.get(normalize_lookup_key(candidate))


def fetch_wordpress_taxonomy_terms(
    wordpress_site: str,
    username: str,
    app_password: str,
    *,
    taxonomy: str,
) -> List[Dict[str, Any]]:
    endpoint = wordpress_site.rstrip("/") + f"/wp-json/wp/v2/{taxonomy}"
    headers = wordpress_headers(username, app_password)
    headers.pop("Content-Type", None)

    terms: List[Dict[str, Any]] = []
    page = 1
    while True:
        url = endpoint + f"?per_page=100&page={page}&hide_empty=false"
        req = urllib.request.Request(url, method="GET", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw) if raw else []
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = str(exc)
            if exc.code == 400 and "invalid_page_number" in detail:
                break
            raise SystemExit(
                f"HTTP {exc.code} for GET {url}: {detail[:500]}"
            ) from exc

        if not isinstance(data, list) or not data:
            break

        for item in data:
            if isinstance(item, dict):
                terms.append(item)

        if len(data) < 100:
            break
        page += 1

    return terms


def build_wordpress_term_index(terms: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for term in terms:
        term_id = term.get("id")
        if isinstance(term_id, int):
            index[str(term_id)] = term
        for raw in [
            term.get("slug"),
            html.unescape(str(term.get("name") or "")),
        ]:
            key = normalize_lookup_key(str(raw or ""))
            if key:
                index[key] = term
    return index


def choose_default_wordpress_category(
    terms: List[Dict[str, Any]],
    term_index: Dict[str, Dict[str, Any]],
    site_cfg: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    cfg_default = (site_cfg or {}).get("default_category")
    cfg_term = find_wp_term_by_any_key(term_index, cfg_default)
    if cfg_term:
        return cfg_term

    for term in terms:
        slug_key = normalize_lookup_key(str(term.get("slug") or ""))
        name_key = normalize_lookup_key(html.unescape(str(term.get("name") or "")))
        if slug_key in DEFAULT_UNCATEGORIZED_KEYS or name_key in DEFAULT_UNCATEGORIZED_KEYS:
            return term

    return terms[0] if terms else None


def resolve_wordpress_categories(
    *,
    wordpress_site: str,
    username: str,
    app_password: str,
    site_cfg: Optional[Dict[str, Any]],
    title: str,
    excerpt: str,
    content_html: str,
    notion_categories: List[str],
    notion_tags: List[str],
) -> Tuple[List[int], List[Dict[str, Any]], str]:
    terms = fetch_wordpress_taxonomy_terms(
        wordpress_site,
        username,
        app_password,
        taxonomy="categories",
    )
    if not terms:
        return [], [], "no_categories_available"

    term_index = build_wordpress_term_index(terms)
    alias_cfg = (site_cfg or {}).get("category_aliases")
    alias_map: Dict[str, str] = {}
    if isinstance(alias_cfg, dict):
        for raw_key, raw_value in alias_cfg.items():
            key = normalize_lookup_key(str(raw_key or ""))
            val = str(raw_value or "").strip()
            if key and val:
                alias_map[key] = val

    matched_terms: List[Dict[str, Any]] = []

    def try_match(values: List[str]) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        for value in unique_non_empty(values):
            term = find_wp_term_by_any_key(term_index, value)
            if not term:
                alias = alias_map.get(normalize_lookup_key(value))
                if alias:
                    term = find_wp_term_by_any_key(term_index, alias)
            if term:
                found.append(term)
        return found

    matched_terms = try_match(notion_categories)
    if matched_terms:
        unique_terms: List[Dict[str, Any]] = []
        seen_ids: set[int] = set()
        for term in matched_terms:
            term_id = term.get("id")
            if isinstance(term_id, int) and term_id not in seen_ids:
                seen_ids.add(term_id)
                unique_terms.append(term)
        return [int(term["id"]) for term in unique_terms if isinstance(term.get("id"), int)], unique_terms, "notion_categories"

    matched_terms = try_match(notion_tags)
    if matched_terms:
        unique_terms = []
        seen_ids = set()
        for term in matched_terms:
            term_id = term.get("id")
            if isinstance(term_id, int) and term_id not in seen_ids:
                seen_ids.add(term_id)
                unique_terms.append(term)
        return [int(term["id"]) for term in unique_terms if isinstance(term.get("id"), int)], unique_terms, "notion_tags"

    plain = re.sub(r"<[^>]+>", " ", content_html or "")
    article_text_key = normalize_lookup_key(
        " ".join(
            [
                title or "",
                excerpt or "",
                " ".join(notion_tags),
                " ".join(notion_categories),
                plain[:4000],
            ]
        )
    )
    article_tokens = set(token for token in article_text_key.split("-") if len(token) >= 4)

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for term in terms:
        slug_key = normalize_lookup_key(str(term.get("slug") or ""))
        name_key = normalize_lookup_key(html.unescape(str(term.get("name") or "")))
        if not slug_key and not name_key:
            continue
        if slug_key in DEFAULT_UNCATEGORIZED_KEYS or name_key in DEFAULT_UNCATEGORIZED_KEYS:
            continue

        score = 0
        if name_key and name_key in article_text_key:
            score += 8
        if slug_key and slug_key in article_text_key:
            score += 7

        for token in set([*name_key.split("-"), *slug_key.split("-")]):
            if len(token) >= 4 and token in article_tokens:
                score += 1

        if score > 0:
            scored.append((score, term))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best = scored[0]
        # Avoid weak one-token matches that often misclassify generic news posts.
        if best_score >= 3:
            best_id = best.get("id")
            if isinstance(best_id, int):
                return [best_id], [best], "content_inference"

    fallback = choose_default_wordpress_category(terms, term_index, site_cfg)
    if fallback and isinstance(fallback.get("id"), int):
        return [int(fallback["id"])], [fallback], "fallback_default"

    return [], [], "unresolved"


def load_sites_config(path: str) -> Dict[str, Dict[str, Any]]:
    path = (path or "").strip()
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        return {}
    raw = config_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid sites config format: {config_path}")
    out: Dict[str, Dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        out[normalize_site_key(str(key))] = value
    return out


def resolve_site_config(
    requested: str,
    sites: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    requested = (requested or "").strip()
    if not requested:
        return None, None

    normalized = normalize_site_key(requested)
    if normalized in sites:
        return normalized, sites[normalized]

    for key, cfg in sites.items():
        candidates: List[str] = [key]
        label = (cfg.get("notion_site_label") or cfg.get("platform_name") or "").strip()
        if label:
            candidates.append(label)
        for alias in cfg.get("aliases") or []:
            if isinstance(alias, str):
                candidates.append(alias)
        if normalized in {normalize_site_key(candidate) for candidate in candidates if candidate}:
            return key, cfg

    return None, None


def resolve_wordpress_credentials(
    *,
    site_cfg: Optional[Dict[str, Any]],
    wordpress_site_cli: str,
    wp_username_cli: str,
    wp_password_cli: str,
) -> Tuple[str, str, str]:
    wordpress_site = (wordpress_site_cli or "").strip()
    wp_username = (wp_username_cli or "").strip()
    wp_app_password = (wp_password_cli or "").strip()

    if site_cfg:
        if not wordpress_site:
            wordpress_site = (site_cfg.get("wp_url") or "").strip()

        user_env = (site_cfg.get("username_env") or "").strip()
        pass_env = (site_cfg.get("password_env") or "").strip()

        if user_env and not wp_username:
            wp_username = os.getenv(user_env, "").strip()
        if pass_env and not wp_app_password:
            wp_app_password = os.getenv(pass_env, "").strip()

    if not wordpress_site:
        wordpress_site = (
            os.getenv("WORDPRESS_SITE", "")
            or os.getenv("WP_URL", "")
            or DEFAULT_WORDPRESS_SITE
        ).strip()

    if not wp_username:
        wp_username = (
            os.getenv("WP_USERNAME", "")
            or os.getenv("WORDPRESS_USERNAME", "")
            or os.getenv("WP_APP_USERNAME", "")
        ).strip()
    if not wp_app_password:
        wp_app_password = (
            os.getenv("WP_APP_PASSWORD", "")
            or os.getenv("WORDPRESS_APP_PASSWORD", "")
        ).strip()

    return wordpress_site, wp_username, wp_app_password


def choose_platform_name(
    explicit_platform_name: str,
    site_cfg: Optional[Dict[str, Any]],
    site_key: Optional[str],
) -> str:
    explicit_platform_name = (explicit_platform_name or "").strip()
    if explicit_platform_name:
        return explicit_platform_name
    if site_cfg:
        for field in ("platform_name", "notion_site_label", "display_name"):
            value = (site_cfg.get(field) or "").strip()
            if value:
                return value
    if site_key:
        return site_key
    return "WordPress"


def load_brand_profiles(profile_dir: str) -> Dict[str, Dict[str, Any]]:
    directory = Path((profile_dir or "").strip())
    if not directory.exists() or not directory.is_dir():
        return {}

    profiles: Dict[str, Dict[str, Any]] = {}
    for candidate in sorted(directory.glob("*.json")):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue

        aliases = set()
        for raw in [data.get("brand_id"), data.get("brand_name"), candidate.stem]:
            if isinstance(raw, str) and raw.strip():
                aliases.add(normalize_site_key(raw))
        for raw_alias in data.get("aliases") or []:
            if isinstance(raw_alias, str) and raw_alias.strip():
                aliases.add(normalize_site_key(raw_alias))

        for alias in aliases:
            if alias and alias not in profiles:
                profiles[alias] = data

    return profiles


def resolve_brand_profile(
    *,
    explicit_brand_profile: str,
    site_cfg: Optional[Dict[str, Any]],
    site_key: Optional[str],
    profiles_by_alias: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    candidates: List[str] = []
    for raw in [
        explicit_brand_profile,
        (site_cfg or {}).get("brand_profile"),
        (site_cfg or {}).get("brand_id"),
        site_key,
    ]:
        if isinstance(raw, str) and raw.strip():
            candidates.append(raw)

    for candidate in candidates:
        alias = normalize_site_key(candidate)
        profile = profiles_by_alias.get(alias)
        if profile:
            brand_id = str(profile.get("brand_id") or alias).strip() or alias
            return brand_id, profile

    return None, None


def _csv_from_values(raw: Any, *, limit: int = 6) -> str:
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
        return ", ".join(values[:limit])
    if isinstance(raw, str):
        return raw.strip()
    return ""


def infer_default_image_style(brand_profile: Optional[Dict[str, Any]]) -> str:
    if not isinstance(brand_profile, dict):
        return "premium editorial hero visual, clean composition, professional, optimistic"

    style = brand_profile.get("illustration_style")
    if not isinstance(style, dict):
        return "premium editorial hero visual, clean composition, professional, optimistic"

    rendering = " ".join(
        [
            str(style.get("rendering") or ""),
            str(style.get("editorial_direction") or ""),
            str(style.get("mood") or ""),
        ]
    ).lower()

    photoreal_markers = [
        "photoreal",
        "photo realistic",
        "photographic",
        "realistic photography",
        "natural light",
    ]
    illustration_markers = ["illustration", "vector", "semi-flat", "flat style", "cartoon"]

    if any(marker in rendering for marker in photoreal_markers):
        return (
            "photorealistic editorial photography, natural light, premium business context, "
            "credible human expressions, magazine quality"
        )

    if any(marker in rendering for marker in illustration_markers):
        return "modern editorial illustration, clean composition, professional, optimistic"

    return "premium editorial hero visual, clean composition, professional, optimistic"


def build_brand_illustration_guidance(brand_profile: Optional[Dict[str, Any]]) -> str:
    if not isinstance(brand_profile, dict):
        return ""

    lines: List[str] = []
    brand_name = (brand_profile.get("brand_name") or "").strip()
    if brand_name:
        lines.append(f"Target brand: {brand_name}.")

    style = brand_profile.get("illustration_style")
    if isinstance(style, dict):
        for label, field in [
            ("Editorial direction", "editorial_direction"),
            ("Rendering", "rendering"),
            ("Composition", "composition"),
            ("Mood", "mood"),
        ]:
            value = (style.get(field) or "").strip()
            if value:
                lines.append(f"{label}: {value.rstrip(' .')}.")

        palette = _csv_from_values(style.get("color_palette"))
        if palette:
            lines.append(f"Color palette: {palette}.")

        motifs = _csv_from_values(style.get("motifs"))
        if motifs:
            lines.append(f"Preferred motifs: {motifs}.")

        avoid = _csv_from_values(style.get("avoid"))
        if avoid:
            lines.append(f"Avoid: {avoid}.")

    css_style = brand_profile.get("css_style")
    if isinstance(css_style, dict):
        typography = css_style.get("typography")
        if isinstance(typography, dict):
            heading = (typography.get("heading_font") or "").strip()
            body = (typography.get("body_font") or "").strip()
            if heading or body:
                lines.append(
                    f"Typography cues: headings use {heading or 'brand heading font'}, body uses {body or 'brand body font'}."
                )

        tokens = css_style.get("tokens")
        if isinstance(tokens, dict):
            accent = (tokens.get("primary_accent") or "").strip()
            bg = (tokens.get("background") or "").strip()
            text = (tokens.get("text_primary") or "").strip()
            token_parts = [part for part in [f"accent {accent}" if accent else "", f"background {bg}" if bg else "", f"text {text}" if text else ""] if part]
            if token_parts:
                lines.append("CSS tokens: " + ", ".join(token_parts) + ".")

    return "\n".join(lines).strip()


def http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 45,
) -> Dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        raise SystemExit(
            f"HTTP {exc.code} for {method} {url}: {detail[:500]}"
        ) from exc


def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def wordpress_headers(username: str, app_password: str) -> Dict[str, str]:
    token = base64.b64encode(f"{username}:{app_password}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def rich_text_to_plain(rich_text: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for item in rich_text or []:
        if item.get("plain_text"):
            parts.append(item["plain_text"])
        elif item.get("text", {}).get("content"):
            parts.append(item["text"]["content"])
    return "".join(parts)


def pick_property(
    properties: Dict[str, Any],
    preferred_names: List[str],
    allowed_types: Tuple[str, ...],
    *,
    allow_fallback: bool = True,
) -> Optional[Tuple[str, str]]:
    lower_map = {name.lower(): name for name in properties.keys()}

    for preferred in preferred_names:
        name = properties.get(preferred)
        if name and name.get("type") in allowed_types:
            return preferred, name.get("type")
        mapped = lower_map.get(preferred.lower())
        if mapped and properties[mapped].get("type") in allowed_types:
            return mapped, properties[mapped].get("type")

    if allow_fallback:
        for name, meta in properties.items():
            if meta.get("type") in allowed_types:
                return name, meta.get("type")

    return None


def load_db_schema(notion_token: str, db_id: str) -> Dict[str, Any]:
    return http_json(
        "GET",
        f"{NOTION_API_BASE}/databases/{db_id}",
        headers=notion_headers(notion_token),
    )


def status_name_from_property(prop: Dict[str, Any]) -> str:
    ptype = prop.get("type")
    if ptype == "select":
        return (prop.get("select") or {}).get("name") or ""
    if ptype == "status":
        return (prop.get("status") or {}).get("name") or ""
    return ""


def query_latest_draft_page(
    notion_token: str,
    db_id: str,
    *,
    status_property_name: str,
    draft_status: str,
    page_size: int,
    selected_site_key: Optional[str] = None,
    target_site_property_name: Optional[str] = None,
    sites: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    cursor: Optional[str] = None
    size = max(1, min(page_size, 100))

    while True:
        payload: Dict[str, Any] = {
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
            "page_size": size,
        }
        if cursor:
            payload["start_cursor"] = cursor

        data = http_json(
            "POST",
            f"{NOTION_API_BASE}/databases/{db_id}/query",
            headers=notion_headers(notion_token),
            payload=payload,
        )

        for row in data.get("results", []):
            properties = row.get("properties", {})
            status_prop = properties.get(status_property_name, {})
            status_name = status_name_from_property(status_prop)
            if status_name.lower() == draft_status.lower():
                if not row_matches_site_target(
                    row,
                    target_site_property_name,
                    selected_site_key,
                    sites or {},
                ):
                    continue
                return row

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    site_hint = f" and site '{selected_site_key}'" if selected_site_key else ""
    raise SystemExit(
        f"No article found with status '{draft_status}'{site_hint} in My Articles database"
    )


def extract_property_text(row: Dict[str, Any], property_name: str) -> str:
    prop = row.get("properties", {}).get(property_name, {})
    ptype = prop.get("type")

    if ptype == "title":
        return rich_text_to_plain(prop.get("title", []))
    if ptype == "rich_text":
        return rich_text_to_plain(prop.get("rich_text", []))
    return ""


def extract_property_url(row: Dict[str, Any], property_name: str) -> str:
    prop = row.get("properties", {}).get(property_name, {})
    if prop.get("type") == "url":
        return (prop.get("url") or "").strip()
    return ""


def extract_property_tags(row: Dict[str, Any], property_name: str) -> List[str]:
    prop = row.get("properties", {}).get(property_name, {})
    ptype = prop.get("type")

    if ptype == "multi_select":
        return [((item or {}).get("name") or "").strip() for item in (prop.get("multi_select") or []) if ((item or {}).get("name") or "").strip()]
    if ptype == "select":
        value = ((prop.get("select") or {}).get("name") or "").strip()
        return [value] if value else []
    if ptype == "rich_text":
        raw = rich_text_to_plain(prop.get("rich_text", []))
        return [part.strip() for part in re.split(r"[,;|]", raw) if part.strip()]

    return []


def row_matches_site_target(
    row: Dict[str, Any],
    target_site_property_name: Optional[str],
    selected_site_key: Optional[str],
    sites: Dict[str, Dict[str, Any]],
) -> bool:
    if not selected_site_key or not target_site_property_name:
        return True

    values = extract_property_tags(row, target_site_property_name)
    if not values:
        return True

    wildcard = {"all", "any", "both", "multi", "all-sites"}
    for value in values:
        normalized = normalize_site_key(value)
        if normalized in wildcard:
            return True
        resolved_key, _ = resolve_site_config(value, sites)
        if resolved_key == selected_site_key:
            return True
        if normalized == selected_site_key:
            return True

    return False


def resolve_site_from_row(
    row: Dict[str, Any],
    target_site_property_name: Optional[str],
    sites: Dict[str, Dict[str, Any]],
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    if not target_site_property_name:
        return None, None, None

    values = extract_property_tags(row, target_site_property_name)
    if not values:
        return None, None, None

    wildcard = {"all", "any", "both", "multi", "all-sites"}
    for value in values:
        normalized = normalize_site_key(value)
        if not normalized or normalized in wildcard:
            continue
        site_key, site_cfg = resolve_site_config(value, sites)
        if site_key:
            return site_key, site_cfg, value
        if normalized in sites:
            return normalized, sites.get(normalized), value

    return None, None, None


def fetch_block_children(notion_token: str, block_id: str) -> List[Dict[str, Any]]:
    children: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        params = {"page_size": "100"}
        if cursor:
            params["start_cursor"] = cursor
        query = urllib.parse.urlencode(params)
        url = f"{NOTION_API_BASE}/blocks/{block_id}/children?{query}"
        data = http_json("GET", url, headers=notion_headers(notion_token))

        children.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return children


def block_plain_text(block: Dict[str, Any]) -> str:
    block_type = block.get("type", "")
    payload = block.get(block_type, {})

    if "rich_text" in payload:
        return rich_text_to_plain(payload.get("rich_text", []))
    if block_type == "code":
        return rich_text_to_plain(payload.get("rich_text", []))
    return ""


def rich_text_to_html(
    rich_text: List[Dict[str, Any]], *, enable_citations: bool = True
) -> str:
    parts: List[str] = []

    for item in rich_text or []:
        text_value = (
            item.get("plain_text")
            or item.get("text", {}).get("content")
            or ""
        )
        if not text_value:
            continue

        segment = apply_inline_formatting(text_value, enable_citations=enable_citations)

        href = (
            item.get("href")
            or ((item.get("text") or {}).get("link") or {}).get("url")
            or ""
        ).strip()
        if href and "<a " not in segment.lower():
            safe_href = html.escape(href, quote=True)
            segment = (
                f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">'
                f"{segment}</a>"
            )

        annotations = item.get("annotations") or {}
        if annotations.get("code"):
            segment = f"<code>{segment}</code>"
        if annotations.get("bold"):
            segment = f"<strong>{segment}</strong>"
        if annotations.get("italic"):
            segment = f"<em>{segment}</em>"
        if annotations.get("strikethrough"):
            segment = f"<s>{segment}</s>"
        if annotations.get("underline"):
            segment = f"<u>{segment}</u>"

        parts.append(segment)

    return "".join(parts)


def block_inline_html(block: Dict[str, Any], *, enable_citations: bool = True) -> str:
    block_type = block.get("type", "")
    payload = block.get(block_type, {})
    rich_text = payload.get("rich_text")

    if isinstance(rich_text, list) and rich_text:
        return rich_text_to_html(rich_text, enable_citations=enable_citations).strip()

    plain = block_plain_text(block).strip()
    if not plain:
        return ""

    return apply_inline_formatting(plain, enable_citations=enable_citations)


def flush_list(buffer: List[str], list_tag: Optional[str], html_parts: List[str]) -> None:
    if not buffer or not list_tag:
        return
    html_parts.append(f"<{list_tag}>" + "".join(buffer) + f"</{list_tag}>")
    buffer.clear()


def notion_blocks_to_html(blocks: List[Dict[str, Any]]) -> str:
    html_parts: List[str] = []
    list_items: List[str] = []
    active_list: Optional[str] = None

    for block in blocks:
        block_type = block.get("type")
        text_html = block_inline_html(block)

        if block_type == "bulleted_list_item":
            if active_list != "ul":
                flush_list(list_items, active_list, html_parts)
                active_list = "ul"
            if text_html:
                list_items.append(f"<li>{text_html}</li>")
            continue

        if block_type == "numbered_list_item":
            if active_list != "ol":
                flush_list(list_items, active_list, html_parts)
                active_list = "ol"
            if text_html:
                list_items.append(f"<li>{text_html}</li>")
            continue

        flush_list(list_items, active_list, html_parts)
        active_list = None

        if block_type == "heading_1":
            if text_html:
                html_parts.append(f"<h1>{text_html}</h1>")
        elif block_type == "heading_2":
            if text_html:
                html_parts.append(f"<h2>{text_html}</h2>")
        elif block_type == "heading_3":
            if text_html:
                html_parts.append(f"<h3>{text_html}</h3>")
        elif block_type == "quote":
            if text_html:
                html_parts.append(f"<blockquote>{text_html}</blockquote>")
        elif block_type == "code":
            code_text = html.escape(block_plain_text(block).strip())
            if code_text:
                html_parts.append(f"<pre><code>{code_text}</code></pre>")
        elif block_type == "divider":
            html_parts.append("<hr />")
        elif text_html:
            html_parts.append(f"<p>{text_html}</p>")

    flush_list(list_items, active_list, html_parts)

    return "\n".join(html_parts).strip()


def normalize_line_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def apply_inline_formatting(text: str, *, enable_citations: bool = True) -> str:
    raw = normalize_line_text(text)
    if not raw:
        return ""

    escaped = html.escape(raw)
    placeholders: Dict[str, str] = {}

    def stash(fragment: str) -> str:
        key = f"@@HTML{len(placeholders)}@@"
        placeholders[key] = fragment
        return key

    def repl_md_link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = match.group(2)
        safe_url = html.escape(url, quote=True)
        safe_label = html.escape(label)
        return stash(f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_label}</a>')

    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", repl_md_link, escaped)

    def repl_url(match: re.Match[str]) -> str:
        url = match.group(1)
        trailing = ""
        while url and url[-1] in ".,);:":
            trailing = url[-1] + trailing
            url = url[:-1]
        safe_url = html.escape(url, quote=True)
        anchor = f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>'
        return stash(anchor) + html.escape(trailing)

    escaped = re.sub(r"(https?://[^\s<]+)", repl_url, escaped)

    if enable_citations:
        escaped = re.sub(
            r"\[(\d+)\]",
            lambda m: stash(f'<a href="#source-{m.group(1)}" class="citation">[{m.group(1)}]</a>'),
            escaped,
        )

    escaped = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{m.group(1)}</code>"), escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", escaped)

    for key, fragment in placeholders.items():
        escaped = escaped.replace(key, fragment)

    return escaped


def parse_sources(lines: List[str]) -> List[Tuple[int, str]]:
    entries: List[Tuple[int, str]] = []
    current_num: Optional[int] = None
    current_parts: List[str] = []

    def flush() -> None:
        nonlocal current_num, current_parts
        if current_num is None:
            return
        text = normalize_line_text(" ".join(current_parts))
        entries.append((current_num, text))
        current_num = None
        current_parts = []

    for line in lines:
        stripped = normalize_line_text(line)
        if not stripped:
            continue

        match = re.match(r"^\[(\d+)\]\s*(.*)$", stripped) or re.match(
            r"^(\d+)[\.\)]\s*(.*)$", stripped
        )
        if match:
            flush()
            current_num = int(match.group(1))
            tail = normalize_line_text(match.group(2))
            if tail:
                current_parts.append(tail)
            continue

        if current_num is not None:
            current_parts.append(stripped)

    flush()
    return entries


def render_sources_section(lines: List[str]) -> str:
    entries = parse_sources(lines)
    if not entries:
        # Fallback for markdown source sections authored as bullet lists:
        # - Source name: https://...
        raw_items: List[str] = []
        for line in lines:
            stripped = normalize_line_text(line)
            if not stripped:
                continue
            stripped = re.sub(r"^[-*]\s+", "", stripped)
            stripped = re.sub(r"^\d+[\.\)]\s+", "", stripped)
            stripped = normalize_line_text(stripped)
            if stripped:
                raw_items.append(stripped)

        if not raw_items:
            return ""

        items = [
            (
                '<li '
                'style="text-align:left !important; text-justify:auto !important; '
                'word-spacing:normal !important; letter-spacing:normal !important;">'
                f"{apply_inline_formatting(text, enable_citations=False)}</li>"
            )
            for text in raw_items
        ]
        return (
            '<div class="sources-block" '
            'style="text-align:left !important; text-justify:auto !important; '
            'word-spacing:normal !important; letter-spacing:normal !important;">'
            '<ul class="sources-list" '
            'style="text-align:left !important; text-justify:auto !important; '
            'word-spacing:normal !important; letter-spacing:normal !important;">'
            + "".join(items)
            + "</ul></div>"
        )

    items = [
        (
            f'<li id="source-{num}" '
            'style="text-align:left !important; text-justify:auto !important; '
            'word-spacing:normal !important; letter-spacing:normal !important;">'
            f"{apply_inline_formatting(text, enable_citations=False)}</li>"
        )
        for num, text in entries
    ]
    return (
        '<div class="sources-block" '
        'style="text-align:left !important; text-justify:auto !important; '
        'word-spacing:normal !important; letter-spacing:normal !important;">'
        '<ol class="sources-list" '
        'style="text-align:left !important; text-justify:auto !important; '
        'word-spacing:normal !important; letter-spacing:normal !important;">'
        + "".join(items)
        + "</ol></div>"
    )


def basic_markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    html_parts: List[str] = []
    list_items: List[str] = []
    active_list: Optional[str] = None
    paragraph_lines: List[str] = []
    source_lines: List[str] = []
    in_sources = False
    in_code = False
    code_lines: List[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        text = normalize_line_text(" ".join(paragraph_lines))
        if text:
            html_parts.append(f"<p>{apply_inline_formatting(text)}</p>")
        paragraph_lines = []

    def flush_code() -> None:
        nonlocal code_lines
        if not code_lines:
            return
        code = "\n".join(code_lines)
        html_parts.append(f"<pre><code>{html.escape(code)}</code></pre>")
        code_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                flush_code()
                in_code = False
            else:
                code_lines.append(line)
            continue

        if in_sources:
            source_lines.append(line)
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list(list_items, active_list, html_parts)
            active_list = None
            in_code = True
            code_lines = []
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list(list_items, active_list, html_parts)
            active_list = None
            level = len(heading_match.group(1))
            heading_text = normalize_line_text(heading_match.group(2))
            if heading_text.lower() == "sources":
                html_parts.append(f"<h{level}>Sources</h{level}>")
                in_sources = True
                source_lines = []
            elif heading_text:
                html_parts.append(f"<h{level}>{apply_inline_formatting(heading_text)}</h{level}>")
            continue

        if not stripped:
            flush_paragraph()
            flush_list(list_items, active_list, html_parts)
            active_list = None
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet_match:
            flush_paragraph()
            if active_list != "ul":
                flush_list(list_items, active_list, html_parts)
                active_list = "ul"
            list_items.append(f"<li>{apply_inline_formatting(bullet_match.group(1))}</li>")
            continue

        numbered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if numbered_match:
            flush_paragraph()
            if active_list != "ol":
                flush_list(list_items, active_list, html_parts)
                active_list = "ol"
            list_items.append(f"<li>{apply_inline_formatting(numbered_match.group(1))}</li>")
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_list(list_items, active_list, html_parts)
            active_list = None
            quote_text = normalize_line_text(stripped.lstrip(">").strip())
            if quote_text:
                html_parts.append(f"<blockquote><p>{apply_inline_formatting(quote_text)}</p></blockquote>")
            continue

        flush_list(list_items, active_list, html_parts)
        active_list = None
        paragraph_lines.append(stripped)

    if in_code:
        flush_code()
    flush_paragraph()
    flush_list(list_items, active_list, html_parts)

    if in_sources:
        rendered_sources = render_sources_section(source_lines)
        if rendered_sources:
            html_parts.append(rendered_sources)

    return "\n".join(html_parts).strip()


def markdown_to_html(markdown_text: str) -> str:
    text = (markdown_text or "").replace("\xa0", " ").strip()
    if not text:
        return ""

    if re.search(r"<\s*(p|h[1-6]|ul|ol|li|blockquote|pre|code|img)\b", text, re.IGNORECASE):
        return text

    return basic_markdown_to_html(text)


def build_article_content_html(
    notion_token: str,
    page: Dict[str, Any],
    content_property_name: Optional[str],
) -> str:
    if content_property_name:
        content = extract_property_text(page, content_property_name)
        if content.strip():
            return markdown_to_html(content)

    blocks = fetch_block_children(notion_token, page.get("id", ""))
    content_html = notion_blocks_to_html(blocks)
    if content_html:
        return content_html

    raise SystemExit("Draft article has no usable content (Content property and page blocks are empty)")


def has_inline_image(content_html: str) -> bool:
    return bool(re.search(r"<img\\b", content_html or "", re.IGNORECASE))


def guess_extension_from_mime(mime_type: str) -> str:
    ext = mimetypes.guess_extension(mime_type or "") or ""
    if ext.lower() in {".jpe", ".jpeg"}:
        return ".jpg"
    return ext or ".png"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned[:80] or "article-illustration"


def build_illustration_prompt(
    title: str,
    excerpt: str,
    content_html: str,
    custom_prompt: Optional[str] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
) -> str:
    plain = re.sub(r"<[^>]+>", " ", content_html or "")
    plain = re.sub(r"\\s+", " ", plain).strip()
    snippet = plain[:900]
    summary = excerpt.strip() if excerpt else ""
    prompt = (
        custom_prompt.strip()
        if custom_prompt and custom_prompt.strip()
        else (
            "Create a single high-quality editorial hero image for a blog article.\n"
            f"Article title: {title}\n"
            f"Article summary: {summary}\n"
            f"Article key points: {snippet}\n"
            f"Style: {infer_default_image_style(brand_profile)}."
        )
    )

    brand_guidance = build_brand_illustration_guidance(brand_profile)
    if brand_guidance:
        prompt += "\nBrand style alignment:\n" + brand_guidance

    prompt += (
        "\nConstraints: no text, no logos, no watermarks, no brand marks, "
        "and avoid duplicated faces or cloned subjects."
    )
    return prompt


def generate_illustration_image(
    api_key: str,
    *,
    prompt: str,
    model: str,
    size: str,
    quality: str,
    dry_run: bool,
) -> Tuple[Optional[bytes], str]:
    if dry_run:
        return None, "image/png"

    api_key = (api_key or "").strip()
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY; required to generate article illustration")

    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
    }
    data = http_json(
        "POST",
        f"{OPENAI_API_BASE}/images/generations",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload=payload,
        timeout=120,
    )

    first = (data.get("data") or [{}])[0]
    b64 = first.get("b64_json")
    if b64:
        return base64.b64decode(b64), "image/png"

    image_url = (first.get("url") or "").strip()
    if image_url:
        req = urllib.request.Request(image_url, method="GET")
        with urllib.request.urlopen(req, timeout=120) as resp:
            mime = (resp.headers.get("Content-Type") or "image/png").split(";")[0].strip()
            return resp.read(), mime

    raise SystemExit("Image generation returned no usable image payload")


def upload_media_to_wordpress(
    wordpress_site: str,
    username: str,
    app_password: str,
    *,
    filename: str,
    image_bytes: Optional[bytes],
    content_type: str,
    dry_run: bool,
) -> Dict[str, Any]:
    endpoint = wordpress_site.rstrip("/") + "/wp-json/wp/v2/media"

    if dry_run:
        safe_name = urllib.parse.quote(filename)
        return {
            "id": None,
            "source_url": f"{wordpress_site.rstrip('/')}/wp-content/uploads/{safe_name}",
        }

    if not image_bytes:
        raise SystemExit("Missing illustration bytes for WordPress media upload")

    headers = wordpress_headers(username, app_password)
    headers["Content-Type"] = content_type
    headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    req = urllib.request.Request(
        endpoint,
        data=image_bytes,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        raise SystemExit(
            f"HTTP {exc.code} for POST {endpoint} (media upload): {detail[:500]}"
        ) from exc


def prepend_image_to_content(content_html: str, image_url: str, alt_text: str) -> str:
    safe_url = html.escape(image_url, quote=True)
    safe_alt = html.escape((alt_text or "Article illustration").strip(), quote=True)
    hero = (
        '<figure class="article-illustration">'
        f'<img src="{safe_url}" alt="{safe_alt}" />'
        "</figure>"
    )
    if not (content_html or "").strip():
        return hero
    return hero + "\n" + content_html


def strip_duplicate_leading_h1(content_html: str, title: str) -> str:
    content = content_html or ""
    if not content.strip():
        return content

    match = re.match(r"^\s*<h1[^>]*>(.*?)</h1>\s*", content, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return content

    heading_raw = re.sub(r"<[^>]+>", "", match.group(1))
    heading_text = normalize_line_text(html.unescape(heading_raw))
    title_text = normalize_line_text(title)
    if heading_text and title_text and heading_text.lower() == title_text.lower():
        return content[match.end():].lstrip()

    return content


def publish_to_wordpress(
    wordpress_site: str,
    username: str,
    app_password: str,
    payload: Dict[str, Any],
    *,
    dry_run: bool,
) -> Dict[str, Any]:
    endpoint = wordpress_site.rstrip("/") + "/wp-json/wp/v2/posts"

    if dry_run:
        return {
            "id": None,
            "link": "(dry-run)",
            "endpoint": endpoint,
            "payload": payload,
        }

    return http_json(
        "POST",
        endpoint,
        headers=wordpress_headers(username, app_password),
        payload=payload,
        timeout=60,
    )


def notion_status_property_payload(prop_type: str, status_name: str) -> Dict[str, Any]:
    if prop_type == "status":
        return {"status": {"name": status_name}}
    if prop_type == "select":
        return {"select": {"name": status_name}}
    raise SystemExit(f"Unsupported status property type: {prop_type}")


def notion_platform_property_payload(
    prop_type: str,
    current_platforms: List[str],
    platform_name: str,
) -> Dict[str, Any]:
    merged = sorted({name for name in [*current_platforms, platform_name] if (name or "").strip()})

    if prop_type == "multi_select":
        return {"multi_select": [{"name": name} for name in merged]}
    if prop_type == "select":
        return {"select": {"name": platform_name}}
    if prop_type == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": ", ".join(merged)}}]}

    raise SystemExit(f"Unsupported platform property type: {prop_type}")


def notion_terms_property_payload(prop_type: str, values: List[str]) -> Dict[str, Any]:
    clean = unique_non_empty(values)
    if prop_type == "multi_select":
        return {"multi_select": [{"name": value} for value in clean]}
    if prop_type == "select":
        return {"select": {"name": clean[0]} if clean else None}
    if prop_type == "rich_text":
        return {"rich_text": notion_rich_text(", ".join(clean))}
    raise SystemExit(f"Unsupported terms property type: {prop_type}")


def extract_status_options(prop_meta: Dict[str, Any], prop_type: str) -> List[str]:
    config = prop_meta.get(prop_type, {}) if isinstance(prop_meta, dict) else {}
    options = config.get("options", []) if isinstance(config, dict) else []
    names: List[str] = []
    for option in options:
        name = (option or {}).get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def resolve_status_name(preferred: str, fallback: str, options: List[str]) -> str:
    if not options:
        return preferred
    by_lower = {name.lower(): name for name in options}
    if preferred.lower() in by_lower:
        return by_lower[preferred.lower()]
    if fallback.lower() in by_lower:
        return by_lower[fallback.lower()]
    return preferred


def decide_status_after_publish(
    *,
    published_platforms_after: List[str],
    required_platforms: List[str],
    published_status: str,
    partially_published_status: str,
    status_options: List[str],
) -> str:
    if not required_platforms:
        return resolve_status_name(published_status, published_status, status_options)

    published_set = {name.lower() for name in published_platforms_after}
    required_set = {name.lower() for name in required_platforms}
    all_required_done = required_set.issubset(published_set)
    preferred = published_status if all_required_done else partially_published_status
    fallback = published_status
    return resolve_status_name(preferred, fallback, status_options)


def update_notion_page_after_publish(
    notion_token: str,
    page_id: str,
    *,
    status_property_name: str,
    status_property_type: str,
    status_to_set: str,
    published_url_property_name: Optional[str],
    published_platforms_property_name: Optional[str],
    published_platforms_property_type: Optional[str],
    current_published_platforms: List[str],
    platform_name: str,
    category_property_name: Optional[str],
    category_property_type: Optional[str],
    category_values: List[str],
    illustration_url_property_name: Optional[str],
    publish_date_property_name: Optional[str],
    wordpress_link: str,
    illustration_url: str,
    dry_run: bool,
) -> Dict[str, Any]:
    properties: Dict[str, Any] = {
        status_property_name: notion_status_property_payload(
            status_property_type, status_to_set
        )
    }

    if published_url_property_name and wordpress_link:
        properties[published_url_property_name] = {"url": wordpress_link}
    if (
        published_platforms_property_name
        and published_platforms_property_type
        and platform_name
    ):
        properties[published_platforms_property_name] = notion_platform_property_payload(
            published_platforms_property_type,
            current_published_platforms,
            platform_name,
        )
    if category_property_name and category_property_type and category_values:
        properties[category_property_name] = notion_terms_property_payload(
            category_property_type,
            category_values,
        )
    if illustration_url_property_name and illustration_url:
        properties[illustration_url_property_name] = {"url": illustration_url}

    if publish_date_property_name:
        properties[publish_date_property_name] = {
            "date": {"start": dt.datetime.now(dt.timezone.utc).date().isoformat()}
        }

    payload = {"properties": properties}

    if dry_run:
        return {"dry_run": True, "payload": payload}

    return http_json(
        "PATCH",
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=notion_headers(notion_token),
        payload=payload,
    )


def notion_rich_text(text: str) -> List[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []
    chunks = [text[i : i + 1800] for i in range(0, len(text), 1800)]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks[:10]]


def resolve_option_name(preferred: str, options: List[str]) -> str:
    preferred = (preferred or "").strip()
    if not preferred:
        return options[0] if options else preferred
    if not options:
        return preferred
    by_lower = {name.lower(): name for name in options}
    return by_lower.get(preferred.lower(), options[0])


def publication_site_payload(prop_type: str, prop_meta: Dict[str, Any], site_label: str) -> Dict[str, Any]:
    if prop_type == "multi_select":
        return {"multi_select": [{"name": site_label}]}
    if prop_type == "select":
        options = extract_status_options(prop_meta, "select")
        return {"select": {"name": resolve_option_name(site_label, options)}}
    if prop_type == "rich_text":
        return {"rich_text": notion_rich_text(site_label)}
    raise SystemExit(f"Unsupported publication site property type: {prop_type}")


def publication_post_id_payload(prop_type: str, wp_post_id: Optional[int]) -> Dict[str, Any]:
    if wp_post_id is None:
        if prop_type == "number":
            return {"number": None}
        if prop_type == "rich_text":
            return {"rich_text": []}
        return {}
    if prop_type == "number":
        return {"number": wp_post_id}
    if prop_type == "rich_text":
        return {"rich_text": notion_rich_text(str(wp_post_id))}
    return {}


def create_publication_log_entry(
    notion_token: str,
    publications_db_id: str,
    *,
    article_page_id: str,
    article_title: str,
    site_label: str,
    wp_post_id: Optional[int],
    wp_link: str,
    illustration_url: str,
    dry_run: bool,
) -> Dict[str, Any]:
    publications_db_id = (publications_db_id or "").strip()
    if not publications_db_id:
        return {"skipped": True, "reason": "No publications DB ID configured"}

    schema = load_db_schema(notion_token, publications_db_id)
    props = schema.get("properties", {})

    title_prop = pick_property(props, ["Title", "Name"], ("title",))
    article_relation_prop = pick_property(
        props,
        ["Article", "My Article", "Content", "Post", "Article Page"],
        ("relation",),
        allow_fallback=False,
    )
    site_prop = pick_property(
        props,
        ["Site", "Website", "Platform", "Channel", "Published On Site", "Publish Site"],
        ("select", "multi_select", "rich_text"),
        allow_fallback=False,
    )
    status_prop = pick_property(props, ["Status"], ("status", "select"), allow_fallback=False)
    post_id_prop = pick_property(
        props,
        ["WP Post ID", "WordPress Post ID", "Post ID"],
        ("number", "rich_text"),
        allow_fallback=False,
    )
    published_url_prop = pick_property(
        props,
        ["Published URL", "Post URL", "URL", "WordPress URL"],
        ("url",),
        allow_fallback=False,
    )
    published_at_prop = pick_property(
        props,
        ["Published At", "Publish Date", "Published Date"],
        ("date",),
        allow_fallback=False,
    )
    illustration_url_prop = pick_property(
        props,
        ["Illustration URL", "Featured Image URL", "Image URL"],
        ("url",),
        allow_fallback=False,
    )

    properties: Dict[str, Any] = {}

    if title_prop:
        properties[title_prop[0]] = {
            "title": notion_rich_text(f"{article_title} · {site_label}") or notion_rich_text(article_title)
        }
    if article_relation_prop:
        properties[article_relation_prop[0]] = {"relation": [{"id": article_page_id}]}
    if site_prop:
        properties[site_prop[0]] = publication_site_payload(site_prop[1], props.get(site_prop[0], {}), site_label)
    if status_prop:
        options = extract_status_options(props.get(status_prop[0], {}), status_prop[1])
        if status_prop[1] == "status":
            properties[status_prop[0]] = {"status": {"name": resolve_option_name("Published", options)}}
        else:
            properties[status_prop[0]] = {"select": {"name": resolve_option_name("Published", options)}}
    if post_id_prop:
        payload = publication_post_id_payload(post_id_prop[1], wp_post_id)
        if payload:
            properties[post_id_prop[0]] = payload
    if published_url_prop and wp_link:
        properties[published_url_prop[0]] = {"url": wp_link}
    if published_at_prop:
        properties[published_at_prop[0]] = {
            "date": {"start": dt.datetime.now(dt.timezone.utc).date().isoformat()}
        }
    if illustration_url_prop and illustration_url:
        properties[illustration_url_prop[0]] = {"url": illustration_url}

    payload = {"parent": {"database_id": publications_db_id}, "properties": properties}
    if dry_run:
        return {"dry_run": True, "payload": payload}

    result = http_json(
        "POST",
        f"{NOTION_API_BASE}/pages",
        headers=notion_headers(notion_token),
        payload=payload,
    )
    return {"id": result.get("id"), "url": result.get("url")}


def main() -> None:
    args = parse_args()

    notion_token = require(args.notion_token, "--notion-token or NOTION_TOKEN")
    articles_db_id = require(args.articles_db_id, "--articles-db-id or MY_ARTICLES_DB_ID")
    sites = load_sites_config(args.sites_config)

    requested_site_key, requested_site_cfg = resolve_site_config(args.site, sites)
    if (args.site or "").strip():
        if sites and not requested_site_key:
            known = ", ".join(sorted(sites.keys()))
            raise SystemExit(
                f"Unknown site '{args.site}'. Available site keys: {known}"
            )
        if not requested_site_key:
            requested_site_key = normalize_site_key(args.site)
            requested_site_cfg = None

    default_site_key, default_site_cfg = resolve_site_config(args.default_site_key, sites)
    if (args.default_site_key or "").strip():
        if sites and not default_site_key:
            known = ", ".join(sorted(sites.keys()))
            raise SystemExit(
                f"Unknown default site '{args.default_site_key}'. Available site keys: {known}"
            )
        if not default_site_key:
            default_site_key = normalize_site_key(args.default_site_key)
            default_site_cfg = None

    schema = load_db_schema(notion_token, articles_db_id)
    props = schema.get("properties", {})

    title_prop = pick_property(props, ["Title", "Name"], ("title",))
    status_prop = pick_property(props, ["Status"], ("status", "select"))
    content_prop = pick_property(
        props,
        ["Content", "Body", "Article", "Markdown"],
        ("rich_text",),
        allow_fallback=False,
    )
    slug_prop = pick_property(props, ["Slug"], ("rich_text",), allow_fallback=False)
    summary_prop = pick_property(
        props,
        ["Summary", "Excerpt"],
        ("rich_text",),
        allow_fallback=False,
    )
    illustration_prompt_prop = pick_property(
        props,
        ["Illustration Prompt", "Image Prompt", "Visual Prompt"],
        ("rich_text",),
        allow_fallback=False,
    )
    illustration_url_prop = pick_property(
        props,
        [
            "Illustration URL",
            "Featured Image URL",
            "Hero Image URL",
            "Cover Image URL",
            "Image URL",
        ],
        ("url",),
        allow_fallback=False,
    )
    published_url_prop = pick_property(
        props,
        ["Published URL", "WordPress URL", "Post URL", "URL"],
        ("url",),
        allow_fallback=False,
    )
    published_platforms_prop = pick_property(
        props,
        [
            "Published Platforms",
            "Published On",
            "Platforms Published",
            "Published To",
            "Live On",
        ],
        ("multi_select", "select", "rich_text"),
        allow_fallback=False,
    )
    required_platforms_prop = pick_property(
        props,
        [
            "Required Platforms",
            "Target Platforms",
            "Publish Targets",
            "Target Channels",
            "Publish On",
            "Channels",
        ],
        ("multi_select", "select", "rich_text"),
        allow_fallback=False,
    )
    category_prop = pick_property(
        props,
        [
            "Category",
            "Categories",
            "Catégorie",
            "Catégories",
            "Topic",
            "Topics",
            "Theme",
            "Themes",
        ],
        ("multi_select", "select", "rich_text"),
        allow_fallback=False,
    )
    tags_prop = pick_property(
        props,
        [
            "Tags",
            "Tag",
            "Mots-clés",
            "Mots clés",
            "Keywords",
            "Keyword",
            "Labels",
            "Etiquettes",
            "Étiquettes",
        ],
        ("multi_select", "select", "rich_text"),
        allow_fallback=False,
    )
    target_site_prop = pick_property(
        props,
        [
            "Target Site",
            "Publish Site",
            "Site",
            "Website",
            "WordPress Site",
            "Target Website",
            "Publication Site",
            "Publish To Site",
        ],
        ("multi_select", "select", "rich_text"),
        allow_fallback=False,
    )
    publish_date_prop = pick_property(
        props,
        ["Publish Date", "Published Date"],
        ("date",),
        allow_fallback=False,
    )
    if category_prop and tags_prop and category_prop[0] == tags_prop[0]:
        tags_prop = None

    if not title_prop:
        raise SystemExit("My Articles DB has no title property")
    if not status_prop:
        raise SystemExit("My Articles DB has no Status property of type status/select")

    status_name, status_type = status_prop
    site_key_for_draft_filter = requested_site_key or default_site_key
    page = query_latest_draft_page(
        notion_token,
        articles_db_id,
        status_property_name=status_name,
        draft_status=args.draft_status,
        page_size=args.page_size,
        selected_site_key=site_key_for_draft_filter,
        target_site_property_name=target_site_prop[0] if target_site_prop else None,
        sites=sites,
    )

    selected_site_key = requested_site_key
    selected_site_cfg = requested_site_cfg

    if not selected_site_key:
        row_site_key, row_site_cfg, _ = resolve_site_from_row(
            page,
            target_site_prop[0] if target_site_prop else None,
            sites,
        )
        if row_site_key:
            selected_site_key = row_site_key
            selected_site_cfg = row_site_cfg

    if not selected_site_key:
        selected_site_key = default_site_key
        selected_site_cfg = default_site_cfg

    if not selected_site_key and sites:
        if len(sites) == 1:
            selected_site_key = next(iter(sites))
            selected_site_cfg = sites[selected_site_key]
        else:
            known = ", ".join(sorted(sites.keys()))
            raise SystemExit(
                "Multiple WordPress sites are configured but no target site was resolved. "
                "Set --site or fill a Notion 'Target Site' style property. "
                f"Available site keys: {known}"
            )

    wordpress_site, wp_username, wp_app_password = resolve_wordpress_credentials(
        site_cfg=selected_site_cfg,
        wordpress_site_cli=args.wordpress_site,
        wp_username_cli=args.wp_username,
        wp_password_cli=args.wp_app_password,
    )
    wordpress_site = require(wordpress_site, "--wordpress-site or WORDPRESS_SITE")
    wp_username = require(wp_username, "--wp-username or WP_USERNAME")
    wp_app_password = require(
        wp_app_password,
        "--wp-app-password or WP_APP_PASSWORD",
    )
    platform_name = choose_platform_name(
        args.platform_name,
        selected_site_cfg,
        selected_site_key,
    )
    brand_profiles = load_brand_profiles(args.brand_profiles_dir)
    selected_brand_profile_id, selected_brand_profile = resolve_brand_profile(
        explicit_brand_profile=args.brand_profile,
        site_cfg=selected_site_cfg,
        site_key=selected_site_key,
        profiles_by_alias=brand_profiles,
    )
    site_label = (
        ((selected_site_cfg or {}).get("notion_site_label") or "").strip()
        or platform_name
    )

    page_id = page.get("id", "")
    title = extract_property_text(page, title_prop[0]).strip() or "Untitled"
    slug = extract_property_text(page, slug_prop[0]).strip() if slug_prop else ""
    excerpt = extract_property_text(page, summary_prop[0]).strip() if summary_prop else ""
    illustration_prompt = (
        extract_property_text(page, illustration_prompt_prop[0]).strip()
        if illustration_prompt_prop
        else ""
    )
    existing_illustration_url = (
        extract_property_url(page, illustration_url_prop[0]).strip()
        if illustration_url_prop
        else ""
    )
    notion_categories = (
        extract_property_tags(page, category_prop[0])
        if category_prop
        else []
    )
    notion_tags = (
        extract_property_tags(page, tags_prop[0])
        if tags_prop
        else []
    )
    current_published_platforms = (
        extract_property_tags(page, published_platforms_prop[0])
        if published_platforms_prop
        else []
    )
    required_platforms = (
        extract_property_tags(page, required_platforms_prop[0])
        if required_platforms_prop
        else []
    )
    published_platforms_after = sorted(
        {name for name in [*current_published_platforms, platform_name] if (name or "").strip()}
    )
    status_options = extract_status_options(props.get(status_name, {}), status_type)
    resolved_status_after_publish = decide_status_after_publish(
        published_platforms_after=published_platforms_after,
        required_platforms=required_platforms,
        published_status=args.published_status,
        partially_published_status=args.partially_published_status,
        status_options=status_options,
    )
    content_html = build_article_content_html(
        notion_token,
        page,
        content_prop[0] if content_prop else None,
    )
    # WordPress theme already renders the post title; drop duplicated leading <h1>.
    content_html = strip_duplicate_leading_h1(content_html, title)
    category_ids, resolved_category_terms, category_resolution_source = resolve_wordpress_categories(
        wordpress_site=wordpress_site,
        username=wp_username,
        app_password=wp_app_password,
        site_cfg=selected_site_cfg,
        title=title,
        excerpt=excerpt,
        content_html=content_html,
        notion_categories=notion_categories,
        notion_tags=notion_tags,
    )
    resolved_category_names = unique_non_empty(
        [html.unescape(str((term or {}).get("name") or "").strip()) for term in resolved_category_terms]
    )

    content_has_image = has_inline_image(content_html)
    illustration_status = "already_present" if content_has_image else "none"
    illustration_url = ""
    illustration_media_id: Optional[int] = None
    prepend_illustration = False

    if not args.skip_illustration and not content_has_image:
        if existing_illustration_url:
            illustration_url = existing_illustration_url
            illustration_status = "reused_existing_url"
        else:
            prompt = build_illustration_prompt(
                title=title,
                excerpt=excerpt,
                content_html=content_html,
                custom_prompt=illustration_prompt,
                brand_profile=selected_brand_profile,
            )
            image_bytes, mime_type = generate_illustration_image(
                args.openai_api_key,
                prompt=prompt,
                model=args.image_model,
                size=args.image_size,
                quality=args.image_quality,
                dry_run=args.dry_run,
            )
            ext = guess_extension_from_mime(mime_type)
            filename = f"{slugify(slug or title)}-illustration{ext}"
            media = upload_media_to_wordpress(
                wordpress_site,
                wp_username,
                wp_app_password,
                filename=filename,
                image_bytes=image_bytes,
                content_type=mime_type,
                dry_run=args.dry_run,
            )
            illustration_url = (media.get("source_url") or "").strip()
            media_id = media.get("id")
            if isinstance(media_id, int):
                illustration_media_id = media_id
            illustration_status = "generated"

        if illustration_url and not illustration_media_id:
            prepend_illustration = True

        if prepend_illustration and illustration_url:
            content_html = prepend_image_to_content(content_html, illustration_url, title)
    elif args.skip_illustration:
        illustration_status = "skipped_by_flag"

    wp_payload: Dict[str, Any] = {
        "title": title,
        "content": content_html,
        "status": "publish",
    }
    if illustration_media_id:
        wp_payload["featured_media"] = illustration_media_id
    if slug:
        wp_payload["slug"] = slug
    if excerpt:
        wp_payload["excerpt"] = excerpt
    if category_ids:
        wp_payload["categories"] = category_ids

    wp_response = publish_to_wordpress(
        wordpress_site,
        wp_username,
        wp_app_password,
        wp_payload,
        dry_run=args.dry_run,
    )
    wp_link = (wp_response.get("link") or "").strip()

    update_response = update_notion_page_after_publish(
        notion_token,
        page_id,
        status_property_name=status_name,
        status_property_type=status_type,
        status_to_set=resolved_status_after_publish,
        published_url_property_name=published_url_prop[0] if published_url_prop else None,
        published_platforms_property_name=(
            published_platforms_prop[0] if published_platforms_prop else None
        ),
        published_platforms_property_type=(
            published_platforms_prop[1] if published_platforms_prop else None
        ),
        current_published_platforms=current_published_platforms,
        platform_name=platform_name,
        category_property_name=category_prop[0] if category_prop else None,
        category_property_type=category_prop[1] if category_prop else None,
        category_values=resolved_category_names,
        illustration_url_property_name=illustration_url_prop[0] if illustration_url_prop else None,
        publish_date_property_name=publish_date_prop[0] if publish_date_prop else None,
        wordpress_link=wp_link,
        illustration_url=illustration_url,
        dry_run=args.dry_run,
    )
    publication_log_response = create_publication_log_entry(
        notion_token,
        args.publications_db_id,
        article_page_id=page_id,
        article_title=title,
        site_label=site_label,
        wp_post_id=wp_response.get("id"),
        wp_link=wp_link,
        illustration_url=illustration_url,
        dry_run=args.dry_run,
    )

    result = {
        "dry_run": args.dry_run,
        "notion_page_id": page_id,
        "title": title,
        "site_key": selected_site_key,
        "site_label": site_label,
        "brand_profile_id": selected_brand_profile_id,
        "brand_profile_name": (
            (selected_brand_profile or {}).get("brand_name") if selected_brand_profile else None
        ),
        "wordpress_site": wordpress_site,
        "wordpress_post_id": wp_response.get("id"),
        "wordpress_link": wp_link,
        "notion_status_set_to": resolved_status_after_publish,
        "platform_name": platform_name,
        "required_platforms": required_platforms,
        "published_platforms_before": current_published_platforms,
        "published_platforms_after": published_platforms_after,
        "notion_categories_before": notion_categories,
        "notion_tags": notion_tags,
        "category_resolution_source": category_resolution_source,
        "wordpress_category_ids": category_ids,
        "wordpress_categories": [
            {
                "id": term.get("id"),
                "slug": term.get("slug"),
                "name": html.unescape(str(term.get("name") or "")).strip(),
            }
            for term in resolved_category_terms
        ],
        "notion_category_property": category_prop[0] if category_prop else None,
        "notion_categories_after": resolved_category_names,
        "illustration_status": illustration_status,
        "illustration_url": illustration_url,
        "illustration_media_id": illustration_media_id,
        "illustration_placement": (
            "featured_media"
            if illustration_media_id
            else ("inline_prepended" if prepend_illustration else "unchanged")
        ),
        "publication_log": publication_log_response,
    }

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Page ID: {page_id}")
    print(f"Title: {title}")
    if selected_site_key:
        print(f"Target site key: {selected_site_key}")
    if selected_brand_profile_id:
        print(f"Brand profile: {selected_brand_profile_id}")
    print(f"Target WordPress site: {wordpress_site}")
    print(f"WordPress post ID: {wp_response.get('id')}")
    print(f"WordPress link: {wp_link or '(none)'}")
    if resolved_category_names:
        print(
            "WordPress categories: "
            + ", ".join(resolved_category_names)
            + f" ({category_resolution_source})"
        )
    else:
        print(f"WordPress categories: none ({category_resolution_source})")
    print(f"Illustration: {illustration_status}")
    if illustration_url:
        print(f"Illustration URL: {illustration_url}")
    print(f"Notion status updated to: {resolved_status_after_publish}")
    if required_platforms:
        print(f"Required platforms: {', '.join(sorted(required_platforms))}")
    if published_platforms_prop:
        print(f"Published platforms: {', '.join(published_platforms_after)}")
    if publication_log_response.get("id"):
        print(f"Publication log page ID: {publication_log_response.get('id')}")
    if args.dry_run:
        print("Dry run completed; no external changes were made.")

    # Keep these available for debugging without printing full payloads by default.
    _ = (update_response, publication_log_response)


if __name__ == "__main__":
    main()
