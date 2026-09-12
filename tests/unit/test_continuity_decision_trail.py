"""Observe real classifier decisions and final warnings without setting proxy state."""

import asyncio
import logging
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.core.utils.request_id import (
    reset_request_id,
    reset_request_scope_id,
    set_request_id,
    set_request_scope_id,
)
from app.modules.proxy._service.observability import _record_continuity_fail_closed
from app.modules.proxy.continuity_diagnostics import initialize_replay_observations, record_continuity_decision
from app.modules.proxy.replay_safety import responses_payload_is_account_neutral_fresh_replay

pytestmark = pytest.mark.unit


@contextmanager
def request_scope(request="private-request", scope="auto"):
    r = set_request_id(request)
    s = set_request_scope_id(str(uuid4()) if scope == "auto" else scope)
    try:
        yield
    finally:
        reset_request_scope_id(s)
        reset_request_id(r)


def warn():
    _record_continuity_fail_closed(
        surface="websocket_connect",
        reason="owner_account_unavailable",
        previous_response_id="private-response",
        upstream_error_code="no_accounts",
    )


def test_warning_retains_projection_sequence_with_info_disabled(caplog):
    caplog.set_level(logging.WARNING)
    with request_scope():
        assert not responses_payload_is_account_neutral_fresh_replay({"previous_response_id": "private"})
        assert responses_payload_is_account_neutral_fresh_replay({"input": "private"})
        warn()
    assert len(caplog.records) == 1
    assert (
        "observed_replay_decisions=payload_portability:previous_response_bound,payload_portability:accepted"
        in caplog.text
    )
    assert "replay_decisions_omitted=0" in caplog.text
    assert "request=sha256:" in caplog.text and "scope=sha256:" in caplog.text
    assert "private" not in caplog.text


@pytest.mark.parametrize(
    "request_name,scope", [("other", "private-scope"), ("private-request", "other"), ("private-request", None)]
)
def test_absent_or_changed_scope_never_reuses_decisions(caplog, request_name, scope):
    with request_scope(scope="private-scope"):
        record_continuity_decision(stage="http_ingress", reason="client_anchored")
        responses_payload_is_account_neutral_fresh_replay({"previous_response_id": "private"})
        with request_scope(request_name, scope):
            warn()
    assert "observed_replay_decisions=not_observed" in caplog.text


def test_bounded_allowlisted_trail_and_ingress_reset(caplog):
    with request_scope():
        for _ in range(10):
            record_continuity_decision(stage="private", reason="private")
        warn()
        assert "replay_decisions_omitted=2" in caplog.text
        assert caplog.text.count("unknown:unknown") == 8
        assert "private" not in caplog.text
        caplog.clear()
        record_continuity_decision(stage="http_ingress", reason="client_unanchored")
        warn()
        assert "observed_replay_decisions=http_ingress:client_unanchored" in caplog.text
        assert "replay_decisions_omitted=0" in caplog.text


async def test_child_tasks_do_not_mix_decisions_or_write_back_to_parent(caplog):
    async def check(extra):
        responses_payload_is_account_neutral_fresh_replay(extra)
        await asyncio.sleep(0)
        warn()

    with request_scope():
        await asyncio.gather(check({"previous_response_id": "private"}), check({"input": "private"}))
        warn()
    warnings = [r.message for r in caplog.records if "continuity_fail_closed" in r.message]
    assert len(warnings) == 3
    assert "observed_replay_decisions=payload_portability:previous_response_bound " in warnings[0]
    assert "observed_replay_decisions=payload_portability:accepted " in warnings[1]
    assert "observed_replay_decisions=not_observed " in warnings[2]


async def test_initialized_probe_collector_reaches_parent_but_not_other_requests(caplog):
    with request_scope():
        initialize_replay_observations()

        async def check():
            responses_payload_is_account_neutral_fresh_replay({"previous_response_id": "private"})
            with request_scope():
                responses_payload_is_account_neutral_fresh_replay({"input": "private"})

        await asyncio.create_task(check())
        warn()
    assert "observed_replay_decisions=payload_portability:previous_response_bound " in caplog.text
    assert "payload_portability:accepted" not in caplog.text
