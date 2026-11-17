"""FastAPI app:  ``uvicorn minerllm.api.app:app``  (or ``make ui``).

Endpoints (all JSON unless noted):

    GET  /api/health
    GET  /api/datasets              datasets, sizes, planted patterns
    GET  /api/providers             which providers have a key (true/false), model, price
    GET  /api/replays               recorded runs that can be replayed offline
    GET  /api/results               evaluation summary and verdicts (make report)
    GET  /api/usage                 API usage summed over this session's live runs
    POST /api/runs                  start a live run or a replay
    GET  /api/runs                  runs started in this session
    GET  /api/runs/{id}             one run: status, usage, result
    GET  /api/runs/{id}/events      Server-Sent Events: the run's events from ?after=<seq>
    POST /api/runs/{id}/cancel      stop a run

If ``ui/dist`` exists (``make ui-build``), the built dashboard is served at ``/``.
"""
from __future__ import annotations

import asyncio
import json
import warnings
from pathlib import Path
from typing import List, Optional

warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from ..config import ROOT  # noqa: E402
from . import catalog  # noqa: E402
from .runs import FINAL, RunManager, RunRequest  # noqa: E402

UI_DIST = ROOT / "ui" / "dist"


class RunBody(BaseModel):
    mode: str = Field("live", description="live | replay")
    dataset: str = "university"
    strategy: str = "llm"
    budget: float = 0.3
    providers: Optional[List[str]] = None
    use_cache: bool = True
    replay_id: Optional[str] = None
    speed: float = 4.0


def ui_build_is_stale(src: Path = ROOT / "ui", dist: Path = UI_DIST) -> Optional[str]:
    """Name of a UI source file edited after the last build, or None if the build is current."""
    index = dist / "index.html"
    if not index.exists():
        return None
    built = index.stat().st_mtime
    candidates = [src / "index.html", src / "package.json"] + list((src / "src").rglob("*"))
    for f in candidates:
        if f.is_file() and f.stat().st_mtime > built + 1:
            return str(f.relative_to(src.parent))
    return None


def create_app(manager: Optional[RunManager] = None) -> FastAPI:
    app = FastAPI(title="hyperon-miner-llm", version="0.1.0",
                  description="Live dashboard API for the LLM-guided Hyperon Pattern Miner")
    app.state.runs = manager or RunManager()
    # The Vite dev server runs on another port during development.
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/datasets")
    def datasets():
        return catalog.list_datasets()

    @app.get("/api/providers")
    def providers():
        return catalog.provider_status()

    @app.get("/api/replays")
    def replays():
        return catalog.list_replays()

    @app.get("/api/results")
    def results():
        return catalog.results_summary()

    @app.get("/api/usage")
    def usage():
        return app.state.runs.session_usage()

    @app.get("/api/runs")
    def list_runs():
        return [r.summary() for r in sorted(app.state.runs.runs.values(), key=lambda r: -r.started)]

    @app.post("/api/runs", status_code=201)
    def start_run(body: RunBody):
        try:
            data = body.model_dump() if hasattr(body, "model_dump") else body.dict()
            run = app.state.runs.start(RunRequest(**data))
        except KeyError as e:
            raise HTTPException(404, f"unknown dataset or recorded run: {e}") from None
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from None
        return run.summary()

    def _run(run_id: str):
        try:
            return app.state.runs.get(run_id)
        except KeyError:
            raise HTTPException(404, f"no run {run_id}") from None

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return _run(run_id).summary()

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        _run(run_id)
        return app.state.runs.cancel(run_id).summary()

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = -1):
        run = _run(run_id)

        async def stream():
            seq = after + 1
            idle = 0.0
            while True:
                batch = run.events[seq:]
                for e in batch:
                    yield f"id: {e['seq']}\nevent: {e['kind']}\ndata: {json.dumps(e)}\n\n"
                seq += len(batch)
                if run.status in FINAL and seq >= len(run.events):
                    yield "event: end\ndata: {}\n\n"
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.15)
                idle = 0.0 if batch else idle + 0.15
                if idle >= 15:                     # keep proxies from closing the stream
                    idle = 0.0
                    yield ": keep-alive\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    if UI_DIST.exists():
        stale = ui_build_is_stale()
        if stale:
            warnings.warn(f"ui/dist is older than {stale}: the page you see is out of date. "
                          "Run `make ui` (or `make ui-build`) to rebuild it.", stacklevel=2)
        app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = (UI_DIST / path).resolve()
            if path and f.is_file() and UI_DIST.resolve() in f.parents:
                return FileResponse(f)
            if "." in path.rsplit("/", 1)[-1] or path.startswith("api/"):
                raise HTTPException(404, "not found")     # a missing file, not a page
            # index.html names the hashed asset files: never let the browser keep an old one
            return FileResponse(UI_DIST / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
