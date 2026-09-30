"""Tests for the shared Ollama generation-options policy.

Four clients talk to one Ollama server, and each used to build its own
``options``. The voice answer sent num_ctx 1024 and num_gpu 99. The intent
fallback sent neither, so on a machine whose Ollama app exported
OLLAMA_CONTEXT_LENGTH=131072 it loaded gemma3:4b with a 128K context, 61% on
the CPU, and Ollama reloaded the model between the two calls on every voice
turn. One spoken question took 45.6 s, of which the answer itself was about
3 s.

These tests pin the properties that fix that: every client sends the same
load-affecting options, the default window holds the largest prompt the
voice pipeline builds, the server-side context variable cannot leak back in,
and a prompt that does not fit is reported instead of silently truncated.
"""

from __future__ import annotations

import logging
from typing import Any, Self

import pytest

from Agent_Guru.reasoning.llm import generation

#: Largest prompt the voice pipeline builds, measured with Ollama's own
#: tokenizer (prompt_eval_count) on gemma3:4b: the orchestrator's 2900-token
#: history budget binding, plus a web snippet. At num_ctx 4096 Ollama came
#: back with 4039 and no error, meaning 218 tokens of conversation were dropped.
WORST_MEASURED_VOICE_PROMPT_TOKENS = 4257

#: Largest reply budget any voice turn requests: a clipboard rewrite, which
#: returns up to 1000 characters of the user's text.
LARGEST_VOICE_REPLY_BUDGET = 400

ENV_VARS = ("AGENT_GURU_NUM_CTX", "AGENT_GURU_NUM_GPU", "OLLAMA_MODEL")


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from the shipped defaults."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # The server-side variable that caused the bug, set the way the Ollama
    # desktop app sets it. Nothing in the client may read it.
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "131072")


class TestDefaults:
    def test_default_window_holds_the_largest_voice_prompt_and_its_reply(self) -> None:
        assert generation.DEFAULT_NUM_CTX >= (
            WORST_MEASURED_VOICE_PROMPT_TOKENS + LARGEST_VOICE_REPLY_BUDGET
        )

    def test_default_window_is_not_the_server_default(self) -> None:
        """OLLAMA_CONTEXT_LENGTH configures the server and is ignored here."""
        assert generation.context_window() == generation.DEFAULT_NUM_CTX

    def test_default_window_is_not_below_what_ollama_actually_loads(self) -> None:
        assert generation.DEFAULT_NUM_CTX >= generation.MIN_NUM_CTX

    def test_all_layers_are_requested_on_the_gpu_by_default(self) -> None:
        assert generation.gpu_layers() == generation.DEFAULT_NUM_GPU == 99


class TestEnvironmentOverride:
    def test_context_window_can_be_raised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_GURU_NUM_CTX", "16384")
        assert generation.context_window() == 16384

    @pytest.mark.parametrize("raw", ["lots", "", "  ", "1024", "0", "-5"])
    def test_unusable_context_window_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        """Typos and values Ollama would silently raise are ignored, not raised."""
        monkeypatch.setenv("AGENT_GURU_NUM_CTX", raw)
        assert generation.context_window() == generation.DEFAULT_NUM_CTX

    def test_gpu_layers_can_be_zero_for_cpu_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_GURU_NUM_GPU", "0")
        assert generation.gpu_layers() == 0

    def test_negative_gpu_layers_fall_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_GURU_NUM_GPU", "-1")
        assert generation.gpu_layers() == generation.DEFAULT_NUM_GPU


class TestOptions:
    def test_carries_load_options_and_sampling(self) -> None:
        opts = generation.ollama_options(num_predict=50, temperature=0.2, top_p=0.9, stop=["\n"])
        assert opts == {
            "num_ctx": generation.DEFAULT_NUM_CTX,
            "num_gpu": generation.DEFAULT_NUM_GPU,
            "num_predict": 50,
            "temperature": 0.2,
            "top_p": 0.9,
            "stop": ["\n"],
        }

    def test_unset_values_are_left_to_ollama(self) -> None:
        opts = generation.ollama_options(num_predict=None)
        assert opts == {"num_ctx": generation.DEFAULT_NUM_CTX, "num_gpu": generation.DEFAULT_NUM_GPU}


