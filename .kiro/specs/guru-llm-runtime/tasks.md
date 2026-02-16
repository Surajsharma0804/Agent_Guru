# Implementation Plan: LLM Runtime System

## Overview

This implementation plan breaks down the LLM Runtime System into discrete, incremental coding tasks. The system provides a unified interface for running language models across multiple providers (Ollama, OpenAI, Anthropic, Google) with advanced features including streaming, function calling, context management, token optimization, and performance monitoring.

The implementation follows a bottom-up approach: core data models → provider adapters → unified interface → context management → performance monitoring → error handling → GitHub integration → testing.

## Tasks

- [ ] 1. Set up project structure and core data models
  - Create Python package structure with proper __init__.py files
  - Define core data models (Message, CompletionRequest, CompletionResponse, TokenUsage, StreamChunk, FunctionDefinition)
  - Set up Pydantic models for request/response validation
  - Create configuration classes (RuntimeConfig, OllamaConfig, OpenAIConfig, AnthropicConfig, GoogleConfig)
  - Set up development dependencies (pytest, hypothesis, black, mypy)
  - _Requirements: 1.1, 1.2, 1.3, 11.1, 11.4_

- [ ] 2. Implement Token Counter
  - [ ] 2.1 Create TokenCounter class with provider detection
    - Implement _get_provider() method to detect provider from model name
    - Set up tiktoken for OpenAI token counting
    - Set up anthropic library for Anthropic token counting
    - Implement approximation logic for Google and Ollama
    - _Requirements: 5.1, 5.7_
  
  - [ ] 2.2 Write property test for token counting accuracy
    - **Property 23: Provider-Specific Token Counting**
    - **Validates: Requirements 5.1**
  
  - [ ] 2.3 Implement message token counting
    - Implement count_messages() for all providers
    - Handle message format overhead (role, name fields)
    - Handle special tokens correctly per provider
    - _Requirements: 5.1, 5.7_
  
  - [ ] 2.4 Write unit tests for token counter
    - Test OpenAI counting matches tiktoken
    - Test Anthropic counting matches anthropic library
    - Test special token handling
    - Test edge cases (empty text, very long text, unicode)
    - _Requirements: 5.1, 5.7_

- [ ] 3. Implement Provider Adapters
  - [ ] 3.1 Create base adapter interface
    - Define abstract ProviderAdapter class
    - Define complete(), stream(), embed() abstract methods
    - Create adapter factory for provider selection
    - _Requirements: 1.1, 1.2, 1.3, 11.2, 11.3_
  
  - [ ] 3.2 Implement OpenAI Adapter
    - Set up AsyncOpenAI client
    - Implement complete() with function calling support
    - Implement stream() with function calling support
    - Implement embed() for embeddings
    - Implement cost calculation based on pricing
    - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.2_
  
  - [ ] 3.3 Implement Ollama Adapter
    - Set up ollama AsyncClient
    - Implement complete() for local models
    - Implement stream() for local models
    - Implement embed() for local embeddings
    - Handle function calling unsupported error
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 3.5_
  
  - [ ] 3.4 Implement Anthropic Adapter
    - Set up Anthropic client
    - Implement complete() with Claude-specific format
    - Implement stream() with Claude-specific format
    - Implement function calling translation
    - Implement cost calculation
    - _Requirements: 1.1, 1.2, 3.1, 3.2_
  
  - [ ] 3.5 Implement Google Adapter
    - Set up Google AI client
    - Implement complete() with Gemini-specific format
    - Implement stream() with Gemini-specific format
    - Implement embed() for Google embeddings
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [ ] 3.6 Write property test for cross-provider compatibility
    - **Property 1: Cross-Provider Request Compatibility**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.8**
  
  - [ ] 3.7 Write property test for function calling
    - **Property 14: Function Argument Validation**
    - **Validates: Requirements 3.6, 3.7**

