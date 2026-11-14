# hyperon-miner-llm

LLM-guided candidate ranking for the [Hyperon Pattern Miner](https://github.com/iCog-Labs-Dev/hyperon-miner) (PeTTa edition).

> **The LLM decides which candidate patterns to check first.
> The miner still checks everything it keeps.**

This project answers the assignment question:

> *How can a large language model be integrated with Hyperon Miner to improve one clearly
> defined aspect of usability, correctness or performance while preserving verifiable
> symbolic behavior?*

**Aspect chosen: performance**, specifically the conjunction expansion step, where the
number of candidate patterns explodes and which limited the PeTTa miner to 3 conjuncts.

> 🚧 Work in progress. This README grows phase by phase.

## The six steps

| Step | Document | Status |
|---|---|---|
| 1. Problem | [docs/01-problem.md](docs/01-problem.md) | ✅ six issues, with evidence |
| 2. Hypothesis | docs/02-hypothesis.md | ⏳ phase 3 |
| 3. Architecture | docs/03-architecture.md | ⏳ phase 3 |
| 4. Prototype | `experiments/llm-guided-miner/`, `minerllm/` | ⏳ phases 2–3 |
| 5. Baseline | docs/05-baseline.md | ⏳ phase 4 |
| 6. Results | docs/06-results.md | ⏳ phase 4 |

### Step 1 in one table

| # | Issue found in upstream (petta-main @ `7461878`) | Evidence |
|---|---|---|
| 1 | Documented entry point does not run | returns `(partial pattern-miner …)`: 8 args passed to a 9-arg function |
| 2 | CI tracks PeTTa HEAD | **8/8** tests pass on pinned PeTTa, **3/8** on HEAD |
| 3 | End-to-end tests never run their assertions | corrupting an expected value still passes CI |
| 4 | `isurp` silently drops a pattern | 12 frequent patterns in, 11 scored out |
| 5 | Global spaces leak state between runs | 2nd run returns 32 patterns instead of 20 |
| **6** | **Conjunction expansion explodes** | 2→3 conjuncts costs **3×** time at 200 atoms, **10×** at 800; 4 conjuncts on 200 atoms takes 97 s |

## Quick start

Requirements: SWI-Prolog ≥ 9.1.22 **with janus** (the Python bridge), Python ≥ 3.10, git.

```bash
git clone --recurse-submodules https://github.com/yeezyyoba/hyperon-miner-llm.git
cd hyperon-miner-llm
python3 -m venv .venv && source .venv/bin/activate   # recommended (PEP 668)
brew install swi-prolog                              # macOS; Ubuntu: see setup.sh
./setup.sh                                           # pinned PeTTa + Python deps

make run                 # fixed upstream miner on the sample data
make test                # Python tests
make test-metta          # MeTTa tests with live assertions
make reproduce-issues    # regenerate the Step 1 evidence
make profile             # regenerate docs/evidence/baseline-profile.md
```

## Repository layout

```
external/hyperon-miner/        iCog's miner, git submodule pinned to petta-main @ 7461878
run_miner.metta                working entry point for the upstream miner (Issue 1 fix)
setup.sh                       pinned PeTTa + dependency checks (Issue 2 fix)
experiments/
  upstream-regression/tests/   live-assertion tests of the upstream pipeline (Issues 3–5)
scripts/
  run_metta_tests.py           strict MeTTa test runner
  reproduce_issues.sh          evidence for Issues 1–2
  profile_baseline.py          evidence for Issue 6
patches/                       fixes ready to send upstream
docs/                          one document per assignment step
tests/                         pytest suite
```

The layout mirrors upstream on purpose: MeTTa code lives under `experiments/<component>/`
with tests in `experiments/<component>/tests/test-*.metta`.

## License

AGPL-3.0, the same license as the upstream miner.
