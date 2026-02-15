# Implementation Plan: LLM Runtime & Provider Management

## Overview

This implementation plan breaks down the LLM Runtime & Provider Management system into discrete, incremental tasks. The system provides a unified interface for interacting with multiple LLM providers (Ollama, OpenAI, Gemini, Anthropic) with intelligent routing, fallback mechanisms, streaming support, conversation context management, caching, and comprehensive audit logging.

The implementation follows a bottom-up approach: starting with core data models and configuration, then building provider adapters, followed by routing and fallback logic, and finally integrating caching, context management, and audit logging.

## Tasks

- [ ] 1. Set up project structure and core data models
  - Create directory structure: `guru/llm_runtime/` with subdirectories for `providers/`, `routing/`, `context/`, `cache/`, `audit/`
  - Define core Pydantic models: `Message`, `LLMRequest`, `LLMResponse`, `TokenUsage`, `Conversation`
  - Define error classes: `LLMError`, `ProviderError`, `TimeoutError`, `AuthenticationError`, `RateLimitError`, `AllProvidersFailedError`
  - Set up testing framework with pytest and pytest-asyncio
  - _Requirements: 1.5, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

- [ ] 2. Implement configuration management
  - [ ] 2.1 Create configuration Pydantic models
    - Implement `ProviderConfig`, `RouterConfig`, `FallbackConfig`, `CacheConfig`, `ContextConfig`, `AuditConfig`
    - Implement `LLMRuntimeConfig` with validators
    - Add support for environment variable overrides
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
  
  - [ ]* 2.2 Write property test for configuration validation
    - **Property: Configuration Validation**
    - *For any* configuration with missing required fields, validation SHALL raise descriptive errors
    - **Validates: Requirements 9.2, 9.3**
  
  - [ ]* 2.3 Write unit tests for configuration
    - Test environment variable overrides
    - Test provider validation (at least one enabled)
    - Test invalid configuration scenarios
    - _Requirements: 9.2, 9.3, 9.6_

- [ ] 3. Implement provider adapter interface and base classes
  - [ ] 3.1 Create abstract `ProviderAdapter` base class
    - Define abstract methods: `generate()`, `get_available_models()`, `health_check()`
    - Define `provider_name` property
    - Implement common error handling and retry logic
    - _Requirements: 1.5, 1.6_
  
  - [ ] 3.2 Create `ModelInfo` and `ModelCapabilities` models
    - Define model capability attributes
    - Implement capability comparison methods
    - _Requirements: 10.3, 10.5_

- [ ] 4. Implement Ollama provider adapter
  - [ ] 4.1 Create `OllamaAdapter` class
    - Implement `generate()` method with streaming and non-streaming support
    - Implement `get_available_models()` using Ollama API
    - Implement `health_check()` method
    - Handle Ollama-specific errors and map to standard error types
    - _Requirements: 1.1, 4.4, 11.1_
  
  - [ ]* 4.2 Write property test for Ollama streaming
    - **Property: Streaming Token Delivery**
    - *For any* streaming request to Ollama, tokens SHALL be yielded incrementally
    - **Validates: Requirements 4.1, 4.2**
  
  - [ ]* 4.3 Write unit tests for Ollama adapter
    - Test non-streaming generation
    - Test error handling and mapping
    - Test health check
    - _Requirements: 1.1, 4.4_

- [ ] 5. Implement OpenAI provider adapter
  - [ ] 5.1 Create `OpenAIAdapter` class
    - Implement `generate()` method with streaming and non-streaming support
    - Implement `get_available_models()` using OpenAI API
    - Implement `health_check()` method
    - Handle OpenAI-specific errors (rate limits, authentication) and map to standard error types
    - _Requirements: 1.2, 4.4, 11.3, 11.4_
  
  - [ ]* 5.2 Write property test for OpenAI error handling
    - **Property: Error Type Mapping**
    - *For any* OpenAI error response, the adapter SHALL map it to the appropriate standard error type
    - **Validates: Requirements 11.1, 11.3, 11.4**
  
  - [ ]* 5.3 Write unit tests for OpenAI adapter
    - Test authentication error handling
    - Test rate limit error handling
    - Test streaming and non-streaming modes
    - _Requirements: 1.2, 11.3, 11.4_

