"""Python side of the MeTTa ↔ LLM boundary, called from PeTTa via ``py-call``.

The guided miner (experiments/llm-guided-miner/guided-conjunction-expansion.metta)
calls, in order:

    (minerllm_bridge.configure "<run.json>")        once
    (minerllm_bridge.select <candidate reprs> L)    per level -> indices to verify
    (minerllm_bridge.verify_started L)              per level, before support counting
    (minerllm_bridge.verify_finished L <kept>)      per level, after support counting
    (minerllm_bridge.finish)                        once

``select`` is the whole boundary. It gets the candidates as text, deduplicates
them (Issue 4), asks the configured ranker for an order, and returns the
positions of the first ``ceil(budget × unique)`` candidates. MeTTa then counts
support for exactly those, so nothing the ranker says is taken as fact.

Every call appends a JSON line to the run's trace file. That trace is the
"agentic execution log" for the evaluation.
"""
from __future__ import annotations

import json
import math
import time
import traceback
from pathlib import Path

from .datasets import load_atoms, stats
from .patterns import canonical
from .rankers import Candidate, cardinality_order, make_ranker


class _Session:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.budget = float(cfg.get("budget", 1.0))
        self.min_select = int(cfg.get("min_select", 1))
        self.trace_path = Path(cfg["trace_path"])
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.trace_path.write_text("")
        self.stats = stats(load_atoms(cfg["dataset"])) if cfg.get("dataset") else None
        client = None
        if cfg["strategy"].startswith("llm"):
            from .llm import build_chain
            client = build_chain(cfg.get("providers"), cfg.get("cache_dir"),
                                 max_retries=int(cfg.get("max_retries", 2)),
                                 timeout_s=float(cfg.get("timeout_s", 60)))
        self.ranker = make_ranker(cfg["strategy"], seed=int(cfg.get("seed", 0)), client=client,
                                  batch_size=int(cfg.get("batch_size", 60)),
                                  timeout_s=float(cfg.get("timeout_s", 180)),
                                  workers=int(cfg.get("workers", 4)),
                                  on_batch=self._on_batch,
                                  samples=int(cfg.get("samples", 3)))
        self.t0 = time.time()
        self.verify_t: dict[int, float] = {}
        self.totals = {"generated": 0, "unique": 0, "selected": 0, "kept": 0,
                       "llm_seconds": 0.0, "verify_seconds": 0.0, "input_tokens": 0,
                       "output_tokens": 0, "fallback_batches": 0, "batches": 0}

    def _on_batch(self, i, n, resp, err, secs) -> None:
        """Called as each LLM batch finishes, so long runs show progress in the trace."""
        if resp is not None:
            self.log("llm_batch", batch=i + 1, of=n, provider=resp.provider, model=resp.model,
                     cached=resp.cached, seconds=round(secs, 2))
        else:
            self.log("llm_batch", batch=i + 1, of=n, failed=str(err)[:160], seconds=round(secs, 2))

    def log(self, event: str, **data) -> None:
        rec = {"t": round(time.time() - self.t0, 3), "event": event, **data}
        with open(self.trace_path, "a") as f:
            f.write(json.dumps(rec) + "\n")


_S: _Session | None = None


def configure(path: str) -> bool:
    global _S
    cfg = json.loads(Path(path).read_text())
    _S = _Session(cfg)
    _S.log("configure", strategy=cfg["strategy"], budget=_S.budget,
           providers=cfg.get("providers"), dataset=cfg.get("dataset"))
    return True


def select(reprs, level) -> list[int]:
    assert _S is not None, "minerllm_bridge.configure was not called"
    level = int(level)
    reprs = [str(r) for r in (reprs or [])]
    # 1. deduplicate (clause order / variable names), keeping the first spelling
    first: dict[str, int] = {}
    for i, r in enumerate(reprs):
        first.setdefault(canonical(r), i)
    uniq = list(first.items())                       # [(canonical, original index)]
    cands = [Candidate(j, c) for j, (c, _) in enumerate(uniq)]
    if not cands:
        _S.log("select", level=level, generated=len(reprs), unique=0, selected=0)
        return []

    # 2. rank (any failure inside the ranker degrades to the cardinality order; mining goes on)
    try:
        res = _S.ranker.rank(cands, _S.stats, level)
        order, meta = res.order, res
        if sorted(order) != list(range(len(cands))):      # ranker must return a permutation
            raise ValueError("ranker did not return a permutation")
    except Exception as e:                                # noqa: BLE001 - deliberate safety net
        order, meta = cardinality_order(cands, _S.stats), None
        _S.log("ranker_error", level=level, error=f"{type(e).__name__}: {e}",
               trace=traceback.format_exc(limit=3))

    # 3. budget
    k = len(cands) if _S.budget >= 1 else max(min(_S.min_select, len(cands)),
                                               math.ceil(_S.budget * len(cands)))
    chosen = order[:k]
    picked = [uniq[j][1] for j in chosen]

    t = _S.totals
    t["generated"] += len(reprs)
    t["unique"] += len(cands)
    t["selected"] += k
    if meta is not None:
        t["llm_seconds"] += meta.llm_seconds
        t["input_tokens"] += meta.input_tokens
        t["output_tokens"] += meta.output_tokens
        t["fallback_batches"] += meta.fallback_batches
        t["batches"] += len(meta.batches)
    extra = {}
    top = getattr(_S.ranker, "top_joins", None)
    if top and not getattr(_S, "_logged_joins", False):
        extra["top_joins"] = [[f"{a[0]}.arg{a[1]} = {b[0]}.arg{b[1]}", s] for (a, b), s in top]
        _S._logged_joins = True
    _S.log("select", level=level, generated=len(reprs), unique=len(cands), selected=k,
           strategy=_S.ranker.strategy, **extra,
           llm_seconds=round(meta.llm_seconds, 3) if meta else 0,
           batches=meta.batches if meta else [],
           selected_patterns=[uniq[j][0] for j in chosen])
    return picked


def verify_started(level) -> bool:
    if _S:
        _S.verify_t[int(level)] = time.time()
    return True


def verify_finished(level, kept) -> bool:
    if _S:
        secs = time.time() - _S.verify_t.pop(int(level), time.time())
        _S.totals["verify_seconds"] += secs
        _S.totals["kept"] = int(kept)          # last level's survivors = final patterns
        _S.log("verify", level=int(level), kept=int(kept), seconds=round(secs, 3))
    return True


def finish() -> bool:
    if _S:
        t = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in _S.totals.items()}
        _S.log("finish", wall_seconds=round(time.time() - _S.t0, 3), **t)
    return True
