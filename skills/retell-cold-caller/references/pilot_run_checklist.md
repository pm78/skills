# Pilot run checklist (Retell + France B2B)

## 1) Prerequisites

- `RETELL_API_KEY` set in environment or `.env`.
- BYO telephony configured and caller number active for outbound to `+33`.
- Suppression list available (even if empty at pilot start).

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

## 4) Internal pilot calls first

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
  --report-path-template /get-phone-call/{call_id} \
  --execute
```

## 5) Small external pilot (5-10 leads)

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
  --report-path-template /get-phone-call/{call_id} \
  --limit 10 \
  --sleep-seconds 20 \
  --out-jsonl /tmp/retell_payloads.jsonl \
  --out-blocked-jsonl /tmp/retell_blocked.jsonl \
  --logs-dir /tmp/retell_logs \
  --execute \
  --verbose
```

## 6) QA scorecard per call

- Opener clarity (first 10 seconds)
- Correct identity and purpose disclosure
- Objection handling quality
- Opt-out handling and suppression update
- Next-step capture quality (booked, callback, no-interest)

## 7) Iterate prompt and rerun

- Tighten opener if too long.
- Reduce question count if call feels robotic.
- Improve meeting ask wording if conversion is low.
- Review blocked leads (`out-blocked-jsonl`) and adjust list hygiene/time windows.
- Review per-call logs in `--logs-dir` for outcome quality and timeout patterns.
