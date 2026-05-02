# Remove Cloud API Keys Bugfix Design

## Overview

The Agent Guru codebase contains cloud LLM provider integrations for OpenAI (ChatGPT/GPT-4),
Google Gemini, and Anthropic Claude that are no longer needed. These integrations are spread
across the LLM runtime, reasoning subsystem, vision module, resilience controller, and
deployment configs. The fix removes all cloud provider code, configuration, and secrets while
preserving the Ollama local LLM path entirely intact. The user intends to add custom model
support later, so the architecture must remain clean and extensible.

The fix is a targeted deletion and simplification — no new logic is introduced. Every change
either removes a cloud-specific code path or narrows an existing conditional to Ollama-only.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the defect — any code path that
  references, instantiates, or configures a cloud LLM provider (OpenAI, Anthropic, Google/Gemini).
- **Property (P)**: The desired post-fix behavior — the system operates exclusively through
  Ollama for all LLM operations, and any attempt to use a cloud provider is either silently
  ignored (deleted code) or raises a clear error (narrowed validators).
- **Preservation**: All Ollama adapter behavior, LLM runtime orchestration, context management,
  retry logic, streaming, and embedding must remain functionally identical after the fix.
- **OllamaAdapter**: `Agent_Guru/llm/providers/ollama_adapter.py` — the local HTTP adapter
  that calls the Ollama server at the configured host.
- **OllamaProvider**: `Agent_Guru/reasoning/llm/providers/ollama_provider.py` — the reasoning
  subsystem's Ollama provider implementation.
- **LLMRuntime**: `Agent_Guru/llm/llm_runtime.py` — the unified runtime that orchestrates
  context injection, token counting, retry, and metrics for all LLM calls.
- **LLMManager**: `Agent_Guru/llm/llm_manager.py` — the higher-level manager that handles
  personality prompts, session context, and provider failover.
- **isBugCondition**: A predicate that returns `True` when a given code location or
  configuration value references a cloud provider.

## Bug Details

### Bug Condition

The bug manifests whenever any module in the codebase instantiates, imports, configures, or
references a cloud LLM provider (OpenAI, Anthropic, Google/Gemini). This includes adapter
files, enum values, config fields, environment variable reads, Kubernetes secrets, Helm chart
values, and UI references.

**Formal Specification:**
```
FUNCTION isBugCondition(artifact)
  INPUT: artifact — a file, class, function, config key, or enum value
  OUTPUT: boolean

  RETURN (
    artifact IMPORTS OR INSTANTIATES [OpenAIAdapter, AnthropicAdapter, GoogleAdapter,
                                       OpenAIProvider, AnthropicProvider, GeminiProvider]
    OR artifact DEFINES config field IN [openai_config, anthropic_config, google_config]
    OR artifact READS env var IN [OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY,
                                   GEMINI_API_KEY, DEEPSEEK_API_KEY]
    OR artifact DEFINES enum value IN [ModelProvider.OPENAI, ModelProvider.ANTHROPIC,
                                        ModelProvider.GOOGLE, LLMProvider.OPENAI,
                                        LLMProvider.ANTHROPIC, LLMProvider.GOOGLE,
                                        LLMProvider.GEMINI]
    OR artifact DEFINES k8s/helm secret key IN [openai-api-key, anthropic-api-key,
                                                  google-api-key, OPENAI_API_KEY,
                                                  ANTHROPIC_API_KEY]
    OR artifact ROUTES model prefix IN [gpt-*, claude-*, gemini-*] to a cloud provider
    OR artifact ACCEPTS provider string IN ["openai", "anthropic", "gemini"]
       AND does NOT raise an error
  )
END FUNCTION
```

### Examples

- **`LLMRuntime.__init__`** builds `self.adapters` with `ModelProvider.OPENAI`,
  `ModelProvider.ANTHROPIC`, and `ModelProvider.GOOGLE` keys — `isBugCondition` = `True`.
  After fix: only `ModelProvider.OLLAMA` key present.

- **`RuntimeConfig`** has `openai_config`, `anthropic_config`, `google_config` fields —
  `isBugCondition` = `True`. After fix: only `ollama_config` field present.

