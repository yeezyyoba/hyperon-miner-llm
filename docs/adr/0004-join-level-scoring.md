# ADR 0004 — Score schema joins, not candidates

**Status:** accepted (per-candidate scoring kept as `llm-direct` for comparison)

**Context.** The first LLM ranker scored every unique candidate. On the university graph
(30 % budget, 3 conjuncts) that took 75 LLM calls and ≈ 128k tokens in one run (token counts estimated by the mock). With hosted
models at a few seconds per call, that's minutes of LLM time to save ≈ 15 s of
verification, so the LLM would cost more than it saves.

**Decision.** The default `llm` ranker asks the LLM to score every **join** between two
argument slots of the schema (`ADVISED_BY.arg2 = MEMBER_OF.arg1`, …): 171 joins for the
university graph, so 3 calls. The scores depend only on the schema, so they're computed once
per run (and cached across runs) and reused at every level. A candidate's score is the mean
of its joins' scores; the heuristic breaks ties.

**Consequences.** ≈ 3.7k tokens per run instead of ≈ 128k, and LLM cost no longer grows
with the number of candidates or the depth. The LLM's judgement is also easier to inspect:
the trace logs the top-scored joins. Trade-off: a join score can't express
interactions between three or more clauses. `llm-direct` remains available, and the
evaluation compares the two.
