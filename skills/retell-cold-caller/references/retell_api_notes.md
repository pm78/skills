# Retell API notes (minimal outbound set)

Base URL:

- `https://api.retellai.com`

Auth header:

- `Authorization: Bearer $RETELL_API_KEY`

## Core endpoints used by this skill

- `POST /create-agent`
- `GET /list-agents`
- `POST /create-phone-call`
- Optional report polling endpoint(s), configured by CLI:
  - `--report-path-template` (default: `/get-phone-call/{call_id}`)
  - `--report-path-fallback` for environment-specific variants

## Agent payload shape (typical)

```json
{
  "agent_name": "FR B2B Appointment Setter",
  "response_engine": {
    "type": "retell-llm",
    "llm_id": "llm_xxx"
  },
  "voice_id": "11labs-Adrian",
  "language": "fr-FR",
  "begin_message": "Bonjour, ici Camille de ACME. Est-ce que je vous dérange ?",
  "webhook_url": "https://your-app.example/webhooks/retell",
  "enable_voicemail_detection": true,
  "voicemail_message": "Bonjour, ici Camille de ACME...",
  "analysis_summary_prompt": "Summarize call outcome in two sentences"
}
```

Useful optional fields frequently seen in Retell docs/examples:

- `max_call_duration_ms`
- `ring_duration_ms`
- `stt_mode`
- `custom_stt_config`
- `post_call_analysis_data`
- `analysis_successful_prompt`
- `analysis_summary_prompt`

## Call payload shape (typical)

```json
{
  "from_number": "+331XXXXXXXX",
  "to_number": "+33YYYYYYYYY",
  "override_agent_id": "agent_xxx",
  "retell_llm_dynamic_variables": {
    "first_name": "Ariane",
    "company": "Example SAS"
  },
  "metadata": {
    "campaign": "fr-b2b-q1"
  }
}
```

## BYO telephony note

For international outbound reliability (including France), prefer custom telephony with SIP trunking and imported/managed numbers rather than relying on default provisioned numbers.

## Runtime/reporting notes

- `retell_campaign.py` can optionally wait for post-call report data (`--wait-report`) using polling.
- Watchdog controls:
  - `--inactivity-timeout-seconds`
  - `--post-end-timeout-seconds`
  - `--call-timeout-seconds`
- Every executed call is logged as structured JSON (`--logs-dir`) with status, timing, policy, and analysis fields.

## Documentation references

- Create agent: https://docs.retellai.com/api-references/create-agent
- List agents: https://docs.retellai.com/api-references/list-agents
- Create phone call: https://docs.retellai.com/api-references/create-phone-call
- Custom telephony: https://docs.retellai.com/deploy/custom-telephony
- Language/voice: https://docs.retellai.com/build/set-language-and-voice
