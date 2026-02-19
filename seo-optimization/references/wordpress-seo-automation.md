# WordPress SEO Automation via REST API

Playbook for automating SEO fixes on WordPress sites using the WP REST API + Code Snippets plugin.

## Prerequisites

- WordPress site with REST API enabled (default)
- Application Password for an admin user (wp-admin > Users > Application Passwords)
- Code Snippets plugin active (for operations not exposed by REST API)
- Rank Math or Yoast SEO plugin (for meta descriptions, schema)

## Authentication

WordPress Application Passwords with spaces require explicit Base64 encoding:

```bash
# WRONG — curl -u fails with spaces in password
curl -u "user:pass word" https://site.com/wp-json/wp/v2/posts

# CORRECT — explicit Base64 Authorization header
AUTH=$(echo -n "user:pass word" | base64)
curl -H "Authorization: Basic $AUTH" https://site.com/wp-json/wp/v2/posts
```

**Gotcha**: Some hosts redirect `www` to non-www (or vice versa) and DROP the Authorization header during redirect. Always use the canonical URL (test with `curl -I`).

## Audit Sequence

Run these checks first to build a complete picture before making changes:

```bash
AUTH=$(echo -n "user:password" | base64)
BASE="https://site.com"

# 1. Site settings (title, tagline, default category)
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-json/wp/v2/settings"

# 2. All posts (titles, slugs, links, categories, authors)
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-json/wp/v2/posts?per_page=100&_fields=id,title,slug,link,categories,author"

# 3. All categories (check for "Non classé", empty categories)
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-json/wp/v2/categories?per_page=50&_fields=id,name,slug,count"

# 4. All users (check for "admin" display names)
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-json/wp/v2/users?_fields=id,name,slug,description"

# 5. Navigation menus
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-json/wp/v2/menu-items?per_page=50&_fields=id,title,url,menu_order"

# 6. Installed plugins
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-json/wp/v2/plugins"

# 7. Sitemap check
curl -s "$BASE/wp-sitemap.xml"

# 8. Permalink structure (look for /index.php/ in post links)
# If post links contain /index.php/, permalinks need fixing
```

## Common SEO Fixes

### 1. Site Title & Tagline

Bad: "Actualités, trucs et astuces pour les coachs — les news"
Good: "Les News du Coach — Veille marché et stratégie pour coachs indépendants"

```bash
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/settings" \
    -d '{"title":"Site Name","description":"Keyword-rich tagline under 60 chars"}'
```

Rules:
- Title: brand name, concise, recognizable
- Tagline: include primary keyword, describe the site's value proposition
- Both appear in `<title>` of every page, so keep them tight

### 2. Fix Permalinks (remove /index.php/ and dates)

The REST API doesn't expose `permalink_structure`. Use Code Snippets:

```php
// Snippet 1: Change permalink structure (runs once via admin_init)
add_action('admin_init', function() {
    $current = get_option('permalink_structure');
    if ($current !== '/%postname%/') {
        update_option('permalink_structure', '/%postname%/');
        flush_rewrite_rules();
    }
});
```

If new URLs return 404, the `.htaccess` needs WordPress rewrite rules:

```php
// Snippet 2: Force .htaccess rewrite rules (run once, then deactivate)
add_action('admin_init', function() {
    $htaccess = ABSPATH . '.htaccess';
    $current = file_exists($htaccess) ? file_get_contents($htaccess) : '';
    if (strpos($current, 'RewriteBase /') === false) {
        $rules = "# BEGIN WordPress\n<IfModule mod_rewrite.c>\nRewriteEngine On\nRewriteBase /\n";
        $rules .= "RewriteRule ^index\\.php$ - [L]\nRewriteCond %{REQUEST_FILENAME} !-f\n";
        $rules .= "RewriteCond %{REQUEST_FILENAME} !-d\nRewriteRule . /index.php [L]\n";
        $rules .= "</IfModule>\n# END WordPress\n";
        file_put_contents($htaccess, $rules . "\n" . $current);
    }
    flush_rewrite_rules(true);
});
```

**Important**: After confirming new URLs work (HTTP 200), trigger admin_init:
```bash
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-admin/admin-ajax.php?action=heartbeat"
```

