"""Content-addressed disk cache for LLM answers.

Key = sha256(system prompt + user prompt). The provider is not part of the key:
the cache answers "what did we get for this exact question last time?", so an
evaluation re-run replays exactly the same rankings at zero cost, whichever
provider originally answered. Each entry records that provider.
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
    def key(prompt: str, system: str = "") -> str:
        return hashlib.sha256(f"{system}\x00{prompt}".encode()).hexdigest()

    def get(self, prompt: str, system: str = "") -> LLMResponse | None:
        path = self.dir / f"{self.key(prompt, system)}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        resp = LLMResponse(**{k: v for k, v in data.items() if k != "attempts"})
        resp.cached = True
        resp.latency_s = 0.0
        return resp

    def put(self, prompt: str, system: str, resp: LLMResponse) -> None:
        path = self.dir / f"{self.key(prompt, system)}.json"
        data = {"text": resp.text, "provider": resp.provider, "model": resp.model,
                "input_tokens": resp.input_tokens, "output_tokens": resp.output_tokens,
                "latency_s": resp.latency_s}
        path.write_text(json.dumps(data, indent=1))
