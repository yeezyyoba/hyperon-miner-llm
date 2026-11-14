"""Deterministic offline LLM, used for CI, demos and failure injection.

``MockLLM`` reads the candidate list out of the ranking prompt and answers in the
expected JSON format, so the whole pipeline runs with no network and no keys.

Its scores are **not** smart. They come from a seeded hash of each candidate's
text, so a mock run tests plumbing, never quality. Quality claims come only
from real-provider runs (docs/06-results.md).

Fault modes (``MockLLM(fault=...)``) exercise every failure path of the validator
and the chain:

    garbage        not JSON at all
    fenced         valid JSON wrapped in ```json fences (must be accepted)
    out_of_range   ids that don't exist + a valid subset
    duplicates     every id listed twice with different scores
    partial        scores only the first third of the candidates
    wrong_schema   valid JSON, wrong keys
    error          raises a retryable LLMError (provider down)
    fatal          raises a non-retryable LLMError (bad key)
"""
from __future__ import annotations

import hashlib
import json
import re
import time

from .base import LLMClient, LLMError, LLMResponse

_ID_LINE = re.compile(r"^\s*\[(\d+)\]\s+(.*)$", re.M)


class MockLLM(LLMClient):
    def __init__(self, name: str = "mock", fault: str | None = None, seed: int = 0,
                 latency_s: float = 0.0, fail_times: int = 0):
        self.name = name
        self.model = f"mock-{fault or 'ok'}"
        self.fault = fault
        self.seed = seed
        self.latency_s = latency_s
        self.fail_times = fail_times     # fail this many calls, then behave normally
        self.calls = 0

    def _score(self, text: str) -> int:
        h = hashlib.sha256(f"{self.seed}:{text}".encode()).digest()
        return h[0] % 11

    def complete(self, prompt: str, system: str = "", timeout: float = 60.0) -> LLMResponse:
        self.calls += 1
        if self.latency_s:
            time.sleep(self.latency_s)
        if self.fault == "fatal":
            raise LLMError("mock: invalid API key", retryable=False)
        if self.fault == "error" or self.calls <= self.fail_times:
            raise LLMError("mock: provider unavailable", retryable=True)

        items = _ID_LINE.findall(prompt)
        scores = [{"id": int(i), "score": self._score(t)} for i, t in items]
        if self.fault == "garbage":
            text = "Sure! Here are the most interesting patterns, I think the third one."
        elif self.fault == "wrong_schema":
            text = json.dumps({"ranking": "best first", "items": len(items)})
        elif self.fault == "out_of_range":
            text = json.dumps({"scores": scores + [{"id": 10_000, "score": 10},
                                                   {"id": -3, "score": 9}]})
        elif self.fault == "duplicates":
            text = json.dumps({"scores": scores + [{"id": s["id"], "score": 10 - s["score"]}
                                                   for s in scores]})
        elif self.fault == "partial":
            text = json.dumps({"scores": scores[: max(1, len(scores) // 3)]})
        elif self.fault == "fenced":
            text = "```json\n" + json.dumps({"scores": scores}) + "\n```"
        else:
            text = json.dumps({"scores": scores})
        return LLMResponse(text, self.name, self.model,
                           input_tokens=len(prompt) // 4, output_tokens=len(text) // 4,
                           latency_s=self.latency_s)
