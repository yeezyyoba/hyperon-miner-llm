# Datasets

| File | Atoms | Source | Regenerate |
|---|---:|---|---|
| `university_s0_st80.metta` | 504 | synthetic, 3 planted patterns at strength 0.8 | `minerllm datagen --seed 0 --strength 0.8` |
| `university_s0_st80_anon.metta` | 504 | same graph, names replaced by `R1..R9` / `e1..eN` | `minerllm datagen --seed 0 --strength 0.8 --anonymize` |
| `university_s0_st0.metta` | 504 | same generator, **no** planted signal (control) | `minerllm datagen --seed 0 --strength 0.0` |
| `galaxy_400.metta` | 400 | deterministic sample of upstream `galaxy_data_full.metta` | `minerllm galaxy 400` |

| `heldout/university_s{1,2}_st80.metta` | 504 | **held-out** (Step 7): fresh graphs, same generator | `minerllm datagen --seed 1 --strength 0.8 --out experiments/data/heldout` |
| `heldout/galaxy_400_s11.metta` | 400 | **held-out** (Step 7): different Galaxy sample | `minerllm galaxy 400 --seed 11 --name galaxy_400_s11 --out experiments/data/heldout` |

Each synthetic file has a `*.truth.json` with the generator spec and the planted
patterns (renamed accordingly in the anonymised version).

Upstream's datasets are used in place from `external/hyperon-miner/experiments/data/`.
Validation of the synthetic data: [docs/evidence/synthetic-validation.md](../../docs/evidence/synthetic-validation.md).
