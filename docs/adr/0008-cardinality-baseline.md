# ADR 0008 — Add a cardinality baseline; LLM ties fall back to it

**Status:** accepted (amendment recorded in [Step 2](../02-hypothesis.md#amendment-phase-4-2026-11-16-before-the-llm-evaluation-runs))

**Context.** The first baseline runs showed the structural heuristic finds 0 patterns at
10–30 % budget: it prefers rare multi-relation joins that miss minsup, so the next level
has nothing to extend. An LLM that beats a degenerate baseline proves nothing, and the
LLM ranker used the same heuristic as its fallback.

**Decision.** Add `cardinality`: the textbook independence estimate of a candidate's
support (relation sizes, distinct values per argument), computed from exactly the schema
statistics the LLM is shown. Verify the most-likely-frequent candidates first. Use it as:
* a baseline arm in the evaluation (H1 must beat the best of random / structural /
  cardinality; H2 measures the gap over cardinality);
* the tie-breaker for LLM scores (many candidates share a mean join score);
* the fallback when an LLM batch fails or the ranker errors.

**Consequences.** A much stronger reference point: 67 % recall@10 at 30 % budget on the
university graph, against 28 % for random and 0 % for the structural heuristic. The LLM is
measured as *what it adds on top of* the best cheap signal. A principled limit is visible
too: a surprising pattern is by definition one whose real support exceeds the independence
estimate, so cardinality ranks exactly those patterns low (0/3 planted patterns at 30 %).