Then deactivate the .htaccess snippet (keep only the redirect snippet active).

### 3. 301 Redirects for Old URLs

Keep this snippet permanently active to redirect old date-based URLs:

```php
// Persistent snippet: 301 redirect /YYYY/MM/DD/slug/ → /slug/
add_action('template_redirect', function() {
    $path = strtok($_SERVER['REQUEST_URI'], '?');
    $pattern = '@^(/index\\.php)?/\\d{4}/\\d{2}/\\d{2}/([a-z0-9][a-z0-9\\-]*)/?$@i';
    if (preg_match($pattern, $path, $matches)) {
        $slug = $matches[2];
        $posts = get_posts(array(
            'name' => $slug,
            'post_type' => 'post',
            'post_status' => 'publish',
            'numberposts' => 1
        ));
        if (!empty($posts)) {
            $new_url = get_permalink($posts[0]->ID);
            if ($new_url) {
                wp_redirect($new_url, 301);
                exit;
            }
        }
    }
});
```

After permalink changes, also update all internal links in article content:
```python
import re, requests, base64

# Pattern to match old URLs in content
old_pattern = re.compile(r'https?://site\.com/index\.php/\d{4}/\d{2}/\d{2}/([a-z0-9][a-z0-9\-]*)/?')

for post in posts:
    content = get_content(post['id'])
    new_content = old_pattern.sub(lambda m: slug_to_url.get(m.group(1), m.group(0)), content)
    if new_content != content:
        update_content(post['id'], new_content)
```

### 4. Category Restructuring

Common issues:
- "Non classé" / "Uncategorized" with articles in it
- Empty categories in sitemap
- Categories that don't match navigation menu
- Generic names ("Economie") instead of SEO-targeted names ("Marché du coaching")

```bash
# Create SEO-friendly category
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/categories" \
    -d '{"name":"Marché du coaching","slug":"marche-du-coaching","description":"Keyword-rich description"}'

# Reassign post to new category
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/posts/POST_ID" \
    -d '{"categories":[NEW_CAT_ID]}'

# Change default category (before deleting "Non classé")
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/settings" \
    -d '{"default_category":NEW_CAT_ID}'

# Delete empty category
curl -s -X DELETE -H "Authorization: Basic $AUTH" \
    "$BASE/wp-json/wp/v2/categories/OLD_CAT_ID?force=true"
```

**Checklist**: After restructuring categories, update the navigation menu to match:
```bash
# Update menu item
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/menu-items/ITEM_ID" \
    -d '{"title":"New Label","url":"https://site.com/category/new-slug/","type":"taxonomy","object":"category","object_id":CAT_ID}'

# Add new menu item
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/menu-items" \
    -d '{"title":"Label","url":"...","type":"taxonomy","object":"category","object_id":CAT_ID,"menus":MENU_ID,"menu_order":N,"status":"publish"}'
```

### 5. Rank Math Meta via REST API

Rank Math doesn't expose its fields in REST API by default. Deploy this persistent snippet:

```php
// Expose Rank Math SEO fields in WordPress REST API
add_action('init', function() {
    $fields = array('rank_math_title', 'rank_math_description', 'rank_math_focus_keyword', 'rank_math_robots');
    foreach (array('post', 'page') as $type) {
        foreach ($fields as $field) {
            register_post_meta($type, $field, array(
                'show_in_rest' => true,
                'single' => true,
                'type' => 'string',
                'auth_callback' => function() { return current_user_can('edit_posts'); }
            ));
        }
    }
});
```

Then set meta descriptions via standard REST API:
```bash
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/posts/POST_ID" \
    -d '{"meta":{"rank_math_title":"SEO Title (50-60 chars)","rank_math_description":"Meta description (150-160 chars)","rank_math_focus_keyword":"primary keyword"}}'
```

**For Yoast SEO**: Same approach, but field names are `_yoast_wpseo_title`, `_yoast_wpseo_metadesc`, `_yoast_wpseo_focuskw`.

### 6. Internal Linking (Maillage Interne)

