"""Focused proof-contract tests; external regression lives in the probe script."""

import pytest

from app.core.types import JsonValue
from app.modules.proxy.replay_safety import (
    project_responses_input_for_account_neutral_fresh_replay,
    responses_input_items_are_self_contained_fresh_replay,
    responses_input_suffix_matches_pending_tool_calls,
)


@pytest.mark.parametrize("verified", [False, True])
@pytest.mark.parametrize(
    "variant", ["portable", "missing_output", "unknown_metadata", "bad_kinds", "opaque", "parallel"]
)
def test_historical_prefix_proof_keeps_context_and_settlement_boundaries(verified, variant):
    metadata: dict[str, JsonValue] = {"turn_id": "turn_old", "content_item_kinds": ["permissions.instructions"]}
    if variant == "unknown_metadata":
        metadata["owner_token"] = "opaque"
    if variant == "bad_kinds":
        metadata["content_item_kinds"] = {"owner": "opaque"}
    developer: dict[str, JsonValue] = {
        "type": "message",
        "role": "developer",
        "id": "msg_old",
        "content": [{"type": "input_text", "text": "Historical instructions"}],
        "internal_chat_message_metadata_passthrough": metadata,
    }
    if variant == "opaque":
        developer["content"] = [{"type": "input_audio", "audio": "owner-bound"}]
    call: JsonValue = {"type": "custom_tool_call", "call_id": "call_one", "name": "shell", "input": "pwd"}
    output: JsonValue = {"type": "custom_tool_call_output", "call_id": "call_one", "output": "/tmp"}
    prefix: list[JsonValue] = [{"role": "user", "content": "Task"}, developer]
    suffix: list[JsonValue] = [call] if variant == "missing_output" else [call, output]
    manifest = {"call_one": "custom_tool_call"}
    if variant == "parallel":
        manifest["call_two"] = "custom_tool_call"
    projection = project_responses_input_for_account_neutral_fresh_replay(
        [*prefix, *suffix], stored_count=len(prefix), preserve_developer_message_ids=True
    )
    assert projection is not None
    context_proven = responses_input_suffix_matches_pending_tool_calls(
        projection.input_items,
        stored_count=projection.stored_prefix_count,
        pending_tool_calls=manifest,
        fingerprint_verified_prefix=verified,
    )
    replay = project_responses_input_for_account_neutral_fresh_replay([*prefix, *suffix], stored_count=len(prefix))
    assert replay is not None
    portable = responses_input_items_are_self_contained_fresh_replay(replay.input_items)
    assert (context_proven and portable) == (
        verified and variant not in {"missing_output", "unknown_metadata", "bad_kinds", "opaque", "parallel"}
    )
