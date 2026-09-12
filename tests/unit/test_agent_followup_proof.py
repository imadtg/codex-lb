"""Output provenance stays independent of portable agent delivery content."""

from copy import deepcopy

import pytest

from app.core.types import JsonValue
from app.modules.proxy.replay_safety import (
    responses_input_suffix_matches_pending_tool_calls,
    responses_input_suffix_retains_prior_output,
)

pytestmark = pytest.mark.unit

PREFIX: list[JsonValue] = [{"role": "user", "content": "Research the problem"}]
CALL: dict[str, JsonValue] = {"type": "function_call", "name": "lookup", "arguments": "{}", "call_id": "call_1"}
RESULT: dict[str, JsonValue] = {"type": "function_call_output", "call_id": "call_1", "output": "Found evidence"}
ANSWER: dict[str, JsonValue] = {
    "role": "assistant",
    "phase": "final_answer",
    "content": [{"type": "output_text", "text": "Done"}],
}
USER: dict[str, JsonValue] = {"role": "user", "content": "Continue"}
AGENT: dict[str, JsonValue] = {
    "type": "agent_message",
    "author": "worker",
    "recipient": "parent",
    "content": [{"type": "input_text", "text": "Additional findings"}],
}


@pytest.mark.parametrize(
    "suffix,expected",
    [
        ([ANSWER, AGENT], True),
        ([CALL, RESULT, AGENT, ANSWER, USER], True),
        ([AGENT, ANSWER, USER], True),
        ([AGENT], False),
        ([CALL, RESULT, AGENT], False),  # No stored manifest or retained answer.
        ([CALL, AGENT, RESULT, ANSWER, USER], False),
        ([CALL, AGENT], False),
    ],
)
def test_agent_is_input_not_output_proof(suffix, expected):
    assert responses_input_suffix_retains_prior_output([*PREFIX, *suffix], stored_count=1) is expected


@pytest.mark.parametrize(
    "suffix,expected",
    [
        ([CALL, RESULT, AGENT], True),
        ([CALL, RESULT, AGENT, USER], True),
        ([CALL, AGENT, RESULT], False),
        ([CALL, AGENT], False),
        ([AGENT], False),
        ([CALL, RESULT, USER, AGENT, ANSWER, USER], True),
    ],
)
def test_manifest_must_be_exactly_settled_before_agent_followup(suffix, expected):
    assert (
        responses_input_suffix_matches_pending_tool_calls(
            [*PREFIX, *suffix], stored_count=1, pending_tool_calls={"call_1": "function_call"}
        )
        is expected
    )


@pytest.mark.parametrize("mutation", ["encrypted", "recipient", "unknown", "empty"])
def test_malformed_agent_cannot_supply_followup_or_cross_historical_proof(mutation):
    agent = deepcopy(AGENT)
    if mutation == "encrypted":
        content = agent["content"]
        assert isinstance(content, list)
        content.append({"type": "encrypted_content", "encrypted_content": "opaque"})
    elif mutation == "recipient":
        agent["recipient"] = ""
    elif mutation == "unknown":
        agent["future_field"] = "opaque"
    else:
        agent["content"] = []
    assert not responses_input_suffix_retains_prior_output([*PREFIX, ANSWER, agent], stored_count=1)
    assert not responses_input_suffix_retains_prior_output([*PREFIX, agent, ANSWER, USER], stored_count=1)
    assert not responses_input_suffix_matches_pending_tool_calls(
        [*PREFIX, CALL, RESULT, agent], stored_count=1, pending_tool_calls={"call_1": "function_call"}
    )
