"""Run one immutable public-process probe against independent checkouts.

Writes durable JSON summaries and wire reports. Scenario failures are evidence,
not permission to weaken assertions. Does not import application code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, action="append", required=True)
    parser.add_argument("--variant", action="append", help="Repeat for a subset; omitted runs the entire catalog.")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--temporary-root", type=Path, help="Disposable database directory; defaults to artifact/tmp.")
    args = parser.parse_args()
    catalog = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/continuity_scenarios.json").read_text())
    scenarios = {scenario["id"]: scenario for scenario in catalog}
    variants = args.variant or list(scenarios)
    if any(variant not in scenarios for variant in variants):
        parser.error("unknown scenario; consult tests/fixtures/continuity_scenarios.json")
    artifact = args.artifact.resolve()
    artifact.mkdir(parents=True, exist_ok=True)
    temporary = (args.temporary_root or artifact / "tmp").resolve()
    temporary.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("probe_historical_prefix.py").read_bytes()
    probe = artifact / "probe.py"
    if probe.exists() and probe.read_bytes() != source:
        parser.error("artifact directory belongs to a different probe; choose a new directory")
    probe.write_bytes(source)
    results = []
    env = {**os.environ, "TMPDIR": str(temporary)}
    for checkout_index, checkout in enumerate(args.checkout):
        checkout = checkout.resolve()
        for variant in variants:
            case_dir = artifact / f"checkout-{checkout_index}" / variant
            case_dir.mkdir(parents=True, exist_ok=True)
            with (case_dir / "runner.log").open("w") as output:
                try:
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            str(probe),
                            "--checkout",
                            str(checkout),
                            "--variant",
                            variant,
                            "--artifact",
                            str(case_dir),
                        ],
                        env=env,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                    exit_code = process.wait(timeout=240)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    exit_code = 124
            report_path = case_dir / "report.json"
            report = json.loads(report_path.read_text()) if report_path.exists() else {}
            row = {
                "checkout": str(checkout),
                "variant": variant,
                "evidence": scenarios[variant],
                "probe_sha256": hashlib.sha256(source).hexdigest(),
                "commit": report.get("checkout_commit"),
                "dirty": report.get("checkout_dirty"),
                "exit_code": exit_code,
                "outcome": "pass"
                if exit_code == 0 and report.get("passed")
                else "scenario_failure"
                if report.get("phase") == "scenario"
                else "setup_failure",
                "failure": report.get("failure"),
                "accounts": [call["account"] for call in report.get("calls", [])],
                "artifact": str(case_dir),
            }
            results.append(row)
            (artifact / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps(row), flush=True)
    return int(any(row["outcome"] != "pass" for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
