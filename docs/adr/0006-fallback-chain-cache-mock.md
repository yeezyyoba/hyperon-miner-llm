# ADR 0006 — Gemini → Groq → NVIDIA, disk cache, offline mock

**Status:** accepted

**Context.** Hosted LLMs fail: rate limits, outages, malformed answers. Evaluation runs must
be repeatable, and CI has no API keys.

**Decision.**
* **Chain:** Gemini, then Groq, then NVIDIA (same order as AIRA). Up to 2 retries with
  exponential backoff on retryable errors. A fatal error or an answer that fails validation
  moves to the next provider. If all fail, the batch uses the heuristic order.
* **Cache:** answers are stored by `sha256(system + prompt)`. A re-run replays the same
  scores at zero cost; invalid cached answers are never replayed.
* **Mock:** `MockLLM` parses the prompt and answers in the expected format, with fault modes
  (`garbage`, `partial`, `out_of_range`, `duplicates`, `error`, `fatal`, …) to test every failure
  path. Its scores are hash-based, so mock runs test plumbing, never quality.
* Default models: `gemini-3.8-flash` (thinking level `low`), `openai/gpt-oss-120b` (Groq),
  `minimaxai/minimax-m3.1-flash` (NVIDIA), all overridable in `.env`; the order is overridable
  with `MINERLLM_PROVIDERS` (models are checked with `minerllm models --probe`: the original Llama defaults, and
  then NVIDIA's mistral-large-2, were retired during this project, and NVIDIA's model
  list still includes retired models, so being listed doesn't mean a model answers). JSON mode; temperature 0
  where honoured (Gemini 3.x ignores sampling parameters). Keys come only from the environment
  and are sent in headers, never in URLs.

**Consequences.** Mining never stops because of the LLM. CI runs the full pipeline offline.
Results state which provider answered each batch (in the trace).
