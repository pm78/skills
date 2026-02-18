---
name: publish-article
description: Publish automation that finds the latest draft article in Notion `My Articles`, posts it to WordPress via REST API, then marks that Notion article as `published`. Use when asked to publish drafted Notion articles to a WordPress site and sync publication status back to Notion.
---

# Publish Article

## Overview

Publish one article per run: select the latest `draft` row in Notion `My Articles`, publish it to WordPress, update Notion status/platform fields, and optionally write a publication-log row in a `Publications` database.

## Required Environment

Set these variables before running the script:

- `NOTION_TOKEN`
- `MY_ARTICLES_DB_ID` (optional; defaults to your current DB ID)
- `OPENAI_API_KEY` (needed when an article has no image and the script must generate one)
- Site credentials used by `config/wp_sites.json`:
  - `WP_USERNAME`
  - `WP_APP_PASSWORD`
  - `WP_LNC_USERNAME`
  - `WP_LNC_APP_PASSWORD`

Optional:

- `PUBLICATIONS_DB_ID` (if set, create one publication log row per publish)
- `WP_SITE_KEY` (target site key from config, for example `thrivethroughtime` or `lesnewsducoach`)
- `DEFAULT_SITE_KEY` (fallback site key; default `thrivethroughtime`)
- `WP_SITES_CONFIG` (path override; default `config/wp_sites.json`)
- Legacy single-site fallback vars remain supported:
  - `WORDPRESS_SITE` or `WP_URL`
  - `WORDPRESS_USERNAME` or `WP_APP_USERNAME`
  - `WORDPRESS_APP_PASSWORD`

## Multi-Site Config

Default registry file:

- `config/wp_sites.json`

Expected shape:

```json
{
  "site_key": {
    "wp_url": "https://example.com",
    "username_env": "WP_SITE_USERNAME",
    "password_env": "WP_SITE_APP_PASSWORD",
    "platform_name": "WordPress-SiteName",
    "notion_site_label": "site_label",
    "aliases": ["optional alias", "optional domain"]
  }
}
```

## Commands

Run a dry run first:

```bash
python3 scripts/publish_latest_draft.py --dry-run
```

Run live publish:

```bash
python3 scripts/publish_latest_draft.py
```

Publish to a specific site key:

```bash
python3 scripts/publish_latest_draft.py --site lesnewsducoach
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

Write publication logs into a Notion Publications DB:

```bash
python3 scripts/publish_latest_draft.py \
  --publications-db-id "$PUBLICATIONS_DB_ID"
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
- Auto-detect optional Notion target-site property (`Target Site`, `Publish Site`, `Site`, `Website`, etc.).
- Resolve target site in this order:
  - `--site` / `WP_SITE_KEY`
  - article row target-site value
  - `--default-site-key` / `DEFAULT_SITE_KEY`
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
- If a `Published Platforms`-style property exists (`Published Platforms`, `Published On`, `Platforms Published`, `Published To`, `Live On`), append this run's platform value.
- Write generated/reused illustration URL back into a Notion image URL property when available.
- If `PUBLICATIONS_DB_ID` is configured, create a publication row and map best-effort fields:
  - title
  - relation to article
  - site/platform
  - status (`Published`)
  - published URL
  - WP post ID
  - published date
  - illustration URL
- Avoid duplicate top images by preferring WordPress `featured_media` placement when media ID is available.
- Stop with a clear error if no draft article is found.

## Resource

- `scripts/publish_latest_draft.py`: End-to-end Notion -> WordPress -> Notion publish pipeline.
- `config/wp_sites.json`: Site registry for multi-site publishing.
