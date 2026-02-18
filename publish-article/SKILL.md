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
- `OPENAI_API_KEY` (needed when an article has no image and the script must generate one)

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
  --published-status Published \
  --partially-published-status Partially Published
```

Track which channel this run published to:

```bash
python3 scripts/publish_latest_draft.py \
  --platform-name WordPress
```

Print machine-readable output:

```bash
python3 scripts/publish_latest_draft.py --print-json
```

Skip automatic illustration logic:

```bash
python3 scripts/publish_latest_draft.py --skip-illustration
```

## Behavior

- Auto-detect Notion properties for title, status, content, slug, and summary.
- Prefer content from a `Content` rich text field; fall back to Notion page blocks if empty.
- Convert markdown content to clean HTML with headings, bold/italic, quotes, lists, code, and paragraphs.
- Convert bare URLs and markdown links into clickable anchors.
- Convert inline citations like `[1]` into links to source entries.
- Render a structured clickable `Sources` section (`<ol>` with anchor targets).
- Publish via `POST /wp-json/wp/v2/posts` with status `publish`.
- Ensure at least one illustration:
  - If content already contains an image, keep it.
  - Else if an `Illustration URL`/`Featured Image URL`-style property exists in Notion and has a URL, reuse it.
  - Else generate an illustration with OpenAI Images, upload to WordPress media, and set it as `featured_media` (fallback: prepend inline when media ID is unavailable).
- Update Notion status after publish.
- If a `Required Platforms`-style property exists (`Required Platforms`, `Target Platforms`, `Publish Targets`, `Target Channels`, `Publish On`, `Channels`), status is resolved automatically:
  - `published` when all required platforms are present in published platforms
  - `partially_published` otherwise
- Also update `Publish Date` and URL property (`Published URL`, `WordPress URL`, `Post URL`, or `URL`) if present.
- If a `Published Platforms`-style property exists (`Published Platforms`, `Published On`, `Platforms Published`, `Published To`, `Live On`), append this run's platform value (default: `WordPress`).
- Write generated/reused illustration URL back into a Notion image URL property when available.
- Avoid duplicate top images by preferring WordPress `featured_media` placement when media ID is available.
- Stop with a clear error if no draft article is found.

## Resource

- `scripts/publish_latest_draft.py`: End-to-end Notion -> WordPress -> Notion publish pipeline.
