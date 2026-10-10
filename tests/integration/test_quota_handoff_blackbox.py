"""Public-process probes. The same script can target an unmodified checkout.

No imported application helpers or internal state writes create these scenarios.
"""

import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
SCENARIOS = json.loads((Path(__file__).resolve().parents[1] / "fixtures/continuity_scenarios.json").read_text())


@pytest.mark.parametrize(
    "variant",
    [scenario["id"] for scenario in SCENARIOS],
)
def test_quota_handoff_public_process(variant, tmp_path):
    root = Path(__file__).resolve().parents[2]
    checkout = Path(os.environ.get("CODEX_LB_BLACKBOX_CHECKOUT", str(root)))
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/probe_historical_prefix.py"),
            "--checkout",
            str(checkout),
            "--variant",
            variant,
            "--artifact",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}\nArtifacts: {tmp_path}"


@pytest.mark.parametrize("variant", ["model_compaction_build_swap", "model_compaction_build_swap_ambiguous"])
@pytest.mark.timeout(240)
def test_model_compaction_continues_across_build_swap(variant, tmp_path):
    root = Path(__file__).resolve().parents[2]
    # Construct the exact unmodified base through git's read-only object API.
    # No branch, commit, application import, or test-only state mutation.
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    archive = subprocess.run(["git", "archive", "HEAD"], cwd=root, capture_output=True, check=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as files:
        files.extractall(baseline, filter="data")
    # The source archive excludes the runtime. This baseline uses the same
    # pinned dependencies; independently installed official builds have their
    # own interpreter in the process probe.
    (baseline / ".venv").symlink_to((root / ".venv").resolve(), target_is_directory=True)
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/probe_historical_prefix.py"),
            "--checkout",
            str(root),
            "--initial-checkout",
            str(baseline),
            "--return-checkout",
            str(baseline),
            "--variant",
            variant,
            "--artifact",
            str(tmp_path / "wire-evidence"),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}\nArtifacts: {tmp_path}"
