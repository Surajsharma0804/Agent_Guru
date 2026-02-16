# Implementation Plan: LLM Runtime & Provider Management

## Overview

This implementation plan breaks down the LLM Runtime into discrete coding tasks for implementing flexible LLM configuration with support for local Ollama models and cloud API providers (OpenAI, Gemini, DeepSeek, Anthropic).

**Key Features**:
- User choice between local Ollama or cloud APIs during onboarding
- Secure API key storage in OS keychain
- Multi-provider support with intelligent routing
- Cost tracking for cloud APIs
- Streaming responses

## Task Completion Protocol

After completing EACH task:
1. ✅ Run all tests for that task
2. ✅ Verify all tests pass
3. ✅ Commit changes with descriptive message
4. ✅ Push to GitHub immediately
5. ✅ Mark task as complete in this file

## Tasks

### Phase 1: Project Setup and Configuration

- [ ] **Task 1: Project Structure and Dependencies**
  - Create `guru_llm/` package directory structure
  - Create subpackages: `providers/`, `routing/`, `caching/`, `audit/`, `config/`
  - Create `requirements.txt` with dependencies:
    - langchain (provider abstraction)
    - openai, google-generativeai, anthropic (cloud providers)
    - httpx or aiohttp (async HTTP)
    - redis or diskcache (caching)
    - keyring (OS keychain)
    - pydantic (configuration)
    - hypothesis, pytest, pytest-cov (testing)
  - _Requirements: Req 14 (Python Implementation)_
  - **Tests Required**: None (setup task)
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 2: Configuration System**
  - Implement `config/llm_config.py`:
    - `LLMConfig` class with Pydantic
    - `ProviderType` enum (OLLAMA, OPENAI, GEMINI, DEEPSEEK, ANTHROPIC)
    - `ProviderConfig` for each provider
    - Configuration validation
    - Default configurations
  - _Requirements: Req 9 (Flexible LLM Configuration)_
  - **Tests Required**:
    - Unit tests for configuration loading
    - Unit tests for validation
    - Unit tests for all provider types
    - Unit tests for default values
  - **GitHub Push**: ✅ Required after completion

### Phase 2: Provider Implementations

- [ ] **Task 3: Ollama Provider**
  - Implement `providers/ollama.py`:
    - `OllamaProvider` class
    - Local model support (mistral, llama, qwen, etc.)
    - Async request handling
    - Streaming support
    - Model availability checking
  - _Requirements: Req 1 (Multi-Provider Support), Req 9 (Local Ollama)_
  - **Tests Required**:
    - Unit tests for model requests
    - Unit tests for streaming
    - Integration tests with local Ollama
    - Performance tests for latency
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 4: OpenAI Provider**
  - Implement `providers/openai.py`:
    - `OpenAIProvider` class
    - Support for GPT-4, GPT-3.5-turbo
    - API key management
    - Async request handling
    - Streaming support
    - Error handling for rate limits
  - _Requirements: Req 1 (Multi-Provider Support), Req 9 (Cloud APIs)_
  - **Tests Required**:
    - Unit tests with mocked API
    - Unit tests for API key validation
    - Unit tests for rate limit handling
    - Integration tests with real API (optional)
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 5: Google Gemini Provider**
  - Implement `providers/gemini.py`:
    - `GeminiProvider` class
    - Support for Gemini Pro, Gemini Ultra
    - API key management
    - Async request handling
    - Streaming support
  - _Requirements: Req 1 (Multi-Provider Support), Req 9 (Cloud APIs)_
  - **Tests Required**:
    - Unit tests with mocked API
    - Unit tests for API key validation
    - Integration tests with real API (optional)
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 6: DeepSeek and Anthropic Providers**
  - Implement `providers/deepseek.py` and `providers/anthropic.py`:
    - Provider classes for both
    - API key management
    - Async request handling
    - Streaming support
  - _Requirements: Req 1 (Multi-Provider Support), Req 9 (Cloud APIs)_
  - **Tests Required**:
    - Unit tests for both providers
    - Unit tests for API key validation
  - **GitHub Push**: ✅ Required after completion

### Phase 3: API Key Management

- [ ] **Task 7: Secure API Key Storage**
  - Implement `config/key_manager.py`:
    - `APIKeyManager` class
    - Integration with OS keychain (keyring library)
    - `store_api_key()` method
    - `retrieve_api_key()` method
    - `validate_api_key()` method with test request
    - `delete_api_key()` method
  - _Requirements: Req 9 (Secure API Key Storage)_
  - **Tests Required**:
    - Unit tests for key storage/retrieval
    - Unit tests for key validation
    - Security tests for key exposure prevention
    - Unit tests for OS keychain integration
  - **GitHub Push**: ✅ Required after completion

### Phase 4: Provider Routing and Fallback

- [ ] **Task 8: Provider Router**
  - Implement `routing/router.py`:
    - `ProviderRouter` class
    - Intelligent provider selection based on task type
    - Load balancing across providers
    - Provider priority configuration
  - _Requirements: Req 2 (Intelligent Provider Routing)_
  - **Tests Required**:
    - Unit tests for routing logic
    - Unit tests for all task types
    - Property tests for routing determinism
    - Unit tests for load balancing
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 9: Fallback Handler**
  - Implement `routing/fallback.py`:
    - `FallbackHandler` class
    - Automatic fallback on provider failure
    - Fallback chain configuration
    - Retry logic with exponential backoff
  - _Requirements: Req 3 (Provider Fallback Mechanism)_
  - **Tests Required**:
    - Unit tests for fallback logic
    - Unit tests for retry behavior
    - Integration tests for provider failures
    - Property tests for eventual success or exhaustion
  - **GitHub Push**: ✅ Required after completion

