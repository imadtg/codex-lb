from __future__ import annotations

import json
import logging
from dataclasses import replace

import pytest

from app.core.openai.requests import ResponsesRequest
from app.core.types import JsonValue
from app.db.models import HttpBridgeSessionState
from app.modules.proxy import service as proxy_service
from app.modules.proxy._service import observability as observability_module
from app.modules.proxy._service.http_bridge import helpers as http_bridge_helpers
from app.modules.proxy._service.http_bridge import streaming as http_bridge_streaming_module
from app.modules.proxy._service.response_create import (
    _fingerprint_input_items,
    _input_context_prefix_fingerprints,
    _stored_context_prefix_fingerprints,
)
from app.modules.proxy.durable_bridge_coordinator import DurableBridgeLookup

pytestmark = pytest.mark.unit

_STORED_ITEMS: list[JsonValue] = [
    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "first"}]},
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "answer"}]},
]
_FRESH_ITEM: JsonValue = {
    "type": "message",
    "role": "user",
    "content": [{"type": "input_text", "text": "second"}],
}


def _payload(input_value: object) -> ResponsesRequest:
    return ResponsesRequest.model_validate({"model": "gpt-5.4", "instructions": "be brief", "input": input_value})


def _lookup(
    *,
    latest_input_item_count: int | None,
    latest_input_full_fingerprint: str | None,
) -> DurableBridgeLookup:
    return DurableBridgeLookup(
        session_id="session-1",
        canonical_kind="thread_header",
        canonical_key="thread-1",
        api_key_scope="global",
        account_id="account-1",
        owner_instance_id="codex-lb",
        owner_epoch=1,
        lease_expires_at=None,
        state=HttpBridgeSessionState.ACTIVE,
        latest_turn_state=None,
        latest_response_id="resp-1",
        latest_input_item_count=latest_input_item_count,
        latest_input_full_fingerprint=latest_input_full_fingerprint,
    )


def _matching_lookup() -> DurableBridgeLookup:
    return _lookup(
        latest_input_item_count=len(_STORED_ITEMS),
        latest_input_full_fingerprint=_fingerprint_input_items(list(_STORED_ITEMS)),
    )


def _full_resend_payload() -> ResponsesRequest:
    return _payload([*_STORED_ITEMS, _FRESH_ITEM])


def _anchor_rejection(
    payload: ResponsesRequest,
    lookup: DurableBridgeLookup,
    *,
    payload_looks_like_full_resend: bool = True,
) -> str | None:
    return http_bridge_streaming_module._durable_full_resend_anchor_rejection(
        payload,
        lookup,
        payload_looks_like_full_resend=payload_looks_like_full_resend,
    )


@pytest.mark.parametrize(
    "case",
    [
        "portable",
        "changed_prefix",
        "duplicate",
        "missing_tool",
        "explicit_anchor",
        "historical_developer",
        "file_bound",
    ],
)
def test_history_discovery_requires_unique_complete_context(case: str) -> None:
    prefix: list[JsonValue] = [_STORED_ITEMS[0]]
    if case == "historical_developer":
        prefix.insert(0, {"type": "additional_tools", "role": "developer", "tools": []})
        prefix.append(
            {
                "type": "message",
                "id": "msg_historical",
                "role": "developer",
                "content": [{"type": "input_text", "text": "retained settings"}],
                "internal_chat_message_metadata_passthrough": {"turn_id": "turn_prior"},
            }
        )
    payload = _payload(
        [
            *prefix,
            {
                "role": "assistant",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": "prior answer"}],
            },
            _FRESH_ITEM,
        ]
    )
    candidate = _lookup(
        latest_input_item_count=len(prefix),
        latest_input_full_fingerprint=_fingerprint_input_items(prefix),
    )
    candidates = [candidate]
    if case == "changed_prefix":
        candidate = replace(candidate, latest_input_full_fingerprint="different-prefix")
        candidates = [candidate]
    elif case == "duplicate":
        candidates.append(replace(candidate, session_id="other-session", account_id="other-owner"))
    elif case == "missing_tool":
        candidates = [replace(candidate, latest_pending_tool_calls={"call-missing": "custom_tool_call_output"})]
    elif case == "explicit_anchor":
        payload = payload.model_copy(update={"previous_response_id": "resp-explicit"})
    elif case == "file_bound":
        assert isinstance(payload.input, list)
        payload = payload.model_copy(
            update={
                "input": [
                    *payload.input[:-1],
                    {"role": "user", "content": [{"type": "input_file", "file_id": "file-owner-bound"}]},
                ]
            }
        )
    result = http_bridge_streaming_module._unique_portable_history_source(payload, candidates)
    if case in {"portable", "historical_developer"}:
        assert result == candidate
    else:
        assert result is None


