"""Dashboard API: usage accounting, replays, live runs (with a fake miner), SSE, safety.

No PeTTa and no network: replays read a small recorded trace written to a temp dir,
and the live path runs a stand-in process that writes a trace and a result file the
way ``minerllm guided`` does.
"""
from __future__ import annotations

import json
import sys
import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from minerllm.api import catalog, runs  # noqa: E402
from minerllm.api.app import create_app  # noqa: E402
from minerllm.api.runs import RunManager  # noqa: E402
from minerllm.api.usage import add_usage, summarize_usage  # noqa: E402
from minerllm.patterns import canonical  # noqa: E402

PLANTED = "(, (ADVISED_BY $s $p) (MEMBER_OF $p $d) (MAJORS_IN $s $d))"
OTHER = "(, (USES $v0 $v1) (USES $v0 $v2))"
PLANTED_CANON = canonical(PLANTED)

BATCH_OK = {"level": 0, "kind": "joins", "size": 60, "provider": "groq", "model": "openai/gpt-oss-120b",
            "cached": False, "input_tokens": 1000, "output_tokens": 500, "latency_s": 2.0,
            "attempts": [{"provider": "groq", "attempt": 1, "error": "429 rate limited",
                          "seconds": 0.3, "waited_s": 4.0},
                         {"provider": "groq", "attempt": 2, "ok": True, "seconds": 2.0}]}
BATCH_CACHED = {"level": 0, "kind": "joins", "size": 60, "provider": "nvidia", "model": "m",
                "cached": True, "input_tokens": 900, "output_tokens": 400, "latency_s": 0.0,
                "attempts": []}
BATCH_FALLBACK = {"level": 0, "kind": "joins", "size": 10, "fallback": True,
                  "reason": "llm unavailable", "attempts": [
                      {"provider": "groq", "attempt": 1, "error": "boom", "seconds": 0.1}]}

TRACE = [
    {"t": 0.0, "event": "configure", "strategy": "llm", "budget": 0.3, "providers": ["groq"]},
    {"t": 1.0, "event": "llm_batch", "batch": 1, "of": 3, "provider": "groq", "model": "x",
     "cached": False, "seconds": 1.0},
    {"t": 1.5, "event": "llm_batch", "batch": 2, "of": 3, "provider": "nvidia", "model": "m",
     "cached": True, "seconds": 0.0},
    {"t": 2.0, "event": "llm_batch", "batch": 3, "of": 3, "failed": "boom", "seconds": 0.1},
    {"t": 2.1, "event": "select", "level": 0, "generated": 100, "unique": 80, "selected": 24,
     "strategy": "llm", "llm_seconds": 2.0, "top_joins": [["A.arg1 = B.arg1", 9.0]],
     "batches": [BATCH_OK, BATCH_CACHED, BATCH_FALLBACK], "selected_patterns": [OTHER] * 20},
    {"t": 2.5, "event": "verify", "level": 0, "kept": 2, "seconds": 0.4},
    {"t": 3.0, "event": "finish", "wall_seconds": 3.0, "generated": 100, "unique": 80,
     "selected": 24, "kept": 2, "llm_seconds": 2.0, "input_tokens": 1900, "output_tokens": 900,
     "fallback_batches": 1, "batches": 3},
]


def record(patterns=(PLANTED_CANON, OTHER)) -> dict:
    return {"label": "llm-b30", "ok": True, "seconds": 3.0, "n_patterns": len(patterns),
            "patterns": [{"pattern": p, "support": 20 + i, "surprisingness": 0.9 - i * 0.5}
                         for i, p in enumerate(patterns)],
            "verification": {"checked": 0, "ok": True, "mismatches": []},
            "ranker": {"strategy": "llm", "budget": 0.3, "providers": ["groq"]},
            "trace_summary": {"generated": 100, "unique": 80, "selected": 24, "kept": 2}}