### Phase 5: Streaming and Context Management

- [ ] **Task 10: Streaming Support**
  - Implement streaming for all providers
  - Add `stream_response()` method
  - Handle streaming errors gracefully
  - Support async iteration over tokens
  - _Requirements: Req 4 (Streaming Response Support)_
  - **Tests Required**:
    - Unit tests for streaming with each provider
    - Unit tests for streaming errors
    - Property tests for complete data delivery
    - Performance tests for first token latency
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 11: Context Management Integration**
  - Implement `context/manager.py`:
    - `ContextManager` class
    - Integration with guru_memory for conversation history
    - Context length management
    - Context truncation strategies
  - _Requirements: Req 5 (Conversation Context Management)_
  - **Tests Required**:
    - Integration tests with guru_memory
    - Unit tests for context truncation
    - Unit tests for context length limits
    - Property tests for context preservation
  - **GitHub Push**: ✅ Required after completion

### Phase 6: Caching and Performance

- [ ] **Task 12: Response Caching**
  - Implement `caching/cache.py`:
    - `ResponseCache` class
    - Redis or diskcache integration
    - Cache key generation from request
    - Configurable TTL
    - Cache invalidation
  - _Requirements: Req 8 (Response Caching)_
  - **Tests Required**:
    - Unit tests for cache hit/miss
    - Unit tests for TTL expiration
    - Unit tests for cache invalidation
    - Property tests for cache correctness
    - Performance tests for cache speedup
  - **GitHub Push**: ✅ Required after completion

### Phase 7: Audit Logging and Cost Tracking

- [ ] **Task 13: Audit Logger**
  - Implement `audit/logger.py`:
    - `AuditLogger` class
    - Log all LLM requests and responses
    - Include provider, model, tokens, latency
    - SQLite or PostgreSQL storage
    - Query interface for audit logs
  - _Requirements: Req 6 (Comprehensive Audit Logging)_
  - **Tests Required**:
    - Unit tests for log writing
    - Unit tests for log querying
    - Unit tests for all metadata fields
    - Property tests for log completeness
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 14: Cost Tracking**
  - Implement `audit/cost_tracker.py`:
    - `CostTracker` class
    - Token counting for all providers
    - Cost estimation based on provider pricing
    - Usage reports and summaries
  - _Requirements: Req 9 (Cost Tracking)_
  - **Tests Required**:
    - Unit tests for token counting
    - Unit tests for cost calculation
    - Unit tests for usage reports
    - Property tests for cost accuracy
  - **GitHub Push**: ✅ Required after completion

### Phase 8: Main LLM Runtime

- [ ] **Task 15: LLM Runtime Facade**
  - Implement `llm_runtime.py`:
    - `GuruLLMRuntime` class (main facade)
    - `initialize()` method
    - `generate_response()` method
    - `stream_response()` method
    - `switch_provider()` method
    - Integration with all subsystems
    - Error handling and logging
  - _Requirements: All LLM runtime requirements_
  - **Tests Required**:
    - Integration tests for end-to-end flow
    - Unit tests for provider switching
    - Property tests for error handling
    - Performance tests for response latency
  - **GitHub Push**: ✅ Required after completion

### Phase 9: Testing and Documentation

- [ ] **Task 16: Comprehensive Test Suite**
  - Implement all property-based tests (100+ iterations each)
  - Implement all unit tests for edge cases
  - Add integration tests for all providers
  - Add performance regression tests
  - Achieve minimum 80% code coverage
  - _Requirements: All testing requirements_
  - **Tests Required**:
    - All property tests passing
    - All unit tests passing
    - Coverage report >80%
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 17: Example Scripts and Documentation**
  - Create example scripts:
    - `example_local_ollama.py` - Local model usage
    - `example_cloud_api.py` - Cloud provider usage
    - `example_api_key_setup.py` - API key management
    - `example_streaming.py` - Streaming responses
    - `example_cost_tracking.py` - Cost monitoring
  - Create comprehensive README.md
  - _Requirements: Documentation requirements_
  - **Tests Required**: None (documentation task)
  - **GitHub Push**: ✅ Required after completion

### Phase 10: Integration

- [ ] **Task 18: Onboarding Integration**
  - Integrate with guru_security onboarding system
  - Support LLM configuration during onboarding
  - Test end-to-end onboarding flow
  - _Requirements: Integration with onboarding_
  - **Tests Required**:
    - Integration tests with guru_security
    - End-to-end onboarding tests
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 19: Memory System Integration**
  - Integrate with guru_memory for context
  - Test conversation history retrieval
  - _Requirements: Integration with memory_
  - **Tests Required**:
    - Integration tests with guru_memory
  - **GitHub Push**: ✅ Required after completion

## Testing Summary

### Property-Based Tests
- Provider routing determinism
- Fallback eventual success
- Cache correctness
- Streaming data completeness
- Cost calculation accuracy

### Unit Tests
- All provider implementations
- API key management
- Routing and fallback logic
- Caching operations
- Audit logging

### Integration Tests
- All cloud providers
- Local Ollama
- Onboarding system
- Memory system

### Coverage Goals
- Minimum 80% line coverage
- All providers tested
- All error paths tested

## Dependencies

This component depends on:
- guru_security (for API key storage and onboarding)
- guru_memory (for conversation context)

This component is used by:
- Main AGENT_GURU application
- All components needing LLM capabilities
