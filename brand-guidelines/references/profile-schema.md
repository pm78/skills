# Brand Profile Schema

Use this normalized JSON schema for selected brand profiles.

```json
{
  "schema_version": "1.0",
  "brand_id": "hyphenated-id",
  "brand_name": "Display Name",
  "captured_at": "ISO-8601 timestamp",
  "sources": [{ "type": "web|pptx|docx|preset", "value": "source reference" }],
  "logos": [{ "url": "https://..." }, { "path": "ppt/media/image1.png" }],
  "colors": [{ "hex": "#RRGGBB", "count": 12 }],
  "fonts": [{ "name": "Font Name", "count": 8 }],
  "guidelines": [{ "title": "Brand Guidelines", "url": "https://..." }],
  "policies": [{ "title": "Trademark Policy", "url": "https://..." }],
  "style_notes": ["free-form guidance"]
}
```

Required fields for application are `brand_id`, `brand_name`, `colors`, and `fonts`.
Use `guidelines` and `policies` links for compliance checks before external publishing.
