"""Probe which retained Responses items survive a cross-account continuation.

This script talks directly to OpenAI with two disposable credentials. It does
not import codex-lb, read its database, or persist responses upstream. The JSON
artifact contains hashes and equality flags, never tokens, ciphertext, raw
model text, or account identifiers.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _events(body: str) -> list[dict[str, Any]]:
    if body.lstrip().startswith(("{", "[")):
        value = json.loads(body)
        values = value if isinstance(value, list) else [value]
        return [item for item in values if isinstance(item, dict)]
    parsed: list[dict[str, Any]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        if not data or data == "[DONE]":
            continue
        value = json.loads(data)
        if isinstance(value, dict):
            parsed.append(value)
    return parsed


def _walk(value: object) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            found.append(current)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return found


def _request(
    credential: tuple[str, str],
    payload: dict[str, Any],
    *,
    client_version: str,
) -> dict[str, Any]:
    account_id, token = credential
    upstream = request.Request(
        ENDPOINT,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "chatgpt-account-id": account_id,
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": f"codex_cli_rs/{client_version}",
            "originator": "codex_cli_rs",
            "version": client_version,
        },
    )
    try:
        with request.urlopen(upstream, timeout=180) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    events = _events(body)
    objects = _walk(events)
    terminals = [item for item in objects if item.get("type") in {"response.completed", "response.failed", "error"}]
    terminal = terminals[0] if terminals else None
    output = [
        item["item"]
        for item in events
        if item.get("type") == "response.output_item.done" and isinstance(item.get("item"), dict)
    ]
    texts = [
        str(item["text"])
        for item in objects
        if item.get("type") == "output_text" and isinstance(item.get("text"), str)
    ]
    codes = sorted({str(item["code"]) for item in objects if isinstance(item.get("code"), str)})
    return {
        "http_status": status,
        "terminal": terminal.get("type") if terminal else None,
        "output": output,
        "text": "\n".join(dict.fromkeys(texts)).strip(),
        "error_codes": codes,
    }


def _without_types(items: list[dict[str, Any]], omitted: set[str]) -> list[dict[str, Any]]:
    return [copy.deepcopy(item) for item in items if item.get("type") not in omitted]


def _without_ids(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key != "id"} for item in copy.deepcopy(items)]


def _corrupt_reasoning(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    corrupted = copy.deepcopy(items)
    for item in corrupted:
        ciphertext = item.get("encrypted_content")
        if item.get("type") == "reasoning" and isinstance(ciphertext, str) and ciphertext:
            index = len(ciphertext) // 2
            replacement = "A" if ciphertext[index] != "A" else "B"
            item["encrypted_content"] = ciphertext[:index] + replacement + ciphertext[index + 1 :]
            return corrupted
    raise RuntimeError("source response did not contain encrypted reasoning")


def _summary(name: str, result: dict[str, Any], *, expected: str | None = None) -> dict[str, Any]:
    text = result["text"]
    return {
        "name": name,
        "http_status": result["http_status"],
        "terminal": result["terminal"],
        "error_codes": result["error_codes"],
        "text_sha256": _sha256(text) if text else None,
        "text_bytes": len(text.encode()),
        "expected_exact": text == expected if expected is not None else None,
    }


def _continuation_payload(
    *,
    model: str,
    history: list[dict[str, Any]],
    prompt: str,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "instructions": "Follow the user. Do not invent unavailable retained context.",
        "input": [
            *history,
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        ],
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "low"},
        "store": False,
        "stream": True,
    }
    if tools is not None:
        payload["tools"] = tools
        payload["tool_choice"] = "none"
    return payload


def _reasoning_experiment(
    source: tuple[str, str], target: tuple[str, str], *, model: str, client_version: str
) -> dict[str, Any]:
    first = _request(
        source,
        {
            "model": model,
            "instructions": "Follow the user exactly.",
            "input": [{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "Privately invent and commit to one random 16-character string. Keep it only in your hidden "
                        "reasoning. Do not reveal any character now. Reply exactly READY. On the next turn reveal it."
                    ),
                }],
            }],
            "include": ["reasoning.encrypted_content"],
            "reasoning": {"effort": "medium"},
            "store": False,
            "stream": True,
        },
        client_version=client_version,
    )
    history = first["output"]
    prompt = "Reveal the exact 16-character string you committed to. Output only that string, or UNAVAILABLE."
    variants = {
        "same_account_full": (source, history),
        "different_account_full": (target, history),
        "different_account_strip_ids": (target, _without_ids(history)),
        "different_account_omit_reasoning": (target, _without_types(history, {"reasoning"})),
        "different_account_corrupt_reasoning": (target, _corrupt_reasoning(history)),
    }
    results: list[tuple[str, dict[str, Any]]] = []
    for name, (credential, items) in variants.items():
        results.append((name, _request(
            credential,
            _continuation_payload(model=model, history=items, prompt=prompt),
            client_version=client_version,
        )))
    control = results[0][1]["text"]
    return {
        "source_item_types": [item.get("type") for item in history],
        "same_account_control_sha256": _sha256(control) if control else None,
        "variants": [
            {**_summary(name, result), "matches_same_account_control": result["text"] == control}
            for name, result in results
        ],
    }


def _web_search_experiment(
    source: tuple[str, str], target: tuple[str, str], *, model: str, client_version: str
) -> dict[str, Any]:
    first = _request(
        source,
        {
            "model": model,
            "instructions": "Follow the user exactly.",
            "input": [{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "Use web search to find the current first headline on OpenAI News. Remember the headline "
                        "privately and reply exactly READY. Do not reveal the headline yet."
                    ),
                }],
            }],
            "tools": [{"type": "web_search"}],
            "include": ["reasoning.encrypted_content"],
            "reasoning": {"effort": "medium"},
            "store": False,
            "stream": True,
        },
        client_version=client_version,
    )
    history = first["output"]
    prompt = "Reveal the exact headline you remembered. Output only the headline."
    variants = {
        "same_account_full": (source, history),
        "different_account_full": (target, history),
        "different_account_strip_ids": (target, _without_ids(history)),
        "different_account_omit_reasoning": (target, _without_types(history, {"reasoning"})),
        "different_account_omit_web_search": (target, _without_types(history, {"web_search_call"})),
    }
    results: list[tuple[str, dict[str, Any]]] = []
    for name, (credential, items) in variants.items():
        results.append((name, _request(
            credential,
            _continuation_payload(model=model, history=items, prompt=prompt),
            client_version=client_version,
        )))
    control = results[0][1]["text"]
    return {
        "source_item_types": [item.get("type") for item in history],
        "same_account_control_sha256": _sha256(control) if control else None,
        "variants": [
            {**_summary(name, result), "matches_same_account_control": result["text"] == control}
            for name, result in results
        ],
    }


def _tool_search_experiment(
    source: tuple[str, str], target: tuple[str, str], *, model: str, client_version: str
) -> dict[str, Any]:
    marker = f"probe-{secrets.token_hex(12)}"
    deferred_tool = {
        "type": "function",
        "name": "remember_probe_value",
        "description": f"The opaque probe value is {marker}.",
        "defer_loading": True,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    }
    search_tool = {
        "type": "tool_search",
        "execution": "client",
        "description": "Searches deferred tools.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "number"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    }
    first = _request(
        source,
        {
            "model": model,
            "instructions": "Find the relevant deferred tool before answering.",
            "input": [{
                "role": "user",
                "content": [{"type": "input_text", "text": "Find the tool that contains an opaque probe value."}],
            }],
            "tools": [search_tool, deferred_tool],
            "include": ["reasoning.encrypted_content"],
            "reasoning": {"effort": "medium"},
            "store": False,
            "stream": True,
        },
        client_version=client_version,
    )
    history = first["output"]
    search_calls = [item for item in history if item.get("type") == "tool_search_call"]
    if not search_calls or not isinstance(search_calls[-1].get("call_id"), str):
        raise RuntimeError("source response did not emit a tool_search_call")
    history = [
        *history,
        {
            "type": "tool_search_output",
            "call_id": search_calls[-1]["call_id"],
            "execution": "client",
            "status": "completed",
            "tools": [deferred_tool],
        },
    ]
    prompt = "What exact opaque probe value was in the discovered tool description? Output only that value."
    variants = {
        "same_account_full": (source, history),
        "different_account_full": (target, history),
        "different_account_strip_ids": (target, _without_ids(history)),
        "different_account_omit_reasoning": (target, _without_types(history, {"reasoning"})),
        "different_account_omit_tool_search": (
            target,
            _without_types(history, {"tool_search_call", "tool_search_output"}),
        ),
    }
    rows = []
    for name, (credential, items) in variants.items():
        result = _request(
            credential,
            _continuation_payload(model=model, history=items, prompt=prompt, tools=[search_tool]),
            client_version=client_version,
        )
        rows.append(_summary(name, result, expected=marker))
    return {
        "source_item_types": [item.get("type") for item in history],
        "marker_sha256": _sha256(marker),
        "variants": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--client-version", default="0.154.0")
    args = parser.parse_args()
    required = {
        name: os.environ.get(name)
        for name in (
            "CODEX_PORTABILITY_SOURCE_TOKEN",
            "CODEX_PORTABILITY_SOURCE_ACCOUNT_ID",
            "CODEX_PORTABILITY_TARGET_TOKEN",
            "CODEX_PORTABILITY_TARGET_ACCOUNT_ID",
        )
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error(f"missing environment variables: {', '.join(missing)}")
    source = (required["CODEX_PORTABILITY_SOURCE_ACCOUNT_ID"], required["CODEX_PORTABILITY_SOURCE_TOKEN"])
    target = (required["CODEX_PORTABILITY_TARGET_ACCOUNT_ID"], required["CODEX_PORTABILITY_TARGET_TOKEN"])
    if source[0] == target[0]:
        parser.error("source and target account IDs must differ")
    artifact = {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": ENDPOINT,
        "model": args.model,
        "client_version": args.client_version,
        "source_account_id_sha256": _sha256(source[0]),
        "target_account_id_sha256": _sha256(target[0]),
        "request_invariants": {"store": False, "previous_response_id": False, "via_codex_lb": False},
        "experiments": {
            "reasoning": _reasoning_experiment(source, target, model=args.model, client_version=args.client_version),
            "web_search": _web_search_experiment(source, target, model=args.model, client_version=args.client_version),
            "tool_search": _tool_search_experiment(
                source, target, model=args.model, client_version=args.client_version
            ),
        },
        "privacy": {
            "contains_access_token": False,
            "contains_raw_model_text": False,
            "contains_ciphertext": False,
            "contains_account_identifier": False,
            "contains_database_record": False,
        },
    }
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(args.artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
