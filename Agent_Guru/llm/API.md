# LLM Runtime - API Reference

## Overview

The `Agent_Guru.llm` package provides a unified interface for running language models
across Ollama (local), OpenAI, Anthropic, and Google providers.

---

## Quick Start

```python
from Agent_Guru.llm import LLMRuntime, RuntimeConfig, OpenAIConfig, CompletionRequest, Message

config = RuntimeConfig(
    openai_config=OpenAIConfig(api_key="sk-..."),
)
runtime = LLMRuntime.from_config(config)

response = await runtime.complete(
    CompletionRequest(
        model="gpt-3.5-turbo",
        messages=[Message(role="user", content="Hello!")],
    )
)
print(response.content)
```

---

## LLMRuntime

Main entry point for all LLM operations.

### Factory

```python
LLMRuntime.from_config(config: RuntimeConfig) -> LLMRuntime
```

Wires all components (adapters, context manager, token counter, performance monitor,
error handler) from a single `RuntimeConfig`.

### Methods

#### `complete(request: CompletionRequest) -> CompletionResponse`

Non-streaming completion. Injects session context, validates token budget,
executes with retry logic, updates context, and records metrics.

**Raises:**
- `ContextWindowExceededError` - request exceeds model context limit
- `CircuitBreakerOpenError` - provider circuit is open after repeated failures

#### `stream(request: CompletionRequest) -> AsyncIterator[StreamChunk]`

Streaming completion. Yields `StreamChunk` objects incrementally.
Updates context and records metrics after the stream completes.

**Raises:**
- `ContextWindowExceededError` - request exceeds model context limit

#### `embed(text: str | list[str], model: str) -> list[list[float]]`

Generate embeddings. Routes to the appropriate provider adapter.

---

## Configuration

### RuntimeConfig

```python
RuntimeConfig(
    openai_config: OpenAIConfig = OpenAIConfig(),
    anthropic_config: AnthropicConfig = AnthropicConfig(),
    google_config: GoogleConfig = GoogleConfig(),
    ollama_config: OllamaConfig = OllamaConfig(),
    max_retries: int = 3,
    initial_backoff_ms: float = 500.0,
    max_backoff_ms: float = 30000.0,
    circuit_breaker_threshold: int = 5,
    circuit_breaker_timeout_s: float = 60.0,
    compression_threshold: float = 0.8,
    max_history_messages: int = 100,
    slow_threshold_ms: float = 5000.0,
    failure_threshold: int = 5,
    github_repo_url: str | None = None,
    github_branch: str = "main",
    github_auth_token: str | None = None,
)
```

### Provider Configs

| Class | Key Field | Default |
|---|---|---|
| `OpenAIConfig` | `api_key` | `""` |
| `AnthropicConfig` | `api_key` | `""` |
| `GoogleConfig` | `api_key` | `""` |
| `OllamaConfig` | `host` | `"http://localhost:11434"` |

### Loading from Environment

```python
from Agent_Guru.llm import load_config_from_env
config = load_config_from_env()
```

Environment variables: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`,
`OLLAMA_HOST`, `LLM_MAX_RETRIES`, `LLM_SLOW_THRESHOLD_MS`, `GITHUB_REPO_URL`,
`GITHUB_BRANCH`, `GITHUB_AUTH_TOKEN`.

### Loading from File

```python
from Agent_Guru.llm import load_config_from_file
config = load_config_from_file("config.json")  # or config.yaml
```

---

## Data Models

### Message

```python
Message(role: str, content: str, name: str | None = None)
```

`role` is one of `"system"`, `"user"`, `"assistant"`, `"function"`.

### CompletionRequest

```python
CompletionRequest(
    model: str,
    messages: list[Message],
    max_tokens: int | None = None,
    temperature: float = 0.7,
    stream: bool = False,
    functions: list[FunctionDefinition] | None = None,
    session_id: str | None = None,
)
```

Set `session_id` to enable automatic context injection and history tracking.

### CompletionResponse

```python
CompletionResponse(
    content: str,
    model: str,
    provider: ModelProvider,
    finish_reason: str,
    usage: TokenUsage,
    latency_ms: float,
    timestamp: datetime,
    function_call: dict | None = None,
)
```

### StreamChunk

```python
StreamChunk(
    content: str,
    finish_reason: str | None = None,
    function_call: dict | None = None,
)
```

### TokenUsage

```python
TokenUsage(
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    estimated_cost: float = 0.0,
)
```

### FunctionDefinition

```python
FunctionDefinition(
    name: str,
    description: str,
    parameters: dict,  # JSON Schema object
)
```

---

## Provider Routing

Model names are automatically routed to the correct provider:

| Prefix | Provider |
|---|---|
| `gpt-`, `text-embedding-`, `o1-`, `o3-` | OpenAI |
| `claude-` | Anthropic |
| `gemini-` | Google |
| anything else | Ollama (local) |

---

## Error Codes

| Exception | Cause |
|---|---|
| `ContextWindowExceededError` | Request token count exceeds model limit |
| `CircuitBreakerOpenError` | Provider has too many recent failures |
| `ProviderNotSupportedError` | Operation not supported by provider (e.g. function calling on Ollama) |

---

## Error Handling & Retries

Transient errors (network timeouts, 5xx responses, rate limits) are retried
automatically with exponential backoff. Permanent errors (4xx, invalid requests)
are not retried.

The circuit breaker opens after `circuit_breaker_threshold` consecutive failures
and resets after `circuit_breaker_timeout_s` seconds.

---

## Context Management

Pass `session_id` in `CompletionRequest` to enable automatic multi-turn context:

```python
# Turn 1
await runtime.complete(CompletionRequest(
    model="gpt-3.5-turbo",
    messages=[Message(role="user", content="My name is Alice")],
    session_id="my-session",
))

# Turn 2 - previous messages injected automatically
await runtime.complete(CompletionRequest(
    model="gpt-3.5-turbo",
    messages=[Message(role="user", content="What is my name?")],
    session_id="my-session",
))
```

Context is automatically compressed when it reaches `compression_threshold`
(default 80%) of the model's context window.

---

## Performance Monitoring

```python
metrics = await runtime.performance_monitor.get_metrics()
# metrics["openai:gpt-3.5-turbo"].avg_latency_ms
# metrics["openai:gpt-3.5-turbo"].success_rate
# metrics["openai:gpt-3.5-turbo"].total_requests
```