- **`LLMRuntime._get_provider("gpt-4")`** returns `ModelProvider.OPENAI` —
  `isBugCondition` = `True`. After fix: returns `ModelProvider.OLLAMA` for all inputs
  (or raises `ProviderNotSupportedError` for unrecognized cloud prefixes).

- **`DegradationController._llm_providers`** = `["ollama", "openai", "gemini", "rule_based"]` —
  `isBugCondition` = `True`. After fix: `["ollama", "rule_based"]`.

- **`LLMFallbackConfig(provider="anthropic")`** accepted without error —
  `isBugCondition` = `True`. After fix: raises `ValueError`.

- **`OllamaAdapter.complete(request)`** called with a valid Ollama model —
  `isBugCondition` = `False`. Behavior must be preserved.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `OllamaAdapter.complete()`, `OllamaAdapter.stream()`, and `OllamaAdapter.embed()` must
  continue to work exactly as before, including retry logic and error handling.
- `LLMRuntime.complete()` and `LLMRuntime.stream()` must continue to inject session context,
  validate token budgets, execute with retry, and record metrics for Ollama model names.
- `LLMManager.generate_response()` must continue to apply personality system prompts (Guru/Maya)
  and return a valid `LLMResponse` when using Ollama.
- `IntentDetectionEngine` must continue to use Ollama as the LLM fallback classifier.
- `VQAEngine` on desktop platform must continue to route to the local LLaVA/InternVL2 model.
- `DegradationController.llm_with_failover()` must continue to work with `["ollama", "rule_based"]`.
- All existing unit and property-based tests for the Ollama adapter and Ollama provider must
  continue to pass without modification.
- `ModelProvider.OLLAMA` enum value must remain available for all internal routing.

**Scope:**
All code paths that do NOT involve cloud provider references are completely unaffected by this
fix. This includes:
- All Ollama HTTP calls and response parsing
- Context management, token counting, and compression
- Performance monitoring and circuit breaker logic
- Personality prompt injection and session management
- Vision OCR and local LLaVA inference
- Kubernetes infrastructure (non-secret resources)
- Helm chart (non-secret values)

## Hypothesized Root Cause

The cloud provider integrations were built into the codebase from the start as first-class
citizens alongside Ollama. There is no single root cause — the defect is the presence of the
cloud code itself, distributed across multiple layers:

1. **Provider Layer** (`llm/providers/`, `reasoning/llm/providers/`): Dedicated adapter and
   provider files for each cloud service that import third-party SDKs (`openai`, `anthropic`,
   `google-generativeai`).

2. **Model Layer** (`llm/models.py`, `reasoning/llm/models.py`): Config dataclasses
   (`OpenAIConfig`, `AnthropicConfig`, `GoogleConfig`) and enum values that make cloud
   providers appear as valid first-class options throughout the type system.

3. **Runtime Layer** (`llm_runtime.py`, `llm_manager.py`, `config_loader.py`): Instantiation
   of cloud adapters, loading of cloud API keys from keyring/env, and routing logic that
   dispatches `gpt-*`, `claude-*`, `gemini-*` model prefixes to cloud providers.

4. **Reasoning Layer** (`intent/engine.py`, `intent/llm_fallback.py`, `knowledge/synthesizer.py`):
   Cloud provider checks and client initialization scattered through the reasoning subsystem.

5. **Vision Layer** (`vision/vqa.py`): Cloud VLM fallback for mobile platform that calls
   OpenAI GPT-4V and Google Gemini Vision.

6. **Resilience Layer** (`resilience/controller.py`): Cloud provider names hardcoded in the
   failover chain list.

7. **Deployment Layer** (`k8s/`, `helm/`): Cloud API key secrets defined in Kubernetes and
   Helm configurations.

## Correctness Properties

Property 1: Bug Condition — No Cloud Provider References Remain

_For any_ artifact in the codebase where `isBugCondition(artifact)` returns `true` (i.e., the
artifact currently references a cloud LLM provider), the fixed codebase SHALL NOT contain that
artifact or SHALL have replaced it with an Ollama-only equivalent, such that no cloud provider
can be instantiated, configured, or called at runtime.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14, 2.15**

