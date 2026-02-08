---
name: linkedin
description: LinkedIn workflows using the chrome-devtools MCP server for search, profile review, and outreach drafting with explicit send confirmation.
homepage: https://linkedin.com
metadata: {"clawdbot":{"emoji":"💼"}}
---

# LinkedIn

Use LinkedIn with the `chrome-devtools` MCP server in Codex.

Canonical tool names on the server:
- `list_pages`
- `new_page`
- `navigate_page`
- `take_snapshot`
- `select_page`
- `click`
- `fill`
- `evaluate_script`

Note: Codex may render these internally as `mcp__chrome_devtools__<tool>`.

Do not use OpenClaw-style `browser action=...` commands in Codex sessions.

## Session Setup

1. Open LinkedIn feed: `https://www.linkedin.com/feed/`
2. If redirected to login, authenticate manually.
3. Take a snapshot and continue from discovered element UIDs.

## Common Operations

### Check Connection Status

- Open feed (`new_page`): `https://www.linkedin.com/feed/`
- Capture state (`take_snapshot`)

### View Notifications/Messages

- Navigate (`navigate_page`) to: `https://www.linkedin.com/messaging/`
- Capture state (`take_snapshot`)

### Search People

- Navigate (`navigate_page`) to: `https://www.linkedin.com/search/results/people/?keywords=QUERY`
- Capture state (`take_snapshot`)

### Find HR Directors In Boston

- Navigate (`navigate_page`) to:
  `https://www.linkedin.com/search/results/people/?keywords=%28%22HR%20Director%22%20OR%20%22Director%20of%20HR%22%20OR%20%22Director%20Human%20Resources%22%29%20Boston`
- Capture state (`take_snapshot`)
- Apply filters in UI:
  - `Locations` -> `Boston, Massachusetts, United States`
  - Optional: `Current company`, `Industry`, `Connections`
- Capture another snapshot after filters.

### View Profile

- Navigate (`navigate_page`) to: `https://www.linkedin.com/in/USERNAME/`
- Capture state (`take_snapshot`)

### Extract Visible Result Cards (Optional)

Use `evaluate_script` with:

```js
() => [...document.querySelectorAll('a[href*="/in/"]')]
  .slice(0, 25)
  .map(a => ({ name: a.textContent?.trim() || '', url: a.href }))
```

## Safety Rules

- Never send messages without explicit user approval.
- Never accept/send connection requests without confirmation.
- Avoid rapid repetitive actions; keep activity human-paced.
- Recommended throttle: about 30 actions per hour maximum.

## Troubleshooting

- `Target closed`: chrome-devtools MCP browser target/session is unavailable. Restart Codex or reconnect browser target, then retry `list_pages` or `new_page`.
- Logged out or redirected to sign-in: authenticate manually and continue.
- CAPTCHA/rate limits: complete CAPTCHA manually, then pause and reduce action frequency for 24 hours.
