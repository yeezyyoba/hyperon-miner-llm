import { useState } from "react";
import { familyName, fmtPct } from "../format.js";

const BUDGETS = [0.1, 0.2, 0.3, 0.5];

// Recall@10 of every method at one budget: how many of the 10 most surprising
// patterns (from the exhaustive reference) each method reached. One series, so one
// colour; the 90 % line is the pre-registered success threshold for the LLM (H1).
export default function Comparison({ results, dataset, datasetTitle, budget, highlight }) {
  const [hover, setHover] = useState(null);
  const [chosen, setChosen] = useState(null);
  const b = chosen ?? (BUDGETS.includes(budget) ? budget : 0.3);
  const rows = (results?.rows ?? [])
    .filter((r) => r.dataset === dataset && r.family !== "upstream" && r["recall@10"] != null &&
      (Math.abs(r.budget - b) < 1e-9 || r.family === "exhaustive"))
    .sort((x, y) => y["recall@10"] - x["recall@10"]);
  const verdicts = Object.entries(results?.verdicts?.H1 ?? {}).filter(([k]) => k.startsWith(`${dataset} /`));

  return (
    <section className="panel compare" aria-labelledby="compare-title">
      <div className="panel__head">
        <h2 id="compare-title" className="panel__title">How the methods compare</h2>
        <div className="segmented segmented--small" role="radiogroup" aria-label="Budget">
          {BUDGETS.map((x) => (
            <button key={x} type="button" role="radio" aria-checked={b === x}
                    className={`segmented__option ${b === x ? "is-on" : ""}`} onClick={() => setChosen(x)}>
              {Math.round(x * 100)} %
            </button>
          ))}
        </div>
      </div>
      <p className="compare__lede">
        Share of the 10 most surprising patterns each method found on the {datasetTitle ?? dataset} when
        it checked {Math.round(b * 100)} % of the candidates. Averages over seeds and repeats; whiskers
        show one standard deviation.
      </p>

      {rows.length === 0 ? (
        <p className="empty">No evaluation results for this dataset yet. Run <code>make eval-baselines</code> and <code>make report</code>.</p>
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
              const isLlm = r.family.startsWith("llm");
              return (
                <div key={r.family} className={`bars__row ${isLlm ? "is-llm" : ""}`}
                     onMouseEnter={() => setHover(r)} onMouseLeave={() => setHover(null)}
                     onFocus={() => setHover(r)} onBlur={() => setHover(null)} tabIndex={0}>
                  <span className="bars__label">{familyName(r.family)}{r.family === "exhaustive" ? ", 100 %" : ""}</span>
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
                      <strong>{familyName(r.family)}</strong>
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

      {verdicts.length > 0 && (
        <div className="verdicts">
          <h3 className="verdicts__title">Hypothesis H1 at 30 %</h3>
          <p className="verdicts__rule">The LLM had to reach at least 90 % of the top 10 and beat every cheap baseline.</p>
          <ul>
            {verdicts.map(([k, v]) => (
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
