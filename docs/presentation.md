# Presentation guide

Everything needed to present the project: the talk track with timings, the background
you must be able to explain (how the miner and surprisingness work), the algorithms we
built, how the evaluation is computed, every result, the demo runbook and the questions
to rehearse.

The instructor said he'll look at **what issues we found · what architecture and design we
chose · the prototype's quality (automation)**. The talk follows the six required steps
(slide 14 of the training), answers those three as it goes, and ends with the follow-up.

* **Repository:** github.com/yeezyyoba/hyperon-miner-llm
* **Upstream:** iCog-Labs-Dev/hyperon-miner, `petta-main` @ `7461878` (git submodule, unmodified)
* **Assignment row (training slide 11):** *Performance · Candidate ranking*: "ranks candidate
  patterns before expensive evaluation; recall is measured; the miner still verifies actual support"

---

# Part A · Talk track (≈ 14 minutes + questions)

| Time | Section | Key line |
|---:|---|---|
| 0:30 | Pitch | "The LLM decides which candidates are checked first; the miner still checks everything it keeps." |
| 2:30 | 1 · Problem | "Issue 6 is the LLM's target; the others we had to fix so our measurements mean something." |
| 1:00 | 2 · Hypothesis | "Criteria fixed before the runs; the one amendment made the test stricter." |
| 2:30 | 3 · Architecture | "Scores in, nothing else. Precision is 100 % by construction." |
| 2:00 | 4 · Prototype + demo | "One command per step; the failure path is part of the demo." |
| 1:00 | 5 · Baseline | "3× faster with no LLM, credited separately. Cardinality is the bar." |
| 2:30 | 6 · Results | "The evidence does not support the hypothesis, and we can show exactly why." |
| 1:30 | 7 · Follow-up | "The traces told us why; a design built on that reason did better on unseen data." |

## 0 · Pitch (30 s)

> "The Hyperon miner's slowest step is conjunction expansion: it builds every possible join
> and counts each one. We let an LLM decide **which** candidates get counted first, and only
> count a budget of them. The miner still counts **everything it keeps**, so the output can
> never contain a wrong pattern."

## 1 · Problem: what issues we found (2.5 min) → [docs/01](01-problem.md)

Before improving the miner we had to be able to *trust* it, and that is where most of the
issues came from. Every one is reproducible (`make reproduce-issues`, `make test-metta`).

| # | Issue | Evidence |
|---|---|---|
| 1 | The documented entry point does not run | 8 arguments to a 9-argument function: returns `(partial pattern-miner …)`. Fixed in our `run_miner.metta`, patch 0001 |
| 2 | Setup tracks PeTTa HEAD | 8/8 tests pass on the pinned commit, 3/8 on HEAD. We pin PeTTa (ADR 0001) |
| 3 | End-to-end tests never execute | assertions lack `!`: changing an expected value to 999999 still passes |
| 4 | Output full of duplicates | 801 printed vs 137 distinct patterns (83 %) |
| 5 | State leaks between runs | the second run in a session returns 32 patterns instead of 20 |
| **6** | **Conjunction expansion explodes** | 2 → 3 conjuncts costs 3× more at 200 atoms, 10× at 800; 4 conjuncts take 90 s on 200 atoms (`make profile`) |
| 7 | Scoring silently drops half the patterns | `add-atom-nodup` *unifies* instead of comparing: 641 frequent in, 343 scored out. Patch 0002 |

*Say:* "Issue 6 is the one the LLM targets, and it matches training slide 7: this is where
PeTTa stopped at 3 conjuncts. The others are things we had to fix or work around so our
measurements mean something."

## 2 · Hypothesis (1 min) → [docs/02](02-hypothesis.md)

* **H1 (performance):** at a 30 % verification budget, the LLM join ranker recovers
  **≥ 90 %** of the full miner's top-10 patterns (recall@10 ≥ 0.9) **and** beats every cheap
  baseline.
* **H2 (ablation):** on the anonymised graph (relations renamed R1…R9, same structure) the
  advantage disappears, so any gain comes from understanding the relation names.
