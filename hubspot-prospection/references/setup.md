# HubSpot MCP Setup Guide

## MCP Server: @shinzolabs/hubspot-mcp

This skill uses the community MCP server `@shinzolabs/hubspot-mcp` which provides 127 tools for full CRUD operations on HubSpot CRM objects.

> **Why not the official HubSpot MCP?** The official `@hubspot/mcp` is read-only. We need write access to create contacts, companies, deals, and associations.

## Installation

### 1. Create a HubSpot Private App

1. Go to **Settings > Integrations > Private Apps** in your HubSpot portal
2. Click **Create a private app**
3. Name it (e.g., "Claude Code Prospection")
4. Under **Scopes**, enable the following:

#### Required Scopes

| Scope | Purpose |
|-------|---------|
| `crm.objects.contacts.read` | Read contacts |
| `crm.objects.contacts.write` | Create/update contacts |
| `crm.objects.companies.read` | Read companies |
| `crm.objects.companies.write` | Create/update companies |
| `crm.objects.deals.read` | Read deals |
| `crm.objects.deals.write` | Create/update deals |
| `crm.schemas.contacts.read` | Read contact properties |
| `crm.schemas.companies.read` | Read company properties |
| `crm.schemas.deals.read` | Read deal properties |
| `crm.objects.owners.read` | Read owners for assignment |
| `sales-email-read` | Read email engagement |
| `automation` | Sequences API access |

5. Click **Create app** and copy the access token

### 2. Configure MCP in Claude Code

Add to your Claude Code MCP settings (`.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "hubspot": {
      "command": "npx",
      "args": ["-y", "@shinzolabs/hubspot-mcp"],
      "env": {
        "HUBSPOT_ACCESS_TOKEN": "pat-na1-XXXXX"
      }
    }
  }
}
```

### 3. Verify Installation

After restarting Claude Code, verify the MCP is working:

1. Ask Claude to list HubSpot contacts: the `hubspot_list_contacts` tool should be available
2. Try a simple read operation to confirm the token is valid

### 4. Python Dependencies (for scripts)

The Python scripts require:

```bash
pip install requests openpyxl
```

- `requests` — HTTP calls to HubSpot Sequences API v4
- `openpyxl` — Excel file reading for contact import

## Environment Variable Alternative

Instead of hardcoding the token in MCP config, you can use an environment variable:

```bash
export HUBSPOT_ACCESS_TOKEN="<YOUR_HUBSPOT_PRIVATE_APP_TOKEN>"
```

Then reference it in MCP config:
```json
{
  "env": {
    "HUBSPOT_ACCESS_TOKEN": "${HUBSPOT_ACCESS_TOKEN}"
  }
}
```

For the Python scripts, pass the token via `--token` argument or set the environment variable.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "401 Unauthorized" | Token expired or incorrect. Regenerate in HubSpot private app settings. |
| "403 Forbidden" on contacts | Missing `crm.objects.contacts.write` scope. Edit private app scopes. |
| "403 Forbidden" on sequences | Missing `automation` scope. |
| MCP tools not appearing | Restart Claude Code. Check `npx @shinzolabs/hubspot-mcp` runs without error. |
| "ENOENT npx" | Node.js not installed or not in PATH. |
