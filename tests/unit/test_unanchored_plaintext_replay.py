from copy import deepcopy

import pytest

from app.modules.proxy.replay_safety import project_unanchored_plaintext_history

pytestmark = pytest.mark.unit


def history():
    return {
        "model": "gpt-6-astra",
        "input": [
            {"role": "user", "content": "Run the tool"},
            {"type": "function_call", "id": "fc_local", "call_id": "call_local", "name": "read", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "call_local", "output": "the full result"},
        ],
    }


def test_plaintext_tool_history_removes_only_item_ids_without_mutating_request():
    payload = history()
    original = deepcopy(payload)
    projected = project_unanchored_plaintext_history(payload)
    assert projected == [{key: value for key, value in item.items() if key != "id"} for item in payload["input"]]
    assert payload == original


@pytest.mark.parametrize("binding", ["previous_response_id", "conversation"])
def test_explicit_binding_cannot_be_removed(binding):
    assert project_unanchored_plaintext_history({**history(), binding: "owned"}) is None


@pytest.mark.parametrize(
    "case",
    ["missing_result", "orphan", "duplicate", "no_user", "file", "compaction", "reasoning", "unknown", "hosted_tool"],
)
def test_incomplete_or_account_owned_history_is_not_normalized(case):
    payload = history()
    if case == "missing_result":
        payload["input"].pop()
    elif case == "orphan":
        payload["input"].pop(1)
    elif case == "duplicate":
        payload["input"].append(deepcopy(payload["input"][-1]))
    elif case == "no_user":
        payload["input"].pop(0)
    elif case == "file":
        payload["input"][0]["content"] = [{"type": "input_file", "file_id": "file_owned"}]
    elif case in {"reasoning", "compaction"}:
        payload["input"].insert(1, {"type": case, "encrypted_content": "opaque"})
    elif case == "unknown":
        payload["input"][1]["unknown"] = "opaque"
    else:
        payload["tools"] = [{"type": "file_search", "vector_store_ids": ["vs_owned"]}]
    assert project_unanchored_plaintext_history(payload) is None


@pytest.mark.parametrize("case", ["portable", "missing_result", "hosted_tool", "unknown_bundle_field", "file"])
def test_responses_lite_bundle_is_retained_only_when_full_history_is_portable(case):
    payload = history()
    bundle = {"type": "additional_tools", "role": "developer", "tools": [{"type": "function", "name": "read"}]}
    payload["input"].insert(0, bundle)
    if case == "missing_result":
        payload["input"].pop()
    elif case == "hosted_tool":
        bundle["tools"] = [{"type": "file_search", "vector_store_ids": ["vs_owned"]}]
    elif case == "unknown_bundle_field":
        bundle["owner_state"] = "opaque"
    elif case == "file":
        payload["input"][1]["content"] = [{"type": "input_file", "file_id": "file_owned"}]
    original = deepcopy(payload)
    projected = project_unanchored_plaintext_history(payload)
    if case == "portable":
        assert projected == [{key: value for key, value in item.items() if key != "id"} for item in payload["input"]]
    else:
        assert projected is None
    assert payload == original
