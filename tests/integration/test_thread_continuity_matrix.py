"""Real route + real selector + disposable SQLite; only provider transport is fake.

Portable requests must recover. State-dependent requests must fail without unsafe forwarding.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import update

import app.modules.proxy.service as proxy_module
from app.db.models import Account, AccountStatus, UsageHistory
from app.db.session import SessionLocal
from app.dependencies import get_proxy_service_for_app
from tests.integration.test_http_responses_bridge import (
    _cleanup_http_bridge_sessions,  # noqa: F401 -- imported fixture owns all fake sockets
    _ClosingBridgeUpstreamWebSocket,
    _FakeBridgeUpstreamWebSocket,
    _get_account,
    _import_account,
    _install_bridge_settings,
)

pytestmark = pytest.mark.integration


def _events(response):
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]


@pytest.mark.parametrize("owner_status", ["paused", "rate_limited", "quota_exceeded"])
@pytest.mark.parametrize(
    "shape",
    [
        "complete",
        "poisoned",
        "retired_anchor",
        "denied_anchor",
        "legacy_proof_lost",
        "legacy_delta",
        "legacy_compaction",
        "legacy_turn_state",
        "namespace",
        "namespaced_history",
        "reasoning_context",
        "codex_metadata",
        "compaction",
        "orphan",
        "delta",
    ],
)
async def test_existing_thread_owner_loss_matrix(async_client, app_instance, monkeypatch, owner_status, shape, caplog):
    caplog.set_level(logging.INFO, logger="app.modules.proxy.continuity")
    _install_bridge_settings(monkeypatch, enabled=True)
    owner_id = await _import_account(async_client, "audit-owner", "audit-owner@example.invalid")
    owner = await _get_account(owner_id)
    owner_ws = (
        _FakeBridgeUpstreamWebSocket
        if shape in {"poisoned", "retired_anchor", "denied_anchor"} or shape.startswith("legacy_")
        else _ClosingBridgeUpstreamWebSocket
    )("resp_audit_owner")
    alternate_ws = _FakeBridgeUpstreamWebSocket("resp_audit_alternate")
    connects = []

    async def fresh(self, account, *, force=False, timeout_seconds):
        return account

    async def connect(headers, access_token, account_id_header, *, base_url=None, session=None):
        connects.append(account_id_header)
        return owner_ws if account_id_header == owner.chatgpt_account_id else alternate_ws

    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh_with_budget", fresh)
    monkeypatch.setattr(proxy_module, "connect_responses_websocket", connect)
    path = "/backend-api/codex/responses"
    headers = {"session_id": "audit-process", "thread-id": "audit-thread"}
    if shape == "legacy_turn_state":
        headers["x-codex-turn-state"] = "synthetic-owner-token"
    history = [{"role": "user", "content": [{"type": "input_text", "text": "remember synthetic 42"}]}]
    if shape == "namespaced_history":
        history.extend(
            [
                {
                    "type": "function_call",
                    "namespace": "functions",
                    "name": "read",
                    "call_id": "done",
                    "arguments": "{}",
                },
                {"type": "function_call_output", "call_id": "done", "output": "synthetic result"},
            ]
        )
    base = {"model": "gpt-6-astra", "instructions": "Continue.", "stream": True}
    first = await asyncio.wait_for(async_client.post(path, headers=headers, json={**base, "input": history}), 8)
    assert first.status_code == 200, first.text
    first_response = _events(first)[-1]["response"]

    if shape in {"poisoned", "retired_anchor", "denied_anchor"} or shape.startswith("legacy_"):
        from sqlalchemy import select

        from app.db.models import HttpBridgeSessionRecord
        from app.modules.proxy.durable_bridge_repository import DurableBridgeRepository

        async with SessionLocal() as session:
            row = await session.scalar(
                select(HttpBridgeSessionRecord).where(HttpBridgeSessionRecord.account_id == owner_id)
            )
            assert row is not None
            assert row.owner_instance_id is not None
            proof = (row.latest_input_item_count, row.latest_input_full_fingerprint)
            assert proof[0]
            repo = DurableBridgeRepository(session)
            if shape == "retired_anchor":
                assert (
                    await repo.clear_latest_response_anchor(
                        session_id=row.id,
                        instance_id=row.owner_instance_id,
                        owner_epoch=row.owner_epoch,
                    )
                    is not None
                )
            elif shape == "denied_anchor":
                assert row.latest_response_id is not None
                assert (
                    await repo.clear_latest_response_anchor_if_matches(
                        session_id=row.id,
                        api_key_scope=row.api_key_scope,
                        instance_id=row.owner_instance_id,
                        owner_epoch=row.owner_epoch,
                        response_id=row.latest_response_id,
                    )
                    is not None
                )
            else:
                assert await DurableBridgeRepository(session).rebind_session_account(
                    session_id=row.id,
                    instance_id=row.owner_instance_id,
                    owner_epoch=row.owner_epoch,
                    account_id=owner_id,
                    clear_continuity=True,
                    preserve_replay_proof=shape == "poisoned",
                    expected_latest_response_id=row.latest_response_id,
                    expected_latest_turn_state=row.latest_turn_state,
                )
            await session.refresh(row)
            assert row.latest_response_id is None
            assert (row.latest_input_item_count, row.latest_input_full_fingerprint) == (
                proof if shape in {"poisoned", "retired_anchor", "denied_anchor"} else (None, None)
            )
    if shape in {"poisoned", "retired_anchor", "denied_anchor"} or shape.startswith("legacy_"):
        service = get_proxy_service_for_app(app_instance)
        async with service._http_bridge_lock:
            old_sessions = list(service._http_bridge_sessions.values())
            service._http_bridge_sessions.clear()
            service._http_bridge_turn_state_index.clear()
            service._http_bridge_previous_response_index.clear()
        for old_session in old_sessions:
            await service._close_http_bridge_session(old_session)
    alternate_id = await _import_account(async_client, "audit-alternate", "audit-alternate@example.invalid")
    alternate = await _get_account(alternate_id)
    now = int(time.time())
    async with SessionLocal() as session:
        await session.execute(
            update(Account)
            .where(Account.id == owner_id)
            .values(status=AccountStatus(owner_status), blocked_at=now, reset_at=now + 1800)
        )
        for window, used in [("primary", 100.0), ("secondary", 100.0 if owner_status == "quota_exceeded" else 16.0)]:
            session.add(
                UsageHistory(
                    account_id=owner_id,
                    window=window,
                    used_percent=used,
                    recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    reset_at=now + 1800,
                    window_minutes=300 if window == "primary" else 10080,
                )
            )
        await session.commit()
    service = get_proxy_service_for_app(app_instance)
    service._load_balancer._selection_inputs_cache.invalidate()

    followup = {
        **base,
        "input": [
            *history,
            first_response["output"][0],
            {"role": "user", "content": [{"type": "input_text", "text": "continue"}]},
        ],
    }
    if shape == "codex_metadata":
        followup["reasoning"] = {"effort": "high", "context": "all_turns"}
        followup["client_metadata"] = {
            key: "synthetic" for key in ("session_id", "thread_id", "turn_id", "parent_turn_id", "root_turn_id")
        }
    if shape == "reasoning_context":
        followup["reasoning"] = {"effort": "high", "context": "all_turns"}
    if shape in {"namespace", "namespaced_history"}:
        followup["tools"] = [
            {
                "type": "namespace",
                "name": "functions",
                "tools": [{"type": "function", "name": "read", "parameters": {"type": "object"}}],
            }
        ]
    elif shape in {"compaction", "legacy_compaction"}:
        followup["input"].insert(1, {"type": "compaction", "encrypted_content": "synthetic-opaque"})
    elif shape == "orphan":
        followup["input"].append({"type": "function_call_output", "call_id": "missing", "output": "synthetic"})
    elif shape in {"delta", "legacy_delta"}:
        followup["previous_response_id"] = first_response["id"]
        followup["input"] = followup["input"][-1:]
    caplog.clear()
    response = await asyncio.wait_for(async_client.post(path, headers=headers, json=followup), 8)
    assert "stage=http_ingress" in caplog.text
    assert "continuity_selection version=1" in caplog.text
    if shape in {"retired_anchor", "denied_anchor", "poisoned"}:
        assert "stage=durable_context_proof reason=context_proven" in caplog.text
    diagnostic_lines = [r.message for r in caplog.records if r.name == "app.modules.proxy.continuity"]
    assert not any(
        "audit-owner@example.invalid" in line or "synthetic-owner-token" in line for line in diagnostic_lines
    )
    if shape in {
        "complete",
        "poisoned",
        "retired_anchor",
        "denied_anchor",
        "legacy_proof_lost",
        "namespace",
        "namespaced_history",
        "reasoning_context",
        "codex_metadata",
    }:
        assert response.status_code == 200, response.text
        assert _events(response)[-1]["response"]["id"].startswith("resp_audit_alternate")
        assert connects == [owner.chatgpt_account_id, alternate.chatgpt_account_id]
        replay = json.loads(alternate_ws.sent_text[0])
        assert not replay.get("previous_response_id")
        expected = json.loads(json.dumps(followup["input"]))
        for item in expected:
            if item.get("type") in {"function_call", "custom_tool_call"}:
                item.pop("namespace", None)
        assert replay["input"] == expected
    else:
        # Characterize the boundary, not a claim that all these rejections are necessary.
        assert response.status_code >= 400 or any(
            e.get("type") in {"error", "response.failed"} for e in _events(response)
        )
        assert not alternate_ws.sent_text, "Account-owned/delta state was forwarded without reconstruction"


async def test_legacy_owner_exclusion_exits_real_bridge_selection_loop(async_client, app_instance, monkeypatch):
    from app.db.models import StickySessionKind
    from app.modules.proxy.affinity import _AffinityPolicy
    from app.modules.proxy.sticky_repository import StickySessionsRepository

    _install_bridge_settings(monkeypatch, enabled=True)
    owner_id = await _import_account(async_client, "excluded-owner", "excluded-owner@example.invalid")
    await _import_account(async_client, "healthy-alternate", "healthy-alternate@example.invalid")
    async with SessionLocal() as session:
        await StickySessionsRepository(session).upsert("legacy-process", owner_id, kind=StickySessionKind.CODEX_SESSION)
    service = get_proxy_service_for_app(app_instance)
    # This is the production selection loop used by the bridge, with actual
    # affinity parsing, selector, and DB. Eight seconds is only the test bound;
    # the production budget remains two hours to expose accidental waiting.
    result = await asyncio.wait_for(
        service._select_account_with_budget_for_stream(
            time.monotonic() + 7200,
            request_id="synthetic-exclusion",
            kind="http_bridge",
            affinity_policy=_AffinityPolicy(
                key="legacy-process", kind=StickySessionKind.CODEX_SESSION, codex_session_source="session_header"
            ),
            exclude_account_ids={owner_id},
        ),
        8,
    )
    assert result.account is None
    assert result.error_code == "hard_affinity_owner_excluded"