class TestContextFit:
    def test_fitting_request_is_silent(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            assert generation.context_fits(1619, 400, source="test")
        assert not caplog.records

    def test_missing_count_is_not_reported(self) -> None:
        assert generation.context_fits(None, 400, source="test")

    def test_overflow_is_reported_with_the_numbers(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The measured truncation: 4039 tokens came back from a 4096 window."""
        monkeypatch.setenv("AGENT_GURU_NUM_CTX", "4096")
        with caplog.at_level(logging.WARNING):
            assert not generation.context_fits(4039, 400, source="OllamaAdapter")
        message = caplog.records[-1].getMessage()
        assert "OllamaAdapter" in message
        assert "4039" in message
        assert "4096" in message


# ---------------------------------------------------------------------------
# Every client sends the policy's options. This is the regression test for
# the 45.6 s turn: before the fix these four payloads disagreed.
# ---------------------------------------------------------------------------

OLLAMA_REPLY: dict[str, Any] = {
    "response": '{"intent_type": "query_fact", "confidence": 0.9}',
    "message": {"role": "assistant", "content": "Paris."},
    "done": True,
    "done_reason": "stop",
    "prompt_eval_count": 20,
    "eval_count": 3,
}


async def _adapter_request(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from Agent_Guru.llm.models import CompletionRequest, Message, OllamaConfig
    from Agent_Guru.llm.providers.ollama_adapter import OllamaAdapter

    # The adapter setdefault()s these into os.environ; pre-set them so the
    # test leaves the process environment as it found it.
    for name, value in (
        ("OLLAMA_KEEP_ALIVE", "-1"),
        ("OLLAMA_FLASH_ATTENTION", "1"),
        ("OLLAMA_NUM_PARALLEL", "1"),
    ):
        monkeypatch.setenv(name, value)
    sent: dict[str, Any] = {}

    class FakeClient:
        async def chat(self, **kwargs: Any) -> dict[str, Any]:
            sent.update(kwargs)
            return OLLAMA_REPLY

    adapter = OllamaAdapter(OllamaConfig())
    adapter._client = FakeClient()
    await adapter.complete(
        CompletionRequest(
            model="gemma3:4b",
            messages=[Message(role="user", content="what is the capital of France")],
            max_tokens=100,
        )
    )
    return sent


async def _provider_request(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from Agent_Guru.reasoning.llm.models import LLMRequest
    from Agent_Guru.reasoning.llm.providers import ollama_provider

    sent: dict[str, Any] = {}

    class FakeResponse:
        status = 200

        async def json(self) -> dict[str, Any]:
            return OLLAMA_REPLY

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    class FakeSession:
        def __init__(self, **_: Any) -> None:
            pass

        def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
            sent.update(json)
            return FakeResponse()

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(ollama_provider.aiohttp, "ClientSession", FakeSession)
    # The reasoning conftest replaces ollama_provider.OllamaProvider with a
    # mock for the whole session. The payload under test is built by the real
    # class, which is still registered as a subclass of its base.
    real_provider = next(
        cls for cls in ollama_provider.BaseLLMProvider.__subclasses__()
        if cls.__name__ == "OllamaProvider"
    )
    provider = real_provider(ollama_provider.OllamaProviderConfig())
    await provider._generate_impl(LLMRequest(prompt="plan", max_tokens=100))
    return sent


class _FakeRequestsResponse:
    status_code = 200
    text = ""

    @staticmethod
    def json() -> dict[str, Any]:
        return OLLAMA_REPLY


async def _server_request(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from Agent_Guru.reasoning.llm import ollama_server
    from Agent_Guru.reasoning.llm.models import LLMRequest

    sent: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeRequestsResponse:
        sent.update(json)
        return _FakeRequestsResponse()

    monkeypatch.setattr(ollama_server.requests, "post", fake_post)
    server = ollama_server.OllamaServer()
    server._is_running = True
    server._available_models = [generation.ollama_model()]
    try:
        await server.generate(LLMRequest(prompt="hello", max_tokens=100))
    finally:
        await server.stop()
    return sent


async def _fallback_request(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    import requests

    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackClassifier, LLMFallbackConfig

    sent: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeRequestsResponse:
        sent.update(json)
        return _FakeRequestsResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    classifier = LLMFallbackClassifier(LLMFallbackConfig(provider="ollama"))
    await classifier._call_ollama('Input: "what is the capital of France"')
    return sent


CLIENTS = {
    "voice answer (OllamaAdapter)": _adapter_request,
    "reasoning (OllamaProvider)": _provider_request,
    "OllamaServer": _server_request,
    "intent fallback (LLMFallbackClassifier)": _fallback_request,
}


class TestEveryClientUsesThePolicy:
    @pytest.mark.parametrize("client", list(CLIENTS), ids=list(CLIENTS))
    async def test_client_sends_policy_load_options(
        self, monkeypatch: pytest.MonkeyPatch, client: str
    ) -> None:
        options = (await CLIENTS[client](monkeypatch))["options"]
        assert options["num_ctx"] == generation.DEFAULT_NUM_CTX
        assert options["num_gpu"] == generation.DEFAULT_NUM_GPU

    async def test_all_clients_agree_so_ollama_never_reloads_between_them(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ollama reloads the model when num_ctx or num_gpu change between requests."""
        load_options = set()
        for fetch in CLIENTS.values():
            options = (await fetch(monkeypatch))["options"]
            load_options.add((options.get("num_ctx"), options.get("num_gpu"), options.get("num_thread")))
        assert len(load_options) == 1, load_options

    async def test_override_reaches_every_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_GURU_NUM_CTX", "8192")
        for fetch in CLIENTS.values():
            assert (await fetch(monkeypatch))["options"]["num_ctx"] == 8192


# ---------------------------------------------------------------------------
# Thinking and the model name. Measured with gemma4:latest on a 4 GB RTX 2050:
# without "think": false every one of these clients got an empty reply,
# because the model spent the whole reply budget reasoning. "What is the
# capital of France?" took 21 s and Guru said nothing; the intent classifier
# took 5.4 s and returned "" instead of JSON. Three of the clients also asked
# for a fixed "gemma3:4b" whatever OLLAMA_MODEL said.
# ---------------------------------------------------------------------------

#: A model name no default could produce, so a client that ignores
#: OLLAMA_MODEL cannot pass by accident.
CONFIGURED_MODEL = "qwen3:8b"

#: The clients that choose a model themselves. The voice answer takes its
#: model from the request the orchestrator builds.
SELF_CONFIGURED = [name for name in CLIENTS if name != "voice answer (OllamaAdapter)"]


class TestModel:
    def test_default_when_unset(self) -> None:
        assert generation.ollama_model() == generation.DEFAULT_OLLAMA_MODEL

    def test_environment_names_the_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_MODEL", f"  {CONFIGURED_MODEL} ")
        assert generation.ollama_model() == CONFIGURED_MODEL

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_blank_setting_falls_back_to_default(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        """The intent engine used to send "" to Ollama for a blank OLLAMA_MODEL."""
        monkeypatch.setenv("OLLAMA_MODEL", raw)
        assert generation.ollama_model() == generation.DEFAULT_OLLAMA_MODEL


class TestThinkingIsOff:
    def test_policy_turns_thinking_off(self) -> None:
        assert generation.OLLAMA_THINK is False

    @pytest.mark.parametrize("client", list(CLIENTS), ids=list(CLIENTS))
    async def test_client_turns_thinking_off(
        self, monkeypatch: pytest.MonkeyPatch, client: str
    ) -> None:
        request = await CLIENTS[client](monkeypatch)
        # "is False", not falsy: a missing key means the model decides, and a
        # thinking model decides to think.
        assert request.get("think") is False

    async def test_streamed_voice_answer_turns_thinking_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from Agent_Guru.llm.models import CompletionRequest, Message, OllamaConfig
        from Agent_Guru.llm.providers.ollama_adapter import OllamaAdapter

        for name, value in (
            ("OLLAMA_KEEP_ALIVE", "-1"),
            ("OLLAMA_FLASH_ATTENTION", "1"),
            ("OLLAMA_NUM_PARALLEL", "1"),
        ):
            monkeypatch.setenv(name, value)
        sent: dict[str, Any] = {}

        async def _chunks() -> Any:
            yield {"message": {"content": "Paris."}, "done": True}

        class FakeClient:
            async def chat(self, **kwargs: Any) -> Any:
                sent.update(kwargs)
                return _chunks()

        adapter = OllamaAdapter(OllamaConfig())
        adapter._client = FakeClient()
        chunks = [
            chunk
            async for chunk in adapter.stream(
                CompletionRequest(
                    model=generation.ollama_model(),
                    messages=[Message(role="user", content="what is the capital of France")],
                    max_tokens=100,
                )
            )
        ]
        assert [c.content for c in chunks] == ["Paris."]
        assert sent.get("think") is False


class TestEveryClientAsksForTheConfiguredModel:
    @pytest.mark.parametrize("client", SELF_CONFIGURED, ids=SELF_CONFIGURED)
    async def test_client_follows_ollama_model(
        self, monkeypatch: pytest.MonkeyPatch, client: str
    ) -> None:
        """A client on a different model makes Ollama swap models on every turn."""
        monkeypatch.setenv("OLLAMA_MODEL", CONFIGURED_MODEL)
        assert (await CLIENTS[client](monkeypatch))["model"] == CONFIGURED_MODEL

    @pytest.mark.parametrize("client", SELF_CONFIGURED, ids=SELF_CONFIGURED)
    async def test_client_uses_the_shared_default(
        self, monkeypatch: pytest.MonkeyPatch, client: str
    ) -> None:
        assert (await CLIENTS[client](monkeypatch))["model"] == generation.DEFAULT_OLLAMA_MODEL
