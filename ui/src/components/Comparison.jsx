import { useState } from "react";
import { familyName, fmtPct } from "../format.js";

const BUDGETS = [0.1, 0.2, 0.3, 0.5];
const isHybrid = (fam) => fam.startsWith("llm-hybrid");

// Recall@10 of every method at one budget: how many of the 10 most surprising
// patterns (from the exhaustive reference) each method reached. One series, so one
// colour; Step 7 (exploratory) rows are drawn lighter and labelled. The 90 % line is
// the pre-registered success threshold for the LLM (H1).
export default function Comparison({ results, dataset, heldout, datasetTitle, budget, highlight }) {
  const [hover, setHover] = useState(null);
  const [chosen, setChosen] = useState(null);
  const b = heldout ? 0.3 : chosen ?? (BUDGETS.includes(budget) ? budget : 0.3);
  const atBudget = (r) => Math.abs(r.budget - b) < 1e-9;

  // Held-out datasets exist only in Step 7. Development datasets show the pre-registered
  // rows, plus the Step 7 hybrid rows at 30 % (marked exploratory).
  const pre = heldout ? [] : (results?.rows ?? []).filter((r) => r.dataset === dataset && r.family !== "upstream" &&
    r["recall@10"] != null && (atBudget(r) || r.family === "exhaustive"));
  const explore = (results?.exploratory ?? []).filter((r) => r.dataset === dataset && r["recall@10"] != null &&
    atBudget(r) && (heldout || isHybrid(r.family)));
  const rows = [...pre, ...explore].sort((x, y) => y["recall@10"] - x["recall@10"]);

  const h1 = Object.entries(results?.verdicts?.H1 ?? {}).filter(([k]) => k.startsWith(`${dataset} /`));
  const checks = Object.values(results?.exploratory_checks ?? {}).filter((c) => c.dataset === dataset && c.heldout);

  return (
    <section className="panel compare" aria-labelledby="compare-title">
      <div className="panel__head">
        <h2 id="compare-title" className="panel__title">How the methods compare</h2>
        {heldout ? (
          <span className="compare__badge">Step 7 · held-out data · 30 %</span>
        ) : (
          <div className="segmented segmented--small" role="radiogroup" aria-label="Budget">
            {BUDGETS.map((x) => (
              <button key={x} type="button" role="radio" aria-checked={b === x}
                      className={`segmented__option ${b === x ? "is-on" : ""}`} onClick={() => setChosen(x)}>
                {Math.round(x * 100)} %
              </button>
            ))}
          </div>
        )}
      </div>
      <p className="compare__lede">
        Share of the 10 most surprising patterns each method found on the {datasetTitle ?? dataset} when
        it checked {Math.round(b * 100)} % of the candidates.{" "}
        {heldout
          ? "This dataset played no part in designing the hybrid ranker; one run per method (random: 5 seeds)."
          : "Averages over seeds and repeats; whiskers show one standard deviation."}
        {!heldout && explore.length > 0 && " Lighter bars are the Step 7 follow-up, which is exploratory and not part of the pre-registered test."}
      </p>

      {rows.length === 0 ? (
        <p className="empty">No evaluation results for this dataset at this budget.</p>
      ) : (
        <div className="bars" role="img" aria-label={`Recall at 10 by method at ${Math.round(b * 100)} % budget`}>
          <div className="bars__plot">
            <div className="bars__overlay" aria-hidden="true">
              <span className="bars__target" style={{ left: "90%" }}><span>90 % target</span></span>
              {highlight != null && (
                <span className="bars__run" style={{ left: `${highlight * 100}%` }}><span>this run</span></span>
              )}
            </div>
            {rows.map((r) => {
              const v = r["recall@10"], sd = r["recall@10_sd"] ?? 0;
              const exploratory = isHybrid(r.family) || heldout;
              return (
                <div key={r.family} className={`bars__row ${r.family.startsWith("llm") ? "is-llm" : ""} ${isHybrid(r.family) && !heldout ? "is-exploratory" : ""}`}
                     onMouseEnter={() => setHover(r)} onMouseLeave={() => setHover(null)}
                     onFocus={() => setHover(r)} onBlur={() => setHover(null)} tabIndex={0}>
                  <span className="bars__label">
                    {familyName(r.family)}{r.family === "exhaustive" ? ", 100 %" : ""}
                    {isHybrid(r.family) && !heldout && <span className="bars__tag">Step 7</span>}
                  </span>
                  <span className="bars__track">
                    <span className="bars__fill" style={{ width: `${Math.max(v * 100, 0.6)}%` }} />
                    {sd > 0 && (
                      <span className="bars__whisker"
                            style={{ left: `${Math.max(0, v - sd) * 100}%`, width: `${(Math.min(1, v + sd) - Math.max(0, v - sd)) * 100}%` }} />
                    )}
                  </span>
                  <span className="bars__value">{fmtPct(v)}</span>
                  {hover === r && (
                    <span className="tooltip" role="tooltip">
                      <strong>{familyName(r.family)}{exploratory ? " (Step 7, exploratory)" : ""}</strong>
                      <span>Recall@10 {fmtPct(v, 1)}{sd ? ` ± ${fmtPct(sd, 1)}` : ""} over {r.runs} run{r.runs === 1 ? "" : "s"}</span>
                      <span>Checked {Math.round(r.verified)} candidates in {r.seconds?.toFixed(1)} s</span>
                      {r.planted_found != null && <span>Planted patterns found: {r.planted_found.toFixed(1)} of 3</span>}
                      {r.cost_usd != null && r.family.startsWith("llm") && (
                        <span>{r.cost_usd > 0 ? `LLM cost $${r.cost_usd.toFixed(4)} per run` : "LLM cost: free tier"}</span>
                      )}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {heldout && checks.length > 0 && (
        <div className="verdicts">
          <h3 className="verdicts__title">Step 7 checks against the H1 bar (exploratory)</h3>
          <p className="verdicts__rule">
            The same rule as H1: at least 90 % of the top 10 and above every cheap baseline. H1 itself stays rejected.
          </p>
          <ul>
            {checks.sort((x, y) => y["recall@10"] - x["recall@10"]).map((c) => {
              const good = c.verdict === "meets the H1 bar";
              const better = c.verdict.startsWith("beats");
              return (
                <li key={c.family} className={good ? "is-good" : better ? "is-mid" : "is-bad"}>
                  <span className="verdicts__mark" aria-hidden="true">{good ? "✓" : better ? "↑" : "✕"}</span>
                  {familyName(c.family)}: {fmtPct(c["recall@10"])} against {familyName(c.best_baseline).toLowerCase()}'s{" "}
                  {fmtPct(c["best_baseline_recall@10"])}, {c.verdict}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {!heldout && h1.length > 0 && (
        <div className="verdicts">
          <h3 className="verdicts__title">Hypothesis H1 at 30 %</h3>
          <p className="verdicts__rule">The LLM had to reach at least 90 % of the top 10 and beat every cheap baseline.</p>
          <ul>
            {h1.map(([k, v]) => (
              <li key={k} className={v.verdict === "supported" ? "is-good" : "is-bad"}>
                <span className="verdicts__mark" aria-hidden="true">{v.verdict === "supported" ? "✓" : "✕"}</span>
                {familyName(k.split(" / ")[1])}: {fmtPct(v.llm)} against the best baseline's{" "}
                {fmtPct(Math.max(v.heuristic ?? 0, v.cardinality ?? 0, v.random ?? 0))}, {v.verdict}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
