#!/usr/bin/env python3
"""Daily YouTube ingestion pipeline -> Notion Sources DB.

- Read channel IDs from a JSON file (supports large lists, e.g. 200 channels).
- Fetch new videos per channel using YouTube Data API v3.
- Extract metadata + transcript (best effort).
- Summarize key messages with OpenAI model (default gpt-5.1-mini).
- Store records in Notion Sources database.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
NOTION_API_BASE = "https://api.notion.com/v1"
OPENAI_API_BASE = "https://api.openai.com/v1"


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest new YouTube videos into Notion Sources DB")
    p.add_argument("--channels-file", required=True, help="JSON file with channels list")
    p.add_argument(
        "--state-file",
        default=os.path.expanduser("~/.agent/state/youtube-ingestor-state.json"),
        help="Path to state file for processed IDs",
    )
    p.add_argument("--notion-db-id", default=os.getenv("SOURCES_DB_ID", ""))
    p.add_argument("--youtube-api-key", default=os.getenv("YOUTUBE_API_KEY", ""))
    p.add_argument("--notion-token", default=os.getenv("NOTION_TOKEN", ""))
    p.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.1-mini"))
    p.add_argument("--max-per-channel", type=int, default=5)
    p.add_argument("--lookback-hours", type=int, default=72)
    p.add_argument("--max-transcript-chars", type=int, default=15000)
    p.add_argument("--sleep-ms", type=int, default=50, help="Sleep between external calls")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def load_json(path: str, default: Any) -> Any:
    p = pathlib.Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: str, obj: Any) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def http_json(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_text(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def yt_get(api_key: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    q = dict(params)
    q["key"] = api_key
    url = f"{YOUTUBE_API_BASE}/{path}?{urllib.parse.urlencode(q)}"
    return http_json("GET", url)


def iso_z(dt_obj: dt.datetime) -> str:
    return dt_obj.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iter_chunks(items: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def list_recent_video_ids(
    api_key: str,
    channel_id: str,
    published_after: str,
    max_results: int,
) -> List[str]:
    data = yt_get(
        api_key,
        "search",
        {
            "part": "id,snippet",
            "channelId": channel_id,
            "order": "date",
            "publishedAfter": published_after,
            "maxResults": str(max_results),
            "type": "video",
        },
    )
    out = []
    for item in data.get("items", []):
        vid = (item.get("id") or {}).get("videoId")
        if vid:
            out.append(vid)
    return out


def get_video_details(api_key: str, video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    details: Dict[str, Dict[str, Any]] = {}
    for chunk in iter_chunks(video_ids, 50):
        data = yt_get(
            api_key,
            "videos",
            {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(chunk),
                "maxResults": str(len(chunk)),
            },
        )
        for item in data.get("items", []):
            details[item["id"]] = item
    return details


def choose_caption_track(caption_tracks: List[Dict[str, Any]]) -> Optional[str]:
    if not caption_tracks:
        return None
    preferred_langs = ("en", "en-US", "en-GB", "fr", "fr-FR")
    for lang in preferred_langs:
        for t in caption_tracks:
            if t.get("languageCode") == lang and t.get("baseUrl"):
                return t["baseUrl"]
    for t in caption_tracks:
        if t.get("baseUrl"):
            return t["baseUrl"]
    return None


def extract_caption_base_url(watch_html: str) -> Optional[str]:
    # Best effort parse from player response JSON embedded in watch HTML.
    m = re.search(r'"captionTracks":(\[.*?\])', watch_html, flags=re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    try:
        tracks = json.loads(raw)
        return choose_caption_track(tracks)
    except json.JSONDecodeError:
        return None


def transcript_from_video(video_id: str, max_chars: int = 15000) -> str:
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    ua = {"User-Agent": "Mozilla/5.0"}
    try:
        watch_html = http_text(watch_url, headers=ua)
    except Exception:
        return ""

    base_url = extract_caption_base_url(watch_html)
    if not base_url:
        return ""

    caption_url = base_url
    if "fmt=" not in caption_url:
        joiner = "&" if "?" in caption_url else "?"
        caption_url = f"{caption_url}{joiner}fmt=srv3"

    try:
        xml_text = http_text(caption_url, headers=ua)
    except Exception:
        return ""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""

    lines: List[str] = []
    for node in root.findall(".//text"):
        text = "".join(node.itertext()).strip()
        if not text:
            continue
        lines.append(html.unescape(text))
        if sum(len(x) for x in lines) >= max_chars:
            break

    return "\n".join(lines)[:max_chars]


def openai_key_messages(
    api_key: str,
    model: str,
    title: str,
    description: str,
    transcript: str,
) -> str:
    if not api_key:
        # Fallback summary when no OpenAI key is configured.
        text = (description or transcript[:1200] or "No summary available").strip()
        return text[:1800]

    source_text = transcript[:12000] if transcript else description[:4000]
    prompt = (
        "Extract the 6-10 most important insights from this video. "
        "Return concise bullet points and keep practical facts, numbers, and claims."
    )

    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "You produce concise structured insight summaries for knowledge pipelines.",
            },
            {
                "role": "user",
                "content": (
                    f"Title: {title}\n\nDescription:\n{description[:3000]}\n\n"
                    f"Transcript:\n{source_text}\n\n{prompt}"
                ),
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        data = http_json("POST", f"{OPENAI_API_BASE}/chat/completions", headers=headers, payload=payload)
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()[:1800]
        ) or "No summary generated"
    except Exception:
        return (description or "No summary generated")[:1800]


def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def notion_query_by_url(notion_token: str, db_id: str, url_value: str) -> bool:
    payload = {
        "filter": {
            "property": "URL",
            "url": {"equals": url_value},
        },
        "page_size": 1,
    }
    data = http_json(
        "POST",
        f"{NOTION_API_BASE}/databases/{db_id}/query",
        headers=notion_headers(notion_token),
        payload=payload,
    )
    return bool(data.get("results"))


def notion_rich_text_chunks(text: str, max_len: int = 1900, max_chunks: int = 50) -> List[Dict[str, Any]]:
    chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
    chunks = chunks[:max_chunks] or [""]
    return [{"type": "text", "text": {"content": c}} for c in chunks]


def md_lines_to_blocks(markdown_text: str, max_blocks: int = 100) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for raw in markdown_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": notion_rich_text_chunks(line[4:], max_chunks=1)},
                }
            )
        elif line.startswith("- "):
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": notion_rich_text_chunks(line[2:], max_chunks=1)},
                }
            )
        else:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": notion_rich_text_chunks(line, max_chunks=1)},
                }
            )
        if len(blocks) >= max_blocks:
            break
    return blocks


def notion_create_source_item(
    notion_token: str,
    db_id: str,
    *,
    title: str,
    url: str,
    source_name: str,
    published_date: Optional[str],
    summary: str,
    transcript: str,
    topic: str,
    dry_run: bool,
) -> Optional[str]:
    properties = {
        "Title": {"title": notion_rich_text_chunks(title, max_chunks=1)},
        "Type": {"select": {"name": "Video"}},
        "URL": {"url": url},
        "Source Name": {"rich_text": notion_rich_text_chunks(source_name, max_chunks=1)},
        "Captured Date": {"date": {"start": utcnow().date().isoformat()}},
        "Summary": {"rich_text": notion_rich_text_chunks(summary)},
        "Reliability": {"select": {"name": "Medium"}},
        "Status": {"select": {"name": "Inbox"}},
        "Tags": {"multi_select": [{"name": "YouTube"}] + ([{"name": topic}] if topic else [])},
    }
    if published_date:
        properties["Published Date"] = {"date": {"start": published_date[:10]}}

    body = "\n".join(
        [
            "### Key Messages",
            summary or "No key messages extracted.",
            "### Transcript",
            transcript[:12000] if transcript else "Transcript unavailable",
        ]
    )

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": md_lines_to_blocks(body),
    }

    if dry_run:
        print(f"[DRY RUN] Would create Notion row for: {title}")
        return None

    data = http_json(
        "POST",
        f"{NOTION_API_BASE}/pages",
        headers=notion_headers(notion_token),
        payload=payload,
    )
    return data.get("id")


def required(value: str, name: str) -> str:
    value = (value or '').strip()
    if not value:
        raise SystemExit(f"Missing required value: {name}")
    return value


def normalize_channels(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        raise SystemExit("channels-file must contain a JSON array")
    out: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            out.append({"channel_id": item, "label": "", "topic": ""})
            continue
        if not isinstance(item, dict) or "channel_id" not in item:
            continue
        out.append(
            {
                "channel_id": str(item.get("channel_id", "")).strip(),
                "label": str(item.get("label", "")).strip(),
                "topic": str(item.get("topic", "")).strip(),
            }
        )
    return [x for x in out if x["channel_id"]]


def main() -> None:
    args = parse_args()

    # Normalize env/CLI values that may include CRLF from Windows-edited .env files.
    args.notion_db_id = (args.notion_db_id or "").strip()
    args.youtube_api_key = (args.youtube_api_key or "").strip()
    args.notion_token = (args.notion_token or "").strip()
    args.openai_api_key = (args.openai_api_key or "").strip()

    notion_db_id = required(args.notion_db_id, "--notion-db-id or SOURCES_DB_ID")
    youtube_api_key = required(args.youtube_api_key, "--youtube-api-key or YOUTUBE_API_KEY")
    notion_token = required(args.notion_token, "--notion-token or NOTION_TOKEN")

    channels = normalize_channels(load_json(args.channels_file, []))
    if not channels:
        raise SystemExit("No channels found in channels-file")

    state = load_json(args.state_file, {"processed_video_ids": [], "last_run": None})
    processed = set(state.get("processed_video_ids", []))

    cutoff = utcnow() - dt.timedelta(hours=args.lookback_hours)
    published_after = iso_z(cutoff)

    to_process: List[Dict[str, Any]] = []
    print(f"Scanning {len(channels)} channels (published_after={published_after})...")
    for ch in channels:
        ch_id = ch["channel_id"]
        vids = list_recent_video_ids(
            youtube_api_key,
            ch_id,
            published_after=published_after,
            max_results=args.max_per_channel,
        )
        for vid in vids:
            if vid in processed:
                continue
            to_process.append({"video_id": vid, **ch})
        time.sleep(args.sleep_ms / 1000.0)

    if not to_process:
        print("No new videos found.")
        return

    video_ids = [x["video_id"] for x in to_process]
    details = get_video_details(youtube_api_key, video_ids)

    created = 0
    for item in to_process:
        vid = item["video_id"]
        d = details.get(vid)
        if not d:
            continue

        snippet = d.get("snippet", {})
        title = snippet.get("title", f"YouTube video {vid}")
        description = snippet.get("description", "")
        channel_title = snippet.get("channelTitle") or item.get("label") or item["channel_id"]
        published_at = snippet.get("publishedAt")
        url = f"https://www.youtube.com/watch?v={vid}"

        try:
            if notion_query_by_url(notion_token, notion_db_id, url):
                processed.add(vid)
                continue
        except urllib.error.HTTPError as e:
            print(f"[WARN] Notion dedupe query failed for {vid}: {e}")

        transcript = transcript_from_video(vid, max_chars=args.max_transcript_chars)
        summary = openai_key_messages(
            args.openai_api_key,
            args.model,
            title=title,
            description=description,
            transcript=transcript,
        )

        notion_create_source_item(
            notion_token,
            notion_db_id,
            title=title,
            url=url,
            source_name=channel_title,
            published_date=published_at,
            summary=summary,
            transcript=transcript,
            topic=item.get("topic", ""),
            dry_run=args.dry_run,
        )

        processed.add(vid)
        created += 1
        print(f"[OK] {title}")
        time.sleep(args.sleep_ms / 1000.0)

    state["processed_video_ids"] = sorted(processed)
    state["last_run"] = iso_z(utcnow())
    if not args.dry_run:
        save_json(args.state_file, state)

    print(f"Completed. New rows: {created}")


if __name__ == "__main__":
    main()
