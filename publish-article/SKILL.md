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
  - `WP_TTT_APP_USERNAME`
  - `WP_TTT_APP_PASSWORD`
  - `WP_LNC_APP_USERNAME`
  - `WP_LNC_APP_PASSWORD`

Optional:

- `PUBLICATIONS_DB_ID` (if set, create one publication log row per publish)
- `WP_SITE_KEY` (target site key from config, for example `thrivethroughtime` or `lesnewsducoach`)
- `DEFAULT_SITE_KEY` (fallback site key; default `lesnewsducoach`)
- `WP_SITES_CONFIG` (path override; default `config/wp_sites.json`)
- `WP_BRAND_PROFILE` (optional brand profile override for illustration style)
- `OPENAI_IMAGE_MODEL` (optional; default `gpt-image-1`)
- `OPENAI_IMAGE_SIZE` (optional; default `1536x1024`)
- `OPENAI_IMAGE_QUALITY` (optional; default `high`)
- `BRAND_PROFILES_DIR` (path to brand profile presets; default points to `brand-guidelines/assets/profiles`)
- Legacy single-site fallback vars remain supported:
  - `WORDPRESS_SITE` or `WP_URL`
  - `WP_USERNAME`, `WORDPRESS_USERNAME`, or `WP_APP_USERNAME`
  - `WP_APP_PASSWORD` or `WORDPRESS_APP_PASSWORD`

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
    "brand_profile": "brand-profile-id",
    "default_category": "optional category slug|name|id fallback",
    "category_aliases": { "optional notion tag/keyword": "wordpress-category-slug" },
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

Override brand profile for image styling:

```bash
python3 scripts/publish_latest_draft.py --site lesnewsducoach --brand-profile lesnewsducoach
```

## Behavior

- Auto-detect Notion properties for title, status, content, slug, and summary.
- Auto-detect optional Notion category/tag properties (`Category/Categories/Catégorie/Catégories`, `Tags/Keywords/...`) to drive taxonomy mapping.
- Auto-detect optional Notion target-site property (`Target Site`, `Publish Site`, `Site`, `Website`, etc.).
- Resolve target site in this order:
  - `--site` / `WP_SITE_KEY`
  - article row target-site value
  - `--default-site-key` / `DEFAULT_SITE_KEY`
- Resolve brand style profile for images in this order:
  - `--brand-profile` / `WP_BRAND_PROFILE`
  - `brand_profile` (or `brand_id`) from selected site config
  - selected site key
- Default image style is now inferred from the selected brand profile rendering cues (for example photorealistic vs illustration), instead of always forcing illustration style.
- Prefer content from a `Content` rich text field; fall back to Notion page blocks if empty.
- Convert markdown content to clean HTML with headings, bold/italic, quotes, lists, code, and paragraphs.
- Convert bare URLs and markdown links into clickable anchors.
- Convert inline citations like `[1]` into links to source entries.
- Render a structured clickable `Sources` section (`<ol>` with anchor targets).
- Publish via `POST /wp-json/wp/v2/posts` with status `publish`.
- Publish with comments/pings disabled by default (`comment_status=closed`, `ping_status=closed`).
- Resolve WordPress categories before publish:
  - Priority 1: explicit Notion categories (if present)
  - Priority 2: Notion tags/keywords mapped to available WordPress categories
  - Priority 3: content inference (title/excerpt/body vs available category names/slugs)
  - Priority 4: `default_category` (site config) or site uncategorized fallback
- Publish with `categories` set in WordPress payload when at least one category is resolved.
- Ensure at least one illustration:
  - If content already contains an image, keep it.
  - Else if an `Illustration URL`/`Featured Image URL`-style property exists in Notion and has a URL, download it, optimize/compress it when needed (Pillow fallback logic), upload to WordPress media, and set it as `featured_media` when possible.
  - Else generate an illustration with OpenAI Images, optimize/compress image bytes before upload (especially oversized PNG outputs), upload to WordPress media, and set it as `featured_media` (fallback: prepend inline when media ID is unavailable).
- Compute and write Rank Math SEO metadata on every publish:
  - `rank_math_title` (length-normalized, CTR-safe)
  - `rank_math_description` (target <= 158 chars after cleanup)
  - `rank_math_focus_keyword` (category/tag/title-derived fallback)
- Run post-publish frontend verification checks:
  - single `<title>`
  - single `<meta name="description">` and valid description length
  - single canonical tag
  - single `<h1>`
  - comments/pings closed
  - OG tag presence (`og:title`, `og:description`, `og:image`)
- Enforce an SEO gate before Notion status update:
  - If Rank Math metadata write fails or required verification checks fail, the script exits with an SEO gate error and does **not** mark the article as published in Notion.
- Update Notion status after publish.
- If a `Required Platforms`-style property exists (`Required Platforms`, `Target Platforms`, `Publish Targets`, `Target Channels`, `Publish On`, `Channels`), status is resolved automatically:
  - `published` when all required platforms are present in published platforms
  - `partially_published` otherwise
- Also update `Publish Date` and URL property (`Published URL`, `WordPress URL`, `Post URL`, or `URL`) if present.
- Write resolved categories back to Notion when a category-like property exists.
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
