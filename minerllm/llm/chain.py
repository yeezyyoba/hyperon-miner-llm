"""Provider fallback chain. Default order: Groq → NVIDIA → Gemini.

(AIRA used Gemini first. Here Gemini 3.8 Flash was repeatedly overloaded, with
180 s timeouts and 503 "high demand", while Groq answered in ~7 s, so Groq leads.
Override with MINERLLM_PROVIDERS.)

Per provider: up to ``max_retries`` retries on *retryable* errors (timeouts,
429, 5xx) with exponential backoff; on HTTP 429 we wait as long as the provider
asks ("try again in 12.3s" / Retry-After), capped at ``max_wait_s``. A non-retryable error (bad key, 400) moves
straight to the next provider. If the caller passes ``validate``, an answer that
fails validation also moves on to the next provider (a model that returns
malformed output once usually does so again, so we don't retry it). If every provider fails, ``AllProvidersFailed``
is raised, and the ranker catches it and falls back to the deterministic
heuristic. **Mining never stops because of the LLM.**
"""
from __future__ import annotations

import time

from .base import LLMClient, LLMError, LLMResponse
from .cache import DiskCache


DEFAULT_ORDER = ("groq", "nvidia", "gemini")


class AllProvidersFailed(LLMError):
    def __init__(self, attempts: list[dict]):
        super().__init__("all LLM providers failed", retryable=False)
        self.attempts = attempts


class FallbackChain(LLMClient):
    name = "chain"

    def __init__(self, clients: list[LLMClient], max_retries: int = 2, backoff_s: float = 1.0,
                 timeout_s: float = 60.0, cache: DiskCache | None = None,
                 max_wait_s: float = 65.0):
        self.clients = [c for c in clients if c.available()]
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        self.cache = cache
        self.max_wait_s = max_wait_s
        self.model = "+".join(f"{c.name}:{c.model}" for c in self.clients) or "none"

    def available(self) -> bool:
        return bool(self.clients) or self.cache is not None

    def complete(self, prompt: str, system: str = "", timeout: float | None = None,
                 validate=None) -> LLMResponse:
        ns = self.model                              # e.g. "groq+nvidia+gemini"
        if self.cache:
            hit = self.cache.get(prompt, system, ns)
            if hit and (validate is None or validate(hit.text)):
                return hit
        attempts: list[dict] = []
        for client in self.clients:
            for attempt in range(self.max_retries + 1):
                start = time.time()
                try:
                    resp = client.complete(prompt, system, timeout or self.timeout_s)
                except LLMError as e:
                    attempts.append({"provider": client.name, "attempt": attempt + 1,
                                     "error": str(e)[:200], "seconds": round(time.time() - start, 2)})
                    if not e.retryable:
                        break
                    if attempt < self.max_retries:
                        wait = self.backoff_s * (2 ** attempt)
                        if getattr(e, "retry_after", None):
                            wait = max(wait, min(e.retry_after + 0.5, self.max_wait_s))
                        attempts[-1]["waited_s"] = round(wait, 2)
                        time.sleep(wait)
                    continue
                if validate is not None and not validate(resp.text):
                    attempts.append({"provider": client.name, "attempt": attempt + 1,
                                     "error": "answer failed validation",
                                     "seconds": round(time.time() - start, 2)})
                    break                       # next provider
                attempts.append({"provider": client.name, "attempt": attempt + 1, "ok": True,
                                 "seconds": round(time.time() - start, 2)})
                resp.attempts = attempts
                if self.cache:
                    self.cache.put(prompt, system, resp, ns)
                return resp
        raise AllProvidersFailed(attempts)


def load_env() -> None:
    """Load API keys from the repository's .env, by explicit path.

    Auto-discovery (``load_dotenv()`` with no path) is unreliable when this code runs in
    Python embedded in PeTTa (SWI-Prolog/janus) from a run directory: there the keys were
    silently not found and every LLM call fell back. Variables already set win.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def build_chain(providers: list[str] | None = None, cache_dir: str | None = None,
                max_retries: int = 2, timeout_s: float = 60.0) -> FallbackChain:
    """Build the chain from provider names: gemini, groq, nvidia, mock[:fault]."""
    from .mock import MockLLM
    from .providers import GeminiClient, groq_client, nvidia_client

    load_env()

    import os
    env_order = os.environ.get("MINERLLM_PROVIDERS", "")
    providers = providers or [p.strip() for p in env_order.split(",") if p.strip()] \
        or list(DEFAULT_ORDER)
    clients: list[LLMClient] = []
    for p in providers:
        if p == "gemini":
            clients.append(GeminiClient())
        elif p == "groq":
            clients.append(groq_client())
        elif p == "nvidia":
            clients.append(nvidia_client())
        elif p.startswith("mock"):
            fault = p.split(":", 1)[1] if ":" in p else None
            clients.append(MockLLM(name=p, fault=fault))
        else:
            raise ValueError(f"unknown provider {p!r}")
    cache = DiskCache(cache_dir) if cache_dir else None
    return FallbackChain(clients, max_retries=max_retries, timeout_s=timeout_s, cache=cache)
