# Results (generated)

### university

Exhaustive @ 100 %: 641 patterns, 13053 candidates verified, 31.4 s; upstream miner (same config): 97.9 s, 343 patterns scored.

| method | budget | recall@10 | recall@25 | planted | verified | time (s) | LLM (s) | tokens in/out | LLM fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cardinality | 10 % | 50 % | 41 % | 0.0/3 | 582 | 6.9 | 0.0 | – | – |
| heuristic | 10 % | 0 % | 0 % | 0.0/3 | 111 | 1.7 | 0.0 | – | – |
| llm:groq | 10 % | 33 % | 21 % | 0.0/3 | 713 | 15.3 | 9.4 | 4282 / 6250 | 0/3 |
| llm:nvidia | 10 % | 8 % | 7 % | 0.0/3 | 658 | 44.4 | 39.0 | 4659 / 1551 | 0/3 |
| random | 10 % | 0 % ± 0 | 3 % | 0.0/3 | 245 | 2.8 | 0.0 | – | – |
| cardinality | 20 % | 58 % | 66 % | 0.0/3 | 1548 | 11.8 | 0.0 | – | – |
| heuristic | 20 % | 0 % | 0 % | 0.0/3 | 222 | 1.9 | 0.0 | – | – |
| llm:groq | 20 % | 67 % | 41 % | 1.0/3 | 1995 | 11.7 | 0.0 | 4282 / 6250 | 0/3 |
| llm:nvidia | 20 % | 25 % | 41 % | 0.0/3 | 2201 | 12.9 | 0.0 | 4659 / 1551 | 0/3 |
| random | 20 % | 7 % ± 8 | 8 % | 0.2/3 | 823 | 4.7 | 0.0 | – | – |
| cardinality | 30 % | 67 % | 76 % | 0.0/3 | 3037 | 19.6 | 0.0 | – | – |
| heuristic | 30 % | 0 % | 0 % | 0.0/3 | 782 | 2.4 | 0.0 | – | – |
| llm-direct:groq | 30 % | 67 % | 76 % | 0.0/3 | 2754 | 238.5 | 223.0 | 6346 / 6726 | 151/154 |
| llm:groq | 30 % | 33 % ± 26 | 30 % | 0.2/3 | 3246 | 31.0 | 16.9 | 4282 / 4602 | 0/3 |
| llm:nvidia | 30 % | 48 % ± 4 | 44 % | 0.0/3 | 3309 | 58.4 | 42.8 | 4659 / 1551 | 0/3 |
| random | 30 % | 28 % ± 10 | 23 % | 1.2/3 | 1525 | 7.0 | 0.0 | – | – |
| cardinality | 50 % | 100 % | 100 % | 3.0/3 | 6527 | 31.9 | 0.0 | – | – |
| heuristic | 50 % | 0 % | 0 % | 0.0/3 | 2956 | 7.4 | 0.0 | – | – |
| llm:groq | 50 % | 100 % | 90 % | 3.0/3 | 6378 | 23.8 | 0.0 | 4282 / 6250 | 0/3 |
| llm:nvidia | 50 % | 83 % | 83 % | 3.0/3 | 6288 | 23.3 | 0.0 | 4659 / 1551 | 0/3 |
| random | 50 % | 43 % ± 14 | 39 % | 1.4/3 | 3793 | 12.8 | 0.0 | – | – |

### university-anon

Exhaustive @ 100 %: 641 patterns, 13053 candidates verified, 31.1 s; upstream miner (same config): 100.6 s, 343 patterns scored.

| method | budget | recall@10 | recall@25 | planted | verified | time (s) | LLM (s) | tokens in/out | LLM fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cardinality | 10 % | 50 % | 41 % | 0.0/3 | 582 | 7.3 | 0.0 | – | – |
| heuristic | 10 % | 0 % | 0 % | 0.0/3 | 111 | 1.9 | 0.0 | – | – |
| llm:groq | 10 % | 42 % | 34 % | 1.0/3 | 974 | 14.1 | 3.9 | 3954 / 7431 | 0/3 |
| llm:nvidia | 10 % | 0 % | 0 % | 0.0/3 | 551 | 100.7 | 95.5 | 4167 / 1551 | 0/3 |
| random | 10 % | 7 % ± 10 | 4 % | 0.2/3 | 255 | 2.7 | 0.0 | – | – |
| cardinality | 20 % | 58 % | 66 % | 0.0/3 | 1615 | 12.9 | 0.0 | – | – |
| heuristic | 20 % | 0 % | 0 % | 0.0/3 | 222 | 2.0 | 0.0 | – | – |
| llm:groq | 20 % | 42 % | 41 % | 1.0/3 | 1978 | 12.1 | 0.0 | 3954 / 7431 | 0/3 |
| llm:nvidia | 20 % | 8 % | 14 % | 0.0/3 | 2254 | 14.5 | 0.0 | 4167 / 1551 | 0/3 |
| random | 20 % | 18 % ± 17 | 13 % | 0.2/3 | 847 | 4.9 | 0.0 | – | – |
| cardinality | 30 % | 67 % | 76 % | 0.0/3 | 3037 | 20.9 | 0.0 | – | – |
| heuristic | 30 % | 0 % | 0 % | 0.0/3 | 333 | 2.0 | 0.0 | – | – |
| llm-direct:groq | 30 % | 67 % | 76 % | 0.0/3 | 3037 | 291.3 | 274.8 | 6045 / 6694 | 167/170 |
| llm:groq | 30 % | 31 % ± 32 | 41 % | 1.5/3 | 2970 | 31.7 | 18.8 | 3954 / 4097 | 0/3 |
| llm:nvidia | 30 % | 8 % ± 0 | 12 % | 0.0/3 | 3195 | 57.8 | 43.1 | 4167 / 1551 | 0/3 |
| random | 30 % | 22 % ± 11 | 23 % | 0.4/3 | 1703 | 7.8 | 0.0 | – | – |
| cardinality | 50 % | 100 % | 100 % | 3.0/3 | 6527 | 31.7 | 0.0 | – | – |
| heuristic | 50 % | 0 % | 0 % | 0.0/3 | 2956 | 7.4 | 0.0 | – | – |
| llm:groq | 50 % | 83 % | 93 % | 3.0/3 | 5662 | 19.2 | 0.0 | 3954 / 7431 | 0/3 |
| llm:nvidia | 50 % | 8 % | 14 % | 0.0/3 | 5861 | 20.4 | 0.0 | 4167 / 1551 | 0/3 |
| random | 50 % | 43 % ± 22 | 41 % | 1.4/3 | 3990 | 13.6 | 0.0 | – | – |

