# WordPress Application

## Auto-Deploy (Recommended)

Use `--deploy` flag to push CSS directly to WordPress. No manual steps needed.

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode creative \
  --brief "Your style description" \
  --site-name "Your Site" \
  --wp-url "https://yoursite.com" \
  --deploy
```

### What happens automatically

1. CSS style pack is generated to `output/wordpress-style-director/<run>/`
2. Credentials are loaded from `~/.claude/skills/.env`
3. Canonical URL is resolved (handles www redirects)
4. Admin auth is verified via REST API
5. Code Snippets plugin is installed/activated if needed
6. A PHP snippet outputs the CSS via `wp_head` at priority 999
7. Front-end is checked for CSS presence
8. Old helper plugins are cleaned up

### Deploying an existing CSS file

```bash
python3 scripts/deploy_to_wordpress.py \
  --css-file "/path/to/additional-css-combined.css" \
  --wp-url "https://yoursite.com" \
  --site-name "Your Site"
```

## Credential Setup

### 1. Create a WordPress Application Password

1. Log into WordPress admin
2. Go to `Users > Your Profile`
3. Scroll to **Application Passwords**
4. Enter a name (e.g. "Codex Style Director")
5. Click **Add New Application Password**
6. Copy the generated password (spaces are normal)

### 2. Add to .env file

Add these two lines to `~/.claude/skills/.env`:

```
WP_APP_USERNAME=your_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

The deploy script searches for `.env` files in this order:
1. `~/.claude/skills/.env`
2. `~/.agents/skills/.env`
3. `~/.env`
4. Custom path via `--env-file` flag

## Output Files

- `tokens.css`: CSS variables (`:root` design tokens)
- `wordpress-overrides.css`: Site-level and article-level style overrides
- `additional-css-combined.css`: The full CSS bundle (tokens + overrides)
- `summary.json`: Mode, palette, fonts, deployment status, and output metadata

## Managing Deployed CSS

### View in WordPress admin

The deployed CSS lives in: `Snippets > "WSD Style Pack – Your Site Name"`

### Update via CLI

Re-run the same command with `--deploy`. The existing snippet is updated in place.

### Revert / Remove

Option A: Deactivate the snippet in `Snippets` admin panel.
Option B: Via REST API:
```bash
# Find snippet ID
curl -s "https://yoursite.com/wp-json/code-snippets/v1/snippets" \
  -u "user:app-password" | python3 -m json.tool

# Deactivate snippet (replace ID)
curl -X PUT "https://yoursite.com/wp-json/code-snippets/v1/snippets/6/deactivate" \
  -u "user:app-password"
```

## Quick QA Checklist

After deployment (or manual paste), verify:

- [ ] Headings/body typography render with the expected fonts
- [ ] Links are readable in normal + hover state
- [ ] Content remains legible in article body and sidebar widgets
- [ ] Source lists are left-aligned and clickable links remain visible
- [ ] Buttons and forms are readable and consistent
- [ ] Mobile layout is correct (check at 375px and 768px widths)
- [ ] No WCAG contrast failures on text or links
- [ ] Print stylesheet hides nav/footer (Ctrl+P to check)

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 401 Unauthorized | www/non-www redirect dropping auth | Deploy script handles this automatically; if manual, use the non-www URL |
| CSS not visible after deploy | Server-side cache | Clear cache or wait; the snippet IS saved |
| `rest_cannot_view` errors | User role is not Administrator | Use an admin account for the Application Password |
| Code Snippets not installing | Plugin installation disabled by host | Install Code Snippets manually, then re-run deploy |
| Global Styles CSS not rendering | Classic theme (not block/FSE) | This is expected; Code Snippets approach works for both |
