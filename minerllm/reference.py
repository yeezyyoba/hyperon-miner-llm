"""A complete, stable reference for the evaluation.

Why not just use the exhaustive run's output? Upstream's scoring pipeline silently
drops patterns depending on the size of the run (docs/01-problem.md, Issue 7). In
the full university run, 269 of 641 frequent patterns get no `isurp` score, but the
same patterns are scored, with deterministic values, when they appear in smaller runs.
A reference built from one big run would therefore be incomplete, and it would treat
correct outputs of budgeted runs as if they were invented.

Cause: upstream stores scores with ``add-atom-nodup``, whose duplicate check is a
two-way ``match``. A new pattern that unifies with an already-stored one (variables
binding to constants) and has the same score is silently dropped. Scoring every
pattern into its OWN fresh space avoids the collision while still using upstream's
own ``call-surprisingness``.

So the reference is built in two steps, both with upstream's own code:

1. **frequent set**: the guided miner, exhaustive, budget 100 %, no scoring. This is
   identical to upstream's frequent output (tested) and every support is oracle-checked.
2. **scores**: every frequent pattern scored with upstream's ``call-surprisingness``
   (``isurp``, same normalisation and db-ratio as the config), each into its own fresh
   space, ``CHUNK`` patterns per PeTTa process.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import MinerConfig, RankerConfig, render_upstream_script
from .petta import run_script
from .sexpr import dumps, parse

CHUNK = 60


def _scoring_script(cfg: MinerConfig, items: list[tuple[str, int]]) -> str:
    base = render_upstream_script(cfg)
    head = base[: base.index("!(pattern-miner &res")]
    norm = "True" if cfg.normalize else "False"
    calls = []
    for i, (pattern, sup) in enumerate(items):
        p = dumps(parse(pattern))
        calls += [f"!(bind! &score{i} (new-space))",
                  f"!(call-surprisingness &score{i} &db (supportOf {p} {sup}) "
                  f"{cfg.surp_mode} {norm} {cfg.db_ratio})",
                  f"!(get-atoms &score{i})"]
    return head + "\n".join(calls) + "\n"


def build_reference(cfg: MinerConfig, out_dir: Path, log=print) -> dict:
    """Write ``reference.json``: {pattern: {"support": int, "score": float | None}}."""
    from .harness import run_guided
    out_dir.mkdir(parents=True, exist_ok=True)
    freq_cfg = MinerConfig(**{**cfg.to_dict(), "surp_mode": "none"})
    run, ver, _ = run_guided(freq_cfg, RankerConfig(strategy="exhaustive"), out_dir,
                             label="frequent-b100")
    if not (run.ok and ver.ok):
        raise RuntimeError("frequent reference run failed or disagrees with the oracle")
    frequent = {p.pattern: p.support for p in run.patterns}
    log(f"  frequent set: {len(frequent)} patterns (oracle ok)")

    scores: dict[str, float] = {}
    items = sorted(frequent.items())
    work = out_dir / "_reference"
    work.mkdir(exist_ok=True)
    for i in range(0, len(items), CHUNK):
        chunk = items[i:i + CHUNK]
        script = work / f"score_{i // CHUNK:03d}.metta"
        script.write_text(_scoring_script(cfg, chunk))
        res = run_script(script, timeout=cfg.timeout)
        got = {p.pattern: p.surprisingness for p in res.patterns if p.surprisingness is not None}
        scores.update(got)
        log(f"  scored chunk {i // CHUNK + 1}/{-(-len(items) // CHUNK)}: "
            f"{len(got)}/{len(chunk)} patterns")
    ref = {p: {"support": s, "score": scores.get(p)} for p, s in frequent.items()}
    missing = [p for p, v in ref.items() if v["score"] is None]
    meta = {"config": cfg.to_dict(), "frequent": len(frequent), "scored": len(scores),
            "unscored": missing, "patterns": ref}
    (out_dir / "reference.json").write_text(json.dumps(meta, indent=1))
    log(f"  reference: {len(scores)}/{len(frequent)} frequent patterns scored"
        + (f" ({len(missing)} could not be scored even alone)" if missing else ""))
    return meta