- [ ] 6. Implement Gemini provider adapter
  - [ ] 6.1 Create `GeminiAdapter` class
    - Implement `generate()` method with streaming and non-streaming support
    - Implement `get_available_models()` using Gemini API
    - Implement `health_check()` method
    - Handle Gemini-specific errors and map to standard error types
    - _Requirements: 1.3, 4.4, 11.1_
  
  - [ ]* 6.2 Write unit tests for Gemini adapter
    - Test generation with various parameters
    - Test error handling
    - Test model listing
    - _Requirements: 1.3_

- [ ] 7. Implement Anthropic provider adapter
  - [ ] 7.1 Create `AnthropicAdapter` class
    - Implement `generate()` method with streaming and non-streaming support
    - Implement `get_available_models()` using Anthropic API
    - Implement `health_check()` method
    - Handle Anthropic-specific errors and map to standard error types
    - _Requirements: 1.4, 4.4, 11.1_
  
  - [ ]* 7.2 Write unit tests for Anthropic adapter
    - Test generation with various parameters
    - Test error handling
    - Test streaming mode
    - _Requirements: 1.4_

- [ ] 8. Checkpoint - Ensure all provider adapters work independently
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement provider router
  - [ ] 9.1 Create `ProviderRouter` class
    - Implement `route()` method with priority-based selection
    - Implement `_match_capabilities()` for capability-based routing
    - Implement `_apply_load_balancing()` for load distribution
    - Support routing strategies: priority, round_robin, least_loaded, cost_optimized
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ]* 9.2 Write property test for routing rule compliance
    - **Property: Routing Rule Compliance**
    - *For any* request and routing configuration, the selected provider SHALL satisfy all routing rules
    - **Validates: Requirements 2.1, 2.5**
  
  - [ ]* 9.3 Write property test for capability matching
    - **Property: Capability Matching**
    - *For any* request specifying model capabilities, the Router SHALL only select providers meeting those capabilities
    - **Validates: Requirements 2.2, 10.2**
  
  - [ ]* 9.4 Write property test for cost optimization
    - **Property: Cost Optimization**
    - *For any* request with cost optimization enabled, the Router SHALL prefer the lowest-cost provider
    - **Validates: Requirements 2.3**
  
  - [ ]* 9.5 Write property test for load distribution
    - **Property: Load Distribution**
    - *For any* sequence of requests with load balancing, distribution SHALL follow the configured strategy
    - **Validates: Requirements 2.4**
  
  - [ ]* 9.6 Write unit tests for router
    - Test priority-based routing
    - Test round-robin load balancing
    - Test cost optimization logic
    - Test capability matching edge cases
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 10. Implement fallback handler
  - [ ] 10.1 Create `FallbackHandler` class
    - Implement `execute_with_fallback()` method
    - Implement `_is_retryable()` to classify errors
    - Implement `_should_retry()` to enforce retry limits
    - Support exponential backoff for retries
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 11.6_
  
  - [ ]* 10.2 Write property test for fallback on failure
    - **Property: Fallback on Failure**
    - *For any* provider failure with fallback enabled, the handler SHALL attempt the next provider
    - **Validates: Requirements 3.1, 3.2**
  
  - [ ]* 10.3 Write property test for retry limit enforcement
    - **Property: Retry Limit Enforcement**
    - *For any* provider with retry limits, the handler SHALL not exceed the maximum retry count
    - **Validates: Requirements 3.5**
  
  - [ ]* 10.4 Write unit tests for fallback handler
    - Test fallback chain execution
    - Test all providers failed scenario
    - Test retry limit enforcement
    - Test exponential backoff timing
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [ ] 11. Implement context manager
  - [ ] 11.1 Create `ContextManager` class
    - Implement `create_conversation()` to generate unique conversation IDs
    - Implement `add_message()` to append messages to conversation history
    - Implement `get_context()` to retrieve conversation history within token limits
    - Implement `_truncate_context()` for context length management
    - Implement `_estimate_tokens()` for token counting
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  
  - [ ]* 11.2 Write property test for context token limits
    - **Property: Context Length Enforcement**
    - *For any* conversation and token limit, `get_context()` SHALL return messages within the token limit
    - **Validates: Requirements 5.5, 5.6**
  
  - [ ]* 11.3 Write property test for conversation history integrity
    - **Property: Message Ordering**
    - *For any* sequence of messages added to a conversation, retrieval SHALL preserve the original order
    - **Validates: Requirements 5.2, 5.3, 5.4**
  
  - [ ]* 11.4 Write unit tests for context manager
    - Test conversation creation
    - Test message addition
    - Test context truncation strategies
    - Test token estimation
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

