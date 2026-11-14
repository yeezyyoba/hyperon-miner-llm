"""Run the miner from a config, save artefacts, and verify results against the oracle."""
from __future__ import annotations

import json
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
    out_dir = out_dir or RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{cfg.fingerprint()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    script = out_dir / f"{label}.metta"
    script.write_text(render_upstream_script(cfg))
    run = run_script(script, timeout=cfg.timeout)
    verification = verify_supports(run, Oracle(load_atoms(cfg.dataset_path()))) if verify else None
    save_run(run, cfg, out_dir, label, verification)
    return run, verification
