"""Evaluation metrics and verdict logic, on hand-made numbers."""
from __future__ import annotations

import pytest

from minerllm.evaluate import (Arm, baseline_arms, llm_arms, summarize, tie_aware_top,
                               verdicts)


def test_tie_aware_top_includes_ties_at_the_cut():
    scores = {"a": 0.99, "b": 0.95, "c": 0.95, "d": 0.95, "e": 0.5}
    assert tie_aware_top(scores, 2) == {"a", "b", "c", "d"}     # 3-way tie at rank 2
    assert tie_aware_top(scores, 1) == {"a"}
    assert tie_aware_top(scores, 10) == set(scores)               # k larger than the set
    assert tie_aware_top({}, 5) == set()


def test_arm_matrix_shape():
    base = baseline_arms(budgets=[0.1, 0.3], seeds=[0, 1, 2])
    assert base[0].name == "exhaustive-b100"
    assert len(base) == 1 + 2 * (2 + 3)            # heuristic + cardinality + 3 seeds
    llm = llm_arms(["groq", "nvidia"], budgets=[0.3])
    assert [a.name for a in llm] == ["llm-groq-b30", "llm-nvidia-b30", "llm-direct-nvidia-b30"]
    assert llm[0].ranker().providers == ["groq"]                  # one provider per arm
    assert Arm("x", "random", 0.3, seed=2).family == "random"
    assert llm[1].family == "llm:nvidia"


def _row(ds, fam, b, r10, seed=0):
    return {"dataset": ds, "family": fam, "budget": b, "seed": seed, "recall@10": r10,
            "recall@25": r10, "verified": 10, "seconds": 1.0, "llm_seconds": 0.0,
            "miner_seconds": 1.0, "patterns": 5, "planted_found": None, "tokens_in": 0,
            "tokens_out": 0, "cost_usd": None, "fallback_batches": 0, "batches": 0,
            "oracle_ok": True, "precision_ok": True}


def test_random_seeds_are_averaged():
    rows = [_row("university", "random", 0.3, v, seed=i) for i, v in enumerate([0.2, 0.4, 0.6])]
    (s,) = summarize(rows)
    assert s["runs"] == 3 and s["recall@10"] == pytest.approx(0.4)
    assert s["recall@10_sd"] == pytest.approx(0.1633, abs=1e-3)


def _summary(named_llm, named_heur, anon_llm, anon_heur, rand=0.1):
    rows = []
    for ds, l, h in (("university", named_llm, named_heur), ("university-anon", anon_llm, anon_heur)):
        rows += [_row(ds, "llm:groq", 0.3, l), _row(ds, "heuristic", 0.3, h),
                 _row(ds, "random", 0.3, rand)]
    return summarize(rows)


def test_h1_supported_only_if_90_percent_and_better_than_baselines():
    v = verdicts(_summary(0.95, 0.5, 0.95, 0.5))
    assert v["H1"]["university / llm:groq"]["verdict"] == "supported"
    v = verdicts(_summary(0.92, 0.95, 0.92, 0.95))
    assert v["H1"]["university / llm:groq"]["verdict"].startswith("rejected: a cheap baseline")
    v = verdicts(_summary(0.6, 0.2, 0.6, 0.2))
    assert v["H1"]["university / llm:groq"]["verdict"] == "rejected: below 90 %"


def test_h2_needs_gap_on_named_data_that_vanishes_when_anonymised():
    assert verdicts(_summary(0.9, 0.5, 0.52, 0.5))["H2"]["llm:groq"]["verdict"] == "supported"
    assert verdicts(_summary(0.9, 0.5, 0.9, 0.5))["H2"]["llm:groq"]["verdict"] == "not supported"


def test_groq_arms_are_sequential_and_direct_arm_runs_on_nvidia_university_only():
    arms = {a.name: a for a in llm_arms(["groq", "nvidia"], budgets=[0.3])}
    assert arms["llm-groq-b30"].ranker().workers == 1
    assert arms["llm-groq-b30"].ranker().max_retries == 4
    assert arms["llm-nvidia-b30"].ranker().workers == 4
    direct = arms["llm-direct-nvidia-b30"]
    assert direct.only == ("university",) and direct.ranker().providers == ["nvidia"]
    assert "llm-direct-groq-b30" not in arms
