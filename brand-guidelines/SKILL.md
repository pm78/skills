---
name: brand-guidelines
description: Build and apply brand style guidelines for any company by selecting a brand preset or extracting a profile from website URLs, .pptx themes, and .docx templates. Use when the user needs logos, color palettes, typography, policy/guideline links, or consistent branded formatting across outputs.
---

# Multi-Brand Guidelines

Use this skill to create a brand profile and apply it consistently to the requested artifact.

## Workflow

1. Build candidate profiles.
2. Ask the user which brand should be used for the current task.
3. Select exactly one profile with `select_brand_profile.py`.
4. Apply the selected profile to the output.
5. Keep the selected profile path in context while generating follow-up assets.

## Build Candidate Profiles

### Option A: Use built-in presets

Preset profiles live in `assets/profiles/`.

Example list command:

```bash
python3 scripts/select_brand_profile.py --list
```

### Option B: Extract from web / PPTX / DOCX

Run the extractor with one or many sources:

```bash
python3 scripts/build_brand_profile.py \
  --brand-name "Stripe" \
  --web-url "https://stripe.com" \
  --pptx "/path/to/template.pptx" \
  --docx "/path/to/template.docx" \
  --out /tmp/stripe.profile.json
```

Notes:
- `--web-url` extracts logo candidates, color hexes, font-family declarations, and potential guideline/policy links.
- `--pptx` and `--docx` extract theme colors/fonts and image candidates from the Office package.
- Multiple sources are merged into one normalized profile.

Schema reference: `references/profile-schema.md`.

## Select the Brand

After gathering presets and/or extracted profiles, select a single brand:

```bash
python3 scripts/select_brand_profile.py \
  --profile /tmp/stripe.profile.json \
  --brand stripe \
  --out /tmp/selected-brand.json
```

If matching is uncertain, run:

```bash
python3 scripts/select_brand_profile.py --list --profile /tmp/stripe.profile.json
```

Never apply multiple brands in one artifact unless the user explicitly asks for co-branding.

## Apply the Selected Profile

Use `/tmp/selected-brand.json` (or equivalent) as source of truth.

Application rules:
- Use the top 2-4 colors in `colors` as primary/secondary/accent tokens.
- Use the top heading/body fonts from `fonts` and include safe fallbacks.
- Use the first valid logo candidate from `logos` unless the user overrides it.
- Preserve hierarchy and contrast for readability and accessibility.
- If `guidelines` or `policies` links are present, check them before finalizing external-facing output.

If user asks for Anthropic styling specifically, select preset `anthropic` from `assets/profiles/anthropic.json`.
