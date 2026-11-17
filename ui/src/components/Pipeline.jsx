import { fmtInt, fmtSec } from "../format.js";

// The four stages every run goes through, filled in as trace events arrive.
export function pipelineState(events) {
  const s = { generated: null, unique: null, selected: null, kept: null, level: null,
    batchesAnswered: 0, batchesTotal: 0, wall: null, llmSeconds: 0 };
  for (const e of events) {
    if (e.kind === "llm_batch") {
      s.batchesAnswered += 1;
      s.batchesTotal = Math.max(s.batchesTotal, e.of ?? 0);
    } else if (e.kind === "select") {
      s.generated = (s.generated ?? 0) + e.generated;
      s.unique = (s.unique ?? 0) + e.unique;
      s.selected = (s.selected ?? 0) + e.selected;
      s.level = e.level;
      s.llmSeconds += e.llm_seconds ?? 0;
    } else if (e.kind === "verify") {
      s.kept = e.kept;
      s.level = e.level;
    } else if (e.kind === "finish") {
      s.wall = e.wall_seconds;
      s.generated = e.generated;
      s.unique = e.unique;
      s.selected = e.selected;
      s.kept = e.kept;
    }
  }
  return s;
}

export default function Pipeline({ run, budget }) {
  const s = pipelineState(run.events);
  const scored = run.result?.n_patterns ?? null;
  const usesLlm = (run.info?.strategy ?? "").startsWith("llm");
  const active = run.status === "running";

  const stages = [
    { key: "generated", label: "Candidates built", value: s.generated,
      note: "every way to extend a frequent pattern" },
    { key: "unique", label: "After removing duplicates", value: s.unique,
      note: "same pattern, different variable names" },
    { key: "selected", label: "Checked by the miner", value: s.selected,
      note: s.unique ? `${Math.round((s.selected / s.unique) * 100)} % of candidates, best first` :
        `budget ${Math.round(budget * 100)} %, best first` },
    { key: "kept", label: "Frequent patterns", value: s.kept,
      note: scored != null ? `${fmtInt(scored)} scored for surprisingness` : "support at or above the threshold" },
  ];

  return (
    <section className={`pipeline ${active ? "is-active" : ""}`} aria-label="Mining progress">
      <ol className="pipeline__stages">
        {stages.map((st, i) => (
          <li key={st.key} className={`stage ${st.value != null ? "is-filled" : ""}`}>
            <span className="stage__value">{st.value != null ? fmtInt(st.value) : "–"}</span>
            <span className="stage__label">{st.label}</span>
            <span className="stage__note">{st.note}</span>
            {i === 1 && usesLlm && (
              <span className={`stage__llm ${s.batchesAnswered ? "is-on" : ""}`}>
                LLM ordering: {s.batchesAnswered}/{s.batchesTotal || "…"} batches
              </span>
            )}
          </li>
        ))}
      </ol>
      <p className="pipeline__status" aria-live="polite">
        {statusLine(run, s)}
      </p>
    </section>
  );
}

function statusLine(run, s) {
  if (run.status === "idle") return "Choose a dataset and press start. Replays need no API keys.";
  if (run.status === "running") {
    if (s.level == null) return run.mode === "live" ? "Loading the data into PeTTa…" : "Starting the replay…";
    return `Working on level ${s.level + 1} (${s.level + 2}-clause patterns)`;
  }
  if (run.status === "cancelling") return "Stopping…";
  if (run.status === "cancelled") return "Stopped.";
  if (run.status === "failed") return `Run failed: ${run.error ?? "see the events log"}`;
  return `Finished in ${fmtSec(s.wall)}${s.llmSeconds >= 0.05 ? `, of which ${fmtSec(s.llmSeconds)} waiting for the LLM` : ""}.`;
}
