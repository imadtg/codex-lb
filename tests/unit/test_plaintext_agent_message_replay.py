"""Codex agent history must not broaden standard provider portability."""

from copy import deepcopy
from typing import cast

import pytest

from app.core.types import JsonValue
from app.modules.model_sources.projection import PortabilityView
from app.modules.proxy.replay_safety import (
    project_responses_input_for_account_neutral_fresh_replay,
    responses_payload_is_account_neutral_fresh_replay,
    responses_payload_is_provider_portable,
    transcript_is_source_free,
)

pytestmark = pytest.mark.unit


def agent_message():
    return {
        "type": "agent_message",
        "id": "amsg_original",
        "author": "worker",
        "recipient": "parent",
        "content": [{"type": "input_text", "text": "Verified findings"}],
        "internal_chat_message_metadata_passthrough": {"turn_id": "earlier", "create_time": 1789075583.415},
    }


def projected_payload(item):
    projection = project_responses_input_for_account_neutral_fresh_replay(
        cast(list[JsonValue], [item, {"role": "user", "content": "Continue"}]), stored_count=1
    )
    assert projection is not None
    return {"input": projection.input_items}


def test_plaintext_agent_message_is_preserved_only_for_codex_accounts():
    item = agent_message()
    before = deepcopy(item)
    payload = projected_payload(item)
    assert payload["input"][0] == {k: v for k, v in item.items() if k != "id"}
    assert item == before
    assert responses_payload_is_account_neutral_fresh_replay(payload)
    view = PortabilityView(body=payload)
    assert not transcript_is_source_free(view)
    verdict = responses_payload_is_provider_portable(view, {}, supported_tool_types=frozenset(), supports_vision=True)
    assert not verdict.portable


@pytest.mark.parametrize(
    "changes",
    [
        {"author": ""},
        {"recipient": None},
        {"content": []},
        {"content": [{"type": "input_text", "text": "text", "file_id": "file_owned"}]},
        {"content": [{"type": "encrypted_content", "encrypted_content": "opaque"}]},
        {
            "content": [
                {"type": "input_text", "text": "text"},
                {"type": "encrypted_content", "encrypted_content": "opaque"},
            ]
        },
        {"container_id": "owned"},
        {"internal_chat_message_metadata_passthrough": {"unknown": "value"}},
        {"internal_chat_message_metadata_passthrough": {"turn_id": 42}},
        *[
            {"internal_chat_message_metadata_passthrough": {"create_time": value}}
            for value in (True, -1, float("inf"), float("nan"), 10**400)
        ],
    ],
)
def test_unknown_or_opaque_agent_history_remains_nonportable(changes):
    assert not responses_payload_is_account_neutral_fresh_replay(projected_payload({**agent_message(), **changes}))
