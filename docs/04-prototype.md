# Step 4 — Prototype

> *Implement a small prototype of the LLM integration based on the designed architecture.*

## Run it

```bash
./setup.sh                                        # pinned PeTTa + Python deps (once)

# offline, no keys: mock LLM
bash .petta/run.sh run_guided.metta               # plain MeTTa entry point
python -m minerllm guided --providers mock        # + oracle check + summary

# live demo for the presentation (problem → equivalence → LLM → failure path → results)
make demo

# real LLMs: put keys in .env (see .env.example)
python -m minerllm guided --config configs/university.yaml --strategy llm --budget 0.3
python -m minerllm guided --config configs/galaxy400.yaml  --strategy llm --budget 0.3

# baselines, same interface
python -m minerllm guided --strategy cardinality --budget 0.3
python -m minerllm guided --strategy heuristic --budget 0.3
python -m minerllm guided --strategy random    --budget 0.3 --seed 2
python -m minerllm guided --strategy exhaustive --budget 1.0      # == upstream output
python -m minerllm mine   --config configs/university.yaml        # unmodified upstream
```

Example output (mock LLM, so the ranking quality is meaningless; this shows the plumbing):

```
0.996  sup=66     (, (ENROLLED_IN $v0 $v1) (MAJORS_IN $v0 $v2) (OFFERED_BY $v1 $v2))
...
87 patterns in 8.2s | strategy=llm budget=30% | candidates generated=13222 unique=7563
verified=2270 | LLM 0.0s, 2657+1030 tokens, 0/3 batches fell back | supports vs oracle: ok
```

Each run writes into `runs/<timestamp>-<config hash>/`:

| File | Content |
|---|---|
| `<label>.metta` | the exact script PeTTa ran |
| `<label>.run.json` | ranker config (strategy, budget, providers, …) |
| `<label>.trace.jsonl` | execution log: per level generated / unique / selected / kept, every LLM batch with provider, model, tokens, latency, validation issues, fallback reason, top joins |
| `<label>.json` | mined patterns with support + surprisingness, timings, oracle verification |
| `<label>.stdout.txt` | raw PeTTa output |

## What is in the prototype

| Part | File | Size |
|---|---|---|
| guided conjunction expansion (MeTTa) | `experiments/llm-guided-miner/guided-conjunction-expansion.metta` | ~120 lines (half of them comments) |
| py-call shim | `experiments/llm-guided-miner/minerllm_bridge.py` | 15 lines |
| bridge (dedupe → rank → budget → trace) | `minerllm/bridge.py` | |
| rankers + validator + prompts | `minerllm/rankers.py` | |
| LLM chain, providers, cache, mock | `minerllm/llm/` | no vendor SDKs |
| harness + oracle | `minerllm/harness.py`, `minerllm/oracle.py` | |

## How it is tested

| Property | Test |
|---|---|
| exhaustive @ 100 % equals upstream (MeTTa, live assertions) | `experiments/llm-guided-miner/tests/test-guided-equivalence.metta` |
| budget output meets minsup (MeTTa) | `experiments/llm-guided-miner/tests/test-guided-budget.metta` |
| equals upstream; subset at any budget; LLM garbage → next provider; total outage completes; works with `isurp` | `tests/test_guided_petta.py` (real PeTTa) |
| upstream's `add-atom-nodup` collision (Issue 7) | `experiments/upstream-regression/tests/test-upstream-nodup.metta` |
| evaluation metrics: tie-aware top-K, seed averaging, verdict rules | `tests/test_evaluate.py` |
| validator, every mock fault mode, chain order/retries/cache, join extraction, prompts contain no data atoms | `tests/test_rankers.py`, `tests/test_llm_chain.py`, `tests/test_bridge.py` |

Verified equivalence with upstream (exhaustive, budget 100 %):

| Data | conjuncts | upstream | guided | identical patterns + supports |
|---|---:|---:|---:|---|
| sample (`ugly_man_sodaDrinker`) | 3 | 3.4 s | 1.5 s | ✅ 16 = 16 |
| Galaxy-200 | 3 | 5.0 s | 2.7 s | ✅ 46 = 46 |
| university (synthetic) | 3 | 65.4 s | 19.0 s | ✅ 641 = 641 |
| Galaxy-200 | **4** | 90.2 s | 14.1 s | ✅ 137 = 137 |

The speed-up in this table has **nothing to do with the LLM** (see ADR 0005). It's the
baseline every ranker is compared against in Step 5.

→ Continued in [Step 5 — Baseline](05-baseline.md).
