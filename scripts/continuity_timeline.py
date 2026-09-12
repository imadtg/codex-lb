"""Export bounded, redacted v1 continuity telemetry from text or JSON logs.

This reads log files only. It does not contact providers or open application databases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from pathlib import Path

import app
from app.modules.proxy.continuity_diagnostics import DECISION_REASONS, DECISION_STAGES, correlation_hash

_EVENTS = {
    "continuity_decision",
    "continuity_selection",
    "continuity_candidate",
    "continuity_candidate_snapshot",
    "continuity_proof_mutation",
    "continuity_terminal",
    "continuity_retry",
}
_IDENTIFIERS = {
    "request",
    "archive_request",
    "observer_request",
    "scope",
    "session",
    "account",
    "selected",
    "required",
    "model",
}
_NUMBERS = {
    "observed_at_ns",
    "monotonic_ns",
    "process",
    "input_count",
    "stored_count",
    "candidates",
    "excluded",
    "primary_used",
    "secondary_used",
    "reset_at",
    "cooldown_until",
    "priority_used",
    "priority_secondary_used",
    "health_tier",
    "inflight_streams",
    "observed_at",
    "total",
    "omitted",
    "owner_epoch",
    "response_events",
    "replay_count",
}
_BOOLEANS = {
    "fingerprint_present",
    "manifest_present",
    "owner_restricted",
    "limit_scoped",
    "ignore_standard_quota",
    "applied",
    "proof_preserved",
    "downstream_visible",
    "hard_owner",
    "fresh_switch_allowed",
    "require_preferred",
    "account_bound_body",
    "operation_present",
    "hard_anchor",
    "owner_excluded",
}
_ENUM_VALUES = {
    "stage": DECISION_STAGES,
    "reason": DECISION_REASONS,
    "outcome": {"selected", "unavailable"},
    "status": {"active", "paused", "rate_limited", "quota_exceeded", "deactivated", "reauth_required"},
    "action": {"rebind_session_account", "deny_response_anchor", "retire_response_anchor"},
    "event": {"response.completed", "response.failed", "response.incomplete", "error", "other"},
    "error_code": {
        "hard_affinity_owner_excluded",
        "hard_affinity_saturated",
        "continuity_owner_unavailable",
        "continuity_owner_policy_conflict",
        "usage_limit_reached",
        "conversation_owner_unavailable",
        "continuity_owner_conflict",
    },
}
_MARKER = re.compile(r"observed_at_ns=\d+ monotonic_ns=\d+ process=\d+ (continuity_[a-z_]+) version=1(?:\s|$)")


def parse_event(line: str) -> dict[str, str] | None:
    """Export only known fields; unexpected string values never pass through."""
    if line.lstrip().startswith("{"):
        try:
            record = json.loads(line)
        except ValueError:
            return None
        if not isinstance(record, dict) or not isinstance(record.get("message"), str):
            return None
        line = record["message"]
    match = _MARKER.search(line)
    if match is None or match[1] not in _EVENTS:
        return None
    result = {"record": match[1], "version": "1"}
    for key, value in re.findall(r"\b([a-z_]+)=([^\s]+)", line[match.start() :]):
        if key in _IDENTIFIERS and re.fullmatch(r"sha256:[0-9a-f]{12}|None", value):
            result[key] = value
        elif key in _NUMBERS and re.fullmatch(r"-?\d+(?:\.\d+)?|None", value):
            result[key] = value
        elif key in _BOOLEANS and value in {"True", "False", "None"}:
            result[key] = value
        elif key in _ENUM_VALUES:
            if value in _ENUM_VALUES[key] or value == "None":
                result[key] = value
            elif key == "error_code" and re.fullmatch(r"sha256:[0-9a-f]{12}", value):
                result[key] = value
            else:
                result[key] = "unrecognized"
    return result


def implementation_manifest() -> dict[str, object]:
    """Fingerprint installed proxy source, not private configuration or data."""
    proxy_root = Path(app.__file__).parent / "modules" / "proxy"
    digest = hashlib.sha256()
    for path in sorted(proxy_root.rglob("*.py")):
        digest.update(str(path.relative_to(proxy_root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {
        "codex_lb_version": app.__version__,
        "python": platform.python_version(),
        "proxy_source_sha256": digest.hexdigest(),
        "telemetry_schema": 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="*", type=Path)
    parser.add_argument("--request-id", help="Select the hash of this request ID; raw ID is never exported")
    parser.add_argument("--max-events", type=int, default=10000)
    args = parser.parse_args()
    if args.max_events < 1:
        parser.error("--max-events must be positive")
    events = []
    request = correlation_hash(args.request_id)
    truncated = False
    for path in args.logs:
        with path.open(errors="replace") as source:
            for line in source:
                event = parse_event(line)
                if event is None or (
                    request is not None and request not in (event.get("request"), event.get("archive_request"))
                ):
                    continue
                if len(events) == args.max_events:
                    truncated = True
                    break
                events.append(event)
        if truncated:
            break
    print(
        json.dumps(
            {
                "implementation": implementation_manifest(),
                "events": events,
                "truncated": truncated,
                "note": "File order retained; missing events do not prove success.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
