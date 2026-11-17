# Step 7 — Exploratory follow-up: merging the LLM with cardinality

> **Status: exploratory, not pre-registered.** H1 and H2 were tested and rejected in
> [Step 6](06-results.md); nothing here changes those verdicts. This follow-up was designed
> *after* seeing the Step 6 results, so it is tested only on **held-out datasets** that played
> no part in its design. The protocol below was committed before any held-out run.

## Why the join ranker lost: what the traces show

The first guess was that the LLM wastes the budget on joins that fall below minimum support.
The Step 6 traces rule that out. At 30 % budget on the university graph, the LLM keeps
**more** frequent patterns than cardinality at both levels:

| ranker (university, 30 %) | level 1 kept / checked | level 2 kept / checked | recall@10 |
|---|---:|---:|---:|
| cardinality | 70 / 333 | 358 / 2,704 | 67 % |
| llm (Groq, 4 runs) | 73–88 / 333 | 302–386 / 2,605–3,042 | 33 % ± 26 |
| llm (NVIDIA, 4 runs) | 86–87 / 333 | 373–380 / 2,950–2,990 | 48 % ± 4 |

So the two rankers find *different* frequent patterns. The university's reference top 10
(12 with ties) holds two kinds of pattern:

* **9 high-support structural patterns**, such as two students majoring in the same
  department (thousands of matches; the independence estimate is close to the truth).
  Cardinality ranks these first. The LLM tends to score same-relation joins as trivial.
* **the 3 planted patterns** (24–56 matches; estimate 6–15). Cardinality ranks them late,
  because a surprising pattern is by definition one the independence estimate under-predicts
  (slide 8 of the training). The LLM sometimes finds one.

The two signals fail in complementary ways.

## Design: `llm-hybrid`

Fixed before any held-out run:

1. **Merge, half each.** Interleave the cardinality order and the LLM join order
   (cardinality first, then the LLM's best not yet taken, and so on). With budget *k*, each
   signal contributes about *k*/2 candidates.
2. **Average 3 LLM samples per join**, to reduce the run-to-run variance seen in Step 6
   (Groq ± 26 points). Sample 1 uses the exact `llm` prompt; samples 2–3 add one line
   ("Independent rating 2 of 3"), so they are not answered from the cache.
3. **Failure path unchanged.** If every LLM call fails, the LLM order *is* the cardinality
   order, so the merge degrades to the cardinality baseline.
4. Everything else is unchanged: same prompt, schema statistics, validator, fallback chain,
   cache, miner configuration and verification.

Decision record: [ADR 0010](adr/0010-merge-llm-and-cardinality.md).
Code: `LLMHybridRanker` and `interleave` in [`minerllm/rankers.py`](../minerllm/rankers.py);
tests in `tests/test_rankers.py`.

Rejected alternative: a support gate (drop candidates whose estimate is below a fraction of
minsup, then let the LLM order the rest). The traces show the LLM's problem is not
infrequent picks, and on Galaxy the estimate is too rough: 2 of the top 10 have estimates
below 0.1 × minsup, so a gate would discard them.

## Protocol

| | |
|---|---|
| Budget | 30 % (the pre-registered budget) |
| Providers | Groq (`openai/gpt-oss-120b`), NVIDIA (`minimaxai/minimax-m3.1-flash`), each alone |
| Held-out data | `university_s1_st80`, `university_s2_st80` (fresh graphs, same generator, seeds 1, 2); `galaxy_400_s11` (a different Galaxy sample: 35 of 400 atoms shared with the development sample) |
| Comparison | cardinality, structural heuristic, random × 5 seeds, `llm`, `llm-hybrid`; same configs |
| Reference | exhaustive frequent set with isolated `isurp` scores, built per held-out dataset as in Step 5 |
| Metric | recall@10 (tie-aware), planted patterns found |
| Bar | the H1 rule applied mechanically: recall@10 ≥ 90 % **and** above every cheap baseline |
| Runs | one per arm (random: 5 seeds). No changes to the method after the held-out runs |

Development datasets (university, university-anon, galaxy400) also get an `llm-hybrid` run
for completeness, but they informed the design, so they are **not evidence**.

Known limitation, stated in advance: the held-out university graphs share the development
schema, so the LLM sees nearly the same schema description and may give the same join
scores (sample 1 can come from the cache). They test whether the merge generalises to new
data, not whether the LLM's judgments do. `galaxy_400_s11` has a different schema profile
and tests both.

Run:

```bash
make eval-explore      # references for the held-out sets, then every arm; resumable
```

### Amendment: repeated runs (17 Nov, recorded before running them)

The first held-out run had one run per LLM arm, and a dashboard re-run on university s1
tied cardinality where the protocol run had beaten it. To measure that variance:

* every held-out `llm` and `llm-hybrid` arm (Groq and NVIDIA) runs **2 more times** with the
  cache off (`make eval-explore-repeats`), so each run gets fresh LLM answers;
* the tables report **mean ± sd over all runs** (the first run included), and the H1-bar
  check uses the **mean**;
* nothing else changes: same method, datasets, budget and settings. Baselines are not
  re-run (cardinality and heuristic are deterministic; random already has 5 seeds);
* the results are reported as they come out, whichever way they go. The dashboard
  re-runs stay in the run log only and are not added to the tables.

## Run log

* **First run (commit `6d8ef30`): invalid.** Every LLM batch in every `llm` and
  `llm-hybrid` run fell back (`attempts: []` in the traces): the API keys in `.env` were not
  loaded inside PeTTa's embedded Python, so the chain had no providers, and each LLM arm
  silently ran the cardinality order. Its "results" equal cardinality exactly and say
  nothing about the LLM. Nothing in the method or protocol was changed in response.
* Fixes: keys are loaded from the repository's `.env` by explicit path (and into the
  parent process, so PeTTa inherits them); `make eval-*` refuses to start an LLM arm
  without its key and **stops** if a run gets no LLM answer at all; such runs are re-run on
  resume and excluded from every metric. The pre-registered Step 6 runs all had real LLM
  answers and are unaffected (their summary and verdicts recompute identically).
