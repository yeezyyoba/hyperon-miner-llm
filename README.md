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

> 🚧 Work in progress (phase 3 of 5). Real-LLM results arrive in phase 4.

## How the LLM is integrated, in one picture

```
             upstream miner (unmodified, MeTTa)          our module (MeTTa)            Python
 frequent clauses ──► GENERATE linked candidates ──► SELECT ──py-call──► dedupe → rank → top budget %
                       (no support counted)            │                     │
                                                       │            LLM scores schema JOINS
                                                       ▼            (Groq → NVIDIA → Gemini,
                                     VERIFY: MeTTa counts support,    validated, cached;
                                     minsup + redundancy filter        heuristic on failure)
                                                       │
                                     score with upstream isurp ──► output ──► oracle re-counts every support
```

The LLM only changes **which candidates are verified first**. It can't add a pattern,
change a support, or stop the run. At any budget the output is a subset of the full
miner's output (precision is 100 %), and at budget 100 % it **equals** the upstream output.

## The six steps

| Step | Document | Status |
|---|---|---|
| 1. Problem | [docs/01-problem.md](docs/01-problem.md) | ✅ six issues, with evidence |
| 2. Hypothesis | [docs/02-hypothesis.md](docs/02-hypothesis.md) | ✅ H1 + H2, rejection criteria fixed in advance |
| 3. Architecture | [docs/03-architecture.md](docs/03-architecture.md) · [ADRs](docs/adr/) | ✅ components, flows, boundary, validator, failure path |
| 4. Prototype | [docs/04-prototype.md](docs/04-prototype.md) · `experiments/llm-guided-miner/` · `minerllm/` | ✅ equals upstream at 100 %; tested failure paths |
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
| 7 | Scoring silently drops ~half the patterns | 641 frequent patterns in, 343 scored out: `add-atom-nodup` unifies instead of comparing |
| **6** | **Conjunction expansion explodes** | 2→3 conjuncts costs **3×** time at 200 atoms, **10×** at 800; 4 conjuncts on 200 atoms takes 90 s |

## Quick start

Requirements: SWI-Prolog ≥ 9.1.22 **with janus** (the Python bridge), Python ≥ 3.9, git.
The Python used for the venv must be the **same minor version** as janus's Python
(`make doctor` checks this).

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

# the LLM-guided miner
cp .env.example .env                                  # add GEMINI / GROQ / NVIDIA keys
python -m minerllm guided --strategy llm --budget 0.3  # real LLMs
python -m minerllm guided --providers mock             # offline, no keys
bash .petta/run.sh run_guided.metta                    # plain MeTTa entry point (mock)
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

### macOS (Homebrew) note

Homebrew's SWI-Prolog links janus against Apple's Python 3.9 framework, but looks for it
inside Xcode. If `make doctor` reports `Library not loaded: @rpath/Python3.framework/…`:

```bash
J=$(find "$(brew --prefix swi-prolog)/" -name janus.so | head -1)
chmod +w "$J"
install_name_tool -add_rpath /Library/Developer/CommandLineTools/Library/Frameworks "$J"
chmod -w "$J"
codesign -f -s - "$J"
/usr/bin/python3 -m venv .venv && source .venv/bin/activate   # Apple's 3.9, matching janus
```

## Repository layout

```
external/hyperon-miner/        iCog's miner, git submodule pinned to petta-main @ 7461878
run_miner.metta                working entry point for the upstream miner (Issue 1 fix)
run_guided.metta               entry point for the LLM-guided miner (offline mock config)
setup.sh                       pinned PeTTa + dependency checks (Issue 2 fix)
configs/                       YAML miner configurations (dataset, minsup, depth, scorer)
minerllm/                      Python package
  sexpr.py, patterns.py        MeTTa parsing + canonical pattern form (Issue 4)
  oracle.py                    independent support counter
  petta.py, harness.py         run PeTTa from a config, verify, save artefacts
  datagen.py, datasets.py      synthetic graphs with planted patterns, Galaxy subsets
  bridge.py                    py-call API used by MeTTa: dedupe → rank → budget → trace
  rankers.py                   exhaustive · random · heuristic · llm (joins) · llm-direct + validator
  llm/                         Groq → NVIDIA → Gemini chain, retries, disk cache, offline mock
  cli.py                       `python -m minerllm mine | guided | datagen | galaxy | support | stats`
experiments/
  data/                        evaluation datasets (+ planted-pattern answer keys)
  llm-guided-miner/            guided conjunction expansion (MeTTa) + py-call shim + tests
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
