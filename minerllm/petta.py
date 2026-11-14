"""Run MeTTa scripts on the pinned PeTTa and parse what the miner prints."""
from __future__ import annotations

import os
import re
import site
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .patterns import canonical
from .sexpr import parse

ROOT = Path(__file__).resolve().parent.parent
PETTA_RUN = ROOT / ".petta" / "run.sh"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
RESULT_LINE = re.compile(r"^\((supportOf|surprisingnessOf) ", re.M)


class PettaNotInstalled(RuntimeError):
    pass


@dataclass
class MinedPattern:
    pattern: str                    # canonical form (see patterns.canonical)
    raw: str                        # as printed by the miner
    support: int | None = None
    surprisingness: float | None = None


@dataclass
class PettaRun:
    returncode: int
    seconds: float
    stdout: str
    stderr: str
    timed_out: bool = False
    patterns: list[MinedPattern] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and "(partial " not in self.stdout

    def by_pattern(self) -> dict[str, MinedPattern]:
        return {p.pattern: p for p in self.patterns}


def parse_results(stdout: str) -> list[MinedPattern]:
    """Collect ``(supportOf P n)`` / ``(surprisingnessOf P s)`` lines, merged per pattern."""
    merged: dict[str, MinedPattern] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not RESULT_LINE.match(line):
            continue
        try:
            tag, pattern, value = parse(line)
        except ValueError:
            continue
        key = canonical(pattern)
        mp = merged.setdefault(key, MinedPattern(pattern=key, raw=line))
        if tag == "supportOf":
            mp.support = int(value)
        else:
            mp.surprisingness = float(value)
    return list(merged.values())


def python_path(existing: str = "") -> str:
    """PYTHONPATH for PeTTa's embedded Python (janus).

    janus runs the Python that SWI-Prolog was built with, not the caller's
    virtualenv, so packages installed in the venv (scipy, requests, ...) would be
    invisible to py-call. We pass this repo plus the current interpreter's
    site-packages. This only works when both Pythons have the same minor version
    (check with `make doctor`).
    """
    paths = [str(ROOT)]
    try:
        paths += site.getsitepackages()
    except AttributeError:          # very old virtualenv
        pass
    paths += [p for p in sys.path if p.endswith("site-packages")]
    if existing:
        paths.append(existing)
    seen: dict[str, None] = {}
    for p in paths:
        seen.setdefault(p, None)
    return os.pathsep.join(seen)


def run_script(script: str | Path, timeout: float = 1800, cwd: str | Path | None = None,
               env: dict | None = None) -> PettaRun:
    """Run one MeTTa file in a fresh PeTTa process (fresh state: see Issue 5)."""
    if not PETTA_RUN.exists():
        raise PettaNotInstalled("pinned PeTTa not found — run ./setup.sh")
    script = Path(script).resolve()
    full_env = dict(os.environ, LANG="C.UTF-8", LC_ALL="C.UTF-8")
    full_env["PYTHONPATH"] = python_path(full_env.get("PYTHONPATH", ""))
    if env:
        full_env.update(env)
    start = time.time()
    try:
        proc = subprocess.run(["bash", str(PETTA_RUN), str(script)],
                              cwd=str(cwd or script.parent), env=full_env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return PettaRun(-1, time.time() - start, ANSI.sub("", out), "", timed_out=True)
    stdout = ANSI.sub("", proc.stdout)
    return PettaRun(proc.returncode, time.time() - start, stdout, ANSI.sub("", proc.stderr),
                    patterns=parse_results(stdout))
