"""Rankers and the validator: the LLM boundary, tested without any network."""
from __future__ import annotations

import pytest

from minerllm.datagen import UniversitySpec, generate
from minerllm.datasets import stats
from minerllm.llm import FallbackChain
from minerllm.llm.mock import MockLLM
from minerllm.rankers import (Candidate, LLMRanker, build_prompt, heuristic_order,
                              heuristic_score, make_ranker, validate_scores)

CANDS = [Candidate(i, p) for i, p in enumerate([
    "(, (ADVISED_BY $v0 $v1) (MEMBER_OF $v1 $v2) (MAJORS_IN $v0 $v2))",
    "(, (USES $v0 $v1) (USES $v2 $v3) (USES $v4 $v5))",
    "(, (ENROLLED_IN $v0 $v1) (TEACHES $v2 $v1))",
    "(, (FRIENDS_WITH $v0 $v1) (USES $v0 $v2))",
    "(, (ADVISED_BY $v0 $v1) (TEACHES $v1 $v2) (ENROLLED_IN $v0 $v2))",
])]


# ------------------------------------------------------------------ validator

def test_valid_answer_accepted():
    v = validate_scores('{"scores": [{"id": 0, "score": 9}, {"id": 1, "score": 2}]}', {0, 1})
    assert v.accepted and v.scores == {0: 9.0, 1: 2.0} and v.coverage == 1.0


def test_code_fences_are_tolerated():
    assert validate_scores('```json\n{"scores": [{"id": 0, "score": 5}]}\n```', {0}).accepted


@pytest.mark.parametrize("text", ["not json", '{"ranking": [0, 1]}', '[1, 2, 3]', ""])
def test_malformed_answers_rejected(text):
    v = validate_scores(text, {0, 1})
    assert not v.accepted and v.scores == {}


def test_unknown_ids_are_dropped_the_llm_cannot_invent_candidates():
    v = validate_scores('{"scores": [{"id": 0, "score": 7}, {"id": 99, "score": 10}, '
                        '{"id": -1, "score": 10}]}', {0})
    assert v.scores == {0: 7.0} and any("unknown id 99" in i for i in v.issues)


def test_duplicates_keep_first_and_scores_are_clamped():
    v = validate_scores('{"scores": [{"id": 0, "score": 42}, {"id": 0, "score": 1}, '
                        '{"id": 1, "score": -5}]}', {0, 1})
    assert v.scores == {0: 10.0, 1: 0.0}


def test_low_coverage_rejected():
    v = validate_scores('{"scores": [{"id": 0, "score": 7}]}', {0, 1, 2})
    assert not v.accepted and v.coverage == pytest.approx(1 / 3)


# ------------------------------------------------------------------ rankers

@pytest.mark.parametrize("strategy", ["exhaustive", "random", "heuristic"])
def test_every_ranker_returns_a_permutation(strategy):
    order = make_ranker(strategy, seed=1).rank(CANDS).order
    assert sorted(order) == [c.idx for c in CANDS]


def test_random_ranker_is_seeded():
    a = make_ranker("random", seed=3).rank(CANDS, level=1).order
    assert a == make_ranker("random", seed=3).rank(CANDS, level=1).order
    assert a != make_ranker("random", seed=4).rank(CANDS, level=1).order or len(CANDS) < 3


def test_heuristic_prefers_multi_relation_joins_over_generic_patterns():
    assert heuristic_score(CANDS[0].pattern) > heuristic_score(CANDS[1].pattern)
    order = heuristic_order(CANDS)
    assert order.index(1) == len(CANDS) - 1          # three unlinked USES clauses: last


def test_prompt_contains_schema_and_every_candidate_but_no_data_atoms():
    s = stats(generate(UniversitySpec())[0])
    prompt = build_prompt(CANDS, list(range(len(CANDS))), s.describe())
    assert "ADVISED_BY/2" in prompt and all(c.pattern in prompt for c in CANDS)
    assert "student_" not in prompt and "prof_" not in prompt      # schema only, no facts


def test_llm_ranker_with_healthy_mock():
    r = LLMRanker(FallbackChain([MockLLM("gemini")]), batch_size=2).rank(CANDS)
    assert sorted(r.order) == list(range(5))
    assert len(r.batches) == 3 and r.fallback_batches == 0
    assert all(b["provider"] == "gemini" for b in r.batches)


@pytest.mark.parametrize("fault", ["garbage", "wrong_schema", "partial"])
def test_invalid_llm_answers_fall_back_per_batch(fault):
    r = LLMRanker(FallbackChain([MockLLM("gemini", fault=fault)]), batch_size=10).rank(CANDS)
    assert sorted(r.order) == list(range(5))
    assert r.fallback_batches == 1
    assert r.order == heuristic_order(CANDS)             # nothing scored -> pure heuristic


@pytest.mark.parametrize("fault", ["out_of_range", "duplicates", "fenced"])
def test_recoverable_llm_answers_are_cleaned_and_used(fault):
    r = LLMRanker(FallbackChain([MockLLM("gemini", fault=fault)]), batch_size=10).rank(CANDS)
    assert r.fallback_batches == 0 and sorted(r.order) == list(range(5))


