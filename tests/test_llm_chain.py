"""Provider chain: fallback order, retries, non-retryable errors, cache."""
from __future__ import annotations

import pytest

from minerllm.llm import AllProvidersFailed, FallbackChain, build_chain
from minerllm.llm.cache import DiskCache
from minerllm.llm.mock import MockLLM
from minerllm.llm.providers import GeminiClient, groq_client, nvidia_client

PROMPT = "## Candidates\n[0] (, (A $v0) (B $v0))\n[1] (, (A $v0) (C $v0))\n"


def test_first_healthy_provider_answers():
    chain = FallbackChain([MockLLM("gemini"), MockLLM("groq")], backoff_s=0)
    resp = chain.complete(PROMPT)
    assert resp.provider == "gemini"
    assert [a["provider"] for a in resp.attempts] == ["gemini"]


def test_falls_back_after_retries_exhausted():
    gemini = MockLLM("gemini", fault="error")
    chain = FallbackChain([gemini, MockLLM("groq"), MockLLM("nvidia")], max_retries=2, backoff_s=0)
    resp = chain.complete(PROMPT)
    assert resp.provider == "groq"
    assert gemini.calls == 3                              # 1 try + 2 retries
    assert [a["provider"] for a in resp.attempts] == ["gemini"] * 3 + ["groq"]


def test_non_retryable_error_skips_straight_to_next_provider():
    gemini = MockLLM("gemini", fault="fatal")
    resp = FallbackChain([gemini, MockLLM("groq")], max_retries=2, backoff_s=0).complete(PROMPT)
    assert gemini.calls == 1 and resp.provider == "groq"


def test_transient_failure_recovers_on_retry():
    flaky = MockLLM("gemini", fail_times=1)
    resp = FallbackChain([flaky, MockLLM("groq")], max_retries=2, backoff_s=0).complete(PROMPT)
    assert resp.provider == "gemini" and flaky.calls == 2


def test_all_providers_failing_raises_with_attempt_log():
    chain = FallbackChain([MockLLM("gemini", fault="error"), MockLLM("groq", fault="fatal"),
                           MockLLM("nvidia", fault="error")], max_retries=1, backoff_s=0)
    with pytest.raises(AllProvidersFailed) as exc:
        chain.complete(PROMPT)
    assert [a["provider"] for a in exc.value.attempts] == ["gemini", "gemini", "groq", "nvidia", "nvidia"]


def test_cache_replays_same_configuration_without_calling_providers(tmp_path):
    a = FallbackChain([MockLLM("gemini")], cache=DiskCache(tmp_path)).complete(PROMPT, "sys")
    again = MockLLM("gemini", fault="fatal")              # same name/model -> same namespace
    again.model = "mock-ok"
    b = FallbackChain([again], cache=DiskCache(tmp_path)).complete(PROMPT, "sys")
    assert b.cached and b.text == a.text and again.calls == 0


def test_cache_never_mixes_providers(tmp_path):
    FallbackChain([MockLLM("gemini")], cache=DiskCache(tmp_path)).complete(PROMPT, "sys")
    groq = MockLLM("groq")
    b = FallbackChain([groq], cache=DiskCache(tmp_path)).complete(PROMPT, "sys")
    assert not b.cached and b.provider == "groq" and groq.calls == 1


