from __future__ import annotations

import json
import sys

import pytest

from scripts.diagnose_continuity import diagnose

pytestmark = pytest.mark.unit


def message(role="user", text="private text"):
    return {"role": role, "content": [{"type": "input_text", "text": text}]}


@pytest.mark.parametrize(
    ("extra", "accepted"),
    [
        ({}, True),
        ({"previous_response_id": "resp_private"}, False),
        ({"conversation": "conv_private"}, False),
        ({"tools": [{"type": "function", "name": "shell", "parameters": {"type": "object"}}]}, True),
        ({"tools": [{"type": "namespace", "name": "functions", "tools": []}]}, True),
        ({"tools": [{"type": "file_search", "vector_store_ids": ["vs_private"]}]}, False),
        ({"tools": [{"type": "computer", "environment": "browser"}]}, False),
        ({"tools": [{"type": "web_search"}]}, True),
        ({"new_control": "unknown-private-value"}, False),
    ],
)
def test_payload_boundaries(extra, accepted):
    payload = {"model": "gpt-6-astra", "input": [message()], **extra}
    report = diagnose(payload)
    assert report["raw"]["account_neutral"] is accepted
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize(
    ("items", "raw", "projected"),
    [
        ([message()], True, True),
        ([message(), {"type": "reasoning", "encrypted_content": "cipher-private", "summary": []}], False, True),
        ([message(), {"type": "compaction", "encrypted_content": "cipher-private"}], False, False),
        ([message(), {"type": "input_image", "image_url": "data:image/png;base64,eA=="}], True, True),
        ([message(), {"type": "input_file", "file_id": "file_private"}], False, False),
        ([message(), {"type": "function_call_output", "call_id": "orphan", "output": "private"}], False, False),
        (
            [message(), {"type": "function_call", "call_id": "pending", "name": "shell", "arguments": "{}"}],
            False,
            False,
        ),
        (
            [
                message(),
                {"type": "function_call", "call_id": "done", "name": "shell", "arguments": "{}"},
                {"type": "function_call_output", "call_id": "done", "output": "private"},
            ],
            True,
            True,
        ),
    ],
)
def test_input_boundaries(items, raw, projected):
    report = diagnose({"model": "gpt-6-astra", "input": items}, stored_count=1)
    assert report["raw"]["account_neutral"] is raw
    assert report["projected"]["account_neutral"] is projected
    assert "private" not in json.dumps(report)


def test_diagnostic_restores_trace_and_never_emits_unknown_input_keys():
    sentinel = "SECRET_KEY_AND_VALUE_12345"
    previous = sys.gettrace()
    report = diagnose({"model": "gpt-6-astra", "input": [message(text=sentinel)], sentinel: sentinel})
    assert sys.gettrace() is previous
    assert sentinel not in json.dumps(report)
    assert report["raw"]["account_neutral"] is False
    assert report["raw"]["rejection_reason"] == "unknown_payload_field"


@pytest.mark.parametrize(
    "child",
    [
        {"type": "function", "name": "read", "parameters": {}, "defer_loading": True},
        {"type": "custom", "name": "patch", "format": {"type": "text"}, "defer_loading": False},
    ],
)
def test_portable_namespace(child):
    payload = {
        "input": [message()],
        "tools": [{"type": "namespace", "name": "functions", "description": "", "tools": [child]}],
    }
    assert diagnose(payload)["raw"]["account_neutral"]


@pytest.mark.parametrize(
    "change",
    [
        {"tools": [{"type": "file_search", "vector_store_ids": ["vs_private"]}]},
        {"tools": [{"type": "namespace", "name": "nested", "tools": []}]},
        {"tools": [{"type": "function", "name": "read", "defer_loading": "true"}]},
        {"tools": [{"type": "function", "name": "read", "future_resource": "private"}]},
        {"name": ""},
        {"name": []},
        {"description": {}},
        {"tools": None},
        {"future_resource": "private"},
    ],
)
def test_namespace_validation_stays_closed(change):
    tool = {"type": "namespace", "name": "functions", "tools": [], **change}
    assert not diagnose({"input": [message()], "tools": [tool]})["raw"]["account_neutral"]


@pytest.mark.parametrize("kind", ["function_call", "custom_tool_call"])
@pytest.mark.parametrize("namespace,accepted", [("functions", True), (None, True), ("", False), ({}, False)])
def test_namespaced_completed_tool_history(kind, namespace, accepted):
    call = {"type": kind, "name": "read", "namespace": namespace, "call_id": "synthetic"}
    call["arguments" if kind == "function_call" else "input"] = "{}"
    output = {"type": kind + "_output", "call_id": "synthetic", "output": "done"}
    assert diagnose({"input": [message(), call, output]})["raw"]["account_neutral"] is accepted


@pytest.mark.parametrize(
    "context,accepted",
    [(None, True), ("auto", True), ("current_turn", True), ("all_turns", True), ("unknown", False), ({}, False)],
)
def test_reasoning_context(context, accepted):
    assert (
        diagnose({"input": [message()], "reasoning": {"effort": "high", "context": context}})["raw"]["account_neutral"]
        is accepted
    )


@pytest.mark.parametrize("key", ["session_id", "thread_id", "turn_id", "parent_turn_id", "root_turn_id"])
@pytest.mark.parametrize("value,accepted", [("synthetic", True), ("", False), ({}, False)])
def test_correlation_metadata(key, value, accepted):
    assert diagnose({"input": [message()], "client_metadata": {key: value}})["raw"]["account_neutral"] is accepted


def test_turn_state_metadata_is_still_account_owned():
    assert not diagnose({"input": [message()], "client_metadata": {"x-codex-turn-state": "synthetic"}})["raw"][
        "account_neutral"
    ]


@pytest.mark.parametrize("changed_field", [None, "arguments", "call_id", "name", "output"])
def test_forwarded_namespace_prefix_preserves_other_history_fields(changed_field):
    from copy import deepcopy

    from app.modules.proxy.service import _fingerprint_input_items, _input_prefix_matches_stored_context

    stored = [
        message(),
        {"type": "function_call", "name": "read", "call_id": "done", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "done", "output": "original"},
    ]
    incoming = deepcopy(stored)
    incoming[1]["namespace"] = "functions"
    if changed_field:
        incoming[2 if changed_field == "output" else 1][changed_field] = "changed"
    incoming.append(message(text="continue"))
    before = deepcopy(incoming)
    assert _input_prefix_matches_stored_context(
        incoming, stored_count=len(stored), stored_fingerprint=_fingerprint_input_items(stored)
    ) is (changed_field is None)
    assert incoming == before


def test_complete_tool_manifest_followed_by_user_input_must_recover():
    from app.modules.proxy.replay_safety import responses_input_suffix_matches_pending_tool_calls

    items = [
        message(),
        {"type": "function_call", "name": "read", "call_id": "done", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "done", "output": "synthetic"},
        message(text="continue"),
    ]
    assert responses_input_suffix_matches_pending_tool_calls(
        items, stored_count=1, pending_tool_calls={"done": "function_call"}
    )
