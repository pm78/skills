#!/usr/bin/env python3
"""Generate article/newsletter drafts from Notion Sources into My Articles."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

NOTION_API_BASE = "https://api.notion.com/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Draft article/newsletter from Notion Sources")
    p.add_argument("--sources-db-id", default=os.getenv("SOURCES_DB_ID", ""))
    p.add_argument("--articles-db-id", default=os.getenv("MY_ARTICLES_DB_ID", "1dc11393-09f8-8049-82eb-e18d8d012f96"))
    p.add_argument("--notion-token", default=os.getenv("NOTION_TOKEN", ""))
    p.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.1-mini"))
    p.add_argument("--topic", required=True)
    p.add_argument("--mode", choices=["article", "newsletter"], default="article")
    p.add_argument("--hours", type=int, default=168)
    p.add_argument("--max-sources", type=int, default=20)
    p.add_argument("--author", default="Pascal Mauze")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_date_days_ago(hours: int) -> str:
    return (now_utc() - dt.timedelta(hours=hours)).date().isoformat()


def http_json(method: str, url: str, *, headers: Optional[Dict[str, str]] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def rich_text_chunks(text: str, max_len: int = 1900, max_chunks: int = 40) -> List[Dict[str, Any]]:
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
    chunks = chunks[:max_chunks] or [""]
    return [{"type": "text", "text": {"content": c}} for c in chunks]


def load_db_schema(token: str, db_id: str) -> Dict[str, Any]:
    return http_json("GET", f"{NOTION_API_BASE}/databases/{db_id}", headers=notion_headers(token))


def find_property_name(props: Dict[str, Any], preferred: str, ptype: str) -> Optional[str]:
    if preferred in props and props[preferred].get("type") == ptype:
        return preferred
    for name, meta in props.items():
        if meta.get("type") == ptype:
            return name
    return None


def query_sources(token: str, db_id: str, topic: str, hours: int, max_sources: int) -> List[Dict[str, Any]]:
    payload = {
        "filter": {
            "and": [
                {"property": "Captured Date", "date": {"on_or_after": iso_date_days_ago(hours)}},
                {"property": "Tags", "multi_select": {"contains": topic}},
            ]
        },
        "sorts": [{"property": "Published Date", "direction": "descending"}],
        "page_size": max_sources,
    }
    data = http_json(
        "POST",
        f"{NOTION_API_BASE}/databases/{db_id}/query",
        headers=notion_headers(token),
        payload=payload,
    )
    return data.get("results", [])


def extract_source_row(row: Dict[str, Any]) -> Dict[str, str]:
    p = row.get("properties", {})

    def title(name: str) -> str:
        return "".join(x.get("plain_text", "") for x in p.get(name, {}).get("title", []))

    def rtext(name: str) -> str:
        return "".join(x.get("plain_text", "") for x in p.get(name, {}).get("rich_text", []))

    def url(name: str) -> str:
        return p.get(name, {}).get("url") or ""

    def datev(name: str) -> str:
        d = p.get(name, {}).get("date") or {}
        return d.get("start") or ""

    def select(name: str) -> str:
        s = p.get(name, {}).get("select") or {}
        return s.get("name") or ""

    return {
        "id": row.get("id", ""),
        "title": title("Title"),
        "url": url("URL"),
        "summary": rtext("Summary"),
        "source_name": rtext("Source Name"),
        "published_date": datev("Published Date"),
        "type": select("Type"),
    }


def generate_draft(
    api_key: str,
    model: str,
    *,
    topic: str,
    mode: str,
    sources: List[Dict[str, str]],
) -> Dict[str, str]:
    api_key = (api_key or "").strip()
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY for draft generation")

    style = (
        "Write as a concise, opinionated blog post with clear subheadings and practical takeaways."
        if mode == "article"
        else "Write as a newsletter issue: short intro, key updates, why it matters, and action points."
    )

    sources_payload = [
        {
            "title": s["title"],
            "url": s["url"],
            "summary": s["summary"][:800],
            "source_name": s["source_name"],
            "published_date": s["published_date"],
            "type": s["type"],
        }
        for s in sources
    ]

    instruction = {
        "task": f"Create a {mode} draft from curated sources",
        "topic": topic,
        "constraints": [
            "Ground claims in provided sources",
            "Cite sources inline as [n] and provide a source list",
            "Avoid fabricated facts",
            "Return strict JSON only"
        ],
        "format": {
            "title": "string",
            "summary": "string",
            "slug": "string",
            "content_markdown": "string"
        },
        "style": style,
        "sources": sources_payload,
    }

    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You produce high-quality drafts from evidence packs."},
            {"role": "user", "content": json.dumps(instruction, ensure_ascii=False)},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = http_json("POST", f"{OPENAI_API_BASE}/chat/completions", headers=headers, payload=payload)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Best effort extraction when model wraps JSON in markdown.
        m = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not m:
            raise SystemExit("Model did not return valid JSON")
        parsed = json.loads(m.group(0))

    for key in ("title", "summary", "slug", "content_markdown"):
        parsed.setdefault(key, "")
    return parsed


def markdown_to_blocks(markdown_text: str, max_blocks: int = 100) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for raw in markdown_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": rich_text_chunks(line[2:], max_chunks=1)}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": rich_text_chunks(line[3:], max_chunks=1)}})
        elif line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": rich_text_chunks(line[4:], max_chunks=1)}})
        elif line.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich_text_chunks(line[2:], max_chunks=1)}})
        elif re.match(r"^\d+\.\s", line):
            txt = re.sub(r"^\d+\.\s", "", line)
            blocks.append({"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": rich_text_chunks(txt, max_chunks=1)}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text_chunks(line, max_chunks=1)}})
        if len(blocks) >= max_blocks:
            break
    return blocks


def create_article_page(
    token: str,
    articles_db_id: str,
    articles_schema: Dict[str, Any],
    draft: Dict[str, str],
    topic: str,
    mode: str,
    author: str,
    source_page_ids: List[str],
    dry_run: bool,
) -> Tuple[Optional[str], Optional[str]]:
    props = articles_schema.get("properties", {})

    title_prop = find_property_name(props, "Title", "title")
    summary_prop = find_property_name(props, "Summary", "rich_text")
    content_prop = find_property_name(props, "Content", "rich_text")
    slug_prop = find_property_name(props, "Slug", "rich_text")
    publish_date_prop = find_property_name(props, "Publish Date", "date")
    status_prop = find_property_name(props, "Status", "select")
    tags_prop = find_property_name(props, "Tags", "multi_select")
    author_prop = find_property_name(props, "Author", "rich_text")
    relation_prop = "Source Materials" if "Source Materials" in props else None

    if not title_prop:
        raise SystemExit("My Articles DB has no title property")

    properties: Dict[str, Any] = {
        title_prop: {"title": rich_text_chunks(draft.get("title", "Untitled"), max_chunks=1)}
    }
    if summary_prop:
        properties[summary_prop] = {"rich_text": rich_text_chunks(draft.get("summary", ""))}
    if content_prop:
        properties[content_prop] = {"rich_text": rich_text_chunks(draft.get("content_markdown", ""), max_chunks=80)}
    if slug_prop:
        properties[slug_prop] = {"rich_text": rich_text_chunks(draft.get("slug", ""), max_chunks=1)}
    if publish_date_prop:
        properties[publish_date_prop] = {"date": {"start": now_utc().date().isoformat()}}
    if status_prop:
        properties[status_prop] = {"select": {"name": "Draft"}}
    if tags_prop:
        properties[tags_prop] = {"multi_select": [{"name": topic}, {"name": mode}]}
    if author_prop:
        properties[author_prop] = {"rich_text": rich_text_chunks(author, max_chunks=1)}
    if relation_prop and source_page_ids:
        properties[relation_prop] = {"relation": [{"id": x} for x in source_page_ids[:50]]}

    blocks = markdown_to_blocks(draft.get("content_markdown", ""), max_blocks=100)

    payload = {
        "parent": {"database_id": articles_db_id},
        "properties": properties,
        "children": blocks,
    }

    if dry_run:
        print("[DRY RUN] Would create draft in My Articles")
        return None, None

    data = http_json("POST", f"{NOTION_API_BASE}/pages", headers=notion_headers(token), payload=payload)
    return data.get("id"), data.get("url")


def require(value: str, label: str) -> str:
    value = (value or '').strip()
    if not value:
        raise SystemExit(f"Missing required value: {label}")
    return value


def main() -> None:
    args = parse_args()

    # Normalize env/CLI values that may include CRLF from Windows-edited .env files.
    args.notion_token = (args.notion_token or "").strip()
    args.sources_db_id = (args.sources_db_id or "").strip()
    args.articles_db_id = (args.articles_db_id or "").strip()
    args.openai_api_key = (args.openai_api_key or "").strip()

    notion_token = require(args.notion_token, "--notion-token or NOTION_TOKEN")
    sources_db_id = require(args.sources_db_id, "--sources-db-id or SOURCES_DB_ID")
    articles_db_id = require(args.articles_db_id, "--articles-db-id or MY_ARTICLES_DB_ID")

    source_rows = query_sources(notion_token, sources_db_id, args.topic, args.hours, args.max_sources)
    if not source_rows:
        raise SystemExit("No source rows found for this topic and window")

    sources = [extract_source_row(r) for r in source_rows]
    draft = generate_draft(
        args.openai_api_key,
        args.model,
        topic=args.topic,
        mode=args.mode,
        sources=sources,
    )

    articles_schema = load_db_schema(notion_token, articles_db_id)
    page_id, page_url = create_article_page(
        notion_token,
        articles_db_id,
        articles_schema,
        draft,
        topic=args.topic,
        mode=args.mode,
        author=args.author,
        source_page_ids=[s["id"] for s in sources if s.get("id")],
        dry_run=args.dry_run,
    )

    print(f"Sources used: {len(sources)}")
    print(f"Draft title: {draft.get('title', '')}")
    if page_id:
        print(f"Page ID: {page_id}")
        print(f"URL: {page_url}")


if __name__ == "__main__":
    main()