- [ ] 4. Checkpoint - Ensure provider adapters work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Context Manager
  - [ ] 5.1 Create ContextManager class with session storage
    - Implement session storage (in-memory dictionary)
    - Implement inject_context() to add history to requests
    - Implement update_context() to add new messages
    - Implement session locking for thread safety
    - _Requirements: 4.1, 4.2_
  
  - [ ] 5.2 Implement context window management
    - Implement get_context_usage() to calculate usage percentage
    - Implement warning emission at 80% threshold
    - Implement compress_context() to reduce token count
    - Preserve system prompts and recent messages during compression
    - _Requirements: 4.3, 4.4, 4.7_
  
  - [ ] 5.3 Implement context manipulation operations
    - Implement manual context injection
    - Implement context insertion, deletion, reordering
    - Implement clear_context() for session cleanup
    - _Requirements: 4.5, 4.6_
  
  - [ ] 5.4 Write property test for context isolation
    - **Property 16: Per-Session History Isolation**
    - **Validates: Requirements 4.1**
  
  - [ ] 5.5 Write property test for automatic compression
    - **Property 19: Automatic Context Compression**
    - **Validates: Requirements 4.4, 4.7**
  
  - [ ] 5.6 Write unit tests for context manager
    - Test session creation and history tracking
    - Test token count calculation
    - Test compression preserves critical elements
    - Test concurrent session updates
    - _Requirements: 4.1, 4.2, 4.4, 4.7_

- [ ] 6. Implement Error Handler with Circuit Breaker
  - [ ] 6.1 Create ErrorHandler class with retry logic
    - Implement execute_with_retry() with exponential backoff
    - Implement _classify_error() for error type detection
    - Implement retry limit enforcement (max 3 retries)
    - Implement rate limit handling with wait time extraction
    - _Requirements: 7.1, 7.2, 7.3, 7.7_
  
  - [ ] 6.2 Implement Circuit Breaker pattern
    - Implement CircuitBreakerState tracking per provider
    - Implement _is_circuit_open() to check circuit state
    - Implement _record_success() and _record_failure()
    - Open circuit after 5 failures, close after 60 seconds
    - _Requirements: 7.5, 7.6_
  
  - [ ] 6.3 Write property test for retry logic
    - **Property 37: Transient Error Retry with Backoff**
    - **Validates: Requirements 7.1**
  
  - [ ] 6.4 Write property test for circuit breaker
    - **Property 41: Circuit Breaker Pattern**
    - **Validates: Requirements 7.5, 7.6**
  
  - [ ] 6.5 Write unit tests for error handler
    - Test transient error retry with backoff
    - Test permanent error no retry
    - Test rate limit wait and retry
    - Test circuit breaker opens and closes
    - Test error classification
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6, 7.7, 7.8_

- [ ] 7. Checkpoint - Ensure error handling works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Performance Monitor
  - [ ] 8.1 Create PerformanceMonitor class with metrics storage
    - Implement PerformanceMetrics data model
    - Implement record_request() to track latency, tokens, cost
    - Implement metrics storage per model/provider
    - Implement latency history tracking (last 1000 samples)
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [ ] 8.2 Implement metrics calculation and warnings
    - Implement percentile calculation (p95, p99) for latency
    - Implement success rate calculation
    - Implement slow response warning (>5000ms)
    - Implement reliability warning (>5 failures in 60s)
    - _Requirements: 6.4, 6.5, 6.8_
  
  - [ ] 8.3 Implement metrics aggregation and reporting
    - Implement get_metrics() with filtering
    - Implement metrics aggregation over time windows
    - Implement report_to_self_improvement() for integration
    - _Requirements: 6.6, 6.7_
  
  - [ ] 8.4 Write property test for cost estimation
    - **Property 31: Cost Estimation Accuracy**
    - **Validates: Requirements 6.3**
  
  - [ ] 8.5 Write unit tests for performance monitor
    - Test latency tracking and percentile calculation
    - Test token usage tracking
    - Test cost estimation
    - Test warning emission
    - Test metrics aggregation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.7, 6.8_

