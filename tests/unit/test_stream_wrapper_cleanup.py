import asyncio

import pytest

from app.core.utils.sse import format_sse_event
from app.modules.proxy.api import (
    _aclose_stream,
    _normalize_public_responses_stream,
    _normalize_reasoning_summary_stream,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
@pytest.mark.parametrize("native", [False, True])
async def test_early_close_cascades_through_actual_response_wrappers(native):
    released = asyncio.Event()

    async def leased_stream():
        try:
            yield format_sse_event(
                {"type": "response.created", "response": {"id": "resp_cleanup", "status": "in_progress"}}
            )
            yield format_sse_event(
                {"type": "response.completed", "response": {"id": "resp_cleanup", "status": "completed", "output": []}}
            )
        finally:
            released.set()

    wrapped = _normalize_reasoning_summary_stream(
        _normalize_public_responses_stream(leased_stream(), enforce_openai_sdk_contract=not native)
    )
    await anext(wrapped)
    await _aclose_stream(wrapped)
    assert released.is_set()
