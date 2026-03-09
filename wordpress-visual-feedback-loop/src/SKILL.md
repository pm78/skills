---
name: wordpress-visual-feedback-loop
description: Use this skill when updating WordPress styling/content via REST API and you need a strict visual feedback loop (multi-zoom screenshots, layout diagnostics, and iterative fixes) to catch inconsistencies like menu wrapping, header overlap, cropped hero, or typography drift.
---

# WordPress Visual Feedback Loop

Use this skill for high-precision front-end edits where visual regressions can appear across zoom levels.

## When to use
- User asks for iterative style fixes on a live WordPress site.
- You must validate at multiple zoom levels (e.g. 75%, 80%, 100%).
- Prior edits caused side effects (header overlap, nav wrapping, spacing drift).

## Required env
- `WP_TTT_APP_USERNAME`
- `WP_TTT_APP_PASSWORD`
- Or equivalent site-specific app credentials (for example `WP_LNC_APP_USERNAME` / `WP_LNC_APP_PASSWORD`).

## Workflow (strict loop)
1. Baseline capture:
- Run `scripts/capture_layout_feedback.mjs` on target URLs at `75,80,100` zoom.
- Keep baseline screenshots + `report.json`.
- Also run a split-screen simulation for zoom-sensitive bugs:
  - `960x900` viewport at `80%` zoom (minimum).
  - Optional tighter checks: `920` and `880` widths.

2. Active snippet audit first:
- List active snippets on the site before editing.
- Identify possible conflicting snippets touching nav/header/hero typography.
- Decide whether to patch existing snippet or create a dedicated hotfix snippet.

3. Apply one change only:
- Update one WP snippet (or one page) via REST using `scripts/wp_snippet_update.py`.
- Do not batch multiple unrelated visual fixes.

4. Re-capture and compare:
- Run capture script again with same URLs/zooms.
- Check `report.json` for:
  - `menu_rows` > 1 (nav wrap)
  - `header_overlap_risk` true
  - `hero_visibility_risk` true
- Re-check split-screen simulation (`960x900 @ 80%`) because full-width captures can miss wrap issues.
- Confirm CSS truly landed in rendered HTML (not just saved in snippet).

5. Fix and iterate:
- If any risk flag appears, patch CSS narrowly and repeat steps 2-3.
- Stop only when all target zooms pass.
- If visual size is still wrong, compare computed sizes with browser evaluation:
  - `getComputedStyle(...).fontSize` in px for title/subtitle/body/nav.
  - Do not rely on `rem` assumptions across themes.

6. Final handoff:
- Report exact snippet/page IDs touched.
- Summarize what changed and what visual risks were cleared.

## Commands

### A) Capture visual diagnostics (multi-zoom)
```bash
node scripts/capture_layout_feedback.mjs \
  --urls "https://thrivethroughtime.com/,https://thrivethroughtime.com/about/" \
  --zooms "75,80,100" \
  --out-dir "/tmp/wp-feedback-run"
```

### B) Update one snippet through REST
```bash
python3 scripts/wp_snippet_update.py \
  --site "https://thrivethroughtime.com" \
  --snippet-id 7 \
  --code-file "/tmp/snippet7.php"
```

### C) Split-screen reproduction check (example)
```bash
node - <<'JS'
const { chromium } = require('playwright');
(async()=>{
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:960,height:900}});
  await page.goto('https://thrivethroughtime.com/',{waitUntil:'networkidle'});
  await page.evaluate(()=>document.body.style.zoom='0.8');
  await page.screenshot({path:'/tmp/wp-feedback-960-z80.png', fullPage:false});
  await browser.close();
})();
JS
```

## Notes
- Start with narrow scope (`body.home`, `.page-id-XXXX`) when the issue is page-specific.
- If the element is shared site-wide (for example header hero branding), promote to global scope to keep consistency across home/blog/category/archive.
- Prefer reducing selector blast radius over raising `!important` everywhere.
- Never trust one zoom level as final validation.
- Prefer dedicated hotfix snippets for isolated behavior changes; they are easier to rollback than large monolithic snippet edits.

## Field Lessons (Réseau de coachs)

Apply these rules when the user asks for a site that is visually stable **and** editable by admin users.

1. Editable blocks first (anti-lock-in)
- Do not leave critical pages on shortcodes (`[lnf_homepage]`, `[lnf_references]`) when user expects direct editing.
- Migrate content to native Gutenberg blocks (`group`, `heading`, `paragraph`, `image`, `columns`, `gallery`).
- Remove raw HTML mega-blocks for bios/authors when possible; convert to block structure so non-technical admins can edit safely.

2. Editor/front parity is mandatory
- Every visual rule applied to front-end tiles/cards must be mirrored in editor styles via `wp_add_inline_style('wp-edit-blocks', $css)`.
- If not mirrored, user sees broken layout in editor and cannot manage content confidently.

3. Reference logos: force equal tiles + auto-fit logos
- Use a native `Gallery` block for references.
- Enforce a predictable grid in CSS for `.lnf-logo-gallery.has-nested-images` and column classes (`.columns-2` ... `.columns-6`).
- Tile requirements:
  - `width: 100%`, `height: 100%`, `min-height: var(--lnf-logo-tile-min-height)`
  - `display:flex; align-items:center; justify-content:center`
  - `box-sizing:border-box; overflow:hidden`
- Image requirements:
  - `max-width: min(100%, var(--lnf-logo-max-width))`
  - `max-height: var(--lnf-logo-max-height)`
  - centered block display.

4. Last row stability
- Avoid `auto-fit` behavior when the user expects all tiles to keep identical visual size.
- Validate that the final row (e.g. 2 logos) keeps same tile dimensions as full rows.

5. Validation loop additions
- After each logo-grid change: capture homepage + references page at minimum 100% zoom and inspect the last row.
- If user reports editor mismatch, inspect block markup first (shortcode vs gallery) before CSS tweaks.

Reference: `references/reseaudecoachs-field-notes.md`.

