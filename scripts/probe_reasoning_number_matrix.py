"""Measure hidden-number continuation across account and projection variants.

The source turn chooses a number only in hidden reasoning and replies READY.
Each retained source prefix is then continued independently through four cases:
same-account full history, different-account full history, different-account
history with top-level IDs unlinked, and different-account history without the
reasoning item. Only parsed integers and redacted status/statistics are saved.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from probe_cross_account_context_portability import (
    _request,
    _sha256,
    _without_ids,
    _without_types,
)

_NUMBER_RE = re.compile(r"(?<!\d)(?:100|[1-9][0-9]?)(?!\d)")
_CASES = (
    "same_account_full",
    "different_account_full",
    "different_account_strip_ids",
    "different_account_omit_reasoning",
)


def _number(text: str) -> int | None:
    stripped = text.strip()
    if stripped.isdigit() and 1 <= int(stripped) <= 100:
        return int(stripped)
    matches = [int(value) for value in _NUMBER_RE.findall(stripped)]
    return matches[-1] if len(matches) == 1 else None


def _payload(model: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": "Follow the user exactly. Output only the committed integer.",
        "input": [
            *history,
            {
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": "What exact integer from 1 to 100 did you commit to? Output only that integer.",
                }],
            },
        ],
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "low"},
        "store": False,
        "stream": True,
    }


def _source_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "instructions": "Follow the user exactly.",
        "input": [{
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": (
                    "Choose one whole number uniformly at random from 1 through 100. Decide it only in your hidden "
                    "reasoning and commit to it. Do not reveal it or any clue now. Reply exactly READY."
                ),
            }],
        }],
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "medium"},
        "store": False,
        "stream": True,
    }


def _continuation(credential: tuple[str, str], model: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    result = _request(credential, _payload(model, history), client_version="0.156.0")
    result["parsed_number"] = _number(result["text"])
    result.pop("output", None)
    result.pop("text", None)
    return result


def _pearson(xs: list[int], ys: list[int]) -> float | None:
    if len(xs) < 2:
        return None
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    denominator_x = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    denominator_y = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    return numerator / (denominator_x * denominator_y) if denominator_x and denominator_y else None


def _rank(values: list[int]) -> list[float]:
    positions: dict[int, list[int]] = {}
    for index, value in enumerate(sorted(values)):
        positions.setdefault(value, []).append(index + 1)
    average_rank = {value: statistics.fmean(ranks) for value, ranks in positions.items()}
    return [average_rank[value] for value in values]


def _mutual_information(xs: list[int], ys: list[int]) -> float | None:
    if not xs:
        return None
    joint = Counter(zip(xs, ys, strict=True))
    x_counts = Counter(xs)
    y_counts = Counter(ys)
    total = len(xs)
    return sum(
        count / total * math.log2(count * total / (x_counts[x] * y_counts[y]))
        for (x, y), count in joint.items()
    )


def _distribution(values: list[int]) -> dict[str, Any]:
    counts = Counter(values)
    total = len(values)
    probabilities = [counts[value] / total for value in range(1, 101)] if total else []
    return {
        "n": total,
        "mean": statistics.fmean(values) if values else None,
        "stdev": statistics.pstdev(values) if len(values) > 1 else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "entropy_bits": -sum(p * math.log2(p) for p in probabilities if p),
        "counts": {str(value): count for value, count in sorted(counts.items())},
    }


def _analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    numbers = {case: [row[case]["parsed_number"] for row in rows] for case in _CASES}
    result: dict[str, Any] = {
        "distributions": {
            case: _distribution([n for n in values if n is not None])
            for case, values in numbers.items()
        }
    }
    baseline = numbers["same_account_full"]
    comparisons: dict[str, Any] = {}
    for case in _CASES[1:]:
        paired = [
            (left, right)
            for left, right in zip(baseline, numbers[case], strict=True)
            if left is not None and right is not None
        ]
        xs = [left for left, _ in paired]
        ys = [right for _, right in paired]
        comparisons[case] = {
            "paired_n": len(paired),
            "exact_match_rate": sum(left == right for left, right in paired) / len(paired) if paired else None,
            "mean_absolute_difference": (
                statistics.fmean(abs(left - right) for left, right in paired) if paired else None
            ),
            "pearson_r": _pearson(xs, ys),
            "spearman_r": _pearson(_rank(xs), _rank(ys)) if len(paired) > 1 else None,
            "mutual_information_bits": _mutual_information(xs, ys),
        }
    result["paired_comparisons_to_same_account"] = comparisons
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--model", default="gpt-5.6-luna")
    args = parser.parse_args()
    if args.repetitions <= 0:
        parser.error("--repetitions must be positive")
    names = (
        "CODEX_PORTABILITY_SOURCE_ACCOUNT_ID",
        "CODEX_PORTABILITY_SOURCE_TOKEN",
        "CODEX_PORTABILITY_TARGET_ACCOUNT_ID",
        "CODEX_PORTABILITY_TARGET_TOKEN",
    )
    values = {name: os.environ.get(name) for name in names}
    if any(not value for value in values.values()):
        parser.error(f"missing environment variables: {', '.join(name for name in names if not values[name])}")
    source = (values[names[0]], values[names[1]])
    target = (values[names[2]], values[names[3]])
    if source[0] == target[0]:
        parser.error("source and target accounts must differ")

    rows: list[dict[str, Any]] = []
    attempts = 0
    while len(rows) < args.repetitions and attempts < args.repetitions * 2:
        attempts += 1
        first = _request(source, _source_payload(args.model), client_version="0.156.0")
        history = first.get("output", [])
        if first["http_status"] != 200 or not any(item.get("type") == "reasoning" for item in history):
            print(
                json.dumps(
                    {"attempt": attempts, "source_status": first["http_status"], "source_reasoning": False}
                ),
                flush=True,
            )
            continue
        cases = {
            "same_account_full": (source, history),
            "different_account_full": (target, history),
            "different_account_strip_ids": (target, _without_ids(history)),
            "different_account_omit_reasoning": (target, _without_types(history, {"reasoning"})),
        }
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                case: pool.submit(_continuation, credential, args.model, retained_history)
                for case, (credential, retained_history) in cases.items()
            }
            row = {case: future.result() for case, future in futures.items()}
        row["trial"] = len(rows) + 1
        rows.append(row)
        print(
            json.dumps({"trial": row["trial"], "numbers": {case: row[case]["parsed_number"] for case in _CASES}}),
            flush=True,
        )

    artifact = {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": "https://chatgpt.com/backend-api/codex/responses",
        "model": args.model,
        "client_version": "0.156.0",
        "requested_repetitions": args.repetitions,
        "completed_repetitions": len(rows),
        "attempts": attempts,
        "source_account_id_sha256": _sha256(source[0]),
        "target_account_id_sha256": _sha256(target[0]),
        "cases": list(_CASES),
        "analysis": _analysis(rows),
        "trials": rows,
        "privacy": {
            "contains_access_token": False,
            "contains_raw_reasoning": False,
            "contains_ciphertext": False,
            "contains_account_identifier": False,
            "contains_raw_model_text": False,
        },
    }
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(args.artifact)
    return 0 if len(rows) == args.repetitions else 2


if __name__ == "__main__":
    raise SystemExit(main())
