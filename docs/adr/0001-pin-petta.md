# ADR 0001 — Pin PeTTa; never track HEAD

**Status:** accepted · **Context:** [Issue 2](../01-problem.md#issue-2--ci-depends-on-petta-head)

**Context.** Upstream `setup.sh` checks out PeTTa's latest commit. Running upstream's own test
whitelist: 8/8 pass on PeTTa `9e5929a` (2026-09-27), 3/8 on HEAD `ee5cacb` (2026-10-28).
Results that depend on the day of installation can't be evaluated.

**Decision.** `setup.sh` checks out `PETTA_COMMIT` (default `9e5929a…`, the last PeTTa commit
on or before the miner's last petta-main commit). It's overridable through the environment.
CI caches it. A patch for upstream is in `patches/`.

**Consequences.** Reproducible runs and green CI. Moving PeTTa forward is now a deliberate
change (bump the pin, rerun `make test-all`) instead of an accident.
