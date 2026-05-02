# Bugfix Requirements Document

## Introduction

The Agent Guru codebase currently contains cloud LLM provider integrations for OpenAI (ChatGPT/GPT-4), Google Gemini, and Anthropic Claude. These include API key configuration classes, provider adapter files, environment variable lookups, Kubernetes secrets, and UI/onboarding references. The user wants a local-only LLM setup using Ollama exclusively, with the intention of adding custom models later. All cloud API key sections must be removed to simplify the codebase, eliminate unused dependencies, and prevent accidental cloud API calls or key leakage.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the LLM runtime is initialized THEN the system instantiates OpenAI, Anthropic, and Google adapters alongside the Ollama adapter, even when no cloud API keys are configured.

1.2 WHEN `RuntimeConfig` is constructed THEN the system includes `openai_config`, `anthropic_config`, and `google_config` fields that accept and store cloud API keys.

1.3 WHEN `LLMRuntime._get_provider()` resolves a model name THEN the system routes `gpt-*`, `claude-*`, and `gemini-*` model prefixes to cloud providers instead of rejecting them.

1.4 WHEN `LLMManager` is initialized THEN the system defines a `LLMProvider` enum with `OPENAI`, `ANTHROPIC`, and `GOOGLE` values and attempts to load cloud API keys from keyring or environment variables.

1.5 WHEN `Agent_Guru/llm/config_loader.py` loads configuration THEN the system reads `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GOOGLE_API_KEY` environment variables and populates cloud provider configs.

1.6 WHEN `Agent_Guru/llm/providers/__init__.py` is imported THEN the system exports `OpenAIAdapter`, `AnthropicAdapter`, and `GoogleAdapter` as part of the public API.

1.7 WHEN `Agent_Guru/reasoning/llm/providers/__init__.py` is imported THEN the system exports `OpenAIProvider`, `AnthropicProvider`, and `GeminiProvider` from the reasoning subsystem.