* Rejection criteria written **before** any LLM run. One dated amendment added the
  cardinality baseline after the structural heuristic turned out degenerate; it made the
  test **stricter**.
* **Guarantee, not hypothesis:** precision is 100 % at every budget.

## 3 · Architecture and design (2.5 min) → [docs/03](03-architecture.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [ADRs](adr/)

Show the component diagram, then the LLM-boundary table (Part C explains the algorithms).

* **Generate → Select → Verify** at every expansion level, built from upstream's own
  functions; the submodule is not modified (ADR 0002).
* **The boundary:** the LLM returns 0–10 scores. It can't add a pattern, change a support,
  skip verification, see the data, or stop the run (ADR 0003).
* **Join-level scoring:** the LLM scores schema joins ("is the advisor the department
  member?") in about 3 calls per dataset, reused at every level, instead of about 150
  per-candidate calls (ADR 0004).
* **Validator + failure path:** malformed answer → retry → next provider → cardinality
  order; the run always completes, every step is logged (ADR 0006).
* **Decisions driven by measurement:** dedupe before counting, filter after (ADR 0005);
  separate search from scoring (ADR 0007); cardinality baseline (ADR 0008); dashboard that
  wraps the CLI (ADR 0009); merging the LLM with cardinality (ADR 0010, Step 7).

## 4 · Prototype quality: automation (2 min, demo) → [docs/04](04-prototype.md)

Use the dashboard replay (Part F) or `make demo`. Then name the automation:

* one command per task: `setup`, `doctor`, `test-all`, `reproduce-issues`, `profile`,
  `eval-baselines`, `eval-llm`, `eval-explore`, `report`, `demo`, `ui`;
* CI on GitHub: Python tests (mock LLM), MeTTa tests on pinned PeTTa, dashboard build;
* 143 Python tests + 12 PeTTa integration tests + MeTTa tests with a strict runner (the
  fix for Issue 3);
* resumable, cached evaluation; every run saves its exact script, config, trace and oracle
  check; runs where no LLM answered are detected and refused.

## 5 · Baseline (1 min) → [docs/05](05-baseline.md)

Same data, same minsup, same depth, fresh PeTTa process per run.

* Without any LLM, our pipeline finds the **same frequent patterns 3× faster** than upstream
  (98 s → 31 s on the university graph; 17 s → 9 s on Galaxy) and scores **all 641** of them
  (upstream 343, Issue 7). Credited to dedupe and filter order (ADR 0005), not to the LLM.
* Recall@10 at 30 %, university graph: random **28 %**, structural heuristic **0 %**
  (degenerate), cardinality **67 %**.

## 6 · Results (2.5 min) → [docs/06](06-results.md)

Show `results/figures/recall_vs_budget.png`, then the table in Part E.

* **Verdict: the evidence does not support the hypothesis.** At 30 %, the LLM's mean
  recall@10 on the university graph was Groq **33 %** and NVIDIA **48 %**, against
  **cardinality 67 %** with no LLM. H1 rejected everywhere; H2 not supported.
* **Unstable:** identical input at temperature 0 gave Groq 0–75 %. NVIDIA's 90 % on Galaxy
  came with two 0 % samples.
* **Why (from the traces):** type errors mixed with good joins (room = course, professor =
  course); `isurp`'s saturated top 10 rewards frequency, which cardinality targets directly.
* **What held in all runs:** 100 % precision, 0 oracle mismatches. *"A bad LLM cost us
  recall, never correctness: that's the architecture working."*
* **Cost:** about 3 calls and 10k tokens per dataset, under $0.01.

*Say it plainly:* "The brief asks whether the evidence supports the hypothesis. It doesn't,
and we can show exactly why."

## 7 · Follow-up: what the failure taught us (1.5 min) → [docs/07](07-exploratory.md)

* **The traces showed why the LLM lost.** It wasn't wasting the budget on infrequent
  candidates: it kept *more* frequent patterns than cardinality (84 vs 70 at level 1). It
  kept *different* ones. Cardinality finds the high-support structural patterns; the LLM
  dismisses same-relation joins but sometimes finds the planted patterns that cardinality,
  by definition, ranks last (training slide 8).
* **So we merged them** (`llm-hybrid`, ADR 0010): half the budget each, 3 LLM ratings
  averaged per join. The design was committed as a protocol **before** any held-out run.
* **Held-out result** (data never used in the design): with Groq, recall@10 **82 % / 82 % /
  70 %** against cardinality's **73 % / 73 % / 20 %**. On both university graphs the
  hybrid's #1 pattern is the planted one: *students take courses taught by their own
  advisor*. Cardinality never found it.
* **Still below 90 %, so H1 stays rejected.** NVIDIA's hybrid only tied cardinality on the
  university graphs.
* **Not stable yet:** a re-run on university s1 the day before the presentation tied
  cardinality (73 %) and missed the planted pattern, because Groq rated the advisor-course
  joins lower. One run per arm is the main limitation.
* **Run log, said openly:** the first held-out run was invalid (keys not loaded inside
  PeTTa; every LLM call fell back). We caught it, made the pipeline refuse such runs, and
  re-ran without changing the method.

*Say it plainly:* "The pre-registered test failed. The traces told us why, and a design
built on that reason did better on unseen data, sometimes finding exactly the hidden
pattern statistics misses. It doesn't reach the bar and it isn't stable yet. That's where
I'd take it next."

---

# Part B · Background you must be able to explain

## B1 · Terms

| Term | What it is, in one breath |
|---|---|
| OpenCog Hyperon | The new OpenCog AGI framework. Knowledge lives in a graph database called the Atomspace; programs are written in MeTTa. |
| Atom / Atomspace | An atom is a symbol or an expression such as `(MEMBER_OF prof3 cs)`. The Atomspace is a space of atoms you query by pattern matching; in MeTTa a space is named like `&db`. |
| MeTTa | Hyperon's language. Code and data are both S-expressions: `(= (f $x) body)` defines a function, `!(expr)` runs one, `$x` is a variable, `(match &db pattern result)` queries a space. |
| PeTTa | A fast MeTTa implementation that compiles MeTTa to SWI-Prolog. The miner's `petta-main` branch targets it. Run a file with `bash .petta/run.sh file.metta`. |
| janus | The SWI-Prolog ↔ Python bridge. PeTTa uses it for `py-call`, which is how MeTTa calls our Python code. |
| Pattern | A conjunction of clauses with variables, written `(, clause1 clause2 …)`. `(, (ADVISED_BY $s $p) (MEMBER_OF $p $d))` means "a student advised by a professor who is a member of a department". |
| Support | The number of variable assignments that make every clause true. A pattern is *frequent* if support ≥ minsup. |
| Conjunct / depth | The number of clauses. `depth` 0 → 2 conjuncts, 1 → 3, 2 → 4. Each extra conjunct multiplies the work. |

## B2 · What the upstream miner does

It is a port of OpenCog Classic's Pattern Miner to MeTTa on PeTTa, and does two jobs
(training slide 4):

1. **Frequent pattern mining:** find every pattern, up to a number of clauses, with support ≥ minsup.
2. **Surprisingness scoring:** rank them by how much more (or less) often they occur than
   if their parts were independent.

The main call takes 9 arguments:
`(pattern-miner &res &db $initpat minsup depth surp-mode normalization db-ratio conj-exp)`.

| Parameter | Meaning (our setting) |
|---|---|
| `&res`, `&db` | output space, input dataset space |
| `$initpat` | initial pattern, a variable (the documented script omits it: Issue 1) |
| `minsup` | minimum support (10 university, 5 Galaxy) |
| `depth` | 0 → 2 conjuncts, 1 → 3 conjuncts (we use 1) |
| `surp-mode` | `none`, `isurp`, `isurp-old`, `jsd`, `IIsurp-*` (we use `isurp`) |
| `normalization` | isurp only: divide the distance so scores are 0–1 (on) |
| `db-ratio` | fraction of the database used when isurp estimates support by subsampling (0.5) |
| `conj-exp` | enable conjunction expansion (on) |

## B3 · How the miner finds frequent patterns

Training slide 5: **specialise, count, prune, repeat.**

1. **Abstract patterns:** replace a link's arguments with variables: `(TEACHES p1 c4)` → `(TEACHES $x $y)`.
2. **Specialise:** plug frequent values back in: `(MEMBER_OF $p cs)`.
3. **Count candidates:** keep those with support ≥ minsup.
4. **Conjunction expansion:** join frequent patterns that share a variable into 2-, 3-,
   4-clause patterns, count each, remove redundant clauses.

**Why pruning is safe (a priori property, slide 5):** a specialisation can never match more
data than its parent, so once a pattern drops below minsup, nothing beneath it can recover.
Conjunction expansion is *not* a specialisation (slide 7): joining two clauses with 3 A→B
and 3 B→C links each can give support 9. But the miner still only grows patterns from
**kept** pieces, which matters for the budget (Part C).

**Upstream functions in expansion:** `alpha_convert` (rename variables), `expand_conjunction_connect`
(all connected joins), `sup-num` (count matches: the costly part),
`remove_conjuncts_with_redundant_clauses`, `formatter`.

**Worked example (minsup 3):**

```
(ADVISED_BY ann p1) (ADVISED_BY bob p1) (ADVISED_BY cat p2)
(MEMBER_OF p1 cs)   (MEMBER_OF p2 cs)   (MEMBER_OF p2 math)

pattern                                         support
(, (ADVISED_BY $s $p))                          3
(, (ADVISED_BY $s $p) (MEMBER_OF $p $d))        4   ann-p1-cs, bob-p1-cs, cat-p2-cs, cat-p2-math
(, (ADVISED_BY $s $p) (MEMBER_OF $p cs))        3   a specialisation
```

Support counts *assignments*, so a 2-clause pattern can have more support than either clause.

**Canonical form:** `(, A B)` and `(, B A)` are the same pattern, and so are two patterns that
differ only in variable names. `patterns.py` sorts clauses and renames variables in order, so
duplicates are merged before counting (Issue 4).

## B4 · Surprisingness, step by step (isurp)

A pattern is surprising when what the data shows differs from what independent parts would
predict (training slide 8; Geisweiller & Goertzel 2019). Code: `experiments/surprisingness/`
and `experiments/utils/surp-utils/`.

**Step 1 · Empirical probability**, what actually happens:

  emp(P) = support(P) / |DB|ⁿ   (n = number of clauses; `universe-count`)

**Step 2 · Partitions**, how the pattern could be split: every way of grouping the clauses
into blocks except "all in one block". For {A, B, C}: {A}{B}{C}, {A,B}{C}, {A,C}{B}, {B,C}{A}.

**Step 3 · Independence estimate** per partition:

  est = Π emp(block) × eq-prob(shared variables)

Blocks share variables (`$p` in A and B). Independence would allow any value there, so
`eq-prob` multiplies by the chance the shared variable takes the same value in both blocks:
roughly 1 / (distinct values it takes).

**Step 4 · Interval:** the minimum and maximum estimate over all partitions, [emin, emax]. Any
probability inside is "explainable by independence of some split".

**Step 5 · isurp**, distance from the interval:

  dst = emp − emax if emp > emax;  emin − emp if emp < emin;  0 otherwise
  isurp = min(1, dst / max(emp, emax))  (normalised)

0 = fully explained by independence; near 1 = strongly surprising.

**Worked example.** |DB| = 10, P = (, A B) sharing `$x`, support 6:
emp(P) = 6 / 10² = 0.06. One partition {A}{B}: emp(A) = 0.4, emp(B) = 0.5, product 0.2; `$x`
has 5 distinct values, so eq-prob = 1/5 and est = 0.04. Interval [0.04, 0.04].
emp 0.06 > 0.04 → dst = 0.02 → isurp = 0.02 / 0.06 = **0.33**: P occurs 1.5× more than
independence predicts.

**The other modes** (slide 9):

| Mode | Idea |
|---|---|
| `isurp-old` | lightweight version of the same interval distance, without subsampled support |
| `jsd` | turns the empirical and estimated probabilities into truth values (strength + confidence → Beta distributions), samples their CDFs in 10 bins, and returns the Jensen–Shannon distance. Uncertainty is built in: small counts give flat distributions and low scores |
| `IIsurp-*` | compares against estimates built from sub-pattern averages |

## B5 · Why we used isurp and not JSD

JSD is not a "better isurp"; it answers a different question. isurp: *how far outside the
independence range is the observed frequency?* JSD: *how different are the observed and
predicted distributions, given how much evidence we have?* Slide 9's example: two different
head rates after 3 coin tosses aren't surprising; after a billion tosses even a tiny gap is.

We kept `isurp` because:
1. it is upstream's full I-Surprisingness (slide 9) and its most tested scorer;
2. its normalised 0–1 score is easy to interpret and compare across datasets;
3. the project's question was **which candidates to check**, not **how to score**, so the
   scorer stayed fixed and only the ranker changed.

What to admit: the choice was not recorded as an ADR, and it matters. isurp's top 10 is
**saturated** (many frequent, generic patterns tie near 1.0), which is part of why
cardinality is so strong. JSD would likely not remove that bias, because large counts give
high confidence, so it also rewards deviations in high-support patterns. Repeating the
evaluation with `jsd` as the target is a good next step.

---

# Part C · The algorithms we built

## C1 · Generate → Select → Verify (per level)

```
frequent single clauses
  └─ for each level 0..depth:
       GENERATE (MeTTa)  all connected candidates (upstream alpha_convert + expand_conjunction_connect), no counting
       SELECT  (Python)  dedupe by canonical form → ranker orders them → keep the first ⌈budget × unique⌉
       VERIFY  (MeTTa)   exact sup-num ≥ minsup on the kept ones only, then the redundancy filter
  └─ score survivors with upstream isurp, each in its own space (ADR 0007, avoids Issue 7)
  └─ Python oracle re-counts every support
```

The budget is per level. Because the next level only grows from **kept** patterns, a
candidate cut at level 1 can prevent a good 3-clause pattern from ever being generated.

## C2 · Rankers

| Ranker | How it orders candidates |
|---|---|
| exhaustive | all of them (the 100 % reference) |
| random | seeded shuffle (5 seeds) |
| heuristic | structural prior: `2·(distinct relations) − (unshared variables) − 0.25·(variables)` |
| **cardinality** | the textbook independence estimate of support, likely-frequent first (below) |
| **llm** | the LLM scores each schema join once; a candidate's score is the mean of its joins' scores; ties by cardinality |
| llm-direct | the LLM scores every candidate (≈ 150 calls; cost comparison only) |
| **llm-hybrid** | cardinality order interleaved with the llm order, 3 LLM ratings averaged per join (Step 7) |

**Cardinality estimate.** Multiply the sizes of the relations; for each extra occurrence of a
shared variable divide by the largest number of distinct values among its slots; for each
constant divide by its slot's distinct count. Example: 60 `MAJORS_IN` atoms over 4
departments → `(, (MAJORS_IN $a $d) (MAJORS_IN $b $d))` ≈ 60 × 60 / 4 = **900**;
`(MAJORS_IN $a dept_0)` ≈ 60 / 4 = **15**. It uses only the statistics the LLM is also shown.
It is strong on frequency, and blind to surprise: a surprising pattern is by definition one
whose real support beats this estimate, so cardinality ranks planted patterns low.

**LLM join scoring.** The LLM sees the schema (relation names, arities, atom counts, distinct
values per argument), never data rows, and scores every join such as
`ADVISED_BY.arg2 = MEMBER_OF.arg1` ("the advisor is the member") from 0 to 10, in batches
of 60. A candidate joining on three slots gets the mean of those three scores. About 3 calls
per dataset, scored once and reused at every level.

**Hybrid merge.** Take cardinality's best, then the LLM's best not yet taken, alternating. With
a budget of k, each signal contributes about k/2. Join scores are the mean of 3 independent
ratings. If every LLM call fails, the LLM order *is* the cardinality order, so the hybrid
degrades to the baseline.

## C3 · Validator and failure path

The validator never trusts the model: not JSON → reject the batch; unknown ids → dropped ("the
LLM cannot invent candidates"); duplicates → keep the first; scores outside 0–10 → clamped;
fewer than 50 % of ids scored → reject. A rejected or failed batch goes to the next provider
(Groq → NVIDIA → Gemini, with retries that honour rate-limit waits); if all fail, that batch
uses the cardinality order. The run always completes and every attempt is in the trace.

---

# Part D · How the evaluation is computed

**Datasets.**

| Dataset | Atoms | Why |
|---|---:|---|
| university (synthetic) | 504 | has an answer key: 3 planted patterns at strength 0.8 (P1 major in advisor's department, P2 enrolled in advisor's course, P3 course offered by teacher's department) |
| university-anon | 504 | same graph, names replaced (R1…R9, e1…eN): the H2 ablation |
| galaxy400 | 400 | deterministic subset of upstream's real Galaxy data |
| held-out (Step 7) | 504 / 504 / 400 | university seeds 1 and 2 (fresh graphs), a different Galaxy sample (35 of 400 atoms shared) |

All at 3 conjuncts, `isurp` normalised, db-ratio 0.5; minsup 10 (university) and 5 (Galaxy);
fresh PeTTa process per run.

**Reference.** The exhaustive miner (budget 100 %) gives the complete frequent set; every pattern
is scored by upstream's `isurp`, each in its own fresh space (so Issue 7 can't drop any).

**Tie-aware top-K.** isurp has many ties, so the top 10 is every pattern scoring at least the
10th-best score. On held-out university s1 that is **11** patterns.

**Recall@K** = |found ∩ top-K| / |top-K|. Example: on university s1 the Groq hybrid found 9 of
the 11 → **82 %**; cardinality found 8 → **73 %**. The whole difference is one pattern: the
planted one.

**Budget** = the fraction of *unique* candidates the miner may verify at each level.
**Precision** = the share of output patterns that are truly frequent with the right support
(checked against the reference and the oracle): 100 % in every run.
**Planted found** = how many of the 3 planted patterns appear in the output (synthetic only).

**Arms.** Exhaustive, random × 5 seeds, heuristic, cardinality, llm per provider, llm-direct,
at budgets 10/20/30/50 %; at 30 %, each LLM cell has 4 samples (cache off) to measure
stability. Reported as mean ± standard deviation.

**Verdict rules** (applied mechanically by `evaluate.py`):
* **H1**, per dataset and provider: supported only if recall@10 ≥ 0.9 **and** above the best
  of random, heuristic and cardinality.
* **H2**: supported only if the LLM's gap over the best baseline is > 5 points with names and
  ≤ 5 points without.
* **Step 7** applies the H1 rule to held-out data only, labelled exploratory, never folded
  into H1.

---

# Part E · Results

## E1 · Step 6 (pre-registered), recall@10 at 30 %

| Dataset | Groq (4 samples) | NVIDIA (4 samples) | Cardinality | Random (5 seeds) | Heuristic |
|---|---|---|---:|---|---:|
| university | 33 ± 26 % (67/50/17/0) | 48 ± 4 % (50/50/50/42) | **67 %** | 28 ± 10 % | 0 % |
| university-anon | 31 ± 32 % (75/50/0/0) | 8 ± 0 % | **67 %** | 22 ± 11 % | 0 % |
| galaxy400 | 22 ± 23 % (60/20/10/0) | 42 ± 43 % (90/80/0/0) | 30 % | 24 ± 8 % | 0 % |

**H1 rejected** (no cell reaches 90 %; cardinality beats every LLM mean on both synthetic
graphs). **H2 not supported** (there was no advantage to lose).

Where the LLM helped: on anonymised data Groq found every *student = student* join by
reasoning about distinct-value counts, and found 3/3 planted patterns in two samples
(cardinality 0/3 at 30 %).

## E2 · Step 7 (exploratory), held-out data, recall@10 at 30 %

| Method | university s1 | university s2 | galaxy s11 |
|---|---|---|---:|
| cardinality (best baseline) | 73 % (0/3) | 73 % (0/3) | 20 % |
| random (5 seeds) | 20 ± 11 % | 11 ± 9 % | 16 ± 10 % |
| LLM joins · Groq | 9 % (1/3) | 55 % (1/3) | 50 % |
| LLM joins · NVIDIA | 45 % (0/3) | 45 % (0/3) | 0 % |
| **LLM + cardinality · Groq** | **82 % (1/3)** | **82 % (1/3)** | **70 %** |
| LLM + cardinality · NVIDIA | 73 % (0/3) | 73 % (0/3) | 30 % |

Groq hybrid: "beats every baseline, below 90 %" on all three. NVIDIA hybrid: ties on the
university graphs, small gain on Galaxy. One run per arm.

**Re-runs from the dashboard (not part of the protocol):** Galaxy s11 gave **70 %** again;
university s1 gave **73 %** with **0/3** planted, a tie with cardinality. Groq scored the
advisor-course joins lower that time, and the budget cut those pieces at level 1, so the
planted pattern could not be generated. This is the instability that repeats should measure.

## E3 · Speed, cost and failures

| | |
|---|---|
| LLM-free pipeline vs upstream | same frequent patterns, 98 s → 31 s (university), 17 s → 9 s (Galaxy); 641 patterns scored vs 343 |
| `llm` cost | about 3 calls, 10k tokens, under $0.01 per dataset |
| `llm-hybrid` cost | 9 calls, about 23–26k tokens, about $0.01 per dataset; 45–160 s wall time vs 3–15 s for cardinality, almost all waiting on Groq's 8,000 tokens/minute limit |
| Failures met and handled | Gemini overloaded; three models retired mid-project; Groq rate limits (retries honour its wait time); one invalid run (keys not loaded) caught and refused |
| Guarantees | 100 % precision and 0 oracle mismatches in every run |

---

# Part F · Demo runbook

## The night before

```bash
cd ~/Documents/hyperon-miner-llm
source .venv/bin/activate
git pull && git submodule update --init
make doctor            # every line OK
make test              # fast Python tests (mock LLM)
DEMO_PAUSE=0 make demo # full dry run
make ui                # then open http://127.0.0.1:8000 and Cmd + Shift + R
```

If `make ui` says *address already in use*: `lsof -nP -iTCP:8000 -sTCP:LISTEN`, then `kill <PID>`.
Restart `make ui` after any code change.

## Dashboard (recommended: no waiting, no network needed)

1. **Replay a recorded run** → *University graph* → *LLM (Groq), 30 %, repeat 1* → **4×** → *Play recording*.
   This run made real API calls. Point at the funnel shrinking, each LLM batch arriving, the
   usage box, and the run's marker on the comparison chart.
2. **Step 7:** dataset *University graph s1 (held-out)* → *Evaluation runs → LLM + cardinality
   (Groq), 30 %* → **4×**. Pattern **#1** is highlighted *Planted: enrolled in advisor's
   course*; its tiles read **advised by** (a, b) · **enrolled in** (a, c) · **teaches** (b, c):
   "student a is advised by professor b, takes course c, and b teaches c". Click **Planted**.
   The chart shows 82 % vs cardinality's 73 %.
3. Say that a re-run tied cardinality (E2), and why.
4. Optional, to show the real pipeline: *Run live* → *University graph* → *LLM ranks joins* →
   30 % → *Offline mock*, cached answers off.

## Terminal (`make demo`, waits for Enter between steps)

| Step | What appears | What to say |
|---|---|---|
| 1 | upstream prints `(partial pattern-miner …)`; ours prints a count | "The documented entry point doesn't mine: Issue 1. We fixed it and pinned PeTTa." |
| 2 | guided at 100 % = upstream, oracle OK | "Before adding an LLM, we prove our miner equals upstream." |
| 3 | LLM run at 30 % and the joins it scored | "The LLM sees the schema, never the data." |
| 4 | garbage → next provider; outage → still completes | "A bad LLM costs recall, never correctness." |
| 5 | results table and verdicts | "Generated from the raw runs. Rejected, and here's why." |
| 6 | Step 7 held-out table | "The follow-up, tested on unseen data." |

## If something breaks

No internet: use replays (they need none). A provider is slow: Groq waits for its retry time;
keep talking about the boundary. PeTTa errors: `make doctor`; the macOS janus fix is in the
README. The page looks out of date: restart `make ui` and hard-refresh.

---

# Part G · Questions to rehearse

**Why not let the LLM propose patterns directly?** Its output would need re-verifying anyway,
so nothing is saved, and hallucinated patterns could leak into the results. Ordering keeps
precision at 100 % by construction.

**How do you know the symbolic side is right?** An independent Python oracle re-counts every
support (0 mismatches), and the guided miner at 100 % equals upstream on 4 configurations,
including 4 conjuncts.

**Isn't the 3× speed-up from the LLM?** No. It comes from deduplicating before counting and
filtering after verification (ADR 0005), and is reported as its own baseline.

**What is isurp, in one sentence?** How far a pattern's observed probability falls outside the
range that independence between its parts would predict, normalised to 0–1.

**Why isurp and not JSD? Isn't JSD more advanced?** See B5: JSD measures something different
(distributions with uncertainty), not a better version of the same thing. We kept upstream's
main scorer fixed to change one variable at a time. Its saturation is a real limitation, and
JSD would likely still reward frequent patterns. Testing the result under `jsd` is next.

**Why is cardinality so strong?** It estimates join sizes from distinct-value counts, and the
saturated isurp top 10 mostly rewards frequent patterns, which is what join size predicts.

**Why synthetic data?** It has an answer key (planted patterns); the anonymised copy isolates
the effect of names; Galaxy is the real-data check.

**Temperature 0, so why different answers?** `gpt-oss-120b` is a reasoning model: its hidden
reasoning differs between runs, and hosted models are not bit-for-bit deterministic (requests
are batched on shared GPUs). Then the miner amplifies it: the budget is a hard cut, and the
next level only grows from kept pieces, so a small change in one join's score can decide
whether a pattern is found at all.

**Isn't Step 7 just trying things until one works?** That's why it's labelled exploratory and
kept out of the H1 verdict. The design came from the traces, not the test data; it was
committed before the held-out runs (see the git history); it was tested once on three unseen
datasets; and the result is reported as it came out, including NVIDIA's tie, the 90 % miss
and the re-run that tied.

**Why only one run per arm in Step 7?** Time and rate limits: one Groq hybrid run takes about
2.5 minutes. The re-run that tied shows why repeats are the first thing to add.

**The hybrid is 10× slower than cardinality. How is that an improvement?** The hypothesis
measures patterns found per candidate verified, not wall time. Wall time here is the API's
rate limit. The LLM cost is fixed per schema while verification grows with data and
conjuncts, so the trade-off should improve on larger graphs; we haven't measured that.

**So was the LLM a failure?** As a ranker on its own, here, yes, and the evaluation was
designed so it could say so. Combined with statistics, it found the hidden relationship
statistics misses, on unseen data, though not reliably yet.

**Does the LLM see private data?** No. Relation names, argument positions and aggregate counts,
never data rows (tested). Keys stay in a git-ignored `.env`.

**What would you do next?** Repeat the Step 7 runs to measure variance; stabilise the LLM's
judgments (more samples, a more deterministic model, or protecting promising joins at the
first level); evaluate under `jsd`; test at 4 conjuncts and on larger real graphs; send
patches 0001 and 0002 upstream.

---

# Glossary

| Term | Meaning |
|---|---|
| Budget | fraction of unique candidates the miner may verify at each level |
| Recall@10 | share of the reference top 10 (by isurp, ties included) that a run also found |
| Precision | share of output patterns that are truly frequent with the right support |
| Schema join | two relation slots that hold the same entity, e.g. `TEACHES.arg1 = MEMBER_OF.arg1` |
| Cardinality ranker | orders candidates by estimated join size (independence over distinct-value counts); no LLM |
| Hybrid ranker | cardinality and LLM orders interleaved, half the budget each |
| Oracle | our independent Python support counter |
| Planted pattern | a dependency deliberately built into the synthetic data (P1–P3) at strength 0.8 |
| Held-out data | datasets never used to design a method, used only to test it |
| ADR | architecture decision record: what was decided, why, and what else was considered |
| Canonical form | a unique spelling of a pattern (sorted clauses, renamed variables) |
| Fallback | when every provider fails, the cardinality order is used so the run completes |
