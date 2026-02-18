#!/usr/bin/env python3
"""Publish the latest draft article from Notion My Articles to WordPress."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_WORDPRESS_SITE = "https://thrivethroughtime.com"
DEFAULT_MY_ARTICLES_DB_ID = "1dc11393-09f8-8049-82eb-e18d8d012f96"


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
    parser.add_argument("--draft-status", default="draft")
    parser.add_argument("--published-status", default="published")
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


def basic_markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    html_parts: List[str] = []
    list_items: List[str] = []
    active_list: Optional[str] = None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        bullet_match = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered_match = re.match(r"^\d+\.\s+(.*)$", stripped)

        if bullet_match:
            if active_list != "ul":
                flush_list(list_items, active_list, html_parts)
                active_list = "ul"
            list_items.append(f"<li>{html.escape(bullet_match.group(1))}</li>")
            continue

        if numbered_match:
            if active_list != "ol":
                flush_list(list_items, active_list, html_parts)
                active_list = "ol"
            list_items.append(f"<li>{html.escape(numbered_match.group(1))}</li>")
            continue

        flush_list(list_items, active_list, html_parts)
        active_list = None

        if not stripped:
            continue
        if stripped.startswith("### "):
            html_parts.append(f"<h3>{html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            html_parts.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        else:
            html_parts.append(f"<p>{html.escape(stripped)}</p>")

    flush_list(list_items, active_list, html_parts)
    return "\n".join(html_parts).strip()


def markdown_to_html(markdown_text: str) -> str:
    text = (markdown_text or "").strip()
    if not text:
        return ""

    if re.search(r"<\s*(p|h[1-6]|ul|ol|li|blockquote|pre|code)\b", text, re.IGNORECASE):
        return text

    try:
        import markdown as md  # type: ignore

        return md.markdown(text, extensions=["extra", "sane_lists"])
    except Exception:
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


def update_notion_page_after_publish(
    notion_token: str,
    page_id: str,
    *,
    status_property_name: str,
    status_property_type: str,
    published_status: str,
    published_url_property_name: Optional[str],
    publish_date_property_name: Optional[str],
    wordpress_link: str,
    dry_run: bool,
) -> Dict[str, Any]:
    properties: Dict[str, Any] = {
        status_property_name: notion_status_property_payload(
            status_property_type, published_status
        )
    }

    if published_url_property_name and wordpress_link:
        properties[published_url_property_name] = {"url": wordpress_link}

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
    published_url_prop = pick_property(
        props,
        ["Published URL", "WordPress URL", "Post URL", "URL"],
        ("url",),
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
    content_html = build_article_content_html(
        notion_token,
        page,
        content_prop[0] if content_prop else None,
    )

    wp_payload: Dict[str, Any] = {
        "title": title,
        "content": content_html,
        "status": "publish",
    }
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
        published_status=args.published_status,
        published_url_property_name=published_url_prop[0] if published_url_prop else None,
        publish_date_property_name=publish_date_prop[0] if publish_date_prop else None,
        wordpress_link=wp_link,
        dry_run=args.dry_run,
    )

    result = {
        "dry_run": args.dry_run,
        "notion_page_id": page_id,
        "title": title,
        "wordpress_post_id": wp_response.get("id"),
        "wordpress_link": wp_link,
        "notion_status_set_to": args.published_status,
    }

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Page ID: {page_id}")
    print(f"Title: {title}")
    print(f"WordPress post ID: {wp_response.get('id')}")
    print(f"WordPress link: {wp_link or '(none)'}")
    print(f"Notion status updated to: {args.published_status}")
    if args.dry_run:
        print("Dry run completed; no external changes were made.")

    # Keep these available for debugging without printing full payloads by default.
    _ = update_response


if __name__ == "__main__":
    main()
