"""Live rejection through real routes, selector and operation ledger; fake provider only."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

import app.modules.proxy.service as proxy_module
from app.db.models import ApiKeyLimit, ApiKeyUsageReservation, HttpBridgeOperationRecord
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from tests.integration.test_http_responses_bridge import (
    _cleanup_http_bridge_sessions,  # noqa: F401
    _FakeBridgeUpstreamWebSocket,
    _FakeUpstreamMessage,
    _get_account,
    _import_account,
    _install_bridge_settings,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "case",
    [
        "complete",
        "keyed_complete",
        "keyed_spool_failure",
        "keyed_replacement_quota",
        "rate_limit",
        "missing_parallel_output",
        "missing_output",
        "changed_prefix",
        "missing_fence",
        "spool_failure",
        "turn_state",
        "visible_output",
        "replacement_quota",
    ],
)
async def test_live_quota_handoff_preserves_operation_or_refuses(async_client, app_instance, monkeypatch, case):
    _install_bridge_settings(monkeypatch, enabled=True)
    replacement_rejects = case in {"replacement_quota", "keyed_replacement_quota"}
    (await proxy_module.get_settings_cache().get()).upstream_stream_transport = "websocket"
    owner_id = await _import_account(async_client, "handoff-owner", "owner@example.invalid")
    owner = await _get_account(owner_id)
    call = {"type": "function_call", "id": "fc_owned", "call_id": "call_one", "name": "read", "arguments": "{}"}

    class Owner(_FakeBridgeUpstreamWebSocket):
        async def send_text(self, text):
            self.sent_text.append(text)
            if len(self.sent_text) == 1:
                events = [
                    {"type": "response.created", "response": {"id": "resp_owner", "status": "in_progress"}},
                    {"type": "response.output_item.added", "output_index": 0, "item": call},
                    {"type": "response.output_item.done", "output_index": 0, "item": call},
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_owner",
                            "status": "completed",
                            "output": [call],
                            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                        },
                    },
                ]
            else:
                events = []
                if case == "visible_output":
                    events += [
                        {"type": "response.created", "response": {"id": "resp_partial", "status": "in_progress"}},
                        {
                            "type": "response.output_text.delta",
                            "response_id": "resp_partial",
                            "delta": "already visible",
                            "output_index": 0,
                            "content_index": 0,
                        },
                    ]
                events.append(
                    {
                        "type": "error",
                        "status": 429,
                        "error": {
                            "type": "usage_limit_reached",
                            "code": "usage_limit_reached",
                            "message": "Synthetic quota",
                        },
                    }
                )
            if len(self.sent_text) == 1 and case == "missing_parallel_output":
                parallel_call = {**call, "id": "fc_parallel", "call_id": "call_parallel"}
                events.insert(2, {"type": "response.output_item.added", "output_index": 1, "item": parallel_call})
                events.insert(3, {"type": "response.output_item.done", "output_index": 1, "item": parallel_call})
                terminal_response = events[-1]["response"]
                assert isinstance(terminal_response, dict)
                terminal_output = terminal_response["output"]
                assert isinstance(terminal_output, list)
                terminal_output.append(parallel_call)
            if len(self.sent_text) > 1 and case == "rate_limit":
                events[-1]["error"] = {
                    "code": "rate_limit_exceeded",
                    "type": "rate_limit_exceeded",
                    "message": "Synthetic quota",
                }
            for event in events:
                await self._messages.put(_FakeUpstreamMessage("text", text=json.dumps(event)))

    class Replacement(_FakeBridgeUpstreamWebSocket):
        async def send_text(self, text):
            if not replacement_rejects:
                await super().send_text(text)
                return
            self.sent_text.append(text)
            await self._messages.put(
                _FakeUpstreamMessage(
                    "text",
                    text=json.dumps(
                        {
                            "type": "error",
                            "status": 429,
                            "error": {"code": "usage_limit_reached", "message": "Second owner quota"},
                        }
                    ),
                )
            )

    first, alternate = Owner(), Replacement("resp_alternate")
    connects = []

    async def fresh(self, account, *, force=False, timeout_seconds):
        return account

    async def connect(headers, access_token, account_id_header, *, base_url=None, session=None):
        connects.append(account_id_header)
        return first if account_id_header == owner.chatgpt_account_id else alternate

    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh_with_budget", fresh)
    monkeypatch.setattr(proxy_module, "connect_responses_websocket", connect)
    headers = {"session_id": "handoff-process", "thread-id": "handoff-thread"}
    if case == "turn_state":
        headers["x-codex-turn-state"] = "explicit-owner-token"
    api_key_id = None
    if case.startswith("keyed_"):
        assert (await async_client.put("/api/settings", json={"apiKeyAuthEnabled": True})).status_code == 200
        key_response = await async_client.post(
            "/api/api-keys/",
            json={
                "name": "quota-settlement",
                "limits": [{"limitType": "total_tokens", "limitWindow": "daily", "maxValue": 1000000}],
            },
        )
        assert key_response.status_code == 200
        api_key_id = key_response.json()["id"]
        headers["Authorization"] = "Bearer " + key_response.json()["key"]
    body = {"model": "gpt-6-astra", "instructions": "Continue", "stream": True}
    original = [{"role": "user", "content": "Run the tool"}]
    path = "/backend-api/codex/responses"
    response = await async_client.post(path, headers=headers, json={**body, "input": original})
    assert response.status_code == 200
    alternate_id = await _import_account(async_client, "handoff-alternate", "alternate@example.invalid")
    full = [*original, call, {"type": "function_call_output", "call_id": "call_one", "output": "complete tool result"}]
    if case == "missing_output":
        full.pop()
    if case == "changed_prefix":
        full[0] = {"role": "user", "content": "Different history"}
    if case == "turn_state":
        headers["x-codex-turn-state"] = "explicit-owner-token"
    if case == "missing_fence":
        import app.modules.proxy._service.http_bridge.streaming as bridge_streaming

        monkeypatch.setattr(
            bridge_streaming, "_http_bridge_verified_stale_anchor_replay_is_operation_fenced", lambda *_: False
        )
    if case in {"spool_failure", "keyed_spool_failure"}:
        service = get_proxy_service_for_app(app_instance)
        monkeypatch.setattr(service._durable_bridge, "reset_operation_event_spool", AsyncMock(return_value=False))
    response = await asyncio.wait_for(async_client.post(path, headers=headers, json={**body, "input": full}), 12)
    if case in {"complete", "rate_limit", "replacement_quota", "keyed_complete", "keyed_replacement_quota"}:
        assert len(alternate.sent_text) == 1, response.text
        old_dispatch = json.loads(first.sent_text[1])
        new_dispatch = json.loads(alternate.sent_text[0])
        operation_id = old_dispatch["client_metadata"]["codex_lb_operation_id"]
        assert new_dispatch["client_metadata"]["codex_lb_operation_id"] == operation_id
        assert not new_dispatch.get("previous_response_id")
        assert new_dispatch["input"] == [{key: value for key, value in item.items() if key != "id"} for item in full]
        async with SessionLocal() as db:
            operation = await db.get(HttpBridgeOperationRecord, operation_id)
            assert operation is not None and operation.account_id == alternate_id
            assert operation.state == ("failed" if replacement_rejects else "completed")
        if not replacement_rejects:
            assert "resp_alternate" in response.text
        assert len(connects) == 2
    else:
        assert not alternate.sent_text, response.text

    if api_key_id is not None:
        async with SessionLocal() as db:
            reservations = list(
                await db.scalars(select(ApiKeyUsageReservation).where(ApiKeyUsageReservation.api_key_id == api_key_id))
            )
            assert reservations and all(row.status != "reserved" for row in reservations)
            limit = await db.scalar(select(ApiKeyLimit).where(ApiKeyLimit.api_key_id == api_key_id))
            assert limit is not None
            assert limit.current_value == (28 if case == "keyed_complete" else 2)
