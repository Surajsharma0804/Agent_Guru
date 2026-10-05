"""The real OpenAI and Anthropic SDK clients, driven against local stand-in servers.

Mocks of the SDK cannot show what the SDK does on the wire: its own timeout,
its own retries, the error types it raises. Those were the defects found here
(a DeepSeek key sent to api.openai.com, 600 s SDK timeouts and hidden SDK
retries under 2 s budgets, knowledge synthesis that never returned). These
tests point the real clients at local HTTP servers that speak the two APIs,
so routing, payload, deadline, retry count and fallback are checked end to end
with no network. Real provider accounts are not exercised.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pytest

pytest.importorskip("openai")
pytest.importorskip("anthropic")


class Stand_in:  # noqa: N801
    """Answers OpenAI /v1/chat/completions and Anthropic /v1/messages."""

    def __init__(self, content: str = "ok", status: int = 200, delay: float = 0.0):
        self.content, self.status, self.delay = content, status, delay
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                headers = {k.lower(): v for k, v in self.headers.items()}
                outer.requests.append({"path": self.path, "headers": headers, "body": body})
                time.sleep(outer.delay)
                if outer.status != 200:
                    payload = {"error": {"message": "stand-in failure", "type": "server_error"}}
                elif self.path.endswith("/messages"):
                    payload = {
                        "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                        "content": [{"type": "text", "text": outer.content}],
                        "stop_reason": "end_turn", "stop_sequence": None,
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    }
                else:
                    payload = {
                        "id": "c1", "object": "chat.completion", "created": 0, "model": body["model"],
                        "choices": [{"index": 0, "finish_reason": "stop",
                                     "message": {"role": "assistant", "content": outer.content}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    }
                data = json.dumps(payload).encode()
                try:
                    self.send_response(outer.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass  # the client gave up first, which is what the stall tests want

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stand_in():
    servers = []

    def make(**kwargs):
        s = Stand_in(**kwargs)
        servers.append(s)
        return s

    yield make
    for s in servers:
        s.close()


# --------------------------------------------------------------------------
# Intent fallback (DeepSeek through the OpenAI protocol)
# --------------------------------------------------------------------------

INTENT_JSON = json.dumps({"intent_type": "open_app", "confidence": 0.9, "entities": {}, "reasoning": "r"})


def _deepseek_config(base_url: str, **overrides):
    from Agent_Guru.reasoning.intent.engine import IntentDetectionEngine

    config = IntentDetectionEngine._select_llm_provider("sk-deepseek-test", None, None)
    assert config.base_url == "https://api.deepseek.com"  # nosec B101  routed to DeepSeek, not OpenAI
    config.base_url = f"{base_url}/v1"
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


async def test_intent_fallback_round_trip(stand_in):
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackClassifier

    server = stand_in(content=INTENT_JSON)
    result = await LLMFallbackClassifier(_deepseek_config(server.url)).classify_async("open chrome")

    assert result.intent_type == "open_app" and result.retries == 0  # nosec B101
    sent = server.requests[0]
    assert sent["path"] == "/v1/chat/completions"  # nosec B101
    assert sent["body"]["model"] == "deepseek-chat"  # nosec B101
    assert sent["headers"]["authorization"] == "Bearer sk-deepseek-test"  # nosec B101
    assert sent["body"]["response_format"] == {"type": "json_object"}  # nosec B101


async def test_intent_fallback_retries_exactly_its_own_attempts(stand_in):
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackClassifier

    server = stand_in(status=500)
    config = _deepseek_config(server.url, max_retries=2, timeout_ms=2000.0)
    result = await LLMFallbackClassifier(config).classify_async("open chrome")

    # The SDK used to add 2 hidden retries to each of these.
    assert len(server.requests) == 2  # nosec B101
    assert result.intent_type.lower() == "unknown"  # nosec B101


async def test_intent_fallback_stall_ends_at_the_deadline(stand_in):
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackClassifier

    server = stand_in(content=INTENT_JSON, delay=6.0)
    config = _deepseek_config(server.url, max_retries=2, timeout_ms=500.0)
    started = time.perf_counter()
    result = await LLMFallbackClassifier(config).classify_async("open chrome")

    assert result.intent_type.lower() == "unknown"  # nosec B101
    assert time.perf_counter() - started < 4.0  # nosec B101
    assert len(server.requests) <= 2  # nosec B101


# --------------------------------------------------------------------------
# Reasoning providers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "env", "suffix"), [
    ("openai", "OPENAI_BASE_URL", "/v1"),
    ("anthropic", "ANTHROPIC_BASE_URL", ""),
])
async def test_provider_round_trip(stand_in, monkeypatch, name, env, suffix):
    from Agent_Guru.reasoning.llm.models import LLMRequest

    server = stand_in(content="hello there")
    monkeypatch.setenv(env, server.url + suffix)
    provider = _provider(name, timeout_seconds=5.0, max_retries=2)

    response = await provider.generate(LLMRequest(prompt="hi", max_tokens=16))

    assert response.text == "hello there"  # nosec B101
    assert len(server.requests) == 1  # nosec B101


@pytest.mark.parametrize(("name", "env", "suffix"), [
    ("openai", "OPENAI_BASE_URL", "/v1"),
    ("anthropic", "ANTHROPIC_BASE_URL", ""),
])
async def test_provider_stall_ends_at_its_deadline(stand_in, monkeypatch, name, env, suffix):
    from Agent_Guru.reasoning.llm.models import LLMRequest

    server = stand_in(delay=8.0)
    monkeypatch.setenv(env, server.url + suffix)
    provider = _provider(name, timeout_seconds=1.0, max_retries=2)

    started = time.perf_counter()
    with pytest.raises(TimeoutError):
        await provider.generate(LLMRequest(prompt="hi", max_tokens=16))
    # Two 1 s attempts and one 1 s backoff; the SDK's 600 s and its own two
    # retries per attempt would have taken minutes.
    assert time.perf_counter() - started < 6.0  # nosec B101
    assert len(server.requests) == 2  # nosec B101


@pytest.mark.parametrize(("name", "env", "suffix"), [
    ("openai", "OPENAI_BASE_URL", "/v1"),
    ("anthropic", "ANTHROPIC_BASE_URL", ""),
])
async def test_provider_server_error_is_retried_by_generate_only(stand_in, monkeypatch, name, env, suffix):
    from Agent_Guru.reasoning.llm.models import LLMRequest

    server = stand_in(status=500)
    monkeypatch.setenv(env, server.url + suffix)
    provider = _provider(name, timeout_seconds=5.0, max_retries=2)

    with pytest.raises(RuntimeError):
        await provider.generate(LLMRequest(prompt="hi", max_tokens=16))
    assert len(server.requests) == 2  # nosec B101


def _provider(name: str, **config):
    from Agent_Guru.reasoning.llm.providers.base import ProviderConfig

    if name == "openai":
        from Agent_Guru.reasoning.llm.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(ProviderConfig(api_key="k", **config))
    from Agent_Guru.reasoning.llm.providers.anthropic_provider import AnthropicProvider

    return AnthropicProvider(ProviderConfig(api_key="k", **config))


# --------------------------------------------------------------------------
# Knowledge synthesis
# --------------------------------------------------------------------------


def _synthesizer(**kwargs):
    from Agent_Guru.reasoning.knowledge.synthesizer import KnowledgeSynthesizer
    from Agent_Guru.reasoning.memory_retriever import MemoryRetriever

    return KnowledgeSynthesizer(
        memory_retriever=Mock(spec=MemoryRetriever), llm_provider="openai", llm_api_key="k",
        use_llm_synthesis=True, **kwargs,
    )


def _query():
    from Agent_Guru.reasoning.models.knowledge import KnowledgeQuery, KnowledgeQueryType

    return KnowledgeQuery(query_text="what did I do?", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9)


def test_synthesis_round_trip(stand_in, monkeypatch):
    server = stand_in(content=json.dumps({"summary": "You went running.", "confidence": 0.8}))
    monkeypatch.setenv("OPENAI_BASE_URL", server.url + "/v1")

    answer = _synthesizer(llm_timeout_ms=5000.0).generate_answer(_query(), [], [], {})

    # The synthesizer hedges below high confidence ("I'm not very confident, but ...").
    assert "you went running" in answer.summary.lower()  # nosec B101
    assert len(server.requests) == 1  # nosec B101


def test_synthesis_falls_back_after_its_own_attempts(stand_in, monkeypatch):
    server = stand_in(status=500)
    monkeypatch.setenv("OPENAI_BASE_URL", server.url + "/v1")

    answer = _synthesizer(llm_timeout_ms=5000.0, llm_max_retries=2).generate_answer(_query(), [], [], {})

    assert answer.summary  # nosec B101  the template answer
    assert len(server.requests) == 2  # nosec B101


async def test_synthesis_inside_a_loop_returns_by_its_deadline(stand_in, monkeypatch):
    server = stand_in(delay=8.0)
    monkeypatch.setenv("OPENAI_BASE_URL", server.url + "/v1")

    started = time.perf_counter()
    answer = _synthesizer(llm_timeout_ms=500.0, llm_max_retries=2).generate_answer(_query(), [], [], {})

    assert answer.summary  # nosec B101
    assert time.perf_counter() - started < 4.0  # nosec B101
