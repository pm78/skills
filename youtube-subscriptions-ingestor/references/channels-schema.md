# Channels File Schema

Provide a JSON array. Use one object per channel.

```json
[
  {
    "channel_id": "UCxxxx",
    "label": "Example Creator",
    "topic": "AI"
  }
]
```

Fields:

- `channel_id` (required): YouTube channel ID (`UC...`)
- `label` (optional): Friendly label for display
- `topic` (optional): Tag to assign in Notion (`AI`, `Health`, `Payments`, etc.)

You can also use a plain string list when only IDs are needed:

```json
["UCxxxx", "UCyyyy"]
```
