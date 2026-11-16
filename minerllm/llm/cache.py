"""Content-addressed disk cache for LLM answers.

Key = sha256(namespace + system prompt + user prompt), where the namespace is the
chain's provider/model list (e.g. "groq:openai/gpt-oss-120b+nvidia:..."). A re-run
of the same configuration replays exactly the same answers at zero cost, while
comparing providers never mixes their answers. Each entry records which
provider actually answered.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .base import LLMResponse


class DiskCache:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(prompt: str, system: str = "", namespace: str = "") -> str:
        return hashlib.sha256(f"{namespace}\x00{system}\x00{prompt}".encode()).hexdigest()

    def get(self, prompt: str, system: str = "", namespace: str = "") -> LLMResponse | None:
        path = self.dir / f"{self.key(prompt, system, namespace)}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        resp = LLMResponse(**{k: v for k, v in data.items() if k != "attempts"})
        resp.cached = True
        resp.latency_s = 0.0
        return resp

    def put(self, prompt: str, system: str, resp: LLMResponse, namespace: str = "") -> None:
        path = self.dir / f"{self.key(prompt, system, namespace)}.json"
        data = {"text": resp.text, "provider": resp.provider, "model": resp.model,
                "input_tokens": resp.input_tokens, "output_tokens": resp.output_tokens,
                "latency_s": resp.latency_s}
        path.write_text(json.dumps(data, indent=1))
