"""Black-box continuity regression: separate codex-lb process, public APIs only.

Run with the harness environment's Python and --checkout pointing at either build.
No application/test imports, monkeypatches, SQL writes, or production credentials.
Synthetic text replaces private content; developer item structure comes from a
compacted Codex rollout. This is a wire replay, not yet a real-client compaction E2E.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, FormData, web


def jwt(payload):
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{encoded}.synthetic"


def response_events_from_wire(text):
    """Parse native WS recordings, JSON errors, or SSE without application imports."""
    if text.lstrip().startswith(("[", "{")):
        value = json.loads(text)
        return value if isinstance(value, list) else [value]
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        if data and data != "[DONE]":
            events.append(json.loads(data))
    return events


def completed_response(text):
    events = response_events_from_wire(text)
    terminals = [e for e in events if e.get("type") in {"response.completed", "response.failed", "error"}]
    if not terminals or terminals[-1].get("type") != "response.completed":
        return None
    assert len(terminals) == 1, "Multiple terminal responses delivered for one request"
    response = terminals[0]["response"]
    assert response.get("status") == "completed", response
    return response


def recovered_response(text):
    response = completed_response(text)
    return response is not None and any(
        part.get("type") == "output_text" and part.get("text") == "RECOVERED"
        for item in response.get("output", [])
        for part in item.get("content", [])
    )


async def run(checkout, variant, artifact):
    calls = []
    response_turn_states: list[str | None] = []
    fresh_prewarm = variant == "fresh_prewarm_capacity"
    replacement_exhausted = variant == "quota_bridge_replacement_exhausted"
    healthy = variant == "quota_bridge_healthy"
    namespaced_tool = variant == "quota_bridge_namespace_plain_prefix"
    bridge_quota = variant.startswith("quota_bridge")
    direct_quota = variant.startswith("quota_status")
    echo_turn_state = "turn_state" in variant or replacement_exhausted
    agent_message_history = "agent_message" in variant
    visible_failure = variant == "quota_bridge_visible_failure"
    accepted_failure = "accepted_failure" in variant or visible_failure
    exhausted_accounts = set()
    unsafe_history = any(reason in variant for reason in ("changed_prefix", "missing_output", "encrypted"))
    tool = {
        "type": "custom_tool_call",
        "id": "ct_synthetic",
        "call_id": "call_synthetic",
        "name": "apply_patch",
        "input": "*** Begin Patch\n*** End Patch",
    }
    result = {"type": "custom_tool_call_output", "call_id": "call_synthetic", "output": "Success"}
    if namespaced_tool:
        tool = {
            "type": "function_call",
            "id": "fc_synthetic",
            "call_id": "call_synthetic",
            "namespace": "functions",
            "name": "lookup",
            "arguments": "{}",
        }
        result = {"type": "function_call_output", "call_id": "call_synthetic", "output": "Success"}
    answer = {
        "type": "message",
        "id": "msg_answer",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": "RECOVERED", "annotations": []}],
    }

    def response_events():
        item = tool if len(calls) == 1 else {**answer, "id": f"msg_answer_{len(calls)}"}
        rid = "resp_owner" if len(calls) == 1 else f"resp_alternate_{len(calls)}"
        if fresh_prewarm and len(calls) == 1:
            return [
                {"type": "response.created", "response": {"id": rid, "status": "in_progress"}},
                {"type": "response.completed", "response": {"id": rid, "status": "completed", "output": []}},
            ]
        return [
            {"type": "response.created", "response": {"id": rid, "status": "in_progress"}},
            {"type": "response.output_item.added", "output_index": 0, "item": item},
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {
                "type": "response.completed",
                "response": {
                    "id": rid,
                    "status": "completed",
                    "output": [item],
                    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                },
            },
        ]

    async def upstream(request):
        account = request.headers.get("chatgpt-account-id")
        ws = web.WebSocketResponse()
        ws.headers["x-codex-turn-state"] = f"turn-{account}"
        await ws.prepare(request)
        async for message in ws:
            calls.append(
                {
                    "account": account,
                    "transport": "websocket",
                    "turn_state": request.headers.get("x-codex-turn-state"),
                    "body": json.loads(message.data),
                }
            )
            if fresh_prewarm and account == "synthetic-owner" and len(calls) > 1:
                for sequence, event in enumerate(
                    [
                        {"type": "response.created", "response": {"id": "resp_capacity", "status": "in_progress"}},
                        {"type": "response.in_progress", "response": {"id": "resp_capacity", "status": "in_progress"}},
                        {
                            "type": "error",
                            "status": 503,
                            "error": {"code": "server_is_overloaded", "message": "Synthetic capacity rejection"},
                        },
                    ]
                ):
                    await ws.send_json({**event, "sequence_number": sequence})
                continue
            if (
                bridge_quota
                and not healthy
                and ((account == "synthetic-owner" and len(calls) > 1) or account in exhausted_accounts)
            ):
                error = {
                    "code": "usage_limit_reached",
                    "type": "usage_limit_reached",
                    "message": "Synthetic quota exhausted",
                }
                if (
                    replacement_exhausted
                    and account == "synthetic-owner"
                    and calls[-1]["body"].get("previous_response_id")
                ):
                    error = {
                        "code": "previous_response_not_found",
                        "type": "invalid_request_error",
                        "message": "Previous response not found",
                        "param": "previous_response_id",
                    }
                if accepted_failure:
                    await ws.send_json(
                        {"type": "response.created", "response": {"id": "resp_accepted", "status": "in_progress"}}
                    )
                if visible_failure:
                    await ws.send_json(
                        {
                            "type": "response.output_item.added",
                            "response_id": "resp_accepted",
                            "output_index": 0,
                            "item": {"id": "msg_visible", "type": "message", "role": "assistant", "content": []},
                        }
                    )
                    await ws.send_json(
                        {
                            "type": "response.output_text.delta",
                            "response_id": "resp_accepted",
                            "item_id": "msg_visible",
                            "output_index": 0,
                            "content_index": 0,
                            "delta": "Already shown",
                        }
                    )
                await ws.send_json(
                    {
                        "type": "response.failed",
                        "response": {
                            "status": "failed",
                            "error": error,
                        },
                    }
                    if variant == "quota_bridge_failed_event"
                    else {
                        "type": "error",
                        "status": 400 if error["code"] == "previous_response_not_found" else 429,
                        "error": error,
                    }
                )
                continue
            for sequence, event in enumerate(response_events()):
                await ws.send_json({**event, "sequence_number": sequence})
            if "reconnect" in variant and account == "synthetic-alternate":
                await ws.close()
        return ws

    async def upstream_http(request):
        account = request.headers.get("chatgpt-account-id")
        calls.append({"account": account, "transport": "http", "body": await request.json()})
        if bridge_quota:
            return web.json_response({"error": {"code": "unexpected_transport"}}, status=400)
        if account == "synthetic-owner" and len(calls) > 1:
            return web.json_response(
                {
                    "error": {
                        "code": "usage_limit_reached",
                        "type": "usage_limit_reached",
                        "message": "Synthetic quota exhausted",
                    }
                },
                status=429,
            )
        text = "".join(
            "data: " + json.dumps({**event, "sequence_number": index}) + "\n\n"
            for index, event in enumerate(response_events())
        )
        return web.Response(text=text, content_type="text/event-stream")

    app = web.Application()
    app.router.add_get("/backend-api/codex/responses", upstream)
    app.router.add_post("/backend-api/codex/responses", upstream_http)
    runner = web.AppRunner(app, shutdown_timeout=1)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    upstream_port = runner.addresses[0][1]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    artifact.mkdir(parents=True, exist_ok=True)
    report = {
        "variant": variant,
        "checkout": str(checkout),
        "calls": calls,
        "response_turn_states": response_turn_states,
        "checkout_commit": subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip(),
        "checkout_dirty": bool(
            subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain"], text=True).strip()
        ),
        "phase": "setup",
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "application_diff_sha256": hashlib.sha256(
            subprocess.check_output(
                ["git", "-C", str(checkout), "diff", "HEAD", "--", "app", "pyproject.toml", "uv.lock"]
            )
        ).hexdigest(),
    }
    with tempfile.TemporaryDirectory(prefix="lb-blackbox-") as directory:
        env = {
            k: v
            for k, v in os.environ.items()
            if not any(word in k.upper() for word in ("CODEX", "OPENAI", "TOKEN", "PROXY", "T3"))
        }
        env.update(
            HOME=directory,
            NO_PROXY="127.0.0.1,localhost",
            CODEX_LB_DATA_DIR=directory,
            CODEX_LB_DATABASE_URL=f"sqlite+aiosqlite:///{directory}/store.db",
            CODEX_LB_UPSTREAM_BASE_URL=f"http://127.0.0.1:{upstream_port}/backend-api",
        )
        for setting in (
            "USAGE_REFRESH",
            "RATE_LIMIT_RESET_CREDITS_REFRESH",
            "AUTH_GUARDIAN",
            "MODEL_REGISTRY",
            "QUOTA_PLANNER_SCHEDULER",
            "AUTOMATIONS_SCHEDULER",
            "TELEMETRY",
        ):
            env[f"CODEX_LB_{setting}_ENABLED"] = "false"
        proc = None
        with (artifact / "server.log").open("w") as log:
            try:
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
                async with ClientSession(timeout=ClientTimeout(total=25)) as client:
                    base = f"http://127.0.0.1:{port}"
                    for _ in range(450):
                        try:
                            async with client.get(base + "/health") as response:
                                if response.status == 200:
                                    break
                        except OSError:
                            pass
                        if proc.returncode is not None:
                            raise RuntimeError("server exited; see server.log")
                        await asyncio.sleep(0.2)
                    else:
                        raise RuntimeError("server startup timed out")

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
                        form.add_field(
                            "auth_json", json.dumps(auth), filename="auth.json", content_type="application/json"
                        )
                        return (await api("POST", "/api/accounts/import", data=form))["accountId"]

                    await api(
                        "PUT",
                        "/api/settings",
                        json={"upstreamStreamTransport": "http" if direct_quota else "websocket"},
                    )
                    owner = await account("synthetic-owner")
                    prefix: list[dict[str, object]] = [
                        {
                            "type": "additional_tools",
                            "role": "developer",
                            "tools": [{"type": "custom", "name": "apply_patch"}],
                        },
                        {"type": "message", "role": "developer", "content": "Synthetic base instructions"},
                        {"role": "user", "content": "Synthetic summarized task"},
                    ]
                    if variant != "control" and not fresh_prewarm and not variant.endswith("plain_prefix"):
                        prefix += [
                            {
                                "type": "message",
                                "id": f"msg_history_{i}",
                                "role": "developer",
                                "content": [
                                    {"type": "input_text", "text": f"Historical instruction {i}: {kind}"}
                                    for kind in kinds
                                ],
                                "internal_chat_message_metadata_passthrough": {
                                    "turn_id": "synthetic-turn",
                                    "content_item_kinds": kinds,
                                },
                            }
                            for i, kinds in enumerate(
                                [
                                    [
                                        "host_skills.instructions",
                                        "permissions.instructions",
                                        "collaboration_mode.instructions",
                                    ],
                                    ["multi_agent.role_instructions"],
                                    ["multi_agent.mode_instructions"],
                                ]
                            )
                        ]
                    body = {
                        "model": "gpt-6-astra",
                        "instructions": "Continue",
                        "stream": True,
                        "tools": [{"type": "custom", "name": "apply_patch", "description": "Apply a patch"}],
                    }
                    if namespaced_tool:
                        prefix = prefix[1:]
                        body["tools"] = [
                            {
                                "type": "namespace",
                                "name": "functions",
                                "description": "Local tools",
                                "tools": [
                                    {
                                        "type": "function",
                                        "name": "lookup",
                                        "description": "Read local data",
                                        "parameters": {"type": "object", "properties": {}},
                                        "strict": False,
                                    }
                                ],
                            }
                        ]
                    headers = {"session_id": "synthetic-process", "thread-id": "synthetic-thread"}
                    if agent_message_history:
                        prefix.append(
                            {
                                "type": "agent_message",
                                "id": "amsg_synthetic",
                                "author": "synthetic-worker",
                                "recipient": "synthetic-parent",
                                "content": [{"type": "input_text", "text": "Synthetic research findings"}],
                                "internal_chat_message_metadata_passthrough": {
                                    "turn_id": "synthetic-earlier-turn",
                                    "create_time": 1789075583.415,
                                },
                            }
                        )
                        if "encrypted" in variant:
                            agent_content = prefix[-1]["content"]
                            assert isinstance(agent_content, list)
                            agent_content.append(
                                {"type": "encrypted_content", "encrypted_content": "synthetic-opaque-content"}
                            )

                    downstream_ws = None

                    async def send(items):
                        nonlocal downstream_ws
                        if fresh_prewarm:
                            if downstream_ws is None:
                                downstream_ws = await client.ws_connect(
                                    base + "/backend-api/codex/responses", headers=headers
                                )
                            await downstream_ws.send_json({"type": "response.create", **body, "input": items})
                            events = []
                            while True:
                                event = await asyncio.wait_for(downstream_ws.receive_json(), 25)
                                events.append(event)
                                if event["type"] in {"response.completed", "response.failed", "error"}:
                                    break
                            report.setdefault("native_events", []).append(events)
                            return 200, json.dumps(events)

                        async with client.post(
                            base + "/backend-api/codex/responses", headers=headers, json={**body, "input": items}
                        ) as response:
                            response_turn_states.append(response.headers.get("x-codex-turn-state"))
                            return response.status, await response.text()

                    if fresh_prewarm:
                        body["generate"] = False
                    report["first"] = await send(prefix)
                    if fresh_prewarm:
                        body.pop("generate")
                        body["previous_response_id"] = "resp_owner"

                    initial_response = completed_response(report["first"][1])
                    assert initial_response is not None and initial_response["id"] == "resp_owner", report["first"]
                    if not fresh_prewarm:
                        # Replay the tool actually delivered through the public API.
                        assert initial_response["output"][0]["call_id"] == result["call_id"]
                        tool = initial_response["output"][0]
                    report["phase"] = "scenario"
                    if bridge_quota:
                        assert len(calls) == 1 and calls[0]["transport"] == "websocket", calls
                    if echo_turn_state:
                        first_turn_state = response_turn_states[0]
                        assert first_turn_state, "The server must establish the token; never fabricate client state"
                        headers["x-codex-turn-state"] = first_turn_state
                    await account("synthetic-alternate")
                    if replacement_exhausted:
                        exhausted_accounts.add("synthetic-alternate")
                    if not direct_quota and not bridge_quota and not fresh_prewarm:
                        await api("POST", f"/api/accounts/{owner}/pause")
                    full = [*prefix, tool, result, {"role": "user", "content": "Continue"}]
                    if fresh_prewarm:
                        full = [*prefix, {"role": "user", "content": "First real task"}]
                    if "suffix_agent" in variant:
                        delivery = {
                            "type": "agent_message",
                            "id": "amsg_delivery",
                            "author": "synthetic-worker",
                            "recipient": "synthetic-parent",
                            "content": [{"type": "input_text", "text": "Worker finished its research"}],
                        }
                        if "encrypted" in variant:
                            delivery["content"].append(
                                {"type": "encrypted_content", "encrypted_content": "synthetic-opaque"}
                            )
                        full.insert(-1, delivery)
                    if "changed_prefix" in variant:
                        full[2] = {"role": "user", "content": "Different task"}
                    if "missing_output" in variant:
                        full.remove(result)
                    if variant == "owner_unavailable":
                        body["previous_response_id"] = "resp_owner"
                        full = [{"role": "user", "content": "Continue"}]
                    # Codex sends only the suffix when reusing a completed warmup
                    # anchor (client.rs prepare_websocket_request). A rollout's
                    # logical full request is not evidence of the wire payload.
                    report["second"] = await send(full[-1:] if fresh_prewarm else full)
                    if healthy:
                        assert recovered_response(report["second"][1]), report["second"]
                        assert [call["account"] for call in calls] == ["synthetic-owner", "synthetic-owner"], calls
                        report["passed"] = True
                        return True
                    if replacement_exhausted:
                        # Both failures are learned from public provider responses.
                        # No failed lane/proof is installed by the harness.
                        assert [call["account"] for call in calls] == [
                            "synthetic-owner",
                            "synthetic-owner",
                            "synthetic-alternate",
                        ], calls
                        report["exhausted_error"] = response_events_from_wire(report["second"][1])
                        await account("synthetic-third")
                        report["retry"] = await send(full)
                        assert recovered_response(report["retry"][1]), report["retry"]
                        assert calls[-1]["account"] == "synthetic-third", calls
                        assert not calls[-1]["body"].get("previous_response_id"), calls
                        report["passed"] = True
                        return True
                    report["recovered"] = recovered_response(report["second"][1])
                    if bridge_quota:
                        assert all(call["transport"] == "websocket" for call in calls), calls
                        if not unsafe_history:
                            assert len(calls) >= 2 and calls[1]["account"] == "synthetic-owner", calls
                    if report["recovered"]:
                        assert "response.completed" in report["second"][1]
                        assert calls[-1]["account"] == "synthetic-alternate"
                        assert not calls[-1]["body"].get("previous_response_id")
                        assert not calls[-1].get("turn_state"), "Old account token crossed the handoff"
                        assert calls[-1]["body"]["input"] == [
                            {key: value for key, value in item.items() if key != "id"} for item in full
                        ]
                        if bridge_quota:
                            prior_call_count = len(calls)
                            followup_answer = {
                                **answer,
                                "id": f"msg_answer_{prior_call_count}",
                                "content": [{"type": "output_text", "text": "RECOVERED"}],
                            }
                            # Codex caches the FIRST token for the whole turn.
                            # Keep echoing it even if recovery returned a new one.
                            full = [*full, followup_answer, {"role": "user", "content": "Check the findings"}]
                            report["third"] = await send(full)
                            report["followup_recovered"] = "RECOVERED" in report["third"][1]
                            assert recovered_response(report["third"][1]), report["third"]
                            assert len(calls) == prior_call_count + 1, calls
                            assert calls[-1]["account"] == "synthetic-alternate", calls
                            assert calls[-1].get("turn_state") != "turn-synthetic-owner", calls
                            if "chain" in variant:
                                await account("synthetic-third")
                                exhausted_accounts.add("synthetic-alternate")
                                previous_calls = len(calls)
                                full = [
                                    *full,
                                    {**followup_answer, "id": f"msg_answer_{previous_calls}"},
                                    {"role": "user", "content": "Continue the review"},
                                ]
                                if "suffix_agent" in variant:
                                    full.insert(-1, {**delivery, "id": "amsg_later_delivery"})
                                report["fourth"] = await send(full)
                                assert recovered_response(report["fourth"][1]), report["fourth"]
                                assert [call["account"] for call in calls[previous_calls:]] == [
                                    "synthetic-alternate",
                                    "synthetic-third",
                                ], calls
                                assert not calls[-1].get("turn_state"), calls
                                assert not calls[-1]["body"].get("previous_response_id"), calls
                                assert calls[-1]["body"]["input"] == [
                                    {key: value for key, value in item.items() if key != "id"} for item in full
                                ]
                                full = [
                                    *full,
                                    {**followup_answer, "id": f"msg_answer_{len(calls)}"},
                                    {"role": "user", "content": "Finish the review"},
                                ]
                                previous_calls = len(calls)
                                report["fifth"] = await send(full)
                                assert recovered_response(report["fifth"][1]), report["fifth"]
                                assert len(calls) == previous_calls + 1 and calls[-1]["account"] == "synthetic-third"
                                report["chain_recovered"] = True
                    elif variant == "owner_unavailable":
                        assert report["second"][0] == 502, report["second"]
                        assert json.loads(report["second"][1])["error"]["code"] == "previous_response_owner_unavailable"
                        assert len(calls) == 1, calls
                    elif unsafe_history:
                        assert all(call["account"] == "synthetic-owner" for call in calls), calls
                        if not bridge_quota:
                            assert len(calls) == 1, "unsafe history was dispatched again"
                        envelope = json.loads(report["second"][1])
                        refusal = (report["second"][0], envelope["error"]["code"])
                        # Portability controls forbid a cross-account dispatch.
                        # Forwarded owner quota and an unavailable-owner refusal
                        # are distinct documented outcomes, recorded separately.
                        # Generic 4xx/5xx errors are never accepted as success.
                        if refusal == (502, "upstream_unavailable"):
                            assert (
                                envelope["error"]["message"]
                                == "Previous response owner account is unavailable; retry later."
                            )
                        else:
                            assert refusal in {
                                (429, "usage_limit_reached"),
                                (502, "previous_response_owner_unavailable"),
                            }, report["second"]
                        report["refusal"] = {"status": refusal[0], "code": refusal[1], "cross_account_dispatch": False}
                    elif accepted_failure:
                        assert len(calls) == 2 and all(call["account"] == "synthetic-owner" for call in calls)
                        assert "resp_accepted" in report["second"][1] and "usage_limit_reached" in report["second"][1]
                        if visible_failure:
                            events = response_events_from_wire(report["second"][1])
                            assert [e["delta"] for e in events if e.get("type") == "response.output_text.delta"] == [
                                "Already shown"
                            ]
                    if fresh_prewarm:
                        assert report["recovered"], report["second"]
                        assert [call["account"] for call in calls] == [
                            "synthetic-owner",
                            "synthetic-owner",
                            "synthetic-alternate",
                        ]
                        assert not calls[-1]["body"].get("previous_response_id")
                        events = report["native_events"][-1]
                        assert [e["sequence_number"] for e in events] == list(range(len(events)))
                        assert sum(e["type"] == "response.created" for e in events) == 1
                        assert events[-1]["response"]["id"] == events[0]["response"]["id"]
                        await downstream_ws.close()
                    report["passed"] = report["recovered"] == (
                        not unsafe_history
                        and not accepted_failure
                        and (variant in {"control", "historical"} or direct_quota or bridge_quota or fresh_prewarm)
                    )
            except Exception as exc:
                report["passed"] = False
                report["failure"] = {"phase": report["phase"], "type": type(exc).__name__, "message": str(exc)}
                raise
            finally:
                if proc is not None and proc.returncode is None:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), 10)
                    except TimeoutError:
                        proc.kill()
                        await proc.wait()
                await runner.cleanup()
                (artifact / "report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"calls", "first", "second", "third", "fourth", "fifth"}}
        )
    )
    return report.get("passed", False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument(
        "--variant",
        choices=[
            "quota_bridge_namespace_plain_prefix",
            "quota_bridge_visible_failure",
            "quota_bridge_plain_prefix",
            "quota_bridge_agent_message_plain_prefix",
            "quota_bridge_healthy",
            "quota_bridge_replacement_exhausted",
            "fresh_prewarm_capacity",
            "quota_bridge_turn_state_suffix_agent_chain",
            "quota_bridge_turn_state_suffix_agent",
            "quota_bridge_turn_state_suffix_agent_encrypted",
            "quota_bridge_turn_state_suffix_agent_missing_output",
            "owner_unavailable",
            "control",
            "historical",
            "changed_prefix",
            "missing_output",
            "quota_status",
            "quota_status_agent_message",
            "quota_bridge",
            "quota_bridge_failed_event",
            "quota_bridge_turn_state",
            "quota_bridge_agent_message",
            "quota_bridge_turn_state_agent_message",
            "quota_bridge_turn_state_agent_message_encrypted",
            "quota_bridge_turn_state_changed_prefix",
            "quota_bridge_turn_state_missing_output",
            "quota_bridge_turn_state_agent_message_chain",
            "quota_bridge_turn_state_chain_reconnect",
            "quota_bridge_turn_state_accepted_failure",
        ],
        default="historical",
    )
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(run(args.checkout.resolve(), args.variant, args.artifact.resolve())) else 1)
