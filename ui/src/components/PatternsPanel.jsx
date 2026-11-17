import { useMemo, useState } from "react";
import PatternView from "./PatternView.jsx";
import { fmtInt } from "../format.js";

const FILTERS = [
  ["all", "All"],
  ["top10", "Reference top 10"],
  ["planted", "Planted"],
];
const PAGE = 25;

export default function PatternsPanel({ run, dataset }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);
  const result = run.result;

  const rows = useMemo(() => {
    if (!result) return [];
    const q = query.trim().toLowerCase().replace(/\s+/g, "_");
    return result.patterns.filter((p) =>
      (filter === "all" || (filter === "top10" && p.top10) || (filter === "planted" && p.planted)) &&
      (!q || p.pattern.toLowerCase().includes(q)));
  }, [result, filter, query]);

  const maxSurp = result ? Math.max(...result.patterns.map((p) => p.surprisingness ?? 0), 1e-9) : 1;
  const plantedTotal = dataset?.planted?.length ?? 0;

  return (
    <section className="panel patterns" aria-labelledby="patterns-title">
      <div className="panel__head">
        <h2 id="patterns-title" className="panel__title">Extracted patterns</h2>
        {result && (
          <ul className="patterns__facts">
            <li><strong>{fmtInt(result.n_patterns)}</strong> patterns</li>
            {result.recall_at_10 != null && (
              <li><strong>{Math.round(result.recall_at_10 * 100)} %</strong> of the reference top 10</li>
            )}
            {plantedTotal > 0 && (
              <li><strong>{result.planted_found.length} of {plantedTotal}</strong> planted found</li>
            )}
          </ul>
        )}
      </div>

      {!result ? (
        <EmptyState run={run} dataset={dataset} />
      ) : (
        <>
          <div className="patterns__tools">
            <div className="segmented segmented--small" role="radiogroup" aria-label="Filter patterns">
              {FILTERS.filter(([k]) => k !== "planted" || plantedTotal > 0).map(([k, l]) => (
                <button key={k} type="button" role="radio" aria-checked={filter === k}
                        className={`segmented__option ${filter === k ? "is-on" : ""}`}
                        onClick={() => { setFilter(k); setShown(PAGE); }}>
                  {l}
                </button>
              ))}
            </div>
            <input className="search" type="search" placeholder="Filter by relation, e.g. teaches"
                   value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE); }}
                   aria-label="Filter patterns by relation" />
          </div>

          <div className="patterns__legend">
            Letters are variables: the same letter in two clauses means they share that entity.
          </div>

          {rows.length === 0 ? (
            <p className="empty">
              {filter === "planted" ? "This run did not reach any planted pattern within its budget." : "No pattern matches this filter."}
            </p>
          ) : (
            <ol className="patterns__list">
              {rows.slice(0, shown).map((p) => (
                <li key={p.pattern} className={`pattern-row ${p.planted ? "is-planted" : ""}`}>
                  <span className="pattern-row__rank">{p.rank}</span>
                  <div className="pattern-row__body">
                    <PatternView pattern={p.pattern} />
                    <div className="pattern-row__tags">
                      {p.planted && <span className="tag tag--planted">Planted: {plantedName(p.planted)}</span>}
                      {p.top10 && <span className="tag tag--top">Reference top 10</span>}
                    </div>
                  </div>
                  <div className="pattern-row__nums">
                    <span className="num" title="Surprisingness (isurp)">
                      {p.surprisingness != null ? p.surprisingness.toFixed(3) : "–"}
                    </span>
                    <span className="surp-bar" aria-hidden="true">
                      <span style={{ width: `${Math.max(2, ((p.surprisingness ?? 0) / maxSurp) * 100)}%` }} />
                    </span>
                    <span className="pattern-row__support">support {fmtInt(p.support)}</span>
                  </div>
                </li>
              ))}
            </ol>
          )}
          {rows.length > shown && (
            <button type="button" className="button button--quiet patterns__more" onClick={() => setShown(shown + PAGE)}>
              Show {Math.min(PAGE, rows.length - shown)} more of {fmtInt(rows.length - shown)}
            </button>
          )}
        </>
      )}
    </section>
  );
}

function plantedName(id) {
  // "P1_major_in_advisor_dept" -> "major in advisor's department"
  return id.replace(/^P\d+_/, "").replace(/_/g, " ").replace("advisor dept", "advisor's department")
    .replace("advisor course", "advisor's course").replace("teacher dept", "teacher's department");
}

function EmptyState({ run, dataset }) {
  if (run.status === "running" || run.status === "cancelling")
    return <p className="empty">Patterns appear when the miner finishes scoring them.</p>;
  if (run.status === "failed") return <p className="empty">No patterns: the run failed. The events log says why.</p>;
  return (
    <div className="empty empty--intro">
      <p>The miner looks for patterns that occur more often than chance would predict.</p>
      {dataset?.planted?.length > 0 && (
        <>
          <p>This graph has {dataset.planted.length} patterns planted in it on purpose:</p>
          <ul className="planted-list">
            {dataset.planted.map((p) => (
              <li key={p.name}><PatternView pattern={p.pattern} /></li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