def test_provider_outage_degrades_to_heuristic_and_is_logged():
    chain = FallbackChain([MockLLM("gemini", fault="error"), MockLLM("groq", fault="fatal")],
                          max_retries=0, backoff_s=0)
    r = LLMRanker(chain).rank(CANDS)
    assert r.order == heuristic_order(CANDS)
    assert r.batches[0]["fallback"] and "llm unavailable" in r.batches[0]["reason"]


def test_garbage_from_first_provider_is_rescued_by_the_next():
    chain = FallbackChain([MockLLM("gemini", fault="garbage"), MockLLM("groq")], backoff_s=0)
    r = LLMRanker(chain, batch_size=10).rank(CANDS)
    assert r.fallback_batches == 0 and r.batches[0]["provider"] == "groq"


# ------------------------------------------------------------------ join-level ranker

from minerllm.rankers import LLMJoinRanker, pattern_joins, schema_joins  # noqa: E402

STATS = stats(generate(UniversitySpec())[0])


def test_pattern_joins_lists_shared_argument_slots():
    edges = pattern_joins("(, (ADVISED_BY $s $p) (MEMBER_OF $p $d) (MAJORS_IN $s $d))")
    assert sorted(edges) == sorted([(("ADVISED_BY", 1), ("MAJORS_IN", 1)),
                                    (("ADVISED_BY", 2), ("MEMBER_OF", 1)),
                                    (("MAJORS_IN", 2), ("MEMBER_OF", 2))])


def test_pattern_joins_ignores_variables_within_one_clause():
    assert pattern_joins("(, (R $x $x) (S $y))") == []


def test_schema_joins_cover_all_slot_pairs():
    n_slots = sum(STATS.arity.values())                     # 9 binary relations -> 18 slots
    assert len(schema_joins(STATS)) == n_slots * (n_slots + 1) // 2


def test_join_ranker_scores_schema_once_and_reuses_it():
    llm = MockLLM("gemini")
    r = LLMJoinRanker(FallbackChain([llm]), batch_size=60)
    first = r.rank(CANDS, STATS, level=0)
    calls = llm.calls
    second = r.rank(CANDS, STATS, level=1)
    assert calls == 3 and llm.calls == 3                    # 171 joins / 60 per batch, then cached
    assert len(first.batches) == 3 and second.batches == []
    assert sorted(second.order) == list(range(len(CANDS)))


def test_join_ranker_orders_by_mean_join_score():
    r = LLMJoinRanker(FallbackChain([MockLLM("gemini")]))
    r.join_scores = {(("ADVISED_BY", 2), ("TEACHES", 1)): 10.0,
                     (("ADVISED_BY", 1), ("ENROLLED_IN", 1)): 9.0,
                     (("ENROLLED_IN", 2), ("TEACHES", 2)): 8.0}
    order = r.rank(CANDS, STATS).order
    assert order[0] == 4                                    # the P2 pattern: all joins known & high
    assert r.candidate_score(CANDS[4].pattern) == pytest.approx(9.0)
    assert r.candidate_score(CANDS[1].pattern) is None      # no known joins -> after scored ones


def test_join_ranker_outage_falls_back_to_heuristic():
    chain = FallbackChain([MockLLM("gemini", fault="fatal")], max_retries=0)
    r = LLMJoinRanker(chain).rank(CANDS, STATS)
    assert r.order == heuristic_order(CANDS)
    assert r.fallback_batches == len(r.batches) == 3


def test_join_prompt_has_no_data_atoms():
    seen = []

    class Spy(MockLLM):
        def complete(self, prompt, system="", timeout=60.0):
            seen.append(prompt)
            return super().complete(prompt, system, timeout)

    LLMJoinRanker(FallbackChain([Spy("gemini")])).rank(CANDS, STATS)
    assert seen and all("student_" not in p and "course_" not in p for p in seen)
    assert "ADVISED_BY.arg2 = " in "".join(seen) or "= ADVISED_BY.arg2" in "".join(seen)



def test_batches_run_in_parallel_and_keep_their_order():
    import threading
    import time as _t

    active, peak = [0], [0]
    lock = threading.Lock()

    class Slow(MockLLM):
        def complete(self, prompt, system="", timeout=60.0):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            _t.sleep(0.2)
            try:
                return super().complete(prompt, system, timeout)
            finally:
                with lock:
                    active[0] -= 1

    seen = []
    r = LLMJoinRanker(FallbackChain([Slow("gemini")]), workers=3,
                      on_batch=lambda i, n, resp, err, secs: seen.append((i, n)))
    start = _t.time()
    res = r.rank(CANDS, STATS)
    assert peak[0] == 3 and _t.time() - start < 0.5          # 3 batches at once, not 0.6 s
    assert sorted(seen) == [(0, 3), (1, 3), (2, 3)]
    assert [b["kind"] for b in res.batches] == ["joins"] * 3 and res.fallback_batches == 0


def test_timeout_is_passed_to_the_client():
    got = []

    class Spy(MockLLM):
        def complete(self, prompt, system="", timeout=60.0):
            got.append(timeout)
            return super().complete(prompt, system, timeout)

    LLMJoinRanker(Spy("gemini"), timeout_s=180, workers=1).rank(CANDS, STATS)
    assert got and set(got) == {180}