def test_history_discovery_fingerprints_match_canonical_prefixes_without_mutation() -> None:
    call: dict[str, JsonValue] = {
        "type": "function_call",
        "call_id": "call-1",
        "name": "tool",
        "namespace": "tools",
        "arguments": "{}",
    }
    items: list[JsonValue] = [
        _STORED_ITEMS[0],
        call,
        {"type": "function_call_output", "call_id": "call-1", "output": "unicode café"},
        _FRESH_ITEM,
    ]
    normalized = [items[0], {key: value for key, value in call.items() if key != "namespace"}, *items[2:]]
    expected = {
        _fingerprint_input_items(representation[:count])
        for representation in (items, normalized)
        for count in range(1, len(items))
    }
    assert set(_input_context_prefix_fingerprints(items)) == expected
    assert call["namespace"] == "tools"
    assert _input_context_prefix_fingerprints([]) == []
    assert _input_context_prefix_fingerprints([_FRESH_ITEM]) == []


@pytest.mark.parametrize("change", ["derived_cache", "client_cache", "scope", "api_key", "input", "model"])
def test_portable_history_operation_identity_survives_restart_without_merging_requests(change: str) -> None:
    frame: dict[str, JsonValue] = {
        "type": "response.create",
        "model": "gpt-6.1-sol",
        "input": _STORED_ITEMS,
        "prompt_cache_key": "cache-a",
    }

    def fingerprint(frame: dict[str, JsonValue], *, scope: str = "thread-a", api_key: str = "key-a") -> str:
        return http_bridge_streaming_module._portable_history_operation_fingerprint(
            request_text=json.dumps(frame),
            api_key_scope=api_key,
            client_scope=scope,
            preserve_prompt_cache_key=change == "client_cache",
        )

    original = fingerprint(frame)
    if change in {"derived_cache", "client_cache"}:
        changed = fingerprint({**frame, "prompt_cache_key": "cache-b"})
    elif change == "scope":
        changed = fingerprint(frame, scope="thread-b")
    elif change == "api_key":
        changed = fingerprint(frame, api_key="key-b")
    elif change == "input":
        changed = fingerprint({**frame, "input": [*_STORED_ITEMS, _FRESH_ITEM]})
    else:
        changed = fingerprint({**frame, "model": "gpt-6-astra"})
    assert (original == changed) == (change == "derived_cache")


def test_matching_full_resend_has_no_anchor_rejection() -> None:
    assert _anchor_rejection(_full_resend_payload(), _matching_lookup()) is None


def test_non_full_resend_payload_is_reported_distinctly() -> None:
    # The body carries only the new turn, so there is no history to move.
    assert (
        _anchor_rejection(
            _payload([_FRESH_ITEM]),
            _matching_lookup(),
            payload_looks_like_full_resend=False,
        )
        == "payload_not_full_resend"
    )


def test_row_without_stored_count_is_reported_distinctly() -> None:
    # A durable row written before the anchor metadata existed, or one whose
    # owner was pinned from the request-log index.
    assert (
        _anchor_rejection(
            _full_resend_payload(),
            _lookup(latest_input_item_count=None, latest_input_full_fingerprint="deadbeef"),
        )
        == "anchor_metadata_missing"
    )


def test_diverged_prefix_is_reported_distinctly() -> None:
    assert (
        _anchor_rejection(
            _full_resend_payload(),
            _lookup(
                latest_input_item_count=len(_STORED_ITEMS),
                latest_input_full_fingerprint="0" * 64,
            ),
        )
        == "prefix_fingerprint_mismatch"
    )


def test_missing_fingerprint_is_a_prefix_mismatch() -> None:
    assert (
        _anchor_rejection(
            _full_resend_payload(),
            _lookup(latest_input_item_count=len(_STORED_ITEMS), latest_input_full_fingerprint=None),
        )
        == "prefix_fingerprint_mismatch"
    )


def test_stored_prefix_without_a_fresh_suffix_is_a_prefix_mismatch() -> None:
    # The stored prefix consumes the whole body, so nothing new was sent.
    assert _anchor_rejection(_payload(list(_STORED_ITEMS)), _matching_lookup()) == "prefix_fingerprint_mismatch"


def test_string_input_refuses_on_the_prefix_proof() -> None:
    # A non-list body cannot match a stored prefix, so the prefix proof always
    # refuses first. ``input_not_itemized`` therefore stays a guard rather than
    # an observable outcome: it is only reachable if some future caller admits
    # a non-list body past the prefix proof.
    assert (
        _anchor_rejection(
            _payload("plain string input"),
            _matching_lookup(),
            payload_looks_like_full_resend=True,
        )
        == "prefix_fingerprint_mismatch"
    )


def test_every_anchor_rejection_is_in_the_closed_set() -> None:
    matching = _matching_lookup()
    observed = {
        _anchor_rejection(_payload([_FRESH_ITEM]), matching, payload_looks_like_full_resend=False),
        _anchor_rejection(
            _full_resend_payload(),
            _lookup(latest_input_item_count=None, latest_input_full_fingerprint="deadbeef"),
        ),
        _anchor_rejection(
            _full_resend_payload(),
            _lookup(latest_input_item_count=len(_STORED_ITEMS), latest_input_full_fingerprint="0" * 64),
        ),
    }
    assert observed <= http_bridge_streaming_module.ACCOUNT_NEUTRAL_REPLAY_REJECTIONS
    # The three causes that used to collapse into one ``False``.
    assert len(observed) == 3


