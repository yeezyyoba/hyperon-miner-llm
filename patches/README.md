# Upstream patches

Fixes for `iCog-Labs-Dev/hyperon-miner` (petta-main @ 7461878) that this repo works
around locally. They are kept as patches so they can be opened as PRs upstream
without changing the pinned submodule.

| Patch | Fixes | Issue |
|---|---|---|
| `0002-fix-add-atom-nodup-alpha-equivalence.patch` | `add-atom-nodup` compares with `=alpha` instead of unifying, so different patterns with equal scores are no longer dropped. | [Issue 7](../docs/01-problem.md) |
| `0001-fix-run-miner-entrypoint-and-pin-petta.patch` | `run_miner.metta`: imports the generic miner and the modules it needs, and passes all 9 arguments (76 patterns at minsup 3 after the patch, none before). `setup.sh`: pins PeTTa instead of tracking HEAD. | [Issue 1, Issue 2](../docs/01-problem.md) |

Check a patch still applies:

```bash
git -C external/hyperon-miner apply --check ../../patches/0001-fix-run-miner-entrypoint-and-pin-petta.patch
```