Property 2: Preservation — Ollama Behavior Unchanged

_For any_ input where `isBugCondition(artifact)` returns `false` (i.e., the artifact is part
of the Ollama code path), the fixed codebase SHALL produce exactly the same behavior as the
original codebase, preserving all Ollama adapter operations, LLM runtime orchestration,
context management, and personality-based response generation.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12**

## Fix Implementation

### Changes Required

Assuming the root cause analysis is correct (cloud code is present and must be removed):

---

**File**: `Agent_Guru/llm/providers/openai_adapter.py`
**Action**: DELETE entire file

**File**: `Agent_Guru/llm/providers/anthropic_adapter.py`
**Action**: DELETE entire file

**File**: `Agent_Guru/llm/providers/google_adapter.py`
**Action**: DELETE entire file

**File**: `Agent_Guru/reasoning/llm/providers/openai_provider.py`
**Action**: DELETE entire file

**File**: `Agent_Guru/reasoning/llm/providers/anthropic_provider.py`
**Action**: DELETE entire file

**File**: `Agent_Guru/reasoning/llm/providers/gemini_provider.py`
**Action**: DELETE entire file

---

**File**: `Agent_Guru/llm/models.py`

**Specific Changes**:
1. **Remove `ModelProvider` cloud enum values**: Delete `OPENAI = "openai"`,
   `ANTHROPIC = "anthropic"`, `GOOGLE = "google"` from `ModelProvider`. Keep `OLLAMA = "ollama"`.
2. **Remove cloud config classes**: Delete `OpenAIConfig`, `AnthropicConfig`, `GoogleConfig`
   class definitions entirely.
3. **Simplify `RuntimeConfig`**: Remove `openai_config`, `anthropic_config`, `google_config`
   fields. Keep only `ollama_config` as the provider configuration field.

---

**File**: `Agent_Guru/llm/llm_runtime.py`

**Specific Changes**:
1. **Remove cloud adapter imports**: Delete imports of `AnthropicAdapter`, `GoogleAdapter`,
   `OpenAIAdapter`.
2. **Simplify `self.adapters`**: Replace the four-entry dict with
   `{ModelProvider.OLLAMA: OllamaAdapter(config.ollama_config)}`.
3. **Simplify `_get_provider()`**: Remove cloud prefix checks (`gpt-*`, `claude-*`, `gemini-*`).
   Return `ModelProvider.OLLAMA` for all model names. Optionally raise
   `ProviderNotSupportedError` for recognized cloud prefixes to give a clear error message.
4. **Remove cloud pricing entries** from `_PRICING` dict (keep as empty dict or Ollama-only).

---

**File**: `Agent_Guru/llm/llm_manager.py`

**Specific Changes**:
1. **Remove cloud adapter imports**: Delete imports of `AnthropicAdapter`, `GoogleAdapter`,
   `OpenAIAdapter`, and the cloud config model imports (`AnthropicConfig`, `GoogleConfig`,
   `OpenAIConfig`).
2. **Simplify `LLMProvider` enum**: Remove `OPENAI`, `ANTHROPIC`, `GOOGLE` values. Keep only
   `OLLAMA = "ollama"`.
3. **Remove `_DEFAULT_MODELS` cloud entries**: Keep only `ModelProvider.OLLAMA` entry.
4. **Remove cloud API key detection logic** in `initialize()`: Delete the `has_openai`,
   `has_anthropic`, `has_google`, `has_any_cloud_key` checks and the auto-fallback block.
   The manager always uses local Ollama mode.
5. **Simplify `_build_runtime_config()`**: Remove cloud key assignment logic. Pass only
   `ollama_config`.
6. **Simplify `_build_adapters()`**: Remove cloud adapter instantiation. Return only
   `{ModelProvider.OLLAMA: OllamaAdapter(...)}`.
7. **Simplify `_build_failover_config()`**: Remove mobile/cloud branches. Always use
   `provider_chain = [ModelProvider.OLLAMA]`.
8. **Simplify `validate_api_key()`**: Remove cloud provider branches. Return `True` for
   `OLLAMA`, raise `ValueError` for any other provider.
