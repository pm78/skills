---
name: multi-source-discovery
description: Cross-source discovery and ranking pipeline that searches web, Reddit, Hacker News, Substack, Medium, News APIs, X, and YouTube for keyword/topic updates, then stores the most relevant items in Notion Sources. Use when asked for recurring topic monitoring, daily intelligence capture, or source scouting.
---

# Multi-Source Discovery

## Overview

Run a daily (or intraday) discovery job across multiple public and API-backed sources, score items for relevance, and insert only top-ranked results into `Sources`.

## Workflow

1. Configure topics/keywords in `references/default-topics.json`.
2. Provide API keys (Tavily/NewsAPI/YouTube/OpenAI as available).
3. Run `scripts/discover_sources.py`.
4. Review new `Sources` rows (`Status=Inbox`) and promote selected items.

## Required Environment

- `NOTION_TOKEN`
- `SOURCES_DB_ID`

Optional but recommended:

- `OPENAI_API_KEY` (relevance ranking)
- `TAVILY_API_KEY` (web/substack/medium/x discovery)
- `NEWSAPI_KEY` (news discovery)
- `YOUTUBE_API_KEY` (YouTube keyword discovery)
- `NITTER_BASE_URL` (optional X RSS fallback)

## Commands

Dry run:

```bash
python3 scripts/discover_sources.py \
  --topics-file references/default-topics.json \
  --topics "AI,Health,GeoPolitics,France,Payments" \
  --dry-run
```

Production run:

```bash
python3 scripts/discover_sources.py \
  --topics-file references/default-topics.json \
  --topics "AI,Health,GeoPolitics,France,Payments" \
  --hours 48 \
  --max-per-source 10 \
  --store-top 25
```

## Behavior Notes

- Deduplicate by URL before insert.
- Score with local keyword/recency heuristic and optional GPT reranking.
- Map each connector to `Sources.Type` (`Article`, `Video`, `News`, `Post`).
- Write discovery provenance in page body (`source_kind`, topic, score).

## Resources

- `scripts/discover_sources.py`: Multi-source fetch, score, and store pipeline
- `references/default-topics.json`: Default topic keyword packs
