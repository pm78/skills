from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta, time as dtime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "retell_campaign.py"
SPEC = importlib.util.spec_from_file_location("retell_campaign", SCRIPT_PATH)
assert SPEC and SPEC.loader
retell_campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retell_campaign)


def test_lead_to_call_payload_dynamic_includes_dynamic_vars_and_metadata() -> None:
    lead = {
        "phone_e164": "+33611111111",
        "first_name": "Alice",
        "last_name": "Durand",
        "company": "ACME",
        "title": "DRH",
        "email": "alice@example.com",
        "timezone": "Europe/Paris",
    }
    payload = retell_campaign._lead_to_call_payload(
        from_number="+33102030405",
        agent_id="agent_123",
        lead=lead,
        static_vars={"segment": "pilot"},
        campaign_tag="fr-b2b",
        mode="dynamic",
    )

    assert payload["from_number"] == "+33102030405"
    assert payload["to_number"] == "+33611111111"
    assert payload["override_agent_id"] == "agent_123"
    assert payload["retell_llm_dynamic_variables"]["first_name"] == "Alice"
    assert payload["retell_llm_dynamic_variables"]["segment"] == "pilot"
    assert payload["metadata"]["campaign"] == "fr-b2b"


def test_lead_to_call_payload_static_excludes_dynamic_vars() -> None:
    lead = {
        "phone_e164": "+33622222222",
        "first_name": "Bob",
        "company": "ACME",
        "timezone": "Europe/Paris",
    }
    payload = retell_campaign._lead_to_call_payload(
        from_number="+33102030405",
        agent_id="agent_123",
        lead=lead,
        static_vars={"segment": "pilot"},
        campaign_tag="fr-b2b",
        mode="static",
    )

    assert payload["from_number"] == "+33102030405"
    assert payload["to_number"] == "+33622222222"
    assert "retell_llm_dynamic_variables" not in payload
    assert payload["metadata"]["campaign"] == "fr-b2b"


def test_prepare_batch_calls_filters_dnc() -> None:
    leads = [
        {"phone_e164": "+33600000000", "timezone": "Europe/Paris"},
        {"phone_e164": "+33600000001", "timezone": "Europe/Paris"},
    ]

    prepared, blocked = retell_campaign._prepare_batch_calls(
        leads=leads,
        dnc={"+33600000001"},
        from_number="+33102030405",
        agent_id="agent_123",
        mode="dynamic",
        static_vars={},
        campaign_tag="test",
        fr_policy_enabled=False,
        fr_policy_state=retell_campaign._default_policy_state(),
        fr_windows=[],
        fr_timezone_default="Europe/Paris",
        fr_max_attempts_30d=4,
        fr_refusal_cooldown_days=60,
        fr_holidays=set(),
        now_utc=datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc),
    )

    assert len(prepared) == 1
    assert prepared[0]["payload"]["to_number"] == "+33600000000"
    assert len(blocked) == 1
    assert blocked[0]["status"] == "blocked_dnc"


def test_evaluate_fr_policy_blocks_outside_time_window() -> None:
    state = retell_campaign._default_policy_state()
    windows = retell_campaign._parse_fr_time_windows("10:00-13:00,14:00-20:00")

    # Monday 09:30 local Europe/Paris in winter is 08:30 UTC.
    now_utc = datetime(2026, 2, 2, 8, 30, tzinfo=timezone.utc)
    result = retell_campaign._evaluate_fr_policy(
        number="+33600000000",
        state=state,
        now_utc=now_utc,
        timezone_name="Europe/Paris",
        default_timezone_name="Europe/Paris",
        windows=windows,
        max_attempts_30d=4,
        refusal_cooldown_days=60,
        holidays=set(),
    )

    assert result["allowed"] is False
    assert any(r["code"] == "time_window_block" for r in result["reasons"])


def test_evaluate_fr_policy_blocks_attempt_limit_30d() -> None:
    state = retell_campaign._default_policy_state()
    number = "+33600000000"
    now_utc = datetime(2026, 2, 2, 11, 0, tzinfo=timezone.utc)

    for i in range(4):
        retell_campaign._record_fr_attempt(state, number, now_utc - timedelta(days=i + 1))

    result = retell_campaign._evaluate_fr_policy(
        number=number,
        state=state,
        now_utc=now_utc,
        timezone_name="Europe/Paris",
        default_timezone_name="Europe/Paris",
        windows=[(dtime(10, 0), dtime(20, 0))],
        max_attempts_30d=4,
        refusal_cooldown_days=60,
        holidays=set(),
    )

    assert result["allowed"] is False
    assert any(r["code"] == "attempt_limit_block" for r in result["reasons"])


def test_evaluate_fr_policy_blocks_refusal_cooldown() -> None:
    state = retell_campaign._default_policy_state()
    number = "+33600000000"
    now_utc = datetime(2026, 2, 2, 11, 0, tzinfo=timezone.utc)

    retell_campaign._record_fr_refusal(state, number, now_utc - timedelta(days=10), reason="dnc_requested")

    result = retell_campaign._evaluate_fr_policy(
        number=number,
        state=state,
        now_utc=now_utc,
        timezone_name="Europe/Paris",
        default_timezone_name="Europe/Paris",
        windows=[(dtime(10, 0), dtime(20, 0))],
        max_attempts_30d=4,
        refusal_cooldown_days=60,
        holidays=set(),
    )

    assert result["allowed"] is False
    assert any(r["code"] == "refusal_cooldown_block" for r in result["reasons"])


def test_wait_for_call_report_times_out_on_inactivity() -> None:
    def fetch_report() -> dict:
        return {"ok": False, "error": "HTTP 404"}

    outcome = retell_campaign._wait_for_call_report(
        call_id="call_test",
        fetch_report_fn=fetch_report,
        poll_interval_seconds=0.01,
        inactivity_timeout_seconds=1,
        post_end_timeout_seconds=1,
        call_timeout_seconds=5,
    )

    assert outcome["status"] == "timeout"
    assert outcome["terminal_reason"] == "inactivity_timeout"


def test_wait_for_call_report_completes_when_report_present() -> None:
    calls = {"count": 0}

    def fetch_report() -> dict:
        calls["count"] += 1
        if calls["count"] < 2:
            return {
                "ok": True,
                "status": 200,
                "path": "/get-phone-call/call_test",
                "body": "{}",
                "record": {"status": "in_progress", "id": "call_test"},
            }
        return {
            "ok": True,
            "status": 200,
            "path": "/get-phone-call/call_test",
            "body": "{}",
            "record": {
                "status": "ended",
                "id": "call_test",
                "summary": "Meeting booked",
                "outcome": "booked_meeting",
                "duration_seconds": 95,
            },
        }

    outcome = retell_campaign._wait_for_call_report(
        call_id="call_test",
        fetch_report_fn=fetch_report,
        poll_interval_seconds=0.01,
        inactivity_timeout_seconds=2,
        post_end_timeout_seconds=1,
        call_timeout_seconds=5,
    )

    assert outcome["status"] == "completed"
    fields = outcome["report_fields"]
    assert fields["summary"] == "Meeting booked"
    assert fields["outcome"] == "booked_meeting"
