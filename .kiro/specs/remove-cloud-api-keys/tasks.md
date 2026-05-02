# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Cloud Provider References Exist in Codebase
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate cloud provider code is present and reachable
  - **Scoped PBT Approach**: For each cloud artifact category, scope the property to the concrete failing case(s) to ensure reproducibility
  - Write tests in `Agent_Guru/reasoning/tests/test_remove_cloud_api_keys_exploration.py`
  - Test 1 — Cloud Adapter Import: attempt `from Agent_Guru.llm.providers import OpenAIAdapter, AnthropicAdapter, GoogleAdapter` — succeeds on unfixed code
  - Test 2 — RuntimeConfig Cloud Fields: instantiate `RuntimeConfig()` and assert `hasattr(config, "openai_config")` — True on unfixed code
  - Test 3 — ModelProvider Enum: assert `hasattr(ModelProvider, "OPENAI")` — True on unfixed code
  - Test 4 — LLMProvider Enum: assert `hasattr(LLMProvider, "OPENAI")` in `llm_manager.py` — True on unfixed code
  - Test 5 — Controller Provider List: instantiate `DegradationController()` and assert `"openai" in controller._llm_providers` — True on unfixed code
  - Test 6 — LLM Fallback Cloud Provider: instantiate `LLMFallbackConfig(provider="openai")` without error — succeeds on unfixed code
  - Use `@given` with `hypothesis.strategies` to generate variations where applicable (e.g., cloud provider name strings from `["openai", "anthropic", "gemini"]`)
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bug exists)
  - Document counterexamples found (e.g., "OpenAIAdapter is importable", "ModelProvider.OPENAI exists", "DegradationController._llm_providers contains 'openai'")
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12, 1.13, 1.14, 1.15_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Ollama Adapter and Runtime Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Write tests in `Agent_Guru/reasoning/tests/test_remove_cloud_api_keys_preservation.py`
  - Observe: `OllamaAdapter` is importable from `Agent_Guru.llm.providers` on unfixed code
  - Observe: `ModelProvider.OLLAMA` exists in the `ModelProvider` enum on unfixed code
  - Observe: `LLMRuntime._get_provider("llama3")` returns `ModelProvider.OLLAMA` on unfixed code
  - Observe: `DegradationController._llm_providers` contains `"ollama"` on unfixed code
  - Observe: `LLMFallbackConfig(provider="ollama")` is accepted without error on unfixed code
  - Observe: `VQAEngine` has no `_call_cloud_vlm` attribute on desktop platform on unfixed code (desktop path is already local)
  - Write property-based test: for any model name string that does NOT start with `"gpt-"`, `"claude-"`, or `"gemini-"`, `LLMRuntime._get_provider(model_name)` returns `ModelProvider.OLLAMA` (from Preservation Requirements in design)
  - Write property-based test: for any provider name string other than `"ollama"`, `LLMFallbackConfig` should raise `ValueError` after fix — observe current behavior on unfixed code first
  - Write property-based test: `DegradationController._llm_providers` always contains `"ollama"` regardless of initialization parameters
  - Write property-based test: `OllamaAdapter` is always importable and instantiable with a valid config
  - Use `@given(st.text())` scoped to valid Ollama model name patterns for routing tests
  - Verify all preservation tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline Ollama behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12_

- [x] 3. Remove cloud provider adapter files

  - [x] 3.1 Delete cloud LLM adapter files from `Agent_Guru/llm/providers/`
    - Delete `Agent_Guru/llm/providers/openai_adapter.py`
    - Delete `Agent_Guru/llm/providers/anthropic_adapter.py`
    - Delete `Agent_Guru/llm/providers/google_adapter.py`
    - _Bug_Condition: isBugCondition(artifact) where artifact IMPORTS OR INSTANTIATES [OpenAIAdapter, AnthropicAdapter, GoogleAdapter]_
    - _Expected_Behavior: Files do not exist on disk; importing them raises ImportError_
    - _Preservation: OllamaAdapter and ProviderAdapter (base class) remain in place and importable_
    - _Requirements: 2.1, 2.6_

  - [x] 3.2 Delete cloud LLM provider files from `Agent_Guru/reasoning/llm/providers/`
    - Delete `Agent_Guru/reasoning/llm/providers/openai_provider.py`
    - Delete `Agent_Guru/reasoning/llm/providers/anthropic_provider.py`
    - Delete `Agent_Guru/reasoning/llm/providers/gemini_provider.py`
    - Also remove `DeepSeekProvider` if it requires a cloud API key (remove for clean scope per design)
    - _Bug_Condition: isBugCondition(artifact) where artifact IMPORTS OR INSTANTIATES [OpenAIProvider, AnthropicProvider, GeminiProvider]_
    - _Expected_Behavior: Files do not exist on disk_
    - _Preservation: OllamaProvider, OllamaProviderConfig, BaseLLMProvider, ProviderConfig remain_
    - _Requirements: 2.7_

