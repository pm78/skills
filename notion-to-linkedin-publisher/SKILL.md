---
name: notion-to-linkedin-publisher
description: Publish automation that finds the latest eligible article in Notion `My Articles`, posts it to LinkedIn, writes back the LinkedIn post URL, appends `Published Platforms`, and resolves status to `partially_published` or `published` from required platforms. Use when asked to publish Notion-stored articles to LinkedIn.
---

# Notion To LinkedIn Publisher

## Overview

Publish one article per run from `My Articles` to LinkedIn. The script selects the most recently edited eligible row, publishes a LinkedIn post, then updates Notion.

## Required Environment

- `NOTION_TOKEN`
- `MY_ARTICLES_DB_ID` (optional; defaults to your current DB ID)
- `LINKEDIN_ACCESS_TOKEN`
- `LINKEDIN_AUTHOR_URN` (example: `urn:li:person:xxxx`)

## Commands

Run a dry run first:

```bash
python3 scripts/publish_latest_to_linkedin.py --dry-run
```

Run live publish:

```bash
python3 scripts/publish_latest_to_linkedin.py
```

Use custom status labels:

```bash
python3 scripts/publish_latest_to_linkedin.py \
  --draft-status Draft \
  --partially-published-status Partially Published \
  --published-status Published
```

Print machine-readable output:

```bash
python3 scripts/publish_latest_to_linkedin.py --print-json
```

## Behavior

- Auto-detect Notion properties for title, status, content, summary, and platform fields.
- Select the latest row that is:
  - in candidate statuses (`draft`, `partially_published`, `published` by default)
  - not already published on LinkedIn
  - and either has no required platforms or explicitly requires LinkedIn
- Build LinkedIn post text from `LinkedIn Post` field when present; otherwise derive it from title + summary/content.
- Publish through LinkedIn UGC API.
- Update Notion:
  - `LinkedIn URL`-style property (if present)
  - `Published Platforms`-style property by appending `LinkedIn`
  - `Publish Date`/`Published Date` (if present)
  - `Status` resolved from required platforms:
    - `published` when all required platforms are present in published platforms
    - `partially_published` otherwise

## Resource

- `scripts/publish_latest_to_linkedin.py`: End-to-end Notion -> LinkedIn -> Notion pipeline.