1.8 WHEN `Agent_Guru/reasoning/intent/engine.py` selects an LLM provider THEN the system checks for `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `DEEPSEEK_API_KEY` environment variables and attempts to use cloud providers as fallbacks.

1.9 WHEN `Agent_Guru/reasoning/intent/llm_fallback.py` is configured THEN the system accepts `"openai"` and `"anthropic"` as valid provider values and initializes their respective clients.

1.10 WHEN `Agent_Guru/vision/vqa.py` runs on mobile platform THEN the system routes visual question answering requests to OpenAI GPT-4V or Google Gemini Vision cloud APIs.

1.11 WHEN `Agent_Guru/reasoning/knowledge/synthesizer.py` initializes THEN the system accepts `"openai"` and `"anthropic"` as LLM provider options and instantiates their clients.

1.12 WHEN `k8s/base/secrets.yaml` and `k8s/production/deployment.yaml` are applied THEN the system defines `openai-api-key` and `anthropic-api-key` Kubernetes secrets and injects them as environment variables.

1.13 WHEN `helm/agent-guru/values.yaml` is used for deployment THEN the system includes `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` in the Helm chart secret key references.

1.14 WHEN `Agent_Guru/resilience/controller.py` initializes its provider list THEN the system includes `"openai"` and `"gemini"` in the `_llm_providers` list alongside `"ollama"`.

1.15 WHEN `Agent_Guru/reasoning/llm/models.py` defines the `LLMProvider` enum THEN the system includes `OPENAI`, `ANTHROPIC`, and `GEMINI` values.

### Expected Behavior (Correct)

2.1 WHEN the LLM runtime is initialized THEN the system SHALL instantiate only the Ollama adapter, with no cloud provider adapters present.

2.2 WHEN `RuntimeConfig` is constructed THEN the system SHALL contain only `ollama_config` as a provider configuration field, with no cloud API key fields.

2.3 WHEN `LLMRuntime._get_provider()` resolves a model name THEN the system SHALL route all model names to Ollama (or raise a clear error for unrecognized non-Ollama model prefixes).

2.4 WHEN `LLMManager` is initialized THEN the system SHALL define a `LLMProvider` enum containing only `OLLAMA`, and SHALL NOT attempt to load any cloud API keys.

2.5 WHEN `Agent_Guru/llm/config_loader.py` loads configuration THEN the system SHALL read only Ollama-related environment variables (`OLLAMA_HOST`, `OLLAMA_MODEL`) and SHALL NOT reference any cloud API key variables.

2.6 WHEN `Agent_Guru/llm/providers/__init__.py` is imported THEN the system SHALL export only `OllamaAdapter` and `ProviderAdapter` (the base class).

2.7 WHEN `Agent_Guru/reasoning/llm/providers/__init__.py` is imported THEN the system SHALL export only `OllamaProvider` and the base provider classes, with no cloud provider exports.

2.8 WHEN `Agent_Guru/reasoning/intent/engine.py` selects an LLM provider THEN the system SHALL use Ollama exclusively and SHALL NOT check for any cloud API key environment variables.

2.9 WHEN `Agent_Guru/reasoning/intent/llm_fallback.py` is configured THEN the system SHALL accept only `"ollama"` as a valid provider value and SHALL reject cloud provider names with a clear error.

2.10 WHEN `Agent_Guru/vision/vqa.py` runs on any platform THEN the system SHALL route visual question answering requests to the local LLaVA/InternVL2 model only, with no cloud VLM fallback.

2.11 WHEN `Agent_Guru/reasoning/knowledge/synthesizer.py` initializes THEN the system SHALL accept only `"ollama"` (or local) as an LLM provider option and SHALL NOT instantiate any cloud clients.

2.12 WHEN `k8s/base/secrets.yaml` and `k8s/production/deployment.yaml` are applied THEN the system SHALL NOT define or inject any cloud LLM API key secrets.

2.13 WHEN `helm/agent-guru/values.yaml` is used for deployment THEN the system SHALL NOT include any cloud LLM API key references in the Helm chart.

2.14 WHEN `Agent_Guru/resilience/controller.py` initializes its provider list THEN the system SHALL contain only `"ollama"` and `"rule_based"` in the `_llm_providers` list.

2.15 WHEN `Agent_Guru/reasoning/llm/models.py` defines the `LLMProvider` enum THEN the system SHALL include only `LOCAL` (Ollama) as a provider value, with no cloud provider enum members.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a request is sent to the Ollama adapter THEN the system SHALL CONTINUE TO route it to the local Ollama server at the configured host and return a valid response.

3.2 WHEN `OllamaAdapter.complete()` is called with a valid request THEN the system SHALL CONTINUE TO return a `CompletionResponse` with the correct content, model, and token usage fields.

3.3 WHEN `OllamaAdapter.stream()` is called THEN the system SHALL CONTINUE TO yield `StreamChunk` objects incrementally from the Ollama streaming API.

3.4 WHEN `OllamaAdapter.embed()` is called THEN the system SHALL CONTINUE TO return embedding vectors from the local Ollama embedding model.

3.5 WHEN `LLMRuntime.complete()` is called with an Ollama model name THEN the system SHALL CONTINUE TO inject session context, validate token budget, execute with retry logic, and record metrics.

3.6 WHEN `LLMRuntime.stream()` is called with an Ollama model name THEN the system SHALL CONTINUE TO stream chunks and update context after completion.

3.7 WHEN `LLMManager.generate_response()` is called THEN the system SHALL CONTINUE TO apply the correct personality system prompt (Guru or Maya) and return an `LLMResponse`.

3.8 WHEN `Agent_Guru/reasoning/intent/engine.py` classifies an intent THEN the system SHALL CONTINUE TO use the Ollama-backed provider for LLM inference.

3.9 WHEN `Agent_Guru/vision/vqa.py` runs on desktop platform THEN the system SHALL CONTINUE TO route visual question answering to the local LLaVA/InternVL2 model.

3.10 WHEN `Agent_Guru/resilience/controller.py` detects network state THEN the system SHALL CONTINUE TO function correctly with only local providers in the provider list.

3.11 WHEN existing unit tests for the Ollama adapter and Ollama provider run THEN the system SHALL CONTINUE TO pass without modification.

3.12 WHEN `Agent_Guru/llm/models.py` `ModelProvider` enum is used THEN the system SHALL CONTINUE TO provide the `OLLAMA` enum value for all internal routing and adapter lookup.