- [x] 4. Update `Agent_Guru/llm/models.py`

  - [x] 4.1 Remove cloud enum values and config classes from `models.py`
    - Remove `OPENAI = "openai"`, `ANTHROPIC = "anthropic"`, `GOOGLE = "google"` from `ModelProvider` enum — keep `OLLAMA = "ollama"`
    - Delete `OpenAIConfig`, `AnthropicConfig`, `GoogleConfig` class definitions entirely
    - Remove `openai_config`, `anthropic_config`, `google_config` fields from `RuntimeConfig` — keep only `ollama_config`
    - _Bug_Condition: isBugCondition(artifact) where artifact DEFINES enum value IN [ModelProvider.OPENAI, ModelProvider.ANTHROPIC, ModelProvider.GOOGLE] OR DEFINES config field IN [openai_config, anthropic_config, google_config]_
    - _Expected_Behavior: ModelProvider enum has exactly one value OLLAMA; RuntimeConfig has only ollama_config_
    - _Preservation: ModelProvider.OLLAMA remains; RuntimeConfig instantiation with ollama_config continues to work_
    - _Requirements: 2.2, 2.15, 3.12_

- [x] 5. Update `Agent_Guru/llm/llm_runtime.py`

  - [x] 5.1 Remove cloud adapter imports, routing, and pricing from `llm_runtime.py`
    - Delete imports of `AnthropicAdapter`, `GoogleAdapter`, `OpenAIAdapter`
    - Replace `self.adapters` dict with `{ModelProvider.OLLAMA: OllamaAdapter(config.ollama_config)}`
    - Simplify `_get_provider()`: remove `gpt-*`, `claude-*`, `gemini-*` prefix checks; return `ModelProvider.OLLAMA` for all model names; optionally raise `ProviderNotSupportedError` for recognized cloud prefixes
    - Remove cloud pricing entries from `_PRICING` dict (keep as empty dict or Ollama-only)
    - _Bug_Condition: isBugCondition(artifact) where artifact ROUTES model prefix IN [gpt-*, claude-*, gemini-*] to a cloud provider OR IMPORTS [AnthropicAdapter, GoogleAdapter, OpenAIAdapter]_
    - _Expected_Behavior: self.adapters contains only ModelProvider.OLLAMA key; _get_provider() always returns ModelProvider.OLLAMA_
    - _Preservation: LLMRuntime.complete() and LLMRuntime.stream() continue to inject context, validate token budgets, retry, and record metrics for Ollama model names_
    - _Requirements: 2.1, 2.3, 3.5, 3.6_

- [-] 6. Update `Agent_Guru/llm/llm_manager.py`

  - [ ] 6.1 Remove cloud provider logic from `llm_manager.py`
    - Delete imports of `AnthropicAdapter`, `GoogleAdapter`, `OpenAIAdapter`, `AnthropicConfig`, `GoogleConfig`, `OpenAIConfig`
    - Simplify `LLMProvider` enum: remove `OPENAI`, `ANTHROPIC`, `GOOGLE` — keep only `OLLAMA = "ollama"`
    - Remove `_DEFAULT_MODELS` cloud entries — keep only `ModelProvider.OLLAMA` entry
    - Remove `has_openai`, `has_anthropic`, `has_google`, `has_any_cloud_key` checks and auto-fallback block from `initialize()`; always use local Ollama mode
    - Simplify `_build_runtime_config()`: remove cloud key assignment; pass only `ollama_config`
    - Simplify `_build_adapters()`: remove cloud adapter instantiation; return only `{ModelProvider.OLLAMA: OllamaAdapter(...)}`
    - Simplify `_build_failover_config()`: remove mobile/cloud branches; always use `provider_chain = [ModelProvider.OLLAMA]`
    - Simplify `validate_api_key()`: return `True` for `OLLAMA`, raise `ValueError` for any other provider
    - Remove or narrow `store_api_key()`, `get_api_key()`, `test_api_key()` to raise `ValueError` for non-Ollama providers
    - Remove `_load_api_key_from_keyring()` if it only serves cloud providers
    - Simplify `get_supported_providers()`: return `["ollama"]` always
    - Remove `LLMConfig.mode`, `LLMConfig.provider`, `LLMConfig.cloud_model`, `LLMConfig.api_key`, `LLMConfig.enable_fallback` fields that only apply to cloud
    - _Bug_Condition: isBugCondition(artifact) where artifact DEFINES enum value IN [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GOOGLE] OR READS env var IN [OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY]_
    - _Expected_Behavior: LLMProvider enum contains only OLLAMA; initialize() never loads cloud API keys_
    - _Preservation: LLMManager.generate_response() continues to apply Guru/Maya personality prompts and return valid LLMResponse_
    - _Requirements: 2.4, 3.7_

