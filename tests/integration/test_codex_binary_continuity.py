"""Optional real-client contract probe; only loopback and disposable test DBs."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from aiohttp import web

import app.modules.proxy.service as proxy_module
from tests.integration.test_http_responses_bridge import (
    _cleanup_http_bridge_sessions,  # noqa: F401
    _FakeBridgeUpstreamWebSocket,
    _FakeUpstreamMessage,
    _get_account,
    _import_account,
    _install_bridge_settings,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("loss_mode", ["pause", "quota"])
@pytest.mark.parametrize("upstream_transport", ["websocket", "http"])
async def test_real_codex_http_full_history_after_owner_loss(
    async_client, app_instance, monkeypatch, tmp_path, upstream_transport, loss_mode
):
    binary = os.environ.get("CODEX_LB_TEST_CODEX_BINARY")
    if not binary:
        pytest.skip("Set CODEX_LB_TEST_CODEX_BINARY to a versioned Codex binary")
    assert Path(binary).is_absolute()
    _install_bridge_settings(monkeypatch, enabled=True)
    # An explicit operator pin selects the bridge even for native Codex HTTP.
    (await proxy_module.get_settings_cache().get()).upstream_stream_transport = upstream_transport
    owner_id = await _import_account(async_client, "binary-owner", "owner@example.invalid")
    owner = await _get_account(owner_id)
    connects = []
    incoming = []

    class Provider(_FakeBridgeUpstreamWebSocket):
        def __init__(self, tool):
            super().__init__()
            self.tool = tool

        async def send_text(self, text):
            self.sent_text.append(text)
            item = (
                {
                    "type": "function_call",
                    "id": "fc_binary",
                    "call_id": "call_binary",
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": "echo SYNTHETIC_TOOL_42"}),
                }
                if self.tool
                else {
                    "type": "message",
                    "id": "msg_binary",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "SYNTHETIC_RECOVERY_OK", "annotations": []}],
                }
            )
            if self.tool and len(self.sent_text) > 1:
                await self._messages.put(
                    _FakeUpstreamMessage(
                        "text",
                        text=json.dumps(
                            {
                                "type": "error",
                                "status": 429,
                                "error": {
                                    "type": "usage_limit_reached",
                                    "code": "usage_limit_reached",
                                    "message": "Synthetic quota exhausted",
                                },
                            }
                        ),
                    )
                )
                return
            response_id = "resp_binary_owner" if self.tool else "resp_binary_alternate"
            for event in [
                {"type": "response.created", "response": {"id": response_id, "status": "in_progress"}},
                {"type": "response.output_item.added", "output_index": 0, "item": item},
                {"type": "response.output_item.done", "output_index": 0, "item": item},
                {
                    "type": "response.completed",
                    "response": {
                        "id": response_id,
                        "status": "completed",
                        "output": [item],
                        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                    },
                },
            ]:
                await self._messages.put(_FakeUpstreamMessage("text", text=json.dumps(event)))

    first, alternate = Provider(True), Provider(False)

    async def fresh(self, account, *, force=False, timeout_seconds):
        return account

    async def connect(headers, access_token, account_id_header, *, base_url=None, session=None):
        connects.append(account_id_header)
        return first if account_id_header == owner.chatgpt_account_id else alternate

    monkeypatch.setattr(proxy_module.ProxyService, "_ensure_fresh_with_budget", fresh)
    monkeypatch.setattr(proxy_module, "connect_responses_websocket", connect)

    async def synthetic_http(payload, headers, access_token, account_id, **kwargs):
        connects.append(account_id)
        provider = first if account_id == owner.chatgpt_account_id else alternate
        await provider.send_text(json.dumps(payload.to_payload()))
        while True:
            message = await provider.receive()
            assert message.text is not None
            event = json.loads(message.text)
            yield "data: " + json.dumps(event) + "\n\n"
            if event["type"] in {"response.completed", "error"}:
                break

    monkeypatch.setattr(proxy_module, "core_stream_responses", synthetic_http)

    async def relay(request):
        body = await request.json()
        incoming.append(body)
        if len(incoming) == 2:
            await _import_account(async_client, "binary-alternate", "alternate@example.invalid")
            if loss_mode == "pause":
                response = await async_client.post(f"/api/accounts/{owner_id}/pause")
                assert response.status_code == 200
        response = await asyncio.wait_for(
            async_client.post(
                "/backend-api/codex/responses",
                json=body,
                headers={
                    k: v
                    for k, v in request.headers.items()
                    if k.lower() not in {"host", "content-length", "content-encoding", "transfer-encoding"}
                },
            ),
            12,
        )
        return web.Response(status=response.status_code, body=response.content, content_type="text/event-stream")

    app = web.Application()
    app.router.add_post("/v1/responses", relay)
    runner = web.AppRunner(app, shutdown_timeout=1)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    port = runner.addresses[0][1]
    (tmp_path / "config.toml").write_text(f"""model = "gpt-6-astra"
model_provider = "synthetic"
approval_policy = "never"
sandbox_mode = "read-only"
[features]
image_generation = false
[model_providers.synthetic]
name = "Synthetic"
base_url = "http://127.0.0.1:{port}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
stream_max_retries = 1
request_max_retries = 0
""")
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(x in k.upper() for x in ("TOKEN", "CODEX", "T3CODE", "OPENAI", "PROXY"))
    }
    env.update(HOME=str(tmp_path), CODEX_HOME=str(tmp_path), NO_PROXY="127.0.0.1,localhost", RUST_LOG="off")
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            "exec",
            "--skip-git-repo-check",
            "--json",
            "Run echo SYNTHETIC_TOOL_42, then reply SYNTHETIC_RECOVERY_OK.",
            cwd=tmp_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 45)
        assert proc.returncode == 0, (stdout.decode(), stderr.decode())
        assert b"SYNTHETIC_RECOVERY_OK" in stdout
        assert len(incoming) == 2
        assert not incoming[1].get("previous_response_id")
        expected_dispatches = 3 if loss_mode == "quota" and upstream_transport == "http" else 2
        assert len(connects) == expected_dispatches and connects[0] != connects[-1]
        if expected_dispatches == 3:
            assert connects[0] == connects[1]
        replay = json.loads(alternate.sent_text[0])
        assert not replay.get("previous_response_id")
        outputs = [item for item in replay["input"] if item.get("type") == "function_call_output"]
        assert len(outputs) == 1 and "SYNTHETIC_TOOL_42" in outputs[0]["output"]
    finally:
        if proc is not None and proc.returncode is None:
            proc.kill()
            await proc.wait()
        await runner.cleanup()
