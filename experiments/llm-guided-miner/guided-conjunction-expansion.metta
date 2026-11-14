;; =============================================================================
;; guided-conjunction-expansion.metta
;; LLM-guided conjunction expansion for the Hyperon pattern miner (PeTTa).
;; =============================================================================
;;
;; Upstream (frequent-pattern-miner/conjunction-expansion.metta) does, per level:
;;     for every frontier conjunction F and every frequent clause P
;;       for every way to link a variable of P to a variable of F
;;         count support of (, F P')        <- expensive: a full match on the db
;;         keep it if support >= minsup
;;
;; This module splits that into GENERATE -> SELECT -> VERIFY:
;;
;;   GENERATE  all linked candidates (, F P'), using upstream's own alpha_convert,
;;             expand_conjunction_connect and remove_conjuncts_with_redundant_clauses.
;;             No support is counted here.
;;   SELECT    (py-call (minerllm_bridge.select <reprs> <level>)). Python removes
;;             duplicates, asks the ranker (exhaustive | random | heuristic | llm)
;;             for an order, and returns the positions of the top budget fraction.
;;   VERIFY    support is counted in MeTTa with upstream's sup-num, for exactly
;;             those candidates; minsup is applied as before.
;;
;; The LLM can only change WHICH candidates get verified first. Every pattern
;; this miner outputs has a support counted by MeTTa (and the harness re-checks
;; it with an independent Python oracle). With strategy exhaustive and
;; budget 1.0 the output equals the upstream miner's (tests/test-guided-*.metta).
;;
;; Requires the upstream modules and the Python bridge, imported by the CALLER
;; (PeTTa resolves nested imports relative to the top-level file, and a missing
;; path fails silently, so this module does not import them itself):
;;     !(import! &self <path>/experiments/llm-guided-miner/minerllm_bridge.py)
;; See run_guided.metta, or minerllm.config.render_guided_script.
!(bind! &guided-cndp (new-space))

;; -----------------------------------------------------------------------------
;; Conjunction helpers. Like upstream, conjunctions are kept in nested binary form
;; (, (, C1 C2) C3) during expansion, and flattened to (, C1 C2 C3) for counting
;; and output.
;; -----------------------------------------------------------------------------
(= (guided-flat $nested) (cons-atom , (get-conjuncts $nested)))

;; Fresh copy of an atom (new variables). The frontier and the clause list are
;; reused across nondeterministic branches; without copying, a variable linked in
;; one branch leaks into the others. Upstream avoids the same problem by
;; round-tripping through De Bruijn indices (replace / replacev).
(= (guided-fresh $atom) (sread (repr $atom)))

;; One-step expansions of conjunction $cnj with clause $pat (nondeterministic:
;; one result per variable linkage). Cheap: no support counting and no
;; redundancy filtering here (see guided-verify).
(= (guided-expand-one $cnj0 $pat0)
   (let* (($cnj (guided-fresh $cnj0))
          ($pat (guided-fresh $pat0))
          ($cv (get_variables_for_tree $cnj))
          (($apat $pv) (alpha_convert $pat $cv))
          ($new (expand_conjunction_connect $cnj $apat $cv $pv)))
     (if (== $new ()) (empty) $new)))

;; GENERATE: every candidate of the next level, as a list (no support counted).
(= (guided-generate $frontier $singles)
   (collapse (guided-expand-one (superpose $frontier) (superpose $singles))))

;; Text form of each (flattened) candidate, for the Python bridge.
;; (map-atom is PeTTa's built-in maplist: linear. A hand-written car/cdr
;;  recursion over thousands of candidates was ~10x slower.)
(= (guided-reprs $cands) (map-atom $cands $c (repr (guided-flat $c))))

;; VERIFY one candidate: MeTTa counts the support; minsup decides. Then upstream's
;; redundancy filter runs on survivors only, the same order as upstream's
;; do-conjunct (checker first, remove_conjuncts_with_redundant_clauses after).
;; The filter is the expensive step (~4 ms per candidate on Galaxy), so it must
;; never run on the full candidate list.
(= (guided-verify $db $cand $minsup)
   (let $sup (sup-num $db (guided-flat $cand))
        (if (>= $sup $minsup)
            (if (== (remove_conjuncts_with_redundant_clauses $cand) ()) (empty) ($cand $sup))
            (empty))))

(= (guided-firsts $pairs) (map-atom $pairs $p (car-atom $p)))

;; One level: GENERATE -> SELECT -> VERIFY. Returns a list of (candidate support).
(= (guided-level $db $frontier $singles $minsup $level)
   (let* (($cands (guided-generate $frontier $singles))
          (true (println! (guided-generated $level (size-atom $cands))))
          ($reprs (guided-reprs $cands))
          ($picked (py-call (minerllm_bridge.select $reprs $level)))
          ($t0 (py-call (minerllm_bridge.verify_started $level)))
          ($kept (collapse (guided-verify $db (index-atom $cands (superpose $picked)) $minsup)))
          ($t1 (py-call (minerllm_bridge.verify_finished $level (size-atom $kept)))))
     $kept))

;; Levels: depth 0 -> one expansion (2 conjuncts), depth 1 -> two (3 conjuncts), ...
(= (guided-levels $db $frontier $singles $minsup Z $level)
   (guided-level $db $frontier $singles $minsup $level))
(= (guided-levels $db $frontier $singles $minsup (S $k) $level)
   (let* (($kept (guided-level $db $frontier $singles $minsup $level))
          ($next (guided-firsts $kept)))
     (if (== $next ())
         ()
         (guided-levels $db $next $singles $minsup $k (+ $level 1)))))

;; Emit one final pattern through upstream's scoring dispatcher.
(= (guided-emit $kb $db ($cand $sup) $surp-mode $normalization $db-ratio)
   (call-surprisingness $kb $db (supportOf (guided-flat $cand) $sup) $surp-mode $normalization $db-ratio))

;; -----------------------------------------------------------------------------
;; guided-pattern-miner — same contract as upstream pattern-miner, plus the path
;; of the run's JSON config (ranker strategy, budget, LLM providers, trace file).
;;
;; (guided-pattern-miner <out> <db> <initpat> <minsup> <depth> <surp-mode>
;;                       <normalize> <db-ratio> <run-config.json>)
;; -----------------------------------------------------------------------------
(= (guided-pattern-miner $kb $db $initpat $minsup $depth $surp-mode $normalization $db-ratio $config)
   (let* ((true (println! "==== Guided Pattern Miner Started ====="))
          ($ok (py-call (minerllm_bridge.configure $config)))
          ;; frequent single clauses: upstream's candidate miner, unchanged
          ($c (collapse (candidate-pattern-miner $initpat $db $minsup &guided-cndp)))
          ($singles (collapse (match &guided-cndp (CandidatePattern $p $n) (replacev $p))))
          (true (println! (guided-singles (size-atom $singles))))
          ($final (guided-levels $db $singles $singles $minsup (fromNumber $depth) 0))
          ($e (collapse (guided-emit $kb $db (superpose $final) $surp-mode $normalization $db-ratio)))
          ($done (py-call (minerllm_bridge.finish))))
     ()))
