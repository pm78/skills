# LinkedIn MCP Server setup (justjoehere/linkedin-mcp-server)

Source repo:
- https://github.com/justjoehere/linkedin-mcp-server

## Important: PYTHONPATH

This repo is laid out as a `src/` package. If you run `main.py` directly, you must ensure Python can import `linkedin_mcp_server`.

Use one of:

- Set `PYTHONPATH=src` (simplest)
- Install the package in editable mode (more "packaged" approach)

This guide uses `PYTHONPATH=src`.

## Prerequisites

- Python 3.12+ (per `pyproject.toml`)
- Google Chrome installed
- ChromeDriver matching your Chrome version (set `CHROMEDRIVER` if auto-detect fails)
- A LinkedIn account

## Install (uv recommended)

```bash
git clone https://github.com/justjoehere/linkedin-mcp-server
cd linkedin-mcp-server

# Install uv (if needed): https://astral.sh/uv/
uv venv
uv sync
```

## First run (interactive login)

Run once with a visible browser so you can complete any login checks and (optionally) store credentials locally:

macOS/Linux/WSL:

```bash
PYTHONPATH=src uv run main.py --no-lazy-init --no-headless
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
uv run main.py --no-lazy-init --no-headless
```

The server can store credentials at `~/.linkedin_mcp_credentials.json`.
To persist your LinkedIn session across restarts (recommended to reduce repeated 2FA), also set `LINKEDIN_PROFILE_DIR` (see below).
Security note: prefer `LINKEDIN_PROFILE_DIR` + interactive login once, so you don't need to store a plaintext password on disk. The MCP server supports `LINKEDIN_DISABLE_CREDENTIALS_FILE=1` and `LINKEDIN_STORE_CREDENTIALS_FILE=0`.

## Non-interactive runs (recommended for MCP clients)

If you have the credential file, you can omit `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` entirely.

If you prefer env vars, set:

- `LINKEDIN_EMAIL`
- `LINKEDIN_PASSWORD`

Optional:
- `CHROMEDRIVER`
- `LINKEDIN_PROFILE_DIR` (Chrome user-data dir to persist cookies/device trust; recommended)
- `LINKEDIN_FALLBACK_COMMAND` (optional but recommended on WSL: PowerShell/cmd command template with `{company_url}` placeholder)
- `LINKEDIN_FALLBACK_TIMEOUT_SEC` (optional timeout for fallback command, default `600`)
- `LINKEDIN_FALLBACK_EXEC` (optional; set to `1` only if you want the MCP server to execute the fallback itself)
- `LINKEDIN_FALLBACK_PROFILE_DIR` (optional Windows Chrome profile dir for fallback; use with `{profile_dir}` placeholder)

## MCP client configuration (stdio)

This server runs as an MCP stdio process (the client spawns it). Example pattern (adapt for your client):

- Command: `uv`
- Args: `--directory /path/to/linkedin-mcp-server run main.py --no-setup`
- Env: `PYTHONPATH=src` and optionally `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD`, `CHROMEDRIVER`
- Env (recommended): also set `LINKEDIN_PROFILE_DIR` so the browser session persists across runs. Use distinct values per MCP client (Codex vs Claude Code) to avoid profile locking.
- Env (WSL fallback): set `LINKEDIN_FALLBACK_COMMAND` to a Windows command that can scrape employees and prints JSON on stdout.

Claude Desktop example (pattern; adapt paths):

```json
{
  "mcpServers": {
    "linkedin-scraper": {
      "command": "/path/to/uv",
      "args": ["--directory", "/path/to/linkedin-mcp-server", "run", "main.py", "--no-setup"],
      "env": {
        "PYTHONPATH": "src",
        "LINKEDIN_EMAIL": "your.email@example.com",
        "LINKEDIN_PASSWORD": "your_password",
        "LINKEDIN_PROFILE_DIR": "/path/to/linkedin-chrome-profile",
        "LINKEDIN_FALLBACK_COMMAND": "cmd.exe /c \"powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\YOUR_USER\\AutoBidding\\tools\\linkedin\\company_profile_fallback.ps1 -CompanyUrl {company_url}\""
      }
    }
  }
}
```

Codex config example (`~/.codex/config.toml`):

```toml
[mcp_servers.linkedin-scraper.env]
LINKEDIN_PROFILE_DIR = "/home/USER/.linkedin_mcp_chrome_profile_codex"
LINKEDIN_FALLBACK_PROFILE_DIR = "C:\\Users\\USER\\.linkedin_selenium_profile_codex"
LINKEDIN_FALLBACK_COMMAND = "cmd.exe /c \"powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\USER\\AutoBidding\\tools\\linkedin\\company_profile_fallback.ps1 -CompanyUrl {company_url} -ProfileDir {profile_dir}\""
LINKEDIN_FALLBACK_EXEC = "1"
```

Claude Code config example (use a separate profile dir to avoid lock contention):

```json
{
  "mcpServers": {
    "linkedin-scraper": {
      "env": {
        "LINKEDIN_PROFILE_DIR": "/home/USER/.linkedin_mcp_chrome_profile_claude",
        "LINKEDIN_FALLBACK_COMMAND": "cmd.exe /c \"powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\USER\\AutoBidding\\tools\\linkedin\\company_profile_fallback.ps1 -CompanyUrl {company_url}\""
      }
    }
  }
}
```

## Troubleshooting

- If login fails, retry with visible Chrome (`--no-headless`) to see what’s happening.
- If ChromeDriver fails, download a matching version and set `CHROMEDRIVER` to its full path.
