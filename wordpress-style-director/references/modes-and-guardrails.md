# Modes and Guardrails

## Modes

### `style-reference`

Use when the user provides a website URL and wants a similar look-and-feel.

- Extract top colors and font families from HTML/CSS.
- Build inspired-by tokens and WordPress overrides.
- Do not copy exact layouts, logos, or trademark-specific brand signatures.

### `brand-guided`

Use when the user provides brand guidelines or a brand style file.

- Parse colors and fonts from `.json`, `.md`, or `.txt` guideline files.
- Prioritize explicit brand colors over inferred ones.

### `creative`

Use when the user wants a net-new visual direction.

- Select a creative profile from brief keywords.
- Generate a coherent token set and practical WordPress overrides.

## Deployment

### Auto-deploy via REST API (`--deploy`)

When `--deploy` is passed, the skill automatically pushes CSS to WordPress:

1. **Credentials**: Loaded from `~/.claude/skills/.env` (or `--env-file` override). Required keys: `WP_APP_USERNAME`, `WP_APP_PASSWORD`.
2. **URL resolution**: Detects www/non-www redirects that drop auth headers. Uses canonical URL for all API calls.
3. **Authentication**: Verifies admin-level access via `/wp-json/wp/v2/users/me`.
4. **Plugin management**: Installs and activates the **Code Snippets** plugin (from wordpress.org) if not already present.
5. **Snippet deployment**: Creates a PHP snippet with scope `front-end` that outputs CSS via `wp_head` hook at priority 999.
6. **Verification**: Fetches the front-end HTML and checks that CSS variables and the style block are present.
7. **Cleanup**: Removes temporary plugins (Simple Custom CSS, WPCode Lite) if found from prior manual attempts.

### Why Code Snippets (not Customizer or Global Styles)

| Method | Works for Classic Themes | Works for Block Themes | REST API writable | Idempotent |
|---|---|---|---|---|
| Customizer Additional CSS (`custom_css` post type) | Yes | Yes | No (requires cookie auth + nonce) | N/A |
| Global Styles `css` field | No | Yes | Yes | Yes |
| Code Snippets `front-end` PHP | **Yes** | **Yes** | **Yes** | **Yes** |

The Code Snippets approach is the only one that works universally across all theme types via the REST API with Application Password auth.

### Idempotent updates

Re-running `--deploy` searches for an existing snippet with the name prefix `"WSD Style Pack"` and updates it in place. No duplicate snippets are created.

## Guardrails

- Produce inspired-by styling only, never pixel-perfect cloning.
- Preserve readability and contrast.
- Keep article text left-aligned and source lists non-justified.
- Prefer reversible CSS changes — deactivate the snippet to revert instantly.
- Validate WCAG AA contrast ratios for link and text colors.

## Known Pitfalls

- **www/non-www redirects**: WordPress redirects between `www.` and non-www variants drop the `Authorization` header. The deploy script resolves this automatically.
- **App Passwords vs login passwords**: Application Passwords only work for REST API and XMLRPC. They do NOT work for `wp-login.php`.
- **Classic themes ignore Global Styles `css`**: The `styles.css` field in `/wp/v2/global-styles/{id}` is only rendered by block/FSE themes. Classic themes like Nisarg, Astra, etc. ignore it.
- **Caching**: Some hosting providers or plugins (Wordfence, WP Super Cache) may cache the front-end. Verification may show FAIL immediately after deploy; the CSS is still saved and will appear after cache expiry.
