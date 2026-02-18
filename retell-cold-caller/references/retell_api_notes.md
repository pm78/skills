# Retell API notes (minimal outbound set)

Base URL:

- `https://api.retellai.com`

Auth header:

- `Authorization: Bearer $RETELL_API_KEY`

## Environment setup

Place your API key in a `.env` file **inside the skill root directory** (`retell-cold-caller/.env`):

```
RETELL_API_KEY=key_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The script loads `.env` from (in order):
1. Skill directory (parent of `scripts/`)
2. Current working directory
3. Explicit `--env-file` path

Keys already set in the shell environment take priority over `.env` values.

## Core endpoints used by this skill

| Subcommand | Method | Endpoint |
|---|---|---|
| `create-agent` | POST | `/create-agent` |
| `list-agents` | GET | `/list-agents` |
| `web-call` | POST | `/v2/create-web-call` |
| `import-number` | POST | `/import-phone-number` |
| `list-numbers` | GET | `/list-phone-numbers` |
| `call-one` / `start-calls` | POST | `/v2/create-phone-call` |
| report polling | GET | `/get-phone-call/{call_id}` (configurable) |

### Endpoint gotchas (verified live)

- `GET /list-agents` does **not** accept `offset` query parameter — just call it without pagination.
- `POST /create-phone-call` must use the **v2** path (`/v2/create-phone-call`). The legacy path returns errors.
- `from_number` in create-phone-call is **required** and must be a number already purchased from Retell **or imported** via `import-phone-number`.
- Retell only sells **US/Canada** numbers. For France (+33), you must import via SIP trunk (see `references/setup_france_telephony.md`).

## Web call payload (no phone number needed)

```json
{
  "agent_id": "agent_xxx"
}
```

Returns `access_token` for browser-based call via Retell Web SDK.
Use this for testing agents before setting up telephony.

## Import number payload (BYO telephony)

```json
{
  "phone_number": "+33140000000",
  "termination_uri": "yourtrunk.pstn.twilio.com",
  "sip_trunk_auth_username": "your_username",
  "sip_trunk_auth_password": "your_password",
  "outbound_agent_id": "agent_xxx",
  "nickname": "FR-outbound",
  "transport": "TCP"
}
```

## Voice selection for France (important)

For French metropolitan (France) accent, **use Cartesia voices, not MiniMax or ElevenLabs**.

### Verified French voices (tested, confirmed France accent)

| voice_id | Name | Provider | Gender | Accent |
|---|---|---|---|---|
| `cartesia-Emma` | Emma | Cartesia | female | France (recommended) |
| `cartesia-Pierre` | Pierre | Cartesia | male | France |
| `cartesia-Hailey-French` | Hailey - French | Cartesia | female | France |

### Voices to avoid for France

| voice_id | Provider | Problem |
|---|---|---|
| `minimax-Camille` | MiniMax | Preview sounds French, but runtime produces Canadian/American accent. MiniMax is fundamentally a US/Chinese TTS engine. |
| `minimax-Louis` | MiniMax | Same issue — tagged French but accent drifts at runtime. |
| `11labs-*` | ElevenLabs | Many voices labeled "French" are trained on Canadian French speakers. Hard to distinguish in the catalog. |

### Voice parameters (recommended for France)

- `voice_temperature`: **0.7** (keep low — high values like 1.5+ cause accent drift)
- `voice_speed`: **1.0** (natural pace)

### Accent reinforcement in LLM prompt

Add this to the agent's system prompt identity section:
```
Tu parles avec un accent français métropolitain (France), jamais avec un accent québécois ou canadien. Utilise un registre professionnel parisien.
```

## Agent payload shape (typical)

```json
{
  "agent_name": "FR B2B Appointment Setter",
  "response_engine": {
    "type": "retell-llm",
    "llm_id": "llm_xxx"
  },
  "voice_id": "cartesia-Emma",
  "language": "fr-FR",
  "voice_temperature": 0.7,
  "voice_speed": 1.0,
  "begin_message": "Bonjour, ici Camille de ACME. Est-ce que je vous dérange ?",
  "webhook_url": "https://your-app.example/webhooks/retell",
  "enable_voicemail_detection": true,
  "voicemail_message": "Bonjour, ici Camille de ACME...",
  "analysis_summary_prompt": "Summarize call outcome in two sentences"
}
```

Useful optional fields:

- `max_call_duration_ms`
- `ring_duration_ms`
- `stt_mode`
- `custom_stt_config`
- `post_call_analysis_data`
- `analysis_successful_prompt`
- `analysis_summary_prompt`

## Phone call payload shape (typical)

```json
{
  "from_number": "+33140000000",
  "to_number": "+33600000000",
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

`from_number` must be a number that exists in Retell (purchased or imported).

## BYO telephony — why it matters for France

Retell only provisions US/Canada numbers for purchase. For any other country, including France, you must:

1. Buy a number from Twilio or Telnyx
2. Create a SIP trunk with that provider
3. Import the number into Retell with `import-number`

After import, the number appears in `list-numbers` and can be used as `from_number`.

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
- Create web call: https://docs.retellai.com/api-references/create-web-call
- Import phone number: https://docs.retellai.com/api-references/import-phone-number
- International calling & fees: https://docs.retellai.com/deploy/international-call
- Custom telephony: https://docs.retellai.com/deploy/custom-telephony
- Twilio setup: https://docs.retellai.com/deploy/twilio
- Language/voice: https://docs.retellai.com/build/set-language-and-voice
