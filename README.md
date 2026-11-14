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
| 4. Prototype | `minerllm/` (harness, oracle, data) · `experiments/llm-guided-miner/` | 🟡 harness + oracle done, guided miner in phase 3 |
| 5. Baseline | docs/05-baseline.md | ⏳ phase 4 |
| 6. Results | docs/06-results.md | ⏳ phase 4 |

### Step 1 in one table

| # | Issue found in upstream (petta-main @ `7461878`) | Evidence |
|---|---|---|
| 1 | Documented entry point does not run | returns `(partial pattern-miner …)`: 8 args passed to a 9-arg function |
| 2 | CI tracks PeTTa HEAD | **8/8** tests pass on pinned PeTTa, **3/8** on HEAD |
| 3 | End-to-end tests never run their assertions | corrupting an expected value still passes CI |
| 4 | Output full of clause-order duplicates | 801 printed vs 137 distinct patterns at 4 conjuncts (83 %) |
| 5 | Global spaces leak state between runs | 2nd run returns 32 patterns instead of 20 |
| **6** | **Conjunction expansion explodes** | 2→3 conjuncts costs **3×** time at 200 atoms, **10×** at 800; 4 conjuncts on 200 atoms takes 90 s |

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
make datasets            # regenerate experiments/data (deterministic)
make mine CONFIG=configs/university.yaml   # mine + verify every support with the oracle
```

## How we know the symbolic side is right

The LLM integration is only trustworthy if the miner's own answers are. So the
harness never takes a printed support on faith. `minerllm/oracle.py` is an
**independent Python re-implementation** of upstream's support definition (no MeTTa
involved), and every run is cross-checked against it:

* it reproduces all 7 expected supports from upstream's own test file (10 … 12000),
* across the full baseline profile, **1,163 distinct mined patterns, 0 mismatches**.

Synthetic graphs with **planted** patterns (`minerllm datagen`) give an answer key:
upstream's `isurp` ranks the three planted patterns **#1, #2, #3 of 343**
([evidence](docs/evidence/synthetic-validation.md)).

## Repository layout

```
external/hyperon-miner/        iCog's miner, git submodule pinned to petta-main @ 7461878
run_miner.metta                working entry point for the upstream miner (Issue 1 fix)
setup.sh                       pinned PeTTa + dependency checks (Issue 2 fix)
configs/                       YAML miner configurations (dataset, minsup, depth, scorer)
minerllm/                      Python package
  sexpr.py, patterns.py        MeTTa parsing + canonical pattern form (Issue 4)
  oracle.py                    independent support counter
  petta.py, harness.py         run PeTTa from a config, verify, save artefacts
  datagen.py, datasets.py      synthetic graphs with planted patterns, Galaxy subsets
  cli.py                       `python -m minerllm mine | datagen | galaxy | support | stats`
experiments/
  data/                        evaluation datasets (+ planted-pattern answer keys)
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
