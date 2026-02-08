#!/usr/bin/env python3
"""
Generate Retell cold-calling assets and optionally deploy via Retell REST API.

This script is intentionally safe by default:
- It never places real calls unless you pass --execute and RETELL_API_KEY is set.
- It prints curl commands so payloads can be reviewed before sending.

Subcommands:
  generate          Create agent payload + talk track + call template + curl templates
  create-agent      Create a voice agent in Retell (optional)
  list-agents       List Retell agents (optional)
  call-one          Start one outbound call (optional)
  start-calls       Start outbound calls from a leads CSV (optional)

Environment:
  RETELL_API_KEY    Retell API key (required for --execute)

This script attempts to load `.env` from:
  1) skill directory (../.env relative to this file)
  2) current working directory
Pass --env-file to override/add another source.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, time as dtime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_BASE_URL = "https://api.retellai.com"
RESULT_SCHEMA_VERSION = "retell-call-result/v1"
POLICY_STATE_SCHEMA_VERSION = "fr-policy-state/v1"
DEFAULT_FR_TIMEZONE = "Europe/Paris"
DEFAULT_FR_TIME_WINDOWS = "10:00-13:00,14:00-20:00"
DEFAULT_FR_MAX_ATTEMPTS_30D = 4
DEFAULT_FR_REFUSAL_COOLDOWN_DAYS = 60

DEFAULT_REPORT_PATH_TEMPLATE = "/get-phone-call/{call_id}"
DEFAULT_REPORT_FALLBACKS = [
    "/v2/get-phone-call/{call_id}",
    "/phone-call/{call_id}",
    "/v2/phone-call/{call_id}",
]

DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_INACTIVITY_TIMEOUT_SECONDS = 60
DEFAULT_POST_END_TIMEOUT_SECONDS = 30
DEFAULT_CALL_TIMEOUT_SECONDS = 300

REFUSAL_OUTCOMES = {
    "dnc_requested",
    "do_not_call",
    "opt_out",
    "not_interested",
    "refused",
    "refusal",
}


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_logs_dir() -> Path:
    return _skill_root() / "logs"


def _default_policy_state_path() -> Path:
    return _skill_root() / "state" / "fr_policy_state.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _safe_json_loads(body: str) -> Any:
    try:
        return json.loads(body)
    except Exception:
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except Exception:
            return None
    return None


def _normalize_mode(mode: str) -> str:
    value = (mode or "dynamic").strip().lower()
    if value not in {"dynamic", "static"}:
        raise ValueError("mode must be 'dynamic' or 'static'")
    return value


def _sanitize_file_component(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in (value or ""))
    return safe.strip("_") or "unknown"


def _unquote_env_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def _parse_env_line(line: str) -> Optional[Tuple[str, str]]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if not (value.startswith('"') or value.startswith("'")) and "#" in value:
        value = value.split("#", 1)[0].rstrip()

    return key, _unquote_env_value(value)


def _load_env_file(env_path: Path, *, locked_keys: set[str]) -> None:
    if not env_path.exists() or not env_path.is_file():
        return
    try:
        content = env_path.read_text(encoding="utf-8")
    except OSError:
        return

    for raw_line in content.splitlines():
        parsed = _parse_env_line(raw_line)
        if not parsed:
            continue
        key, value = parsed
        if key in locked_keys:
            continue
        os.environ[key] = value


def _load_default_env_files(*, explicit_env_file: Optional[str]) -> None:
    locked_keys = set(os.environ.keys())
    skill_root = _skill_root()

    _load_env_file(skill_root / ".env", locked_keys=locked_keys)
    _load_env_file(Path.cwd() / ".env", locked_keys=locked_keys)
    if explicit_env_file:
        _load_env_file(Path(explicit_env_file).expanduser().resolve(), locked_keys=locked_keys)


def _read_json(path: str) -> Dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    _write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _coalesce(*values: Optional[str]) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _get_nested(spec: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    current: Any = spec
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _build_system_prompt(spec: Dict[str, Any]) -> str:
    campaign = _get_nested(spec, "campaign")
    seller = _get_nested(spec, "seller")
    product = _get_nested(spec, "product")
    persona = _get_nested(spec, "persona")
    meeting = _get_nested(spec, "meeting")
    qualification = _get_nested(spec, "qualification")
    compliance = _get_nested(spec, "compliance")

    company_name = _coalesce(seller.get("companyName"), "notre entreprise")
    caller_name = _coalesce(seller.get("callerName"), "la personne appelante")
    caller_role = _coalesce(seller.get("callerRole"), "représentant(e)")
    offer = _coalesce(product.get("offer"), meeting.get("goal"), "un échange court")
    persona_title = _coalesce(persona.get("title"), "le bon interlocuteur")
    meeting_len = int(meeting.get("lengthMinutes") or 20)
    booking_link = _coalesce(meeting.get("bookingLink"))
    language_code = _coalesce(campaign.get("language"), _get_nested(spec, "retell").get("language"), "fr-FR")

    value_props = _as_list(product.get("valueProps"))
    proof_points = _as_list(product.get("proofPoints"))
    qual_questions = _as_list(qualification.get("questions"))

    dnc_language = _coalesce(
        compliance.get("dncLanguage"),
        "Bien sûr, je vous retire de nos appels et nous ne vous recontacterons plus.",
    )

    ai_disclosure = compliance.get("aiDisclosure") if isinstance(compliance.get("aiDisclosure"), dict) else {}
    ai_disclosure_enabled = bool(ai_disclosure.get("enabled", False))
    ai_disclosure_message = _coalesce(ai_disclosure.get("message"))

    lines: List[str] = []
    lines.append("You are an outbound B2B appointment-setting caller.")
    lines.append(f"Language: {language_code}. Keep responses natural and concise.")
    lines.append(f"Identity: You represent {company_name}. Your name is {caller_name} ({caller_role}).")
    lines.append(f"Audience: {persona_title} in a B2B context.")
    lines.append(f"Goal: book a {meeting_len}-minute meeting about {offer}.")
    lines.append("")
    lines.append("Non-negotiable rules:")
    lines.append("- Ask permission quickly and keep each turn short.")
    lines.append("- Ask one question at a time; avoid long monologues.")
    lines.append("- Be truthful; never invent metrics, references, or urgency.")
    lines.append("- If asked to stop or remove contact, reply exactly with this intent:")
    lines.append(f'  "{dnc_language}"')
    lines.append("  Then end the call politely.")
    lines.append("- If asked whether you are AI, answer truthfully.")
    if ai_disclosure_enabled and ai_disclosure_message:
        lines.append(f'  Preferred wording: "{ai_disclosure_message}"')
    lines.append("- Do not collect sensitive personal data.")
    lines.append("")
    lines.append("Conversation flow:")
    lines.append("1) Opener: permission-based and brief.")
    lines.append("2) Reason: one sentence with one relevant value point.")
    lines.append("3) Discovery: ask 2-3 qualification questions.")
    lines.append("4) Meeting ask: propose two time options or send booking link.")
    if booking_link:
        lines.append(f"   Booking link: {booking_link}")
    lines.append("5) Close: confirm next step and end quickly.")
    lines.append("")

    if value_props:
        lines.append("Value props (use at most 1-2 per call):")
        for item in value_props:
            lines.append(f"- {item}")
        lines.append("")

    if proof_points:
        lines.append("Proof points (use sparingly):")
        for item in proof_points:
            lines.append(f"- {item}")
        lines.append("")

    if qual_questions:
        lines.append("Qualification questions (pick 2-3):")
        for item in qual_questions:
            lines.append(f"- {item}")
        lines.append("")

    never_say = _as_list(campaign.get("neverSay"))
    if never_say:
        lines.append("Never say:")
        for phrase in never_say:
            lines.append(f"- {phrase}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _build_begin_message(spec: Dict[str, Any]) -> str:
    retell = _get_nested(spec, "retell")
    explicit = _coalesce(retell.get("beginMessage"))
    if explicit:
        return explicit
    seller = _get_nested(spec, "seller")
    company_name = _coalesce(seller.get("companyName"), "notre société")
    caller_name = _coalesce(seller.get("callerName"), "Camille")
    return f"Bonjour, ici {caller_name} de {company_name}. Est-ce que je vous dérange ?"


def _build_post_call_analysis_data() -> List[Dict[str, Any]]:
    return [
        {
            "type": "string",
            "name": "outcome",
            "description": "Best single outcome label.",
            "examples": ["booked_meeting", "requested_email", "not_interested", "dnc_requested"],
        },
        {
            "type": "boolean",
            "name": "is_decision_maker",
            "description": "Whether the contacted person is the right decision maker.",
            "examples": [True, False],
        },
        {
            "type": "string",
            "name": "interest_level",
            "description": "high, medium, low, or unknown.",
            "examples": ["high", "medium", "low", "unknown"],
        },
        {
            "type": "string",
            "name": "next_step",
            "description": "Agreed next action.",
            "examples": ["meeting_booked", "send_email", "follow_up_next_month"],
        },
    ]


def build_agent_payload(spec: Dict[str, Any]) -> Dict[str, Any]:
    campaign = _get_nested(spec, "campaign")
    compliance = _get_nested(spec, "compliance")
    voicemail = _get_nested(spec, "voicemail")
    retell = _get_nested(spec, "retell")

    llm_id = _coalesce(retell.get("llmId"), retell.get("llm_id"), "llm_replace_me")
    agent_name = _coalesce(campaign.get("assistantName"), campaign.get("name"), "Outbound B2B Appointment Setter")
    voice_id = _coalesce(retell.get("voiceId"), retell.get("voice_id"), "11labs-Adrian")
    language = _coalesce(campaign.get("language"), retell.get("language"), "fr-FR")

    payload: Dict[str, Any] = {
        "agent_name": agent_name,
        "response_engine": {"type": "retell-llm", "llm_id": llm_id},
        "voice_id": voice_id,
        "language": language,
        "begin_message": _build_begin_message(spec),
        "post_call_analysis_data": _build_post_call_analysis_data(),
        "analysis_successful_prompt": "The call should end with a clear next step or an explicit no-interest outcome.",
        "analysis_summary_prompt": "Summarize the conversation in two concise sentences.",
    }

    webhook_url = _coalesce(retell.get("webhookUrl"), retell.get("webhook_url"))
    if webhook_url:
        payload["webhook_url"] = webhook_url

    int_mappings = {
        "beginMessageDelayMs": "begin_message_delay_ms",
        "ringDurationMs": "ring_duration_ms",
        "maxCallDurationMs": "max_call_duration_ms",
    }
    for src_key, dst_key in int_mappings.items():
        value = retell.get(src_key)
        if isinstance(value, (int, float)):
            payload[dst_key] = int(value)

    stt_mode = _coalesce(retell.get("sttMode"), retell.get("stt_mode"))
    if stt_mode:
        payload["stt_mode"] = stt_mode

    custom_stt = retell.get("customSttConfig")
    if isinstance(custom_stt, dict) and custom_stt:
        payload["custom_stt_config"] = custom_stt

    boosted_keywords = _as_list(retell.get("boostedKeywords"))
    if boosted_keywords:
        payload["boosted_keywords"] = boosted_keywords

    pronunciation_dictionary = retell.get("pronunciationDictionary")
    if isinstance(pronunciation_dictionary, list) and pronunciation_dictionary:
        payload["pronunciation_dictionary"] = pronunciation_dictionary

    enable_vm = bool(voicemail.get("enabled", False)) or bool(retell.get("enableVoicemailDetection", False))
    if enable_vm:
        payload["enable_voicemail_detection"] = True
        vm_message = _coalesce(voicemail.get("message"), retell.get("voicemailMessage"))
        if vm_message:
            payload["voicemail_message"] = vm_message

    ai_disclosure = compliance.get("aiDisclosure") if isinstance(compliance.get("aiDisclosure"), dict) else {}
    if bool(ai_disclosure.get("enabled", False)):
        payload["version_description"] = "B2B outbound agent with truthful AI disclosure enabled"

    # Optional campaign runtime hints (used by operators, harmless for API payload)
    runtime_mode = _coalesce(retell.get("mode"))
    if runtime_mode:
        payload["version_description"] = _coalesce(payload.get("version_description"), "") + f" | mode={runtime_mode}"

    return payload


def build_talk_track_markdown(spec: Dict[str, Any]) -> str:
    seller = _get_nested(spec, "seller")
    product = _get_nested(spec, "product")
    persona = _get_nested(spec, "persona")
    meeting = _get_nested(spec, "meeting")
    qualification = _get_nested(spec, "qualification")
    compliance = _get_nested(spec, "compliance")

    company_name = _coalesce(seller.get("companyName"), "Votre entreprise")
    caller_name = _coalesce(seller.get("callerName"), "Votre prénom")
    product_name = _coalesce(product.get("name"), "Votre offre")
    persona_title = _coalesce(persona.get("title"), "votre persona cible")
    offer = _coalesce(product.get("offer"), meeting.get("goal"), "un échange de découverte")
    meeting_len = int(meeting.get("lengthMinutes") or 20)
    booking_link = _coalesce(meeting.get("bookingLink"))

    value_props = _as_list(product.get("valueProps"))
    proof_points = _as_list(product.get("proofPoints"))
    qual_questions = _as_list(qualification.get("questions"))

    dnc_language = _coalesce(
        compliance.get("dncLanguage"),
        "Bien sûr, je vous retire de nos appels et nous ne vous recontacterons plus.",
    )

    lines: List[str] = []
    lines.append(f"# Talk Track: {product_name} -> {persona_title}")
    lines.append("")
    lines.append("## Ouverture")
    lines.append(f'- "Bonjour, ici {caller_name} de {company_name}. Est-ce que je vous dérange ?"')
    lines.append("")
    lines.append("## Raison de l'appel (1 phrase)")
    lines.append(f'- "Je vous appelle parce qu\'on aide les {persona_title} à mettre en place {offer}."')
    lines.append("")
    lines.append("## Valeur (1-2 points)")
    for item in value_props[:4] or ["[Ajoutez 1-2 propositions de valeur]"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Questions de découverte (2-3)")
    for item in qual_questions[:6] or ["[Ajoutez une question de qualification]"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Proposition de rendez-vous")
    lines.append(f'- "Si c\'est pertinent, on peut faire un échange de {meeting_len} minutes la semaine prochaine."')
    lines.append('- "Vous préférez mardi matin ou jeudi après-midi ?"')
    if booking_link:
        lines.append(f'- Alternative: "Je peux aussi vous envoyer ce lien: {booking_link}"')
    lines.append("")
    lines.append("## Objections fréquentes")
    lines.append('- **"Envoyez un email"** -> "Avec plaisir, quel est le bon email et l\'angle le plus utile ?"')
    lines.append('- **"On a déjà un prestataire"** -> "Très bien. Je peux vérifier en 20 secondes si notre approche couvre un besoin complémentaire ?"')
    lines.append('- **"Pas de budget"** -> "Compris. C\'est un sujet de timing ou un non-sujet pour cette année ?"')
    lines.append('- **"Pas intéressé"** -> "Entendu, merci pour votre temps."')
    lines.append("")
    lines.append("## Preuves (sans exagération)")
    for item in proof_points[:4] or ["[Ajoutez 1-2 preuves crédibles]"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Suppression")
    lines.append(f'- Si demandé: "{dnc_language}" puis fin d\'appel.')
    lines.append("")
    lines.append("## Notes")
    lines.append("- Rester bref, clair, et orienté rendez-vous.")

    return "\n".join(lines).strip() + "\n"


def _make_curl_create_agent(base_url: str, agent_json_path: str) -> str:
    return "\n".join(
        [
            "# Create Retell agent",
            "curl -sS \\",
            f"  -X POST '{base_url.rstrip('/')}/create-agent' \\",
            "  -H 'Authorization: Bearer '" + '"$RETELL_API_KEY"' + " \\",
            "  -H 'Content-Type: application/json' \\",
            f"  -d @'{agent_json_path}'",
            "",
        ]
    )


def _make_curl_list_agents(base_url: str, *, limit: int, offset: int) -> str:
    query = urllib.parse.urlencode({"limit": int(limit), "offset": int(offset)})
    return "\n".join(
        [
            "# List Retell agents",
            "curl -sS \\",
            f"  -X GET '{base_url.rstrip('/')}/list-agents?{query}' \\",
            "  -H 'Authorization: Bearer '" + '"$RETELL_API_KEY"' + " \\",
            "  -H 'Accept: application/json'",
            "",
        ]
    )


def _make_curl_create_call(base_url: str, payload: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Create outbound phone call",
            "curl -sS \\",
            f"  -X POST '{base_url.rstrip('/')}/create-phone-call' \\",
            "  -H 'Authorization: Bearer '" + '"$RETELL_API_KEY"' + " \\",
            "  -H 'Content-Type: application/json' \\",
            "  -d '" + json.dumps(payload, ensure_ascii=False) + "'",
            "",
        ]
    )


def _retell_request(
    *,
    method: str,
    base_url: str,
    path: str,
    api_key: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[int, str]:
    url = base_url.rstrip("/") + path
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "codex-retell-cold-caller/2.0",
    }
    req = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = resp.read().decode("utf-8", errors="replace")
            return resp.getcode(), data
    except urllib.error.HTTPError as e:
        data = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return int(e.code), data


def _read_leads_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def _read_dnc_numbers(path: Optional[str]) -> set[str]:
    if not path:
        return set()
    numbers: set[str] = set()
    with open(path, "r", encoding="utf-8", newline="") as f:
        for line in f:
            number = line.strip()
            if number and not number.startswith("#"):
                numbers.add(number)
    return numbers


def _parse_kv_pairs(pairs: Optional[List[str]]) -> Dict[str, str]:
    if not pairs:
        return {}
    out: Dict[str, str] = {}
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"Invalid key/value '{item}'. Expected key=value.")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid key/value '{item}'. Key is empty.")
        out[key] = value
    return out


def _default_policy_state() -> Dict[str, Any]:
    return {"schema_version": POLICY_STATE_SCHEMA_VERSION, "numbers": {}}


def _load_policy_state(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return _default_policy_state()
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return _default_policy_state()
    try:
        data = _safe_json_loads(p.read_text(encoding="utf-8"))
    except OSError:
        return _default_policy_state()
    if not isinstance(data, dict):
        return _default_policy_state()
    if not isinstance(data.get("numbers"), dict):
        data["numbers"] = {}
    if not data.get("schema_version"):
        data["schema_version"] = POLICY_STATE_SCHEMA_VERSION
    return data


def _save_policy_state(path: Optional[str], state: Dict[str, Any]) -> None:
    if not path:
        return
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    txt = value.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ensure_number_entry(state: Dict[str, Any], number: str) -> Dict[str, Any]:
    numbers = state.setdefault("numbers", {})
    entry = numbers.get(number)
    if not isinstance(entry, dict):
        entry = {}
        numbers[number] = entry
    attempts = entry.get("attempts")
    refusals = entry.get("refusals")
    if not isinstance(attempts, list):
        entry["attempts"] = []
    if not isinstance(refusals, list):
        entry["refusals"] = []
    return entry


def _prune_number_entry(entry: Dict[str, Any], now_utc: datetime) -> None:
    attempts: List[str] = []
    for item in entry.get("attempts", []):
        dt = _parse_iso_datetime(item)
        if dt and dt >= now_utc - timedelta(days=365):
            attempts.append(_iso_utc(dt))
    entry["attempts"] = attempts

    refusals_clean: List[Dict[str, str]] = []
    for item in entry.get("refusals", []):
        if isinstance(item, str):
            dt = _parse_iso_datetime(item)
            reason = ""
        elif isinstance(item, dict):
            dt = _parse_iso_datetime(item.get("at"))
            reason = str(item.get("reason") or "")
        else:
            dt = None
            reason = ""
        if dt and dt >= now_utc - timedelta(days=3650):
            refusals_clean.append({"at": _iso_utc(dt), "reason": reason})
    entry["refusals"] = refusals_clean


def _record_fr_attempt(state: Dict[str, Any], number: str, when_utc: datetime) -> None:
    entry = _ensure_number_entry(state, number)
    _prune_number_entry(entry, when_utc)
    entry["attempts"].append(_iso_utc(when_utc))


def _record_fr_refusal(state: Dict[str, Any], number: str, when_utc: datetime, reason: str = "") -> None:
    entry = _ensure_number_entry(state, number)
    _prune_number_entry(entry, when_utc)
    entry["refusals"].append({"at": _iso_utc(when_utc), "reason": reason})


def _latest_refusal_datetime(entry: Dict[str, Any]) -> Optional[datetime]:
    latest: Optional[datetime] = None
    for item in entry.get("refusals", []):
        dt = None
        if isinstance(item, str):
            dt = _parse_iso_datetime(item)
        elif isinstance(item, dict):
            dt = _parse_iso_datetime(item.get("at"))
        if dt and (latest is None or dt > latest):
            latest = dt
    return latest


def _parse_fr_time_windows(value: str) -> List[Tuple[dtime, dtime]]:
    windows: List[Tuple[dtime, dtime]] = []
    raw = (value or "").strip()
    if not raw:
        return windows
    for part in raw.split(","):
        segment = part.strip()
        if not segment:
            continue
        if "-" not in segment:
            raise ValueError(f"Invalid time window '{segment}'. Use HH:MM-HH:MM.")
        start_txt, end_txt = segment.split("-", 1)
        try:
            start_t = dtime.fromisoformat(start_txt.strip())
            end_t = dtime.fromisoformat(end_txt.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid time in window '{segment}'.") from exc
        windows.append((start_t, end_t))
    return windows


def _is_local_time_in_windows(local_time: dtime, windows: Sequence[Tuple[dtime, dtime]]) -> bool:
    if not windows:
        return True
    for start_t, end_t in windows:
        if start_t <= local_time <= end_t:
            return True
    return False


def _read_holidays(path: Optional[str]) -> set[date]:
    if not path:
        return set()
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        return set()
    holidays: set[date] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            holidays.add(date.fromisoformat(s))
        except ValueError:
            continue
    return holidays


def _evaluate_fr_policy(
    *,
    number: str,
    state: Dict[str, Any],
    now_utc: Optional[datetime] = None,
    timezone_name: str = DEFAULT_FR_TIMEZONE,
    default_timezone_name: str = DEFAULT_FR_TIMEZONE,
    windows: Sequence[Tuple[dtime, dtime]] = (),
    max_attempts_30d: int = DEFAULT_FR_MAX_ATTEMPTS_30D,
    refusal_cooldown_days: int = DEFAULT_FR_REFUSAL_COOLDOWN_DAYS,
    holidays: Optional[set[date]] = None,
    enforce_weekdays: bool = True,
    enforce_time_windows: bool = True,
    enforce_attempts: bool = True,
    enforce_refusal_cooldown: bool = True,
) -> Dict[str, Any]:
    now = (now_utc or _utc_now()).astimezone(timezone.utc)
    holidays = holidays or set()

    tz_name = _coalesce(timezone_name, default_timezone_name, DEFAULT_FR_TIMEZONE)
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz_name = _coalesce(default_timezone_name, DEFAULT_FR_TIMEZONE)
        tz = ZoneInfo(tz_name)

    local_dt = now.astimezone(tz)

    entry = _ensure_number_entry(state, number)
    _prune_number_entry(entry, now)

    reasons: List[Dict[str, str]] = []

    if enforce_weekdays and local_dt.weekday() >= 5:
        reasons.append(
            {
                "code": "weekend_block",
                "message": "Calls blocked on Saturday/Sunday by FR policy guard.",
            }
        )

    if local_dt.date() in holidays:
        reasons.append(
            {
                "code": "holiday_block",
                "message": "Calls blocked on configured holiday by FR policy guard.",
            }
        )

    if enforce_time_windows and not _is_local_time_in_windows(local_dt.timetz().replace(tzinfo=None), windows):
        reasons.append(
            {
                "code": "time_window_block",
                "message": "Outside allowed local calling windows.",
            }
        )

    window_start = now - timedelta(days=30)
    attempts_30d = 0
    for item in entry.get("attempts", []):
        dt = _parse_iso_datetime(item)
        if dt and dt >= window_start:
            attempts_30d += 1

    if enforce_attempts and attempts_30d >= int(max_attempts_30d):
        reasons.append(
            {
                "code": "attempt_limit_block",
                "message": f"Attempt limit reached in rolling 30 days ({attempts_30d}/{max_attempts_30d}).",
            }
        )

    refusal_until = ""
    latest_refusal = _latest_refusal_datetime(entry)
    if latest_refusal is not None:
        cooldown_until = latest_refusal + timedelta(days=int(refusal_cooldown_days))
        refusal_until = _iso_utc(cooldown_until)
        if enforce_refusal_cooldown and now < cooldown_until:
            reasons.append(
                {
                    "code": "refusal_cooldown_block",
                    "message": f"Refusal cooldown active until {refusal_until}.",
                }
            )

    return {
        "allowed": len(reasons) == 0,
        "reasons": reasons,
        "timezone": tz_name,
        "local_datetime": local_dt.isoformat(),
        "attempts_30d": attempts_30d,
        "refusal_until": refusal_until,
    }


def _lead_to_call_payload(
    *,
    from_number: str,
    agent_id: str,
    lead: Dict[str, str],
    static_vars: Dict[str, str],
    campaign_tag: str,
    mode: str,
) -> Dict[str, Any]:
    phone = _coalesce(lead.get("phone_e164"), lead.get("phone"), lead.get("number"))
    if not phone:
        raise ValueError("Lead is missing phone_e164/phone/number")

    payload: Dict[str, Any] = {
        "from_number": from_number,
        "to_number": phone,
        "override_agent_id": agent_id,
    }

    call_mode = _normalize_mode(mode)

    if call_mode == "dynamic":
        dynamic_vars: Dict[str, str] = {}
        for key in ["first_name", "last_name", "company", "title", "timezone", "notes"]:
            if lead.get(key):
                dynamic_vars[key] = lead[key]
        dynamic_vars.update(static_vars)
        if dynamic_vars:
            payload["retell_llm_dynamic_variables"] = dynamic_vars

    metadata: Dict[str, str] = {}
    if campaign_tag:
        metadata["campaign"] = campaign_tag
    for key in ["email", "company", "title", "timezone"]:
        if lead.get(key):
            metadata[key] = lead[key]
    if metadata:
        payload["metadata"] = metadata

    return payload


def _new_call_result(
    *,
    mode: str,
    from_number: str,
    to_number: str,
    agent_id: str,
    campaign_tag: str,
    lead: Optional[Dict[str, Any]],
    payload: Dict[str, Any],
    watchdog: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "pending",
        "terminal_reason": "",
        "started_at": _iso_utc(_utc_now()),
        "finished_at": "",
        "elapsed_seconds": None,
        "call": {
            "id": "",
            "agent_id": agent_id,
            "from_number": from_number,
            "to_number": to_number,
            "mode": _normalize_mode(mode),
            "campaign_tag": campaign_tag,
        },
        "watchdog": watchdog,
        "lead": lead or {},
        "payload": payload,
        "policy": {
            "fr_gate_enabled": False,
            "allowed": True,
            "reasons": [],
            "timezone": "",
            "local_datetime": "",
            "attempts_30d": None,
            "refusal_until": "",
        },
        "http": {
            "create_call_status": None,
            "report_status": None,
        },
        "analysis": {
            "summary": "",
            "outcome": "",
            "duration_seconds": None,
            "ended_reason": "",
            "transcript": "",
            "raw_fields": {},
        },
        "error": "",
        "raw": {
            "create_call_response": None,
            "report_response": None,
            "errors": [],
        },
    }


def _finalize_call_result(result: Dict[str, Any], *, status: str, terminal_reason: str, error: str = "") -> None:
    result["status"] = status
    result["terminal_reason"] = terminal_reason
    if error:
        result["error"] = error
    finished = _utc_now()
    result["finished_at"] = _iso_utc(finished)

    started = _parse_iso_datetime(result.get("started_at"))
    if started:
        result["elapsed_seconds"] = max(0.0, (finished - started).total_seconds())


def _write_call_result_log(result: Dict[str, Any], logs_dir: str) -> str:
    root = Path(logs_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    started = _parse_iso_datetime(result.get("started_at")) or _utc_now()
    stamp = started.strftime("%Y%m%d_%H%M%S")
    call_id = _sanitize_file_component(str(_get_nested(result, "call").get("id") or "pending"))
    to_number = _sanitize_file_component(str(_get_nested(result, "call").get("to_number") or "unknown"))
    status = _sanitize_file_component(str(result.get("status") or "unknown"))
    filename = f"{stamp}_{status}_{to_number}_{call_id}.json"
    out_path = root / filename
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(out_path)


def _extract_call_id_from_create_response(data: Any) -> str:
    if isinstance(data, dict):
        for key in ["call_id", "callId", "id"]:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = data.get("call")
        if isinstance(nested, dict):
            return _extract_call_id_from_create_response(nested)
        nested_data = data.get("data")
        if isinstance(nested_data, dict):
            return _extract_call_id_from_create_response(nested_data)
    return ""


def _extract_call_record(data: Any, call_id: str) -> Optional[Dict[str, Any]]:
    if isinstance(data, dict):
        cid = _extract_call_id_from_create_response(data)
        if cid and cid == call_id:
            return data

        # Common wrappers
        for key in ["call", "data", "phone_call"]:
            nested = data.get(key)
            if isinstance(nested, dict):
                cid_nested = _extract_call_id_from_create_response(nested)
                if not call_id or cid_nested == call_id:
                    return nested
            if isinstance(nested, list):
                found = _extract_call_record(nested, call_id)
                if found:
                    return found

        # If this dict already looks like a call record, return it.
        for status_key in ["status", "call_status", "state"]:
            if status_key in data:
                return data

    if isinstance(data, list):
        for item in data:
            found = _extract_call_record(item, call_id)
            if found:
                return found

    return None


def _fetch_call_report(
    *,
    base_url: str,
    api_key: str,
    call_id: str,
    report_paths: Sequence[str],
) -> Dict[str, Any]:
    errors: List[str] = []

    safe_call_id = urllib.parse.quote(call_id, safe="")
    candidates = [p for p in report_paths if str(p).strip()]

    for template in candidates:
        path = template.format(call_id=safe_call_id)
        if not path.startswith("/"):
            path = "/" + path

        status, body = _retell_request(method="GET", base_url=base_url, path=path, api_key=api_key)
        if not (200 <= status < 300):
            errors.append(f"{path} -> HTTP {status}")
            continue

        parsed = _safe_json_loads(body)
        if parsed is None:
            errors.append(f"{path} -> non-JSON response")
            continue

        record = _extract_call_record(parsed, call_id)
        if record is None and isinstance(parsed, dict):
            record = parsed

        return {
            "ok": True,
            "status": status,
            "path": path,
            "body": body,
            "record": record,
        }

    return {
        "ok": False,
        "error": "; ".join(errors[-5:]) if errors else "No report path available",
        "record": None,
        "status": None,
        "path": "",
        "body": "",
    }


def _extract_outcome(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ["outcome", "result", "label"]:
            if isinstance(value.get(key), str) and str(value.get(key)).strip():
                return str(value.get(key)).strip()
    if isinstance(value, list):
        # post_call_analysis_data may be a list of {name, value} dictionaries
        for item in value:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip().lower()
                if name == "outcome":
                    v = item.get("value")
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                    ex = item.get("examples")
                    if isinstance(ex, list) and ex and isinstance(ex[0], str):
                        return ex[0].strip()
    return ""


def _extract_report_fields(record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = record or {}

    call_id = _extract_call_id_from_create_response(data)

    status_raw = _coalesce(
        str(data.get("call_status") or ""),
        str(data.get("status") or ""),
        str(data.get("state") or ""),
    )
    status_norm = status_raw.strip().lower()

    summary = _coalesce(
        str(data.get("summary") or ""),
        str(data.get("analysis_summary") or ""),
        str(data.get("call_summary") or ""),
    )

    transcript = _coalesce(str(data.get("transcript") or ""))

    outcome = _extract_outcome(data.get("outcome"))
    if not outcome:
        outcome = _extract_outcome(data.get("post_call_analysis_data"))
    if not outcome:
        outcome = _extract_outcome(data.get("analysis"))

    ended_reason = _coalesce(
        str(data.get("ended_reason") or ""),
        str(data.get("endedReason") or ""),
        str(data.get("disconnection_reason") or ""),
        str(data.get("end_reason") or ""),
    )

    duration_seconds = None
    for key in ["duration_seconds", "duration", "call_duration_seconds", "duration_sec"]:
        v = _coerce_float(data.get(key))
        if v is not None:
            duration_seconds = float(v)
            break
    if duration_seconds is None:
        ms = _coerce_float(data.get("duration_ms"))
        if ms is not None:
            duration_seconds = float(ms) / 1000.0

    ended_statuses = {
        "ended",
        "completed",
        "finished",
        "done",
        "terminated",
        "failed",
        "canceled",
        "cancelled",
    }

    has_report = bool(summary or transcript or outcome)
    ended = status_norm in ended_statuses or bool(ended_reason)

    return {
        "call_id": call_id,
        "status_raw": status_raw,
        "status_norm": status_norm,
        "summary": summary,
        "transcript": transcript,
        "outcome": outcome,
        "ended_reason": ended_reason,
        "duration_seconds": duration_seconds,
        "ended": ended,
        "has_report": has_report,
        "raw_fields": data,
    }


def _wait_for_call_report(
    *,
    call_id: str,
    fetch_report_fn: Callable[[], Dict[str, Any]],
    poll_interval_seconds: float,
    inactivity_timeout_seconds: int,
    post_end_timeout_seconds: int,
    call_timeout_seconds: int,
) -> Dict[str, Any]:
    started = time.monotonic()
    last_activity = started
    ended_seen_at: Optional[float] = None
    last_error = ""

    while True:
        now = time.monotonic()
        elapsed = now - started

        if elapsed >= float(call_timeout_seconds):
            return {
                "status": "timeout",
                "terminal_reason": "global_timeout",
                "elapsed_seconds": elapsed,
                "error": last_error or f"Global timeout reached ({call_timeout_seconds}s)",
                "report": None,
                "report_fields": {},
                "report_fetch": None,
            }

        fetched = fetch_report_fn()
        if fetched.get("ok"):
            last_activity = now
            report_record = fetched.get("record") if isinstance(fetched.get("record"), dict) else {}
            fields = _extract_report_fields(report_record)

            if fields.get("has_report"):
                return {
                    "status": "completed",
                    "terminal_reason": "report_received",
                    "elapsed_seconds": elapsed,
                    "error": "",
                    "report": report_record,
                    "report_fields": fields,
                    "report_fetch": fetched,
                }

            if fields.get("ended") and ended_seen_at is None:
                ended_seen_at = now

            if ended_seen_at is not None and (now - ended_seen_at) >= float(post_end_timeout_seconds):
                return {
                    "status": "ended_no_report",
                    "terminal_reason": "post_end_timeout",
                    "elapsed_seconds": elapsed,
                    "error": f"Call ended but no report within {post_end_timeout_seconds}s",
                    "report": report_record,
                    "report_fields": fields,
                    "report_fetch": fetched,
                }
        else:
            err = _coalesce(str(fetched.get("error") or ""))
            if err:
                last_error = err

        now_after = time.monotonic()
        if (now_after - last_activity) >= float(inactivity_timeout_seconds):
            return {
                "status": "timeout",
                "terminal_reason": "inactivity_timeout",
                "elapsed_seconds": now_after - started,
                "error": last_error or f"No report activity for {inactivity_timeout_seconds}s",
                "report": None,
                "report_fields": {},
                "report_fetch": fetched,
            }

        time.sleep(max(0.1, float(poll_interval_seconds)))


def _build_watchdog_config(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "wait_report": bool(getattr(args, "wait_report", False)),
        "poll_interval_seconds": float(getattr(args, "poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS)),
        "inactivity_timeout_seconds": int(getattr(args, "inactivity_timeout_seconds", DEFAULT_INACTIVITY_TIMEOUT_SECONDS)),
        "post_end_timeout_seconds": int(getattr(args, "post_end_timeout_seconds", DEFAULT_POST_END_TIMEOUT_SECONDS)),
        "call_timeout_seconds": int(getattr(args, "call_timeout_seconds", DEFAULT_CALL_TIMEOUT_SECONDS)),
        "report_path_template": str(getattr(args, "report_path_template", DEFAULT_REPORT_PATH_TEMPLATE)),
        "report_path_fallback": list(getattr(args, "report_path_fallback", []) or []),
    }


def _resolve_report_paths(args: argparse.Namespace) -> List[str]:
    base = _coalesce(getattr(args, "report_path_template", DEFAULT_REPORT_PATH_TEMPLATE), DEFAULT_REPORT_PATH_TEMPLATE)
    fallbacks = list(getattr(args, "report_path_fallback", []) or [])
    paths: List[str] = [base]
    for p in fallbacks + DEFAULT_REPORT_FALLBACKS:
        if p not in paths:
            paths.append(p)
    return paths


def _prepare_batch_calls(
    *,
    leads: Sequence[Dict[str, str]],
    dnc: set[str],
    from_number: str,
    agent_id: str,
    mode: str,
    static_vars: Dict[str, str],
    campaign_tag: str,
    fr_policy_enabled: bool,
    fr_policy_state: Dict[str, Any],
    fr_windows: Sequence[Tuple[dtime, dtime]],
    fr_timezone_default: str,
    fr_max_attempts_30d: int,
    fr_refusal_cooldown_days: int,
    fr_holidays: set[date],
    now_utc: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    prepared: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    now = now_utc or _utc_now()

    for lead in leads:
        phone = _coalesce(lead.get("phone_e164"), lead.get("phone"), lead.get("number"))
        if not phone:
            blocked.append(
                {
                    "status": "blocked_invalid_lead",
                    "number": "",
                    "reasons": [{"code": "missing_number", "message": "Lead missing phone number."}],
                    "lead": lead,
                }
            )
            continue

        if phone in dnc:
            blocked.append(
                {
                    "status": "blocked_dnc",
                    "number": phone,
                    "reasons": [{"code": "dnc_block", "message": "Number exists in suppression list."}],
                    "lead": lead,
                }
            )
            continue

        policy_eval = {
            "allowed": True,
            "reasons": [],
            "timezone": _coalesce(lead.get("timezone"), fr_timezone_default),
            "local_datetime": "",
            "attempts_30d": None,
            "refusal_until": "",
        }

        if fr_policy_enabled:
            policy_eval = _evaluate_fr_policy(
                number=phone,
                state=fr_policy_state,
                now_utc=now,
                timezone_name=_coalesce(lead.get("timezone"), fr_timezone_default),
                default_timezone_name=fr_timezone_default,
                windows=fr_windows,
                max_attempts_30d=fr_max_attempts_30d,
                refusal_cooldown_days=fr_refusal_cooldown_days,
                holidays=fr_holidays,
                enforce_weekdays=True,
                enforce_time_windows=True,
                enforce_attempts=True,
                enforce_refusal_cooldown=True,
            )

            if not policy_eval.get("allowed"):
                blocked.append(
                    {
                        "status": "blocked_policy",
                        "number": phone,
                        "reasons": list(policy_eval.get("reasons") or []),
                        "lead": lead,
                        "policy": policy_eval,
                    }
                )
                continue

        payload = _lead_to_call_payload(
            from_number=from_number,
            agent_id=agent_id,
            lead=lead,
            static_vars=static_vars,
            campaign_tag=campaign_tag,
            mode=mode,
        )
        prepared.append({"lead": lead, "payload": payload, "policy": policy_eval})

    return prepared, blocked


def _apply_policy_to_result(result: Dict[str, Any], *, fr_policy_enabled: bool, policy_eval: Optional[Dict[str, Any]]) -> None:
    result["policy"]["fr_gate_enabled"] = fr_policy_enabled
    if not policy_eval:
        return
    result["policy"]["allowed"] = bool(policy_eval.get("allowed", True))
    result["policy"]["reasons"] = list(policy_eval.get("reasons") or [])
    result["policy"]["timezone"] = _coalesce(str(policy_eval.get("timezone") or ""))
    result["policy"]["local_datetime"] = _coalesce(str(policy_eval.get("local_datetime") or ""))
    result["policy"]["attempts_30d"] = policy_eval.get("attempts_30d")
    result["policy"]["refusal_until"] = _coalesce(str(policy_eval.get("refusal_until") or ""))


def _set_result_analysis(result: Dict[str, Any], fields: Dict[str, Any]) -> None:
    result["analysis"]["summary"] = _coalesce(str(fields.get("summary") or ""))
    result["analysis"]["outcome"] = _coalesce(str(fields.get("outcome") or ""))
    result["analysis"]["duration_seconds"] = fields.get("duration_seconds")
    result["analysis"]["ended_reason"] = _coalesce(str(fields.get("ended_reason") or ""))
    result["analysis"]["transcript"] = _coalesce(str(fields.get("transcript") or ""))
    result["analysis"]["raw_fields"] = fields.get("raw_fields") if isinstance(fields.get("raw_fields"), dict) else {}


def _execute_call(
    *,
    base_url: str,
    api_key: str,
    payload: Dict[str, Any],
    result: Dict[str, Any],
    watchdog: Dict[str, Any],
    report_paths: Sequence[str],
) -> Dict[str, Any]:
    status, body = _retell_request(method="POST", base_url=base_url, path="/create-phone-call", api_key=api_key, payload=payload)
    result["http"]["create_call_status"] = status
    result["raw"]["create_call_response"] = body

    parsed = _safe_json_loads(body)
    call_id = _extract_call_id_from_create_response(parsed)
    if call_id:
        result["call"]["id"] = call_id

    if not (200 <= status < 300):
        _finalize_call_result(
            result,
            status="error",
            terminal_reason="create_call_http_error",
            error=f"HTTP {status} while creating call",
        )
        return result

    if not watchdog.get("wait_report"):
        _finalize_call_result(result, status="submitted", terminal_reason="submitted_without_wait")
        return result

    if not call_id:
        _finalize_call_result(
            result,
            status="ended_no_report",
            terminal_reason="missing_call_id",
            error="Call accepted but call_id missing; cannot wait for report.",
        )
        return result

    def _fetcher() -> Dict[str, Any]:
        return _fetch_call_report(
            base_url=base_url,
            api_key=api_key,
            call_id=call_id,
            report_paths=report_paths,
        )

    wait_outcome = _wait_for_call_report(
        call_id=call_id,
        fetch_report_fn=_fetcher,
        poll_interval_seconds=float(watchdog.get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS)),
        inactivity_timeout_seconds=int(watchdog.get("inactivity_timeout_seconds", DEFAULT_INACTIVITY_TIMEOUT_SECONDS)),
        post_end_timeout_seconds=int(watchdog.get("post_end_timeout_seconds", DEFAULT_POST_END_TIMEOUT_SECONDS)),
        call_timeout_seconds=int(watchdog.get("call_timeout_seconds", DEFAULT_CALL_TIMEOUT_SECONDS)),
    )

    report_fetch = wait_outcome.get("report_fetch") if isinstance(wait_outcome.get("report_fetch"), dict) else {}
    result["http"]["report_status"] = report_fetch.get("status")
    result["raw"]["report_response"] = report_fetch.get("body")

    fields = wait_outcome.get("report_fields") if isinstance(wait_outcome.get("report_fields"), dict) else {}
    _set_result_analysis(result, fields)

    if wait_outcome.get("status") == "completed":
        _finalize_call_result(result, status="completed", terminal_reason="report_received")
    elif wait_outcome.get("status") == "ended_no_report":
        _finalize_call_result(
            result,
            status="ended_no_report",
            terminal_reason="post_end_timeout",
            error=_coalesce(str(wait_outcome.get("error") or "")),
        )
    else:
        _finalize_call_result(
            result,
            status="timeout",
            terminal_reason=_coalesce(str(wait_outcome.get("terminal_reason") or "timeout")),
            error=_coalesce(str(wait_outcome.get("error") or "")),
        )

    return result


def _is_refusal_outcome(outcome: str) -> bool:
    return (outcome or "").strip().lower() in REFUSAL_OUTCOMES


def _print_result_summary(result: Dict[str, Any]) -> None:
    call = result.get("call", {}) if isinstance(result.get("call"), dict) else {}
    analysis = result.get("analysis", {}) if isinstance(result.get("analysis"), dict) else {}
    print(
        "[RESULT] "
        f"status={result.get('status')} "
        f"call_id={call.get('id') or '-'} "
        f"to={call.get('to_number') or '-'} "
        f"outcome={analysis.get('outcome') or '-'}"
    )


def cmd_generate(args: argparse.Namespace) -> int:
    spec = _read_json(args.spec)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    retell_cfg = _get_nested(spec, "retell")
    campaign_cfg = _get_nested(spec, "campaign")
    base_url = _coalesce(retell_cfg.get("baseUrl"), DEFAULT_BASE_URL)

    agent_payload = build_agent_payload(spec)
    talk_track = build_talk_track_markdown(spec)

    from_number = _coalesce(retell_cfg.get("fromNumber"), "+33100000000")
    agent_id_hint = _coalesce(args.agent_id, "agent_replace_me")
    campaign_name = _coalesce(campaign_cfg.get("name"), "fr-b2b-campaign")

    call_example_payload = {
        "from_number": from_number,
        "to_number": "+33600000000",
        "override_agent_id": agent_id_hint,
        "retell_llm_dynamic_variables": {
            "first_name": "Marie",
            "company": "Example SAS",
            "title": "DRH",
            "timezone": "Europe/Paris",
        },
        "metadata": {"campaign": campaign_name},
    }

    agent_json_path = out_dir / "agent.create.json"
    talk_track_path = out_dir / "talk_track.md"
    call_json_path = out_dir / "call.create.example.json"
    curl_agent_path = out_dir / "curl_create_agent.sh"
    curl_call_path = out_dir / "curl_create_call.example.sh"

    _write_json(agent_json_path, agent_payload)
    _write_text(talk_track_path, talk_track)
    _write_json(call_json_path, call_example_payload)
    _write_text(curl_agent_path, _make_curl_create_agent(base_url, str(agent_json_path)))
    _write_text(curl_call_path, _make_curl_create_call(base_url, call_example_payload))

    print(f"[OK] Wrote: {agent_json_path}")
    print(f"[OK] Wrote: {talk_track_path}")
    print(f"[OK] Wrote: {call_json_path}")
    print(f"[OK] Wrote: {curl_agent_path}")
    print(f"[OK] Wrote: {curl_call_path}")
    return 0


def cmd_create_agent(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    payload = _read_json(args.agent_json)

    print(_make_curl_create_agent(base_url, args.agent_json))
    if not args.execute:
        print("[DRY RUN] Pass --execute to create the agent in Retell.")
        return 0

    api_key = os.environ.get("RETELL_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] RETELL_API_KEY is required for --execute", file=sys.stderr)
        return 2

    status, body = _retell_request(method="POST", base_url=base_url, path="/create-agent", api_key=api_key, payload=payload)
    print(f"[HTTP {status}] {body}")
    if 200 <= status < 300:
        parsed = _safe_json_loads(body)
        if isinstance(parsed, dict):
            agent_id = _coalesce(str(parsed.get("agent_id") or ""))
            if agent_id:
                print(f"[OK] agent_id={agent_id}")
    return 0 if 200 <= status < 300 else 1


def cmd_list_agents(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    limit = int(args.limit)
    offset = int(args.offset)

    print(_make_curl_list_agents(base_url, limit=limit, offset=offset))
    if not args.execute:
        print("[DRY RUN] Pass --execute to list agents from Retell.")
        return 0

    api_key = os.environ.get("RETELL_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] RETELL_API_KEY is required for --execute", file=sys.stderr)
        return 2

    status, body = _retell_request(
        method="GET",
        base_url=base_url,
        path=f"/list-agents?limit={limit}&offset={offset}",
        api_key=api_key,
    )
    if not (200 <= status < 300):
        print(f"[HTTP {status}] {body}")
        return 1

    data = _safe_json_loads(body)
    if not isinstance(data, (dict, list)):
        print(body)
        return 0

    agents: List[Dict[str, Any]]
    if isinstance(data, list):
        agents = [item for item in data if isinstance(item, dict)]
    elif isinstance(data.get("data"), list):
        agents = [item for item in data["data"] if isinstance(item, dict)]
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    for agent in agents:
        agent_id = agent.get("agent_id") or ""
        agent_name = agent.get("agent_name") or ""
        is_published = agent.get("is_published")
        print(f"{agent_id}\t{agent_name}\t{is_published}")
    return 0


def _add_fr_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fr-policy", action="store_true", help="Enable France compliance gate before dialing.")
    parser.add_argument(
        "--fr-policy-state",
        default=str(_default_policy_state_path()),
        help="Path to FR policy state JSON used for attempts/refusals tracking.",
    )
    parser.add_argument(
        "--fr-timezone-default",
        default=DEFAULT_FR_TIMEZONE,
        help="Default timezone when lead timezone is missing.",
    )
    parser.add_argument(
        "--fr-time-windows",
        default=DEFAULT_FR_TIME_WINDOWS,
        help="Allowed local time windows (HH:MM-HH:MM,comma-separated).",
    )
    parser.add_argument(
        "--fr-max-attempts-30d",
        type=int,
        default=DEFAULT_FR_MAX_ATTEMPTS_30D,
        help="Maximum solicitation attempts in rolling 30 days.",
    )
    parser.add_argument(
        "--fr-refusal-cooldown-days",
        type=int,
        default=DEFAULT_FR_REFUSAL_COOLDOWN_DAYS,
        help="Minimum days to wait after explicit refusal.",
    )
    parser.add_argument(
        "--fr-holidays-file",
        help="Optional file with blocked holiday dates (YYYY-MM-DD, one per line).",
    )


def _add_wait_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--wait-report", action="store_true", help="Wait for final call report instead of returning on submission.")
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Polling interval while waiting for report.",
    )
    parser.add_argument(
        "--inactivity-timeout-seconds",
        type=int,
        default=DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
        help="Timeout when report endpoint has no usable activity.",
    )
    parser.add_argument(
        "--post-end-timeout-seconds",
        type=int,
        default=DEFAULT_POST_END_TIMEOUT_SECONDS,
        help="Timeout once call is ended but no report details are available.",
    )
    parser.add_argument(
        "--call-timeout-seconds",
        type=int,
        default=DEFAULT_CALL_TIMEOUT_SECONDS,
        help="Global timeout while waiting for report.",
    )
    parser.add_argument(
        "--report-path-template",
        default=DEFAULT_REPORT_PATH_TEMPLATE,
        help="Primary report endpoint template (must include {call_id}).",
    )
    parser.add_argument(
        "--report-path-fallback",
        action="append",
        default=[],
        help="Optional fallback report endpoint template (repeatable).",
    )


def cmd_call_one(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    mode = _normalize_mode(args.mode)

    api_key = os.environ.get("RETELL_API_KEY", "").strip()

    lead = {
        "phone_e164": args.to_number.strip(),
        "first_name": "",
        "last_name": "",
        "company": "",
        "title": "",
        "email": "",
        "timezone": _coalesce(args.timezone, args.fr_timezone_default, DEFAULT_FR_TIMEZONE),
        "notes": "",
    }

    static_vars = _parse_kv_pairs(args.var)
    metadata = _parse_kv_pairs(args.meta)

    payload: Dict[str, Any] = {
        "from_number": args.from_number.strip(),
        "to_number": args.to_number.strip(),
        "override_agent_id": args.agent_id.strip(),
    }

    if mode == "dynamic" and static_vars:
        payload["retell_llm_dynamic_variables"] = static_vars

    if metadata:
        payload["metadata"] = metadata
    elif args.campaign_tag:
        payload["metadata"] = {"campaign": args.campaign_tag}

    dnc = _read_dnc_numbers(args.dnc)
    fr_holidays = _read_holidays(args.fr_holidays_file)
    fr_windows = _parse_fr_time_windows(args.fr_time_windows)
    fr_state = _load_policy_state(args.fr_policy_state if args.fr_policy else None)

    policy_eval = {
        "allowed": True,
        "reasons": [],
        "timezone": _coalesce(lead.get("timezone"), args.fr_timezone_default),
        "local_datetime": "",
        "attempts_30d": None,
        "refusal_until": "",
    }

    if args.to_number.strip() in dnc:
        policy_eval = {
            "allowed": False,
            "reasons": [{"code": "dnc_block", "message": "Number exists in suppression list."}],
            "timezone": _coalesce(lead.get("timezone"), args.fr_timezone_default),
            "local_datetime": "",
            "attempts_30d": None,
            "refusal_until": "",
        }
    elif args.fr_policy:
        policy_eval = _evaluate_fr_policy(
            number=args.to_number.strip(),
            state=fr_state,
            timezone_name=_coalesce(lead.get("timezone"), args.fr_timezone_default),
            default_timezone_name=args.fr_timezone_default,
            windows=fr_windows,
            max_attempts_30d=args.fr_max_attempts_30d,
            refusal_cooldown_days=args.fr_refusal_cooldown_days,
            holidays=fr_holidays,
        )

    watchdog = _build_watchdog_config(args)
    result = _new_call_result(
        mode=mode,
        from_number=args.from_number.strip(),
        to_number=args.to_number.strip(),
        agent_id=args.agent_id.strip(),
        campaign_tag=_coalesce(args.campaign_tag),
        lead=lead,
        payload=payload,
        watchdog=watchdog,
    )
    _apply_policy_to_result(result, fr_policy_enabled=bool(args.fr_policy), policy_eval=policy_eval)

    print(_make_curl_create_call(base_url, payload))

    if not policy_eval.get("allowed", True):
        _finalize_call_result(result, status="blocked_policy", terminal_reason="policy_block")
        if policy_eval.get("reasons"):
            result["error"] = "; ".join([str(r.get("code")) for r in policy_eval["reasons"]])
        log_path = _write_call_result_log(result, args.logs_dir)
        print(f"[BLOCKED] {result['error']} | log={log_path}")
        return 1

    if not args.execute:
        _finalize_call_result(result, status="dry_run", terminal_reason="dry_run")
        log_path = _write_call_result_log(result, args.logs_dir)
        print(f"[DRY RUN] Pass --execute to place the call via Retell. log={log_path}")
        return 0

    if not api_key:
        print("[ERROR] RETELL_API_KEY is required for --execute", file=sys.stderr)
        return 2

    report_paths = _resolve_report_paths(args)
    result = _execute_call(
        base_url=base_url,
        api_key=api_key,
        payload=payload,
        result=result,
        watchdog=watchdog,
        report_paths=report_paths,
    )

    if result["status"] in {"submitted", "completed", "ended_no_report", "timeout"} and result["http"].get("create_call_status") and int(result["http"]["create_call_status"]) < 300:
        if args.fr_policy:
            _record_fr_attempt(fr_state, args.to_number.strip(), _utc_now())

    if args.fr_policy and _is_refusal_outcome(_coalesce(result["analysis"].get("outcome"))):
        _record_fr_refusal(fr_state, args.to_number.strip(), _utc_now(), reason=_coalesce(result["analysis"].get("outcome")))

    if args.fr_policy:
        _save_policy_state(args.fr_policy_state, fr_state)

    log_path = _write_call_result_log(result, args.logs_dir)
    _print_result_summary(result)
    print(f"[LOG] {log_path}")

    return 0 if result.get("status") in {"submitted", "completed", "dry_run"} else 1


def cmd_start_calls(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    mode = _normalize_mode(args.mode)
    static_vars = _parse_kv_pairs(args.var)

    leads = _read_leads_csv(args.leads)
    dnc = _read_dnc_numbers(args.dnc)
    fr_holidays = _read_holidays(args.fr_holidays_file)
    fr_windows = _parse_fr_time_windows(args.fr_time_windows)
    fr_state = _load_policy_state(args.fr_policy_state if args.fr_policy else None)

    prepared, blocked = _prepare_batch_calls(
        leads=leads,
        dnc=dnc,
        from_number=args.from_number.strip(),
        agent_id=args.agent_id.strip(),
        mode=mode,
        static_vars=static_vars,
        campaign_tag=_coalesce(args.campaign_tag),
        fr_policy_enabled=bool(args.fr_policy),
        fr_policy_state=fr_state,
        fr_windows=fr_windows,
        fr_timezone_default=args.fr_timezone_default,
        fr_max_attempts_30d=args.fr_max_attempts_30d,
        fr_refusal_cooldown_days=args.fr_refusal_cooldown_days,
        fr_holidays=fr_holidays,
    )

    if args.limit is not None:
        prepared = prepared[: int(args.limit)]

    print(f"[INFO] Prepared {len(prepared)} callable lead(s).")
    print(f"[INFO] Blocked {len(blocked)} lead(s) by DNC/policy/validation.")

    if args.out_jsonl:
        out_path = Path(args.out_jsonl).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for item in prepared:
                f.write(json.dumps(item["payload"], ensure_ascii=False) + "\n")
        print(f"[OK] Wrote payload JSONL: {out_path}")

    if args.out_blocked_jsonl:
        out_blocked = Path(args.out_blocked_jsonl).expanduser().resolve()
        out_blocked.parent.mkdir(parents=True, exist_ok=True)
        with open(out_blocked, "w", encoding="utf-8") as f:
            for item in blocked:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[OK] Wrote blocked JSONL: {out_blocked}")

    if prepared:
        print("# Example payload (first call):")
        print(json.dumps(prepared[0]["payload"], indent=2, ensure_ascii=False))
        print()
        print(_make_curl_create_call(base_url, prepared[0]["payload"]))

    # Optional logs for blocked calls even before execution.
    if args.logs_blocked:
        watchdog = _build_watchdog_config(args)
        for item in blocked:
            number = _coalesce(str(item.get("number") or ""))
            lead = item.get("lead") if isinstance(item.get("lead"), dict) else {}
            payload_stub = {
                "from_number": args.from_number.strip(),
                "to_number": number,
                "override_agent_id": args.agent_id.strip(),
            }
            res = _new_call_result(
                mode=mode,
                from_number=args.from_number.strip(),
                to_number=number,
                agent_id=args.agent_id.strip(),
                campaign_tag=_coalesce(args.campaign_tag),
                lead=lead,
                payload=payload_stub,
                watchdog=watchdog,
            )
            policy_eval = item.get("policy") if isinstance(item.get("policy"), dict) else {
                "allowed": False,
                "reasons": item.get("reasons") if isinstance(item.get("reasons"), list) else [],
            }
            _apply_policy_to_result(res, fr_policy_enabled=bool(args.fr_policy), policy_eval=policy_eval)
            _finalize_call_result(res, status=str(item.get("status") or "blocked_policy"), terminal_reason="pre_dial_block")
            res["error"] = "; ".join(str(r.get("code")) for r in res["policy"].get("reasons", []) if isinstance(r, dict))
            _write_call_result_log(res, args.logs_dir)

    if not args.execute:
        print("[DRY RUN] Pass --execute to place calls via Retell.")
        return 0

    api_key = os.environ.get("RETELL_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] RETELL_API_KEY is required for --execute", file=sys.stderr)
        return 2

    watchdog = _build_watchdog_config(args)
    report_paths = _resolve_report_paths(args)

    status_counts: Dict[str, int] = {}
    log_paths: List[str] = []

    for idx, item in enumerate(prepared, start=1):
        payload = item["payload"]
        lead = item["lead"]
        policy_eval = item.get("policy") if isinstance(item.get("policy"), dict) else None

        result = _new_call_result(
            mode=mode,
            from_number=args.from_number.strip(),
            to_number=_coalesce(payload.get("to_number")),
            agent_id=args.agent_id.strip(),
            campaign_tag=_coalesce(args.campaign_tag),
            lead=lead,
            payload=payload,
            watchdog=watchdog,
        )
        _apply_policy_to_result(result, fr_policy_enabled=bool(args.fr_policy), policy_eval=policy_eval)

        result = _execute_call(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            result=result,
            watchdog=watchdog,
            report_paths=report_paths,
        )

        if result["status"] in {"submitted", "completed", "ended_no_report", "timeout"} and result["http"].get("create_call_status") and int(result["http"]["create_call_status"]) < 300:
            if args.fr_policy:
                _record_fr_attempt(fr_state, _coalesce(payload.get("to_number")), _utc_now())

        if args.fr_policy and _is_refusal_outcome(_coalesce(result["analysis"].get("outcome"))):
            _record_fr_refusal(
                fr_state,
                _coalesce(payload.get("to_number")),
                _utc_now(),
                reason=_coalesce(result["analysis"].get("outcome")),
            )

        log_path = _write_call_result_log(result, args.logs_dir)
        log_paths.append(log_path)

        status = str(result.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

        print(f"[{idx}/{len(prepared)}] status={status} call_id={_coalesce(result['call'].get('id')) or '-'}")
        if args.verbose:
            print(json.dumps(result, indent=2, ensure_ascii=False))

        if status == "error" and args.stop_on_error:
            print("[STOP] stop-on-error enabled; stopping batch.")
            break

        if args.sleep_seconds and idx < len(prepared):
            time.sleep(float(args.sleep_seconds))

    if args.fr_policy:
        _save_policy_state(args.fr_policy_state, fr_state)

    print("[SUMMARY] statuses:")
    for key in sorted(status_counts.keys()):
        print(f"- {key}: {status_counts[key]}")
    print(f"[SUMMARY] logs written: {len(log_paths)} in {Path(args.logs_dir).expanduser().resolve()}")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="retell_campaign.py")
    parser.add_argument("--env-file", help="Optional path to .env file.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("generate", help="Generate Retell payloads + talk track + curl templates")
    p_gen.add_argument("--spec", required=True, help="Path to campaign spec JSON (or - for stdin)")
    p_gen.add_argument("--out", required=True, help="Output directory")
    p_gen.add_argument("--agent-id", help="Optional agent id hint for call template")
    p_gen.set_defaults(func=cmd_generate)

    p_create = sub.add_parser("create-agent", help="Create Retell agent (prints curl by default)")
    p_create.add_argument("--agent-json", required=True, help="Path to agent.create.json")
    p_create.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Retell API base URL")
    p_create.add_argument("--execute", action="store_true", help="Actually call Retell API")
    p_create.set_defaults(func=cmd_create_agent)

    p_list = sub.add_parser("list-agents", help="List Retell agents (prints curl by default)")
    p_list.add_argument("--limit", type=int, default=100, help="Max records to return")
    p_list.add_argument("--offset", type=int, default=0, help="Pagination offset")
    p_list.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Retell API base URL")
    p_list.add_argument("--execute", action="store_true", help="Actually call Retell API")
    p_list.set_defaults(func=cmd_list_agents)

    p_one = sub.add_parser("call-one", help="Start one outbound call (prints curl by default)")
    p_one.add_argument("--agent-id", required=True, help="Retell agent id")
    p_one.add_argument("--from-number", required=True, help="Caller number in E.164 (e.g. +331...)")
    p_one.add_argument("--to-number", required=True, help="Recipient number in E.164")
    p_one.add_argument("--mode", default="dynamic", choices=["dynamic", "static"], help="Call mode: dynamic vars or static agent behavior")
    p_one.add_argument("--var", action="append", default=[], help="Dynamic vars key=value (repeatable; used in dynamic mode)")
    p_one.add_argument("--meta", action="append", default=[], help="Metadata key=value (repeatable)")
    p_one.add_argument("--campaign-tag", help="Optional campaign tag added to metadata and logs")
    p_one.add_argument("--timezone", default=DEFAULT_FR_TIMEZONE, help="Lead timezone (used by FR policy gate)")
    p_one.add_argument("--dnc", help="Optional newline-separated suppression list")
    p_one.add_argument("--logs-dir", default=str(_default_logs_dir()), help="Directory to write call result logs")
    _add_wait_report_args(p_one)
    _add_fr_policy_args(p_one)
    p_one.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Retell API base URL")
    p_one.add_argument("--execute", action="store_true", help="Actually call Retell API")
    p_one.set_defaults(func=cmd_call_one)

    p_batch = sub.add_parser("start-calls", help="Start outbound calls from a leads CSV")
    p_batch.add_argument("--agent-id", required=True, help="Retell agent id")
    p_batch.add_argument("--from-number", required=True, help="Caller number in E.164")
    p_batch.add_argument("--leads", required=True, help="Leads CSV path")
    p_batch.add_argument("--dnc", help="Optional newline-separated suppression list")
    p_batch.add_argument("--campaign-tag", help="Optional metadata campaign tag")
    p_batch.add_argument("--mode", default="dynamic", choices=["dynamic", "static"], help="Call mode: dynamic vars or static agent behavior")
    p_batch.add_argument("--var", action="append", default=[], help="Static vars key=value for all calls (dynamic mode only)")
    p_batch.add_argument("--limit", type=int, help="Limit number of calls")
    p_batch.add_argument("--sleep-seconds", type=float, default=0.0, help="Delay between calls when executing")
    p_batch.add_argument("--out-jsonl", help="Write callable payloads to JSONL")
    p_batch.add_argument("--out-blocked-jsonl", help="Write blocked leads/reasons to JSONL")
    p_batch.add_argument("--logs-dir", default=str(_default_logs_dir()), help="Directory to write call result logs")
    p_batch.add_argument("--logs-blocked", action="store_true", help="Also log blocked leads as result JSON files")
    p_batch.add_argument("--stop-on-error", action="store_true", help="Stop batch on first API error")
    p_batch.add_argument("--verbose", action="store_true", help="Print full result JSON for each executed call")
    _add_wait_report_args(p_batch)
    _add_fr_policy_args(p_batch)
    p_batch.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Retell API base URL")
    p_batch.add_argument("--execute", action="store_true", help="Actually call Retell API")
    p_batch.set_defaults(func=cmd_start_calls)

    args = parser.parse_args(argv)
    _load_default_env_files(explicit_env_file=args.env_file)

    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
