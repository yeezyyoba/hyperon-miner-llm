# ADR 0007 — Separate search from scoring; never score through add-atom-nodup

**Status:** accepted · **Context:** [Issue 7](../01-problem.md#issue-7--scoring-silently-drops-about-half-of-the-patterns)

**Context.** Upstream stores every surprisingness score with `add-atom-nodup`, whose
duplicate check unifies. Two different patterns with equal scores collide, and one is
silently dropped. On the university graph the full run scores 343 of 641 frequent patterns,
and *which* ones survive depends on run size. A budgeted run (fewer patterns, fewer
collisions) keeps patterns that the full run loses. So "patterns with a score" isn't a
stable basis for an evaluation, and the bug makes larger runs look worse.

**Decision.**
1. The **guided miner** calls upstream's `isurp` / `isurp-old` directly and stores results
   with a plain `add-atom`. Its candidates are already deduplicated by canonical form,
   so nothing is lost: 641/641 scored, every value identical to upstream's.
2. The **evaluation reference** (`minerllm/reference.py`) is (a) the exhaustive frequent
   set, which equals upstream's frequent output, plus (b) every pattern scored with
   upstream's own `call-surprisingness`, **each in its own fresh space**.
3. A **consistency check** runs on every evaluation run: each score it printed must equal
   the reference score (3,443 / 3,443 in the baseline runs).
4. A characterisation test pins the upstream behaviour, and `patches/0002` fixes it
   upstream (`=alpha` instead of unification).

**Consequences.** Recall is measured against a complete, deterministic ranking of all
frequent patterns, computed by upstream's own scorer. What the LLM influences (which
candidates are verified) is evaluated separately from what it must never influence (the
scores).
