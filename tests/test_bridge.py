"""The py-call bridge, exercised directly from Python (no PeTTa)."""
from __future__ import annotations

import json

import pytest

from minerllm import bridge
from minerllm.datagen import UniversitySpec, write_dataset

REPRS = [
    "(, (ADVISED_BY $_0 $_1) (MEMBER_OF $_1 $_2))",
    "(, (MEMBER_OF $_5 $_6) (ADVISED_BY $_7 $_5))",     # duplicate of [0] (clause order)
    "(, (USES $_0 $_1) (USES $_2 $_1))",
    "(, (ENROLLED_IN $_0 $_1) (TEACHES $_2 $_1))",
    "(, (FRIENDS_WITH $_0 $_1) (USES $_0 $_2))",
]


def _configure(tmp_path, **kw) -> list[dict]:
    data = write_dataset(UniversitySpec(students=10), tmp_path)
    trace = tmp_path / "trace.jsonl"
    cfg = {"strategy": "exhaustive", "budget": 1.0, "trace_path": str(trace),
           "dataset": str(data), **kw}
    (tmp_path / "run.json").write_text(json.dumps(cfg))
    assert bridge.configure(str(tmp_path / "run.json")) is True
    return trace


def _events(trace):
    return [json.loads(l) for l in trace.read_text().splitlines()]


def test_exhaustive_selects_every_unique_candidate_once(tmp_path):
    trace = _configure(tmp_path)
    picked = bridge.select(REPRS, 0)
    assert sorted(picked) == [0, 2, 3, 4]                     # [1] is a duplicate of [0]
    sel = _events(trace)[-1]
    assert (sel["generated"], sel["unique"], sel["selected"]) == (5, 4, 4)


def test_budget_selects_ceil_fraction(tmp_path):
    _configure(tmp_path, strategy="heuristic", budget=0.5)
    assert len(bridge.select(REPRS, 0)) == 2                  # ceil(0.5 * 4)


def test_min_select_floor(tmp_path):
    _configure(tmp_path, strategy="random", budget=0.01, min_select=3)
    assert len(bridge.select(REPRS, 0)) == 3


def test_empty_level(tmp_path):
    _configure(tmp_path)
    assert bridge.select([], 2) == []


def test_llm_strategy_with_mock_and_full_trace(tmp_path):
    trace = _configure(tmp_path, strategy="llm", budget=0.5, providers=["mock"], cache_dir=None)
    picked = bridge.select(REPRS, 0)
    assert len(picked) == 2
    bridge.verify_started(0)
    bridge.verify_finished(0, 1)
    bridge.finish()
    ev = _events(trace)
    assert [e["event"] for e in ev] == ["configure", "select", "verify", "finish"]
    assert ev[1]["batches"][0]["provider"] == "mock"
    assert ev[-1]["selected"] == 2 and ev[-1]["kept"] == 1


def test_broken_ranker_degrades_to_heuristic(tmp_path, monkeypatch):
    trace = _configure(tmp_path, strategy="heuristic", budget=1.0)

    def boom(*a, **k):
        raise RuntimeError("ranker exploded")

    monkeypatch.setattr(bridge._S.ranker, "rank", boom)
    picked = bridge.select(REPRS, 0)
    assert sorted(picked) == [0, 2, 3, 4]                     # mining continues
    assert any(e["event"] == "ranker_error" for e in _events(trace))


def test_non_permutation_from_ranker_is_rejected(tmp_path, monkeypatch):
    trace = _configure(tmp_path, strategy="heuristic")
    from minerllm.rankers import RankResult
    monkeypatch.setattr(bridge._S.ranker, "rank", lambda *a, **k: RankResult([0, 0, 1], "evil"))
    assert sorted(bridge.select(REPRS, 0)) == [0, 2, 3, 4]
    assert any(e["event"] == "ranker_error" for e in _events(trace))


def test_select_before_configure_fails_loudly(monkeypatch):
    monkeypatch.setattr(bridge, "_S", None)
    with pytest.raises(AssertionError):
        bridge.select(REPRS, 0)
