import { PROVIDER_NAMES, STRATEGY_NAMES, familyName } from "../format.js";

const BUDGETS = [0.1, 0.2, 0.3, 0.5, 1.0];
const SPEEDS = [1, 4, 10];

export default function Controls({ form, setForm, catalog, running, onStart, onCancel, error, pickReplay }) {
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const providerList = catalog.providers?.providers ?? [];
  const replays = catalog.replays.filter((r) => r.dataset === form.dataset);
  const saved = replays.filter((r) => r.source === "dashboard");
  const recorded = replays.filter((r) => r.source !== "dashboard");
  const live = form.mode === "live";
  const llm = form.strategy.startsWith("llm");

  const changeDataset = (dataset) =>
    set({ dataset, replayId: pickReplay(catalog.replays, dataset, form.budget)?.id ?? "" });

  const toggleProvider = (name) => {
    const has = form.providers.includes(name);
    let next = has ? form.providers.filter((p) => p !== name) : [...form.providers.filter((p) => p !== "mock"), name];
    if (name === "mock") next = has ? [] : ["mock"];
    set({ providers: next });
  };

  return (
    <section className="controls" aria-label="Run settings">
      <div className="segmented" role="radiogroup" aria-label="Run type">
        {[
          ["live", "Run live"],
          ["replay", "Replay a recorded run"],
        ].map(([value, label]) => (
          <button key={value} type="button" role="radio" aria-checked={form.mode === value}
                  className={`segmented__option ${form.mode === value ? "is-on" : ""}`}
                  onClick={() => set({ mode: value })} disabled={running}>
            {label}
          </button>
        ))}
      </div>

      <div className="controls__fields">
        <label className="field">
          <span className="field__label">Dataset</span>
          <select value={form.dataset} onChange={(e) => changeDataset(e.target.value)} disabled={running}>
            {catalog.datasets.map((d) => (
              <option key={d.id} value={d.id}>{d.title}</option>
            ))}
          </select>
        </label>

        {live ? (
          <>
            <label className="field">
              <span className="field__label">Method</span>
              <select value={form.strategy} onChange={(e) => set({ strategy: e.target.value })} disabled={running}>
                {Object.entries(STRATEGY_NAMES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
            <fieldset className="field">
              <legend className="field__label">Share of candidates checked</legend>
              <div className="chips">
                {BUDGETS.map((b) => (
                  <button key={b} type="button" aria-pressed={form.budget === b}
                          className={`chip ${form.budget === b ? "is-on" : ""}`}
                          onClick={() => set({ budget: b })} disabled={running || form.strategy === "exhaustive"}>
                    {Math.round(b * 100)} %
                  </button>
                ))}
              </div>
            </fieldset>
            {llm && (
              <fieldset className="field">
                <legend className="field__label">Providers, in fallback order</legend>
                <div className="chips">
                  {providerList.map((p) => {
                    const idx = form.providers.indexOf(p.name);
                    return (
                      <button key={p.name} type="button" aria-pressed={idx >= 0}
                              className={`chip ${idx >= 0 ? "is-on" : ""}`}
                              onClick={() => toggleProvider(p.name)}
                              disabled={running || !p.configured}
                              title={p.configured ? p.model : "No API key in .env"}>
                        {idx >= 0 && <span className="chip__order">{idx + 1}</span>}
                        {PROVIDER_NAMES[p.name]}
                      </button>
                    );
                  })}
                  <button type="button" aria-pressed={form.providers.includes("mock")}
                          className={`chip ${form.providers.includes("mock") ? "is-on" : ""}`}
                          onClick={() => toggleProvider("mock")} disabled={running}>
                    Offline mock
                  </button>
                </div>
              </fieldset>
            )}
            {llm && (
              <label className="toggle">
                <input type="checkbox" checked={form.useCache} onChange={(e) => set({ useCache: e.target.checked })}
                       disabled={running} />
                <span>Reuse cached answers</span>
              </label>
            )}
          </>
        ) : (
          <>
            <label className="field field--wide">
              <span className="field__label">Recorded run</span>
              <select value={form.replayId} onChange={(e) => set({ replayId: e.target.value })} disabled={running}>
                {saved.length > 0 && (
                  <optgroup label="Your live runs">
                    {saved.map((r) => (
                      <option key={r.id} value={r.id}>{replayLabel(r)}</option>
                    ))}
                  </optgroup>
                )}
                <optgroup label="Evaluation runs">
                  {recorded.map((r) => (
                    <option key={r.id} value={r.id}>{replayLabel(r)}</option>
                  ))}
                </optgroup>
              </select>
            </label>
            <fieldset className="field">
              <legend className="field__label">Speed</legend>
              <div className="chips">
                {SPEEDS.map((s) => (
                  <button key={s} type="button" aria-pressed={form.speed === s}
                          className={`chip ${form.speed === s ? "is-on" : ""}`}
                          onClick={() => set({ speed: s })} disabled={running}>
                    {s}×
                  </button>
                ))}
              </div>
            </fieldset>
          </>
        )}
      </div>

      <div className="controls__actions">
        {running ? (
          <button type="button" className="button button--quiet" onClick={onCancel}>Stop</button>
        ) : (
          <button type="button" className="button button--primary" onClick={onStart}
                  disabled={!live && !form.replayId}>
            {live ? "Start mining" : "Play recording"}
          </button>
        )}
      </div>
      {error && <p className="notice notice--error controls__error" role="alert">{error}</p>}
    </section>
  );
}

const WHEN = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function replayLabel(r) {
  if (r.source === "dashboard") {
    const who = r.providers?.length ? ` with ${r.providers.map((p) => PROVIDER_NAMES[p] ?? p).join(", ")}` : "";
    const when = r.started ? `${WHEN.format(new Date(r.started * 1000))}: ` : "";
    return `${when}${STRATEGY_NAMES[r.strategy] ?? r.strategy}${r.strategy.startsWith("llm") ? who : ""}, ${Math.round((r.budget ?? 1) * 100)} %`;
  }
  const who = r.providers?.length ? ` with ${r.providers.map((p) => PROVIDER_NAMES[p] ?? p).join(", ")}` : "";
  const repeat = r.label.match(/-r(\d)$/);
  const seed = r.label.match(/-s(\d)$/);
  const extra = repeat ? `, repeat ${repeat[1]}` : seed ? `, seed ${seed[1]}` : "";
  const name = r.family ? familyName(r.family) : STRATEGY_NAMES[r.strategy] ?? r.strategy;
  return `${name}${r.family ? "" : who}, ${Math.round((r.budget ?? 1) * 100)} %${extra}`;
}
