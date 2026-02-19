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

## Workflow (strict loop)
1. Baseline capture:
- Run `scripts/capture_layout_feedback.mjs` on target URLs at `75,80,100` zoom.
- Keep baseline screenshots + `report.json`.

2. Apply one change only:
- Update one WP snippet (or one page) via REST using `scripts/wp_snippet_update.py`.
- Do not batch multiple unrelated visual fixes.

3. Re-capture and compare:
- Run capture script again with same URLs/zooms.
- Check `report.json` for:
  - `menu_rows` > 1 (nav wrap)
  - `header_overlap_risk` true
  - `hero_visibility_risk` true

4. Fix and iterate:
- If any risk flag appears, patch CSS narrowly and repeat steps 2-3.
- Stop only when all target zooms pass.

5. Final handoff:
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

## Notes
- Keep fixes scoped with page/body selectors (`body.home`, `.page-id-XXXX`) before global rules.
- Prefer reducing selector blast radius over raising `!important` everywhere.
- Never trust one zoom level as final validation.