- [ ] 12. Implement cache manager
  - [ ] 12.1 Create `CacheManager` class with Redis backend
    - Implement `get()` to retrieve cached responses
    - Implement `set()` to cache responses with TTL
    - Implement `invalidate()` to clear cache entries by pattern or conversation ID
    - Implement `_generate_cache_key()` using request content and parameters
    - Implement `_should_cache()` to respect cache bypass flags
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  
  - [ ]* 12.2 Write property test for cache key uniqueness
    - **Property: Cache Key Correctness**
    - *For any* two different requests, the cache keys SHALL be different; for identical requests, cache keys SHALL be the same
    - **Validates: Requirements 8.7**
  
  - [ ]* 12.3 Write property test for cache bypass
    - **Property: Cache Bypass**
    - *For any* request with caching disabled, the Cache_Manager SHALL forward directly to the provider
    - **Validates: Requirements 8.6**
  
  - [ ]* 12.4 Write unit tests for cache manager
    - Test cache hit and miss scenarios
    - Test TTL expiration
    - Test cache invalidation by pattern
    - Test cache invalidation by conversation ID
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 13. Implement audit logger
  - [ ] 13.1 Create `AuditLogger` class with structlog
    - Implement `log_request()` to record incoming requests
    - Implement `log_response()` to record successful responses with metadata
    - Implement `log_error()` to record errors with stack traces
    - Implement `log_fallback()` to record provider fallback events
    - Implement `log_cache_hit()` to record cache hits
    - Configure structured logging format for log aggregation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [ ]* 13.2 Write property test for audit completeness
    - **Property: Fallback Logging**
    - *For any* fallback event, the Audit_Logger SHALL record both the original failure and the fallback provider
    - **Validates: Requirements 3.4, 6.4**
  
  - [ ]* 13.3 Write unit tests for audit logger
    - Test request logging with all metadata
    - Test response logging with token usage
    - Test error logging with stack traces
    - Test structured log format
    - _Requirements: 6.1, 6.2, 6.3, 6.6_

- [ ] 14. Checkpoint - Ensure all support components work independently
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Implement main LLMRuntime API
  - [ ] 15.1 Create `LLMRuntime` class
    - Initialize all components: router, fallback handler, context manager, cache manager, audit logger
    - Implement `generate()` method integrating all components
    - Implement cache check before routing
    - Implement context retrieval for conversation-based requests
    - Implement streaming and non-streaming response handling
    - Implement response caching after successful generation
    - _Requirements: 1.5, 4.1, 4.2, 4.4, 7.1, 7.2, 7.3_
  
  - [ ] 15.2 Implement conversation management methods
    - Implement `create_conversation()` delegating to context manager
    - Implement `get_conversation()` delegating to context manager
    - Implement `clear_conversation()` delegating to context manager
    - _Requirements: 5.1, 5.4_
  
  - [ ] 15.3 Implement cache management methods
    - Implement `invalidate_cache()` delegating to cache manager
    - _Requirements: 8.5_
  
  - [ ]* 15.4 Write property test for unified interface consistency
    - **Property: Unified Interface Consistency**
    - *For any* LLM request and any provider, the request and response structure SHALL remain identical
    - **Validates: Requirements 1.5**
  
  - [ ]* 15.5 Write property test for streaming mode support
    - **Property: Streaming Mode Support**
    - *For any* configured provider, the LLM_Runtime SHALL handle both streaming and non-streaming modes
    - **Validates: Requirements 4.4**
  
  - [ ]* 15.6 Write integration tests for LLMRuntime
    - Test end-to-end request flow with caching
    - Test end-to-end request flow with conversation context
    - Test end-to-end streaming request
    - Test fallback behavior on provider failure
    - _Requirements: 1.5, 4.1, 5.4, 8.1, 8.2_