9. **Remove `store_api_key()`, `get_api_key()`, `test_api_key()`** cloud-specific methods,
   or narrow them to raise `ValueError` for non-Ollama providers.
10. **Remove `_load_api_key_from_keyring()`** if it only serves cloud providers.
11. **Simplify `get_supported_providers()`**: Return `["ollama"]` always.
12. **Remove `LLMConfig.mode`, `LLMConfig.provider`, `LLMConfig.cloud_model`,
    `LLMConfig.api_key`, `LLMConfig.enable_fallback`** fields that only apply to cloud.

---

**File**: `Agent_Guru/llm/config_loader.py`

**Specific Changes**:
1. **Remove cloud config imports**: Delete `AnthropicConfig`, `GoogleConfig`, `OpenAIConfig`
   from the import.
2. **Simplify `load_config_from_env()`**: Remove `openai_config`, `anthropic_config`,
   `google_config` construction. Remove reads of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
   `GOOGLE_API_KEY`, `OPENAI_ORG_ID` env vars.
3. **Simplify `load_config_from_file()`** and `_dict_to_config()`: Remove `openai_data`,
   `anthropic_data`, `google_data` parsing blocks.

---

**File**: `Agent_Guru/llm/providers/__init__.py`

**Specific Changes**:
1. **Remove cloud adapter exports**: Delete imports and `__all__` entries for
   `OpenAIAdapter`, `AnthropicAdapter`, `GoogleAdapter`.
2. **Keep**: `ProviderAdapter` (base class) and `OllamaAdapter`.

---

**File**: `Agent_Guru/reasoning/llm/providers/__init__.py`

**Specific Changes**:
1. **Remove cloud provider exports**: Delete imports and `__all__` entries for
   `OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`.
2. **Keep**: `OllamaProvider`, `OllamaProviderConfig`, `BaseLLMProvider`, `ProviderConfig`.
3. **Keep `DeepSeekProvider`** only if it uses the Ollama-compatible API without a cloud key;
   otherwise remove it too. (Given the user's intent to add custom models later, remove it
   for now to keep the scope clean.)

---

**File**: `Agent_Guru/reasoning/intent/engine.py`

**Specific Changes**:
1. **Remove cloud API key checks** in `initialize()`: Delete the `deepseek_key`, `gemini_key`,
   `openai_key` detection logic and the `if deepseek_key:` / `elif openai_key:` branches.
2. **Simplify LLM fallback initialization**: Always construct `LLMFallbackConfig` with
   `provider="ollama"` and the configured Ollama model. Remove the multi-branch cloud
   provider selection.
3. **Remove the log message** that mentions `GEMINI_API_KEY` and `DEEPSEEK_API_KEY`.

---

**File**: `Agent_Guru/reasoning/intent/llm_fallback.py`

**Specific Changes**:
1. **Remove cloud client imports**: Delete the `openai` and `anthropic` try/import blocks
   and the `OPENAI_AVAILABLE`, `ANTHROPIC_AVAILABLE` flags.
2. **Narrow `LLMFallbackConfig.provider`** default and validation: Only `"ollama"` is valid.
3. **Simplify `_initialize_client()`**: Remove `elif provider == "openai"` and
   `elif provider == "anthropic"` branches. Raise `ValueError` for any non-`"ollama"` provider.
4. **Remove `_call_openai()`** and **`_call_anthropic()`** methods entirely.
5. **Simplify `_call_llm_async()`**: Remove the `elif provider == "openai"` and
   `elif provider == "anthropic"` dispatch branches.

---

**File**: `Agent_Guru/reasoning/knowledge/synthesizer.py`

**Specific Changes**:
1. **Remove cloud client imports**: Delete the `openai` and `anthropic` try/import blocks
   and the `OPENAI_AVAILABLE`, `ANTHROPIC_AVAILABLE` flags.
2. **Narrow `KnowledgeSynthesizer.__init__` `llm_provider` parameter**: Change default from
   `"openai"` to `"ollama"`. Raise `ValueError` if a cloud provider name is passed.
3. **Simplify `_initialize_llm_client()`**: Remove cloud provider branches. Only initialize
   an Ollama-compatible client (or disable LLM synthesis if no Ollama client is available).

