---
name: source-to-article-newsletter
description: Draft generation workflow that reads curated rows from Notion Sources and produces blog article or newsletter drafts with GPT, then stores them in My Articles with draft status and source relations. Use when asked to synthesize monitored sources into publish-ready written drafts.
---

# Source To Article/Newsletter

## Overview

Turn curated `Sources` rows into a structured draft (`article` or `newsletter`) and save it directly to `My Articles` as `Status=Draft`, with source linkage for traceability.

## Workflow

1. Select topic and time window from `Sources`.
2. Generate a draft with `gpt-5.1-mini` using explicit source evidence.
3. Store in `My Articles` with:
   - `Title`, `Summary`, `Content`, `Slug`
   - `Status=Draft`
   - `Tags` including topic and mode
   - `Source Materials` relation (when present)
4. Hand off to your publishing skill/process.

## Required Environment

- `NOTION_TOKEN`
- `SOURCES_DB_ID`
- `MY_ARTICLES_DB_ID` (defaults to your current DB ID)
- `OPENAI_API_KEY`

Optional:

- `OPENAI_MODEL` (default `gpt-5.1-mini`)

## Commands

Dry run:

```bash
python3 scripts/draft_from_sources.py \
  --topic Payments \
  --mode article \
  --hours 168 \
  --max-sources 20 \
  --dry-run
```

Create draft in My Articles:

```bash
python3 scripts/draft_from_sources.py \
  --topic AI \
  --mode newsletter \
  --hours 96 \
  --max-sources 25
```

## Behavior Notes

- Pull sources by `Tags contains <topic>` + recency filter.
- Enforce source grounding in draft prompt.
- Store full markdown in `Content` and structured body blocks in the page.
- Keep workflow focused on drafting only (publishing is separate).

## Resources

- `scripts/draft_from_sources.py`: Source-to-draft generator
- `references/editorial-modes.md`: Editorial mode guidance
