# Synthetic data validation

Generated with `minerllm datagen` (504 atoms, 9 relations; see `minerllm/datagen.py`) and mined with the **unmodified upstream miner** via `minerllm mine` (minsup 10, 3 conjuncts, `isurp`, normalised, db-ratio 0.5). Every printed support was re-counted by the oracle: 0 mismatches in all runs below.

## 1. Planted patterns come out on top (strength 0.8)

343 distinct patterns, 82 s.

| rank | isurp | support | pattern |
|---:|---:|---:|---|
| 1 | 1.000 | 24 | `(, (MEMBER_OF $v0 $v1) (OFFERED_BY $v2 $v1) (TEACHES $v0 $v2))` **← P3 (planted)** |
| 2 | 0.999 | 48 | `(, (ADVISED_BY $v0 $v1) (MAJORS_IN $v0 $v2) (MEMBER_OF $v1 $v2))` **← P1 (planted)** |
| 3 | 0.998 | 56 | `(, (ADVISED_BY $v0 $v1) (ENROLLED_IN $v0 $v2) (TEACHES $v1 $v2))` **← P2 (planted)** |
| 4 | 0.996 | 66 | `(, (ENROLLED_IN $v0 $v1) (MAJORS_IN $v0 $v2) (OFFERED_BY $v1 $v2))` |
| 5 | 0.992 | 19 | `(, (FRIENDS_WITH $v0 $v1) (USES $v0 $v2) (USES $v1 $v2))` |
| 6 | 0.992 | 2802 | `(, (MAJORS_IN $v0 $v1) (MAJORS_IN $v2 $v1) (MEMBER_OF $v3 $v1))` |
| 7 | 0.992 | 5604 | `(, (MAJORS_IN $v0 $v1) (MAJORS_IN $v2 $v1) (OFFERED_BY $v3 $v1))` |
| 8 | 0.992 | 216 | `(, (MEMBER_OF $v0 $v1) (MEMBER_OF $v2 $v1) (OFFERED_BY $v3 $v1))` |

Rank 4 (`ENROLLED_IN` course `OFFERED_BY` the student's `MAJORS_IN` dept) isn't planted directly. It follows from P1 + P3 combined with P2, so it's a genuine derived regularity.

## 2. Anonymised control: identical structure, no meaningful names

The anonymised graph (`R1..R9`, `e1..eN`) yields the **same 343 patterns with the same scores and supports**, under renamed relations. The miner is name-blind by construction; only an LLM could behave differently on the two versions. That's the ablation used in Step 6.

## 3. Limitation of upstream's scorers (no-signal control)

With `strength 0` (no planted dependency), `isurp` **still** ranks P1 and P2 at #2 and #3 (scores ≈ 0.997), and many unrelated patterns share scores ≈ 0.992. Upstream's `jsd` mode didn't separate the planted patterns from chance either (P2 scores 0.83 with and without the signal).

So on this data, upstream's surprisingness scores are **saturated**: high for most 3-clause join patterns regardless of the planted signal. Fixing the scorers is outside this project's scope (and outside the LLM's role), but it shapes the evaluation:

* **Primary target:** reproduce the *exhaustive miner's own* top-K by `isurp` with fewer support evaluations, i.e. be faithful to the miner, whatever its scorer says. Ties at the K-th score are counted as hits (tie-aware recall).
* **Secondary target:** recall of the three planted patterns on the strength-0.8 graph, where they're the miner's top 3.
