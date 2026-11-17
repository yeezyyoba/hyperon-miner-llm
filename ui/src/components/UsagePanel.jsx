import { useState } from "react";
import { PROVIDER_NAMES, fmtInt, fmtSec, fmtUsd } from "../format.js";

export default function UsagePanel({ run, session, providers }) {
  const [scope, setScope] = useState("run");
  const usage = scope === "run" ? run.usage : session;
  const t = usage?.totals ?? {};
  const rows = Object.entries(usage?.providers ?? {});
  const models = Object.fromEntries((providers?.providers ?? []).map((p) => [p.name, p]));
  const replay = scope === "run" && run.mode === "replay";
  const progress = usage?.batches_total ? usage.batches_answered / usage.batches_total : 0;

  return (
    <section className="panel usage" aria-labelledby="usage-title">
      <div className="panel__head">
        <h2 id="usage-title" className="panel__title">API usage</h2>
        <div className="segmented segmented--small" role="radiogroup" aria-label="Usage scope">
          {[["run", "This run"], ["session", "Session"]].map(([v, l]) => (
            <button key={v} type="button" role="radio" aria-checked={scope === v}
                    className={`segmented__option ${scope === v ? "is-on" : ""}`} onClick={() => setScope(v)}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {replay && <p className="usage__note">Recorded run: these are the numbers it used when it ran.</p>}

      <dl className="usage__headline">
        <div>
          <dt>Tokens</dt>
          <dd>{fmtInt((t.input_tokens ?? 0) + (t.output_tokens ?? 0))}</dd>
          <span className="usage__sub">{fmtInt(t.input_tokens ?? 0)} in, {fmtInt(t.output_tokens ?? 0)} out</span>
        </div>
        <div>
          <dt>Cost</dt>
          <dd>{fmtUsd(t.cost_usd ?? 0)}</dd>
          <span className="usage__sub">at list prices</span>
        </div>
      </dl>

      <div className="usage__progress" aria-label="LLM batches answered">
        <div className="usage__bar"><span style={{ width: `${Math.round(progress * 100)}%` }} /></div>
        <span>{usage?.batches_answered ?? 0} of {usage?.batches_total || "–"} batches answered</span>
      </div>

      <dl className="usage__grid">
        <Stat label="Requests" value={fmtInt(t.requests ?? 0)} />
        <Stat label="Cache hits" value={fmtInt(t.cached ?? 0)} />
        <Stat label="Retries" value={fmtInt(t.retries ?? 0)} />
        <Stat label="Rate-limit wait" value={fmtSec(t.rate_limit_wait_s ?? 0)} />
        <Stat label="Failed requests" value={fmtInt(t.failed ?? 0)} warn={(t.failed ?? 0) > 0} />
        <Stat label="Fell back to baseline" value={fmtInt(usage?.fallback_batches ?? 0)}
              warn={(usage?.fallback_batches ?? 0) > 0} />
      </dl>

      <h3 className="usage__subtitle">By provider</h3>
      {rows.length === 0 ? (
        <p className="empty">No LLM calls yet. Baseline methods don't use the API.</p>
      ) : (
        <table className="usage__table">
          <thead>
            <tr><th scope="col">Provider</th><th scope="col">Calls</th><th scope="col">Tokens</th><th scope="col">Avg. time</th></tr>
          </thead>
          <tbody>
            {rows.map(([name, p]) => (
              <tr key={name}>
                <th scope="row">
                  {PROVIDER_NAMES[name] ?? name}
                  <span className="usage__model">{p.models?.[0] ?? models[name]?.model ?? ""}</span>
                </th>
                <td>{fmtInt(p.requests)}{p.cached ? <span className="usage__cached"> +{p.cached} cached</span> : null}</td>
                <td>{fmtInt(p.input_tokens + p.output_tokens)}</td>
                <td>{!p.batches ? "–" : p.cached === p.batches ? "cached" : fmtSec(p.latency_s / (p.batches - p.cached))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Stat({ label, value, warn }) {
  return (
    <div className={`stat ${warn ? "stat--warn" : ""}`}>
      <dt>{label}</dt>
      <dd>{warn && <span className="stat__icon" aria-hidden="true">!</span>}{value}</dd>
    </div>
  );
}
