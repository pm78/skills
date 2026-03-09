# Brand Profile Schema

Use this normalized JSON schema for selected brand profiles.

```json
{
  "schema_version": "1.0",
  "brand_id": "hyphenated-id",
  "brand_name": "Display Name",
  "captured_at": "ISO-8601 timestamp",
  "aliases": ["optional selector aliases"],
  "sources": [{ "type": "web|pptx|docx|preset", "value": "source reference" }],
  "logos": [{ "url": "https://..." }, { "path": "ppt/media/image1.png" }],
  "colors": [{ "hex": "#RRGGBB", "count": 12 }],
  "fonts": [{ "name": "Font Name", "count": 8 }],
  "css_style": {
    "source_site": "https://...",
    "theme": "theme-or-system-name",
    "tokens": { "primary_accent": "#RRGGBB", "background": "#RRGGBB" },
    "typography": { "heading_font": "Font", "body_font": "Font" },
    "notable_rules": ["short css/style guidance"]
  },
  "illustration_style": {
    "editorial_direction": "high-level visual direction",
    "rendering": "rendering/medium guidance",
    "composition": "layout guidance",
    "mood": "tone",
    "color_palette": ["#RRGGBB"],
    "motifs": ["preferred elements"],
    "avoid": ["styles to avoid"]
  },
  "guidelines": [{ "title": "Brand Guidelines", "url": "https://..." }],
  "policies": [{ "title": "Trademark Policy", "url": "https://..." }],
  "style_notes": ["free-form guidance"]
}
```

Required fields for application are `brand_id`, `brand_name`, `colors`, and `fonts`.
Use `guidelines` and `policies` links for compliance checks before external publishing.
For image generation workflows, prefer `illustration_style` as the prompt style source and use `css_style.tokens` for palette alignment.