- [ ] 9. Implement Unified LLM Runtime Interface
  - [ ] 9.1 Create LLMRuntime class with component integration
    - Initialize all components (adapters, context manager, token counter, performance monitor, error handler)
    - Implement _get_provider() and _get_context_limit() helpers
    - Implement _estimate_cost() helper
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [ ] 9.2 Implement complete() method
    - Inject context from session if session_id provided
    - Validate token budget against context window
    - Execute request with error handler retry logic
    - Update context with response
    - Record performance metrics
    - _Requirements: 1.1, 1.2, 5.3, 6.1, 6.2_
  
  - [ ] 9.3 Implement stream() method
    - Inject context from session
    - Validate token budget
    - Stream response chunks incrementally
    - Handle stream interruption and partial responses
    - Update context with full response
    - Record performance metrics
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [ ] 9.4 Implement embed() method
    - Route to appropriate provider adapter
    - Execute with error handler retry logic
    - Return embeddings in consistent format
    - _Requirements: 1.3_
  
  - [ ] 9.5 Write property test for streaming
    - **Property 4: Incremental Token Delivery**
    - **Validates: Requirements 2.1**
  
  - [ ] 9.6 Write property test for context window validation
    - **Property 25: Context Window Pre-Validation**
    - **Validates: Requirements 5.3**
  
  - [ ] 9.7 Write integration tests for LLM Runtime
    - Test complete() with all providers
    - Test stream() with all providers
    - Test embed() with all providers
    - Test context injection and updates
    - Test error handling and retries
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 4.1, 7.1_

- [ ] 10. Checkpoint - Ensure core runtime works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement GitHub Sync Engine
  - [ ] 11.1 Create GitHubSyncEngine class with queue
    - Implement SyncOperation data model
    - Implement pending operations queue
    - Set up httpx AsyncClient with authentication
    - Implement _generate_operation_id() and _generate_commit_message()
    - _Requirements: 9.1, 9.4_
  
  - [ ] 11.2 Implement sync operations
    - Implement queue_performance_update() to queue operations
    - Implement _format_metrics_for_readme() to create markdown
    - Implement _update_readme() to update GitHub file
    - Implement _batch_operations() to combine multiple updates
    - _Requirements: 9.1, 9.2, 9.4_
  
  - [ ] 11.3 Implement background sync loop
    - Implement _sync_loop() with batch window (5 seconds)
    - Implement _process_pending_operations() with retry logic
    - Implement exponential backoff for GitHub failures (5 retries)
    - Implement persistent queue for unavailability
    - _Requirements: 9.5, 9.6_
  
  - [ ] 11.4 Write property test for README-only updates
    - **Property 50: README-Only File Updates**
    - **Validates: Requirements 9.2, 9.3**
  
  - [ ] 11.5 Write unit tests for GitHub sync
    - Test queue operation adds to queue
    - Test README.md update (mock GitHub API)
    - Test retry logic on failure
    - Test batch operations
    - Test commit message format
    - _Requirements: 9.1, 9.2, 9.4, 9.5, 9.6_

- [ ] 12. Implement Security Features
  - [ ] 12.1 Implement credential sanitization
    - Implement log filtering to redact API keys
    - Implement error message sanitization
    - Add credential patterns to redaction list
    - _Requirements: 12.1, 12.3_
  
  - [ ] 12.2 Implement PII redaction
    - Implement PII detection patterns (email, phone, address)
    - Implement automatic redaction in request/response logging
    - Add configurable PII patterns
    - _Requirements: 12.4, 12.5_
  
  - [ ] 12.3 Implement TLS certificate validation
    - Configure httpx client to validate certificates
    - Reject self-signed certificates
    - Reject invalid certificates
    - _Requirements: 12.6, 12.7_
  
  - [ ] 12.4 Write property test for credential logging prevention
    - **Property 60: Credential Logging Prevention**
    - **Validates: Requirements 12.1**
  
  - [ ] 12.5 Write property test for TLS validation
    - **Property 63: TLS Certificate Validation**
    - **Validates: Requirements 12.6, 12.7**
  
  - [ ] 12.6 Write unit tests for security features
    - Test API key redaction in logs
    - Test error message sanitization
    - Test PII redaction
    - Test TLS certificate rejection
    - _Requirements: 12.1, 12.3, 12.4, 12.5, 12.6, 12.7_

