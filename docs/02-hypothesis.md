# Step 2 — Hypothesis

> *Define a testable hypothesis that names the expected improvement and the metric.*

This hypothesis was written **before** any real-LLM run (Phase 3). The results in
[Step 6](06-results.md) are judged against it as written here.

## What we learned while building the prototype

Two measurements reshaped the hypothesis:

1. **Verification is cheap; generation and redundancy filtering are not.** Counting
   support for *every* unique 3-conjunct candidate on the university graph takes 3.8 s.
   The upstream run takes 65 s in total. Most of the cost was upstream's redundancy filter
   being applied in the wrong order, plus duplicates (Issue 4).
2. Fixing that (deduplicate before counting, filter only survivors) gives the **same
   output faster** with **no LLM at all**: 65 s → 19 s (university, 3 conjuncts), 90 s →
   14 s (Galaxy-200, 4 conjuncts). This gain is real, but it isn't the LLM's, so
   it's reported separately as the `exhaustive` baseline.

After that fix, support verification (plus the per-survivor filter) is the dominant cost
of the guided miner (≈ 80 % of its time), and its cost grows with each level. The
remaining question is whether an LLM can tell the miner **which candidates are worth
verifying**.

## H1 — main hypothesis (performance, with verifiable output)

> On the same data, minsup and depth, when the miner may verify only **30 %** of the
> unique candidates at each level, ordering them with the **LLM join ranker** recovers
> **≥ 90 %** of the exhaustive miner's **top-10 patterns by `isurp`**, and recovers
> **more** of them than the `random` and `heuristic` rankers at the same budget.

**Primary metric:** tie-aware recall@10. A pattern counts as top-10 if its exhaustive
`isurp` score is ≥ the 10th-best score (upstream's scores have many ties; see
[evidence](evidence/synthetic-validation.md)).

**Cost metrics:** candidates verified (machine-independent), miner wall time, LLM time,
tokens and estimated cost, LLM fallback rate.

**Guarantee, not hypothesis:** precision is 100 % at every budget. Every output pattern's
support is counted by MeTTa and re-checked by the oracle, and the output is always a
subset of the exhaustive output (tested in `tests/test_guided_petta.py`).

## H2 — ablation (where any gain comes from)

> On the **anonymised** university graph (relations `R1..R9`, entities `e1..eN`, otherwise
> identical), the LLM ranker's recall@10 advantage over the heuristic shrinks to
> **≤ 5 points**.

If H1 holds and H2 holds, the gain comes from the LLM's world knowledge about the relation
names. If H1 holds but H2 fails, the LLM is exploiting something other than semantics, and
we say so.

## Secondary measures

* **Planted recall:** on the strength-0.8 university graph, how many of the three planted
  patterns (the exhaustive miner's top 3) are found at each budget.
* **Budget curve:** recall@10 and recall@25 at budgets 10, 20, 30, 50 and 100 %.
* **`llm` vs `llm-direct`:** schema-level join scoring (≈ 3 calls per dataset) vs scoring
  every candidate (≈ 1 call per 60 candidates per level). Same quality question,
  very different cost.

## Amendment (Phase 4, 2026-11-16, before the LLM evaluation runs)

The first baseline runs showed that the structural `heuristic` is **degenerate**: at 10–30 %
budget it finds **0 patterns** on the university graph. It favours rare multi-relation joins,
which miss minsup, so the next level has nothing to extend. Beating it would prove
nothing. We therefore added a stronger cheap baseline, **`cardinality`**: estimated support
under independence, computed from the same schema statistics the LLM is shown. That makes
the test **stricter**:

* H1 now requires the LLM to beat the **best** of random, structural and cardinality.
* H2 measures the LLM's gap over the **cardinality** baseline.
* LLM rankers break ties (and fall back) using the cardinality order, so the LLM is
  measured as *what it adds on top of* the best cheap signal.

Before this amendment, only plumbing smoke runs of the LLM ranker had been made (single runs
at 30 % on the university graph, used to debug providers). They aren't part of the
evaluation.

## Rejection criteria (stated in advance)

| Outcome | Verdict |
|---|---|
| LLM recall@10 ≥ 90 % at 30 % **and** > every cheap baseline (random mean of 5 seeds, structural, cardinality) | H1 supported |
| LLM recall@10 ≥ 90 % but ≤ a cheap baseline | H1 **rejected**: a cheap baseline is enough, so no LLM is needed |
| LLM recall@10 < 90 % at 30 % | H1 **rejected** at this budget; report the budget at which 90 % is reached, if any |
| LLM − cardinality on anonymised data ≤ 5 points while > 5 on named data | H2 supported |

## Setup (identical for every compared method)

| | University (named) | University (anonymised) | Galaxy-400 (real) |
|---|---|---|---|
| data | `university_s0_st80` | `university_s0_st80_anon` | `galaxy_400` |
| minsup / conjuncts | 10 / 3 | 10 / 3 | 5 / 3 |
| scorer | `isurp`, normalised, db-ratio 0.5 | same | same |
| methods | upstream · exhaustive · random ×5 seeds · structural heuristic · cardinality · llm (per provider) · llm-direct | same | same |
| budgets | 10, 20, 30, 50, 100 % | same | same |

→ Continued in [Step 3 — Architecture](03-architecture.md).
