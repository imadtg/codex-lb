"""An older exact tool manifest must remain mandatory after later turns."""

from typing import cast

import pytest

from app.core.types import JsonValue
from app.modules.proxy.replay_safety import responses_input_suffix_matches_pending_tool_calls

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("missing", [None, "call_a", "call_b"])
@pytest.mark.parametrize("changed_call", [False, True])
def test_later_assistant_does_not_hide_missing_parallel_tool_context(missing, changed_call):
    prefix = [{"role": "user", "content": "Inspect both files"}]
    batch = []
    for call in ("call_a", "call_b"):
        if call == missing:
            continue
        actual_call = "other_call" if changed_call and call == "call_a" else call
        batch.extend(
            [
                {"type": "function_call", "call_id": actual_call, "name": "inspect", "arguments": "{}"},
                {"type": "function_call_output", "call_id": actual_call, "output": "done"},
            ]
        )
    later = [
        {"role": "user", "content": "Continue"},
        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Reviewed"}]},
        {"role": "user", "content": "Continue again"},
    ]
    assert responses_input_suffix_matches_pending_tool_calls(
        cast(list[JsonValue], prefix + batch + later),
        stored_count=1,
        pending_tool_calls={"call_a": "function_call", "call_b": "function_call"},
        fingerprint_verified_prefix=True,
    ) == (missing is None and not changed_call)
