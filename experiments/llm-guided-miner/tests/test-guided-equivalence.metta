;; =============================================================================
;; Guided miner, strategy exhaustive, budget 1.0 => must equal the upstream miner.
;; Same data / minsup / depth as ../../upstream-regression/tests/test-upstream-depth1.metta:
;; upstream prints 20 patterns there, 16 of them distinct. The guided miner
;; removes clause-order duplicates before counting, so it returns exactly
;; those 16, with the same supports.
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

(= (score-of $space $tag $pattern)
   (collapse (match $space ($tag $p $s) (if (=alpha $p $pattern) $s (empty)))))

!(import! &db ../../../external/hyperon-miner/experiments/data/ugly_man_sodaDrinker)
!(bind! &res (new-space))

!(guided-pattern-miner &res &db $x 10 1 none none none "exhaustive.run.json")
!(test (size-atom (collapse (get-atoms &res))) 16)
!(test (score-of &res supportOf (, (Inheritance $v $a) (Inheritance $w $a) (Inheritance $u $a))) (12000))
!(test (score-of &res supportOf (, (Inheritance $v $a) (Inheritance $v $b) (Inheritance $v $c))) (630))
;; (=alpha is clause-order sensitive; this is the order the guided miner emits)
!(test (score-of &res supportOf (, (Inheritance $v $a) (Inheritance $v human) (Inheritance $v sodaDrinker))) (35))
;; every emitted pattern passed the minsup check in MeTTa
!(test (collapse (match &res (supportOf $p $s) (if (< $s 10) (below-minsup $p) (empty)))) ())
