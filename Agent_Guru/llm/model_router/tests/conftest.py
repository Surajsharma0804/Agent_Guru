"""Shared fixtures for model_router tests."""

from __future__ import annotations

import pytest

from Agent_Guru.llm.model_router.models import (
    ModelCapability,
    ModelMetadata,
    Provider,
)
from Agent_Guru.llm.model_router.registry import ModelRegistry


def make_model(
    model_id: str = "gpt-4",
    provider: Provider = Provider.OPENAI,
    capabilities: set | None = None,
    cost_per_input: float = 0.00003,
    cost_per_output: float = 0.00006,
    average_latency_ms: float = 800.0,
    is_available: bool = True,
    max_tokens: int = 8192,
) -> ModelMetadata:
    """Factory for ModelMetadata test instances."""
    return ModelMetadata(
        model_id=model_id,
        name=model_id,
        provider=provider,
        capabilities=capabilities or {ModelCapability.CONVERSATION},
        cost_per_input_token=cost_per_input,
        cost_per_output_token=cost_per_output,
        average_latency_ms=average_latency_ms,
        is_available=is_available,
        max_tokens=max_tokens,
    )


@pytest.fixture
def registry() -> ModelRegistry:
    return ModelRegistry()


@pytest.fixture
def populated_registry() -> ModelRegistry:
    reg = ModelRegistry()
    reg.register_model(
        make_model(
            "gpt-4",
            Provider.OPENAI,
            {ModelCapability.CONVERSATION, ModelCapability.REASONING},
            cost_per_input=0.00003,
        ),
    )
    reg.register_model(
        make_model(
            "gpt-3.5",
            Provider.OPENAI,
            {ModelCapability.CONVERSATION},
            cost_per_input=0.000001,
        ),
    )
    reg.register_model(
        make_model(
            "claude-3",
            Provider.ANTHROPIC,
            {ModelCapability.CONVERSATION, ModelCapability.CODE_GENERATION},
            cost_per_input=0.000015,
        ),
    )
    reg.register_model(
        make_model(
            "llama3",
            Provider.OLLAMA,
            {ModelCapability.CONVERSATION, ModelCapability.CODE_GENERATION},
            cost_per_input=0.0,
            cost_per_output=0.0,
            average_latency_ms=200.0,
        ),
    )
    return reg