- [ ] 13. Implement Configuration and Integration
  - [ ] 13.1 Implement configuration loading
    - Load configuration from environment variables
    - Load configuration from config files (YAML/JSON)
    - Implement configuration validation at startup
    - Provide sensible defaults for all options
    - _Requirements: 11.1, 11.5, 11.7_
  
  - [ ] 13.2 Implement integration interfaces
    - Implement Model Router integration (receive model selection)
    - Implement Verifier System hooks (register verification callbacks)
    - Implement Memory System integration (accept context injection)
    - Implement Self-Improvement Engine reporting (send metrics)
    - _Requirements: 8.1, 8.3, 8.4, 8.5, 6.6_
  
  - [ ] 13.3 Implement health check and graceful shutdown
    - Implement health check endpoint
    - Implement graceful shutdown (complete in-flight requests)
    - Implement shutdown timeout (30 seconds max)
    - _Requirements: 8.6, 8.7_
  
  - [ ] 13.4 Write unit tests for configuration
    - Test configuration loading from env vars
    - Test configuration loading from files
    - Test configuration validation
    - Test default values
    - Test invalid configuration errors
    - _Requirements: 11.1, 11.5, 11.7_

- [ ] 14. Checkpoint - Ensure all components integrated
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Implement Adversarial Property-Based Tests
  - [ ] 15.1 Write streaming adversarial tests
    - Test stream interruption with partial response
    - Test empty chunks handling
    - Test malformed JSON in stream
    - Test very slow streams with timeout
    - Test unicode and special characters in stream
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [ ] 15.2 Write function calling adversarial tests
    - Test invalid JSON arguments
    - Test missing required arguments
    - Test non-existent function calls
    - Test parallel function calls with failures
    - Test multi-turn circular function calls
    - _Requirements: 3.3, 3.4, 3.6, 3.7_
  
  - [ ] 15.3 Write context management adversarial tests
    - Test filling context to exact limit
    - Test exceeding context by 1 token
    - Test compression with only system message
    - Test concurrent updates to same session
    - Test very large messages (10K tokens)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.7_
  
  - [ ] 15.4 Write token counting adversarial tests
    - Test text with only special tokens
    - Test mixed languages (English, Chinese, Arabic)
    - Test very long text (100K characters)
    - Test empty text
    - Test emoji and unicode
    - _Requirements: 5.1, 5.7_
  
  - [ ] 15.5 Write error handling adversarial tests
    - Test 5 consecutive failures (circuit opens)
    - Test rate limit without Retry-After header
    - Test network timeout during request
    - Test network timeout during stream
    - Test provider 500 error (retry)
    - Test provider 400 error (no retry)
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6, 7.7, 7.8_
  
  - [ ] 15.6 Write security adversarial tests
    - Test API key in request header (redacted in logs)
    - Test error message contains API key (sanitized)
    - Test request with PII (redacted in logs)
    - Test invalid TLS certificate (rejected)
    - Test self-signed certificate (rejected)
    - _Requirements: 12.1, 12.3, 12.4, 12.5, 12.6, 12.7_

- [ ] 16. Final Integration Testing and Documentation
  - [ ] 16.1 Run full integration test suite
    - Test end-to-end flows with all providers
    - Test Model Router → LLM Runtime → Verifier System flow
    - Test Memory System context injection
    - Test Self-Improvement Engine metrics reporting
    - Test GitHub sync with real repository (or mock)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1_
  
  - [ ] 16.2 Create API documentation
    - Document all public interfaces and methods
    - Provide usage examples for each provider
    - Document configuration options
    - Document error codes and handling
    - _Requirements: 1.1, 1.2, 1.3, 11.1, 11.4_
  
  - [ ] 16.3 Create README.md with performance metrics
    - Document system architecture
    - Document supported providers and features
    - Include performance benchmarks
    - Include setup and configuration instructions
    - _Requirements: 9.2, 9.4_

- [ ] 17. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples and edge cases
- Adversarial tests ensure robustness against malicious or malformed inputs
- Implementation uses Python with async/await for concurrent operations
- All network operations use httpx for async HTTP requests
- Provider-specific libraries: ollama-python, openai, anthropic
- Token counting uses tiktoken (OpenAI) and anthropic library
