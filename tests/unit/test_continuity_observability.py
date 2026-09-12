from __future__ import annotations

import asyncio
import logging

import pytest

from app.core.balancer import AccountState
from app.core.utils.request_id import reset_request_id, set_request_id
from app.db.models import AccountStatus
from app.modules.proxy.continuity_diagnostics import correlation_hash, record_candidate_states
from app.modules.proxy.replay_safety import responses_payload_is_account_neutral_fresh_replay

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ({}, "accepted"),
        ({"reasoning": {"context": "SECRET"}}, "reasoning_controls"),
        ({"SECRET": "SECRET"}, "unknown_payload_field"),
        ({"previous_response_id": "SECRET"}, "previous_response_bound"),
        ({"tools": [{"type": "SECRET"}]}, "tool_declarations"),
        ({"input": [{"type": "compaction", "encrypted_content": "SECRET"}]}, "input_item_type"),
        (
            {"input": [{"type": "function_call_output", "call_id": "SECRET", "output": "SECRET"}]},
            "input_tool_output_unmatched_or_invalid",
        ),
    ],
)
def test_classifier_records_actual_gate_without_payload_or_identifier_values(caplog, extra, reason):
    caplog.set_level(logging.INFO, logger="app.modules.proxy.continuity")
    token = set_request_id("SECRET-request")
    try:
        accepted = responses_payload_is_account_neutral_fresh_replay(
            {"input": [{"role": "user", "content": "SECRET"}], **extra}
        )
    finally:
        reset_request_id(token)
    assert accepted is (reason == "accepted")
    assert f"reason={reason}" in caplog.text
    assert f"request={correlation_hash('SECRET-request')}" in caplog.text
    assert "SECRET" not in caplog.text
    assert len(caplog.records) == 1


async def test_interleaved_classifier_calls_keep_request_correlation_isolated(caplog):
    caplog.set_level(logging.INFO, logger="app.modules.proxy.continuity")

    async def classify(request, extra):
        token = set_request_id(request)
        try:
            await asyncio.sleep(0)
            responses_payload_is_account_neutral_fresh_replay(extra)
        finally:
            reset_request_id(token)

    await asyncio.gather(classify("one", {}), classify("two", {"previous_response_id": "private"}))
    assert any(
        f"request={correlation_hash('one')}" in r.message and "reason=accepted" in r.message for r in caplog.records
    )
    assert any(
        f"request={correlation_hash('two')}" in r.message and "reason=previous_response_bound" in r.message
        for r in caplog.records
    )


def test_candidate_snapshot_is_bounded_and_does_not_log_freeform_account_fields(caplog):
    caplog.set_level(logging.INFO, logger="app.modules.proxy.continuity")
    states = [
        AccountState(
            account_id=f"SECRET-{i}",
            status=AccountStatus.RATE_LIMITED,
            used_percent=100,
            reset_at=1234,
            deactivation_reason="SECRET",
        )
        for i in range(100)
    ]
    record_candidate_states(states)
    assert len(caplog.records) == 65
    assert "total=100 omitted=36" in caplog.text
    assert "primary_used=100" in caplog.text
    assert "SECRET" not in caplog.text


def test_disabled_logging_does_not_change_classification(caplog):
    caplog.set_level(logging.WARNING, logger="app.modules.proxy.continuity")
    assert responses_payload_is_account_neutral_fresh_replay({"input": "private"})
    assert not caplog.records


@pytest.mark.parametrize("json_log", [False, True])
def test_timeline_export_preserves_actual_events_and_rejects_unknown_values(caplog, json_log):
    import json

    from scripts.continuity_timeline import parse_event

    caplog.set_level(logging.INFO, logger="app.modules.proxy.continuity")
    responses_payload_is_account_neutral_fresh_replay({"reasoning": {"context": "SECRET"}})
    message = caplog.records[-1].message
    line = json.dumps({"message": message, "credentials": "SECRET"}) if json_log else message
    event = parse_event(line)
    assert event is not None
    assert event["reason"] == "reasoning_controls"
    assert int(event["observed_at_ns"]) > 0
    assert "SECRET" not in json.dumps(event)
    poisoned = parse_event(message + " reason=SECRET request=SECRET extra=SECRET")
    assert "SECRET" not in json.dumps(poisoned)


def test_timeline_ignores_ordinary_logs_and_unknown_schemas():
    from scripts.continuity_timeline import parse_event

    assert parse_event('upstream_error message="private"') is None
    assert parse_event("observed_at_ns=1 monotonic_ns=2 process=3 continuity_decision version=2 reason=private") is None
