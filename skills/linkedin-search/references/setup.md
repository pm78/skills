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

## Non-interactive runs (recommended for MCP clients)

If you have the credential file, you can omit `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` entirely.

If you prefer env vars, set:

- `LINKEDIN_EMAIL`
- `LINKEDIN_PASSWORD`

Optional:
- `CHROMEDRIVER`
- `LINKEDIN_PROFILE_DIR` (Chrome user-data dir to persist cookies/device trust; recommended)

## MCP client configuration (stdio)

This server runs as an MCP stdio process (the client spawns it). Example pattern (adapt for your client):

- Command: `uv`
- Args: `--directory /path/to/linkedin-mcp-server run main.py --no-setup`
- Env: `PYTHONPATH=src` and optionally `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD`, `CHROMEDRIVER`
- Env (recommended): also set `LINKEDIN_PROFILE_DIR` so the browser session persists across runs. Use distinct values per MCP client (Codex vs Claude Code) to avoid profile locking.

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
        "LINKEDIN_PROFILE_DIR": "/path/to/linkedin-chrome-profile"
      }
    }
  }
}
```

## Troubleshooting

- If login fails, retry with visible Chrome (`--no-headless`) to see what’s happening.
- If ChromeDriver fails, download a matching version and set `CHROMEDRIVER` to its full path.
