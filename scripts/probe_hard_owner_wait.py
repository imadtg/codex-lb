"""Public process probe: establish ownership, pause its account, then retry.

No app imports, private state writes, production credentials or database edits.
Optional restart reopens the same disposable data through normal startup.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, FormData, web
from probe_historical_prefix import completed_response, jwt, terminal_error_code


async def run(checkout: Path, artifact: Path, mode: str, restart: bool):
    artifact.mkdir(parents=True, exist_ok=True)
    calls = []

    async def upstream(request):
        ws = None
        if request.method == "GET":
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            body = await ws.receive_json()
        else:
            body = await request.json()
        calls.append({"account": request.headers.get("chatgpt-account-id"), "body": body})
        response = {
            "id": "resp_owner",
            "status": "completed",
            "model": "gpt-6-astra",
            "output": [
                {
                    "type": "message",
                    "id": "msg_owner",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": "OK", "annotations": []}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }
        events = [
            {"type": "response.created", "response": {"id": "resp_owner", "status": "in_progress"}},
            {"type": "response.completed", "response": response},
        ]
        if ws is not None:
            for event in events:
                await ws.send_json(event)
            async for _ in ws:
                pass
            return ws
        return web.Response(
            text="".join("data: " + json.dumps(e) + "\n\n" for e in events), content_type="text/event-stream"
        )

    app = web.Application()
    app.router.add_post("/backend-api/codex/responses", upstream)
    app.router.add_get("/backend-api/codex/responses", upstream)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    provider_port = runner.addresses[0][1]
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = None
    report = {"mode": mode, "restart": restart, "calls": calls, "phase": "setup"}
    temporary = tempfile.TemporaryDirectory(prefix="lb-owner-wait-")
    try:
        directory = temporary.name
        with (artifact / "server.log").open("w") as log:
            env = {
                k: v
                for k, v in os.environ.items()
                if not any(s in k.upper() for s in ("CODEX", "OPENAI", "TOKEN", "PROXY", "T3"))
            }
            env.update(
                HOME=directory,
                CODEX_LB_DATA_DIR=directory,
                CODEX_LB_DATABASE_URL=f"sqlite+aiosqlite:///{directory}/store.db",
                CODEX_LB_UPSTREAM_BASE_URL=f"http://127.0.0.1:{provider_port}/backend-api",
                NO_PROXY="127.0.0.1,localhost",
            )
            for name in (
                "USAGE_REFRESH",
                "RATE_LIMIT_RESET_CREDITS_REFRESH",
                "AUTH_GUARDIAN",
                "MODEL_REGISTRY",
                "QUOTA_PLANNER_SCHEDULER",
                "AUTOMATIONS_SCHEDULER",
                "TELEMETRY",
            ):
                env[f"CODEX_LB_{name}_ENABLED"] = "false"
            async with ClientSession(timeout=ClientTimeout(total=10)) as client:
                base = f"http://127.0.0.1:{port}"

                async def start():
                    nonlocal proc
                    proc = await asyncio.create_subprocess_exec(
                        str(checkout / ".venv/bin/codex-lb"),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        cwd=directory,
                        env=env,
                        stdout=log,
                        stderr=log,
                    )
                    for _ in range(600):
                        try:
                            async with client.get(base + "/health") as response:
                                if response.status == 200:
                                    return
                        except OSError:
                            pass
                        assert proc.returncode is None, "startup exited"
                        await asyncio.sleep(0.2)
                    raise AssertionError("startup timeout")

                async def api(method, path, **kwargs):
                    async with client.request(method, base + path, **kwargs) as response:
                        text = await response.text()
                        assert response.status == 200, (path, response.status, text)
                        return json.loads(text)

                async def account(name):
                    claims = {
                        "email": f"{name}@example.invalid",
                        "chatgpt_account_id": name,
                        "exp": int(time.time()) + 86400,
                        "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
                    }
                    auth = {
                        "tokens": {
                            "idToken": jwt(claims),
                            "accessToken": jwt(claims),
                            "refreshToken": "synthetic",
                            "accountId": name,
                        }
                    }
                    form = FormData()
                    form.add_field("auth_json", json.dumps(auth), filename="auth.json", content_type="application/json")
                    return (await api("POST", "/api/accounts/import", data=form))["accountId"]

                headers = {"session_id": "synthetic-process"}
                body = {
                    "model": "gpt-6-astra",
                    "instructions": "Respond briefly",
                    "stream": True,
                    "input": [{"role": "user", "content": "Hello"}],
                }

                async def send():
                    async with client.post(base + "/backend-api/codex/responses", headers=headers, json=body) as r:
                        return r.status, await r.text()

                await start()
                await api("PUT", "/api/settings", json={"upstreamStreamTransport": "websocket"})
                owner = await account("synthetic-owner")
                async with client.ws_connect(base + "/backend-api/codex/responses", headers=headers) as ws:
                    headers["x-codex-turn-state"] = ws._response.headers["x-codex-turn-state"]
                    await ws.send_json({"type": "response.create", **body})
                    initial = []
                    while True:
                        event = await ws.receive_json()
                        initial.append(event)
                        if event.get("type") in {"response.completed", "response.failed", "error"}:
                            break
                    report["initial"] = initial
                    assert completed_response(json.dumps(initial)) is not None, initial
                await api("PUT", "/api/settings", json={"upstreamStreamTransport": "http"})
                body["previous_response_id"] = initial[-1]["response"]["id"]
                body["input"] = [{"role": "user", "content": "Continue"}]
                assert completed_response((await send())[1]) is not None
                body.pop("previous_response_id")
                body["input"] = [
                    {"role": "user", "content": "Hello"},
                    initial[-1]["response"]["output"][0],
                    {"role": "user", "content": "Continue"},
                ]
                await account("synthetic-alternate")
                if restart:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), 30)
                    await start()
                if mode != "healthy":
                    await api("POST", f"/api/accounts/{owner}/pause")
                report["phase"] = "scenario"

                async def recover():
                    await asyncio.sleep(0.5)
                    await api("POST", f"/api/accounts/{owner}/reactivate")

                recovery = asyncio.create_task(recover()) if mode == "recover" else None
                began = time.monotonic()
                try:
                    status, text = await send()
                    report.update(status=status, wire=text, elapsed=time.monotonic() - began)
                    assert all(c["account"] == "synthetic-owner" for c in calls), calls
                    if mode == "unavailable":
                        report["code"] = terminal_error_code(text)
                        assert report["code"] == "hard_affinity_saturated", report
                        assert report["elapsed"] < 8, report
                        assert len(calls) == 2, calls
                    else:
                        assert completed_response(text) is not None, text
                        assert len(calls) == 3, calls
                    report["passed"] = True
                finally:
                    if recovery:
                        await recovery
    except Exception as exc:
        report["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 30)
            except TimeoutError:
                proc.kill()
                await proc.wait()
        await runner.cleanup()
        temporary.cleanup()
        (artifact / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--mode", choices=["healthy", "unavailable", "recover"], required=True)
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.checkout.resolve(), args.artifact.resolve(), args.mode, args.restart))
