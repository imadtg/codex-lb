"""Public-process probes. The same script can target an unmodified checkout.

No imported application helpers or internal state writes create these scenarios.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
SCENARIOS = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures/continuity_scenarios.json").read_text()
)


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
