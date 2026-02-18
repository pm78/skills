#!/usr/bin/env python3
"""Publish the latest eligible article from Notion My Articles to LinkedIn."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_MY_ARTICLES_DB_ID = "1dc11393-09f8-8049-82eb-e18d8d012f96"
LINKEDIN_UGC_ENDPOINT = "https://api.linkedin.com/v2/ugcPosts"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Publish latest eligible article from Notion My Articles to LinkedIn"
    )
    p.add_argument("--notion-token", default=os.getenv("NOTION_TOKEN", ""))
    p.add_argument(
        "--articles-db-id",
        default=os.getenv("MY_ARTICLES_DB_ID", DEFAULT_MY_ARTICLES_DB_ID),
    )
    p.add_argument(
        "--linkedin-access-token",
        default=os.getenv("LINKEDIN_ACCESS_TOKEN", ""),
    )
    p.add_argument(
        "--linkedin-author-urn",
        default=os.getenv("LINKEDIN_AUTHOR_URN", ""),
    )
    p.add_argument("--draft-status", default="draft")
    p.add_argument("--partially-published-status", default="partially_published")
    p.add_argument("--published-status", default="published")
    p.add_argument(
        "--candidate-statuses",
        default="draft,partially_published,published",
        help="Comma-separated status names eligible for LinkedIn publish selection",
    )
    p.add_argument("--platform-name", default="LinkedIn")
    p.add_argument("--visibility", default="PUBLIC")
    p.add_argument("--max-post-length", type=int, default=2900)
    p.add_argument("--page-size", type=int, default=25)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--print-json", action="store_true")
    return p.parse_args()


def require(value: str, label: str) -> str:
    out = (value or "").strip()
    if not out:
        raise SystemExit(f"Missing required value: {label}")
    return out


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
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        raise SystemExit(f"HTTP {exc.code} for {method} {url}: {detail[:500]}") from exc


def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
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
        prop = properties.get(preferred)
        if prop and prop.get("type") in allowed_types:
            return preferred, prop.get("type")
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
        return [
            ((item or {}).get("name") or "").strip()
            for item in (prop.get("multi_select") or [])
            if ((item or {}).get("name") or "").strip()
        ]
    if ptype == "select":
        name = ((prop.get("select") or {}).get("name") or "").strip()
        return [name] if name else []
    if ptype == "rich_text":
        raw = rich_text_to_plain(prop.get("rich_text", []))
        return [part.strip() for part in re.split(r"[,;|]", raw) if part.strip()]

    return []


def fetch_block_children(notion_token: str, block_id: str) -> List[Dict[str, Any]]:
    children: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        params: Dict[str, str] = {"page_size": "100"}
        if cursor:
            params["start_cursor"] = cursor
        query = urllib.parse.urlencode(params)
        data = http_json(
            "GET",
            f"{NOTION_API_BASE}/blocks/{block_id}/children?{query}",
            headers=notion_headers(notion_token),
        )
        children.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return children


def extract_plain_content(
    notion_token: str,
    row: Dict[str, Any],
    content_property_name: Optional[str],
) -> str:
    if content_property_name:
        text = extract_property_text(row, content_property_name).strip()
        if text:
            return text

    parts: List[str] = []
    for block in fetch_block_children(notion_token, row.get("id", "")):
        btype = block.get("type", "")
        payload = block.get(btype, {})
        text = rich_text_to_plain(payload.get("rich_text", []))
        if text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()


def parse_csv_set(value: str) -> set[str]:
    return {item.strip().lower() for item in (value or "").split(",") if item.strip()}


def query_latest_eligible_page(
    notion_token: str,
    db_id: str,
    *,
    status_property_name: str,
    published_platforms_property_name: Optional[str],
    required_platforms_property_name: Optional[str],
    candidate_statuses: set[str],
    platform_name: str,
    page_size: int,
) -> Dict[str, Any]:
    cursor: Optional[str] = None
    size = max(1, min(page_size, 100))
    platform_lower = platform_name.lower()

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
            props = row.get("properties", {})
            status = status_name_from_property(props.get(status_property_name, {})).lower()
            if status not in candidate_statuses:
                continue

            current_published = (
                extract_property_tags(row, published_platforms_property_name)
                if published_platforms_property_name
                else []
            )
            if platform_lower in {name.lower() for name in current_published}:
                continue

            required = (
                extract_property_tags(row, required_platforms_property_name)
                if required_platforms_property_name
                else []
            )
            if required and platform_lower not in {name.lower() for name in required}:
                continue

            return row

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    raise SystemExit(
        f"No eligible article found for platform '{platform_name}' with statuses: {sorted(candidate_statuses)}"
    )


def build_linkedin_post_text(
    *,
    title: str,
    summary: str,
    content: str,
    manual_text: str,
    article_url: str,
    max_len: int,
) -> str:
    if manual_text.strip():
        text = manual_text.strip()
    else:
        plain = re.sub(r"\s+", " ", content or "").strip()
        snippet = plain[:1200].strip()
        parts = [title.strip()]
        if summary.strip():
            parts.append("")
            parts.append(summary.strip())
        if snippet:
            parts.append("")
            parts.append(snippet)
        text = "\n".join(part for part in parts if part is not None).strip()

    if article_url.strip() and article_url not in text:
        text = (text + "\n\nRead more: " + article_url.strip()).strip()

    if len(text) <= max_len:
        return text

    clipped = text[: max_len - 1].rstrip()
    return clipped + "…"


def post_to_linkedin(
    access_token: str,
    *,
    author_urn: str,
    post_text: str,
    visibility: str,
    dry_run: bool,
) -> Dict[str, Any]:
    if dry_run:
        fake_urn = "urn:li:ugcPost:dry-run"
        return {
            "id": fake_urn,
            "post_url": linkedin_post_url_from_urn(fake_urn),
            "dry_run": True,
        }

    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": post_text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    req = urllib.request.Request(
        LINKEDIN_UGC_ENDPOINT,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            urn = (data.get("id") or "").strip() or (resp.headers.get("x-restli-id") or "").strip()
            if urn and not urn.startswith("urn:li:"):
                urn = f"urn:li:ugcPost:{urn}"
            return {
                "id": urn,
                "post_url": linkedin_post_url_from_urn(urn),
            }
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        raise SystemExit(
            f"HTTP {exc.code} for POST {LINKEDIN_UGC_ENDPOINT}: {detail[:700]}"
        ) from exc

    raise SystemExit("LinkedIn publish returned no response")


def linkedin_post_url_from_urn(urn: str) -> str:
    raw = (urn or "").strip()
    if not raw:
        return ""
    if raw.startswith("urn:li:"):
        return f"https://www.linkedin.com/feed/update/{raw}/"
    return f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{raw}/"


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
    merged = sorted(
        {name for name in [*current_platforms, platform_name] if (name or "").strip()}
    )

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


def update_notion_after_publish(
    notion_token: str,
    *,
    page_id: str,
    status_property_name: str,
    status_property_type: str,
    status_to_set: str,
    linkedin_url_property_name: Optional[str],
    published_platforms_property_name: Optional[str],
    published_platforms_property_type: Optional[str],
    current_published_platforms: List[str],
    platform_name: str,
    publish_date_property_name: Optional[str],
    linkedin_url: str,
    dry_run: bool,
) -> Dict[str, Any]:
    properties: Dict[str, Any] = {
        status_property_name: notion_status_property_payload(status_property_type, status_to_set)
    }

    if linkedin_url_property_name and linkedin_url:
        properties[linkedin_url_property_name] = {"url": linkedin_url}

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
    access_token = (args.linkedin_access_token or "").strip()
    author_urn = (args.linkedin_author_urn or "").strip()
    if not args.dry_run:
        access_token = require(
            access_token,
            "--linkedin-access-token or LINKEDIN_ACCESS_TOKEN",
        )
        author_urn = require(
            author_urn,
            "--linkedin-author-urn or LINKEDIN_AUTHOR_URN",
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
    summary_prop = pick_property(
        props,
        ["Summary", "Excerpt"],
        ("rich_text",),
        allow_fallback=False,
    )
    linkedin_post_prop = pick_property(
        props,
        ["LinkedIn Post", "LinkedIn Caption", "Social Post", "Social Caption"],
        ("rich_text",),
        allow_fallback=False,
    )
    article_url_prop = pick_property(
        props,
        ["Published URL", "WordPress URL", "Post URL", "URL"],
        ("url",),
        allow_fallback=False,
    )
    linkedin_url_prop = pick_property(
        props,
        ["LinkedIn URL", "Linkedin URL", "LinkedIn Post URL"],
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
    candidate_statuses = parse_csv_set(args.candidate_statuses)
    if not candidate_statuses:
        raise SystemExit("--candidate-statuses cannot be empty")

    page = query_latest_eligible_page(
        notion_token,
        articles_db_id,
        status_property_name=status_name,
        published_platforms_property_name=(
            published_platforms_prop[0] if published_platforms_prop else None
        ),
        required_platforms_property_name=(
            required_platforms_prop[0] if required_platforms_prop else None
        ),
        candidate_statuses=candidate_statuses,
        platform_name=args.platform_name,
        page_size=args.page_size,
    )

    page_id = page.get("id", "")
    title = extract_property_text(page, title_prop[0]).strip() or "Untitled"
    summary = extract_property_text(page, summary_prop[0]).strip() if summary_prop else ""
    manual_post = (
        extract_property_text(page, linkedin_post_prop[0]).strip()
        if linkedin_post_prop
        else ""
    )
    article_url = (
        extract_property_url(page, article_url_prop[0]).strip()
        if article_url_prop
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

    content = extract_plain_content(
        notion_token,
        page,
        content_prop[0] if content_prop else None,
    )
    if not (manual_post or summary or content):
        raise SystemExit("Selected article has no usable LinkedIn content (post/summary/content empty)")

    post_text = build_linkedin_post_text(
        title=title,
        summary=summary,
        content=content,
        manual_text=manual_post,
        article_url=article_url,
        max_len=max(300, args.max_post_length),
    )

    linkedin_response = post_to_linkedin(
        access_token,
        author_urn=author_urn,
        post_text=post_text,
        visibility=args.visibility,
        dry_run=args.dry_run,
    )
    linkedin_url = (linkedin_response.get("post_url") or "").strip()
    published_platforms_after = sorted(
        {
            name
            for name in [*current_published_platforms, args.platform_name]
            if (name or "").strip()
        }
    )
    status_options = extract_status_options(props.get(status_name, {}), status_type)
    resolved_status_after_publish = decide_status_after_publish(
        published_platforms_after=published_platforms_after,
        required_platforms=required_platforms,
        published_status=args.published_status,
        partially_published_status=args.partially_published_status,
        status_options=status_options,
    )

    update_response = update_notion_after_publish(
        notion_token,
        page_id=page_id,
        status_property_name=status_name,
        status_property_type=status_type,
        status_to_set=resolved_status_after_publish,
        linkedin_url_property_name=linkedin_url_prop[0] if linkedin_url_prop else None,
        published_platforms_property_name=(
            published_platforms_prop[0] if published_platforms_prop else None
        ),
        published_platforms_property_type=(
            published_platforms_prop[1] if published_platforms_prop else None
        ),
        current_published_platforms=current_published_platforms,
        platform_name=args.platform_name,
        publish_date_property_name=publish_date_prop[0] if publish_date_prop else None,
        linkedin_url=linkedin_url,
        dry_run=args.dry_run,
    )

    result = {
        "dry_run": args.dry_run,
        "notion_page_id": page_id,
        "title": title,
        "linkedin_post_id": linkedin_response.get("id"),
        "linkedin_url": linkedin_url,
        "notion_status_set_to": resolved_status_after_publish,
        "required_platforms": required_platforms,
        "published_platforms_before": current_published_platforms,
        "published_platforms_after": published_platforms_after,
        "post_length": len(post_text),
    }

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Page ID: {page_id}")
    print(f"Title: {title}")
    print(f"LinkedIn post ID: {linkedin_response.get('id')}")
    print(f"LinkedIn URL: {linkedin_url or '(none)'}")
    print(f"Post length: {len(post_text)}")
    print(f"Notion status updated to: {resolved_status_after_publish}")
    if required_platforms:
        print(f"Required platforms: {', '.join(sorted(required_platforms))}")
    if published_platforms_prop:
        print(f"Published platforms: {', '.join(published_platforms_after)}")
    if args.dry_run:
        print("Dry run completed; no external changes were made.")

    _ = update_response


if __name__ == "__main__":
    main()