---

**File**: `Agent_Guru/vision/vqa.py`

**Specific Changes**:
1. **Remove `cloud_provider` parameter** from `VQAEngine.__init__`. The parameter is no
   longer meaningful.
2. **Remove `_call_cloud_vlm()`**, **`_call_openai()`**, and **`_call_gemini()`** methods.
3. **Simplify `answer()`**: Remove the `else: raw_answer = self._call_cloud_vlm(image, prompt)`
   branch. When `platform != "desktop"` and no `_infer_fn` is provided, return a
   `VQAResult` with `not_visible=True` and a clear message, or raise `ProviderNotSupportedError`.

---

**File**: `Agent_Guru/resilience/controller.py`

**Specific Changes**:
1. **Simplify `_llm_providers`**: Change from
   `["ollama", "openai", "gemini", "rule_based"]` to `["ollama", "rule_based"]`.

---

**File**: `k8s/base/secrets.yaml`

**Specific Changes**:
1. **Remove cloud API key entries**: Delete `openai-api-key`, `anthropic-api-key`, and
   `google-api-key` from `stringData`. Keep `sentry-dsn`, `postgres-password`,
   `redis-password`.

---

**File**: `k8s/production/deployment.yaml`

**Specific Changes**:
1. **Remove cloud API key env var injections**: Delete the `OPENAI_API_KEY` and
   `ANTHROPIC_API_KEY` `env` entries that reference `agent-guru-secrets`.

---

**File**: `helm/agent-guru/values.yaml`

**Specific Changes**:
1. **Remove cloud API key secret references**: Delete the `OPENAI_API_KEY` and
   `ANTHROPIC_API_KEY` entries from `secrets.keys`.

---

**File**: `Guru_Demo.py`

**Specific Changes**:
1. **Remove the cloud API key mention** in the summary section: The line
   `"With a better GPU or a cloud API key, response time drops under two seconds."` should
   be updated to remove the cloud API key reference (e.g., replace with
   `"With a better GPU, response time drops under two seconds."`).
2. No other cloud references exist in this file — the demo already uses Ollama exclusively
   for all LLM calls.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate the bug on unfixed code (cloud references exist), then verify the fix removes
all cloud references while preserving Ollama behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix.
Confirm that cloud provider code is present and reachable. If we refute, we will need to
re-examine the scope.

**Test Plan**: Write tests that attempt to import cloud adapters, instantiate cloud configs,
and check enum values. Run these tests on the UNFIXED code to observe that cloud code is
present and accessible.

**Test Cases**:
1. **Cloud Adapter Import Test**: Import `OpenAIAdapter`, `AnthropicAdapter`, `GoogleAdapter`
   from `Agent_Guru.llm.providers` — succeeds on unfixed code (will fail after fix).
2. **RuntimeConfig Cloud Fields Test**: Instantiate `RuntimeConfig()` and check for
   `openai_config` attribute — present on unfixed code (will be absent after fix).
3. **ModelProvider Enum Test**: Check `ModelProvider.OPENAI` exists — present on unfixed code
   (will raise `AttributeError` after fix).
4. **LLMProvider Enum Test**: Check `LLMProvider.OPENAI` in `llm_manager.py` — present on
   unfixed code (will raise `AttributeError` after fix).
5. **Controller Provider List Test**: Instantiate `DegradationController()` and check
   `"openai" in controller._llm_providers` — `True` on unfixed code (`False` after fix).
6. **LLM Fallback Cloud Provider Test**: Instantiate `LLMFallbackConfig(provider="openai")`
   — accepted on unfixed code (raises `ValueError` after fix).

**Expected Counterexamples**:
- Cloud adapter classes are importable and instantiable
- `RuntimeConfig` accepts and stores cloud API keys
- `ModelProvider` and `LLMProvider` enums contain cloud values
- `DegradationController` includes cloud providers in its failover chain

### Fix Checking

**Goal**: Verify that for all artifacts where the bug condition holds, the fixed codebase
does not contain cloud provider references.