@pytest.fixture()
def raw(tmp_path, monkeypatch):
    ds = tmp_path / "raw" / "university"
    ds.mkdir(parents=True)
    (ds / "llm-groq-b30.trace.jsonl").write_text("\n".join(json.dumps(e) for e in TRACE) + "\n")
    (ds / "llm-groq-b30.json").write_text(json.dumps(record()))
    (ds / "reference.json").write_text(json.dumps({"patterns": {
        PLANTED_CANON: {"support": 20, "score": 0.9}, OTHER: {"support": 21, "score": 0.4}}}))
    monkeypatch.setattr(catalog, "RAW", tmp_path / "raw")
    monkeypatch.setattr(catalog, "SAVED_RUNS", tmp_path / "runs")
    return tmp_path


def wait_done(client, run_id, timeout=20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/runs/{run_id}").json()
        if r["status"] in ("done", "failed", "cancelled"):
            return r
        time.sleep(0.05)
    raise AssertionError("run did not finish")


# ------------------------------------------------------------------ usage accounting


def test_usage_counts_requests_tokens_cache_retries_and_cost():
    u = summarize_usage(TRACE)
    groq, nvidia = u["providers"]["groq"], u["providers"]["nvidia"]
    assert groq["requests"] == 3 and groq["failed"] == 2 and groq["retries"] == 1
    assert groq["rate_limit_wait_s"] == 4.0
    assert groq["input_tokens"] == 1000 and groq["output_tokens"] == 500
    assert groq["cost_usd"] == pytest.approx(1000 / 1e6 * 0.15 + 500 / 1e6 * 0.60)
    assert nvidia["cached"] == 1 and nvidia["requests"] == 0 and nvidia["cost_usd"] == 0
    assert u["fallback_batches"] == 1
    assert u["batches_answered"] == 3 and u["batches_total"] == 3
    assert u["totals"]["input_tokens"] == 1900


def test_usage_progress_before_select_and_session_sum():
    early = summarize_usage(TRACE[:2])
    assert early["batches_answered"] == 1 and early["batches_total"] == 3
    assert early["totals"]["requests"] == 0               # tokens arrive with the select event
    both = add_usage(summarize_usage(TRACE), summarize_usage(TRACE))
    assert both["totals"]["input_tokens"] == 3800
    assert both["providers"]["groq"]["requests"] == 6


# ------------------------------------------------------------------ catalog


def test_datasets_list_planted_patterns():
    ds = {d["id"]: d for d in catalog.list_datasets()}
    assert {"university", "university-anon", "galaxy400"} <= set(ds)
    assert len(ds["university"]["planted"]) == 3
    assert ds["galaxy400"]["planted"] == []


def test_provider_status_never_returns_key_values(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-very-secret-value")
    client = TestClient(create_app(RunManager()))
    body = client.get("/api/providers").text
    assert "gsk-very-secret-value" not in body
    groq = next(p for p in json.loads(body)["providers"] if p["name"] == "groq")
    assert groq["configured"] is True


def test_replay_ids_cannot_escape_results_dir(raw):
    for bad in ("../../etc/passwd", "university/../x", "nope/llm", "university/.hidden", "university/"):
        with pytest.raises(KeyError):
            catalog.replay_paths(bad)


def test_result_marks_planted_and_reference_top10(raw):
    res = catalog.build_result(raw / "raw" / "university" / "llm-groq-b30.json", "university")
    top = res["patterns"][0]
    assert top["pattern"] == PLANTED_CANON and top["planted"] == "P1_major_in_advisor_dept"
    assert top["top10"] is True
    assert res["planted_found"] == ["P1_major_in_advisor_dept"] and res["planted_total"] == 3
    assert res["recall_at_10"] == 1.0


# ------------------------------------------------------------------ runs over HTTP


def test_replay_streams_events_and_result(raw):
    client = TestClient(create_app(RunManager()))
    assert any(r["id"] == "university/llm-groq-b30" for r in client.get("/api/replays").json())
    run = client.post("/api/runs", json={"mode": "replay", "replay_id": "university/llm-groq-b30",
                                         "speed": 0}).json()
    done = wait_done(client, run["id"])
    assert done["status"] == "done" and done["strategy"] == "llm"
    assert done["result"]["planted_found"] == ["P1_major_in_advisor_dept"]
    assert done["usage"]["totals"]["input_tokens"] == 1900

    with client.stream("GET", f"/api/runs/{run['id']}/events") as s:
        text = "".join(s.iter_text())
    kinds = [l.split(": ", 1)[1] for l in text.splitlines() if l.startswith("event: ")]
    assert kinds[0] == "started" and kinds[-1] == "end"
    assert {"llm_batch", "select", "verify", "finish", "usage", "result", "status"} <= set(kinds)
    select = next(json.loads(l[6:]) for l in text.splitlines()
                  if l.startswith("data: ") and '"kind": "select"' in l)
    assert "batches" not in select and len(select["selected_sample"]) == 8

    # resume after a sequence number (reconnecting browser)
    with client.stream("GET", f"/api/runs/{run['id']}/events?after=3") as s:
        first = next(l for l in s.iter_lines() if l.startswith("id: "))
    assert first == "id: 4"
    # replays don't count towards the session's API usage
    assert client.get("/api/usage").json()["totals"]["requests"] == 0


FAKE_MINER = r"""
import json, sys, time, pathlib
out = pathlib.Path(sys.argv[1])
trace = out / "llm-b30.trace.jsonl"
events = json.loads(sys.argv[2])
with trace.open("w") as fh:
    for e in events:
        fh.write(json.dumps(e) + "\n"); fh.flush(); time.sleep(0.02)
print("loading dataset", flush=True)
print("(surprisingnessOf (, (A $x)) 0.5)", flush=True)
(out / "llm-b30.run.json").write_text("{}")
(out / "llm-b30.json").write_text(sys.argv[3])
sys.exit(int(sys.argv[4]))
"""


def fake_command(exit_code=0):
    def cmd(req, out_dir):
        return [sys.executable, "-c", FAKE_MINER, str(out_dir), json.dumps(TRACE),
                json.dumps(record()), str(exit_code)]
    return cmd


def test_live_run_streams_trace_and_counts_session_usage(raw):
    client = TestClient(create_app(RunManager(command=fake_command())))
    run = client.post("/api/runs", json={"mode": "live", "dataset": "university",
                                         "strategy": "llm", "budget": 0.3}).json()
    done = wait_done(client, run["id"])
    assert done["status"] == "done", done["error"]
    assert done["result"]["n_patterns"] == 2
    assert client.get("/api/usage").json()["totals"]["input_tokens"] == 1900
    with client.stream("GET", f"/api/runs/{run['id']}/events") as s:
        text = "".join(s.iter_text())
    logs = [json.loads(l[6:])["line"] for l in text.splitlines()
            if l.startswith("data: ") and '"kind": "log"' in l]
    assert logs == ["loading dataset"]                    # pattern dumps are not streamed


def test_live_run_failure_is_reported(raw):
    client = TestClient(create_app(RunManager(command=fake_command(exit_code=3))))
    run = client.post("/api/runs", json={"mode": "live"}).json()
    done = wait_done(client, run["id"])
    assert done["status"] == "failed" and "code 3" in done["error"]


def test_live_command_matches_the_cli(raw):
    req = runs.RunRequest(dataset="university", strategy="llm", budget=0.3,
                          providers=["groq", "nvidia"], use_cache=False)
    cmd = runs.live_command(req, raw / "out")
    assert cmd[1:4] == ["-m", "minerllm", "guided"]
    assert "--providers" in cmd and cmd[cmd.index("--providers") + 1] == "groq,nvidia"
    assert "--no-cache" in cmd and cmd[cmd.index("--config") + 1] == "configs/university.yaml"


@pytest.mark.parametrize("body,code", [
    ({"mode": "live", "dataset": "nope"}, 404),
    ({"mode": "live", "strategy": "magic"}, 422),
    ({"mode": "live", "budget": 0}, 422),
    ({"mode": "live", "providers": ["groq; rm -rf /"]}, 422),
    ({"mode": "replay", "replay_id": "../secrets"}, 404),
    ({"mode": "teleport"}, 422),
])
def test_bad_requests_are_rejected(raw, body, code):
    client = TestClient(create_app(RunManager(command=fake_command())))
    assert client.post("/api/runs", json=body).status_code == code


def test_only_one_live_miner_at_a_time(raw):
    slow = r"import time; time.sleep(5)"
    mgr = RunManager(command=lambda req, out: [sys.executable, "-c", slow])
    client = TestClient(create_app(mgr))
    first = client.post("/api/runs", json={"mode": "live"}).json()
    assert client.post("/api/runs", json={"mode": "live"}).status_code == 409
    client.post(f"/api/runs/{first['id']}/cancel")
    assert wait_done(client, first["id"])["status"] == "cancelled"


def test_live_runs_are_saved_and_replayable_after_a_restart(raw):
    client = TestClient(create_app(RunManager(command=fake_command())))
    run = client.post("/api/runs", json={"mode": "live", "dataset": "university",
                                         "strategy": "llm", "budget": 0.3}).json()
    assert wait_done(client, run["id"])["status"] == "done"

    # a fresh app = the backend restarted: no runs in memory, the files are still on disk
    fresh = TestClient(create_app(RunManager(command=fake_command())))
    assert fresh.get("/api/runs").json() == []
    saved = [r for r in fresh.get("/api/replays").json() if r.get("source") == "dashboard"]
    assert len(saved) == 1 and saved[0]["id"] == f"saved/ui-{run['id']}"
    assert saved[0]["dataset"] == "university" and saved[0]["strategy"] == "llm"

    replay = fresh.post("/api/runs", json={"mode": "replay", "replay_id": saved[0]["id"],
                                           "speed": 0}).json()
    done = wait_done(fresh, replay["id"])
    assert done["status"] == "done" and done["result"]["n_patterns"] == 2
    assert done["usage"]["totals"]["input_tokens"] == 1900


def test_saved_run_ids_cannot_escape_runs_dir(raw):
    for bad in ("saved/../results", "saved/ui-x/../../etc", "saved/notui", "saved/", "saved/ui-missing"):
        with pytest.raises(KeyError):
            catalog.replay_paths(bad)


def test_stale_ui_build_is_detected(tmp_path):
    import os
    from minerllm.api.app import ui_build_is_stale
    src, dist = tmp_path / "ui", tmp_path / "ui" / "dist"
    (src / "src").mkdir(parents=True)
    dist.mkdir()
    (src / "src" / "styles.css").write_text("a{}")
    (dist / "index.html").write_text("<html>")
    os.utime(src / "src" / "styles.css", (1000, 1000))
    os.utime(dist / "index.html", (2000, 2000))
    assert ui_build_is_stale(src, dist) is None
    os.utime(src / "src" / "styles.css", (3000, 3000))      # edited after the build
    assert ui_build_is_stale(src, dist) == "ui/src/styles.css"


def test_heldout_datasets_are_listed_and_replayable():
    ds = {d["id"]: d for d in catalog.list_datasets()}
    assert ds["heldout-galaxy400-s11"]["heldout"] is True and ds["university"]["heldout"] is False
    assert len(ds["heldout-university-s1"]["planted"]) == 3
    ids = {r["id"] for r in catalog.list_replays()}
    assert "heldout-galaxy400-s11/llm-hybrid-groq-b30" in ids
    ds_id, trace, rec = catalog.replay_paths("heldout-galaxy400-s11/llm-hybrid-groq-b30")
    assert ds_id == "heldout-galaxy400-s11" and trace.exists() and rec.exists()


def test_results_carry_step7_separately_from_the_preregistered_rows():
    r = catalog.results_summary()
    assert not any(x["family"].startswith("llm-hybrid") for x in r["rows"])
    assert any(x["family"] == "llm-hybrid:groq" for x in r["exploratory"])
    assert r["exploratory_checks"]["heldout-galaxy400-s11 / llm-hybrid:groq"]["heldout"] is True


def test_runs_where_no_llm_answered_are_not_offered_as_replays(raw):
    dead = record()
    dead["trace_summary"] = {"batches": 3, "fallback_batches": 3}
    (raw / "raw" / "university" / "llm-dead-b30.json").write_text(json.dumps(dead))
    (raw / "raw" / "university" / "llm-dead-b30.trace.jsonl").write_text("\n".join(json.dumps(e) for e in TRACE))
    ids = {r["id"] for r in catalog.list_replays()}
    assert "university/llm-groq-b30" in ids and "university/llm-dead-b30" not in ids
