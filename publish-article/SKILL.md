---
name: publish-article
description: Publish automation that finds the latest draft article in Notion `My Articles`, posts it to WordPress via REST API, then marks that Notion article as `published`. Use when asked to publish drafted Notion articles to a WordPress site and sync publication status back to Notion.
---

# Publish Article

## Overview

Publish one article per run: select the most recently edited row in `My Articles` where status matches `draft`, publish it to WordPress, then update Notion status to `published`.

## Required Environment

Set these variables before running the script:

- `NOTION_TOKEN`
- `MY_ARTICLES_DB_ID` (optional; defaults to your current DB ID)
- `WP_USERNAME` (or `WORDPRESS_USERNAME` or `WP_APP_USERNAME`)
- `WP_APP_PASSWORD` (or `WORDPRESS_APP_PASSWORD`)

Optional:

- `WORDPRESS_SITE` (defaults to `https://thrivethroughtime.com`)

## Commands

Run a dry run first:

```bash
python3 scripts/publish_latest_draft.py --dry-run
```

Run live publish:

```bash
python3 scripts/publish_latest_draft.py
```

Use custom status labels when needed:

```bash
python3 scripts/publish_latest_draft.py \
  --draft-status Draft \
  --published-status Published
```

Print machine-readable output:

```bash
python3 scripts/publish_latest_draft.py --print-json
```

## Behavior

- Auto-detect Notion properties for title, status, content, slug, and summary.
- Prefer content from a `Content` rich text field; fall back to Notion page blocks if empty.
- Convert markdown content to HTML before posting to WordPress.
- Publish via `POST /wp-json/wp/v2/posts` with status `publish`.
- Update Notion status after publish.
- Also update `Publish Date` and URL property (`Published URL`, `WordPress URL`, `Post URL`, or `URL`) if present.
- Stop with a clear error if no draft article is found.

## Resource

- `scripts/publish_latest_draft.py`: End-to-end Notion -> WordPress -> Notion publish pipeline.
