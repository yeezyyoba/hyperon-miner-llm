"""Cheap guards that keep the reproducibility fixes from silently regressing."""
from __future__ import annotations

import re
import subprocess

PINNED_MINER = "7461878"
PINNED_PETTA = "9e5929ad577121bfcf6287d4de6d7649f1d98b91"


def test_submodule_is_pinned_to_petta_main_commit(root):
    head = subprocess.run(["git", "-C", str(root / "external/hyperon-miner"), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    if head.returncode != 0:
        import pytest
        pytest.skip("submodule not initialised")
    assert head.stdout.startswith(PINNED_MINER)


def test_setup_pins_petta_commit(root):
    setup = (root / "setup.sh").read_text()
    assert PINNED_PETTA in setup
    assert "origin/HEAD" not in setup, "PeTTa must not track HEAD (docs/01-problem.md, Issue 2)"


def test_upstream_patch_uses_same_petta_pin(root):
    patch = (root / "patches/0001-fix-run-miner-entrypoint-and-pin-petta.patch").read_text()
    assert PINNED_PETTA in patch


def test_entry_point_calls_pattern_miner_with_nine_arguments(root):
    """Issue 1: upstream passed 8 arguments to a 9-argument function."""
    src = (root / "run_miner.metta").read_text()
    call = re.search(r"^!\(pattern-miner (.*)\)\s*$", src, re.M)
    assert call, "entry point must call pattern-miner"
    assert len(call.group(1).split()) == 9


def test_entry_point_imports_generic_frequent_miner(root):
    src = (root / "run_miner.metta").read_text()
    assert "frequent-pattern-miner-generic" in src
    assert not re.search(r"frequent-pattern-miner/frequent-pattern-miner\)", src)


def test_no_inert_assertions_in_our_metta_tests(root):
    """Issue 3: a top-level assertion without '!' is never executed by PeTTa."""
    for f in (root / "experiments").rglob("tests/test-*.metta"):
        assert not re.search(r"^\((assert\w*|test)\s", f.read_text(), re.M), f
