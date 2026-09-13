"""Public-process hard-owner recovery probes with disposable accounts and data."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("mode", ["unavailable", "recover", "healthy"])
def test_hard_owner_wait_public_process(mode, tmp_path):
    root = Path(__file__).resolve().parents[2]
    checkout = Path(os.environ.get("CODEX_LB_BLACKBOX_CHECKOUT", str(root)))
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/probe_hard_owner_wait.py"),
            "--checkout",
            str(checkout),
            "--mode",
            mode,
            "--artifact",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}\nArtifacts: {tmp_path}"


def test_hard_owner_wait_after_process_restart(tmp_path):
    root = Path(__file__).resolve().parents[2]
    checkout = Path(os.environ.get("CODEX_LB_BLACKBOX_CHECKOUT", str(root)))
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/probe_hard_owner_wait.py"),
            "--checkout",
            str(checkout),
            "--mode",
            "unavailable",
            "--restart",
            "--artifact",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}\nArtifacts: {tmp_path}"
