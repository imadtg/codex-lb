"""Exercise the real Codex binary against loopback-only synthetic Responses.

No live accounts, config, threads or application processes are used. The provider
closes the first WebSocket with 1012, then completes the replay. All input and
credentials are synthetic. Outputs contain only request shape and result counts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path

from aiohttp import web


async def run(binary: str) -> dict:
    requests = []
    sockets = 0
    tool_sent = False
    replay_inputs = []

    async def respond(request):
        nonlocal sockets, tool_sent
        if request.method != "GET":
            return web.Response(status=503, text="synthetic HTTP fallback refused")
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        sockets += 1
        socket_id = sockets
        async for message in ws:
            if message.type != web.WSMsgType.TEXT:
                continue
            payload = json.loads(message.data)
            requests.append(
                {
                    "socket": socket_id,
                    "anchor": bool(payload.get("previous_response_id")),
                    "input_count": len(payload.get("input", [])),
                    "generate": payload.get("generate"),
                }
            )
            if socket_id == 1 and tool_sent and payload.get("generate") is not False:
                await ws.close(code=1012, message=b"synthetic owner lost; resend full input")
                break
            if socket_id > 1:
                replay_inputs.append(payload.get("input", []))
            response_id = "resp_synthetic_recovered"
            if payload.get("generate") is not False and not tool_sent:
                tool_sent = True
                response_id = "resp_synthetic_tool"
                item = {
                    "type": "function_call",
                    "id": "fc_synthetic",
                    "call_id": "call_synthetic",
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": "echo SYNTHETIC_TOOL_42"}),
                }
                await ws.send_json({"type": "response.created", "response": {"id": response_id}})
                await ws.send_json({"type": "response.output_item.done", "output_index": 0, "item": item})
                await ws.send_json(
                    {
                        "type": "response.completed",
                        "response": {
                            "id": response_id,
                            "status": "completed",
                            "output": [item],
                            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                        },
                    }
                )
                continue
            await ws.send_json({"type": "response.created", "response": {"id": response_id, "status": "in_progress"}})
            if payload.get("generate") is not False:
                await ws.send_json(
                    {
                        "type": "response.output_item.done",
                        "output_index": 0,
                        "item": {
                            "type": "message",
                            "id": "msg_synthetic",
                            "role": "assistant",
                            "status": "completed",
                            "content": [{"type": "output_text", "text": "SYNTHETIC_RECOVERY_OK", "annotations": []}],
                        },
                    }
                )
            await ws.send_json(
                {
                    "type": "response.completed",
                    "response": {
                        "id": response_id,
                        "status": "completed",
                        "output": [],
                        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                    },
                }
            )
        return ws

    app = web.Application()
    app.router.add_route("*", "/v1/responses", respond)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    try:
        with tempfile.TemporaryDirectory(prefix="codex-offline-recovery-") as directory:
            home = Path(directory)
            (home / "config.toml").write_text(f"""model = "gpt-6-astra"
model_provider = "synthetic"
approval_policy = "never"
sandbox_mode = "read-only"
[model_providers.synthetic]
name = "Synthetic loopback provider"
base_url = "http://127.0.0.1:{port}/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = true
stream_max_retries = 2
request_max_retries = 0
""")
            env = {
                k: v
                for k, v in os.environ.items()
                if not any(x in k.upper() for x in ("OPENAI", "CODEX", "TOKEN", "PROXY", "T3CODE"))
            }
            env.update(CODEX_HOME=directory, HOME=directory, NO_PROXY="127.0.0.1,localhost", RUST_LOG="off")
            proc = await asyncio.create_subprocess_exec(
                binary,
                "exec",
                "--skip-git-repo-check",
                "--json",
                "Run echo SYNTHETIC_TOOL_42, then reply with SYNTHETIC_RECOVERY_OK.",
                cwd=directory,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), 60)
            except BaseException:
                proc.kill()
                await proc.wait()
                raise
            result = {
                "exit_code": proc.returncode,
                "requests": requests,
                "sockets": sockets,
                "completed": b"SYNTHETIC_RECOVERY_OK" in stdout,
            }
            if proc.returncode or not requests:
                result["synthetic_process_error"] = stderr.decode()[-2500:]
            assert result["exit_code"] == 0 and result["completed"], result
            assert sockets == 2, result
            assert requests[-1]["anchor"] is False, result
            replay = replay_inputs[-1]
            calls = [item for item in replay if item.get("type") == "function_call"]
            outputs = [item for item in replay if item.get("type") == "function_call_output"]
            assert len(calls) == len(outputs) == 1, "Reconnect lost or duplicated tool history"
            assert calls[0]["call_id"] == outputs[0]["call_id"] == "call_synthetic"
            assert "SYNTHETIC_TOOL_42" in outputs[0]["output"], "Synthetic tool did not complete"
            result["tool_history_preserved"] = True
            return result
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", help="Absolute path to the real binary, not an auto-updating wrapper")
    print(json.dumps(asyncio.run(run(parser.parse_args().binary)), indent=2))