**Pseudocode:**
```
FOR ALL artifact WHERE isBugCondition(artifact) DO
  result := inspect_fixed_codebase(artifact)
  ASSERT cloudProviderAbsent(result)
END FOR
```

**Test Cases**:
1. Verify `openai_adapter.py`, `anthropic_adapter.py`, `google_adapter.py` files do not exist.
2. Verify `ModelProvider` enum has only `OLLAMA` value.
3. Verify `RuntimeConfig` has no `openai_config`, `anthropic_config`, `google_config` fields.
4. Verify `LLMRuntime.adapters` contains only `ModelProvider.OLLAMA` key.
5. Verify `LLMFallbackConfig(provider="openai")` raises `ValueError`.
6. Verify `DegradationController._llm_providers` == `["ollama", "rule_based"]`.
7. Verify `VQAEngine` has no `_call_openai` or `_call_gemini` methods.
8. Verify `k8s/base/secrets.yaml` has no `openai-api-key` or `anthropic-api-key` keys.
9. Verify `helm/agent-guru/values.yaml` has no `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in
   `secrets.keys`.

### Preservation Checking

**Goal**: Verify that for all artifacts where the bug condition does NOT hold (Ollama code
paths), the fixed codebase produces the same behavior as the original.

**Pseudocode:**
```
FOR ALL artifact WHERE NOT isBugCondition(artifact) DO
  ASSERT behavior_fixed(artifact) == behavior_original(artifact)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (model names, request
  parameters, message counts)
- It catches edge cases that manual unit tests might miss (e.g., empty messages, max tokens
  boundary, session ID variations)
- It provides strong guarantees that Ollama behavior is unchanged for all valid inputs

**Test Plan**: Observe Ollama adapter behavior on UNFIXED code first, then write property-based
tests capturing that behavior, then verify the same tests pass on FIXED code.

**Test Cases**:
1. **Ollama Adapter Preservation**: For any valid `CompletionRequest` with an Ollama model
   name, `OllamaAdapter.complete()` returns a `CompletionResponse` with non-empty content.
2. **LLM Runtime Routing Preservation**: For any model name that does not start with a cloud
   prefix, `LLMRuntime._get_provider()` returns `ModelProvider.OLLAMA`.
3. **DegradationController Preservation**: `llm_with_failover()` still works correctly with
   the reduced provider list `["ollama", "rule_based"]`.
4. **Intent Engine Preservation**: `IntentDetectionEngine` initializes successfully with
   Ollama fallback when no cloud keys are present.
5. **VQA Desktop Preservation**: `VQAEngine(platform="desktop").answer()` still routes to
   the local LLaVA model.

### Unit Tests

- Test that deleted files no longer exist on disk.
- Test that `ModelProvider` enum has exactly one value: `OLLAMA`.
- Test that `RuntimeConfig()` instantiation succeeds with only `ollama_config`.
- Test that `LLMFallbackConfig(provider="openai")` raises `ValueError`.
- Test that `LLMFallbackConfig(provider="ollama")` succeeds.
- Test that `DegradationController._llm_providers` equals `["ollama", "rule_based"]`.
- Test that `VQAEngine` has no `_call_cloud_vlm`, `_call_openai`, `_call_gemini` attributes.
- Test that `load_config_from_env()` does not read `OPENAI_API_KEY` from environment.

### Property-Based Tests

- Generate random valid Ollama model names and verify `LLMRuntime._get_provider()` always
  returns `ModelProvider.OLLAMA`.
- Generate random `CompletionRequest` objects with Ollama models and verify the runtime
  routes them correctly without raising `ProviderNotSupportedError`.
- Generate random provider name strings and verify `LLMFallbackConfig` raises `ValueError`
  for any value other than `"ollama"`.
- Generate random `DegradationController` states and verify `_llm_providers` never contains
  cloud provider names.

### Integration Tests

- Test full `LLMManager.initialize()` → `generate_response()` flow with Ollama model.
- Test `IntentDetectionEngine.initialize()` with no cloud API keys in environment.
- Test `KnowledgeSynthesizer` initialization with `llm_provider="ollama"`.
- Test that `load_config_from_env()` with cloud API keys set in environment does NOT
  populate any cloud config fields (they no longer exist).
