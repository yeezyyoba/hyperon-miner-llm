# Datasets

| File | Atoms | Source | Regenerate |
|---|---:|---|---|
| `university_s0_st80.metta` | 504 | synthetic, 3 planted patterns at strength 0.8 | `minerllm datagen --seed 0 --strength 0.8` |
| `university_s0_st80_anon.metta` | 504 | same graph, names replaced by `R1..R9` / `e1..eN` | `minerllm datagen --seed 0 --strength 0.8 --anonymize` |
| `university_s0_st0.metta` | 504 | same generator, **no** planted signal (control) | `minerllm datagen --seed 0 --strength 0.0` |
| `galaxy_400.metta` | 400 | deterministic sample of upstream `galaxy_data_full.metta` | `minerllm galaxy 400` |

Each synthetic file has a `*.truth.json` with the generator spec and the planted
patterns (renamed accordingly in the anonymised version).

Upstream's datasets are used in place from `external/hyperon-miner/experiments/data/`.
Validation of the synthetic data: [docs/evidence/synthetic-validation.md](../../docs/evidence/synthetic-validation.md).
