;; =============================================================================
;; Characterisation of Issue 7: add-atom-nodup drops DIFFERENT patterns.
;;
;; upstream common-utils.metta:
;;   (= (add-atom-nodup $space $atom)
;;      (case (match $space $atom $atom) (($atom ()) (Empty (add-atom $space $atom)))))
;;
;; `match` unifies in both directions, so variables in the new atom bind to
;; constants in a stored one (and vice versa). Two different patterns with the
;; SAME score therefore look like duplicates, and the second is silently dropped.
;; Upstream stores every surprisingness score this way (do-surp, do-jsd-surp,
;; do-IIsurp), and scores tie a lot, so a full university run keeps only 343 of
;; its 641 frequent patterns. If this test starts failing, upstream fixed it
;; (see patches/0002): update docs/01-problem.md.
;; =============================================================================
!(import! &self ../../../external/hyperon-miner/experiments/utils/common-utils)

!(bind! &kb (new-space))
!(add-atom &kb (surprisingnessOf (, (R $x a)) 0.5))

;; a different pattern, same score -> silently dropped
!(add-atom-nodup &kb (surprisingnessOf (, (R b $y)) 0.5))
!(test (size-atom (collapse (get-atoms &kb))) 1)

;; the same different pattern with another score -> kept
!(add-atom-nodup &kb (surprisingnessOf (, (R b $y)) 0.7))
!(test (size-atom (collapse (get-atoms &kb))) 2)

;; a pattern with a constant where the stored one has a variable -> also dropped
!(add-atom-nodup &kb (surprisingnessOf (, (R c a)) 0.5))
!(test (size-atom (collapse (get-atoms &kb))) 2)
