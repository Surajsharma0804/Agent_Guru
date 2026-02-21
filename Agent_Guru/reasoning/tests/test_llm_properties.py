"""
Property-based tests for LLM infrastructure.

Tests invariants and edge cases using Hypothesis.
"""

import pytest
from hypothesis import given, strategies as st
from Agent_Guru.reasoning.llm.models import (
    LLMRequest,
    LLMResponse,
    LocalLLMConfig,
    LLMProvider,
    GPUBackend,
)


class TestLLMRequestProperties:
    """Property-based tests for LLMRequest."""

    @given(
        prompt=st.text(min_size=1),
        temperature=st.floats(min_value=0.0, max_value=2.0),
        top_p=st.floats(min_value=0.0, max_value=1.0),
        max_tokens=st.integers(min_value=1, max_value=4096),
    )
    def test_valid_request_always_succeeds(
        self, prompt, temperature, top_p, max_tokens
    ):
        """Property: Valid parameters always create valid request."""
        request = LLMRequest(
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        assert request.prompt == prompt
        assert request.temperature == temperature
        assert request.top_p == top_p
        assert request.max_tokens == max_tokens

    @given(temperature=st.floats(min_value=-10.0, max_value=-0.01))
    def test_negative_temperature_always_fails(self, temperature):
        """Property: Negative temperature always raises error."""
        with pytest.raises(ValueError):
            LLMRequest(prompt="test", temperature=temperature)

    @given(top_p=st.floats(min_value=1.01, max_value=10.0))
    def test_top_p_above_one_always_fails(self, top_p):
        """Property: top_p > 1.0 always raises error."""
        with pytest.raises(ValueError):
            LLMRequest(prompt="test", top_p=top_p)

    @given(max_tokens=st.integers(max_value=0))
    def test_non_positive_max_tokens_always_fails(self, max_tokens):
        """Property: max_tokens <= 0 always raises error."""
        with pytest.raises(ValueError):
            LLMRequest(prompt="test", max_tokens=max_tokens)


class TestLLMResponseProperties:
    """Property-based tests for LLMResponse."""

    @given(
        text=st.text(),
        latency_ms=st.floats(min_value=0.0, max_value=10000.0),
        tokens_generated=st.integers(min_value=0, max_value=4096),
        finish_reason=st.sampled_from(["stop", "length", "error"]),
    )
    def test_valid_response_always_succeeds(
        self, text, latency_ms, tokens_generated, finish_reason
    ):
        """Property: Valid parameters always create valid response."""
        response = LLMResponse(
            text=text,
            provider=LLMProvider.LOCAL,
            latency_ms=latency_ms,
            tokens_generated=tokens_generated,
            finish_reason=finish_reason,
        )

        assert response.text == text
        assert response.latency_ms == latency_ms
        assert response.tokens_generated == tokens_generated
        assert response.finish_reason == finish_reason

    @given(latency_ms=st.floats(min_value=-10000.0, max_value=-0.01))
    def test_negative_latency_always_fails(self, latency_ms):
        """Property: Negative latency always raises error."""
        with pytest.raises(ValueError):
            LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=latency_ms,
                tokens_generated=10,
                finish_reason="stop",
            )

    @given(tokens=st.integers(max_value=-1))
    def test_negative_tokens_always_fails(self, tokens):
        """Property: Negative tokens always raises error."""
        with pytest.raises(ValueError):
            LLMResponse(
                text="test",
                provider=LLMProvider.LOCAL,
                latency_ms=100.0,
                tokens_generated=tokens,
                finish_reason="stop",
            )



class TestLocalLLMConfigProperties:
    """Property-based tests for LocalLLMConfig."""

    @given(
        n_gpu_layers=st.integers(min_value=0, max_value=100),
        n_ctx=st.integers(min_value=1, max_value=8192),
        n_threads=st.integers(min_value=1, max_value=64),
        port=st.integers(min_value=1024, max_value=65535),
        temperature=st.floats(min_value=0.0, max_value=2.0),
        top_p=st.floats(min_value=0.0, max_value=1.0),
        max_tokens=st.integers(min_value=1, max_value=4096),
    )
    def test_valid_config_always_succeeds(
        self,
        n_gpu_layers,
        n_ctx,
        n_threads,
        port,
        temperature,
        top_p,
        max_tokens,
    ):
        """Property: Valid parameters always create valid config."""
        config = LocalLLMConfig(
            model_path="test.gguf",
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            n_threads=n_threads,
            port=port,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        assert config.n_gpu_layers == n_gpu_layers
        assert config.n_ctx == n_ctx
        assert config.n_threads == n_threads
        assert config.port == port
        assert config.temperature == temperature
        assert config.top_p == top_p
        assert config.max_tokens == max_tokens

    @given(n_gpu_layers=st.integers(max_value=-1))
    def test_negative_gpu_layers_always_fails(self, n_gpu_layers):
        """Property: Negative GPU layers always raises error."""
        with pytest.raises(ValueError):
            LocalLLMConfig(model_path="test.gguf", n_gpu_layers=n_gpu_layers)

    @given(n_ctx=st.integers(max_value=0))
    def test_non_positive_context_always_fails(self, n_ctx):
        """Property: n_ctx <= 0 always raises error."""
        with pytest.raises(ValueError):
            LocalLLMConfig(model_path="test.gguf", n_ctx=n_ctx)

    @given(n_threads=st.integers(max_value=0))
    def test_non_positive_threads_always_fails(self, n_threads):
        """Property: n_threads <= 0 always raises error."""
        with pytest.raises(ValueError):
            LocalLLMConfig(model_path="test.gguf", n_threads=n_threads)

    @given(
        port=st.one_of(
            st.integers(max_value=1023), st.integers(min_value=65536)
        )
    )
    def test_invalid_port_always_fails(self, port):
        """Property: Port outside 1024-65535 always raises error."""
        with pytest.raises(ValueError):
            LocalLLMConfig(model_path="test.gguf", port=port)
