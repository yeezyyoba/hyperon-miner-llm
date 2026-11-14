"""Datasets: loading .metta files, Galaxy subsets, and relation statistics."""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .sexpr import Atom, parse_all

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_DATA = ROOT / "external" / "hyperon-miner" / "experiments" / "data"
GALAXY_FULL = UPSTREAM_DATA / "galaxy_data_full.metta"


def load_atoms(path: str | Path) -> list[Atom]:
    """All data atoms of a .metta file, excluding type declarations ``(: x T)``."""
    path = Path(path)
    if path.suffix != ".metta":
        path = path.with_suffix(".metta")
    atoms = parse_all(path.read_text())
    return [a for a in atoms if isinstance(a, tuple) and a and a[0] != ":"]


def write_atoms(atoms: list[Atom], path: str | Path, header: str = "") -> Path:
    from .sexpr import dumps
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f";; {l}" for l in header.splitlines()] if header else []
    lines += [dumps(a) for a in atoms]
    path.write_text("\n".join(lines) + "\n")
    return path


def galaxy_subset(n: int, out_dir: str | Path, seed: int = 7) -> Path:
    """Deterministic random sample of n Galaxy relation atoms.

    Same sampling as scripts/profile_baseline.py, so the profiled datasets and
    the evaluated datasets are identical for the same (n, seed).
    """
    rels = [l for l in GALAXY_FULL.read_text().splitlines()
            if l.startswith("(") and not l.startswith("(:")]
    sample = sorted(random.Random(seed).sample(rels, n))
    path = Path(out_dir) / f"galaxy_{n}.metta"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sample) + "\n")
    return path


@dataclass
class DatasetStats:
    """What an LLM may be told about a dataset: shape only, no individual facts."""
    n_atoms: int
    relations: dict[str, int] = field(default_factory=dict)       # head -> count
    arity: dict[str, int] = field(default_factory=dict)           # head -> arity
    distinct_args: dict[str, list[int]] = field(default_factory=dict)  # head -> per-position

    def describe(self) -> str:
        lines = [f"{self.n_atoms} atoms, {len(self.relations)} relation types:"]
        for head, cnt in sorted(self.relations.items(), key=lambda kv: -kv[1]):
            args = ", ".join(str(x) for x in self.distinct_args.get(head, []))
            lines.append(f"  {head}/{self.arity[head]}: {cnt} atoms "
                         f"(distinct values per argument: {args})")
        return "\n".join(lines)


def stats(atoms: list[Atom]) -> DatasetStats:
    rel = Counter()
    arity: dict[str, int] = {}
    values: dict[str, list[set]] = {}
    for a in atoms:
        head = str(a[0])
        rel[head] += 1
        arity[head] = len(a) - 1
        slots = values.setdefault(head, [set() for _ in a[1:]])
        for i, v in enumerate(a[1:]):
            if i < len(slots):
                slots[i].add(v)
    return DatasetStats(
        n_atoms=len(atoms),
        relations=dict(rel),
        arity=arity,
        distinct_args={h: [len(s) for s in v] for h, v in values.items()},
    )
