# Presentation guide (≈ 14 minutes + questions)

The instructor said he'll look at: **what issues we found · what architecture and design
we chose · the prototype's quality (automation)**. The talk follows the six required steps
and answers those three as it goes.

---

## 0. One-sentence pitch (30 s)

> "We let an LLM decide **which** candidate patterns the Hyperon miner checks first. The
> miner still checks **everything it keeps**, so the output stays verifiable."

## 1. Problem: what issues we found (2.5 min)  → [docs/01](01-problem.md)

Before improving the miner we had to be able to *trust* it, and that is where most of the
issues came from:

| # | Issue | One-line evidence |
|---|---|---|
| 1 | Documented entry point does not run | returns `(partial pattern-miner …)`: 8 args to a 9-arg function |
| 2 | CI tracks PeTTa HEAD | 8/8 tests pass pinned, 3/8 on HEAD |
| 3 | End-to-end tests never execute | asserts lack `!`: we changed an expected value to 999999 and CI still passed |
| 4 | Output full of duplicates | 801 printed vs 137 distinct patterns (83 %) |
| 5 | State leaks between runs | 2nd run returns 32 patterns instead of 20 |
| 7 | Scoring silently drops half the patterns | 641 frequent in, 343 scored out: `add-atom-nodup` *unifies* |
| **6** | **Conjunction expansion explodes** | 2→3 conjuncts: 3× at 200 atoms, 10× at 800; 4 conjuncts: 90 s on 200 atoms |

*Say:* "Issue 6 is the one the LLM targets. The others are things we had to fix or work
around so that our measurements mean something. Each has a test or a script that
reproduces it (`make reproduce-issues`, `make test-metta`)."

## 2. Hypothesis (1 min)  → [docs/02](02-hypothesis.md)

* **H1:** at a 30 % verification budget the LLM join ranker recovers ≥ 90 % of the full
  miner's top-10 patterns and beats every cheap baseline.
* **H2:** on the anonymised graph (names replaced by R1..R9) the advantage disappears, so
  any gain comes from the LLM understanding the relation names.
* Rejection criteria written **before** the LLM runs. The one amendment (adding the
  stronger cardinality baseline) is dated and made the test **stricter**.

## 3. Architecture and design (2.5 min)  → [docs/03](03-architecture.md), [ADRs](adr/)

Show the component diagram, then the LLM-boundary table.

* **Generate → Select → Verify**, built from upstream's own functions; the submodule is not
  modified (ADR 0002).
* **The boundary:** the LLM returns 0–10 scores. It can't add a pattern, change a support,
  skip verification, see data, or stop the run (ADR 0003).
