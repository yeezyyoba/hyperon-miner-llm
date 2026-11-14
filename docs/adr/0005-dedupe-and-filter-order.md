# ADR 0005 — Deduplicate before counting; filter redundancy after counting

**Status:** accepted · **Context:** [Issue 4](../01-problem.md#issue-4--the-output-is-full-of-duplicate-patterns)

**Context.** Upstream's output is 62–83 % clause-order duplicates at 3–4 conjuncts, and each
duplicate is counted and expanded separately. Profiling the guided miner also showed that
upstream's `remove_conjuncts_with_redundant_clauses` costs ≈ 4 ms per candidate (1.8 s for
492), while generating them costs 0.003 s. Upstream applies it only to survivors of the
support check.

**Decision.** The bridge deduplicates candidates by canonical form (`minerllm.patterns`)
before anything is counted. The redundancy filter runs in VERIFY, after the minsup check,
in the same order as upstream.

**Consequences.** Same output as upstream, faster with no LLM involved: 65 s → 19 s
(university, 3 conjuncts) and 90 s → 14 s (Galaxy-200, 4 conjuncts). The evaluation reports
this as its own baseline (`exhaustive`), so the LLM isn't credited for it.
