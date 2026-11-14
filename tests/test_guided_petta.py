"""Integration: the guided miner on the real PeTTa, checked against upstream and the oracle.

The three properties that make the LLM integration *verifiable*:

1. Equivalence: exhaustive ranking at budget 1.0 reproduces the upstream miner exactly.
2. Soundness:   at any budget, with any ranker, the output is a subset of the exhaustive
                output, with identical supports (a budget costs recall, never precision).
3. Robustness:  if the LLM is down or talks nonsense, mining still completes, and the
                trace says what happened.
"""
from __future__ import annotations

import json

import pytest

from minerllm.config import MinerConfig, RankerConfig
from minerllm.datagen import UniversitySpec, write_dataset
from minerllm.harness import run_guided, run_upstream


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("guided")
    data = write_dataset(UniversitySpec(students=24, courses=12, profs=6, seed=11), tmp)
    cfg = MinerConfig(dataset=str(data), minsup=6, depth=1, surp_mode="none", timeout=900)
    up, _ = run_upstream(cfg, tmp / "upstream")
    ex, ver, summary = run_guided(cfg, RankerConfig(strategy="exhaustive"), tmp / "exhaustive")
    return tmp, cfg, up, ex, ver, summary


def _supports(run):
    return {p.pattern: p.support for p in run.patterns}


@pytest.mark.petta
def test_exhaustive_guided_equals_upstream(setup):
    _, _, up, ex, ver, summary = setup
    assert up.ok and ex.ok and ver.ok
    assert _supports(ex) == _supports(up)
    assert summary["unique"] <= summary["generated"]          # duplicates removed before counting


@pytest.mark.petta
@pytest.mark.parametrize("strategy,budget", [("random", 0.3), ("heuristic", 0.3),
                                             ("heuristic", 0.6)])
def test_budgeted_output_is_a_sound_subset(setup, strategy, budget):
    tmp, cfg, _, ex, _, _ = setup
    run, ver, summary = run_guided(cfg, RankerConfig(strategy=strategy, budget=budget),
                                   tmp / f"{strategy}{budget}")
    full, part = _supports(ex), _supports(run)
    assert run.ok and ver.ok, ver.mismatches
    assert set(part) <= set(full)                             # precision is always 100 %
    assert all(part[p] == full[p] for p in part)
    assert summary["selected"] < summary["unique"]            # the budget really applied


@pytest.mark.petta
def test_llm_strategy_end_to_end_with_mock_and_fallback(setup):
    tmp, cfg, _, ex, _, _ = setup
    rc = RankerConfig(strategy="llm", budget=0.4, providers=["mock:garbage", "mock"],
                      cache_dir=None)
    run, ver, summary = run_guided(cfg, rc, tmp / "llm-mock")
    assert run.ok and ver.ok
    assert set(_supports(run)) <= set(_supports(ex))
    trace = [json.loads(l) for l in (tmp / "llm-mock" / f"{rc.label}.trace.jsonl").open()]
    batches = [b for e in trace if e["event"] == "select" for b in e["batches"]]
    assert batches and all(b["provider"] == "mock" for b in batches)   # garbage -> next provider
    assert all(b["attempts"][0]["error"] == "answer failed validation" for b in batches)
    assert summary["fallback_batches"] == 0


@pytest.mark.petta
def test_total_llm_outage_still_completes(setup):
    tmp, cfg, _, ex, _, _ = setup
    rc = RankerConfig(strategy="llm", budget=0.4, providers=["mock:error", "mock:fatal"],
                      max_retries=0, cache_dir=None)
    run, ver, summary = run_guided(cfg, rc, tmp / "llm-down")
    assert run.ok and ver.ok
    assert set(_supports(run)) <= set(_supports(ex))
    assert summary["fallback_batches"] == summary["batches"] > 0       # all heuristic, all logged


@pytest.mark.petta
def test_guided_miner_scores_with_upstream_isurp(setup):
    tmp, cfg, *_ = setup
    scored = MinerConfig(**{**cfg.to_dict(), "surp_mode": "isurp"})
    run, ver, _ = run_guided(scored, RankerConfig(strategy="heuristic", budget=0.5), tmp / "isurp")
    assert run.ok and run.patterns
    assert all(p.surprisingness is not None for p in run.patterns)
