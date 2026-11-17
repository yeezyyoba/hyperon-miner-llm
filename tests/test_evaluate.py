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


def test_repeat_arms_disable_the_cache_and_group_with_the_original():
    from minerllm.evaluate import repeat_arms
    arms = repeat_arms(["groq"], 0.3, repeats=2)
    assert [a.name for a in arms] == ["llm-groq-b30-r1", "llm-groq-b30-r2"]
    assert all(a.ranker().cache_dir is None and a.family == "llm:groq" for a in arms)
    assert llm_arms(["groq"], [0.3])[0].ranker().cache_dir == ".cache/llm"


# ------------------------------------------------------------------ exploratory follow-up

def test_explore_arms_hybrid_everywhere_baselines_only_on_heldout():
    from minerllm.evaluate import HELDOUT, explore_arms
    arms = {a.name: a for a in explore_arms(["groq", "nvidia"])}
    assert arms["llm-hybrid-groq-b30"].only == () and arms["llm-hybrid-groq-b30"].family == "llm-hybrid:groq"
    for name in ("cardinality-b30", "heuristic-b30", "random-b30-s4", "llm-nvidia-b30"):
        assert arms[name].only == tuple(HELDOUT)
    assert arms["llm-hybrid-groq-b30"].ranker().workers == 1          # Groq stays sequential


def test_hybrid_runs_never_enter_the_preregistered_report(monkeypatch):
    import minerllm.evaluate as ev
    fake = {"university": [dict(_row("university", "llm:groq", 0.3, 0.3), strategy="llm"),
                           dict(_row("university", "llm-hybrid:groq", 0.3, 0.9), strategy="llm-hybrid")],
            "university-anon": [], "galaxy400": []}
    monkeypatch.setattr(ev, "metrics_for", lambda ds: fake.get(ds, []))
    fams = {r["family"] for r in ev.collect()}
    assert fams == {"llm:groq"}


def test_explore_report_applies_the_h1_bar_to_heldout(monkeypatch, tmp_path):
    import minerllm.evaluate as ev
    ds = "heldout-university-s1"
    rows = {ds: [dict(_row(ds, "cardinality", 0.3, 0.6), strategy="cardinality"),
                 dict(_row(ds, "random", 0.3, 0.2), strategy="random"),
                 dict(_row(ds, "heuristic", 0.3, 0.0), strategy="heuristic"),
                 dict(_row(ds, "llm:groq", 0.3, 0.4), strategy="llm"),
                 dict(_row(ds, "llm-hybrid:groq", 0.3, 0.8), strategy="llm-hybrid"),
                 dict(_row(ds, "llm-hybrid:nvidia", 0.3, 0.95), strategy="llm-hybrid")]}
    monkeypatch.setattr(ev, "metrics_for", lambda d: rows.get(d, []))
    monkeypatch.setattr(ev, "RESULTS", tmp_path)
    monkeypatch.setattr(ev, "ROOT", tmp_path)                 # no docs to patch here
    out = ev.explore_report(log=lambda m: None)
    c = out["checks"]
    assert c[f"{ds} / llm:groq"]["verdict"] == "below the best baseline"
    assert c[f"{ds} / llm-hybrid:groq"]["verdict"] == "beats every baseline, below 90 %"
    assert c[f"{ds} / llm-hybrid:nvidia"]["verdict"] == "meets the H1 bar"
    assert c[f"{ds} / llm-hybrid:groq"]["best_baseline"] == "cardinality"
    assert (tmp_path / "exploratory.md").read_text().startswith("# Exploratory follow-up")


# ------------------------------------------------------------------ runs where no LLM answered

def test_runs_where_every_llm_batch_fell_back_are_not_done_and_not_counted(tmp_path):
    import json
    from minerllm.evaluate import _done, no_llm_answer
    dead = {"ok": True, "ranker": {"strategy": "llm-hybrid"},
            "trace_summary": {"batches": 9, "fallback_batches": 9}}
    alive = {"ok": True, "ranker": {"strategy": "llm"},
             "trace_summary": {"batches": 3, "fallback_batches": 1}}
    baseline = {"ok": True, "ranker": {"strategy": "cardinality"}, "trace_summary": {"batches": 0}}
    assert no_llm_answer(dead) and not no_llm_answer(alive) and not no_llm_answer(baseline)
    for name, rec, done in (("dead", dead, False), ("alive", alive, True), ("base", baseline, True)):
        (tmp_path / f"{name}.json").write_text(json.dumps(rec))
        assert _done(tmp_path / f"{name}.json") is done


def test_llm_arms_refuse_to_start_without_keys(monkeypatch):
    from minerllm import evaluate as ev
    monkeypatch.setattr("minerllm.llm.chain.load_env", lambda: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "x")
    with pytest.raises(SystemExit, match="GROQ_API_KEY"):
        ev.check_llm_keys([Arm("a", "llm-hybrid", 0.3, provider="groq")])
    ev.check_llm_keys([Arm("b", "llm", 0.3, provider="nvidia"), Arm("c", "cardinality", 0.3)])


def test_env_is_read_without_python_dotenv_and_without_overriding(monkeypatch, tmp_path):
    from minerllm.llm import chain
    fake_pkg = tmp_path / "minerllm" / "llm"
    fake_pkg.mkdir(parents=True)
    (tmp_path / ".env").write_text("# keys\nGROQ_API_KEY=gsk_abc  # comment\n"
                                   "export NVIDIA_API_KEY='nv-1'\nGEMINI_API_KEY=\nBROKEN LINE\n")
    monkeypatch.setattr(chain, "__file__", str(fake_pkg / "chain.py"))
    monkeypatch.chdir(tmp_path.parent)              # not the repo: no auto-discovery involved
    for k in ("GROQ_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "already-set")
    chain.load_env()
    import os
    assert os.environ["GROQ_API_KEY"] == "gsk_abc"
    assert os.environ["NVIDIA_API_KEY"] == "already-set"        # existing values win
    assert "GEMINI_API_KEY" not in os.environ                   # empty values are skipped


def test_live_runs_pace_groq_like_the_evaluation(monkeypatch):
    from minerllm.cli import rate_limit_settings
    from minerllm.evaluate import Arm
    groq_arm = Arm("x", "llm-hybrid", 0.3, provider="groq").ranker()
    assert rate_limit_settings(["groq", "nvidia"]) == {"workers": groq_arm.workers,
                                                       "max_retries": groq_arm.max_retries}
    assert rate_limit_settings(["nvidia", "groq"]) == {}
    monkeypatch.delenv("MINERLLM_PROVIDERS", raising=False)
    assert rate_limit_settings(None)["workers"] == 1          # default order starts with Groq
    monkeypatch.setenv("MINERLLM_PROVIDERS", "nvidia,groq")
    assert rate_limit_settings(None) == {}
