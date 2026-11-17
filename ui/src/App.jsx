import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, followRun } from "./api.js";
import Header from "./components/Header.jsx";
import Controls from "./components/Controls.jsx";
import Pipeline from "./components/Pipeline.jsx";
import UsagePanel from "./components/UsagePanel.jsx";
import EventsPanel from "./components/EventsPanel.jsx";
import PatternsPanel from "./components/PatternsPanel.jsx";
import Comparison from "./components/Comparison.jsx";

const EMPTY_RUN = { id: null, status: "idle", mode: null, events: [], usage: null, result: null, error: null, info: null };

export default function App() {
  const [catalog, setCatalog] = useState({ datasets: [], providers: null, replays: [], results: null });
  const [loadError, setLoadError] = useState(null);
  const [form, setForm] = useState({
    mode: "replay",
    dataset: "university",
    strategy: "llm",
    budget: 0.3,
    providers: [],
    useCache: true,
    replayId: "",
    speed: 4,
  });
  const [run, setRun] = useState(EMPTY_RUN);
  const [sessionUsage, setSessionUsage] = useState(null);
  const [startError, setStartError] = useState(null);
  const closeRef = useRef(null);

  useEffect(() => {
    Promise.all([api.datasets(), api.providers(), api.replays(), api.results()])
      .then(([datasets, providers, replays, results]) => {
        setCatalog({ datasets, providers, replays, results });
        const ready = providers.providers.filter((p) => p.configured).map((p) => p.name);
        setForm((f) => ({
          ...f,
          // With keys present, default to a real run; otherwise the recorded runs work offline.
          mode: ready.length ? "live" : "replay",
          providers: ready.length ? ready : ["mock"],
          replayId: pickReplay(replays, f.dataset, f.budget)?.id ?? "",
        }));
      })
      .catch((e) => setLoadError(e.message));
    api.usage().then(setSessionUsage).catch(() => {});
    return () => closeRef.current?.();
  }, []);

  const onEvent = useCallback((e) => {
    setRun((r) => {
      const next = { ...r, events: [...r.events, e] };
      if (e.kind === "started") next.info = e;
      if (e.kind === "usage") next.usage = e.usage;
      if (e.kind === "result") next.result = e.result;
      if (e.kind === "status") {
        next.status = e.status;
        next.error = e.error;
      }
      return next;
    });
  }, []);

  const start = async () => {
    setStartError(null);
    closeRef.current?.();
    const body =
      form.mode === "replay"
        ? { mode: "replay", replay_id: form.replayId, speed: form.speed }
        : {
            mode: "live",
            dataset: form.dataset,
            strategy: form.strategy,
            budget: form.budget,
            providers: form.providers.length ? form.providers : null,
            use_cache: form.useCache,
          };
    try {
      const created = await api.startRun(body);
      setRun({ ...EMPTY_RUN, id: created.id, status: "running", mode: created.mode });
      closeRef.current = followRun(created.id, onEvent, () => {
        api.usage().then(setSessionUsage).catch(() => {});
        // a finished live run is saved on disk and becomes replayable
        api.replays().then((replays) => setCatalog((c) => ({ ...c, replays }))).catch(() => {});
      });
    } catch (e) {
      setStartError(e.message);
    }
  };

  const cancel = async () => {
    if (run.id) await api.cancelRun(run.id).catch((e) => setStartError(e.message));
  };

  const runDataset = run.info?.dataset ?? form.dataset;
  const dataset = useMemo(
    () => catalog.datasets.find((d) => d.id === runDataset),
    [catalog.datasets, runDataset],
  );
  const running = run.status === "running" || run.status === "cancelling";

  return (
    <div className="app">
      <Header providers={catalog.providers} />
      <main className="app__main">
        {loadError && (
          <p className="notice notice--error" role="alert">
            Can't reach the API ({loadError}). Start it with <code>make ui</code> and reload.
          </p>
        )}
        <Controls
          form={form}
          setForm={setForm}
          catalog={catalog}
          running={running}
          onStart={start}
          onCancel={cancel}
          error={startError}
          pickReplay={pickReplay}
        />
        <Pipeline run={run} budget={run.info?.budget ?? form.budget} />
        <div className="board">
          <UsagePanel run={run} session={sessionUsage} providers={catalog.providers} />
          <PatternsPanel run={run} dataset={dataset} />
          <EventsPanel run={run} />
        </div>
        <Comparison
          results={catalog.results}
          dataset={runDataset}
          datasetTitle={dataset?.title}
          budget={run.info?.budget ?? form.budget}
          highlight={run.result?.recall_at_10}
        />
      </main>
      <footer className="app__footer">
        Mining and support counts come from the Hyperon Pattern Miner running on PeTTa. The LLM only
        decides the order in which candidates are checked; every pattern shown was verified by the
        miner and re-counted by the Python oracle.
      </footer>
    </div>
  );
}

function pickReplay(replays, dataset, budget) {
  // default to an evaluation run with real API calls; the user's own runs are one click away
  const pool = replays.filter((r) => r.dataset === dataset && r.source !== "dashboard");
  const real = pool.find((r) => r.label === "llm-groq-b30-r1" && Math.abs((r.budget ?? 0) - budget) < 1e-9);
  if (real) return real;
  return (
    pool.find((r) => r.strategy === "llm" && Math.abs((r.budget ?? 0) - budget) < 1e-9) ??
    pool.find((r) => r.strategy === "llm") ??
    pool[0]
  );
}
