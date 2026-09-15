"""Probe whether an OpenAI-encrypted Codex agent delivery crosses accounts.

This script talks directly to OpenAI. It does not import codex-lb, read its
database, or create a persistent response. It sends both the supplied item and
a one-character-corrupted control, so running it consumes two requests.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_MARKER = "DECRYPTED"


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _load_agent_message(path: Path) -> dict[str, Any]:
    item = json.loads(path.read_text())
    if not isinstance(item, dict) or item.get("type") != "agent_message":
        raise ValueError("--item must contain one agent_message object")
    allowed = {
        "type",
        "id",
        "author",
        "recipient",
        "content",
        "internal_chat_message_metadata_passthrough",
    }
    if set(item) - allowed or not _nonblank(item.get("author")) or not _nonblank(item.get("recipient")):
        raise ValueError("agent_message routing or fields do not match the bounded probe shape")
    content = item.get("content")
    if not isinstance(content, list) or len(content) != 2:
        raise ValueError("agent_message content must be [input_text, encrypted_content]")
    envelope, encrypted = content
    if not (
        isinstance(envelope, dict)
        and set(envelope) == {"type", "text"}
        and envelope.get("type") == "input_text"
        and _nonblank(envelope.get("text"))
    ):
        raise ValueError("first content part must be an exact nonblank input_text envelope")
    if not (
        isinstance(encrypted, dict)
        and set(encrypted) == {"type", "encrypted_content"}
        and encrypted.get("type") == "encrypted_content"
        and _nonblank(encrypted.get("encrypted_content"))
    ):
        raise ValueError("second content part must be exact nonblank encrypted_content")
    return {key: value for key, value in item.items() if key != "id"}


def _corrupt_ciphertext(item: dict[str, Any]) -> dict[str, Any]:
    corrupted = copy.deepcopy(item)
    ciphertext = corrupted["content"][1]["encrypted_content"]
    index = len(ciphertext) // 2
    replacement = "A" if ciphertext[index] != "A" else "B"
    corrupted["content"][1]["encrypted_content"] = ciphertext[:index] + replacement + ciphertext[index + 1 :]
    return corrupted


def _events_from_body(body: str) -> list[dict[str, Any]]:
    stripped = body.lstrip()
    if stripped.startswith(("{", "[")):
        parsed = json.loads(body)
        values = parsed if isinstance(parsed, list) else [parsed]
        return [value for value in values if isinstance(value, dict)]
    events: list[dict[str, Any]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        if data and data != "[DONE]":
            value = json.loads(data)
            if isinstance(value, dict):
                events.append(value)
    return events


def _error_codes(value: object) -> list[str]:
    found: list[str] = []
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            code = current.get("code")
            if isinstance(code, str):
                found.append(code)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return found


def _output_texts(value: object) -> list[str]:
    found: list[str] = []
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            if current.get("type") == "output_text" and isinstance(current.get("text"), str):
                found.append(current["text"])
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return found


def _run_request(
    *,
    token: str,
    account_id: str,
    client_version: str,
    model: str,
    marker: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "instructions": f"Read the supplied collaboration delivery, then reply with exactly {marker}",
        "input": [item],
        "store": False,
        "stream": True,
    }
    upstream_request = request.Request(
        DEFAULT_ENDPOINT,
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
        with request.urlopen(upstream_request, timeout=120) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except error.URLError as exc:
        return {
            "http_status": None,
            "event_types": [],
            "error_codes": [],
            "saw_response_created": False,
            "completed": False,
            "controlled_output_seen": False,
            "transport_error_type": type(exc.reason).__name__,
        }
    try:
        events = _events_from_body(body)
    except (json.JSONDecodeError, ValueError):
        return {
            "http_status": status,
            "event_types": [],
            "error_codes": [],
            "saw_response_created": False,
            "completed": False,
            "controlled_output_seen": False,
            "response_parse_error": True,
        }
    event_types = [event_type for event in events if isinstance((event_type := event.get("type")), str)]
    texts = _output_texts(events)
    return {
        "http_status": status,
        "event_types": event_types,
        "error_codes": sorted(set(_error_codes(events))),
        "saw_response_created": "response.created" in event_types,
        "completed": "response.completed" in event_types,
        "controlled_output_seen": marker in texts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item", type=Path, required=True, help="Sensitive agent_message JSON kept outside Git")
    parser.add_argument("--artifact", type=Path, required=True, help="Redacted JSON result to write")
    parser.add_argument("--source-account-id", required=True, help="Source ID; only its SHA-256 is recorded")
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--client-version", default="0.154.0")
    parser.add_argument("--marker", default=DEFAULT_MARKER)
    parser.add_argument(
        "--allow-same-account-control",
        action="store_true",
        help="Permit target == source for a separate same-account control run",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without network requests")
    args = parser.parse_args()

    try:
        item = _load_agent_message(args.item)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    ciphertext = item["content"][1]["encrypted_content"]
    item_digest = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": DEFAULT_ENDPOINT,
        "model": args.model,
        "client_version": args.client_version,
        "item_sha256": item_digest,
        "ciphertext_sha256": hashlib.sha256(ciphertext.encode()).hexdigest(),
        "ciphertext_bytes": len(ciphertext.encode()),
        "source_account_id_sha256": hashlib.sha256(args.source_account_id.encode()).hexdigest(),
        "raw_item_retained": False,
        "dry_run": args.dry_run,
    }
    if not args.dry_run:
        token = os.environ.get("CODEX_PORTABILITY_TARGET_TOKEN")
        account_id = os.environ.get("CODEX_PORTABILITY_TARGET_ACCOUNT_ID")
        if not token or not account_id:
            parser.error(
                "CODEX_PORTABILITY_TARGET_TOKEN and CODEX_PORTABILITY_TARGET_ACCOUNT_ID are required"
            )
        if account_id == args.source_account_id and not args.allow_same_account_control:
            parser.error("target account must differ from source; use --allow-same-account-control explicitly")
        artifact["account_relation"] = "same" if account_id == args.source_account_id else "different"
        artifact["target_account_id_sha256"] = hashlib.sha256(account_id.encode()).hexdigest()
        artifact["valid"] = _run_request(
            token=token,
            account_id=account_id,
            client_version=args.client_version,
            model=args.model,
            marker=args.marker,
            item=item,
        )
        artifact["corrupted_control"] = _run_request(
            token=token,
            account_id=account_id,
            client_version=args.client_version,
            model=args.model,
            marker=args.marker,
            item=_corrupt_ciphertext(item),
        )
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(args.artifact)
    if args.dry_run:
        return 0
    valid = artifact["valid"]
    corrupt = artifact["corrupted_control"]
    return int(
        not (
            valid["completed"]
            and valid["controlled_output_seen"]
            and not corrupt["completed"]
            and "invalid_encrypted_content" in corrupt["error_codes"]
        )
    )


if __name__ == "__main__":
    sys.exit(main())
