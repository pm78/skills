# Réseau de coachs: field notes

Date: 2026-02-20

## Problem patterns observed
- Shortcodes and raw HTML blocks made key pages effectively non-editable for admins.
- Logo blocks looked correct on front-end but broke in editor (overflow / inconsistent sizing).
- Last-row logo tiles appeared visually inconsistent when grid behavior depended on auto-fit width.

## Stable solution pattern
1. Replace shortcode sections with native Gutenberg blocks.
2. Use a single Gallery block for logo references.
3. Enforce tile geometry in CSS (fixed grid + flex-centered tile + constrained logo image).
4. Mirror the same style constraints in editor (`wp-edit-blocks`) and front-end.
5. Validate with visual captures after each change.

## Operational checklist
- [ ] Home page has block content (no `[lnf_homepage]`).
- [ ] References page has block content (no `[lnf_references]`).
- [ ] Logo section is `wp:gallery` with editable columns.
- [ ] Last row tile sizes match previous rows.
- [ ] User can add/remove/reorder logos from Gutenberg UI.
