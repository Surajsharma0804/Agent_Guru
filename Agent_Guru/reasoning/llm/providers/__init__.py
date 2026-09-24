"""LLM Provider Implementations - local by default, cloud optional.

This docstring used to claim that "Cloud providers (OpenAI, Anthropic, Google
Gemini, DeepSeek) have been removed", which was only two-thirds true and
therefore worse than saying nothing: gemini_provider and deepseek_provider are
indeed gone, but openai_provider and anthropic_provider are still here, still
tested, and still reachable.

What is actually true:

* Ollama is the DEFAULT and the only provider exported from this package, so
  `from ...providers import *` pulls in nothing that talks to the network.
* OpenAIProvider and AnthropicProvider exist in this package but are
  deliberately NOT exported here. They are imported lazily, by module path, at
  the point of use, and their SDKs live in the optional `cloud` extra
  (`pip install agent-guru[cloud]`). A default offline-first install neither
  installs nor imports them.
* GeminiProvider and DeepSeekProvider do not exist. The two branches in
  ReasoningEngine._initialize_llm_provider() that imported them were dead and
  have been removed.
"""

from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider, ProviderConfig
from Agent_Guru.reasoning.llm.providers.ollama_provider import OllamaProvider, OllamaProviderConfig

__all__ = [
    "BaseLLMProvider",
    "OllamaProvider",
    "OllamaProviderConfig",
    "ProviderConfig",
]
