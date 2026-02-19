---
name: wordpress-style-director
description: Generate WordPress-ready CSS style packs from (1) a reference website URL, (2) brand-guideline files, or (3) a creative brief, then auto-deploy to WordPress via the REST API. Use when users ask to restyle a WordPress site, mimic a style direction, apply brand identity, or create a fresh visual direction.
---

# WordPress Style Director

Generate a reusable style pack for WordPress and **auto-deploy** it to the live site via the REST API. No manual copy-paste required.

## Credentials

WordPress Application Password credentials are loaded automatically from the first `.env` file found at:

1. `~/.claude/skills/.env`  (default)
2. `~/.agents/skills/.env`
3. `~/.env`

Required keys:

```
WP_APP_USERNAME=pascal
WP_APP_PASSWORD=Fh4h 6dVX uuk5 OqOQ 8KDO NqiJ
```

Generate an Application Password in WordPress at: `Users > Your Profile > Application Passwords`.

## Workflow

1. Choose mode:
   - `style-reference`: user provides website URL
   - `brand-guided`: user provides brand guideline file
   - `creative`: user provides style brief
2. Run the generator script with `--deploy` to auto-push to WordPress.
3. The script will:
   - Generate the CSS style pack.
   - Resolve the canonical site URL (handles www/non-www redirects).
   - Authenticate via the WordPress REST API.
   - Install the **Code Snippets** plugin if not present.
   - Create or update a front-end PHP snippet that outputs the CSS.
   - Verify the CSS is rendering on the live front-end.
   - Clean up any temporary helper plugins.
4. Review `summary.json` for deployment results.

For mode behavior and legal guardrails, read `references/modes-and-guardrails.md`.
For deployment details and QA, read `references/wordpress-application.md`.

## Commands

### Generate + Deploy (recommended)

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode creative \
  --brief "Premium editorial dark theme for AI and longevity content" \
  --site-name "Timeless Wisdom" \
  --wp-url "https://www.thrivethroughtime.com" \
  --footer-credit-text "© 2026 | Proudly Powered by Thrivethroughtime" \
  --favicon-file "/path/to/favicon.png" \
  --deploy
```

### Style-reference mode + Deploy

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode style-reference \
  --site-url "https://example.com" \
  --site-name "My Site" \
  --wp-url "https://mysite.com" \
  --deploy
```

### Brand-guided mode + Deploy

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode brand-guided \
  --brand-file "/path/to/brand-guidelines.md" \
  --site-name "My Brand" \
  --wp-url "https://mybrand.com" \
  --deploy
```

### Generate only (no deploy)

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode creative \
  --brief "Clean minimal style" \
  --font-heading "Sora" \
  --font-body "Inter" \
  --run-name "minimal-refresh"
```

### Deploy an existing CSS file

```bash
python3 scripts/deploy_to_wordpress.py \
  --css-file "output/wordpress-style-director/my-run/additional-css-combined.css" \
  --wp-url "https://mysite.com" \
  --site-name "My Site" \
  --favicon-file "/path/to/favicon.png"
```

### Dry-run summary only

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode style-reference \
  --site-url "https://example.com" \
  --dry-run
```

## CLI Flags

| Flag | Description |
|---|---|
| `--mode` | `style-reference`, `brand-guided`, or `creative` (required) |
| `--site-url` | Reference URL for style-reference mode |
| `--brand-file` | Brand guideline file for brand-guided mode |
| `--brief` | Creative brief for creative mode |
| `--site-name` | Site/brand name for output labeling |
| `--wp-url` | WordPress site URL for deployment |
| `--deploy` | Auto-deploy CSS to WordPress via REST API |
| `--env-file` | Custom path to `.env` file with credentials |
| `--font-heading` | Override heading font family |
| `--font-body` | Override body font family |
| `--run-name` | Fixed output folder name |
| `--skip-verify` | Skip front-end verification after deploy |
| `--footer-credit-text` | Inject a custom footer credit line in `.site-info` |
| `--favicon-file` | Upload file and set as WordPress Site Icon (favicon) |
| `--dry-run` | Print summary only, no files written |

## Outputs

The script writes into `output/wordpress-style-director/<run-name-or-timestamp>/`:

- `tokens.css` — CSS custom properties
- `wordpress-overrides.css` — WordPress-specific selectors
- `additional-css-combined.css` — Paste-ready or auto-deployed bundle
- `summary.json` — Metadata, palette, fonts, and deployment results

## Technical Notes

### Classic vs Block Themes
- **Classic themes** (e.g. Nisarg, Astra, GeneratePress): CSS is deployed via Code Snippets plugin using a PHP `wp_head` hook. The WordPress Customizer's "Additional CSS" and the Global Styles API do NOT reliably output user CSS for classic themes.
- **Block/FSE themes** (e.g. Twenty Twenty-Four): Could also use the Global Styles `css` field, but the Code Snippets approach works universally for both.

### www/non-www Redirects
WordPress often redirects `www.example.com` to `example.com` (or vice versa). This redirect **drops the Authorization header**, causing 401 errors. The deploy script auto-detects this and uses the canonical URL for all API calls.

### App Password vs Login Password
WordPress Application Passwords work for REST API and XMLRPC only. They do NOT work for `wp-login.php` cookie-based authentication.

### Idempotent Updates
Re-running `--deploy` updates the existing Code Snippets snippet rather than creating duplicates. The script searches by name prefix `"WSD Style Pack"`.

## Guardrails

- Inspired-by styling only; never pixel-perfect cloning of another site.
- Generated CSS includes content readability rules (left alignment, link clarity, source-list consistency).
- Deployment is reversible: deactivate the snippet in Code Snippets admin or delete it via the REST API.