* Second run: below.
* **Re-runs from the dashboard** (rehearsal, 17 Nov, not part of the protocol; Groq, cache
  off, same settings): `heldout-galaxy400-s11` gave 70 % again. `heldout-university-s1` gave
  73 % with 0/3 planted patterns, a **tie** with cardinality (the protocol run: 82 %, 1/3).
  Groq scored the advisor-course joins lower that time, so those 2-clause pieces fell outside
  the level-1 budget and the planted 3-clause pattern could not be generated. One run per arm
  is not enough to say how often the hybrid wins; repeats are the next step.

## Results

Generated by `make eval-explore` (or `python -m minerllm eval explore-report`):

<!-- BEGIN EXPLORATORY -->
### Held-out datasets (the test)

Recall@10 at 30 % budget (planted patterns found in brackets; ± = sd over seeds/repeats):

| method | heldout-university-s1 | heldout-university-s2 | heldout-galaxy400-s11 |
|---|---:|---:|---:|
| cardinality | 73 % (0/3) | 73 % (0/3) | 20 % |
| heuristic | 0 % (0/3) | 0 % (0/3) | 0 % |
| random | 20 % ± 11 (0.8/3) | 11 % ± 9 (0.2/3) | 16 % ± 10 |
| llm:groq | 9 % (1/3) | 55 % (1/3) | 50 % |
| llm:nvidia | 45 % (0/3) | 45 % (0/3) | 0 % |
| llm-hybrid:groq | 82 % (1/3) | 82 % (1/3) | 70 % |
| llm-hybrid:nvidia | 73 % (0/3) | 73 % (0/3) | 30 % |

### Development datasets (design only; not evidence)

Recall@10 at 30 % budget (planted patterns found in brackets; ± = sd over seeds/repeats):

| method | university | university-anon | galaxy400 |
|---|---:|---:|---:|
| cardinality | 67 % (0/3) | 67 % (0/3) | 30 % |
| heuristic | 0 % (0/3) | 0 % (0/3) | 0 % |
| random | 28 % ± 10 (1.2/3) | 22 % ± 11 (0.4/3) | 24 % ± 8 |
| llm:groq | 33 % ± 26 (0.2/3) | 31 % ± 32 (1.5/3) | 22 % ± 23 |
| llm:nvidia | 48 % ± 4 (0.0/3) | 8 % (0.0/3) | 42 % ± 43 |
| llm-hybrid:groq | 75 % (1/3) | 83 % (2/3) | 70 % |
| llm-hybrid:nvidia | 67 % (0/3) | 67 % (0/3) | 30 % |
| llm-direct:groq | 67 % (0/3) | 67 % (0/3) | 30 % |

### Checks against the H1 bar (held-out only)

| dataset / method | recall@10 | best baseline | verdict |
|---|---:|---|---|
| heldout-university-s1 / llm-hybrid:groq | 82 % | cardinality 73 % | beats every baseline, below 90 % |
| heldout-university-s1 / llm-hybrid:nvidia | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s1 / llm:groq | 9 % | cardinality 73 % | below the best baseline |
| heldout-university-s1 / llm:nvidia | 45 % | cardinality 73 % | below the best baseline |
| heldout-university-s2 / llm-hybrid:groq | 82 % | cardinality 73 % | beats every baseline, below 90 % |
| heldout-university-s2 / llm-hybrid:nvidia | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s2 / llm:groq | 55 % | cardinality 73 % | below the best baseline |
| heldout-university-s2 / llm:nvidia | 45 % | cardinality 73 % | below the best baseline |
| heldout-galaxy400-s11 / llm-hybrid:groq | 70 % | cardinality 20 % | beats every baseline, below 90 % |
| heldout-galaxy400-s11 / llm-hybrid:nvidia | 30 % | cardinality 20 % | beats every baseline, below 90 % |
| heldout-galaxy400-s11 / llm:groq | 50 % | cardinality 20 % | beats every baseline, below 90 % |
| heldout-galaxy400-s11 / llm:nvidia | 0 % | cardinality 20 % | below the best baseline |

<!-- END EXPLORATORY -->
