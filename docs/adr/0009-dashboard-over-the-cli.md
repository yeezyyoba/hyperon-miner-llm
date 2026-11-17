# ADR 0009 — A dashboard that wraps the CLI and replays recorded traces

**Status:** accepted

**Context.** The CLI is the real interface and stays that way: every result in Step 6
comes from `make` targets. But a terminal is a poor way to show a live audience what
the system does while it runs: which provider answered, how many tokens it cost, how
the candidate set shrinks level by level, and which patterns came out. The presentation
also runs on a network we don't control, and Groq's free tier rate-limits bursts.

**Decision.**
* A FastAPI service (`minerllm/api`) and a React page (`ui/`), started with `make ui`.
* **Live runs execute the exact CLI command** (`python -m minerllm guided ...`) as a
  subprocess and stream the execution trace the bridge already writes. The API adds no
  mining, ranking or scoring logic of its own, so the dashboard cannot disagree with
  the evaluation. The command is shown in the events panel.
* **Replays** stream a recorded trace from `results/raw/` at 1×, 4× or 10× and then
  load that run's result file. They need no keys and no network, so the demo cannot be
  broken by an outage or a rate limit.
* Server-Sent Events, not WebSockets: data only flows from server to browser.
* One live miner at a time (PeTTa is CPU-heavy); the process group is stopped on cancel.
* Usage is computed from trace events by pure functions (`api/usage.py`) using the same
  price table as the evaluation. API keys are only checked for presence.

**Consequences.** One more dependency group (FastAPI, uvicorn; Node only to build the
page). Pattern meaning (planted, reference top 10, recall@10) is computed with the same
canonical form and tie-aware top-k as `evaluate.py`. The UI is covered by API tests with
a stand-in miner process (`tests/test_api.py`), not by browser tests.
