# WordPress Application

## Output Files

- `tokens.css`: CSS variables (`:root` design tokens)
- `wordpress-overrides.css`: Site-level and article-level style overrides
- `additional-css-combined.css`: Paste-ready bundle for WordPress `Additional CSS`
- `summary.json`: Mode, palette, fonts, and output metadata

## Apply in WordPress

1. Open `Appearance -> Customize -> Additional CSS`
2. Paste `additional-css-combined.css`
3. Publish
4. Hard-refresh front-end pages and validate desktop + mobile

## Quick QA Checklist

- Headings/body typography render as expected
- Links are readable in normal + hover state
- Content remains legible in article body and sidebar widgets
- Source lists are left-aligned and clickable links remain visible
- Buttons and forms are readable and consistent
