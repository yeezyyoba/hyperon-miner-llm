"""Integration: the fixed entry point runs end to end on the pinned PeTTa."""
from __future__ import annotations

import os
import re
import subprocess

import pytest


@pytest.mark.petta
def test_fixed_entry_point_scores_patterns(root):
    env = dict(os.environ, LANG="C.UTF-8", LC_ALL="C.UTF-8")
    proc = subprocess.run(["bash", ".petta/run.sh", "run_miner.metta"], cwd=root, env=env,
                          capture_output=True, text=True, timeout=600)
    out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout)
    assert proc.returncode == 0
    assert "(partial pattern-miner" not in out
    scored = re.findall(r"^\(surprisingnessOf .* ([0-9.]+)\)$", out, re.M)
    assert len(scored) == 11          # 12 frequent patterns, 1 dropped by Issue 4
    assert all(0.0 <= float(s) <= 1.0 for s in scored)
