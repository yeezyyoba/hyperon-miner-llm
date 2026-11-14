# ADR 0002 — Generate → select → verify, reusing upstream functions

**Status:** accepted

**Context.** Upstream's `expand_conjunction` generates a candidate and immediately counts its
support (`checker`). There's no point at which "which candidates should we count?" can be
asked.

**Decision.** A new module, `guided-conjunction-expansion.metta`, splits each level into:
GENERATE (upstream's `alpha_convert` + `expand_conjunction_connect`, no counting), SELECT
(`py-call` to `minerllm_bridge.select`) and VERIFY (upstream's `sup-num` + minsup + upstream's
redundancy filter). The upstream submodule isn't modified. Inputs are copied
(`sread (repr x)`) before linking, because shared variables leaked across nondeterministic
branches without that (found when the full-budget output differed from upstream by one pattern).

**Consequences.** One integration point, in MeTTa, in upstream's style. With strategy
`exhaustive` and budget 1.0 the output equals upstream's (tested on 3 datasets and at 4
conjuncts), which proves the split didn't change the semantics.
