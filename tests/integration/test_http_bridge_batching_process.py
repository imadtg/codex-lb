"""Public-process accumulation regression with real streaming and SQLite."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("spool_format", ["rows_v1", "chunks_v2"])
def test_paced_transcript_batching_process(spool_format, tmp_path):
    if importlib.util.find_spec("prometheus_client") is None:
        pytest.skip("requires the optional metrics extra for batch observations")
    root = Path(__file__).resolve().parents[2]
    checkout = Path(os.environ.get("CODEX_LB_BLACKBOX_CHECKOUT", str(root)))
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/probe_http_bridge_batching.py"),
            "--checkout",
            str(checkout),
            "--artifact",
            str(tmp_path),
            "--format",
            spool_format,
            "--expect-batching",
            "--interrupt",
            "--concurrent",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}\nArtifacts: {tmp_path}"
