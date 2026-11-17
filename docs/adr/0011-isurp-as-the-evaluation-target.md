# ADR 0011 — Keep upstream's `isurp` as the evaluation target

**Status:** accepted, recorded retrospectively (17 Nov). The choice was made at the start
of the project without a written comparison; this record states the reasons and the cost.

**Context.** Recall@K needs a reference ranking of the frequent patterns. Upstream offers
several surprisingness modes (training slide 9):

* `isurp`: how far a pattern's empirical probability falls outside the interval
  [emin, emax] of estimates obtained by splitting it into independent parts, normalised to
  0–1 (0 = inside the interval, explained by independence);
* `isurp-old`: a lighter version of the same distance, without subsampled support;
* `jsd`: turns the empirical and estimated probabilities into truth values (strength and
  confidence → Beta distributions), samples their CDFs in 10 bins and returns the
  Jensen–Shannon distance. Uncertainty is built in: small counts give low scores;
* `IIsurp-*`: estimates built from sub-pattern averages.

**Decision.** Use `isurp`, normalised, db-ratio 0.5, for every dataset and every method.

1. It is upstream's full I-Surprisingness and its most tested mode.
2. A single 0–1 distance from the independence interval is easy to explain and to check by
   hand (docs: worked example, score 0.33).
3. The hypothesis is about **which candidates are verified first**, not how patterns are
   scored. Keeping the scorer fixed means only the ranker changes between methods.

`jsd` is not a refinement of `isurp`; it measures something else (surprise weighted by the
amount of evidence). It was not compared.

**Consequences.**
* The results are relative to `isurp`. Its top 10 is **saturated** on our data: of 641
  frequent university patterns, 75 score ≥ 0.9 and the 10th-best score is 0.992, so the top
  10 is decided by small differences among very frequent patterns. This favours the
  cardinality baseline (docs/06, "The target rewards frequency").
* Scoring is separate from search (ADR 0007) and the rankers do not depend on the scorer.
  The reference builder already scores with the config's `surp_mode`, each pattern in its own
  space. But the guided miner calls only `isurp` and `isurp-old` directly; other modes,
  including `jsd`, still go through upstream's dispatcher, which stores scores with
  `add-atom-nodup` and so drops patterns (Issue 7). Evaluating with `jsd` therefore needs a
  direct `jsd` path in `guided-emit` first (a few lines, like the `isurp` branch).
* Expected, not measured: `jsd` would probably keep a bias toward frequent patterns, because
  large counts give high confidence. Re-running the evaluation with `jsd` as the target is
  listed as future work.
