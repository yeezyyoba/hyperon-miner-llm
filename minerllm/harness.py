"""Run the miner from a config, save artefacts, and verify results against the oracle."""
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT, MinerConfig, render_upstream_script
from .datasets import load_atoms
from .oracle import Oracle
from .petta import PettaRun, run_script

RUNS = ROOT / "runs"


@dataclass
class Verification:
    checked: int = 0
    mismatches: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mismatches

    def to_dict(self) -> dict:
        return {"checked": self.checked, "ok": self.ok, "mismatches": self.mismatches[:20]}


def verify_supports(run: PettaRun, oracle: Oracle, fill_missing: bool = True) -> Verification:
    """Compare every support the miner printed with the oracle's count.

    Runs with a surprisingness mode print no supports; with ``fill_missing`` the
    oracle's value is filled in so downstream metrics always have a support.
    """
    v = Verification()
    for mp in run.patterns:
        truth = oracle.support(mp.pattern)
        if mp.support is None:
            if fill_missing:
                mp.support = truth
            continue
        v.checked += 1
        if mp.support != truth:
            v.mismatches.append({"pattern": mp.pattern, "miner": mp.support, "oracle": truth})
    return v


def save_run(run: PettaRun, cfg: MinerConfig, out_dir: Path, label: str,
             verification: Verification | None = None, extra: dict | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "label": label,
        "config": cfg.to_dict(),
        "ok": run.ok,
        "returncode": run.returncode,
        "timed_out": run.timed_out,
        "seconds": round(run.seconds, 3),
        "n_patterns": len(run.patterns),
        "patterns": [mp.__dict__ for mp in run.patterns],
        "verification": verification.to_dict() if verification else None,
        **(extra or {}),
    }
    path = out_dir / f"{label}.json"
    path.write_text(json.dumps(record, indent=2))
    (out_dir / f"{label}.stdout.txt").write_text(run.stdout)
    return path


def run_upstream(cfg: MinerConfig, out_dir: Path | None = None, label: str = "upstream",
                 verify: bool = True) -> tuple[PettaRun, Verification | None]:
    """Run the unmodified upstream miner (via the fixed entry point) for ``cfg``."""
    out_dir = (out_dir or RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{cfg.fingerprint()}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    script = out_dir / f"{label}.metta"
    script.write_text(render_upstream_script(cfg))
    run = run_script(script, timeout=cfg.timeout)
    verification = verify_supports(run, Oracle(load_atoms(cfg.dataset_path()))) if verify else None
    save_run(run, cfg, out_dir, label, verification)
    return run, verification


def read_trace(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _follow_trace(trace: Path, stop: threading.Event) -> None:
    """Print one short line per trace event while the miner runs (to stderr)."""
    seen = 0
    while not stop.is_set():
        time.sleep(1.0)
        events = read_trace(trace)
        for e in events[seen:]:
            ev, t = e["event"], f"[{e['t']:7.1f}s]"
            if ev == "llm_batch":
                what = (f"{e['provider']}/{e['model']}" + (" (cached)" if e.get("cached") else "")
                        if "provider" in e else f"FAILED -> heuristic ({e.get('failed', '')[:70]})")
                msg = f"LLM batch {e['batch']}/{e['of']}: {what}, {e['seconds']}s"
            elif ev == "select":
                msg = (f"level {e['level']}: {e['generated']} candidates, {e['unique']} unique, "
                       f"verifying {e['selected']}")
            elif ev == "verify":
                msg = f"level {e['level']}: {e['kept']} frequent patterns kept ({e['seconds']}s)"
            elif ev == "configure":
                msg = f"started: strategy={e['strategy']} budget={e['budget']}"
            else:
                continue
            print(f"{t} {msg}", file=sys.stderr, flush=True)
        seen = len(events)


def run_guided(cfg: MinerConfig, ranker, out_dir: Path | None = None, label: str | None = None,
               verify: bool = True, progress: bool = False) -> tuple[PettaRun, Verification | None, dict]:
    """Run the guided miner. Returns (run, oracle verification, trace summary)."""
    from .config import render_guided_script
    label = label or ranker.label
    out_dir = (out_dir or RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{cfg.fingerprint()}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = out_dir / f"{label}.trace.jsonl"
    run_json = out_dir / f"{label}.run.json"
    cache_dir = ranker.cache_dir
    if cache_dir and not Path(cache_dir).is_absolute():
        cache_dir = str(ROOT / cache_dir)
    run_json.write_text(json.dumps({**ranker.to_dict(), "cache_dir": cache_dir,
                                    "trace_path": str(trace),
                                    "dataset": str(cfg.dataset_path())}, indent=2))
    script = out_dir / f"{label}.metta"
    script.write_text(render_guided_script(cfg, run_json))
    stop = threading.Event()
    watcher = None
    if progress:
        watcher = threading.Thread(target=_follow_trace, args=(trace, stop), daemon=True)
        watcher.start()
    try:
        run = run_script(script, timeout=cfg.timeout)
    finally:
        stop.set()
        if watcher:
            watcher.join(timeout=3)
    events = read_trace(trace)
    summary = next((e for e in reversed(events) if e["event"] == "finish"), {})
    summary["levels"] = [e for e in events if e["event"] in ("select", "verify")]
    verification = verify_supports(run, Oracle(load_atoms(cfg.dataset_path()))) if verify else None
    save_run(run, cfg, out_dir, label, verification,
             extra={"ranker": ranker.to_dict(),
                    "trace_summary": {k: v for k, v in summary.items() if k != "levels"}})
    return run, verification, summary
