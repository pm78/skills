# Skills Environment Variable Matrix

Generated from script-level env references (`scripts/*` and code files) and compared against `.env`.

## Legend

- `in .env`: variable currently defined in `/home/pascal/.agent/skills/.env`
- `missing`: variable referenced by a script but not currently defined in `.env` (may be optional, runtime-provided, or deprecated)

## By Skill

| Skill | Variables |
|---|---|
| `blog-writer` | _none detected_ |
| `brand-guidelines` | _none detected_ |
| `content-writer` | _none detected_ |
| `docx` | _none detected_ |
| `git-worktree-manager` | _none detected_ |
| `hubspot-prospection` | _none detected_ |
| `imagegen` | `OPENAI_API_KEY` (in .env) |
| `in-person-training-intelligence-suite` | _none detected_ |
| `linkedin-search` | _none detected_ |
| `multi-source-discovery` | `NEWSAPI_API_KEY` (in .env); `NEWSAPI_KEY` (missing); `NITTER_BASE_URL` (missing); `NOTION_TOKEN` (in .env); `OPENAI_API_KEY` (in .env); `OPENAI_MODEL` (in .env); `SOURCES_DB_ID` (in .env); `TAVILY_API_KEY` (in .env); `YOUTUBE_API_KEY` (in .env) |
| `notion-to-linkedin-publisher` | `LINKEDIN_ACCESS_TOKEN` (missing); `LINKEDIN_AUTHOR_URN` (missing); `MY_ARTICLES_DB_ID` (missing); `NOTION_TOKEN` (in .env) |
| `openclaw-skill-installer` | _none detected_ |
| `pdf` | _none detected_ |
| `pptx` | _none detected_ |
| `prospecting-intelligence` | _none detected_ |
| `publish-article` | `BRAND_PROFILES_DIR` (missing); `DEFAULT_SITE_KEY` (missing); `MY_ARTICLES_DB_ID` (missing); `NOTION_TOKEN` (in .env); `OPENAI_API_KEY` (in .env); `OPENAI_IMAGE_MODEL` (missing); `OPENAI_IMAGE_QUALITY` (missing); `OPENAI_IMAGE_SIZE` (missing); `PUBLICATIONS_DB_ID` (in .env); `WORDPRESS_APP_PASSWORD` (missing); `WORDPRESS_SITE` (missing); `WORDPRESS_USERNAME` (missing); `WP_APP_PASSWORD` (missing); `WP_APP_USERNAME` (missing); `WP_BRAND_PROFILE` (missing); `WP_SITES_CONFIG` (missing); `WP_SITE_KEY` (missing); `WP_URL` (missing); `WP_USERNAME` (missing) |
| `report-synthesizer` | _none detected_ |
| `research-brief` | _none detected_ |
| `retell-cold-caller` | `RETELL_API_KEY` (in .env) |
| `seo-optimization` | _none detected_ |
| `skill-creator` | _none detected_ |
| `skill-installer` | `CODEX_HOME` (missing); `GH_TOKEN` (missing); `GITHUB_TOKEN` (missing) |
| `skills-github-push` | `CODEX_HOME` (missing) |
| `source-to-article-newsletter` | `MY_ARTICLES_DB_ID` (missing); `NOTION_TOKEN` (in .env); `OPENAI_API_KEY` (in .env); `OPENAI_MODEL` (in .env); `SOURCES_DB_ID` (in .env) |
| `strategy-intelligence-suite` | _none detected_ |
| `vapi-calls` | `VAPI_API_KEY` (missing); `VAPI_ASSISTANT_ID` (missing); `VAPI_LLM_MODEL` (missing); `VAPI_LLM_PROVIDER` (missing); `VAPI_PHONE_NUMBER_ID` (missing); `WEBHOOK_BASE_URL` (missing); `WEBHOOK_PORT` (missing) |
| `web-research` | _none detected_ |
| `wordpress-style-director` | _none detected_ |
| `worldline-brand-guidelines` | _none detected_ |
| `xlsx` | _none detected_ |
| `youtube-subscriptions-ingestor` | `NOTION_TOKEN` (in .env); `OPENAI_API_KEY` (in .env); `OPENAI_MODEL` (in .env); `SOURCES_DB_ID` (in .env); `YOUTUBE_API_KEY` (in .env) |

## Global Summary

- Skills scanned: `31`
- Unique script-level variables: `39`
- Variables present in `.env`: `9`
- Variables missing from `.env`: `30`

### Present in `.env`

`NEWSAPI_API_KEY`, `NOTION_TOKEN`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `PUBLICATIONS_DB_ID`, `RETELL_API_KEY`, `SOURCES_DB_ID`, `TAVILY_API_KEY`, `YOUTUBE_API_KEY`

### Missing from `.env`

`BRAND_PROFILES_DIR`, `CODEX_HOME`, `DEFAULT_SITE_KEY`, `GH_TOKEN`, `GITHUB_TOKEN`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN`, `MY_ARTICLES_DB_ID`, `NEWSAPI_KEY`, `NITTER_BASE_URL`, `OPENAI_IMAGE_MODEL`, `OPENAI_IMAGE_QUALITY`, `OPENAI_IMAGE_SIZE`, `VAPI_API_KEY`, `VAPI_ASSISTANT_ID`, `VAPI_LLM_MODEL`, `VAPI_LLM_PROVIDER`, `VAPI_PHONE_NUMBER_ID`, `WEBHOOK_BASE_URL`, `WEBHOOK_PORT`, `WORDPRESS_APP_PASSWORD`, `WORDPRESS_SITE`, `WORDPRESS_USERNAME`, `WP_APP_PASSWORD`, `WP_APP_USERNAME`, `WP_BRAND_PROFILE`, `WP_SITES_CONFIG`, `WP_SITE_KEY`, `WP_URL`, `WP_USERNAME`
