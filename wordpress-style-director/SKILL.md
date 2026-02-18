---
name: wordpress-style-director
description: Generate WordPress-ready CSS style packs from (1) a reference website URL, (2) brand-guideline files, or (3) a creative brief, including design tokens and practical theme overrides. Use when users ask to restyle a WordPress site, mimic a style direction, apply brand identity, or create a fresh visual direction.
---

# WordPress Style Director

Generate a reusable style pack for WordPress and deliver paste-ready CSS for `Appearance -> Customize -> Additional CSS`.

## Workflow

1. Choose mode:
   - `style-reference`: user provides website URL
   - `brand-guided`: user provides brand guideline file
   - `creative`: user provides style brief
2. Run the generator script.
3. Review `summary.json` and `additional-css-combined.css`.
4. Apply CSS to WordPress and validate desktop/mobile readability.

For mode behavior and legal guardrails, read `references/modes-and-guardrails.md`.
For apply instructions and QA, read `references/wordpress-application.md`.

## Commands

### Style-reference mode

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode style-reference \
  --site-url "https://example.com" \
  --site-name "My Site"
```

### Brand-guided mode

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode brand-guided \
  --brand-file "/path/to/brand-guidelines.md" \
  --site-name "My Brand"
```

### Creative mode

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode creative \
  --brief "Premium editorial dark theme for AI and longevity content" \
  --site-name "Timeless Wisdom"
```

### Optional overrides

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode creative \
  --brief "Clean minimal style" \
  --font-heading "Sora" \
  --font-body "Inter" \
  --run-name "minimal-refresh"
```

### Dry-run summary only

```bash
python3 scripts/generate_wp_style_pack.py \
  --mode style-reference \
  --site-url "https://example.com" \
  --dry-run
```

## Outputs

The script writes into `output/wordpress-style-director/<run-name-or-timestamp>/`:

- `tokens.css`
- `wordpress-overrides.css`
- `additional-css-combined.css`
- `summary.json`

## Notes

- Use inspired-by style transfer only; do not clone another site exactly.
- Generated CSS includes content readability rules (left alignment, link clarity, source-list consistency).
- Keep changes reversible by applying through Additional CSS first.
