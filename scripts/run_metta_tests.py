#!/usr/bin/env python3
"""Run this repo's MeTTa tests with the pinned PeTTa.

Stricter than the upstream runner (external/hyperon-miner/scripts/run-tests.py):

* A test FAILS on a non-zero exit code, a ❌ marker, or a ``(partial ...)``
  result (PeTTa's sign of a call with the wrong number of arguments).
* A test FAILS if it contains a top-level ``(assertEqual ...)`` without ``!``.
  Those lines are never executed (docs/01-problem.md, Issue 3), so they give
  false confidence.
* A test FAILS if it executes zero assertions.

Usage:  python3 scripts/run_metta_tests.py [paths...]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PETTA = ROOT / ".petta" / "run.sh"
TIMEOUT = int(os.environ.get("METTA_TEST_TIMEOUT", "900"))
ANSI = re.compile(r"\x1b\[[0-9;]*m")
INERT = re.compile(r"^\((assert\w*|test)\s", re.M)       # top-level, no "!"
LIVE = re.compile(r"^!\((assert\w*|test)\s", re.M)


def discover(args: list[str]) -> list[Path]:
    if args:
        return [Path(a).resolve() for a in args]
    return sorted(p for p in (ROOT / "experiments").rglob("tests/test-*.metta"))


def run(path: Path) -> tuple[bool, str, float]:
    source = path.read_text()
    inert = INERT.findall(source)
    if inert:
        return False, f"{len(inert)} top-level assertion(s) without '!' are never executed", 0.0
    expected = len(LIVE.findall(source))
    if expected == 0:
        return False, "no executable assertions", 0.0

    env = dict(os.environ, LANG="C.UTF-8", LC_ALL="C.UTF-8")
    start = time.time()
    try:
        proc = subprocess.run(["bash", str(PETTA), path.name], cwd=path.parent, env=env,
                              capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {TIMEOUT}s", time.time() - start
    elapsed = time.time() - start
    out = ANSI.sub("", proc.stdout + proc.stderr)
    passed = out.count("✅")
    if proc.returncode != 0 or "❌" in out:
        bad = [l for l in out.splitlines() if "❌" in l][:3]
        return False, "\n".join(bad) or f"exit code {proc.returncode}", elapsed
    if re.search(r"^\(partial ", out, re.M):
        return False, "a call returned (partial ...): wrong number of arguments", elapsed
    return True, f"{passed} ✅ / {expected} assertions", elapsed


def main() -> int:
    if not PETTA.exists():
        print("PeTTa not found. Run ./setup.sh first.", file=sys.stderr)
        return 2
    tests = discover(sys.argv[1:])
    failures = 0
    for t in tests:
        ok, msg, secs = run(t)
        failures += not ok
        tag = "\033[92mPASS\033[0m" if ok else "\033[91mFAIL\033[0m"
        print(f"{tag} {t.relative_to(ROOT)}  ({secs:.1f}s)  {msg}")
    print(f"\n{len(tests) - failures}/{len(tests)} MeTTa test files passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
