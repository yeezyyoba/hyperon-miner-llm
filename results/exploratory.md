# Exploratory follow-up (generated)

### Held-out datasets (the test)

Recall@10 at 30 % budget (planted patterns found in brackets; ± = sd over seeds/repeats):

| method | heldout-university-s1 | heldout-university-s2 | heldout-galaxy400-s11 |
|---|---:|---:|---:|
| cardinality | 73 % (0/3) | 73 % (0/3) | 20 % |
| heuristic | 0 % (0/3) | 0 % (0/3) | 0 % |
| random | 20 % ± 11 (0.8/3) | 11 % ± 9 (0.2/3) | 16 % ± 10 |
| llm:groq | 73 % (0/3) | 73 % (0/3) | 20 % |
| llm:nvidia | 73 % (0/3) | 73 % (0/3) | 20 % |
| llm-hybrid:groq | 73 % (0/3) | 73 % (0/3) | 20 % |
| llm-hybrid:nvidia | 73 % (0/3) | 73 % (0/3) | 20 % |

### Development datasets (design only; not evidence)

Recall@10 at 30 % budget (planted patterns found in brackets; ± = sd over seeds/repeats):

| method | university | university-anon | galaxy400 |
|---|---:|---:|---:|
| cardinality | 67 % (0/3) | 67 % (0/3) | 30 % |
| heuristic | 0 % (0/3) | 0 % (0/3) | 0 % |
| random | 28 % ± 10 (1.2/3) | 22 % ± 11 (0.4/3) | 24 % ± 8 |
| llm:groq | 33 % ± 26 (0.2/3) | 31 % ± 32 (1.5/3) | 22 % ± 23 |
| llm:nvidia | 48 % ± 4 (0.0/3) | 8 % (0.0/3) | 42 % ± 43 |
| llm-hybrid:groq | 67 % (0/3) | 67 % (0/3) | 30 % |
| llm-hybrid:nvidia | 67 % (0/3) | 67 % (0/3) | 30 % |
| llm-direct:groq | 67 % (0/3) | 67 % (0/3) | 30 % |

### Checks against the H1 bar (held-out only)

| dataset / method | recall@10 | best baseline | verdict |
|---|---:|---|---|
| heldout-university-s1 / llm-hybrid:groq | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s1 / llm-hybrid:nvidia | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s1 / llm:groq | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s1 / llm:nvidia | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s2 / llm-hybrid:groq | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s2 / llm-hybrid:nvidia | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s2 / llm:groq | 73 % | cardinality 73 % | ties the best baseline |
| heldout-university-s2 / llm:nvidia | 73 % | cardinality 73 % | ties the best baseline |
| heldout-galaxy400-s11 / llm-hybrid:groq | 20 % | cardinality 20 % | ties the best baseline |
| heldout-galaxy400-s11 / llm-hybrid:nvidia | 20 % | cardinality 20 % | ties the best baseline |
| heldout-galaxy400-s11 / llm:groq | 20 % | cardinality 20 % | ties the best baseline |
| heldout-galaxy400-s11 / llm:nvidia | 20 % | cardinality 20 % | ties the best baseline |

