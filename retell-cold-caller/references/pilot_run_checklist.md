# Pilot run checklist (Retell + France B2B)

## 1) Prerequisites

- `RETELL_API_KEY` set in `retell-cold-caller/.env` (not the parent directory).
- Suppression list available (even if empty at pilot start).
- For phone calls: BYO telephony configured and French number imported (see step 1b).
- For web-call testing: no telephony setup needed.

### 1b) Telephony setup (for phone calls only)

If you need to make real phone calls (not just web-call testing), set up BYO telephony first:

```bash
# Check if you already have numbers imported
python3 scripts/retell_campaign.py list-numbers --execute

# If not, import a French number from Twilio/Telnyx
python3 scripts/retell_campaign.py import-number \
  --phone-number "+33140000000" \
  --termination-uri "yourtrunk.pstn.twilio.com" \
  --sip-username "your_username" \
  --sip-password "your_password" \
  --nickname "FR-outbound" \
  --execute
```

See `references/setup_france_telephony.md` for the full Twilio SIP trunk setup.

## 2) Generate assets

```bash
python3 scripts/retell_campaign.py generate \
  --spec assets/campaign_spec.example.json \
  --out /tmp/retell-pilot
```

Review:

- `/tmp/retell-pilot/agent.create.json`
- `/tmp/retell-pilot/talk_track.md`
- `/tmp/retell-pilot/call.create.example.json`

## 3) Create agent

```bash
python3 scripts/retell_campaign.py create-agent \
  --agent-json /tmp/retell-pilot/agent.create.json \
  --execute
```

Capture returned `agent_id`.

Or list existing agents:

```bash
python3 scripts/retell_campaign.py list-agents --execute
```

## 4) Web call test (recommended first step)

Before using real phone numbers, validate your agent with a browser-based web call:

```bash
python3 scripts/retell_campaign.py web-call \
  --agent-id <agent_id> \
  --execute
```

This returns an `access_token`. Test the agent in the Retell dashboard under "Test Agent", or use the Retell Web SDK in a frontend.

Check:
- Does the opener sound natural?
- Does the agent handle objections correctly?
- Does opt-out handling work?

## 5) Internal pilot phone calls

Use internal numbers before prospect calls.

```bash
python3 scripts/retell_campaign.py call-one \
  --agent-id <agent_id> \
  --from-number +33XXXXXXXXX \
  --to-number +33YYYYYYYYY \
  --mode dynamic \
  --meta campaign=fr-b2b-internal \
  --fr-policy \
  --wait-report \
  --execute
```

## 6) Small external pilot (5-10 leads)

```bash
python3 scripts/retell_campaign.py start-calls \
  --agent-id <agent_id> \
  --from-number +33XXXXXXXXX \
  --leads assets/leads_template.csv \
  --dnc /path/to/dnc.txt \
  --mode dynamic \
  --campaign-tag fr-b2b-pilot \
  --fr-policy \
  --fr-policy-state /path/to/fr_policy_state.json \
  --wait-report \
  --limit 10 \
  --sleep-seconds 20 \
  --out-jsonl /tmp/retell_payloads.jsonl \
  --out-blocked-jsonl /tmp/retell_blocked.jsonl \
  --logs-dir /tmp/retell_logs \
  --execute \
  --verbose
```

## 7) QA scorecard per call

- Opener clarity (first 10 seconds)
- Correct identity and purpose disclosure
- Objection handling quality
- Opt-out handling and suppression update
- Next-step capture quality (booked, callback, no-interest)

## 8) Iterate prompt and rerun

- Tighten opener if too long.
- Reduce question count if call feels robotic.
- Improve meeting ask wording if conversion is low.
- Review blocked leads (`out-blocked-jsonl`) and adjust list hygiene/time windows.
- Review per-call logs in `--logs-dir` for outcome quality and timeout patterns.
