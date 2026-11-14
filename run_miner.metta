;; =============================================================================
;; run_miner.metta — a working entry point for the upstream Hyperon miner
;; =============================================================================
;; The upstream starter script (external/hyperon-miner/run_miner.metta) does not
;; run on petta-main @ 7461878 (see docs/01-problem.md, Issue 1):
;;   * it imports frequent-pattern-miner.metta (8-argument signature) while
;;     pattern-miner.metta calls the *generic* 7-argument version, and
;;   * it calls pattern-miner with 8 arguments, but pattern-miner takes 9
;;     (the initial pattern $initpat was added later and the script never caught up).
;;
;; This file fixes both, without editing the submodule.
;; Run:   make run          (or)   bash .petta/run.sh run_miner.metta
;; =============================================================================

;; --- 1. Upstream modules (same order as upstream tests/test-pattern-miner) ---
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/boost_petta.py)
!(import! &self external/hyperon-miner/experiments/utils/common-utils)
!(import! &self external/hyperon-miner/experiments/utils/index_to_var)
!(import! &self external/hyperon-miner/experiments/utils/constants)
!(import! &self external/hyperon-miner/experiments/utils/TruthValue)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/partition-metta)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/binomialMetta)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/beta-dist)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/surp-utils)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/IIsurp_utils)
!(import! &self external/hyperon-miner/experiments/utils/sort)
!(import! &self external/hyperon-miner/experiments/utils/variable-combinations)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/blk-abstractness)
!(import! &self external/hyperon-miner/experiments/utils/remove_useless_clauses)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/eq-prob-petta)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/bs-utils)
!(import! &self external/hyperon-miner/experiments/utils/surp-utils/jsd-helper)
!(import! &self external/hyperon-miner/experiments/truth-values/est-tv)
!(import! &self external/hyperon-miner/experiments/truth-values/emp-tv)
!(import! &self external/hyperon-miner/experiments/surprisingness/emp-prob)
!(import! &self external/hyperon-miner/experiments/surprisingness/isurp)
!(import! &self external/hyperon-miner/experiments/surprisingness/isurp-old)
!(import! &self external/hyperon-miner/experiments/surprisingness/jsd)
!(import! &self external/hyperon-miner/experiments/surprisingness/IIsurp-old)
!(import! &self external/hyperon-miner/experiments/frequent-pattern-miner/valuation)
!(import! &self external/hyperon-miner/experiments/frequent-pattern-miner/shallow-abstractions)
!(import! &self external/hyperon-miner/experiments/frequent-pattern-miner/specialization)
!(import! &self external/hyperon-miner/experiments/frequent-pattern-miner/candidate)
!(import! &self external/hyperon-miner/experiments/frequent-pattern-miner/conjunction-expansion)
;; FIX 1: the generic miner, which matches the call inside pattern-miner.metta
!(import! &self external/hyperon-miner/experiments/frequent-pattern-miner/frequent-pattern-miner-generic)
!(import! &self external/hyperon-miner/experiments/pattern-miner/pattern-miner)

;; --- 2. Data ---------------------------------------------------------------
!(import! &db external/hyperon-miner/experiments/data/ugly_man_sodaDrinker)
!(bind! &res (new-space))

;; --- 3. Run ----------------------------------------------------------------
;; FIX 2: all 9 arguments, in the order pattern-miner.metta declares them:
;; (pattern-miner <out> <db> <initpat> <minsup> <depth> <surp-mode> <normalize> <db-ratio> <conj-exp>)
;;   <initpat>    $x  -> start from the most abstract pattern
;;   <minsup>     10  -> a pattern must match at least 10 times
;;   <depth>      0   -> 2-conjunct patterns (1 -> 3 conjuncts, ...)
;;   <surp-mode>  isurp | isurp-old | jsd | none
!(pattern-miner &res &db $x 10 0 isurp True 0.5 True)

;; --- 4. Results ------------------------------------------------------------
!(get-atoms &res)
