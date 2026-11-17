import { PROVIDER_NAMES, fmtInt, fmtSec } from "../format.js";

export default function EventsPanel({ run }) {
  const items = run.events.map(describe).filter(Boolean).reverse();
  return (
    <section className="panel events" aria-labelledby="events-title">
      <div className="panel__head">
        <h2 id="events-title" className="panel__title">Live events</h2>
        {run.status === "running" && <span className="live-dot" aria-label="streaming">streaming</span>}
      </div>
      {run.info?.command && <code className="events__command">{run.info.command}</code>}
      {items.length === 0 ? (
        <p className="empty">Events from the miner and the LLM appear here as they happen.</p>
      ) : (
        <ol className="events__list" aria-live="polite">
          {items.map((it) => (
            <li key={it.seq} className={`event event--${it.tone}`}>
              <span className="event__time">{it.t != null ? `${it.t.toFixed(1)} s` : ""}</span>
              <span className="event__text">
                {it.text}
                {it.detail && <span className="event__detail">{it.detail}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function describe(e) {
  // Trace events carry the miner's clock (t). Others (log, result, status) have no
  // place on that clock, so they show no time rather than a misleading one.
  const base = { seq: e.seq, t: e.t ?? null, tone: "info" };
  switch (e.kind) {
    case "started":
      return { ...base, t: 0, text: e.mode === "live" ? "Started the miner" : "Started the replay" };
    case "configure":
      return { ...base, text: `Miner ready: ${e.strategy}, ${Math.round(e.budget * 100)} % budget`,
        detail: e.providers?.length ? `Providers: ${e.providers.map((p) => PROVIDER_NAMES[p] ?? p).join(" then ")}` : null };
    case "llm_batch":
      if (e.failed)
        return { ...base, tone: "warn", text: `Batch ${e.batch} of ${e.of}: every provider failed`,
          detail: `Used the cardinality order instead. ${e.failed}` };
      return { ...base, tone: e.cached ? "quiet" : "llm",
        text: e.cached
          ? `Batch ${e.batch} of ${e.of} from cache (${PROVIDER_NAMES[e.provider] ?? e.provider})`
          : `${PROVIDER_NAMES[e.provider] ?? e.provider} scored batch ${e.batch} of ${e.of} in ${fmtSec(e.seconds)}`,
        detail: e.model };
    case "select": {
      const joins = (e.top_joins ?? []).slice(0, 3).map(([j, s]) => `${j} (${s})`).join("; ");
      return { ...base, text: `Level ${e.level + 1}: ${fmtInt(e.generated)} candidates, ${fmtInt(e.unique)} unique, checking ${fmtInt(e.selected)}`,
        detail: joins ? `Highest-rated joins: ${joins}` : null };
    }
    case "verify":
      return { ...base, tone: "good", text: `Level ${e.level + 1}: ${fmtInt(e.kept)} frequent patterns kept`,
        detail: `Verified by the miner in ${fmtSec(e.seconds)}` };
    case "finish":
      return { ...base, tone: "good", text: `Mining finished in ${fmtSec(e.wall_seconds)}`,
        detail: e.batches ? `${e.batches} LLM batches, ${e.fallback_batches} fell back` : null };
    case "result": {
      const r = e.result;
      return { ...base, tone: "good", text: `${fmtInt(r.n_patterns)} patterns scored and ranked`,
        detail: r.oracle_ok === false ? "Oracle found mismatching supports" : "Supports match the Python oracle" };
    }
    case "log":
      return { ...base, tone: "quiet", text: e.line };
    case "status":
      if (e.status === "failed") return { ...base, tone: "warn", text: "Run failed", detail: e.error };
      if (e.status === "cancelled") return { ...base, tone: "warn", text: "Run stopped" };
      return null;
    default:
      return null;
  }
}
