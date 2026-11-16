"""Provider interface."""
from __future__ import annotations

from dataclasses import dataclass, field


class LLMError(RuntimeError):
    """A provider failed (network, HTTP error, timeout, empty answer, rate limit)."""

    def __init__(self, message: str, retryable: bool = True, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after      # seconds the provider asked us to wait (HTTP 429)


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False
    attempts: list[dict] = field(default_factory=list)   # filled in by the chain

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "text"}


class LLMClient:
    """One provider. Subclasses implement :meth:`complete`."""

    name: str = "base"
    model: str = ""

    def available(self) -> bool:
        """True if the client is configured (e.g. its API key is set)."""
        return True

    def complete(self, prompt: str, system: str = "", timeout: float = 60.0) -> LLMResponse:
        raise NotImplementedError
