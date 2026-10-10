"""Paced public streaming and replay through disposable application processes.

No application imports, patched internals, database writes, or real credentials.
WAL commit markers count all transactions in the stimulus window; exported
metrics separately count confirmed nonterminal transcript append batches.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import socket
import sqlite3
import struct
import sys
import tempfile
import time
import zlib
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, FormData, web
from probe_historical_prefix import jwt


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wal_snapshot(path: Path) -> dict:
    data = path.with_name(path.name + "-wal").read_bytes()
    page_size = struct.unpack_from(">I", data, 8)[0]
    salt = data[16:24]
    commits = frames = 0
    for offset in range(32, len(data) - 23, page_size + 24):
        if offset + page_size + 24 > len(data) or data[offset + 8 : offset + 16] != salt:
            break
        frames += 1
        commits += struct.unpack_from(">I", data, offset + 4)[0] != 0
    return {"salt": salt.hex(), "frames": frames, "commits": commits, "bytes": len(data)}


def transcript(path: Path, response_id: str) -> dict | None:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM http_bridge_operations WHERE response_id=?", (response_id,)).fetchone()
        if row is None:
            return None
        events = [
            r[0]
            for r in db.execute(
                "SELECT event_text FROM http_bridge_operation_events WHERE operation_id=? ORDER BY sequence_number",
                (row["operation_id"],),
            )
        ]
        chunks = list(
            db.execute(
                "SELECT * FROM http_bridge_operation_event_chunks WHERE operation_id=? ORDER BY first_sequence_number",
                (row["operation_id"],),
            )
        )
        if chunks:
            assert events == []
            for chunk in chunks:
                assert chunk["codec"] == "zlib-length-prefixed-utf8-v1"
                canonical = zlib.decompress(chunk["payload"])
                assert len(canonical) == chunk["uncompressed_bytes"]
                assert hashlib.sha256(canonical).hexdigest() == chunk["payload_sha256"]
                assert chunk["first_sequence_number"] == len(events) + 1
                offset = 0
                for _ in range(chunk["event_count"]):
                    size = struct.unpack_from(">I", canonical, offset)[0]
                    events.append(canonical[offset + 4 : offset + 4 + size].decode())
                    offset += 4 + size
                assert offset == len(canonical)
        return {
            "state": row["state"],
            "complete": bool(row["event_spool_complete"]),
            "format": row["spool_format"],
            "events": events,
            "rows": len(events) if not chunks else 0,
            "chunks": len(chunks),
            "stored_payload_bytes": sum(len(c["payload"]) for c in chunks)
            if chunks
            else sum(len(e.encode()) for e in events),
        }


def event_values(blocks: list[str]) -> list[dict]:
    return [json.loads(next(line[6:] for line in block.splitlines() if line.startswith("data: "))) for block in blocks]


async def run(args) -> dict:
    args.artifact.mkdir(parents=True, exist_ok=True)
    calls = []
    wire_requests = []
    delivered = {}
    spooled = {}

    async def upstream(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for incoming in ws:
            if incoming.type != web.WSMsgType.TEXT:
                continue
            body = json.loads(incoming.data)
            key = body["input"][-1]["content"]
            calls.append(key)
            wire_requests.append(body)
            response_id = f"resp_{key}"
            item = {
                "type": "message",
                "id": f"msg_{key}",
                "role": "assistant",
                "status": "completed",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": "é" * 32, "annotations": []}],
            }
            events = [
                {"type": "response.created", "response": {"id": response_id, "status": "in_progress"}},
                {"type": "response.output_item.added", "output_index": 0, "item": {**item, "status": "in_progress"}},
                *[
                    {
                        "type": "response.output_text.delta",
                        "item_id": item["id"],
                        "output_index": 0,
                        "content_index": 0,
                        "delta": "é",
                    }
                    for _ in range(32)
                ],
                {"type": "response.output_item.done", "output_index": 0, "item": item},
                {
                    "type": "response.completed",
                    "response": {
                        "id": response_id,
                        "status": "completed",
                        "model": "gpt-6-astra",
                        "output": [item],
                        "usage": {"input_tokens": 1, "output_tokens": 32, "total_tokens": 33},
                    },
                },
            ]
            delivered[key] = []
            spooled[key] = []
            try:
                for index, event in enumerate(events):
                    wire_text = json.dumps(event, separators=(",", ":"))
                    await ws.send_str(wire_text)
                    spooled[key].append(f"event: {event['type']}\ndata: {wire_text}\n\n")
                    delivered[key].append(time.monotonic())
                    if key == "interrupted" and index == 10:
                        await asyncio.Future()
                    await asyncio.sleep(0.02)
            except (ConnectionError, RuntimeError):
                break
        return ws

    app = web.Application()
    app.router.add_get("/backend-api/codex/responses", upstream)
    runner = web.AppRunner(app, shutdown_timeout=0.1)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    upstream_port = runner.addresses[0][1]
    port, metrics_port = free_port(), free_port()
    proc = None
    report = {
        "calls": calls,
        "checkout": str(args.checkout),
        "format": args.format,
        "interval_seconds": args.interval,
        "phase": "setup",
    }
    with (
        tempfile.TemporaryDirectory(prefix="lb-batching-") as directory,
        (args.artifact / "server.log").open("w") as log,
    ):
        database = Path(directory) / "store.db"
        env = {
            k: v
            for k, v in os.environ.items()
            if not any(s in k.upper() for s in ("CODEX", "OPENAI", "TOKEN", "PROXY", "T3", "PROMETHEUS"))
        }
        env.update(
            HOME=directory,
            NO_PROXY="127.0.0.1,localhost",
            CODEX_LB_DATA_DIR=directory,
            CODEX_LB_DATABASE_URL=f"sqlite+aiosqlite:///{database}",
            CODEX_LB_UPSTREAM_BASE_URL=f"http://127.0.0.1:{upstream_port}/backend-api",
            CODEX_LB_METRICS_ENABLED="true",
            CODEX_LB_METRICS_PORT=str(metrics_port),
            CODEX_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_EVENT_SPOOL_FLUSH_INTERVAL_SECONDS=str(args.interval),
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

        async with ClientSession(timeout=ClientTimeout(total=25)) as client:
            base = f"http://127.0.0.1:{port}"

            async def stop(kill=False):
                nonlocal proc
                if proc is not None and proc.returncode is None:
                    proc.kill() if kill else proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), 15)
                    except TimeoutError:
                        proc.kill()
                        await proc.wait()

            async def start(build, spool_format):
                nonlocal proc
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "app.cli",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    cwd=directory,
                    env={
                        **env,
                        "PYTHONPATH": str(build),
                        "CODEX_LB_HTTP_RESPONSES_SESSION_BRIDGE_OPERATION_SPOOL_FORMAT": spool_format,
                    },
                    stdout=log,
                    stderr=log,
                )
                for _ in range(300):
                    try:
                        async with client.get(base + "/health/ready") as response:
                            if response.status == 200:
                                return
                    except OSError:
                        pass
                    assert proc.returncode is None, "application exited; see server.log"
                    await asyncio.sleep(0.1)
                raise AssertionError("startup timeout")

            async def api(method, path, **kwargs):
                async with client.request(method, base + path, **kwargs) as response:
                    text = await response.text()
                    assert response.status == 200, (path, response.status, text)
                    return json.loads(text)

            async def send(key, interrupt=False, seed=False):
                body = {
                    "model": "gpt-6-astra",
                    "instructions": "Synthetic batching regression",
                    "stream": True,
                    # A client-owned key keeps request identity stable across
                    # process swaps; the upstream's auto-key index is volatile.
                    "prompt_cache_key": f"synthetic-stable-{key}",
                    "input": [{"role": "user", "content": f"seed_{key}" if seed else key}],
                }
                if not seed:
                    body["previous_response_id"] = f"resp_seed_{key}"
                blocks, received = [], []
                async with client.post(
                    base + "/backend-api/codex/responses",
                    json=body,
                    headers={"session_id": f"session-{key}", "thread-id": f"thread-{key}"},
                ) as response:
                    assert response.status == 200, await response.text() if response.status != 200 else ""
                    buffer = ""
                    async for data in response.content.iter_any():
                        buffer += data.decode()
                        while "\n\n" in buffer:
                            block, buffer = buffer.split("\n\n", 1)
                            if (
                                "data: " in block
                                and "[DONE]" not in block
                                and not block.startswith("event: codex.keepalive")
                            ):
                                blocks.append(block + "\n\n")
                                received.append(time.monotonic())
                            if interrupt and len(blocks) >= 8:
                                await stop(kill=True)
                                return blocks, received
                return blocks, received

            async def complete(key):
                for _ in range(100):
                    result = transcript(database, f"resp_{key}")
                    if result and result["complete"]:
                        return result
                    await asyncio.sleep(0.02)
                raise AssertionError(f"spool not completed: {key}: {result}")

            try:
                await start(args.checkout, args.format)
                claims = {
                    "email": "synthetic@example.invalid",
                    "chatgpt_account_id": "synthetic",
                    "exp": int(time.time()) + 86400,
                    "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
                }
                auth = {
                    "tokens": {
                        "idToken": jwt(claims),
                        "accessToken": jwt(claims),
                        "refreshToken": "synthetic",
                        "accountId": "synthetic",
                    }
                }
                form = FormData()
                form.add_field("auth_json", json.dumps(auth), filename="auth.json", content_type="application/json")
                await api("POST", "/api/accounts/import", data=form)
                await api("PUT", "/api/settings", json={"upstreamStreamTransport": "websocket"})
                # Durable operation spooling covers continuity-bound followups.
                # Establish the parent through an actual completed public turn.
                await send("paced", seed=True)
                before = wal_snapshot(database)
                blocks, received = await send("paced")
                saved = await complete("paced")
                (args.artifact / "transcript.json").write_text(
                    json.dumps({"persisted": saved["events"], "public": blocks}, indent=2)
                )
                assert saved["events"] == spooled["paced"], "spool changed source bytes or order"
                # Public normalization already compacts some JSON envelopes.
                assert event_values(saved["events"]) == event_values(blocks), "public event content changed"
                assert len(blocks) == 36, len(blocks)
                after = wal_snapshot(database)
                assert before["salt"] == after["salt"], "WAL reset; transaction comparison invalid"
                lags = [r - s for r, s in zip(received, delivered["paced"], strict=True)]
                assert max(lags[2:34]) < 0.5, lags
                assert received[2] < delivered["paced"][-1], "deltas withheld until terminal"
                report.update(
                    transcript={k: v for k, v in saved.items() if k != "events"},
                    wal_transactions=after["commits"] - before["commits"],
                    wal_frames=after["frames"] - before["frames"],
                    wal_bytes_added=after["bytes"] - before["bytes"],
                    max_delivery_lag_seconds=max(lags),
                    max_delta_delivery_lag_seconds=max(lags[2:34]),
                    terminal_delivery_lag_seconds=lags[-1],
                    transcript_sha256=hashlib.sha256("".join(saved["events"]).encode()).hexdigest(),
                )
                async with client.get(f"http://127.0.0.1:{metrics_port}/metrics") as response:
                    metrics_text = await response.text()
                    (args.artifact / "metrics.txt").write_text(metrics_text)
                if args.expect_batching:
                    samples = [
                        line
                        for line in metrics_text.splitlines()
                        if line.startswith("codex_lb_http_bridge_spool_batch_events_")
                    ]
                    count = sum(
                        float(line.split()[-1])
                        for line in samples
                        if line.startswith("codex_lb_http_bridge_spool_batch_events_count")
                    )
                    total = sum(
                        float(line.split()[-1])
                        for line in samples
                        if line.startswith("codex_lb_http_bridge_spool_batch_events_sum")
                    )
                    assert 0 < count < total / 2, (count, total)
                    report["nonterminal_batches"] = count
                    report["batched_events"] = total
                if args.concurrent:
                    await send("busy", seed=True)
                    await send("quiet", seed=True)
                    results = await asyncio.gather(send("busy"), send("quiet"))
                    for key, (public, times) in zip(("busy", "quiet"), results, strict=True):
                        persisted = await complete(key)
                        assert persisted["events"] == spooled[key]
                        assert event_values(public) == event_values(persisted["events"])
                        concurrent_lags = [r - t for r, t in zip(times, delivered[key], strict=True)]
                        assert max(concurrent_lags[2:34]) < 0.5, concurrent_lags
                        assert times[2] < delivered[key][-1], "deltas withheld until terminal"
                    report["concurrent_streams"] = "passed"
                if args.base:
                    await stop()
                    await start(args.base, "rows_v1")
                    replay, _ = await send("paced")
                    assert event_values(replay) == event_values(blocks) and calls == ["seed_paced", "paced"], (
                        "base did not replay exact fork transcript"
                    )
                    await send("base_rows", seed=True)
                    base_blocks, _ = await send("base_rows")
                    assert (await complete("base_rows"))["events"] == spooled["base_rows"]
                    await stop()
                    await start(args.checkout, args.format)
                    replay, _ = await send("base_rows")
                    assert event_values(replay) == event_values(base_blocks) and calls == [
                        "seed_paced",
                        "paced",
                        "seed_base_rows",
                        "base_rows",
                    ]
                    replay, _ = await send("paced")
                    assert event_values(replay) == event_values(blocks) and calls == [
                        "seed_paced",
                        "paced",
                        "seed_base_rows",
                        "base_rows",
                    ]
                    report["base_fork_replay"] = "passed"
                if args.interrupt:
                    await send("interrupted", seed=True)
                    await send("interrupted", interrupt=True)
                    interrupted = transcript(database, "resp_interrupted")
                    assert interrupted is None or not interrupted["complete"], interrupted
                    await start(args.checkout, args.format)
                    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
                        assert (
                            db.execute(
                                "SELECT count(*) FROM http_bridge_operations WHERE "
                                "state NOT IN ('completed','failed','incomplete') AND event_spool_complete=1"
                            ).fetchone()[0]
                            == 0
                        )
                    assert (await complete("paced"))["events"] == saved["events"]
                    report["interruption"] = "incomplete spool fenced; completed transcript retained"
                report["phase"] = "passed"
            finally:
                await stop()
                (args.artifact / "wire-requests.json").write_text(json.dumps(wire_requests, indent=2))
                with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
                    db.row_factory = sqlite3.Row
                    operations = [
                        dict(row)
                        for row in db.execute(
                            "SELECT session_id,request_fingerprint,parent_response_id,request_text,spool_format "
                            "FROM http_bridge_operations"
                        )
                    ]
                    (args.artifact / "operation-identities.json").write_text(json.dumps(operations, indent=2))
                (args.artifact / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    await runner.cleanup()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--format", choices=("rows_v1", "chunks_v2"), default="rows_v1")
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--expect-batching", action="store_true")
    parser.add_argument("--interrupt", action="store_true")
    parser.add_argument("--concurrent", action="store_true")
    options = parser.parse_args()
    print(json.dumps(asyncio.run(run(options)), indent=2))
