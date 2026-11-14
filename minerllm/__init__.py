"""minerllm — LLM-guided candidate ranking for the Hyperon (PeTTa) Pattern Miner.

Package map:
    sexpr      parse / print MeTTa S-expressions
    patterns   canonical form for conjunctive patterns (clause order + variable names)
    oracle     independent Python support counter (verifies the MeTTa miner)
    datasets   load .metta datasets, Galaxy subsets, relation statistics
    datagen    synthetic graphs with planted, known-surprising patterns
    petta      run MeTTa scripts on the pinned PeTTa and parse their results
    config     miner configuration + script rendering
"""

__version__ = "0.1.0"
