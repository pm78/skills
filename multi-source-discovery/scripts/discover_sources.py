#!/usr/bin/env python3
"""Discover relevant content across multiple sources and store in Notion Sources DB.

Connectors:
- Web (Tavily)
- Reddit
- Hacker News
- Substack (Tavily domain filter)
- Medium (Tavily domain filter)
- News API
- X/Twitter (Tavily domain filter + optional Nitter RSS)
- YouTube (YouTube Data API)
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

NOTION_API_BASE = "https://api.notion.com/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"


@dataclass
class Item:
    title: str
    url: str
    source_name: str
    source_kind: str
    topic: str
    summary: str
    published_at: Optional[str]
    raw_score: float = 0.0
    llm_score: float = 0.0

    @property
    def score(self) -> float:
        return self.llm_score if self.llm_score > 0 else self.raw_score


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Discover and store external sources into Notion")
    p.add_argument("--sources-db-id", default=os.getenv("SOURCES_DB_ID", ""))
    p.add_argument("--notion-token", default=os.getenv("NOTION_TOKEN", ""))
    p.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    p.add_argument("--openai-model", default=os.getenv("OPENAI_MODEL", "gpt-5.1-mini"))
    p.add_argument("--tavily-api-key", default=os.getenv("TAVILY_API_KEY", ""))
    p.add_argument("--newsapi-key", default=os.getenv("NEWSAPI_KEY", ""))
    p.add_argument("--youtube-api-key", default=os.getenv("YOUTUBE_API_KEY", ""))
    p.add_argument("--nitter-base-url", default=os.getenv("NITTER_BASE_URL", ""))
    p.add_argument("--topics-file", default="references/default-topics.json")
    p.add_argument("--topics", default="AI,Health,GeoPolitics,France,Payments")
    p.add_argument("--keywords", action="append", default=[])
    p.add_argument("--hours", type=int, default=48)
    p.add_argument("--max-per-source", type=int, default=10)
    p.add_argument("--store-top", type=int, default=25)
    p.add_argument("--sleep-ms", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_z(x: dt.datetime) -> str:
    return x.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_json(method: str, url: str, *, headers: Optional[Dict[str, str]] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_text(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.read().decode("utf-8", errors="replace")


def load_topics(path: str, selected_topics: List[str], inline_keywords: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, list):
                    out[k] = [str(x).strip() for x in v if str(x).strip()]

    # Ensure selected topics exist even if file missing.
    for t in selected_topics:
        out.setdefault(t, [t])

    if inline_keywords:
        out.setdefault("Custom", [])
        out["Custom"].extend([x for x in inline_keywords if x])

    filtered: Dict[str, List[str]] = {}
    wanted = set(x.strip() for x in selected_topics if x.strip())
    for topic, kws in out.items():
        if topic in wanted or topic == "Custom":
            filtered[topic] = kws
    return filtered


def local_score(title: str, summary: str, keywords: List[str], published_at: Optional[str]) -> float:
    text = f"{title}\n{summary}".lower()
    score = 0.0
    for kw in keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        if kw_l in text:
            score += 10.0
    if published_at:
        try:
            d = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            age_h = max((now_utc() - d).total_seconds() / 3600.0, 0.0)
            score += max(0.0, 8.0 - min(age_h / 12.0, 8.0))
        except Exception:
            pass
    return score


def dedupe(items: List[Item]) -> List[Item]:
    seen = set()
    out: List[Item] = []
    for item in items:
        k = item.url.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def parse_pubdate(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    try:
        if value.endswith("Z"):
            dt_obj = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return iso_z(dt_obj)
        dt_obj = dt.datetime.fromisoformat(value)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
        return iso_z(dt_obj)
    except Exception:
        pass
    try:
        p = email.utils.parsedate_to_datetime(value)
        if p and p.tzinfo is None:
            p = p.replace(tzinfo=dt.timezone.utc)
        return iso_z(p)
    except Exception:
        return None


def tavily_search(api_key: str, query: str, max_results: int, include_domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    if not api_key:
        return []
    payload: Dict[str, Any] = {
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        data = http_json("POST", "https://api.tavily.com/search", headers=headers, payload=payload)
        return data.get("results", [])
    except Exception:
        return []


def fetch_reddit(query: str, max_results: int) -> List[Dict[str, Any]]:
    q = urllib.parse.urlencode({"q": query, "sort": "new", "limit": max_results, "t": "day"})
    url = f"https://www.reddit.com/search.json?{q}"
    try:
        data = http_json("GET", url, headers={"User-Agent": "source-discovery/1.0"})
    except Exception:
        return []
    out = []
    for child in ((data.get("data") or {}).get("children") or []):
        d = child.get("data") or {}
        permalink = d.get("permalink")
        if not permalink:
            continue
        out.append(
            {
                "title": d.get("title", ""),
                "url": f"https://www.reddit.com{permalink}",
                "summary": d.get("selftext", "")[:1200],
                "source": f"r/{d.get('subreddit', '')}",
                "published_at": iso_z(dt.datetime.fromtimestamp(d.get("created_utc", 0), tz=dt.timezone.utc)) if d.get("created_utc") else None,
            }
        )
    return out


def fetch_hackernews(query: str, max_results: int) -> List[Dict[str, Any]]:
    q = urllib.parse.urlencode({"query": query, "tags": "story", "hitsPerPage": max_results})
    url = f"https://hn.algolia.com/api/v1/search_by_date?{q}"
    try:
        data = http_json("GET", url)
    except Exception:
        return []
    out = []
    for hit in data.get("hits", []):
        url_value = hit.get("url")
        title = hit.get("title") or hit.get("story_title") or ""
        if not url_value or not title:
            continue
        out.append(
            {
                "title": title,
                "url": url_value,
                "summary": (hit.get("_highlightResult", {}).get("story_text", {}).get("value") or "")[:1200],
                "source": "Hacker News",
                "published_at": parse_pubdate(hit.get("created_at")),
            }
        )
    return out


def fetch_newsapi(news_key: str, query: str, max_results: int) -> List[Dict[str, Any]]:
    if not news_key:
        return []
    q = urllib.parse.urlencode(
        {
            "q": query,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": max_results,
            "apiKey": news_key,
        }
    )
    url = f"https://newsapi.org/v2/everything?{q}"
    try:
        data = http_json("GET", url)
    except Exception:
        return []

    out = []
    for a in data.get("articles", []):
        u = a.get("url")
        t = a.get("title")
        if not u or not t:
            continue
        out.append(
            {
                "title": t,
                "url": u,
                "summary": (a.get("description") or "")[:1200],
                "source": (a.get("source") or {}).get("name") or "News",
                "published_at": parse_pubdate(a.get("publishedAt")),
            }
        )
    return out


def fetch_youtube(youtube_api_key: str, query: str, max_results: int, published_after: str) -> List[Dict[str, Any]]:
    if not youtube_api_key:
        return []
    q = urllib.parse.urlencode(
        {
            "part": "id,snippet",
            "q": query,
            "maxResults": max_results,
            "order": "date",
            "type": "video",
            "publishedAfter": published_after,
            "key": youtube_api_key,
        }
    )
    url = f"https://www.googleapis.com/youtube/v3/search?{q}"
    try:
        data = http_json("GET", url)
    except Exception:
        return []

    out = []
    for item in data.get("items", []):
        vid = (item.get("id") or {}).get("videoId")
        sn = item.get("snippet") or {}
        if not vid:
            continue
        out.append(
            {
                "title": sn.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "summary": (sn.get("description") or "")[:1200],
                "source": sn.get("channelTitle") or "YouTube",
                "published_at": parse_pubdate(sn.get("publishedAt")),
            }
        )
    return out


def fetch_nitter(nitter_base_url: str, query: str, max_results: int) -> List[Dict[str, Any]]:
    if not nitter_base_url:
        return []
    base = nitter_base_url.rstrip("/")
    url = f"{base}/search/rss?f=tweets&q={urllib.parse.quote(query)}"
    try:
        xml_text = http_text(url, headers={"User-Agent": "source-discovery/1.0"})
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    out = []
    for item in root.findall(".//item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = parse_pubdate(item.findtext("pubDate"))
        if not title or not link:
            continue
        out.append({"title": title, "url": link, "summary": "", "source": "X (via Nitter)", "published_at": pub})
    return out


def score_with_llm(api_key: str, model: str, topic: str, keywords: List[str], items: List[Item]) -> None:
    if not api_key or not items:
        return
    payload_items = []
    for idx, item in enumerate(items):
        payload_items.append(
            {
                "idx": idx,
                "title": item.title,
                "url": item.url,
                "summary": item.summary[:300],
                "source": item.source_name,
            }
        )

    prompt = {
        "topic": topic,
        "keywords": keywords,
        "task": "Score each item 0-100 for relevance, novelty, and actionability for a curated intelligence feed.",
        "items": payload_items,
        "output": {"scores": [{"idx": 0, "score": 0}]},
    }

    req = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You are a strict ranking engine. Return JSON only."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        data = http_json("POST", f"{OPENAI_API_BASE}/chat/completions", headers=headers, payload=req)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content)
        for row in parsed.get("scores", []):
            idx = int(row.get("idx", -1))
            score = float(row.get("score", 0))
            if 0 <= idx < len(items):
                items[idx].llm_score = score
    except Exception:
        return


def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def notion_rich_text(text: str, max_len: int = 1900, max_chunks: int = 40) -> List[Dict[str, Any]]:
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
    chunks = chunks[:max_chunks] or [""]
    return [{"type": "text", "text": {"content": c}} for c in chunks]


def notion_exists_by_url(token: str, db_id: str, url_value: str) -> bool:
    payload = {
        "filter": {"property": "URL", "url": {"equals": url_value}},
        "page_size": 1,
    }
    data = http_json(
        "POST",
        f"{NOTION_API_BASE}/databases/{db_id}/query",
        headers=notion_headers(token),
        payload=payload,
    )
    return bool(data.get("results"))


def source_kind_to_type(source_kind: str) -> str:
    m = {
        "web": "Article",
        "reddit": "Post",
        "hn": "News",
        "substack": "Article",
        "medium": "Article",
        "news": "News",
        "x": "Post",
        "youtube": "Video",
    }
    return m.get(source_kind, "Article")


def source_kind_reliability(source_kind: str) -> str:
    if source_kind in {"news", "hn"}:
        return "Medium"
    if source_kind in {"web", "substack", "medium"}:
        return "Medium"
    if source_kind in {"youtube", "reddit", "x"}:
        return "Low"
    return "Medium"


def store_item(token: str, db_id: str, item: Item, dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY RUN] {item.topic} | {item.source_kind} | {item.title}")
        return

    props = {
        "Title": {"title": notion_rich_text(item.title, max_chunks=1)},
        "Type": {"select": {"name": source_kind_to_type(item.source_kind)}},
        "URL": {"url": item.url},
        "Source Name": {"rich_text": notion_rich_text(item.source_name or item.source_kind, max_chunks=1)},
        "Captured Date": {"date": {"start": now_utc().date().isoformat()}},
        "Summary": {"rich_text": notion_rich_text(item.summary)},
        "Reliability": {"select": {"name": source_kind_reliability(item.source_kind)}},
        "Status": {"select": {"name": "Inbox"}},
        "Tags": {
            "multi_select": [
                {"name": item.topic},
                {"name": item.source_kind},
            ]
        },
    }
    if item.published_at:
        props["Published Date"] = {"date": {"start": item.published_at[:10]}}

    body = (
        f"### Discovery Metadata\n"
        f"- Source kind: {item.source_kind}\n"
        f"- Topic: {item.topic}\n"
        f"- Score: {item.score:.2f}\n"
        f"### Extract\n{item.summary[:4000]}"
    )

    children = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("### "):
            children.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": notion_rich_text(line[4:], max_chunks=1)},
                }
            )
        elif line.startswith("- "):
            children.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": notion_rich_text(line[2:], max_chunks=1)},
                }
            )
        else:
            children.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": notion_rich_text(line, max_chunks=1)},
                }
            )

    payload = {
        "parent": {"database_id": db_id},
        "properties": props,
        "children": children[:100],
    }
    http_json("POST", f"{NOTION_API_BASE}/pages", headers=notion_headers(token), payload=payload)


def build_items_for_topic(args: argparse.Namespace, topic: str, keywords: List[str], published_after: str) -> List[Item]:
    out: List[Item] = []
    query = " OR ".join(keywords[:8]) if keywords else topic

    # 1) Web
    for r in tavily_search(args.tavily_api_key, query, args.max_per_source):
        out.append(
            Item(
                title=r.get("title", ""),
                url=r.get("url", ""),
                summary=(r.get("content") or "")[:1200],
                source_name=r.get("url", "Web"),
                source_kind="web",
                topic=topic,
                published_at=parse_pubdate(r.get("published_date")),
            )
        )

    # 2) Reddit
    for r in fetch_reddit(query, args.max_per_source):
        out.append(
            Item(
                title=r["title"],
                url=r["url"],
                summary=r.get("summary", ""),
                source_name=r.get("source", "Reddit"),
                source_kind="reddit",
                topic=topic,
                published_at=r.get("published_at"),
            )
        )

    # 3) Hacker News
    for r in fetch_hackernews(query, args.max_per_source):
        out.append(
            Item(
                title=r["title"],
                url=r["url"],
                summary=r.get("summary", ""),
                source_name=r.get("source", "Hacker News"),
                source_kind="hn",
                topic=topic,
                published_at=r.get("published_at"),
            )
        )

    # 4) Substack
    for r in tavily_search(args.tavily_api_key, query, args.max_per_source, include_domains=["substack.com"]):
        out.append(
            Item(
                title=r.get("title", ""),
                url=r.get("url", ""),
                summary=(r.get("content") or "")[:1200],
                source_name="Substack",
                source_kind="substack",
                topic=topic,
                published_at=parse_pubdate(r.get("published_date")),
            )
        )

    # 5) Medium
    for r in tavily_search(args.tavily_api_key, query, args.max_per_source, include_domains=["medium.com"]):
        out.append(
            Item(
                title=r.get("title", ""),
                url=r.get("url", ""),
                summary=(r.get("content") or "")[:1200],
                source_name="Medium",
                source_kind="medium",
                topic=topic,
                published_at=parse_pubdate(r.get("published_date")),
            )
        )

    # 6) News API
    for r in fetch_newsapi(args.newsapi_key, query, args.max_per_source):
        out.append(
            Item(
                title=r["title"],
                url=r["url"],
                summary=r.get("summary", ""),
                source_name=r.get("source", "News"),
                source_kind="news",
                topic=topic,
                published_at=r.get("published_at"),
            )
        )

    # 7) X (Tavily domain filter + Nitter fallback)
    x_hits = tavily_search(args.tavily_api_key, query, args.max_per_source, include_domains=["x.com", "twitter.com"])
    for r in x_hits:
        out.append(
            Item(
                title=r.get("title", ""),
                url=r.get("url", ""),
                summary=(r.get("content") or "")[:1200],
                source_name="X",
                source_kind="x",
                topic=topic,
                published_at=parse_pubdate(r.get("published_date")),
            )
        )
    if args.nitter_base_url:
        for r in fetch_nitter(args.nitter_base_url, query, args.max_per_source):
            out.append(
                Item(
                    title=r["title"],
                    url=r["url"],
                    summary=r.get("summary", ""),
                    source_name=r.get("source", "X"),
                    source_kind="x",
                    topic=topic,
                    published_at=r.get("published_at"),
                )
            )

    # 8) YouTube
    for r in fetch_youtube(args.youtube_api_key, query, args.max_per_source, published_after):
        out.append(
            Item(
                title=r["title"],
                url=r["url"],
                summary=r.get("summary", ""),
                source_name=r.get("source", "YouTube"),
                source_kind="youtube",
                topic=topic,
                published_at=r.get("published_at"),
            )
        )

    # Local scoring
    for item in out:
        item.raw_score = local_score(item.title, item.summary, keywords, item.published_at)

    return out


def require_non_empty(value: str, label: str) -> str:
    value = (value or '').strip()
    if not value:
        raise SystemExit(f"Missing required value: {label}")
    return value


def main() -> None:
    args = parse_args()

    # Normalize env/CLI values that may include CRLF from Windows-edited .env files.
    args.sources_db_id = (args.sources_db_id or "").strip()
    args.notion_token = (args.notion_token or "").strip()
    args.openai_api_key = (args.openai_api_key or "").strip()
    args.tavily_api_key = (args.tavily_api_key or "").strip()
    args.newsapi_key = (args.newsapi_key or "").strip()
    args.youtube_api_key = (args.youtube_api_key or "").strip()
    args.nitter_base_url = (args.nitter_base_url or "").strip()

    notion_token = require_non_empty(args.notion_token, "--notion-token or NOTION_TOKEN")
    db_id = require_non_empty(args.sources_db_id, "--sources-db-id or SOURCES_DB_ID")

    selected_topics = [x.strip() for x in args.topics.split(",") if x.strip()]
    topics = load_topics(args.topics_file, selected_topics, args.keywords)
    if not topics:
        raise SystemExit("No topics/keywords configured")

    published_after = iso_z(now_utc() - dt.timedelta(hours=args.hours))
    all_items: List[Item] = []

    for topic, keywords in topics.items():
        items = build_items_for_topic(args, topic, keywords, published_after)
        score_with_llm(args.openai_api_key, args.openai_model, topic, keywords, items)
        all_items.extend(items)
        time.sleep(args.sleep_ms / 1000.0)

    all_items = dedupe(all_items)
    all_items.sort(key=lambda x: x.score, reverse=True)
    selected = all_items[: args.store_top]

    inserted = 0
    for item in selected:
        try:
            if notion_exists_by_url(notion_token, db_id, item.url):
                continue
            store_item(notion_token, db_id, item, args.dry_run)
            inserted += 1
            print(f"[OK] {item.topic} | {item.source_kind} | {item.title}")
        except Exception as e:
            print(f"[WARN] Failed to store item: {item.title} ({e})")
        time.sleep(args.sleep_ms / 1000.0)

    print(f"Completed. Candidate items: {len(all_items)}, inserted: {inserted}")


if __name__ == "__main__":
    main()