### galaxy400

Exhaustive @ 100 %: 115 patterns, 4267 candidates verified, 9.2 s; upstream miner (same config): 17.4 s, 109 patterns scored.

| method | budget | recall@10 | recall@25 | planted | verified | time (s) | LLM (s) | tokens in/out | LLM fallbacks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cardinality | 10 % | 10 % | 16 % | – | 204 | 4.4 | 0.0 | – | – |
| heuristic | 10 % | 0 % | 0 % | – | 75 | 2.9 | 0.0 | – | – |
| llm:groq | 10 % | 0 % | 8 % | – | 197 | 9.6 | 6.5 | 3806 / 3756 | 0/3 |
| llm:nvidia | 10 % | 40 % | 24 % | – | 231 | 48.7 | 45.5 | 4241 / 1236 | 0/3 |
| random | 10 % | 2 % ± 4 | 2 % | – | 123 | 3.0 | 0.0 | – | – |
| cardinality | 20 % | 30 % | 24 % | – | 638 | 5.7 | 0.0 | – | – |
| heuristic | 20 % | 0 % | 0 % | – | 150 | 3.1 | 0.0 | – | – |
| llm:groq | 20 % | 20 % | 32 % | – | 605 | 4.5 | 0.0 | 3806 / 3756 | 0/3 |
| llm:nvidia | 20 % | 80 % | 60 % | – | 622 | 4.1 | 0.0 | 4241 / 1236 | 0/3 |
| random | 20 % | 16 % ± 8 | 12 % | – | 325 | 3.5 | 0.0 | – | – |
| cardinality | 30 % | 30 % | 36 % | – | 1106 | 6.5 | 0.0 | – | – |
| heuristic | 30 % | 0 % | 0 % | – | 225 | 2.4 | 0.0 | – | – |
| llm-direct:groq | 30 % | 30 % | 32 % | – | 1057 | 77.1 | 71.9 | 1695 / 2913 | 59/60 |
| llm:groq | 30 % | 22 % ± 23 | 27 % | – | 865 | 159.9 | 155.1 | 3432 / 2532 | 0/3 |
| llm:nvidia | 30 % | 42 % ± 43 | 35 % | – | 1045 | 34.1 | 29.4 | 4241 / 1236 | 0/3 |
| random | 30 % | 24 % ± 8 | 21 % | – | 576 | 3.7 | 0.0 | – | – |
| cardinality | 50 % | 70 % | 72 % | – | 2092 | 7.9 | 0.0 | – | – |
| heuristic | 50 % | 10 % | 8 % | – | 552 | 3.1 | 0.0 | – | – |
| llm:groq | 50 % | 100 % | 96 % | – | 2134 | 6.3 | 0.0 | 3806 / 3756 | 0/3 |
| llm:nvidia | 50 % | 100 % | 88 % | – | 2095 | 6.5 | 0.0 | 4241 / 1236 | 0/3 |
| random | 50 % | 36 % ± 10 | 38 % | – | 1301 | 4.8 | 0.0 | – | – |

**H1** (budget 30 %, recall@10):

| dataset / ranker | LLM | cardinality | structural | random (mean) | verdict |
|---|---:|---:|---:|---:|---|
| university / llm:groq | 33 % | 67 % | 0 % | 28 % | rejected: below 90 % |
| university / llm:nvidia | 48 % | 67 % | 0 % | 28 % | rejected: below 90 % |
| university-anon / llm:groq | 31 % | 67 % | 0 % | 22 % | rejected: below 90 % |
| university-anon / llm:nvidia | 8 % | 67 % | 0 % | 22 % | rejected: below 90 % |
| galaxy400 / llm:groq | 22 % | 30 % | 0 % | 24 % | rejected: below 90 % |
| galaxy400 / llm:nvidia | 42 % | 30 % | 0 % | 24 % | rejected: below 90 % |

**H2** (LLM − best cheap baseline, recall@10, budget 30 %):

| ranker | named | anonymised | verdict |
|---|---:|---:|---|
| llm:groq | -33 pts | -35 pts | not supported |
| llm:nvidia | -19 pts | -58 pts | not supported |