Strategy:
- Every article should have 2-3 contextual internal links
- Link to thematically related articles (not just random)
- Place "À lire aussi" blocks before the Sources/References section
- Use descriptive anchor text (not "cliquez ici")

Implementation via Python:
```python
# Build URL map from current posts
posts = get_all_posts()
slug_to_url = {p['slug']: p['link'] for p in posts}

# For each article, insert contextual links
# Option A: Before the Sources/References heading
content = content.replace(
    "<h2>Sources</h2>",
    f'<p><strong>À lire aussi :</strong> <a href="{url1}">Title 1</a> — et <a href="{url2}">Title 2</a>.</p>\n<h2>Sources</h2>'
)

# Option B: Inline anchor in existing text
content = content.replace(
    "existing text phrase",
    f'<a href="{url}">existing text phrase</a>'
)
```

### 7. Author Profiles & E-E-A-T

Fix generic author names ("admin", "admin3330"):
```bash
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/users/USER_ID" \
    -d '{"name":"Display Name","nickname":"Display Name","first_name":"First","description":"Professional bio with credentials","url":"https://linkedin.com/in/profile"}'
```

Reassign all posts to the correct author:
```bash
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/posts/POST_ID" \
    -d '{"author":USER_ID}'
```

### 8. About Page (E-E-A-T)

Essential for YMYL-adjacent topics (coaching, health, finance). Must include:
- **Photo** (real, professional — check LinkedIn, company site, ICF directory)
- **Name and role**
- **Credentials** (certifications, education)
- **Experience** (concrete, not vague)
- **Links** (LinkedIn, professional directory listings)
- **Contact method** (email, form)
- **Internal links** to content categories

Upload author photo:
```bash
curl -s -X POST -H "Authorization: Basic $AUTH" \
    -H "Content-Disposition: attachment; filename=author-photo.jpg" \
    -H "Content-Type: image/jpeg" \
    --data-binary @/tmp/photo.jpg \
    "$BASE/wp-json/wp/v2/media"
```

**Gotcha**: Don't set both `featured_media` AND an inline `<img>` — many themes display the featured image automatically, causing duplicates. Use inline image only.

### 9. Fix Bad Slugs

Articles created with placeholder titles get useless slugs like `article-n1`:
```bash
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/wp/v2/posts/POST_ID" \
    -d '{"slug":"descriptive-keyword-rich-slug"}'
```

### 10. Cleanup

After completing all fixes:
- Delete unused pages (sample page, plugin-generated pages like Yatra)
- Remove empty categories
- Deactivate one-time Code Snippets (keep redirect and Rank Math snippets active)
- Verify sitemap reflects new structure: `curl $BASE/wp-sitemap.xml`
- Check no orphan pages exist

## Code Snippets REST API Reference

The Code Snippets plugin exposes `$BASE/wp-json/code-snippets/v1/snippets`:

```bash
# List all snippets
curl -s -H "Authorization: Basic $AUTH" "$BASE/wp-json/code-snippets/v1/snippets"

# Create snippet
curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/code-snippets/v1/snippets" \
    -d '{"name":"Name","code":"PHP code","active":true,"scope":"global","priority":10}'

# Update snippet
curl -s -X PUT -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/code-snippets/v1/snippets/ID" \
    -d '{"code":"new code","active":true}'

# Deactivate snippet
curl -s -X PUT -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \
    "$BASE/wp-json/code-snippets/v1/snippets/ID" \
    -d '{"active":false}'
```

## Full Automated Audit + Fix Sequence

1. **Audit**: settings, posts, categories, users, menus, plugins, sitemap
2. **Title/tagline**: update with keywords
3. **Permalinks**: switch to `/%postname%/`, fix .htaccess, add 301 redirects
4. **Categories**: create SEO-friendly ones, reassign posts, delete empty ones, update default
5. **Menu**: align navigation with new categories + add "À propos"
6. **SEO plugin meta**: expose Rank Math/Yoast fields, write meta descriptions + focus keywords
7. **Internal links**: add 2-3 contextual links per article
8. **Authors**: fix display names, add bios, upload photos, reassign posts
9. **About page**: create with E-E-A-T content, photo, credentials, links
10. **Cleanup**: delete junk pages, deactivate temp snippets, verify sitemap
