---
name: linkedin-search
description: Search LinkedIn jobs and scrape LinkedIn profiles, companies, and job postings via the LinkedIn MCP Server (justjoehere/linkedin-mcp-server). Use when you need LinkedIn data for recruiting, prospect research, company intel, or job market scans, especially when you have LinkedIn URLs or a job search query.
---

# LinkedIn Search (via MCP)

## Quick start

- If LinkedIn MCP tools are available, use them to fetch the smallest set of pages needed.
- If LinkedIn MCP tools are not available, follow `references/setup.md` to install and configure the server.
- If MCP scraping tools are unavailable in-session but `chrome-devtools` MCP is available, use the manual browser fallback workflow below.

## Available MCP tools

These tool names come from the LinkedIn MCP server (`FastMCP("linkedin_scraper")`):

- `get_person_profile(linkedin_url: str) -> dict`
- `get_company_profile(linkedin_url: str, get_employees: bool = False) -> dict`
- `search_jobs(search_term: str) -> list[dict]`
- `get_job_details(job_url: str) -> dict`
- `get_recommended_jobs() -> list[dict]`
- `close_session() -> dict`

## Operating rules

- Do not ask for or repeat passwords. Credentials must be provided to the server via env vars or a local credential file.
- To avoid repeated 2FA, use a persistent Chrome profile directory (`LINKEDIN_PROFILE_DIR` or `--profile-dir`). Use separate directories per MCP client (e.g., Codex vs Claude Code) to avoid Chrome profile locking.
- If WSL ChromeDriver cannot start, use MCP fallback via `LINKEDIN_FALLBACK_COMMAND` (typically a `powershell.exe` command) so the skill can still return company employees.
- Prefer URL-based scraping for people/companies; this server does not provide keyword search for people/companies.
- Use `get_employees=True` only with explicit user confirmation due to time and rate-limit risk.
- Never send messages without explicit user approval.
- Never accept/send connection requests without explicit user approval.
- Avoid rapid repetitive actions; keep activity human-paced.
- Recommended throttle: about 30 actions per hour maximum.
- Call `close_session()` only when finished with LinkedIn for this conversation (or after errors) to keep the session reusable.

## Workflows

### Job search

1. Ask for constraints: role, location, remote/hybrid, keywords, seniority, must-haves.
2. Call `search_jobs(search_term)` with a concise query string.
3. Present a short ranked list with title/company/location and the job URL.
4. If the user selects jobs, call `get_job_details(job_url)` per selected URL and summarize description, requirements, and key signals.

### Recommended jobs

1. Confirm the user is comfortable using their logged-in LinkedIn recommendations.
2. Call `get_recommended_jobs()`.
3. Present a short ranked list and offer to fetch details for selected URLs.

### Person profile (URL required)

1. Ask for the exact `https://www.linkedin.com/in/...` URL.
2. Call `get_person_profile(linkedin_url)`.
3. Summarize: current role, top relevant past roles, education highlights, and notable keywords from the about/experience fields.

### Company profile (URL required)

1. Ask for the exact `https://www.linkedin.com/company/...` URL.
2. Call `get_company_profile(linkedin_url, get_employees=False)`.
3. Summarize: overview, industry, size/headcount, specialties, HQ, website.
4. If the user explicitly wants employees, re-run with `get_employees=True` and warn it can be slow.

## Manual browser fallback (chrome-devtools MCP)

Use this only when LinkedIn MCP scraping tools are not available but browser automation tools are.

Canonical tool names on the server:
- `list_pages`
- `new_page`
- `navigate_page`
- `take_snapshot`
- `select_page`
- `click`
- `fill`
- `evaluate_script`

Notes:
- Codex may render these internally as `mcp__chrome_devtools__<tool>`.
- Do not use OpenClaw-style `browser action=...` commands in Codex sessions.

Fallback workflow:
1. Open `https://www.linkedin.com/feed/` and authenticate manually if redirected.
2. Capture state with `take_snapshot` and continue using discovered element UIDs.
3. For people search, open: `https://www.linkedin.com/search/results/people/?keywords=QUERY`.
4. For profile review, open: `https://www.linkedin.com/in/USERNAME/`.
5. Optionally extract visible profile cards with `evaluate_script`:

```js
() => [...document.querySelectorAll('a[href*="/in/"]')]
  .slice(0, 25)
  .map(a => ({ name: a.textContent?.trim() || '', url: a.href }))
```

## Troubleshooting

- If tools return auth or empty results, run the server once interactively (visible Chrome) to complete login; see `references/setup.md`.
- If ChromeDriver issues occur, set `CHROMEDRIVER` to a matching chromedriver binary and retry.
- If ChromeDriver fails in WSL with status `127`, look for `error_code=CHROMEDRIVER_BOOT_FAILED` and `fallback_command` in the tool response, then run that command via the shell to fetch employees.
- Optionally, set `LINKEDIN_FALLBACK_EXEC=1` if you want the MCP server itself to execute the fallback (not always supported in WSL).
- If you see repeated login/2FA prompts, configure `LINKEDIN_PROFILE_DIR` so cookies and device trust persist across runs.
- If `Target closed` appears in browser fallback mode, reconnect browser target and retry `list_pages` or `new_page`.
- If logged out or redirected to sign-in in browser fallback mode, authenticate manually and resume.
- If CAPTCHA/rate limits appear, complete CAPTCHA manually and reduce action frequency for 24 hours.

## Compliance note

LinkedIn scraping may violate LinkedIn's Terms of Service depending on use. Use responsibly and only with an account you control.
