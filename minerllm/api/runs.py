"""Runs started from the dashboard: live (the real CLI) or replayed (a recorded trace).

Each run keeps an append-only list of events. The SSE endpoint reads from it by
sequence number, so several browser tabs (or a reconnect) see the same stream.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..config import ROOT, RankerConfig
from . import catalog
from .usage import add_usage, summarize_usage

FINAL = {"done", "failed", "cancelled"}
_PROGRESS_LINE = re.compile(r"^\[\s*[\d.]+s\]")      # the CLI's own trace echo; we stream the trace itself
_ALLOWED_PROVIDERS = {"groq", "nvidia", "gemini", "mock", "mock:garbage", "mock:error", "mock:fatal"}


@dataclass
class RunRequest:
    mode: str = "live"                    # live | replay
    dataset: str = "university"
    strategy: str = "llm"
    budget: float = 0.3
    providers: Optional[list] = None      # None -> MINERLLM_PROVIDERS / default order
    use_cache: bool = True
    replay_id: Optional[str] = None
    speed: float = 4.0                    # replay: how many times faster than recorded

    def validate(self) -> None:
        if self.mode not in ("live", "replay"):
            raise ValueError("mode must be 'live' or 'replay'")
        if self.mode == "replay":
            catalog.replay_paths(self.replay_id or "")       # KeyError if unknown
            if not 0 <= self.speed <= 100:
                raise ValueError("speed must be between 0 and 100")
            return
        catalog.config_for(self.dataset)                     # KeyError if unknown
        RankerConfig(strategy=self.strategy, budget=self.budget)   # ValueError if invalid
        for p in self.providers or []:
            if p not in _ALLOWED_PROVIDERS:
                raise ValueError(f"unknown provider {p!r}")


@dataclass
class Run:
    id: str
    request: RunRequest
    dataset: str
    status: str = "running"
    started: float = field(default_factory=time.time)
    finished: Optional[float] = None
    events: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None
    usage: dict = field(default_factory=lambda: summarize_usage([]))
    out_dir: Optional[Path] = None
    proc: Optional[subprocess.Popen] = None
    trace_lines: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    # ----------------------------------------------------------------- events
    def emit(self, kind: str, **data) -> None:
        with self.lock:
            self.events.append({"seq": len(self.events), "kind": kind,
                                "at": round(time.time() - self.started, 3), **data})

    def add_trace(self, e: dict) -> None:
        """Forward one trace event (trimmed for the browser) and refresh usage."""
        self.trace.append(e)
        ev = dict(e)
        kind = ev.pop("event", "trace")
        if kind == "select":
            sel = ev.pop("selected_patterns", None) or []
            ev["selected_sample"] = sel[:8]
            ev.pop("batches", None)
        self.emit(kind, **ev)
        if kind in ("llm_batch", "select", "finish"):
            self.usage = summarize_usage(self.trace)
            self.emit("usage", usage=self.usage)

    def finish(self, status: str, error: Optional[str] = None) -> None:
        self.status, self.error, self.finished = status, error, time.time()
        self.emit("status", status=status, error=error,
                  seconds=round(self.finished - self.started, 2))

    def summary(self) -> dict:
        r = self.request
        return {"id": self.id, "mode": r.mode, "dataset": self.dataset, "strategy": r.strategy,
                "budget": r.budget, "providers": r.providers, "replay_id": r.replay_id,
                "status": self.status, "error": self.error, "started": self.started,
                "finished": self.finished, "events": len(self.events), "usage": self.usage,
                "result": self.result}


def live_command(req: RunRequest, out_dir: Path) -> list[str]:
    """The exact CLI invocation a live run executes (shown in the UI as well)."""
    cmd = [sys.executable, "-m", "minerllm", "guided", "--config", str(catalog.ALL_DATASETS[req.dataset]),
           "--strategy", req.strategy, "--budget", str(req.budget), "--top", "0",
           "--out", str(out_dir)]
    if req.providers:
        cmd += ["--providers", ",".join(req.providers)]
    if not req.use_cache:
        cmd.append("--no-cache")
    return cmd


class RunManager:
    """Holds runs in memory; at most one live miner process at a time."""

    def __init__(self, command: Callable[[RunRequest, Path], list] = live_command):
        self.command = command
        self.runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ public
    def start(self, req: RunRequest) -> Run:
        req.validate()
        with self._lock:
            busy = [r for r in self.runs.values() if r.status == "running" and r.request.mode == "live"]
            if req.mode == "live" and busy:
                raise RuntimeError(f"run {busy[0].id} is still mining; cancel it or wait")
            run_id = time.strftime("%H%M%S-") + uuid.uuid4().hex[:6]
            dataset = req.dataset if req.mode == "live" else catalog.replay_paths(req.replay_id)[0]
            if req.mode == "replay":
                req.dataset = dataset
            run = Run(id=run_id, request=req, dataset=dataset)
            self.runs[run_id] = run
        target = self._live if req.mode == "live" else self._replay
        threading.Thread(target=target, args=(run,), daemon=True).start()
        return run

    def get(self, run_id: str) -> Run:
        return self.runs[run_id]

    def cancel(self, run_id: str) -> Run:
        run = self.runs[run_id]
        if run.status != "running":
            return run
        run.status = "cancelling"
        if run.proc and run.proc.poll() is None:
            try:                                   # the miner spawns PeTTa: stop the whole group
                os.killpg(run.proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, AttributeError):
                run.proc.terminate()
        return run

    def session_usage(self) -> dict:
        total = summarize_usage([])
        for r in self.runs.values():
            if r.request.mode == "live":
                total = add_usage(total, r.usage)
        return total

    # ------------------------------------------------------------------ live
    def _live(self, run: Run) -> None:
        req = run.request
        run.out_dir = (catalog.SAVED_RUNS / f"ui-{run.id}").resolve()
        run.out_dir.mkdir(parents=True, exist_ok=True)
        # Recorded next to the CLI's own files so the run can be replayed after a restart.
        (run.out_dir / catalog.SAVED_META).write_text(json.dumps({
            "dataset": run.dataset, "strategy": req.strategy, "budget": req.budget,
            "providers": req.providers, "use_cache": req.use_cache, "started": run.started}, indent=2))
        cmd = self.command(req, run.out_dir)
        shown = ["minerllm"] + [str(c) for c in cmd[3:]] if cmd[1:3] == ["-m", "minerllm"] else cmd
        run.emit("started", mode="live", dataset=run.dataset, strategy=req.strategy,
                 budget=req.budget, command=" ".join(str(c) for c in shown))
        try:
            run.proc = subprocess.Popen(
                [str(c) for c in cmd], cwd=str(ROOT), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                start_new_session=(os.name == "posix"))
        except OSError as e:
            run.finish("failed", f"could not start the miner: {e}")
            return

        tail_stop = threading.Event()
        tailer = threading.Thread(target=self._tail_traces, args=(run, tail_stop), daemon=True)
        tailer.start()
        log_tail: list[str] = []
        assert run.proc.stdout is not None
        for line in run.proc.stdout:
            line = line.rstrip()
            if not line or _PROGRESS_LINE.match(line):
                continue
            log_tail = (log_tail + [line])[-40:]
            if not line.startswith("(") and len(line) < 400:   # skip pattern dumps
                run.emit("log", line=line)
        code = run.proc.wait()
        tail_stop.set()
        tailer.join(timeout=5)
        self._drain_traces(run)

        if run.status == "cancelling":
            run.finish("cancelled")
            return
        # the miner's record sits next to its trace (not dashboard.json or *.run.json)
        files = catalog._saved_files(run.out_dir)
        records = [files[1]] if files else []
        if records:
            try:
                run.result = catalog.build_result(records[0], run.dataset)
                run.emit("result", result=run.result)
            except Exception as e:      # noqa: BLE001 - report, don't crash the server
                run.finish("failed", f"could not read the run output: {e}")
                return
        if code == 0 and records:
            run.finish("done")
        else:
            reason = next((l for l in reversed(log_tail) if "error" in l.lower()), None)
            run.finish("failed", reason or f"miner exited with code {code}")

    def _trace_files(self, run: Run) -> list[Path]:
        return sorted(run.out_dir.glob("*.trace.jsonl")) if run.out_dir else []

    def _drain_traces(self, run: Run) -> None:
        seen = run.trace_lines
        for f in self._trace_files(run)[:1]:
            lines = f.read_text().splitlines()
            for line in lines[seen:]:
                if not line.strip():
                    continue
                try:
                    run.add_trace(json.loads(line))
                except json.JSONDecodeError:
                    break                          # half-written line: read it next time
                seen += 1
        run.trace_lines = seen

    def _tail_traces(self, run: Run, stop: threading.Event) -> None:
        while not stop.wait(0.4):
            self._drain_traces(run)

    # ------------------------------------------------------------------ replay
    def _replay(self, run: Run) -> None:
        req = run.request
        ds, trace_path, record_path = catalog.replay_paths(req.replay_id)
        meta = next((r for r in catalog.list_replays() if r["id"] == req.replay_id), {})
        req.strategy = meta.get("strategy") or req.strategy
        req.budget = meta.get("budget") or req.budget
        req.providers = meta.get("providers") or None
        run.emit("started", mode="replay", dataset=ds, strategy=req.strategy, budget=req.budget,
                 command=f"replay of results/raw/{req.replay_id} at {req.speed:g}x")
        events = [json.loads(l) for l in trace_path.read_text().splitlines() if l.strip()]
        prev = 0.0
        for e in events:
            if run.status == "cancelling":
                run.finish("cancelled")
                return
            t = float(e.get("t") or 0.0)
            if req.speed > 0:
                time.sleep(min(max(t - prev, 0.0) / req.speed, 2.5))
            prev = t
            run.add_trace(e)
        run.result = catalog.build_result(record_path, ds)
        run.emit("result", result=run.result)
        run.finish("done")