def test_unconfigured_providers_are_skipped(monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert not GeminiClient().available()
    assert not groq_client().available() and not nvidia_client().available()
    monkeypatch.setenv("GROQ_API_KEY", "x")
    chain = FallbackChain([GeminiClient(), groq_client(), nvidia_client()])
    assert [c.name for c in chain.clients] == ["groq"]


def test_build_chain_parses_mock_fault_specs():
    chain = build_chain(["mock:garbage", "mock"])
    assert [c.model for c in chain.clients] == ["mock-garbage", "mock-ok"]
    with pytest.raises(ValueError):
        build_chain(["openai"])


def test_invalid_answer_moves_to_next_provider():
    bad = MockLLM("gemini", fault="garbage")
    chain = FallbackChain([bad, MockLLM("groq")], max_retries=2, backoff_s=0)
    resp = chain.complete(PROMPT, validate=lambda t: t.startswith("{"))
    assert resp.provider == "groq" and bad.calls == 1        # no retries on bad content
    assert resp.attempts[0]["error"] == "answer failed validation"


def test_cached_invalid_answer_is_not_replayed(tmp_path):
    cache = DiskCache(tmp_path)
    FallbackChain([MockLLM("gemini", fault="garbage")], cache=cache).complete(PROMPT)
    resp = FallbackChain([MockLLM("groq")], cache=cache).complete(
        PROMPT, validate=lambda t: t.startswith("{"))
    assert resp.provider == "groq" and not resp.cached


# ------------------------------------------------- Gemini request/response shape (no network)

class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload
        self.text = ""

    def json(self):
        return self._p


def _capture(monkeypatch, payload):
    sent = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        sent.update(url=url, body=json, headers=headers)
        return _FakeResp(payload)

    monkeypatch.setattr("minerllm.llm.providers.requests.post", fake_post)
    return sent


ANSWER = {"candidates": [{"content": {"parts": [
    {"text": "thinking about joins...", "thought": True},
    {"text": '{"scores": [{"id": 0, "score": 8}]}'}]}}],
    "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 30}}


def test_gemini_defaults_to_3_8_flash_with_low_thinking(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_THINKING_LEVEL", raising=False)
    sent = _capture(monkeypatch, ANSWER)
    resp = GeminiClient(api_key="k").complete("p", "sys")
    assert "models/gemini-3.8-flash:generateContent" in sent["url"]
    assert "key=" not in sent["url"] and sent["headers"]["x-goog-api-key"] == "k"
    cfg = sent["body"]["generationConfig"]
    assert cfg["thinkingConfig"] == {"thinkingLevel": "low"} and "temperature" not in cfg
    assert resp.text == '{"scores": [{"id": 0, "score": 8}]}'     # thought part skipped
    assert (resp.input_tokens, resp.output_tokens) == (100, 50)    # thinking billed as output


def test_gemini_2_x_still_gets_temperature_zero(monkeypatch):
    sent = _capture(monkeypatch, ANSWER)
    GeminiClient(model="gemini-2.5-flash", api_key="k").complete("p")
    cfg = sent["body"]["generationConfig"]
    assert cfg["temperature"] == 0 and "thinkingConfig" not in cfg


def test_provider_order_from_environment(monkeypatch):
    monkeypatch.setenv("MINERLLM_PROVIDERS", "mock:error, mock")
    chain = build_chain()
    assert [c.model for c in chain.clients] == ["mock-error", "mock-ok"]


def test_json_mode_rejected_retries_without_it(monkeypatch):
    calls = []

    class R:
        def __init__(self, code, payload, text=""):
            self.status_code, self._p, self.text = code, payload, text

        def json(self):
            return self._p

    def fake_post(url, json=None, timeout=None, headers=None):
        calls.append(dict(json))
        if "response_format" in json:
            return R(400, {}, '{"error": "response_format not supported"}')
        return R(200, {"choices": [{"message": {"content": '{"scores": []}'}}], "usage": {}})

    monkeypatch.setattr("minerllm.llm.providers.requests.post", fake_post)
    resp = nvidia_client(api_key="k").complete("p")
    assert resp.text == '{"scores": []}' and len(calls) == 2
    assert "response_format" in calls[0] and "response_format" not in calls[1]
    assert nvidia_client(api_key="k").model == "minimaxai/minimax-m3.1-flash"


# ------------------------------------------------------------------ rate limits (Groq 429)

class _R:
    def __init__(self, code, text="", headers=None, payload=None):
        self.status_code, self.text, self.headers, self._p = code, text, headers or {}, payload

    def json(self):
        return self._p


@pytest.mark.parametrize("text,headers,expected", [
    ('{"error":{"message":"Rate limit ... Please try again in 7.66s. Need more tokens?"}}', {}, 7.66),
    ('{"error":{"message":"... Please try again in 1m5.5s"}}', {}, 65.5),
    ('{"error":{"message":"... Please try again in 450ms"}}', {}, 0.45),
    ("rate limited", {"retry-after": "12"}, 12.0),
    ("rate limited", {}, None),
])
def test_retry_after_parsing(text, headers, expected):
    from minerllm.llm.providers import retry_after_seconds
    got = retry_after_seconds(_R(429, text, headers))
    assert got == pytest.approx(expected) if expected is not None else got is None


def test_chain_waits_as_long_as_the_provider_asks(monkeypatch):
    from minerllm.llm.base import LLMError
    slept = []
    monkeypatch.setattr("minerllm.llm.chain.time.sleep", lambda s: slept.append(s))

    class Limited(MockLLM):
        def complete(self, prompt, system="", timeout=60.0):
            self.calls += 1
            if self.calls == 1:
                raise LLMError("groq HTTP 429", retryable=True, retry_after=9.0)
            return super().complete(prompt, system, timeout)

    resp = FallbackChain([Limited("groq")], max_retries=2, backoff_s=1.0).complete(PROMPT)
    assert resp.provider == "groq" and slept == [9.5]          # waited 9 s + margin, not 1 s
    assert resp.attempts[0]["waited_s"] == 9.5


def test_gpt_oss_gets_low_reasoning_effort_and_json_validation_retry(monkeypatch):
    sent = []

    def fake_post(url, json=None, timeout=None, headers=None):
        sent.append(dict(json))
        if len(sent) == 1:
            return _R(400, '{"error":{"message":"Failed to validate JSON.","code":"json_validate_failed"}}')
        return _R(200, payload={"choices": [{"message": {"content": '{"scores": []}'}}], "usage": {}})

    monkeypatch.setattr("minerllm.llm.providers.requests.post", fake_post)
    monkeypatch.delenv("GROQ_REASONING_EFFORT", raising=False)
    resp = groq_client(api_key="k").complete("p")
    assert sent[0]["reasoning_effort"] == "low" and sent[0]["model"] == "openai/gpt-oss-120b"
    assert "response_format" not in sent[1] and resp.text == '{"scores": []}'
