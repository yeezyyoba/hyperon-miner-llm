"""Miner configuration and MeTTa script rendering.

A ``MinerConfig`` holds everything that defines a run. It's what makes
"same tasks, data and miner configuration" (assignment step 5) checkable:
every result file records the config it came from.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = ROOT / "run_miner.metta"
SURP_MODES = {"none", "isurp", "isurp-old", "jsd"}


@dataclass
class MinerConfig:
    dataset: str                      # path to a .metta data file
    minsup: int = 5
    depth: int = 0                    # 0 -> 2 conjuncts, 1 -> 3 conjuncts, ...
    surp_mode: str = "isurp"
    normalize: bool = True
    db_ratio: float = 0.5
    timeout: int = 1800
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.surp_mode not in SURP_MODES:
            raise ValueError(f"surp_mode must be one of {sorted(SURP_MODES)}")
        if self.minsup < 1 or self.depth < 0:
            raise ValueError("minsup must be >= 1 and depth >= 0")

    @property
    def conjuncts(self) -> int:
        return self.depth + 2

    def dataset_path(self) -> Path:
        p = Path(self.dataset)
        p = p if p.is_absolute() else ROOT / p
        return p if p.suffix == ".metta" else p.with_suffix(".metta")

    def fingerprint(self) -> str:
        """Short stable hash of the config, used in run directory names."""
        blob = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha1(blob).hexdigest()[:10]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "MinerConfig":
        data = yaml.safe_load(Path(path).read_text()) or {}
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


def _metta_bool(b: bool) -> str:
    return "True" if b else "False"


def render_upstream_script(cfg: MinerConfig) -> str:
    """The fixed entry point (run_miner.metta) with this config's data and parameters.

    Imports are made absolute so the script can live anywhere (e.g. runs/...).
    """
    src = ENTRY_POINT.read_text()
    src = src.replace("!(import! &self external/", f"!(import! &self {ROOT}/external/")
    src = re.sub(r"^!\(import! &db .*\)$",
                 f"!(import! &db {cfg.dataset_path().with_suffix('')})", src, flags=re.M)
    surp = cfg.surp_mode
    norm = _metta_bool(cfg.normalize) if surp != "none" else "none"
    ratio = cfg.db_ratio if surp != "none" else "none"
    src = re.sub(r"^!\(pattern-miner &res .*\)$",
                 f"!(pattern-miner &res &db $x {cfg.minsup} {cfg.depth} {surp} {norm} {ratio} True)",
                 src, flags=re.M)
    return src
