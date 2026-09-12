"""Offline replay diagnostics. Emits classifier decisions, never request values.

Run with `uv run python -m scripts.diagnose_continuity payload.json --stored-count N`.
The input file is private. Output includes only counts, source locations, and booleans.
No network, account mutations, model calls, or database writes are performed.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from types import FrameType
from typing import Any

from app.modules.proxy import replay_safety


def _false_return_sources() -> dict[int, str]:
    source = Path(replay_safety.__file__).read_text()
    tree = ast.parse(source)
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for child in node.body:
                if (
                    isinstance(child, ast.Return)
                    and isinstance(child.value, ast.Constant)
                    and child.value.value is False
                ):
                    result[child.lineno] = ast.unparse(node.test)
    return result


def classify(payload: dict[str, Any]) -> dict[str, Any]:
    """Trace the actual classifier, without copying locals or payload-derived names.

    False returns in nested helpers are observations, not necessarily fatal:
    some helpers deliberately test whether account-owned state is present.
    The top-level result is authoritative. Tracing is scoped and restored.
    """
    returns: Counter[tuple[str, int]] = Counter()
    classifier_file = replay_safety.__file__

    def trace(frame: FrameType, event: str, value: Any):
        if frame.f_code.co_filename != classifier_file:
            return None
        if event == "return" and value is False:
            returns[(frame.f_code.co_name, frame.f_lineno)] += 1
        return trace

    previous_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        accepted = replay_safety.responses_payload_is_account_neutral_fresh_replay(payload)
    finally:
        sys.settrace(previous_trace)
    sources = _false_return_sources()
    return {
        "account_neutral": accepted,
        "rejection_reason": replay_safety.responses_payload_replay_rejection_reason(payload),
        "false_return_observations": [
            {"function": name, "line": line, "condition": sources.get(line, "return False"), "count": count}
            for (name, line), count in returns.items()
        ],
    }


def diagnose(payload: dict[str, Any], stored_count: int | None = None) -> dict[str, Any]:
    items = payload.get("input")
    report = {
        "input_count": len(items) if isinstance(items, list) else None,
        "has_previous_response": bool(payload.get("previous_response_id")),
        "has_conversation": bool(payload.get("conversation")),
        "raw": classify(payload),
    }
    if stored_count is not None and isinstance(items, list):
        projection = replay_safety.project_responses_input_for_account_neutral_fresh_replay(
            items, stored_count=stored_count
        )
        report["projection_available"] = projection is not None
        if projection is not None:
            projected = {**payload, "input": projection.input_items}
            projected.pop("previous_response_id", None)
            report["projected_input_count"] = len(projection.input_items)
            report["projected"] = classify(projected)
            report["projection_note"] = "Hypothetical only: stored-prefix equality and dispatch safety are not proven."
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--stored-count", type=int)
    args = parser.parse_args()
    payload = json.loads(args.payload.read_text())
    if not isinstance(payload, dict):
        parser.error("Expected a Responses request object")
    print(json.dumps(diagnose(payload, args.stored_count), indent=2))


if __name__ == "__main__":
    main()
