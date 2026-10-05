"""The failover router names the same Anthropic model as the Anthropic provider."""

from __future__ import annotations

import inspect

from Agent_Guru.llm.failover_router import ProviderFailoverRouter
from Agent_Guru.llm.models import ModelProvider
from Agent_Guru.reasoning.llm.providers.anthropic_provider import AnthropicProvider


def test_anthropic_default_matches_the_anthropic_provider():
    # It named claude-3-haiku-20240307, a model nothing else here uses.
    served = inspect.signature(AnthropicProvider.__init__).parameters["model"].default
    assert ProviderFailoverRouter._get_default_model(ModelProvider.ANTHROPIC) == served  # nosec B101


def test_request_for_another_providers_model_is_renamed_for_anthropic():
    from Agent_Guru.llm.models import CompletionRequest, Message

    router = ProviderFailoverRouter.__new__(ProviderFailoverRouter)
    request = CompletionRequest(model="gemma3:4b", messages=[Message(role="user", content="hi")])
    adapted = router._adapt_request(request, ModelProvider.ANTHROPIC)
    assert adapted.model == "claude-opus-5-5"  # nosec B101
