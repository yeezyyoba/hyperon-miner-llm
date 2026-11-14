;; =============================================================================
;; Upstream miner, 2 conjuncts (depth 0), minsup 10, with live assertions.
;; Expected values are copied from upstream's test-pattern-miner.metta, whose
;; own assertions are never executed (no "!"; docs/01-problem.md, Issue 3).
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
!(bind! &res1 (new-space))
!(bind! &res2 (new-space))

!(pattern-miner &res1 &db $x 10 0 none none none True)
!(test (size-atom (collapse (get-atoms &res1))) 12)
!(test (score-of &res1 supportOf (, (Inheritance $v sodaDrinker) (Inheritance $v human))) (10))
!(test (score-of &res1 supportOf (, (Inheritance $v $a) (Inheritance $v $b))) (190))
!(test (score-of &res1 supportOf (, (Inheritance $v $a) (Inheritance $w $a))) (800))

;; Issue 5 (state leak): pattern-miner writes into the global spaces &cndpspace
;; and &conjspace and never clears them. A second run in the same process
;; therefore returns 32 patterns instead of the 20 a fresh process returns
;; (see test-upstream-depth1.metta). Upstream's test runs both configurations
;; in one file, so it would fail if its assertions were executed.
!(pattern-miner &res2 &db $x 10 1 none none none True)
!(test (size-atom (collapse (get-atoms &res2))) 32)
