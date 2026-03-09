#!/usr/bin/env python3
"""Research recent coaching sources, store to Notion Sources, draft one Written article.

Flow:
1) search recent items from Notion Sources (recent window)
2) if not enough, enrich via web search (news RSS + optional Brave)
3) upsert new sources in Sources DB
4) generate article draft with OpenAI (JSON format)
5) create My Articles page with Status=Written
6) attach source relations and notify via SMTP if configured
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
import os
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from pathlib import Path

NOTION_API_BASE = "https://api.notion.com/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


BLOCKED_PERSONAL_KEYWORDS = [
    "coaching perso",
    "coaching personnel",
    "coaching de vie",
    "coaching life",
    "couple",
    "relation",
    "amour",
    "famille",
    "bien-être",
    "bien etre",
    "confiance en soi",
    "gestion du stress",
    "burnout",
    "anxié",
    "mindset",
    "santé",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Research + draft pipeline for coaching")
    p.add_argument("--topic", default="marché du coaching exécutif B2B")
    p.add_argument("--hours", type=int, default=168)
    p.add_argument("--max-sources", type=int, default=12)
    p.add_argument("--max-search", type=int, default=20)
    p.add_argument("--allow-personal", action="store_true", help="Autoriser explicitement les thèmes de coaching personnel")
    p.add_argument("--min-sources", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--notion-token", default=(__import__('os').environ.get("NOTION_TOKEN", "")))
    p.add_argument("--sources-db-id", default=(__import__('os').environ.get("SOURCES_DB_ID", "30a11393-09f8-8137-9cab-d82dff672715")))
    p.add_argument("--articles-db-id", default=(__import__('os').environ.get("MY_ARTICLES_DB_ID", "1dc11393-09f8-8049-82eb-e18d8d012f96")))
    p.add_argument("--openai-api-key", default=(__import__('os').environ.get("OPENAI_API_KEY", "")))
    p.add_argument("--model", default=(__import__('os').environ.get("OPENAI_MODEL", "gpt-4o-mini")))
    p.add_argument("--author", default="Pascal Mauze")
    p.add_argument("--notify", default=(__import__('os').environ.get("MAIL_TO", "")))
    p.add_argument("--smtp-host", default=(__import__('os').environ.get("SMTP_HOST", "")))
    p.add_argument("--smtp-port", type=int, default=int(__import__('os').environ.get("SMTP_PORT", "587")))
    p.add_argument("--smtp-user", default=(__import__('os').environ.get("SMTP_USER", "")))
    p.add_argument("--smtp-password", default=(__import__('os').environ.get("SMTP_PASSWORD", "")))
    p.add_argument("--smtp-from", default=(__import__('os').environ.get("SMTP_FROM", __import__('os').environ.get("SMTP_USER", ""))))
    return p.parse_args()


def _require(v: str, label: str) -> str:
    v = (v or "").strip()
    if not v:
        raise SystemExit(f"Missing required value: {label}")
    return v


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_date_hours_ago(hours: int) -> str:
    return (now_utc() - dt.timedelta(hours=hours)).date().isoformat()


def http_json(method: str, url: str, headers: Optional[Dict[str, str]] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    req_headers = headers or {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def find_prop(props: Dict[str, Any], candidates: List[str], ptype: str) -> Optional[str]:
    for c in candidates:
        p = props.get(c)
        if p and p.get("type") == ptype:
            return c
    for name, meta in props.items():
        if meta.get("type") == ptype:
            return name
    return None


def notion_db_schema(token: str, db_id: str) -> Dict[str, Any]:
    return http_json("GET", f"{NOTION_API_BASE}/databases/{db_id}", headers=notion_headers(token))


def notion_page_children(token: str, page_id: str) -> List[Dict[str, Any]]:
    data = http_json("GET", f"{NOTION_API_BASE}/blocks/{page_id}/children", headers=notion_headers(token)).get("results", [])
    return data


def query_sources(token: str, db_id: str, captured_from: str, topic: str) -> List[Dict[str, Any]]:
    payload = {
        "filter": {
            "and": [
                {"property": "Captured Date", "date": {"on_or_after": captured_from}},
                {"property": "Tags", "multi_select": {"contains": topic}},
            ]
        },
        "sorts": [{"property": "Captured Date", "direction": "descending"}],
        "page_size": 100,
    }
    data = http_json("POST", f"{NOTION_API_BASE}/databases/{db_id}/query", headers=notion_headers(token), payload=payload)
    return data.get("results", [])


def all_sources(token: str, db_id: str) -> Dict[str, str]:
    """Return url->page_id for existing sources (first 100 only is enough for dedupe of fresh run)."""
    cursor = None
    dups = {}
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = http_json("POST", f"{NOTION_API_BASE}/databases/{db_id}/query", headers=notion_headers(token), payload=body)
        for row in data.get("results", []):
            url = ((row.get("properties", {}).get("URL", {}) or {}).get("url") or "").strip()
            if url:
                dups[url] = row["id"]
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return dups


def extract_page_text(page: Dict[str, Any], prop: str) -> str:
    p = page.get("properties", {}).get(prop, {})
    if not p:
        return ""
    t = p.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in p.get("title", []))
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in p.get("rich_text", []))
    if t == "url":
        return p.get("url") or ""
    if t == "date":
        return (p.get("date") or {}).get("start") or ""
    if t == "multi_select":
        return ",".join(x.get("name", "") for x in p.get("multi_select", []))
    if t == "select":
        return (p.get("select") or {}).get("name", "")
    return ""


def normalize_url(url: str) -> str:
    if not url:
        return ""
    u = url.strip().lower()
    return re.sub(r"\/$", "", u)


def parse_pubdate(raw: str) -> Optional[dt.datetime]:
    if not raw:
        return None
    # RFC 822 / RSS-ish
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ]:
        try:
            dt_obj = dt.datetime.strptime(raw, fmt)
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
            return dt_obj
        except Exception:
            continue
    return None


def search_recent_news_rss(topic: str, max_items: int = 20) -> List[Dict[str, str]]:
    params = {
        "q": topic,
        "hl": "fr",
        "gl": "FR",
        "ceid": "FR:fr",
    }
    url = f"{GOOGLE_NEWS_RSS}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/xml"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        xml = resp.read()
    root = ET.fromstring(xml)
    out: List[Dict[str, str]] = []
    for item in root.findall(".//item")[:max_items * 2]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        date_raw = (item.findtext("pubDate") or "").strip()
        pdt = parse_pubdate(date_raw)
        date_iso = pdt.isoformat() if pdt else ""
        if title and link:
            out.append({
                "title": title,
                "url": link,
                "summary": desc[:1200],
                "published_date": date_iso,
            })
        if len(out) >= max_items:
            break
    return out


def search_brave(topic: str, api_key: Optional[str], max_items: int = 20) -> List[Dict[str, str]]:
    if not api_key:
        return []
    payload = {
        "q": topic,
        "search_lang": "fr",
        "count": min(max_items, 20),
        "freshness": "pw",
    }
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
        "User-Agent": "openclaw-skill/1.0",
    }
    url = "https://api.search.brave.com/res/v1/web/search"
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(payload), headers=headers)
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for r in data.get("web", {}).get("results", [])[:max_items]:
        out.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "summary": r.get("description", "")[:1200],
            "published_date": (r.get("published") or ""),
        })
    return out


def deduce_topic_tag(topic: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", " ", topic).strip().lower()
    return " ".join(s.split())[:25].title() or "Coaching"


def create_source_rows(
    token: str,
    schema: Dict[str, Any],
    db_id: str,
    topic: str,
    items: List[Dict[str, str]],
    existing_urls: Dict[str, str],
) -> List[Dict[str, Any]]:
    props = schema.get("properties", {})
    title_prop = find_prop(props, ["Title"], "title")
    url_prop = find_prop(props, ["URL"], "url")
    summary_prop = find_prop(props, ["Summary"], "rich_text")
    source_name_prop = find_prop(props, ["Source Name"], "rich_text")
    captured_prop = find_prop(props, ["Captured Date"], "date")
    published_prop = find_prop(props, ["Published Date"], "date")
    tags_prop = find_prop(props, ["Tags"], "multi_select")
    status_prop = find_prop(props, ["Status"], "select")
    rel_type_prop = find_prop(props, ["Type"], "select")
    reliability_prop = find_prop(props, ["Reliability"], "select")

    created = []
    now = now_utc().date().isoformat()
    for it in items:
        url = normalize_url(it.get("url", ""))
        if not url:
            continue
        if url in existing_urls:
            created.append({"id": existing_urls[url], "title": it.get("title", ""), "url": it.get("url", "")})
            continue

        payload = {
            "parent": {"database_id": db_id},
            "properties": {},
        }
        if title_prop:
            payload["properties"][title_prop] = {"title": [{"type": "text", "text": {"content": it.get("title", "")[:1500]}}]}
        if url_prop:
            payload["properties"][url_prop] = {"url": it.get("url")}
        if summary_prop:
            payload["properties"][summary_prop] = {"rich_text": [{"type": "text", "text": {"content": it.get("summary", "")[:1900]}}]}
        if source_name_prop:
            source_name = re.sub(r"https?://(www\.)?", "", it.get("url", ""))[:45]
            source_name = source_name.split("/")[0]
            payload["properties"][source_name_prop] = {"rich_text": [{"type": "text", "text": {"content": source_name}}]}
        if captured_prop:
            payload["properties"][captured_prop] = {"date": {"start": now}}
        if published_prop:
            pdate = it.get("published_date")
            if pdate:
                payload["properties"][published_prop] = {"date": {"start": pdate[:10]}}
        if tags_prop:
            t = deduce_topic_tag(topic)
            payload["properties"][tags_prop] = {"multi_select": [{"name": "Auto"}, {"name": t}]}
        if status_prop:
            payload["properties"][status_prop] = {"select": {"name": "Inbox"}}
        if rel_type_prop:
            t = "News"
            if any(k in (it.get("title", "").lower()) for k in ["forum", "reddit", "linkedin", "discord", "discourse"]):
                t = "Post"
            payload["properties"][rel_type_prop] = {"select": {"name": t}}
        if reliability_prop:
            payload["properties"][reliability_prop] = {"select": {"name": "Medium"}}

        row = http_json("POST", f"{NOTION_API_BASE}/pages", headers=notion_headers(token), payload=payload)
        page_id = row.get("id")
        if page_id:
            existing_urls[url] = page_id
            created.append({"id": page_id, "title": it.get("title", ""), "url": it.get("url", "")})
    return created


def map_sources_to_text(rows: List[Dict[str, Any]], limit: int = 12) -> str:
    lines = []
    for i, row in enumerate(rows[:limit], 1):
        lines.append(
            f"{i}. {extract_page_text(row, 'Title')}\n"
            f"URL: {extract_page_text(row, 'URL')}\n"
            f"Résumé: {extract_page_text(row, 'Summary')[:350]}"
        )
    return "\n\n".join(lines)


def generate_draft(
    openai_api_key: str,
    model: str,
    topic: str,
    source_blocks: str,
    style_path: str,
) -> Dict[str, str]:
    # style guide content improves robustness and consistency.
    style = ""
    try:
        style = Path(style_path).read_text(encoding="utf-8")[:3000]
    except Exception:
        style = "Rédaction claire, structurée, orientée coaching et action." 

    payload = {
        "model": model,
        "temperature": 0.3,
        "messages": [
            {
                "role": "system",
                "content": "Tu rédiges des articles de blog éditoriaux en français, orientés coaching business/coaching pro."
            },
            {
                "role": "user",
                "content": (
                    f"Sujet: {topic}\n\n"
                    "Construit un article en français de 900+ mots, format markdown, avec :\n"
                    "- intro,\n- 4 à 6 sections H2,\n- paragraphes développés,\n- conclusion claire,\n- CTA final.\n"
                    "Base-toi uniquement sur ces sources récentes (moins d’une semaine) et ne sors pas de la synthèse proposée.\n"
                    f"Style guide (extrait):\n{style}\n\n"
                    f"Sources:\n{source_blocks}\n\n"
                    "Retourne un JSON strict: {\"title\":..., \"summary\":..., \"seo_description\":..., \"slug\":..., \"content_markdown\":...}\n"
                    "Le slug doit être court, SEO-friendly, en minuscules, sans accents ni ponctuation agressive."
                )
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }
    resp = http_json("POST", f"{OPENAI_API_BASE}/chat/completions", headers=headers, payload=payload)
    content = (resp.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
    if not content:
        raise RuntimeError("OpenAI n’a renvoyé aucun contenu.")
    try:
        draft = json.loads(content)
    except Exception:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise RuntimeError(f"Réponse OpenAI non JSON: {content[:250]}")
        draft = json.loads(match.group(0))
    for key in ["title", "summary", "seo_description", "slug", "content_markdown"]:
        draft.setdefault(key, "")
    return {
        "title": (draft.get("title") or "").strip()[:180],
        "summary": (draft.get("summary") or "").strip(),
        "seo_description": (draft.get("seo_description") or "").strip(),
        "slug": (draft.get("slug") or "").strip(),
        "content_markdown": (draft.get("content_markdown") or "").strip(),
    }


def rich_text_chunks(text: str, max_len: int = 1900, max_chunks: int = 40) -> List[Dict[str, Any]]:
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
    if not chunks:
        chunks = [""]
    chunks = chunks[:max_chunks]
    return [{"type": "text", "text": {"content": c}} for c in chunks]


def markdown_to_blocks(text: str, max_blocks: int = 160) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": rich_text_chunks(line[2:], max_chunks=1)}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": rich_text_chunks(line[3:], max_chunks=1)}})
        elif line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": rich_text_chunks(line[4:], max_chunks=1)}})
        elif re.match(r"^\d+[\)\.]\s+", line):
            txt = re.sub(r"^\d+[\)\.]\s+", "", line)
            blocks.append({"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": rich_text_chunks(txt, max_chunks=1)}})
        elif line.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rich_text_chunks(line[2:], max_chunks=1)}})
        elif line.startswith("> "):
            blocks.append({"object": "block", "type": "quote", "quote": {"rich_text": rich_text_chunks(line[2:], max_chunks=1)}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text_chunks(line, max_chunks=1)}})
        if len(blocks) >= max_blocks:
            break
    return blocks


def create_article(token: str, db_id: str, schema: Dict[str, Any], draft: Dict[str, str], source_ids: List[str], topic: str, dry_run: bool = False) -> Dict[str, str]:
    props = schema.get("properties", {})
    title_prop = find_prop(props, ["Title"], "title")
    summary_prop = find_prop(props, ["Summary"], "rich_text")
    seo_prop = find_prop(props, ["SEO Description"], "rich_text")
    slug_prop = find_prop(props, ["Slug"], "rich_text")
    content_prop = find_prop(props, ["Content"], "rich_text")
    status_prop = find_prop(props, ["Status"], "select")
    mode_prop = find_prop(props, ["Content Mode"], "select")
    published_platform_prop = find_prop(props, ["Published Platforms"], "multi_select")
    tags_prop = find_prop(props, ["Tags"], "multi_select")
    author_prop = find_prop(props, ["Author"], "rich_text")
    source_rel = find_prop(props, ["Source Materials"], "relation")

    if not title_prop:
        raise RuntimeError("My Articles has no Title property")

    title = draft["title"][:180] if draft.get("title") else "Draft coaching"
    blocks = markdown_to_blocks(draft.get("content_markdown", ""))
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            title_prop: {"title": [{"type": "text", "text": {"content": title}}]},
        },
    }
    p = payload["properties"]
    if summary_prop:
        p[summary_prop] = {"rich_text": rich_text_chunks(draft.get("summary", ""))}
    if seo_prop:
        p[seo_prop] = {"rich_text": rich_text_chunks(draft.get("seo_description", "")[:1900])}
    if slug_prop:
        slug = slugify(draft.get("slug", title))[:120]
        p[slug_prop] = {"rich_text": rich_text_chunks(slug)}
    if content_prop:
        p[content_prop] = {"rich_text": rich_text_chunks(draft.get("content_markdown", "")[:1900*40], max_len=1900, max_chunks=40)}
    if status_prop:
        p[status_prop] = {"select": {"name": "Written"}}
    if mode_prop:
        p[mode_prop] = {"select": {"name": "Classic Blog"}}
    if published_platform_prop:
        p[published_platform_prop] = {"multi_select": [{"name": "WordPress-LesNewsDuCoach"}]}
    if tags_prop:
        p[tags_prop] = {"multi_select": [{"name": topic[:25]}, {"name": "coaching"}]}
    if author_prop:
        p[author_prop] = {"rich_text": [{"type": "text", "text": {"content": "Pascal Mauze"}}]}
    if source_rel and source_ids:
        p[source_rel] = {"relation": [{"id": x} for x in source_ids[:50]]}

    if dry_run:
        return {"id": "dry-run", "url": "not-created"}

    payload["children"] = blocks
    data = http_json("POST", f"{NOTION_API_BASE}/pages", headers=notion_headers(token), payload=payload)
    return {"id": data.get("id", ""), "url": data.get("url", "")}


def slugify(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[àáâãäåāăą]", "a", value)
    value = re.sub(r"[èéêëėęē]", "e", value)
    value = re.sub(r"[ìíîïīį]", "i", value)
    value = re.sub(r"[òóôõöøō]", "o", value)
    value = re.sub(r"[ùúûüū]", "u", value)
    value = re.sub(r"[ç]", "c", value)
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        value = f"article-{now_utc().strftime('%Y%m%d')}"
    return value


def send_email_notification(article_url: str, recipients: str, smtp_cfg: Dict[str, str]) -> bool:
    if not recipients:
        return False
    recips = [r.strip() for r in recipients.split(",") if r.strip()]
    if not recips:
        return False

    smtp_host = smtp_cfg.get("host", "").strip()
    smtp_port = int(smtp_cfg.get("port", "587"))
    smtp_user = smtp_cfg.get("user", "").strip()
    smtp_password = smtp_cfg.get("password", "").strip()
    smtp_from = smtp_cfg.get("from", smtp_user).strip()

    if not (smtp_host and smtp_user and smtp_password and smtp_from):
        print("[email] SMTP config incomplete, skip notification.")
        return False

    msg = MIMEMultipart()
    msg["From"] = smtp_from
    msg["To"] = ", ".join(recips)
    msg["Subject"] = "Nouveau draft Notion à réviser"

    body = (
        "Bonjour,\n\n"
        "Un nouveau draft coaching a été généré et est prêt pour révision.\n\n"
        f"Voir le draft: {article_url}\n\n"
        "Bonne correction !\n"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=45) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, recips, msg.as_string())

    print(f"[email] Sent draft notification to: {', '.join(recips)}")
    return True


def ensure_fresh_sources(token: str, sources_schema: Dict[str, Any], sources_db_id: str, topic: str, min_sources: int, max_sources: int, existing: Dict[str, str]) -> List[Dict[str, Any]]:
    captured_from = iso_date_hours_ago(168)
    existing_rows = []
    cursor = None
    # collect sources from DB recent + topic to avoid duplicates and provide relations
    fresh = query_sources(token, sources_db_id, captured_from, topic)
    if fresh:
        existing_rows.extend(fresh)

    # if low, enrich via web search
    if len(existing_rows) < min_sources:
        discovered: List[Dict[str, str]] = []
        brave_key = __import__('os').environ.get("BRAVE_API_KEY", "").strip()
        try:
            discovered = search_brave(topic + " coaching", brave_key, max_items=max_sources)
        except Exception:
            discovered = []

        if len(discovered) < min_sources:
            try:
                discovered.extend(search_recent_news_rss(topic + " coaching", max_items=max_sources * 2))
            except (urllib.error.URLError, ET.ParseError, json.JSONDecodeError):
                discovered = discovered

        # dedupe by URL and ignore if already exists
        seen = set(normalize_url(x.get("url", "")) for x in existing_rows)
        selected: List[Dict[str, str]] = []
        for it in discovered:
            u = normalize_url(it.get("url", ""))
            if not u or u in seen:
                continue
            seen.add(u)
            selected.append(it)
            if len(selected) >= max_sources:
                break

        if selected:
            created = create_source_rows(token, sources_schema, sources_db_id, topic, selected, existing)
            created_ids = set(x["id"] for x in created if x.get("id"))
            # fetch newly created rows with id
            if created_ids:
                for cid in created_ids:
                    page = http_json("GET", f"{NOTION_API_BASE}/pages/{cid}", headers=notion_headers(token))
                    existing_rows.append(page)

    return existing_rows[: max_sources]


def fetch_sources_by_topic(token: str, schema: Dict[str, Any], db_id: str, topic: str, hours: int, max_sources: int, min_sources: int) -> List[Dict[str, Any]]:
    captured_from = iso_date_hours_ago(hours)
    rows = query_sources(token, db_id, captured_from, topic)
    if len(rows) >= min_sources:
        return rows[:max_sources]
    # fallback to last N recent rows regardless of tag
    all_rows = []
    cursor = None
    while len(all_rows) < max(max_sources, min_sources):
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = http_json("POST", f"{NOTION_API_BASE}/databases/{db_id}/query", headers=notion_headers(token), payload=body)
        for row in data.get("results", []):
            captured = extract_page_text(row, "Captured Date")
            all_rows.append((row, captured))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    threshold = now_utc() - dt.timedelta(hours=hours)
    filtered = [r for r, c in all_rows if c and parse_pubdate(c) and parse_pubdate(c) >= threshold]
    if filtered:
        return filtered[:max_sources]

    # If no time-filtered rows, still allow recent DB entries; we prefer latest.
    fallback = [r for r, _ in all_rows][:max_sources]
    return fallback


def main() -> None:
    args = parse_args()
    notion_token = _require(args.notion_token, "NOTION_TOKEN")

    topic = args.topic.strip() or "marché du coaching exécutif B2B"
    if not args.dry_run:
        _require(args.openai_api_key, "OPENAI_API_KEY")

    topic_l = topic.lower()
    if not args.allow_personal:
        if any(k in topic_l for k in BLOCKED_PERSONAL_KEYWORDS):
            topic = "marché du coaching exécutif B2B"
            print(f"[info] sujet recalé car orienté coaching personnel: using fallback topic '{topic}'.")


    # prepare db schema
    sources_schema = notion_db_schema(notion_token, args.sources_db_id)
    article_schema = notion_db_schema(notion_token, args.articles_db_id)

    existing_map = all_sources(notion_token, args.sources_db_id)
    recent_sources = query_sources(notion_token, args.sources_db_id, iso_date_hours_ago(args.hours), topic)
    if len(recent_sources) < args.min_sources:
        recent_sources = ensure_fresh_sources(
            notion_token,
            sources_schema,
            args.sources_db_id,
            topic,
            min_sources=args.min_sources,
            max_sources=args.max_sources,
            existing=existing_map,
        )

    # if we still have too few, top up from any source in window without tag
    if len(recent_sources) < args.min_sources:
        recent_sources = fetch_sources_by_topic(
            notion_token,
            sources_schema,
            args.sources_db_id,
            topic,
            args.hours,
            args.max_sources,
            args.min_sources,
        )

    if not recent_sources:
        raise SystemExit("No source available and no discoverable source found for this run.")

    recent_sources = recent_sources[: args.max_sources]
    sources_text = map_sources_to_text(recent_sources, limit=len(recent_sources))
    source_ids = [row.get("id") for row in recent_sources if row.get("id")]

    draft = generate_draft(
        args.openai_api_key,
        args.model,
        topic=topic,
        source_blocks=sources_text,
        style_path="/home/folkadmin/.openclaw/workspace/skills/blog-writer/style-guide.md",
    )

    if args.dry_run:
        print("[DRY RUN] would generate draft:")
        print(f"topic={topic}")
        print(f"title={draft['title']}")
        print(f"slug={slugify(draft.get('title', ''))}")
        print(f"source_count={len(source_ids)}")
        print(f"summary={draft['summary'][:120]}")
        return

    article = create_article(
        notion_token,
        args.articles_db_id,
        article_schema,
        draft,
        source_ids,
        topic=topic,
        dry_run=args.dry_run,
    )

    print(f"Draft created id={article.get('id')} url={article.get('url')}")
    print(f"Title: {draft['title']}")
    print(f"Sources used: {len(source_ids)}")

    # notification
    send_email_notification(
        article.get("url", ""),
        args.notify,
        {
            "host": args.smtp_host,
            "port": str(args.smtp_port),
            "user": args.smtp_user,
            "password": args.smtp_password,
            "from": args.smtp_from,
        },
    )


if __name__ == "__main__":
    main()
