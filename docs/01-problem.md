# Step 1 — Problem

> *Select one concrete problem and support it with an observation, example or measurement.*

Before an LLM can improve the miner, we need a miner we can run and measure reliably.
Setting that baseline up surfaced **five reliability issues** in the upstream repository
(Issues 1–5). We fixed or worked around all of them, and they matter because they decide
whether any later measurement can be trusted. **Issue 6 is the problem the LLM targets.**

All evidence was collected on `iCog-Labs-Dev/hyperon-miner` **petta-main @ `7461878`**
(2026-09-27) and can be regenerated:

```bash
make reproduce-issues   # Issues 1, 2   -> runs/issues/*.log
make test-metta         # Issues 3, 4, 5 (characterisation tests)
make test-all          # + harness vs independent oracle
make profile            # Issue 6       -> docs/evidence/baseline-profile.md
```

| # | Issue | Kind | Status in this repo |
|---|---|---|---|
| 1 | The documented entry point does not run | usability | fixed (`run_miner.metta`) + [upstream patch](../patches/) |
| 2 | CI depends on PeTTa HEAD: 8/8 tests pass pinned, 3/8 on HEAD | reproducibility | fixed (`setup.sh` pins PeTTa) + upstream patch |
| 3 | End-to-end tests never execute their assertions | correctness | fixed (strict runner + live regression tests) |
| 4 | Output is full of clause-order duplicates (62–83 % at 3–4 conjuncts) | correctness / performance | detected and merged by `minerllm.patterns.canonical` |
| 5 | Global spaces leak state between miner runs | correctness | worked around (one process per run) |
| **6** | **Conjunction expansion cost explodes with depth** | **performance** | **target of the LLM integration** |

---

## Issue 1 — The documented entry point does not run

The README tells users to run `run_miner.metta`. On the pinned PeTTa it prints no
patterns; its last output line is

```
(partial pattern-miner (&res &db 3 0 none none none true))
```

A `partial` result is PeTTa's way of saying the function received the wrong number of
arguments. Two mismatches cause it:

1. `pattern-miner` takes **9** arguments (`$initpat` was added later), but the script
   passes **8**.
2. The script imports `frequent-pattern-miner.metta` (an 8-argument
   `frequency-pattern-miner`), while `pattern-miner.metta` calls the **generic**
   7-argument version and needs `valuation`, `shallow-abstractions`, `specialization`
   and `candidate`, none of which the script imports.

**Fix:** [`run_miner.metta`](../run_miner.metta) in this repo, plus
[`patches/0001-…`](../patches/), which makes upstream's own script return 76 patterns
(minsup 3) instead of none.

## Issue 2 — CI depends on PeTTa HEAD

Upstream `setup.sh` checks out PeTTa's latest commit on every run. Running upstream's
own CI whitelist (`scripts/run-tests.py`, 8 test files):

| PeTTa | Date | Passed | Failed |
|---|---|---:|---:|
| `9e5929a` (pinned, last commit before the miner's) | 2026-09-27 | **8** | 0 |
| `ee5cacb` (HEAD at time of writing) | 2026-10-28 | 3 | **5** |

Nothing in the miner changed; only PeTTa moved. **Fix:** `setup.sh` pins
`PETTA_COMMIT` (overridable), and CI caches it.

## Issue 3 — End-to-end tests never execute their assertions

In PeTTa only top-level expressions starting with `!` are evaluated. The two
end-to-end tests write their pipeline calls and assertions **without** `!`:

| Test file | `!(assertEqual …)` (executed) | `(assertEqual …)` (never executed) |
|---|---:|---:|
| `pattern-miner/tests/test-pattern-miner.metta` | 1 | **8** |
| `miner/tests/test-surp.metta` | 6 | **2** |

**Demonstration:** changing an expected support in `test-pattern-miner.metta` from `10`
to `999999` still gives exit code 0 and no ❌, so CI reports PASSED. Unit-level files
such as `test-common-utils.metta` use `!(assertEqual …)` and do fail when corrupted. So
the gap is specifically the full mining pipeline.

**Fix:** [`scripts/run_metta_tests.py`](../scripts/run_metta_tests.py) refuses test files
that contain non-executed assertions, files with zero assertions, and `(partial …)`
results. [`experiments/upstream-regression/tests/`](../experiments/upstream-regression/tests/)
re-states upstream's expectations with live `!(test …)` assertions (11 assertions, all
passing).

## Issue 4 — The output is full of duplicate patterns