- [ ] 7. Update `Agent_Guru/llm/config_loader.py`

  - [ ] 7.1 Remove cloud env var reads and config parsing from `config_loader.py`
    - Delete `AnthropicConfig`, `GoogleConfig`, `OpenAIConfig` from imports
    - Remove `openai_config`, `anthropic_config`, `google_config` construction from `load_config_from_env()`
    - Remove reads of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_ORG_ID` env vars
    - Remove `openai_data`, `anthropic_data`, `google_data` parsing blocks from `load_config_from_file()` and `_dict_to_config()`
    - _Bug_Condition: isBugCondition(artifact) where artifact READS env var IN [OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY]_
    - _Expected_Behavior: load_config_from_env() reads only OLLAMA_HOST and OLLAMA_MODEL; cloud env vars are ignored even if set_
    - _Preservation: Ollama config loading from env and file continues to work correctly_
    - _Requirements: 2.5_

- [ ] 8. Update `__init__.py` provider export files

  - [ ] 8.1 Update `Agent_Guru/llm/providers/__init__.py`
    - Remove imports and `__all__` entries for `OpenAIAdapter`, `AnthropicAdapter`, `GoogleAdapter`
    - Keep `ProviderAdapter` (base class) and `OllamaAdapter`
    - _Bug_Condition: isBugCondition(artifact) where artifact IMPORTS [OpenAIAdapter, AnthropicAdapter, GoogleAdapter]_
    - _Expected_Behavior: __all__ exports only OllamaAdapter and ProviderAdapter_
    - _Preservation: OllamaAdapter remains importable from Agent_Guru.llm.providers_
    - _Requirements: 2.6_

  - [ ] 8.2 Update `Agent_Guru/reasoning/llm/providers/__init__.py`
    - Remove imports and `__all__` entries for `OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`
    - Keep `OllamaProvider`, `OllamaProviderConfig`, `BaseLLMProvider`, `ProviderConfig`
    - _Bug_Condition: isBugCondition(artifact) where artifact IMPORTS [OpenAIProvider, AnthropicProvider, GeminiProvider]_
    - _Expected_Behavior: __all__ exports only OllamaProvider and base classes_
    - _Preservation: OllamaProvider remains importable from Agent_Guru.reasoning.llm.providers_
    - _Requirements: 2.7_

- [ ] 9. Update `Agent_Guru/reasoning/intent/engine.py`

  - [ ] 9.1 Remove cloud API key checks and multi-provider selection from `engine.py`
    - Delete `deepseek_key`, `gemini_key`, `openai_key` detection logic from `initialize()`
    - Remove `if deepseek_key:` / `elif openai_key:` / `elif gemini_key:` branches
    - Always construct `LLMFallbackConfig` with `provider="ollama"` and the configured Ollama model
    - Remove log message mentioning `GEMINI_API_KEY` and `DEEPSEEK_API_KEY`
    - _Bug_Condition: isBugCondition(artifact) where artifact READS env var IN [GEMINI_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY]_
    - _Expected_Behavior: engine.py always initializes LLMFallbackConfig with provider="ollama"; no cloud env var checks_
    - _Preservation: IntentDetectionEngine continues to use Ollama as the LLM fallback classifier_
    - _Requirements: 2.8, 3.8_

- [ ] 10. Update `Agent_Guru/reasoning/intent/llm_fallback.py`

  - [ ] 10.1 Remove cloud client support from `llm_fallback.py`
    - Delete `openai` and `anthropic` try/import blocks and `OPENAI_AVAILABLE`, `ANTHROPIC_AVAILABLE` flags
    - Narrow `LLMFallbackConfig.provider` validation: only `"ollama"` is valid; raise `ValueError` for any other value
    - Simplify `_initialize_client()`: remove `elif provider == "openai"` and `elif provider == "anthropic"` branches; raise `ValueError` for non-`"ollama"` provider
    - Delete `_call_openai()` and `_call_anthropic()` methods entirely
    - Simplify `_call_llm_async()`: remove `elif provider == "openai"` and `elif provider == "anthropic"` dispatch branches
    - _Bug_Condition: isBugCondition(artifact) where artifact ACCEPTS provider string IN ["openai", "anthropic"] AND does NOT raise an error_
    - _Expected_Behavior: LLMFallbackConfig(provider="openai") raises ValueError; only "ollama" is accepted_
    - _Preservation: LLMFallbackConfig(provider="ollama") continues to work; Ollama-backed intent classification is unaffected_
    - _Requirements: 2.9_

- [ ] 11. Update `Agent_Guru/reasoning/knowledge/synthesizer.py`

  - [ ] 11.1 Remove cloud client initialization from `synthesizer.py`
    - Delete `openai` and `anthropic` try/import blocks and `OPENAI_AVAILABLE`, `ANTHROPIC_AVAILABLE` flags
    - Change `KnowledgeSynthesizer.__init__` `llm_provider` default from `"openai"` to `"ollama"`
    - Raise `ValueError` if a cloud provider name (`"openai"`, `"anthropic"`) is passed
    - Simplify `_initialize_llm_client()`: remove cloud provider branches; initialize only Ollama-compatible client
    - _Bug_Condition: isBugCondition(artifact) where artifact ACCEPTS provider string IN ["openai", "anthropic"] AND does NOT raise an error_
    - _Expected_Behavior: KnowledgeSynthesizer defaults to "ollama"; passing "openai" raises ValueError_
    - _Preservation: KnowledgeSynthesizer with llm_provider="ollama" continues to initialize and synthesize knowledge_
    - _Requirements: 2.11_

- [ ] 12. Update `Agent_Guru/vision/vqa.py`

  - [ ] 12.1 Remove cloud VLM methods from `vqa.py`
    - Remove `cloud_provider` parameter from `VQAEngine.__init__`
    - Delete `_call_cloud_vlm()`, `_call_openai()`, and `_call_gemini()` methods
    - Simplify `answer()`: remove `else: raw_answer = self._call_cloud_vlm(image, prompt)` branch; when `platform != "desktop"` and no `_infer_fn` is provided, return `VQAResult(not_visible=True)` with a clear message or raise `ProviderNotSupportedError`
    - _Bug_Condition: isBugCondition(artifact) where artifact IMPORTS OR INSTANTIATES cloud VLM clients (OpenAI GPT-4V, Google Gemini Vision)_
    - _Expected_Behavior: VQAEngine has no _call_cloud_vlm, _call_openai, _call_gemini attributes; non-desktop platform returns not_visible result_
    - _Preservation: VQAEngine(platform="desktop").answer() continues to route to local LLaVA/InternVL2 model_
    - _Requirements: 2.10, 3.9_

- [ ] 13. Update `Agent_Guru/resilience/controller.py`

  - [ ] 13.1 Trim cloud providers from `_llm_providers` list in `controller.py`
    - Change `_llm_providers` from `["ollama", "openai", "gemini", "rule_based"]` to `["ollama", "rule_based"]`
    - _Bug_Condition: isBugCondition(artifact) where artifact ACCEPTS provider string IN ["openai", "gemini"] in _llm_providers_
    - _Expected_Behavior: DegradationController._llm_providers == ["ollama", "rule_based"]_
    - _Preservation: DegradationController.llm_with_failover() continues to work correctly with the reduced provider list_
    - _Requirements: 2.14, 3.10_

- [ ] 14. Update Kubernetes and Helm deployment configs

  - [ ] 14.1 Remove cloud API key secrets from `k8s/base/secrets.yaml`
    - Delete `openai-api-key`, `anthropic-api-key`, and `google-api-key` entries from `stringData`
    - Keep `sentry-dsn`, `postgres-password`, `redis-password`
    - _Bug_Condition: isBugCondition(artifact) where artifact DEFINES k8s/helm secret key IN [openai-api-key, anthropic-api-key, google-api-key]_
    - _Expected_Behavior: secrets.yaml contains no cloud LLM API key entries_
    - _Preservation: Non-cloud secrets (sentry-dsn, postgres-password, redis-password) remain unchanged_
    - _Requirements: 2.12_

  - [ ] 14.2 Remove cloud API key env var injections from `k8s/production/deployment.yaml`
    - Delete `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` `env` entries that reference `agent-guru-secrets`
    - _Bug_Condition: isBugCondition(artifact) where artifact DEFINES k8s/helm secret key IN [OPENAI_API_KEY, ANTHROPIC_API_KEY]_
    - _Expected_Behavior: deployment.yaml injects no cloud LLM API key environment variables_
    - _Preservation: All non-cloud environment variable injections remain unchanged_
    - _Requirements: 2.12_

  - [ ] 14.3 Remove cloud API key references from `helm/agent-guru/values.yaml`
    - Delete `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` entries from `secrets.keys`
    - _Bug_Condition: isBugCondition(artifact) where artifact DEFINES k8s/helm secret key IN [OPENAI_API_KEY, ANTHROPIC_API_KEY]_
    - _Expected_Behavior: values.yaml contains no cloud LLM API key secret references_
    - _Preservation: All non-cloud Helm values remain unchanged_
    - _Requirements: 2.13_

- [ ] 15. Update `Guru_Demo.py`

  - [ ] 15.1 Remove cloud API key mention from `Guru_Demo.py`
    - Replace `"With a better GPU or a cloud API key, response time drops under two seconds."` with `"With a better GPU, response time drops under two seconds."`
    - Verify no other cloud provider references exist in this file
    - _Bug_Condition: isBugCondition(artifact) where artifact references cloud API key in user-facing text_
    - _Expected_Behavior: Guru_Demo.py contains no cloud API key references_
    - _Preservation: All other demo content and Ollama-based LLM calls remain unchanged_
    - _Requirements: 2.1_

- [ ] 16. Fix for remove all cloud LLM API key sections

  - [ ] 16.1 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - No Cloud Provider References Remain
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior (cloud code is absent)
    - Run `Agent_Guru/reasoning/tests/test_remove_cloud_api_keys_exploration.py` on FIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms all cloud provider references have been removed)
    - Verify: `openai_adapter.py`, `anthropic_adapter.py`, `google_adapter.py` do not exist
    - Verify: `ModelProvider` enum has only `OLLAMA` value
    - Verify: `RuntimeConfig` has no `openai_config`, `anthropic_config`, `google_config` fields
    - Verify: `LLMRuntime.adapters` contains only `ModelProvider.OLLAMA` key
    - Verify: `LLMFallbackConfig(provider="openai")` raises `ValueError`
    - Verify: `DegradationController._llm_providers` == `["ollama", "rule_based"]`
    - Verify: `VQAEngine` has no `_call_cloud_vlm`, `_call_openai`, `_call_gemini` attributes
    - Verify: `k8s/base/secrets.yaml` has no `openai-api-key` or `anthropic-api-key` keys
    - Verify: `helm/agent-guru/values.yaml` has no `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `secrets.keys`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14, 2.15_

  - [ ] 16.2 Verify preservation tests still pass
    - **Property 2: Preservation** - Ollama Adapter and Runtime Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `Agent_Guru/reasoning/tests/test_remove_cloud_api_keys_preservation.py` on FIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in Ollama behavior)
    - Confirm: `OllamaAdapter` is importable and instantiable
    - Confirm: `ModelProvider.OLLAMA` exists and is the only enum value
    - Confirm: `LLMRuntime._get_provider(model_name)` returns `ModelProvider.OLLAMA` for all non-cloud model names
    - Confirm: `DegradationController._llm_providers` still contains `"ollama"`
    - Confirm: `LLMFallbackConfig(provider="ollama")` is accepted without error
    - Confirm all tests still pass after fix (no regressions)

- [ ] 17. Checkpoint - Ensure all tests pass
  - Run the full test suite: `pytest Agent_Guru/reasoning/tests/ -v`
  - Ensure all exploration tests pass (cloud code is gone)
  - Ensure all preservation tests pass (Ollama behavior intact)
  - Ensure existing Ollama adapter and provider unit tests still pass without modification
  - Run `pytest -m property` to confirm all property-based tests pass
  - Run `pytest -m unit` to confirm all unit tests pass
  - Ensure all tests pass; ask the user if questions arise
