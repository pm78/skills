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

## Guardrails

- Produce inspired-by styling only, never pixel-perfect cloning.
- Preserve readability and contrast.
- Keep article text left-aligned and source lists non-justified.
- Prefer reversible CSS changes that can be removed from WordPress Additional CSS.
