---
name: youtube-subscriptions-ingestor
description: Daily ingestion of new videos from large YouTube subscription lists into a Notion Sources database, including metadata capture, transcript extraction, and key-message summarization with GPT. Use when asked to scan channels, detect newly published videos, enrich them, and store them in Sources.
---

# YouTube Subscriptions Ingestor

## Overview

Run a repeatable daily pipeline that scans a large channel list (e.g., 200 channels), finds newly published videos, extracts metadata + transcript, summarizes key messages with `gpt-5.1-mini`, and saves each item to the Notion `Sources` DB.

## Workflow

1. Prepare a channel list JSON (see `references/channels-schema.md`).
2. Run `scripts/ingest_youtube_subscriptions.py` with DB/API credentials.
3. Review inserted rows in Notion `Sources` (`Type=Video`, `Status=Inbox`).
4. Promote useful rows to later drafting workflows.

## Required Environment

- `YOUTUBE_API_KEY`
- `NOTION_TOKEN`
- `SOURCES_DB_ID`

Optional:

- `OPENAI_API_KEY` (for GPT key-message extraction)
- `OPENAI_MODEL` (default `gpt-5.1-mini`)

## Commands

Dry run:

```bash
python3 scripts/ingest_youtube_subscriptions.py \
  --channels-file references/channels.sample.json \
  --dry-run
```

Production run:

```bash
python3 scripts/ingest_youtube_subscriptions.py \
  --channels-file /path/to/channels.json \
  --max-per-channel 5 \
  --lookback-hours 72
```

Suggested scheduler:

- Linux cron: `0 7 * * *` (daily at 07:00)
- Windows Task Scheduler: daily trigger + same command

## Behavior Notes

- Deduplicate by both local state (`processed_video_ids`) and Notion URL lookup.
- Persist state at `~/.agent/state/youtube-ingestor-state.json` by default.
- Store transcript in page body blocks and key messages in `Summary`.
- Fall back to description-based summary when transcript or OpenAI output is unavailable.

## Resources

- `scripts/ingest_youtube_subscriptions.py`: End-to-end ingestion pipeline
- `references/channels-schema.md`: Channel config format
- `references/channels.sample.json`: Minimal starter config
