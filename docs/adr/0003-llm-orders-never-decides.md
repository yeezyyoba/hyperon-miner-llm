# ADR 0003 — The LLM orders candidates; symbolic code decides what is true

**Status:** accepted

**Context.** The assignment requires *verifiable symbolic behaviour*. LLMs hallucinate. An
LLM that proposes patterns or estimates supports would put unverifiable claims in the
output.

**Decision.** The LLM returns only 0–10 scores for items it was given. Those scores only
determine the *order* in which candidates are verified. Supports, minsup, redundancy and
surprisingness are computed by the upstream MeTTa code, and every support is re-counted by
an independent Python oracle.

**Consequences.** Precision is 100 % at any budget, and the output is a subset of the
exhaustive output (tested). The LLM's influence is bounded to *recall*, which is exactly
what the evaluation measures. A wrong LLM costs time or recall, never correctness.
