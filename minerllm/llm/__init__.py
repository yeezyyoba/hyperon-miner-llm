"""LLM access layer: providers, the Gemini → Groq → NVIDIA fallback chain, cache, mock.

Nothing in this package knows about patterns or mining. It turns a prompt into
text and records who answered, how long it took and how many tokens it used.
Interpreting that text is the validator's job (minerllm.rankers).
"""
from .base import LLMClient, LLMError, LLMResponse
from .chain import AllProvidersFailed, FallbackChain, build_chain

__all__ = ["LLMClient", "LLMError", "LLMResponse", "FallbackChain", "AllProvidersFailed",
           "build_chain"]
