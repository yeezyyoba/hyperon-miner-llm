;; =============================================================================
;; Upstream miner + isurp scoring — characterisation of Issue 4 (duplicates).
;;
;; The frequent miner prints 12 patterns at minsup 10 / depth 0, but two of them
;; are the same pattern with the clauses in a different order:
;;     (, (Inheritance $v man) (Inheritance $v $a))
;;     (, (Inheritance $v $a) (Inheritance $v man))
;; Scoring keeps one copy, so 11 scored patterns come out. Nothing is lost, but
;; the frequent output is redundant: on a 200-atom Galaxy subset at 3 conjuncts,
;; 121 printed patterns are only 46 distinct ones (minerllm.patterns.canonical).
;; =============================================================================
;; --- upstream modules (same order as upstream test-pattern-miner.metta) ---
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

;; Exact lookup: match unifies both ways, so a query with variables would also
;; hit more general stored patterns. =alpha compares up to variable renaming.
(= (score-of $space $tag $pattern)
   (collapse (match $space ($tag $p $s) (if (=alpha $p $pattern) $s (empty)))))

!(import! &db ../../../external/hyperon-miner/experiments/data/ugly_man_sodaDrinker)
!(bind! &res (new-space))

!(pattern-miner &res &db $x 10 0 isurp True 0.5 True)
;; 11 scored = 12 printed frequent patterns minus 1 clause-order duplicate
!(test (size-atom (collapse (get-atoms &res))) 11)
;; one spelling of the duplicated pattern is scored ...
!(test (score-of &res surprisingnessOf (, (Inheritance $v man) (Inheritance $v $a))) (0.6666666666666667))
;; ... and the other spelling is not scored a second time
!(test (score-of &res surprisingnessOf (, (Inheritance $v $a) (Inheritance $v man))) ())
!(test (score-of &res surprisingnessOf (, (Inheritance $v $a) (Inheritance $w $a))) (0.925))