* **Join-level scoring:** the LLM scores schema joins ("is the advisor the department
  member?") in ~3 calls per dataset, reused at every level, instead of ~75 calls (ADR 0004).
* **Validator + failure path:** malformed answer → next provider → cardinality fallback;
  every step logged (ADR 0006).
* **Design decisions driven by measurement:** dedupe before counting and filter after
  (ADR 0005), separate search from scoring (ADR 0007), cardinality baseline (ADR 0008), dashboard that wraps the CLI (ADR 0009).

## 4. Prototype quality: automation (2 min, **live demo**)  → [docs/04](04-prototype.md)

Run `make demo` (DEMO_PAUSE=1 waits for Enter between steps):

1. upstream entry point fails, ours works
2. guided @ 100 % = upstream output, every support re-counted by the Python oracle
3. LLM run at 30 % budget, printing the top joins it scored
4. garbage answer → next provider; total outage → still completes
5. the generated results table

**Or show it on the dashboard** (`make ui`, open http://127.0.0.1:8000): *Replay a
recorded run* → University graph → *LLM (Groq), 30 %, repeat 1* → 4× → *Play recording*.
This run made real API calls, so the usage box fills with real requests, tokens and cost.
Point at the funnel shrinking, each LLM batch arriving in the events panel, then the
patterns and the run's marker on the comparison chart. Replays need no network, so this
works even if the venue's Wi-Fi or Groq's rate limit doesn't. Switch to *Run live* with
*Offline mock* (cached answers off) to show the real pipeline running.

For Step 7, replay the hybrid on held-out data: dataset *Galaxy sample s11 (held-out)* →
*LLM + cardinality (Groq), 30 %* → 4×. The comparison chart switches to the Step 7 results
and marks this run at 70 % against cardinality's 20 %.

*Automation to mention:* one command each for setup / doctor / tests / issues / profile /
evaluation / report; CI on GitHub (Python + MeTTa jobs); a strict MeTTa test runner; 100+
tests; resumable, cached evaluation; every run saves its exact script, config, trace and
oracle check.

## 5. Baseline (1 min)  → [docs/05](05-baseline.md)

Same data, same minsup, same depth, fresh process per run. Baselines: upstream (time), the
exhaustive miner (reference), random ×5 seeds, structural heuristic, cardinality.

* Without any LLM, our pipeline finds the **same frequent patterns 3× faster** than upstream
  (98 s → 31 s on the university graph) and scores all 641 of them (upstream: 343). Credited
  separately, not to the LLM.
* At 30 %: random 28 %, structural **0 %** (degenerate), cardinality **67 %** recall@10.

## 6. Results (2.5 min)  → [docs/06](06-results.md)

Show `results/figures/recall_vs_budget.png`, then the per-sample table.

* **Verdict: the evidence does not support the hypothesis.** At 30 %, the mean recall@10
  over 4 LLM samples was Groq 33 % / NVIDIA 48 % on the university graph, vs **cardinality
  67 %** with no LLM. H1 is rejected everywhere; H2 is not supported.
* **Unstable:** Groq gave 0–75 % on identical input (temperature 0). NVIDIA's 90 % on Galaxy
  came with two 0 % samples.
* **Why (from the traces):** the LLM mixes good joins with type errors (room = course,
  professor = course); `isurp`'s saturated top-10 rewards frequency, which cardinality
  targets directly. On the anonymised data, Groq's useful joins came from **reasoning about
  the statistics** (it found all student = student joins), not from names.
* **What held in all 135 runs:** 100 % precision, 0 oracle mismatches. *"A bad LLM cost us
  recall, never correctness: that's the architecture working."*
* **Cost:** 3 calls, ~10k tokens, **< $0.01 per dataset**; per-candidate scoring would need
  ~150 calls (rate-limited out on Groq).
* **Failures observed:** Gemini overloaded; 3 models retired mid-project; Groq's 8k tokens
  per minute limit. All handled by the chain, logged, and fixed.

*Say it plainly:* "The brief asks whether the evidence supports the hypothesis. It doesn't,
and we can show exactly why. The parts that worked, verifiability and the 3× LLM-free
speed-up, are measured just as carefully."

## 7. Follow-up: what the failure taught us (1.5 min)  → [docs/07](07-exploratory.md)

* **The traces showed why the LLM lost.** It wasn't wasting the budget on infrequent
  candidates: it kept *more* frequent patterns than cardinality (84 vs 70 at level 1). It
  kept *different* ones. Cardinality finds the high-support structural patterns; the LLM
  dismisses same-relation joins as trivial but sometimes finds the planted ones that
  cardinality, by definition, ranks last (training slide 8).
* **So we merged them** (`llm-hybrid`): half the budget each, 3 LLM ratings averaged per join.
  The design was committed as a protocol **before** any held-out run.
* **Held-out result (data never used in the design):** with Groq, recall@10 was **82 % / 82 % /
  70 %** against cardinality's **73 % / 73 % / 20 %**. It beat every baseline on all three
  sets, and found a planted pattern cardinality never did.
* **Still below 90 %, so H1 stays rejected.** NVIDIA's hybrid only tied cardinality on the
  university graphs, so the gain depends on the model. One run per arm, and about 10× slower
  in wall time (rate limits), so this is a direction, not a claim.
* **Run log, said openly:** the first held-out run was invalid (keys not loaded inside
  PeTTa, every LLM call silently fell back). We caught it in the logs, made the pipeline stop
  on such runs, and re-ran. Nothing in the method changed.

*Say it plainly:* "The pre-registered test failed. The traces told us why, and a design built
on that reason did better on fresh data, without reaching the bar. That's where I'd take it
next."

---

## Likely questions

**Why not let the LLM propose patterns directly?** Its output couldn't be trusted without
re-verifying everything, so nothing would be saved, and hallucinated patterns would leak
into the output. Ordering keeps precision at 100 % by construction.

**How do you know the symbolic side is right?** An independent Python oracle re-counts
every support (thousands of patterns, 0 mismatches), and the guided miner at 100 % equals
upstream on 4 configurations, including 4 conjuncts.

**Isn't the 3× speed-up the LLM's?** No. It comes from dedupe and filter ordering (ADR 0005),
is reported as its own baseline, and the LLM is compared against it.

**Why synthetic data?** It has an answer key (planted patterns). The anonymised copy is a
controlled ablation, and Galaxy-400 is the real-data check.

**What if the LLM is down during the demo?** That's step 4 of the demo: it falls back and
completes.

**So was the LLM a failure?** As a ranker, here, yes, and the evaluation is designed to say
so. But it showed where an LLM could help: type reasoning (it found the student = student
joins without names), and the planted patterns that statistics rank low (Groq found 3/3 in
two samples, cardinality 0/3).

**Isn't Step 7 just trying things until one works?** That's why it's labelled exploratory
and kept out of the H1 verdict. The design came from the traces, not from the test data;
it was committed before the held-out runs (see the git history); it was tested once, on
three datasets it had never seen; and the result is reported as it came out, including
NVIDIA's tie and the 90 % miss.

**Why only one run per arm in Step 7?** Time and rate limits: one Groq hybrid run takes
about 2.5 minutes, almost all of it waiting on the 8,000 tokens/minute limit. Averaging 3
ratings should reduce the variance seen in Step 6, but repeats are needed to measure how
much. That's the first thing I'd add.

**The hybrid is 10× slower than cardinality. How is that a performance improvement?** It
finds better patterns for the same number of verified candidates, which is the metric the
hypothesis named. Wall time on these small graphs is dominated by the API's rate limit.
The LLM cost is fixed per schema (joins are scored once), while verification cost grows
with the data and the number of conjuncts, so the trade-off improves on larger graphs. We
haven't measured that yet.

**What would you do next?** Repeat the Step 7 runs to measure variance; test the hybrid at
4 conjuncts and on larger real graphs, where verification is expensive; try other ways to
split the budget between the two signals; send patches 0001 and 0002 upstream.
