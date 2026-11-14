;; =============================================================================
;; Guided miner under a budget: heuristic ranker, 30 % of candidates verified.
;; Soundness: fewer patterns may come out, but every one of them still has its
;; support counted in MeTTa and meets minsup. A budget can cost recall,
;; never precision. (On this single-relation toy set the schema heuristic finds
;; nothing at 30 %; tests/test_guided_petta.py measures recall on real data.)
;; =============================================================================
;; --- upstream modules ---
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/boost_petta.py)
!(import! &self ../../../external/hyperon-miner/experiments/utils/common-utils)
!(import! &self ../../../external/hyperon-miner/experiments/utils/index_to_var)
!(import! &self ../../../external/hyperon-miner/experiments/utils/constants)
!(import! &self ../../../external/hyperon-miner/experiments/utils/TruthValue)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/partition-metta)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/binomialMetta)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/beta-dist)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/surp-utils)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/IIsurp_utils)
!(import! &self ../../../external/hyperon-miner/experiments/utils/sort)
!(import! &self ../../../external/hyperon-miner/experiments/utils/variable-combinations)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/blk-abstractness)
!(import! &self ../../../external/hyperon-miner/experiments/utils/remove_useless_clauses)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/eq-prob-petta)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/bs-utils)
!(import! &self ../../../external/hyperon-miner/experiments/utils/surp-utils/jsd-helper)
!(import! &self ../../../external/hyperon-miner/experiments/truth-values/est-tv)
!(import! &self ../../../external/hyperon-miner/experiments/truth-values/emp-tv)
!(import! &self ../../../external/hyperon-miner/experiments/surprisingness/emp-prob)
!(import! &self ../../../external/hyperon-miner/experiments/surprisingness/isurp)
!(import! &self ../../../external/hyperon-miner/experiments/surprisingness/isurp-old)
!(import! &self ../../../external/hyperon-miner/experiments/surprisingness/jsd)
!(import! &self ../../../external/hyperon-miner/experiments/surprisingness/IIsurp-old)
!(import! &self ../../../external/hyperon-miner/experiments/frequent-pattern-miner/valuation)
!(import! &self ../../../external/hyperon-miner/experiments/frequent-pattern-miner/shallow-abstractions)
!(import! &self ../../../external/hyperon-miner/experiments/frequent-pattern-miner/specialization)
!(import! &self ../../../external/hyperon-miner/experiments/frequent-pattern-miner/candidate)
!(import! &self ../../../external/hyperon-miner/experiments/frequent-pattern-miner/conjunction-expansion)
!(import! &self ../../../external/hyperon-miner/experiments/frequent-pattern-miner/frequent-pattern-miner-generic)
!(import! &self ../../../external/hyperon-miner/experiments/pattern-miner/pattern-miner)
;; --- guided miner + Python bridge (paths relative to this file) ---
!(import! &self ../minerllm_bridge.py)
!(import! &self ../guided-conjunction-expansion)

!(import! &db ../../../external/hyperon-miner/experiments/data/ugly_man_sodaDrinker)
!(bind! &res (new-space))

!(guided-pattern-miner &res &db $x 10 1 none none none "heuristic30.run.json")
;; at most the 16 patterns of the full run (the Python integration tests check
;; the stronger property: output is a subset of the exhaustive output)
!(test (<= (size-atom (collapse (get-atoms &res))) 16) True)
!(test (collapse (match &res (supportOf $p $s) (if (< $s 10) (below-minsup $p) (empty)))) ())
