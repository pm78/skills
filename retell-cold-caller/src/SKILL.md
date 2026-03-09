---
name: retell-cold-caller
description: "Generate compliant B2B outbound talk tracks and Retell agent/call payloads for appointment-setting, especially for French (+33) dialing via BYO telephony (Twilio/Telnyx/SIP). Use when replacing or avoiding Vapi for international outbound calling, and when you need dry-run-safe scripts to create agents, place pilot calls, and run small batches."
---

# Retell Cold Caller

## Overview

Design and run B2B outbound appointment-setting campaigns using Retell with BYO telephony. Produce French-ready talk tracks, generate Retell payloads, and (optionally) execute API calls for pilot and batch dialing.

This skill is operational guidance, not legal advice.

## Environment setup

1. Get your API key from the [Retell dashboard](https://www.retellai.com/) (Settings > API Keys)
2. Create a `.env` file **in the skill root directory** (`retell-cold-caller/.env`):

```
RETELL_API_KEY=key_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The script loads `.env` from: skill root dir, then current working dir, then `--env-file` path. Shell environment takes priority.

## Quick Start for France

Retell only sells US/Canada numbers. For France-to-France calling, follow one of these paths:

### Path A: Test your agent immediately (no phone number needed)

```bash
python scripts/retell_campaign.py web-call --agent-id agent_xxx --execute
```

This creates a browser-based call — no SIP trunk or Twilio account required. Test in the Retell dashboard under "Test Agent".

### Path B: Production France-to-France phone calls

1. Buy a +33 number on Twilio and create an Elastic SIP Trunk with auth credentials
2. Import it: `scripts/retell_campaign.py import-number --phone-number "+33..." --termination-uri "yourtrunk.pstn.twilio.com" --sip-username "..." --sip-password "..." --execute`
3. Verify: `scripts/retell_campaign.py list-numbers --execute`
4. Call: `scripts/retell_campaign.py call-one --agent-id agent_xxx --from-number "+33..." --to-number "+33..." --execute`

See `references/setup_france_telephony.md` for the full step-by-step guide.

## Available subcommands

| Subcommand | Purpose |
|---|---|
| `generate` | Create agent payload + talk track + call template + curl templates from campaign spec |
| `create-agent` | Create a voice agent in Retell |
| `list-agents` | List existing Retell agents |
| `web-call` | Create a browser-based web call (no phone number needed — ideal for testing) |
| `import-number` | Import a phone number into Retell via SIP trunk (BYO telephony) |
| `list-numbers` | List phone numbers registered in Retell |
| `call-one` | Place a single outbound phone call |
| `start-calls` | Batch outbound calls from a leads CSV |

All subcommands default to **dry-run** (print curl, no API call). Add `--execute` for live actions.

## Workflow

### Step 0: Gather campaign inputs

Collect:

- Offer and target persona/ICP
- 2-3 pain points and expected outcomes
- 2-3 proof points
- Meeting goal (usually 15-25 min)
- Qualification questions and disqualifiers
- Geographies/languages/time windows
- DNC and recording policy

If details are missing, proceed with explicit assumptions.

### Step 1: Produce talk track and objections

Use short, permission-based openers and one-question-at-a-time discovery.

For French campaigns, keep first turns simple and natural (see `references/examples_b2b_fr.md`).

### Step 2: Generate Retell assets

Run `scripts/retell_campaign.py generate` with `assets/campaign_spec.example.json` to produce:

- `agent.create.json`
- `call.create.example.json`
- `talk_track.md`
- curl templates

### Step 3: Create agent and place pilot calls

- Create agent: `scripts/retell_campaign.py create-agent ...`
- List agents: `scripts/retell_campaign.py list-agents ...`
- Place one call: `scripts/retell_campaign.py call-one ...`

Default behavior is dry-run only. Use `--execute` for live API actions.

### Step 4: Batch dialing with suppression controls

Use `scripts/retell_campaign.py start-calls` with:

- leads CSV (`assets/leads_template.csv` format)
- optional DNC file
- conservative batch size and pacing
- optional FR guardrails (`--fr-policy`) for:
  - weekday/time-window gate
  - attempt counter (rolling 30 days)
  - refusal cooldown
- optional call lifecycle tracking (`--wait-report`) with watchdog timeouts

### Step 4b: Runtime controls (new)

The script now supports production controls commonly needed in FR outbound:

- Result schema + log files per call (`--logs-dir`)
- Dynamic vs static dialing mode (`--mode dynamic|static`)
- Optional report wait with watchdogs:
  - `--wait-report`
  - `--poll-interval-seconds`
  - `--inactivity-timeout-seconds`
  - `--post-end-timeout-seconds`
  - `--call-timeout-seconds`
- Configurable report lookup path(s):
  - `--report-path-template`
  - `--report-path-fallback` (repeatable)
- FR policy state persistence:
  - `--fr-policy-state` (tracks attempts/refusals)

### Step 5: QA before scale

Verify in pilot calls:

- opener clarity in first 10 seconds
- opt-out handling and suppression updates
- voicemail behavior
- call summaries and structured outcomes

## Compliance guardrails

- Always enforce DNC/suppression before every dial.
- Be truthful about identity, purpose, and AI usage.
- Avoid deceptive claims and fabricated proof.
- For France-specific constraints and 2026 changes, check `references/compliance_checklist_fr.md`.

## Resource map

- `scripts/retell_campaign.py`: Generate payloads, print curl, optionally execute Retell API calls.
- `references/setup_france_telephony.md`: **Start here** — step-by-step guide to set up France-to-France calling.
- `references/compliance_checklist_fr.md`: France/B2B compliance checklist with official links.
- `references/examples_b2b_fr.md`: French discovery-first talk-track examples.
- `references/retell_api_notes.md`: Minimal Retell endpoints/payload notes.
- `references/twilio_fr_numbering_notes.md`: Twilio + France practical notes.
- `references/pilot_run_checklist.md`: Step-by-step pilot checklist (internal first, then limited external batch).
- `assets/campaign_spec.example.json`: Starter campaign spec.
- `assets/leads_template.csv`: Leads template for batch calls.
- `tests/test_retell_campaign.py`: Regression tests for FR gates, payload modes, DNC filtering, and report watchdogs.