The frequent miner prints the same pattern several times, with the clauses in a different
order, for example on the sample data:

```
(supportOf (, (Inheritance $_0 man) (Inheritance $_0 $_1)) 30)
(supportOf (, (Inheritance $_0 $_1) (Inheritance $_0 man)) 30)
```

At minsup 10 / depth 0 this makes 12 printed patterns but only 11 distinct ones. Scoring
then keeps one copy, so an `isurp` run returns 11. *(An earlier draft of this document
called that a "silently dropped" pattern. The canonical-form check in Phase 2 showed it's a
duplicate, and the characterisation test now asserts the correct behaviour.)*

The redundancy grows with depth (Galaxy subsets, minsup 5):

| conjuncts | printed | distinct | duplicates |
|---:|---:|---:|---:|
| 2 | 30 – 161 | 22 – 99 | 27 – 39 % |
| 3 | 121 – 1104 | 46 – 418 | 61 – 63 % |
| 4 (200 atoms) | 801 | 137 | **83 %** |

This isn't just cosmetic. Every printed duplicate also went through a separate support
count, and at depth > 0 each duplicate is expanded again at the next level. That
feeds directly into Issue 6.

**Fix in this repo:** `minerllm/patterns.py` puts every pattern in a canonical form (clause
order and variable names normalised). All result sets in this project are compared in
that form, and the guided miner deduplicates candidates **before** paying for support.
Duplicate groups always carry identical supports (checked on every profiled run), so
merging them loses nothing.

## Issue 5 — Global spaces leak state between runs

`pattern-miner` writes intermediate results into the global spaces `&cndpspace` and
`&conjspace` and never clears them. Running depth 0 and then depth 1 in the same process
returns **32** patterns for depth 1 instead of the **20** a fresh process returns
(`test-upstream-depth0.metta` asserts this). Upstream's end-to-end test runs both
configurations in one file, so it would fail if Issue 3 did not hide it.

**Workaround:** every miner run in this repo uses a fresh PeTTa process.

---

## Issue 6 — Conjunction expansion cost explodes with depth (the target)

The deck's own summary: conjunction expansion *"is the step that stopped PeTTa at 3
conjuncts"*, because each extra conjunct multiplies the candidates that must be counted.

**Mechanism.** At each level `expand_conjunction` joins every frequent conjunction with
every frequent single-clause pattern, over every possible variable linkage, and calls
`checker` (a full `sup-eval` match against the database) on **every** candidate. Only
then does it apply the minimum-support filter. The apriori property guarantees that
nothing frequent is lost, but it prunes **after** paying for the support count, not before.

**Measurement** (unmodified upstream miner, Galaxy workflow graph, minsup 5):

| Galaxy atoms | 2 conjuncts | 3 conjuncts | 4 conjuncts | time 3 ÷ 2 |
|---:|---:|---:|---:|---:|
| 200 | 1.5 s · 22 patterns | 4.9 s · 46 patterns | 90.2 s · 137 patterns | **3.3×** |
| 400 | 2.4 s · 35 patterns | 12.2 s · 115 patterns | – | **5.1×** |
| 600 | 3.8 s · 62 patterns | 28.0 s · 229 patterns | – | **7.4×** |
| 800 | 5.7 s · 99 patterns | 54.7 s · 418 patterns | – | **9.6×** |

(patterns = distinct patterns, see Issue 4.) The 2→3 multiplier itself grows with data size (3.3× → 9.6×). Going to **4 conjuncts on only 200 atoms takes 90 s, 18× the 3-conjunct run**. Every printed support in these runs was re-counted by the independent oracle: **0 mismatches**. Full data: [evidence/baseline-profile.md](evidence/baseline-profile.md).

**Why Galaxy.** It has 9 relation types with meaningful names (`HAS_STEP`,
`STEP_USES_TOOL`, `FEEDS_INTO`, …). That makes the candidate space large and makes the
question "which joins are worth checking?" one where world knowledge could plausibly help.
Toy `Inheritance` datasets are cheap enough that no optimisation would matter.

### Problem statement

> The miner spends its budget evaluating the support of every syntactically possible
> conjunction, most of which are uninteresting. The cost grows multiplicatively with each
> conjunct, so the miner cannot go deeper than 3 conjuncts on realistic graphs. We want
> to evaluate **fewer candidates** while still finding **the patterns that matter most**
> (the top-ranked by surprisingness), **without letting an LLM decide what is true**.

→ Continued in [Step 2 — Hypothesis](02-hypothesis.md).
