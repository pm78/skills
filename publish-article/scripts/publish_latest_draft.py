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
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

NOTION_API_BASE = "https://api.notion.com/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_WORDPRESS_SITE = "https://thrivethroughtime.com"
DEFAULT_MY_ARTICLES_DB_ID = "1dc11393-09f8-8049-82eb-e18d8d012f96"
DEFAULT_IMAGE_MODEL = "gpt-image-1"
DEFAULT_IMAGE_SIZE = "1536x1024"
DEFAULT_IMAGE_QUALITY = "high"


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
        "--wordpress-site",
        default=os.getenv("WORDPRESS_SITE", DEFAULT_WORDPRESS_SITE),
    )
    parser.add_argument(
        "--wp-username",
        default=os.getenv(
            "WP_USERNAME",
            os.getenv("WORDPRESS_USERNAME", os.getenv("WP_APP_USERNAME", "")),
        ),
    )
    parser.add_argument(
        "--wp-app-password",
        default=os.getenv("WP_APP_PASSWORD", os.getenv("WORDPRESS_APP_PASSWORD", "")),
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
    parser.add_argument("--platform-name", default="WordPress")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def require(value: str, label: str) -> str:
    value = (value or "").strip()
    if not value:
        raise SystemExit(f"Missing required value: {label}")
    return value


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
                return row

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    raise SystemExit(
        f"No article found with status '{draft_status}' in My Articles database"
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
        text = html.escape(block_plain_text(block).strip())

        if block_type == "bulleted_list_item":
            if active_list != "ul":
                flush_list(list_items, active_list, html_parts)
                active_list = "ul"
            list_items.append(f"<li>{text}</li>")
            continue

        if block_type == "numbered_list_item":
            if active_list != "ol":
                flush_list(list_items, active_list, html_parts)
                active_list = "ol"
            list_items.append(f"<li>{text}</li>")
            continue

        flush_list(list_items, active_list, html_parts)
        active_list = None

        if block_type == "heading_1":
            html_parts.append(f"<h1>{text}</h1>")
        elif block_type == "heading_2":
            html_parts.append(f"<h2>{text}</h2>")
        elif block_type == "heading_3":
            html_parts.append(f"<h3>{text}</h3>")
        elif block_type == "quote":
            html_parts.append(f"<blockquote>{text}</blockquote>")
        elif block_type == "code":
            html_parts.append(f"<pre><code>{text}</code></pre>")
        elif block_type == "divider":
            html_parts.append("<hr />")
        elif text:
            html_parts.append(f"<p>{text}</p>")

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
        return ""

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

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
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
) -> str:
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()

    plain = re.sub(r"<[^>]+>", " ", content_html or "")
    plain = re.sub(r"\\s+", " ", plain).strip()
    snippet = plain[:900]
    summary = excerpt.strip() if excerpt else ""

    return (
        "Create a single high-quality editorial illustration for a blog article.\n"
        f"Article title: {title}\n"
        f"Article summary: {summary}\n"
        f"Article key points: {snippet}\n"
        "Style: modern editorial illustration, clean composition, professional, optimistic.\n"
        "Constraints: no text, no logos, no watermarks, no brand marks."
    )


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


def main() -> None:
    args = parse_args()

    notion_token = require(args.notion_token, "--notion-token or NOTION_TOKEN")
    articles_db_id = require(args.articles_db_id, "--articles-db-id or MY_ARTICLES_DB_ID")
    wordpress_site = require(args.wordpress_site, "--wordpress-site or WORDPRESS_SITE")
    wp_username = require(args.wp_username, "--wp-username or WP_USERNAME")
    wp_app_password = require(
        args.wp_app_password,
        "--wp-app-password or WP_APP_PASSWORD",
    )

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
    publish_date_prop = pick_property(
        props,
        ["Publish Date", "Published Date"],
        ("date",),
        allow_fallback=False,
    )

    if not title_prop:
        raise SystemExit("My Articles DB has no title property")
    if not status_prop:
        raise SystemExit("My Articles DB has no Status property of type status/select")

    status_name, status_type = status_prop
    page = query_latest_draft_page(
        notion_token,
        articles_db_id,
        status_property_name=status_name,
        draft_status=args.draft_status,
        page_size=args.page_size,
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
        {name for name in [*current_published_platforms, args.platform_name] if (name or "").strip()}
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
        platform_name=args.platform_name,
        illustration_url_property_name=illustration_url_prop[0] if illustration_url_prop else None,
        publish_date_property_name=publish_date_prop[0] if publish_date_prop else None,
        wordpress_link=wp_link,
        illustration_url=illustration_url,
        dry_run=args.dry_run,
    )

    result = {
        "dry_run": args.dry_run,
        "notion_page_id": page_id,
        "title": title,
        "wordpress_post_id": wp_response.get("id"),
        "wordpress_link": wp_link,
        "notion_status_set_to": resolved_status_after_publish,
        "platform_name": args.platform_name,
        "required_platforms": required_platforms,
        "published_platforms_before": current_published_platforms,
        "published_platforms_after": published_platforms_after,
        "illustration_status": illustration_status,
        "illustration_url": illustration_url,
        "illustration_media_id": illustration_media_id,
        "illustration_placement": (
            "featured_media"
            if illustration_media_id
            else ("inline_prepended" if prepend_illustration else "unchanged")
        ),
    }

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Page ID: {page_id}")
    print(f"Title: {title}")
    print(f"WordPress post ID: {wp_response.get('id')}")
    print(f"WordPress link: {wp_link or '(none)'}")
    print(f"Illustration: {illustration_status}")
    if illustration_url:
        print(f"Illustration URL: {illustration_url}")
    print(f"Notion status updated to: {resolved_status_after_publish}")
    if required_platforms:
        print(f"Required platforms: {', '.join(sorted(required_platforms))}")
    if published_platforms_prop:
        print(f"Published platforms: {', '.join(published_platforms_after)}")
    if args.dry_run:
        print("Dry run completed; no external changes were made.")

    # Keep these available for debugging without printing full payloads by default.
    _ = update_response


if __name__ == "__main__":
    main()
