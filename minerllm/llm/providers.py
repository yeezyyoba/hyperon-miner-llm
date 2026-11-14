"""Gemini, Groq and NVIDIA clients (plain HTTPS via ``requests``, no vendor SDKs).

Keys come from the environment (or a local ``.env``), never from code or URLs:

    GEMINI_API_KEY   GROQ_API_KEY   NVIDIA_API_KEY

Models can be overridden with GEMINI_MODEL / GROQ_MODEL / NVIDIA_MODEL.
All requests ask for JSON output. Temperature 0 is sent where the model honours
it. Gemini 3.x ignores sampling parameters, so for it we set a low thinking
level instead (GEMINI_THINKING_LEVEL = low | medium | high). The disk cache
(cache.py) makes re-runs exact either way.
"""
from __future__ import annotations

import os
import time

import requests

from .base import LLMClient, LLMError, LLMResponse

DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash",
    "groq": "openai/gpt-oss-120b",
    "nvidia": "meta/llama-3.3-70b-instruct",
}


def _raise_for(resp: requests.Response, provider: str) -> None:
    if resp.status_code == 200:
        return
    retryable = resp.status_code in (408, 409, 429) or resp.status_code >= 500
    # never echo request headers (they hold the key); body is the provider's error text
    raise LLMError(f"{provider} HTTP {resp.status_code}: {resp.text[:300]}", retryable=retryable)


class GeminiClient(LLMClient):
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODELS["gemini"])
        self._key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def available(self) -> bool:
        return bool(self._key)

    def generation_config(self) -> dict:
        cfg: dict = {"responseMimeType": "application/json"}
        major = self.model.split("-")[1].split(".")[0] if self.model.count("-") >= 1 else "0"
        if major.isdigit() and int(major) >= 3:
            # Gemini 3.x: sampling params are ignored; thinking level controls latency/cost
            cfg["thinkingConfig"] = {
                "thinkingLevel": os.environ.get("GEMINI_THINKING_LEVEL", "low")}
        else:
            cfg["temperature"] = 0
        return cfg

    def complete(self, prompt: str, system: str = "", timeout: float = 60.0) -> LLMResponse:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": self.generation_config(),
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        start = time.time()
        try:
            resp = requests.post(self.URL.format(model=self.model), json=body, timeout=timeout,
                                 headers={"x-goog-api-key": self._key})   # key in header, not URL
        except requests.RequestException as e:
            raise LLMError(f"gemini network error: {type(e).__name__}") from None
        _raise_for(resp, self.name)
        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (KeyError, IndexError):
            raise LLMError(f"gemini returned no text (finishReason="
                           f"{data.get('candidates', [{}])[0].get('finishReason')})") from None
        if not text.strip():
            raise LLMError("gemini returned an empty answer")
        usage = data.get("usageMetadata", {})
        # thinking tokens are billed as output, so count them as output
        out = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
        return LLMResponse(text, self.name, self.model, usage.get("promptTokenCount", 0),
                           out, time.time() - start)


class OpenAICompatibleClient(LLMClient):
    """Chat-completions API, as offered by Groq and NVIDIA (build.nvidia.com)."""

    def __init__(self, name: str, url: str, key_env: str, model: str | None = None,
                 api_key: str | None = None, json_mode: bool = True):
        self.name = name
        self.url = url
        self.model = model or os.environ.get(f"{name.upper()}_MODEL", DEFAULT_MODELS[name])
        self._key = api_key or os.environ.get(key_env, "")
        self.json_mode = json_mode

    def available(self) -> bool:
        return bool(self._key)

    def complete(self, prompt: str, system: str = "", timeout: float = 60.0) -> LLMResponse:
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": messages, "temperature": 0}
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        start = time.time()
        try:
            resp = requests.post(self.url, json=body, timeout=timeout,
                                 headers={"Authorization": f"Bearer {self._key}"})
        except requests.RequestException as e:
            raise LLMError(f"{self.name} network error: {type(e).__name__}") from None
        _raise_for(resp, self.name)
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            raise LLMError(f"{self.name} returned no message") from None
        if not text.strip():
            raise LLMError(f"{self.name} returned an empty message")
        usage = data.get("usage", {})
        return LLMResponse(text, self.name, self.model, usage.get("prompt_tokens", 0),
                           usage.get("completion_tokens", 0), time.time() - start)


def groq_client(**kw) -> OpenAICompatibleClient:
    return OpenAICompatibleClient("groq", "https://api.groq.com/openai/v1/chat/completions",
                                  "GROQ_API_KEY", **kw)


def nvidia_client(**kw) -> OpenAICompatibleClient:
    return OpenAICompatibleClient("nvidia", "https://integrate.api.nvidia.com/v1/chat/completions",
                                  "NVIDIA_API_KEY", **kw)


def list_models(provider: str, timeout: float = 30.0) -> list[str]:
    """Model IDs this account can use, straight from the provider's models endpoint."""
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        resp = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                            params={"pageSize": 1000}, headers={"x-goog-api-key": key},
                            timeout=timeout)
        _raise_for(resp, provider)
        return sorted(m["name"].removeprefix("models/") if hasattr(str, "removeprefix")
                      else m["name"].split("/", 1)[-1]
                      for m in resp.json().get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", []))
    urls = {"groq": ("https://api.groq.com/openai/v1/models", "GROQ_API_KEY"),
            "nvidia": ("https://integrate.api.nvidia.com/v1/models", "NVIDIA_API_KEY")}
    url, env = urls[provider]
    resp = requests.get(url, headers={"Authorization": f"Bearer {os.environ.get(env, '')}"},
                        timeout=timeout)
    _raise_for(resp, provider)
    return sorted(m["id"] for m in resp.json().get("data", []))