def test_closed_reason_set_matches_the_literal() -> None:
    assert http_bridge_streaming_module.ACCOUNT_NEUTRAL_REPLAY_REJECTIONS == frozenset(
        {
            "file_bound",
            "no_durable_lookup",
            "payload_not_full_resend",
            "anchor_metadata_missing",
            "prefix_fingerprint_mismatch",
            "input_not_itemized",
            "missing_prior_output",
            "account_scoped_input",
        }
    )


class _RecordingCounter:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self.increments = 0

    def labels(self, **kwargs: str) -> "_RecordingCounter":
        self.calls.append(kwargs)
        return self

    def inc(self, amount: float = 1) -> None:
        self.increments += 1


def test_replay_rejection_counter_uses_the_closed_label_set(monkeypatch: pytest.MonkeyPatch) -> None:
    counter = _RecordingCounter()
    monkeypatch.setattr(proxy_service, "PROMETHEUS_AVAILABLE", True)
    monkeypatch.setattr(proxy_service, "continuity_replay_rejected_total", counter, raising=False)

    observability_module._record_continuity_replay_rejected(
        surface="http_bridge",
        reason="no_durable_lookup",
    )

    assert counter.calls == [{"surface": "http_bridge", "reason": "no_durable_lookup"}]
    assert counter.increments == 1


def test_replay_rejection_recorder_no_ops_without_prometheus(monkeypatch: pytest.MonkeyPatch) -> None:
    counter = _RecordingCounter()
    monkeypatch.setattr(proxy_service, "PROMETHEUS_AVAILABLE", False)
    monkeypatch.setattr(proxy_service, "continuity_replay_rejected_total", counter, raising=False)

    observability_module._record_continuity_replay_rejected(surface="http_bridge", reason="file_bound")

    assert counter.calls == []
    assert counter.increments == 0


def test_replay_rejection_event_is_logged_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.modules.proxy.service")
    key = proxy_service._HTTPBridgeSessionKey("thread_header", "thread-1", None)

    http_bridge_helpers._log_http_bridge_event(
        "owner_unavailable_replay_rejected",
        key,
        account_id="account-1",
        model="gpt-5.4",
        detail="reason=no_durable_lookup",
        cache_key_family="thread_header",
        owner_check_applied=True,
    )

    records = [record for record in caplog.records if "owner_unavailable_replay_rejected" in record.getMessage()]
    assert len(records) == 1
    # A refusal nobody can find in the logs is the failure this change exists
    # to fix, so the level is part of the contract.
    assert records[0].levelno == logging.WARNING
    assert "reason=no_durable_lookup" in records[0].getMessage()
    assert "account_id=account-1" in records[0].getMessage()
    assert "key_strength=hard" in records[0].getMessage()


def test_lookup_field_rename_fails_here() -> None:
    # The anchor proof reads only these two lookup fields, so a rename must
    # fail here rather than silently degrade every refusal to one reason.
    lookup = replace(_matching_lookup(), latest_input_item_count=None)
    assert _anchor_rejection(_full_resend_payload(), lookup) == "anchor_metadata_missing"


def test_prefix_mismatch_logs_only_bounded_proof_facts(caplog: pytest.LogCaptureFixture) -> None:
    secret = "private-context-never-log"
    items: list[JsonValue] = [{"type": "message", "role": "user", "content": secret}, _FRESH_ITEM]
    with caplog.at_level(logging.WARNING):
        assert _anchor_rejection(_payload(items), _matching_lookup()) == "prefix_fingerprint_mismatch"
    assert secret not in caplog.text
    assert "input_count=2 stored_count=2" in caplog.text
    assert "input_longer_than_stored=False" in caplog.text
    assert f"stored_prefix_sha256={_fingerprint_input_items(_STORED_ITEMS)[:12]}" in caplog.text
    assert f"incoming_prefix_sha256={_fingerprint_input_items(items)[:12]}" in caplog.text
    assert "client_anchored=False" in caplog.text


def test_prefix_diagnostic_matches_proof_normalization_without_mutating_input() -> None:
    call: JsonValue = {
        "type": "function_call",
        "name": "run",
        "call_id": "call-private",
        "namespace": "functions",
        "arguments": "{}",
    }
    items: list[JsonValue] = [call, _FRESH_ITEM]
    stripped: JsonValue = {"type": "function_call", "name": "run", "call_id": "call-private", "arguments": "{}"}
    assert _stored_context_prefix_fingerprints(items, stored_count=1) == (
        _fingerprint_input_items([call])[:12],
        _fingerprint_input_items([stripped])[:12],
    )
    assert isinstance(call, dict) and call["namespace"] == "functions"


@pytest.mark.parametrize("input_value,stored_count", [("text", 2), ([], 0), ([], -1)])
def test_prefix_diagnostic_handles_nonpositive_or_unitemized_context(input_value: JsonValue, stored_count: int) -> None:
    assert _stored_context_prefix_fingerprints(input_value, stored_count=stored_count) == (None, None)
