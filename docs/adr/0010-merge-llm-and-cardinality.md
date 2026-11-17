# ADR 0010 — Merge the LLM join order with cardinality (exploratory)

**Status:** accepted as an exploratory follow-up ([Step 7](../07-exploratory.md)); does not
change the pre-registered H1/H2 verdicts.

**Context.** In Step 6 the LLM join ranker lost to the cardinality baseline at 30 % budget
(university: 33 % / 48 % vs 67 % recall@10). The traces showed it was *not* wasting the
budget on infrequent candidates: it kept more frequent patterns than cardinality at both
levels. It kept *different* ones. Cardinality finds the high-support structural patterns
that dominate the reference top 10; the LLM dismisses same-relation joins but sometimes
finds the planted patterns, which cardinality ranks last because a surprising pattern is
one the independence estimate under-predicts.

**Decision.** Add a strategy, `llm-hybrid`, that interleaves the two orders (cardinality
first, then the LLM's best not yet taken, and so on), so each gets about half of any budget.
Each join's LLM score is the mean of 3 independent ratings, to reduce the run-to-run
variance seen in Step 6. The existing strategies are unchanged.

Rejected: a support gate (drop candidates whose estimate is below a fraction of minsup,
then let the LLM order the rest). The LLM's problem was not infrequent picks, and on Galaxy
2 of the top 10 have estimates below 0.1 × minsup, so a gate would discard them.

**Consequences.**
* Same boundary as ADR 0003: the LLM still only orders candidates, so precision stays at
  100 % by construction.
* If every LLM call fails, the LLM order *is* the cardinality order, so the merge degrades
  to the cardinality baseline (same failure path as ADR 0008).
* 3× the LLM calls of `llm` (9 per dataset instead of 3), still scored once per schema.
* Designed after seeing Step 6, so it is evaluated only on held-out datasets, with the
  protocol committed before any held-out run. Result: with Groq it beat every baseline on all
  three held-out sets (82 / 82 / 70 % vs cardinality 73 / 73 / 20 %), below the 90 % bar;
  with NVIDIA it tied cardinality on the university graphs. One run per arm.