- [ ] 16. Implement async operations and resource management
  - [ ] 16.1 Add async context manager support to LLMRuntime
    - Implement `__aenter__()` and `__aexit__()` for proper resource cleanup
    - Implement connection pooling for provider API connections
    - Implement graceful cancellation handling
    - _Requirements: 7.1, 7.2, 7.4, 7.5_
  
  - [ ]* 16.2 Write property test for concurrent request handling
    - **Property: Concurrent Processing**
    - *For any* set of concurrent requests, the LLM_Runtime SHALL process them without blocking
    - **Validates: Requirements 7.2**
  
  - [ ]* 16.3 Write unit tests for async operations
    - Test concurrent request processing
    - Test request cancellation and cleanup
    - Test connection pooling behavior
    - _Requirements: 7.2, 7.4, 7.5_

- [ ] 17. Implement AGENT_GURU integration
  - [ ] 17.1 Create AGENT_GURU-compatible API wrapper
    - Implement message format conversion between AGENT_GURU and LLM Runtime
    - Integrate with AGENT_GURU authentication/authorization components
    - Implement event emission for monitoring and observability
    - Implement graceful shutdown handler for AGENT_GURU system shutdown
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [ ]* 17.2 Write integration tests for AGENT_GURU compatibility
    - Test message format conversion
    - Test authentication integration
    - Test event emission
    - Test graceful shutdown
    - _Requirements: 12.1, 12.2, 12.4, 12.5_

- [ ] 18. Implement configuration hot-reloading
  - [ ] 18.1 Add configuration file watcher
    - Implement file system watcher for configuration changes
    - Implement safe configuration reload without dropping in-flight requests
    - Implement validation before applying new configuration
    - _Requirements: 9.7_
  
  - [ ]* 18.2 Write unit tests for hot-reloading
    - Test configuration reload on file change
    - Test validation failure handling
    - Test in-flight request preservation
    - _Requirements: 9.7_

- [ ] 19. Add model selection and capability registry
  - [ ] 19.1 Implement model registry
    - Create registry of available models and their capabilities
    - Implement model lookup by name
    - Implement model lookup by capabilities
    - Implement fallback model selection for unavailable models
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [ ]* 19.2 Write property test for model capability matching
    - **Property: Model Capability Satisfaction**
    - *For any* request specifying capabilities, the selected model SHALL meet or exceed those capabilities
    - **Validates: Requirements 10.2, 10.4**
  
  - [ ]* 19.3 Write unit tests for model registry
    - Test model lookup by name
    - Test model lookup by capabilities
    - Test fallback model selection
    - _Requirements: 10.1, 10.3, 10.4_

- [ ] 20. Checkpoint - Ensure complete system integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 21. Add comprehensive error handling and logging
  - [ ] 21.1 Review and enhance error handling across all components
    - Ensure all provider errors are properly wrapped
    - Ensure all errors include sufficient context
    - Ensure retryable vs non-retryable error classification is correct
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_
  
  - [ ]* 21.2 Write property test for error context preservation
    - **Property: Error Context Preservation**
    - *For any* provider error, the LLM_Runtime SHALL include the original error details in the error context
    - **Validates: Requirements 11.5**
  
  - [ ]* 21.3 Write unit tests for error scenarios
    - Test timeout error handling
    - Test authentication error handling
    - Test rate limit error handling
    - Test all providers failed scenario
    - _Requirements: 11.2, 11.3, 11.4_

- [ ] 22. Create example usage and documentation
  - Create example scripts demonstrating:
    - Basic LLM generation
    - Streaming responses
    - Conversation management
    - Cache usage
    - Provider fallback
    - Configuration setup
  - _Requirements: All_

- [ ] 23. Final checkpoint - Complete system validation
  - Run all unit tests and property tests
  - Run integration tests with all providers
  - Verify configuration validation
  - Verify audit logging completeness
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key integration points
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation uses Python with async/await patterns throughout
- Provider adapters can be implemented in parallel after task 3 is complete
- Support components (context, cache, audit) can be implemented in parallel after task 8
