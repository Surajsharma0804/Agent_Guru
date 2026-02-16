# Design Document: LLM Runtime System

## Overview

The LLM Runtime System (guru-llm-runtime) is the foundational execution layer of Agent_Guru that provides a unified, high-performance interface for running language models across multiple providers. This is NOT a simple API wrapper - it provides intelligent value-add features including real-time streaming, function calling orchestration, adaptive context management, token optimization, and comprehensive performance monitoring.

**Core Innovation**: The runtime abstracts provider-specific differences while preserving access to advanced features, enabling seamless model switching without code changes. It implements intelligent context window management that automatically compresses history when approaching limits, token optimization that reduces costs by 20-40%, and performance monitoring that enables data-driven model selection.

**Key Capabilities**:
- **Unified Interface**: Single API for Ollama, OpenAI, Anthropic, Google models
- **Streaming Support**: Real-time token delivery with interruption handling
- **Function Calling**: Provider-agnostic tool use with multi-turn support
- **Context Management**: Automatic history tracking and compression
- **Token Optimization**: Accurate counting and budget enforcement
- **Performance Monitoring**: Latency, cost, and reliability tracking
- **Error Handling**: Retry with exponential backoff and circuit breaker
- **GitHub Integration**: Performance data sync to README.md only

**Architecture Principles**:
1. **Provider Agnostic**: Abstract differences, expose common capabilities
2. **Performance First**: Sub-500ms overhead for 95% of requests
3. **Cost Conscious**: Minimize token usage through optimization
4. **Observable**: Comprehensive metrics for debugging and optimization
5. **Resilient**: Graceful degradation and automatic retry
6. **Testable**: Property-based tests for adversarial scenarios

The system uses Python with:
- **httpx**: For async HTTP requests to cloud providers
- **ollama-python**: For local Ollama integration
- **tiktoken**: For OpenAI token counting
- **anthropic**: For Anthropic-specific tokenization
- **asyncio**: For concurrent request handling
- **pydantic**: For request/response validation


## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      LLM Runtime System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │   Unified API    │  │     Context      │  │     Token     │ │
│  │    Interface     │  │    Manager       │  │   Counter     │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│           │                     │                     │          │
│           └─────────────────────┴─────────────────────┘          │
│                              │                                   │
│                    ┌─────────▼─────────┐                        │
│                    │   Provider        │                        │
│                    │   Router          │                        │
│                    └─────────┬─────────┘                        │
│                              │                                   │
│           ┌──────────────────┼──────────────────┐               │
│           │                  │                  │               │
│  ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐      │
│  │     Ollama      │ │   OpenAI    │ │   Anthropic     │      │
│  │    Adapter      │ │   Adapter   │ │    Adapter      │      │
│  └─────────────────┘ └─────────────┘ └─────────────────┘      │
│           │                  │                  │               │
│           └──────────────────┼──────────────────┘               │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────┐       │
│  │           Performance Monitor                        │       │
│  │  (Latency, Token Usage, Cost, Reliability)          │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────┐       │
│  │           Error Handler & Circuit Breaker            │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                    Integration Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  Model Router │ Verifier │ Self-Improvement │ Memory System     │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   GitHub Sync     │
                    │     Engine        │
                    └───────────────────┘
```

### Component Interaction Flow

1. **Request Flow**:
   - Model Router selects model → LLM Runtime receives request
   - Context Manager injects conversation history
   - Token Counter validates request fits in context window
   - Provider Router selects appropriate adapter
   - Adapter translates request to provider format
   - Request sent to provider (streaming or non-streaming)

2. **Response Flow**:
   - Provider returns response (streaming or complete)
   - Adapter translates response to unified format
   - Context Manager updates session history
   - Token Counter records actual usage
   - Performance Monitor records metrics
   - Response returned to caller

3. **Function Calling Flow**:
   - Request includes function definitions
   - Adapter translates to provider-specific format
   - Model requests function execution
   - Runtime returns function call to caller
   - Caller executes function, returns result
   - Runtime sends result back to model
   - Multi-turn continues until completion

4. **Error Flow**:
   - Provider returns error
   - Error Handler classifies error (transient/permanent)
   - If transient: retry with exponential backoff
   - If rate limit: wait specified duration
   - If permanent: return error immediately
   - Circuit Breaker opens after repeated failures
   - Performance Monitor records failure


## Components and Interfaces

### 1. Unified API Interface (`llm_runtime.py`)

The main interface for all LLM operations.

```python
from typing import Dict, Any, Optional, List, AsyncIterator, Union
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio

class ModelProvider(Enum):
    """Supported model providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"

@dataclass
class Message:
    """Chat message."""
    role: str  # "system", "user", "assistant", "function"
    content: str
    name: Optional[str] = None  # For function messages
    function_call: Optional[Dict[str, Any]] = None

@dataclass
class FunctionDefinition:
    """Function definition for function calling."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema

@dataclass
class CompletionRequest:
    """Request for text completion or chat."""
    model: str
    messages: List[Message]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    functions: Optional[List[FunctionDefinition]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class CompletionResponse:
    """Response from completion request."""
    content: str
    model: str
    provider: ModelProvider
    finish_reason: str
    usage: TokenUsage
    function_call: Optional[Dict[str, Any]] = None
    latency_ms: float
    timestamp: datetime

@dataclass
class TokenUsage:
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float

@dataclass
class StreamChunk:
    """Streaming response chunk."""
    content: str
    finish_reason: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None

class LLMRuntime:
    """
    Main interface for LLM operations.
    
    Provides unified API for all model providers with streaming,
    function calling, context management, and performance monitoring.
    """
    
    def __init__(
        self,
        config: RuntimeConfig,
        context_manager: ContextManager,
        token_counter: TokenCounter,
        performance_monitor: PerformanceMonitor,
        error_handler: ErrorHandler
    ):
        """Initialize LLM Runtime."""
        self.config = config
        self.context_manager = context_manager
        self.token_counter = token_counter
        self.performance_monitor = performance_monitor
        self.error_handler = error_handler
        
        # Initialize provider adapters
        self.adapters = {
            ModelProvider.OLLAMA: OllamaAdapter(config.ollama_config),
            ModelProvider.OPENAI: OpenAIAdapter(config.openai_config),
            ModelProvider.ANTHROPIC: AnthropicAdapter(config.anthropic_config),
            ModelProvider.GOOGLE: GoogleAdapter(config.google_config)
        }
    
    async def complete(
        self,
        request: CompletionRequest
    ) -> CompletionResponse:
        """
        Execute completion request (non-streaming).
        
        Args:
            request: Completion request
            
        Returns:
            CompletionResponse with full response
        """
        start_time = datetime.now()
        
        # Get provider for model
        provider = self._get_provider(request.model)
        adapter = self.adapters[provider]
        
        # Inject context if session_id provided
        if request.session_id:
            request.messages = self.context_manager.inject_context(
                request.session_id, request.messages
            )
        
        # Validate token budget
        estimated_tokens = self.token_counter.count_messages(
            request.messages, request.model
        )
        if request.max_tokens:
            estimated_tokens += request.max_tokens
        
        context_limit = self._get_context_limit(request.model)
        if estimated_tokens > context_limit:
            raise ContextWindowExceededError(
                f"Estimated {estimated_tokens} tokens exceeds limit {context_limit}"
            )
        
        # Execute with retry logic
        response = await self.error_handler.execute_with_retry(
            lambda: adapter.complete(request)
        )
        
        # Update context
        if request.session_id:
            self.context_manager.update_context(
                request.session_id,
                request.messages[-1],  # User message
                Message(role="assistant", content=response.content)
            )
        
        # Record metrics
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        response.latency_ms = latency_ms
        
        await self.performance_monitor.record_request(
            model=request.model,
            provider=provider,
            latency_ms=latency_ms,
            tokens=response.usage.total_tokens,
            cost=response.usage.estimated_cost,
            success=True
        )
        
        return response
    
    async def stream(
        self,
        request: CompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """
        Execute streaming completion request.
        
        Args:
            request: Completion request with stream=True
            
        Yields:
            StreamChunk for each token/chunk
        """
        start_time = datetime.now()
        
        # Get provider and adapter
        provider = self._get_provider(request.model)
        adapter = self.adapters[provider]
        
        # Inject context
        if request.session_id:
            request.messages = self.context_manager.inject_context(
                request.session_id, request.messages
            )
        
        # Validate token budget
        estimated_tokens = self.token_counter.count_messages(
            request.messages, request.model
        )
        context_limit = self._get_context_limit(request.model)
        if estimated_tokens > context_limit:
            raise ContextWindowExceededError(
                f"Estimated {estimated_tokens} tokens exceeds limit {context_limit}"
            )
        
        # Stream response
        full_content = ""
        try:
            async for chunk in adapter.stream(request):
                full_content += chunk.content
                yield chunk
        except Exception as e:
            # Record partial response
            await self.performance_monitor.record_request(
                model=request.model,
                provider=provider,
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
                tokens=self.token_counter.count_text(full_content, request.model),
                cost=0.0,  # Estimate later
                success=False,
                error=str(e)
            )
            raise
        
        # Update context with full response
        if request.session_id:
            self.context_manager.update_context(
                request.session_id,
                request.messages[-1],
                Message(role="assistant", content=full_content)
            )
        
        # Record metrics
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        tokens = self.token_counter.count_text(full_content, request.model)
        
        await self.performance_monitor.record_request(
            model=request.model,
            provider=provider,
            latency_ms=latency_ms,
            tokens=tokens,
            cost=self._estimate_cost(tokens, request.model),
            success=True
        )
    
    async def embed(
        self,
        text: Union[str, List[str]],
        model: str
    ) -> List[List[float]]:
        """
        Generate embeddings for text.
        
        Args:
            text: Text or list of texts to embed
            model: Embedding model name
            
        Returns:
            List of embedding vectors
        """
        provider = self._get_provider(model)
        adapter = self.adapters[provider]
        
        return await self.error_handler.execute_with_retry(
            lambda: adapter.embed(text, model)
        )
    
    def _get_provider(self, model: str) -> ModelProvider:
        """Determine provider from model name."""
        if model.startswith("gpt-") or model.startswith("text-embedding"):
            return ModelProvider.OPENAI
        elif model.startswith("claude-"):
            return ModelProvider.ANTHROPIC
        elif model.startswith("gemini-"):
            return ModelProvider.GOOGLE
        else:
            return ModelProvider.OLLAMA
    
    def _get_context_limit(self, model: str) -> int:
        """Get context window limit for model."""
        # Model-specific limits
        limits = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-3.5-turbo": 4096,
            "claude-3-opus": 200000,
            "claude-3-sonnet": 200000,
            "gemini-pro": 32768,
        }
        
        for prefix, limit in limits.items():
            if model.startswith(prefix):
                return limit
        
        # Default for unknown models
        return 4096
    
    def _estimate_cost(self, tokens: int, model: str) -> float:
        """Estimate cost for token usage."""
        # Pricing per 1K tokens (approximate)
        pricing = {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.002,
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003,
        }
        
        for prefix, price_per_1k in pricing.items():
            if model.startswith(prefix):
                return (tokens / 1000) * price_per_1k
        
        return 0.0  # Local models are free
```


### 2. Context Manager (`context_manager.py`)

Manages conversation history and context window optimization.

```python
from typing import List, Dict, Optional
from dataclasses import dataclass
from collections import defaultdict
import asyncio

@dataclass
class SessionContext:
    """Context for a conversation session."""
    session_id: str
    messages: List[Message]
    token_count: int
    created_at: datetime
    last_updated: datetime
    metadata: Dict[str, Any]

class ContextManager:
    """
    Manages conversation history and context windows.
    
    Features:
    - Per-session history tracking
    - Automatic context compression
    - Token budget management
    - Context injection and manipulation
    """
    
    def __init__(
        self,
        token_counter: TokenCounter,
        compression_threshold: float = 0.8,  # Compress at 80% of limit
        max_history_messages: int = 100
    ):
        """Initialize context manager."""
        self.token_counter = token_counter
        self.compression_threshold = compression_threshold
        self.max_history_messages = max_history_messages
        self.sessions: Dict[str, SessionContext] = {}
        self._lock = asyncio.Lock()
    
    def inject_context(
        self,
        session_id: str,
        messages: List[Message]
    ) -> List[Message]:
        """
        Inject conversation history into messages.
        
        Args:
            session_id: Session identifier
            messages: Current messages
            
        Returns:
            Messages with history injected
        """
        if session_id not in self.sessions:
            return messages
        
        context = self.sessions[session_id]
        
        # Combine history with new messages
        # Keep system message first if present
        system_messages = [m for m in messages if m.role == "system"]
        user_messages = [m for m in messages if m.role != "system"]
        
        return system_messages + context.messages + user_messages
    
    async def update_context(
        self,
        session_id: str,
        user_message: Message,
        assistant_message: Message
    ) -> None:
        """
        Update session context with new messages.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            assistant_message: Assistant's response
        """
        async with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = SessionContext(
                    session_id=session_id,
                    messages=[],
                    token_count=0,
                    created_at=datetime.now(),
                    last_updated=datetime.now(),
                    metadata={}
                )
            
            context = self.sessions[session_id]
            context.messages.extend([user_message, assistant_message])
            context.last_updated = datetime.now()
            
            # Update token count
            context.token_count = self.token_counter.count_messages(
                context.messages, "gpt-3.5-turbo"  # Use as baseline
            )
            
            # Trim if exceeds max history
            if len(context.messages) > self.max_history_messages:
                # Keep most recent messages
                context.messages = context.messages[-self.max_history_messages:]
    
    def get_context_usage(
        self,
        session_id: str,
        model: str
    ) -> Dict[str, Any]:
        """
        Get current context usage for session.
        
        Args:
            session_id: Session identifier
            model: Model name for context limit
            
        Returns:
            Dictionary with usage stats
        """
        if session_id not in self.sessions:
            return {
                "token_count": 0,
                "message_count": 0,
                "usage_percentage": 0.0
            }
        
        context = self.sessions[session_id]
        context_limit = self._get_context_limit(model)
        
        return {
            "token_count": context.token_count,
            "message_count": len(context.messages),
            "context_limit": context_limit,
            "usage_percentage": (context.token_count / context_limit) * 100
        }
    
    async def compress_context(
        self,
        session_id: str,
        target_tokens: int
    ) -> None:
        """
        Compress context to fit within token budget.
        
        Strategies:
        1. Remove oldest messages (keep system prompt)
        2. Summarize middle messages
        3. Keep most recent messages
        
        Args:
            session_id: Session identifier
            target_tokens: Target token count
        """
        if session_id not in self.sessions:
            return
        
        async with self._lock:
            context = self.sessions[session_id]
            
            # Strategy 1: Remove oldest messages
            while context.token_count > target_tokens and len(context.messages) > 2:
                # Keep first message if it's a system message
                if context.messages[0].role == "system":
                    # Remove second message
                    context.messages.pop(1)
                else:
                    # Remove first message
                    context.messages.pop(0)
                
                # Recalculate token count
                context.token_count = self.token_counter.count_messages(
                    context.messages, "gpt-3.5-turbo"
                )
    
    def clear_context(self, session_id: str) -> None:
        """Clear context for session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def _get_context_limit(self, model: str) -> int:
        """Get context limit for model."""
        limits = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-3.5-turbo": 4096,
            "claude-3-opus": 200000,
            "claude-3-sonnet": 200000,
            "gemini-pro": 32768,
        }
        
        for prefix, limit in limits.items():
            if model.startswith(prefix):
                return limit
        
        return 4096
```


### 3. Token Counter (`token_counter.py`)

Accurate token counting per provider.

```python
from typing import List, Dict, Any
import tiktoken
from anthropic import Anthropic

class TokenCounter:
    """
    Accurate token counting for all providers.
    
    Uses provider-specific tokenizers:
    - OpenAI: tiktoken
    - Anthropic: anthropic library
    - Google: approximation (no official tokenizer)
    - Ollama: approximation based on model
    """
    
    def __init__(self):
        """Initialize token counter."""
        self.openai_encoders = {}
        self.anthropic_client = Anthropic()
    
    def count_messages(
        self,
        messages: List[Message],
        model: str
    ) -> int:
        """
        Count tokens in message list.
        
        Args:
            messages: List of messages
            model: Model name
            
        Returns:
            Total token count
        """
        provider = self._get_provider(model)
        
        if provider == "openai":
            return self._count_openai_messages(messages, model)
        elif provider == "anthropic":
            return self._count_anthropic_messages(messages, model)
        elif provider == "google":
            return self._count_google_messages(messages, model)
        else:  # ollama
            return self._count_ollama_messages(messages, model)
    
    def count_text(
        self,
        text: str,
        model: str
    ) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count
            model: Model name
            
        Returns:
            Token count
        """
        provider = self._get_provider(model)
        
        if provider == "openai":
            return self._count_openai_text(text, model)
        elif provider == "anthropic":
            return self._count_anthropic_text(text, model)
        elif provider == "google":
            return self._count_google_text(text, model)
        else:  # ollama
            return self._count_ollama_text(text, model)
    
    def _count_openai_messages(
        self,
        messages: List[Message],
        model: str
    ) -> int:
        """Count tokens for OpenAI messages."""
        encoding = self._get_openai_encoder(model)
        
        # OpenAI message format overhead
        tokens_per_message = 3  # <|start|>role/name\n{content}<|end|>\n
        tokens_per_name = 1
        
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            num_tokens += len(encoding.encode(message.content))
            if message.name:
                num_tokens += tokens_per_name
        
        num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
        
        return num_tokens
    
    def _count_openai_text(self, text: str, model: str) -> int:
        """Count tokens for OpenAI text."""
        encoding = self._get_openai_encoder(model)
        return len(encoding.encode(text))
    
    def _get_openai_encoder(self, model: str):
        """Get tiktoken encoder for model."""
        if model not in self.openai_encoders:
            try:
                self.openai_encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Default to cl100k_base for unknown models
                self.openai_encoders[model] = tiktoken.get_encoding("cl100k_base")
        
        return self.openai_encoders[model]
    
    def _count_anthropic_messages(
        self,
        messages: List[Message],
        model: str
    ) -> int:
        """Count tokens for Anthropic messages."""
        # Anthropic uses their own tokenizer
        # Approximate by counting text
        total = 0
        for message in messages:
            total += self._count_anthropic_text(message.content, model)
        return total
    
    def _count_anthropic_text(self, text: str, model: str) -> int:
        """Count tokens for Anthropic text."""
        # Use Anthropic's count_tokens method
        return self.anthropic_client.count_tokens(text)
    
    def _count_google_messages(
        self,
        messages: List[Message],
        model: str
    ) -> int:
        """Count tokens for Google messages (approximation)."""
        # Google doesn't provide official tokenizer
        # Approximate: 1 token ≈ 4 characters
        total = 0
        for message in messages:
            total += len(message.content) // 4
        return total
    
    def _count_google_text(self, text: str, model: str) -> int:
        """Count tokens for Google text (approximation)."""
        return len(text) // 4
    
    def _count_ollama_messages(
        self,
        messages: List[Message],
        model: str
    ) -> int:
        """Count tokens for Ollama messages (approximation)."""
        # Ollama models vary, use conservative estimate
        # 1 token ≈ 3.5 characters
        total = 0
        for message in messages:
            total += len(message.content) // 3
        return total
    
    def _count_ollama_text(self, text: str, model: str) -> int:
        """Count tokens for Ollama text (approximation)."""
        return len(text) // 3
    
    def _get_provider(self, model: str) -> str:
        """Determine provider from model name."""
        if model.startswith("gpt-") or model.startswith("text-embedding"):
            return "openai"
        elif model.startswith("claude-"):
            return "anthropic"
        elif model.startswith("gemini-"):
            return "google"
        else:
            return "ollama"
```


### 4. Provider Adapters

Each provider has an adapter that translates between unified API and provider-specific format.

#### OpenAI Adapter (`adapters/openai_adapter.py`)

```python
from typing import AsyncIterator
import httpx
from openai import AsyncOpenAI

class OpenAIAdapter:
    """Adapter for OpenAI API."""
    
    def __init__(self, config: OpenAIConfig):
        """Initialize OpenAI adapter."""
        self.client = AsyncOpenAI(api_key=config.api_key)
        self.config = config
    
    async def complete(
        self,
        request: CompletionRequest
    ) -> CompletionResponse:
        """Execute completion request."""
        # Translate to OpenAI format
        openai_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]
        
        # Add function calling if present
        kwargs = {}
        if request.functions:
            kwargs["functions"] = [
                {
                    "name": f.name,
                    "description": f.description,
                    "parameters": f.parameters
                }
                for f in request.functions
            ]
            if request.function_call:
                kwargs["function_call"] = request.function_call
        
        # Execute request
        response = await self.client.chat.completions.create(
            model=request.model,
            messages=openai_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **kwargs
        )
        
        # Extract response
        choice = response.choices[0]
        
        # Handle function call
        function_call = None
        if choice.message.function_call:
            function_call = {
                "name": choice.message.function_call.name,
                "arguments": choice.message.function_call.arguments
            }
        
        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=ModelProvider.OPENAI,
            finish_reason=choice.finish_reason,
            usage=TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                estimated_cost=self._calculate_cost(response.usage, request.model)
            ),
            function_call=function_call,
            latency_ms=0.0,  # Set by caller
            timestamp=datetime.now()
        )
    
    async def stream(
        self,
        request: CompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """Execute streaming completion."""
        openai_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]
        
        kwargs = {}
        if request.functions:
            kwargs["functions"] = [
                {
                    "name": f.name,
                    "description": f.description,
                    "parameters": f.parameters
                }
                for f in request.functions
            ]
        
        stream = await self.client.chat.completions.create(
            model=request.model,
            messages=openai_messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
            **kwargs
        )
        
        async for chunk in stream:
            if not chunk.choices:
                continue
            
            choice = chunk.choices[0]
            delta = choice.delta
            
            # Handle function call in stream
            function_call = None
            if delta.function_call:
                function_call = {
                    "name": delta.function_call.name,
                    "arguments": delta.function_call.arguments
                }
            
            yield StreamChunk(
                content=delta.content or "",
                finish_reason=choice.finish_reason,
                function_call=function_call
            )
    
    async def embed(
        self,
        text: Union[str, List[str]],
        model: str
    ) -> List[List[float]]:
        """Generate embeddings."""
        if isinstance(text, str):
            text = [text]
        
        response = await self.client.embeddings.create(
            model=model,
            input=text
        )
        
        return [item.embedding for item in response.data]
    
    def _calculate_cost(
        self,
        usage: Any,
        model: str
    ) -> float:
        """Calculate cost for usage."""
        # Pricing per 1K tokens
        pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        }
        
        for prefix, prices in pricing.items():
            if model.startswith(prefix):
                prompt_cost = (usage.prompt_tokens / 1000) * prices["prompt"]
                completion_cost = (usage.completion_tokens / 1000) * prices["completion"]
                return prompt_cost + completion_cost
        
        return 0.0
```

#### Ollama Adapter (`adapters/ollama_adapter.py`)

```python
import ollama
from typing import AsyncIterator

class OllamaAdapter:
    """Adapter for Ollama local models."""
    
    def __init__(self, config: OllamaConfig):
        """Initialize Ollama adapter."""
        self.client = ollama.AsyncClient(host=config.host)
        self.config = config
    
    async def complete(
        self,
        request: CompletionRequest
    ) -> CompletionResponse:
        """Execute completion request."""
        # Convert messages to Ollama format
        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]
        
        # Ollama doesn't support function calling natively
        if request.functions:
            raise NotImplementedError(
                "Function calling not supported for Ollama models"
            )
        
        response = await self.client.chat(
            model=request.model,
            messages=messages,
            options={
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        )
        
        return CompletionResponse(
            content=response["message"]["content"],
            model=request.model,
            provider=ModelProvider.OLLAMA,
            finish_reason="stop",
            usage=TokenUsage(
                prompt_tokens=response.get("prompt_eval_count", 0),
                completion_tokens=response.get("eval_count", 0),
                total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
                estimated_cost=0.0  # Local models are free
            ),
            function_call=None,
            latency_ms=0.0,
            timestamp=datetime.now()
        )
    
    async def stream(
        self,
        request: CompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """Execute streaming completion."""
        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
        ]
        
        stream = await self.client.chat(
            model=request.model,
            messages=messages,
            stream=True,
            options={
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        )
        
        async for chunk in stream:
            if "message" in chunk:
                yield StreamChunk(
                    content=chunk["message"]["content"],
                    finish_reason="stop" if chunk.get("done") else None
                )
    
    async def embed(
        self,
        text: Union[str, List[str]],
        model: str
    ) -> List[List[float]]:
        """Generate embeddings."""
        if isinstance(text, str):
            text = [text]
        
        embeddings = []
        for t in text:
            response = await self.client.embeddings(
                model=model,
                prompt=t
            )
            embeddings.append(response["embedding"])
        
        return embeddings
```


### 5. Performance Monitor (`performance_monitor.py`)

Tracks latency, token usage, costs, and reliability.

```python
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

@dataclass
class PerformanceMetrics:
    """Performance metrics for a model/provider."""
    model: str
    provider: ModelProvider
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_tokens: int
    total_cost: float
    success_rate: float
    last_updated: datetime

class PerformanceMonitor:
    """
    Monitors and tracks performance metrics.
    
    Features:
    - Request latency tracking
    - Token usage and cost tracking
    - Success/failure rate monitoring
    - Provider reliability tracking
    - Metrics reporting to Self-Improvement Engine
    """
    
    def __init__(
        self,
        slow_threshold_ms: float = 5000.0,
        failure_threshold: int = 5
    ):
        """Initialize performance monitor."""
        self.slow_threshold_ms = slow_threshold_ms
        self.failure_threshold = failure_threshold
        
        # Metrics storage
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.latency_history: Dict[str, List[float]] = defaultdict(list)
        self.recent_failures: Dict[str, List[datetime]] = defaultdict(list)
        
        self._lock = asyncio.Lock()
    
    async def record_request(
        self,
        model: str,
        provider: ModelProvider,
        latency_ms: float,
        tokens: int,
        cost: float,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """
        Record request metrics.
        
        Args:
            model: Model name
            provider: Provider
            latency_ms: Request latency
            tokens: Token count
            cost: Estimated cost
            success: Whether request succeeded
            error: Error message if failed
        """
        async with self._lock:
            key = f"{provider.value}:{model}"
            
            # Initialize metrics if needed
            if key not in self.metrics:
                self.metrics[key] = PerformanceMetrics(
                    model=model,
                    provider=provider,
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0,
                    average_latency_ms=0.0,
                    p95_latency_ms=0.0,
                    p99_latency_ms=0.0,
                    total_tokens=0,
                    total_cost=0.0,
                    success_rate=1.0,
                    last_updated=datetime.now()
                )
            
            metrics = self.metrics[key]
            
            # Update counts
            metrics.total_requests += 1
            if success:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1
                self.recent_failures[key].append(datetime.now())
            
            # Update latency
            self.latency_history[key].append(latency_ms)
            if len(self.latency_history[key]) > 1000:
                # Keep only recent 1000 samples
                self.latency_history[key] = self.latency_history[key][-1000:]
            
            # Calculate latency metrics
            latencies = sorted(self.latency_history[key])
            metrics.average_latency_ms = sum(latencies) / len(latencies)
            metrics.p95_latency_ms = latencies[int(len(latencies) * 0.95)]
            metrics.p99_latency_ms = latencies[int(len(latencies) * 0.99)]
            
            # Update token and cost
            metrics.total_tokens += tokens
            metrics.total_cost += cost
            
            # Update success rate
            metrics.success_rate = (
                metrics.successful_requests / metrics.total_requests
            )
            
            metrics.last_updated = datetime.now()
            
            # Check for warnings
            if latency_ms > self.slow_threshold_ms:
                await self._emit_slow_warning(model, provider, latency_ms)
            
            if len(self.recent_failures[key]) >= self.failure_threshold:
                await self._emit_reliability_warning(model, provider)
    
    async def get_metrics(
        self,
        model: Optional[str] = None,
        provider: Optional[ModelProvider] = None
    ) -> Dict[str, PerformanceMetrics]:
        """
        Get performance metrics.
        
        Args:
            model: Optional model filter
            provider: Optional provider filter
            
        Returns:
            Dictionary of metrics
        """
        async with self._lock:
            if model and provider:
                key = f"{provider.value}:{model}"
                return {key: self.metrics.get(key)} if key in self.metrics else {}
            elif model:
                return {
                    k: v for k, v in self.metrics.items()
                    if v.model == model
                }
            elif provider:
                return {
                    k: v for k, v in self.metrics.items()
                    if v.provider == provider
                }
            else:
                return self.metrics.copy()
    
    async def report_to_self_improvement(self) -> None:
        """Report metrics to Self-Improvement Engine."""
        # This would integrate with Self-Improvement Engine
        # to report performance data for learning
        metrics = await self.get_metrics()
        
        # Format for Self-Improvement Engine
        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                key: {
                    "model": m.model,
                    "provider": m.provider.value,
                    "success_rate": m.success_rate,
                    "average_latency_ms": m.average_latency_ms,
                    "total_cost": m.total_cost,
                    "total_tokens": m.total_tokens
                }
                for key, m in metrics.items()
            }
        }
        
        # Send to Self-Improvement Engine
        # await self.self_improvement_client.report_metrics(report)
    
    async def _emit_slow_warning(
        self,
        model: str,
        provider: ModelProvider,
        latency_ms: float
    ) -> None:
        """Emit warning for slow response."""
        print(f"WARNING: Slow response from {provider.value}:{model} - {latency_ms}ms")
    
    async def _emit_reliability_warning(
        self,
        model: str,
        provider: ModelProvider
    ) -> None:
        """Emit warning for reliability issues."""
        key = f"{provider.value}:{model}"
        failure_count = len(self.recent_failures[key])
        print(f"WARNING: {failure_count} recent failures for {provider.value}:{model}")
```


### 6. Error Handler (`error_handler.py`)

Handles errors with retry logic and circuit breaker.

```python
from typing import Callable, TypeVar, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
from enum import Enum

T = TypeVar('T')

class ErrorType(Enum):
    """Types of errors."""
    TRANSIENT = "transient"  # Retry
    RATE_LIMIT = "rate_limit"  # Wait and retry
    PERMANENT = "permanent"  # Don't retry
    TIMEOUT = "timeout"  # Retry with longer timeout

@dataclass
class CircuitBreakerState:
    """State of circuit breaker."""
    is_open: bool
    failure_count: int
    last_failure: Optional[datetime]
    opened_at: Optional[datetime]

class ErrorHandler:
    """
    Handles errors with retry logic and circuit breaker.
    
    Features:
    - Exponential backoff retry
    - Rate limit handling
    - Circuit breaker pattern
    - Error classification
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_ms: float = 100.0,
        max_backoff_ms: float = 10000.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout_s: float = 60.0
    ):
        """Initialize error handler."""
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout_s = circuit_breaker_timeout_s
        
        # Circuit breaker state per provider
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._lock = asyncio.Lock()
    
    async def execute_with_retry(
        self,
        func: Callable[[], T],
        provider: Optional[str] = None
    ) -> T:
        """
        Execute function with retry logic.
        
        Args:
            func: Async function to execute
            provider: Provider name for circuit breaker
            
        Returns:
            Function result
            
        Raises:
            Exception if all retries exhausted
        """
        # Check circuit breaker
        if provider and await self._is_circuit_open(provider):
            raise CircuitBreakerOpenError(
                f"Circuit breaker open for {provider}"
            )
        
        last_error = None
        backoff_ms = self.initial_backoff_ms
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await func()
                
                # Success - reset circuit breaker
                if provider:
                    await self._record_success(provider)
                
                return result
                
            except Exception as e:
                last_error = e
                error_type = self._classify_error(e)
                
                # Record failure for circuit breaker
                if provider:
                    await self._record_failure(provider)
                
                # Don't retry permanent errors
                if error_type == ErrorType.PERMANENT:
                    raise
                
                # Last attempt - raise error
                if attempt >= self.max_retries:
                    raise
                
                # Handle rate limit
                if error_type == ErrorType.RATE_LIMIT:
                    wait_time = self._extract_rate_limit_wait(e)
                    await asyncio.sleep(wait_time)
                    continue
                
                # Exponential backoff
                await asyncio.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, self.max_backoff_ms)
        
        # Should never reach here, but just in case
        raise last_error
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error type."""
        error_str = str(error).lower()
        
        # Rate limit errors
        if "rate limit" in error_str or "429" in error_str:
            return ErrorType.RATE_LIMIT
        
        # Timeout errors
        if "timeout" in error_str or "timed out" in error_str:
            return ErrorType.TIMEOUT
        
        # Permanent errors
        if any(code in error_str for code in ["400", "401", "403", "404"]):
            return ErrorType.PERMANENT
        
        # Default to transient
        return ErrorType.TRANSIENT
    
    def _extract_rate_limit_wait(self, error: Exception) -> float:
        """Extract wait time from rate limit error."""
        # Try to parse Retry-After header or error message
        # Default to 1 second
        return 1.0
    
    async def _is_circuit_open(self, provider: str) -> bool:
        """Check if circuit breaker is open."""
        async with self._lock:
            if provider not in self.circuit_breakers:
                return False
            
            state = self.circuit_breakers[provider]
            
            if not state.is_open:
                return False
            
            # Check if timeout has passed
            if state.opened_at:
                elapsed = (datetime.now() - state.opened_at).total_seconds()
                if elapsed >= self.circuit_breaker_timeout_s:
                    # Try half-open state
                    state.is_open = False
                    state.failure_count = 0
                    return False
            
            return True
    
    async def _record_success(self, provider: str) -> None:
        """Record successful request."""
        async with self._lock:
            if provider in self.circuit_breakers:
                state = self.circuit_breakers[provider]
                state.failure_count = 0
                state.is_open = False
    
    async def _record_failure(self, provider: str) -> None:
        """Record failed request."""
        async with self._lock:
            if provider not in self.circuit_breakers:
                self.circuit_breakers[provider] = CircuitBreakerState(
                    is_open=False,
                    failure_count=0,
                    last_failure=None,
                    opened_at=None
                )
            
            state = self.circuit_breakers[provider]
            state.failure_count += 1
            state.last_failure = datetime.now()
            
            # Open circuit if threshold exceeded
            if state.failure_count >= self.circuit_breaker_threshold:
                state.is_open = True
                state.opened_at = datetime.now()

class CircuitBreakerOpenError(Exception):
    """Circuit breaker is open."""
    pass

class ContextWindowExceededError(Exception):
    """Context window limit exceeded."""
    pass
```


### 7. GitHub Sync Engine (`github_sync.py`)

Syncs performance data to GitHub README.md only.

```python
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import httpx

@dataclass
class SyncOperation:
    """GitHub sync operation."""
    operation_id: str
    content: str
    commit_message: str
    timestamp: datetime
    retry_count: int
    status: str  # "pending", "in_progress", "completed", "failed"

class GitHubSyncEngine:
    """
    Syncs performance data to GitHub.
    
    CRITICAL: Only updates README.md files, never creates other .md files.
    """
    
    def __init__(
        self,
        repo_url: str,
        branch: str,
        auth_token: str,
        max_retries: int = 5,
        batch_window_ms: int = 5000
    ):
        """Initialize GitHub sync engine."""
        self.repo_url = repo_url
        self.branch = branch
        self.auth_token = auth_token
        self.max_retries = max_retries
        self.batch_window_ms = batch_window_ms
        
        self.pending_operations: List[SyncOperation] = []
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"token {auth_token}"}
        )
        
        # Start background sync task
        self._sync_task = asyncio.create_task(self._sync_loop())
    
    async def queue_performance_update(
        self,
        metrics: Dict[str, Any]
    ) -> str:
        """
        Queue performance data for GitHub sync.
        
        Args:
            metrics: Performance metrics to sync
            
        Returns:
            Operation ID
        """
        # Format metrics for README.md
        content = self._format_metrics_for_readme(metrics)
        
        # Create sync operation
        operation = SyncOperation(
            operation_id=self._generate_operation_id(),
            content=content,
            commit_message=self._generate_commit_message(metrics),
            timestamp=datetime.now(),
            retry_count=0,
            status="pending"
        )
        
        self.pending_operations.append(operation)
        
        return operation.operation_id
    
    async def _sync_loop(self) -> None:
        """Background sync loop."""
        while True:
            try:
                await asyncio.sleep(self.batch_window_ms / 1000.0)
                
                if self.pending_operations:
                    await self._process_pending_operations()
                    
            except Exception as e:
                print(f"Error in sync loop: {e}")
    
    async def _process_pending_operations(self) -> None:
        """Process pending sync operations."""
        # Batch operations if multiple pending
        if len(self.pending_operations) > 1:
            batched = self._batch_operations(self.pending_operations)
            self.pending_operations = [batched]
        
        operation = self.pending_operations[0]
        operation.status = "in_progress"
        
        try:
            # Update README.md only
            await self._update_readme(operation.content, operation.commit_message)
            
            operation.status = "completed"
            self.pending_operations.pop(0)
            
        except Exception as e:
            operation.retry_count += 1
            
            if operation.retry_count >= self.max_retries:
                operation.status = "failed"
                self.pending_operations.pop(0)
                print(f"Failed to sync after {self.max_retries} retries: {e}")
            else:
                operation.status = "pending"
                # Exponential backoff
                await asyncio.sleep(2 ** operation.retry_count)
    
    async def _update_readme(
        self,
        content: str,
        commit_message: str
    ) -> None:
        """
        Update README.md file in repository.
        
        CRITICAL: Only updates README.md, never creates other files.
        """
        # Get current README.md
        readme_path = "README.md"
        api_url = f"{self.repo_url}/contents/{readme_path}"
        
        # Get current file
        response = await self.client.get(
            api_url,
            params={"ref": self.branch}
        )
        response.raise_for_status()
        
        current_file = response.json()
        current_sha = current_file["sha"]
        
        # Update file
        update_response = await self.client.put(
            api_url,
            json={
                "message": commit_message,
                "content": content,
                "sha": current_sha,
                "branch": self.branch
            }
        )
        update_response.raise_for_status()
    
    def _format_metrics_for_readme(
        self,
        metrics: Dict[str, Any]
    ) -> str:
        """Format metrics for README.md."""
        # Create markdown table
        lines = [
            "# LLM Runtime Performance Metrics",
            "",
            f"Last Updated: {datetime.now().isoformat()}",
            "",
            "| Model | Provider | Success Rate | Avg Latency (ms) | Total Cost |",
            "|-------|----------|--------------|------------------|------------|"
        ]
        
        for key, m in metrics.items():
            lines.append(
                f"| {m['model']} | {m['provider']} | "
                f"{m['success_rate']:.2%} | {m['average_latency_ms']:.1f} | "
                f"${m['total_cost']:.4f} |"
            )
        
        return "\n".join(lines)
    
    def _generate_commit_message(
        self,
        metrics: Dict[str, Any]
    ) -> str:
        """Generate meaningful commit message."""
        total_requests = sum(m.get("total_requests", 0) for m in metrics.values())
        
        return (
            f"[LLM Runtime] Performance update - {total_requests} requests processed"
        )
    
    def _batch_operations(
        self,
        operations: List[SyncOperation]
    ) -> SyncOperation:
        """Batch multiple operations into one."""
        # Combine content and messages
        combined_content = operations[-1].content  # Use latest
        combined_message = f"[LLM Runtime] Batched update - {len(operations)} changes"
        
        return SyncOperation(
            operation_id=self._generate_operation_id(),
            content=combined_content,
            commit_message=combined_message,
            timestamp=datetime.now(),
            retry_count=0,
            status="pending"
        )
    
    def _generate_operation_id(self) -> str:
        """Generate unique operation ID."""
        import uuid
        return str(uuid.uuid4())
```


## Data Models

### Core Data Structures

All data models are defined in the Components section above. Key design decisions:

1. **Provider Abstraction**: Unified Message, CompletionRequest, CompletionResponse across all providers
2. **Streaming Support**: StreamChunk for incremental delivery
3. **Function Calling**: FunctionDefinition and function_call fields in requests/responses
4. **Token Tracking**: TokenUsage with prompt/completion/total tokens and cost
5. **Session Management**: session_id for context tracking across requests
6. **Performance Metrics**: Comprehensive metrics per model/provider
7. **Error Classification**: ErrorType enum for retry logic

### Storage Layer

**Session Context Storage**: In-memory with optional Redis persistence
- Key: session_id
- Value: SessionContext with message history and token count
- TTL: Configurable (default 1 hour)

**Performance Metrics Storage**: Time-series database (InfluxDB) or SQLite
- Metrics per model/provider
- Latency histograms for percentile calculation
- Token usage and cost aggregation
- Success/failure tracking

**Circuit Breaker State**: In-memory
- State per provider
- Failure counts and timestamps
- Circuit open/closed status

**GitHub Sync Queue**: Persistent queue (RocksDB or SQLite)
- Pending operations
- Retry counts
- Operation status


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Unified Interface Properties

Property 1: Cross-Provider Request Compatibility
*For any* completion request, the request structure should work across all supported providers without modification, returning responses in the same unified format.
**Validates: Requirements 1.1, 1.2, 1.3, 1.8**

Property 2: Feature Availability Transparency
*For any* provider-specific feature request, if the provider supports the feature, it should be accessible through the unified interface; if not supported, a clear error message should be returned.
**Validates: Requirements 1.4, 1.5**

Property 3: Embedding Interface Consistency
*For any* embedding request, all providers that support embeddings should return vectors in the same format with consistent dimensionality for the same model.
**Validates: Requirements 1.3**

### Streaming Properties

Property 4: Incremental Token Delivery
*For any* streaming request, tokens should arrive incrementally rather than all at once, with each chunk containing a non-empty content string until the final chunk.
**Validates: Requirements 2.1**

Property 5: Partial Response Preservation
*For any* interrupted stream, the system should return all tokens received up to the interruption point, with context about what was received and why the stream ended.
**Validates: Requirements 2.2, 2.3**

Property 6: Stream Failure Context
*For any* stream that fails mid-response, the error should include both the partial content received and the failure reason.
**Validates: Requirements 2.4**

Property 7: Stream Resumption Support
*For any* provider that supports stream resumption, the system should enable resuming from the interruption point; for providers without support, this should be clearly indicated.
**Validates: Requirements 2.5**

Property 8: Streaming Fallback Behavior
*For any* provider that doesn't support streaming, the system should simulate streaming by chunking the complete response into incremental deliveries.
**Validates: Requirements 2.6**

Property 9: Cross-Provider Streaming Consistency
*For any* two streaming requests with identical parameters to different providers, the streaming behavior (chunk timing, size patterns) should be consistent within reasonable variance.
**Validates: Requirements 2.7**

### Function Calling Properties

Property 10: Function Definition Acceptance
*For any* valid function definition in the unified format, the system should accept it and translate it correctly to each provider's specific format.
**Validates: Requirements 3.1, 3.2**

Property 11: Function Call Parsing
*For any* model response containing a function call request, the system should parse it into structured function call information with name and arguments.
**Validates: Requirements 3.3**

Property 12: Multi-Turn Function Calling
*For any* function calling sequence, the system should support multiple rounds of function execution and result feedback until the model completes the task.
**Validates: Requirements 3.4**

Property 13: Function Calling Unsupported Error
*For any* function calling request to a provider that doesn't support it, the system should return a clear error indicating the limitation before attempting the request.
**Validates: Requirements 3.5**

Property 14: Function Argument Validation
*For any* function call with arguments, the system should validate arguments against the function schema and return detailed validation errors for invalid arguments.
**Validates: Requirements 3.6, 3.7**

Property 15: Parallel Function Calling
*For any* provider that supports parallel function calling, the system should enable concurrent function execution; for providers without support, functions should execute sequentially.
**Validates: Requirements 3.8**

### Context Management Properties

Property 16: Per-Session History Isolation
*For any* two different sessions, messages added to one session should not appear in the context of the other session.
**Validates: Requirements 4.1**

Property 17: Token Count Accuracy
*For any* session context, the calculated token count should be within 5% of the actual token count when measured with the provider's tokenizer.
**Validates: Requirements 4.2**

Property 18: Context Window Warning
*For any* session where context usage exceeds 80% of the context window limit, a warning should be emitted before the next request.
**Validates: Requirements 4.3**

Property 19: Automatic Context Compression
*For any* session that exceeds the configured compression threshold, the context should be automatically compressed while preserving system prompts and recent messages.
**Validates: Requirements 4.4, 4.7**

Property 20: Manual Context Injection
*For any* manual context injection operation, the injected messages should appear in the next request to the provider in the specified position.
**Validates: Requirements 4.5**

Property 21: Context Manipulation Operations
*For any* context manipulation operation (insert, delete, reorder), the resulting context should reflect the operation correctly and maintain message ordering consistency.
**Validates: Requirements 4.6**

Property 22: Provider-Specific Context Limits
*For any* model, the context manager should use the correct context window limit for that model's provider, rejecting requests that exceed the limit.
**Validates: Requirements 4.8**

### Token Optimization Properties

Property 23: Provider-Specific Token Counting
*For any* text and model, the token count should match the count produced by the provider's official tokenizer within a 5% margin.
**Validates: Requirements 5.1**

Property 24: Token Usage Reporting
*For any* completed request, the response should include accurate token usage for both prompt and completion, along with total tokens.
**Validates: Requirements 5.2**

Property 25: Context Window Pre-Validation
*For any* request that would exceed the context window limit, the system should reject it with a clear error before sending to the provider.
**Validates: Requirements 5.3**

Property 26: Token Budget Enforcement
*For any* session with a configured token budget, requests that would exceed the budget should be rejected, and the session should track cumulative token usage accurately.
**Validates: Requirements 5.4, 5.5**

Property 27: Token Optimization Suggestions
*For any* request with inefficient token usage (e.g., redundant context, excessive verbosity), the system should provide actionable optimization suggestions.
**Validates: Requirements 5.6**

Property 28: Special Token Handling
*For any* text containing special tokens (e.g., <|endoftext|>, [INST]), the token counter should handle them correctly according to the provider's tokenization rules.
**Validates: Requirements 5.7**

### Performance Monitoring Properties

Property 29: Latency Tracking Completeness
*For any* completed request, the performance monitor should record the latency with millisecond precision for the specific model and provider.
**Validates: Requirements 6.1**

Property 30: Token Usage Tracking
*For any* request, the performance monitor should track token usage both per-request and cumulatively per-session.
**Validates: Requirements 6.2**

Property 31: Cost Estimation Accuracy
*For any* request, the estimated cost should be within 10% of the actual cost based on the provider's published pricing.
**Validates: Requirements 6.3**

Property 32: Slow Response Warning
*For any* request with latency exceeding the configured threshold (default 5000ms), a performance warning should be emitted with timing details.
**Validates: Requirements 6.4**

Property 33: Reliability Warning
*For any* provider with more than 5 failures in a 60-second window, a reliability warning should be emitted.
**Validates: Requirements 6.5**

Property 34: Metrics Reporting to Self-Improvement
*For any* completed request, performance metrics should be reported to the Self-Improvement Engine including latency, tokens, cost, and success status.
**Validates: Requirements 6.6, 8.2**

Property 35: Metrics Aggregation
*For any* time window, aggregated metrics should correctly sum individual request metrics for total tokens, total cost, and average latency.
**Validates: Requirements 6.7**

Property 36: Success Rate Calculation
*For any* model/provider combination, the success rate should equal (successful_requests / total_requests) over the measurement window.
**Validates: Requirements 6.8**

### Error Handling Properties

Property 37: Transient Error Retry with Backoff
*For any* transient error, the system should retry with exponential backoff (100ms, 200ms, 400ms, 800ms, 1600ms) up to the maximum retry limit.
**Validates: Requirements 7.1**

Property 38: Retry Limit Enforcement
*For any* persistent error, the system should stop retrying after the maximum retry limit (default 3) and return a detailed error.
**Validates: Requirements 7.2**

Property 39: Rate Limit Handling
*For any* rate limit error, the system should wait the duration specified in the error response before retrying.
**Validates: Requirements 7.3**

Property 40: Exhausted Retry Error Detail
*For any* request where retries are exhausted, the error message should include all failure attempts, error types, and timestamps.
**Validates: Requirements 7.4**

Property 41: Circuit Breaker Pattern
*For any* provider with 5 consecutive failures, the circuit breaker should open, causing subsequent requests to fail fast for 60 seconds.
**Validates: Requirements 7.5, 7.6**

Property 42: Error Classification
*For any* error, the system should correctly classify it as transient, rate_limit, permanent, or timeout based on error codes and messages.
**Validates: Requirements 7.7**

Property 43: Permanent Error No Retry
*For any* permanent error (4xx status codes except 429), the system should not retry and should return immediately with the error.
**Validates: Requirements 7.8**

Property 44: Error Logging Completeness
*For any* error, the log entry should include error type, provider, model, request context, and stack trace for debugging.
**Validates: Requirements 7.9**

### Integration Properties

Property 45: Model Router Integration
*For any* model selection from the Model Router, the LLM Runtime should use the specified model without modification.
**Validates: Requirements 8.1**

Property 46: Verifier System Hooks
*For any* registered verification hook, the system should call the hook with the response before returning to the caller.
**Validates: Requirements 8.3**

Property 47: Memory System Context Injection
*For any* context provided by the Memory System, the Context Manager should incorporate it into the session before the next request.
**Validates: Requirements 8.4, 8.5**

Property 48: Graceful Shutdown
*For any* shutdown signal, the system should complete all in-flight requests before terminating, with a maximum wait time of 30 seconds.
**Validates: Requirements 8.7**

### GitHub Integration Properties

Property 49: Performance Change GitHub Sync
*For any* significant performance change (>10% latency change or >5% cost change), the system should queue a GitHub sync operation.
**Validates: Requirements 9.1**

Property 50: README-Only File Updates
*For any* GitHub sync operation, only README.md files should be updated, and no other markdown files should be created or modified.
**Validates: Requirements 9.2, 9.3**

Property 51: Meaningful Commit Messages
*For any* GitHub commit, the commit message should include the number of requests processed and key performance metrics.
**Validates: Requirements 9.4**

Property 52: GitHub Retry Logic
*For any* failed GitHub API call, the system should retry with exponential backoff (100ms, 200ms, 400ms, 800ms, 1600ms) up to 5 attempts.
**Validates: Requirements 9.5**

Property 53: GitHub Unavailability Queueing
*For any* period when GitHub is unavailable, performance data should be queued in persistent storage for later upload.
**Validates: Requirements 9.6**

Property 54: Performance Data Validation
*For any* performance data before GitHub push, the system should validate the data format and reject malformed data with clear errors.
**Validates: Requirements 9.8**

### Configuration Properties

Property 55: Plugin Architecture Support
*For any* new provider adapter that implements the required interface, the system should be able to load and use it without modifying core code.
**Validates: Requirements 11.2, 11.3**

Property 56: Per-Provider Configuration
*For any* provider, the system should support independent configuration of API keys, endpoints, timeouts, and retry settings.
**Validates: Requirements 11.4**

Property 57: Configuration Validation
*For any* invalid configuration (missing required fields, invalid values), the system should fail at startup with clear error messages indicating the issues.
**Validates: Requirements 11.5**

Property 58: Runtime Configuration Updates
*For any* non-critical configuration change (timeouts, retry limits), the system should apply the change without requiring restart.
**Validates: Requirements 11.6**

Property 59: Configuration Defaults
*For any* omitted configuration option, the system should use sensible defaults that enable basic functionality.
**Validates: Requirements 11.7**

### Security Properties

Property 60: Credential Logging Prevention
*For any* log entry, API keys and authentication tokens should never appear in plain text, even in debug mode.
**Validates: Requirements 12.1**

Property 61: Error Message Sanitization
*For any* error message, sensitive credentials should be redacted or replaced with placeholders before being returned or logged.
**Validates: Requirements 12.3**

Property 62: PII Redaction
*For any* request/response logging, personally identifiable information (emails, names, addresses) should be automatically redacted before writing to logs.
**Validates: Requirements 12.4, 12.5**

Property 63: TLS Certificate Validation
*For any* network connection to a provider, the system should validate TLS certificates and reject connections with invalid or self-signed certificates.
**Validates: Requirements 12.6, 12.7**


## Error Handling

### Error Categories

1. **Provider Errors**:
   - Connection failures (network timeout, DNS resolution)
   - Authentication errors (invalid API key, expired token)
   - Rate limiting (429 status code)
   - Service unavailable (503 status code)
   - Action: Classify, retry if transient, open circuit breaker if persistent

2. **Validation Errors**:
   - Invalid request format (missing required fields)
   - Context window exceeded (request too large)
   - Token budget exceeded (session over limit)
   - Invalid function schema (malformed function definition)
   - Action: Return clear error immediately, no retry

3. **Runtime Errors**:
   - Stream interruption (connection dropped mid-stream)
   - Parsing errors (malformed provider response)
   - Timeout errors (request exceeded timeout)
   - Action: Return partial results if available, retry if appropriate

4. **Integration Errors**:
   - Verifier System unavailable (verification hook fails)
   - Memory System unavailable (context injection fails)
   - GitHub API unavailable (sync operation fails)
   - Action: Degrade gracefully, queue for later, log warning

### Error Recovery Strategies

**Retry with Exponential Backoff**:
```
Attempt 1: Immediate
Attempt 2: 100ms delay
Attempt 3: 200ms delay
Attempt 4: 400ms delay
Attempt 5: 800ms delay
```

**Circuit Breaker States**:
- **Closed**: Normal operation, requests pass through
- **Open**: After 5 failures, reject requests immediately for 60 seconds
- **Half-Open**: After timeout, allow one test request
- **Success**: Close circuit, resume normal operation
- **Failure**: Re-open circuit for another 60 seconds

**Graceful Degradation**:
- If Context Manager fails: Continue without context injection
- If Performance Monitor fails: Continue without metrics recording
- If GitHub Sync fails: Queue for later, continue operation
- If Verifier System fails: Log warning, continue without verification

### Error Messages

All errors should include:
- Error code (for programmatic handling)
- Human-readable message
- Provider and model information
- Request ID for tracing
- Suggested action (retry, adjust request, contact support)
- Timestamp

Example error format:
```json
{
  "error_code": "CONTEXT_WINDOW_EXCEEDED",
  "message": "Request exceeds context window limit",
  "provider": "openai",
  "model": "gpt-4",
  "request_id": "req_abc123",
  "details": {
    "estimated_tokens": 10000,
    "context_limit": 8192,
    "excess_tokens": 1808
  },
  "suggested_action": "Reduce message history or use a model with larger context window",
  "timestamp": "2024-01-15T10:30:00Z"
}
```


## Testing Strategy

### Dual Testing Approach

The LLM Runtime requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests**: Focus on specific examples, edge cases, and integration points
- Specific provider response formats (OpenAI vs Anthropic vs Google)
- Edge cases (empty responses, malformed JSON, missing fields)
- Integration with Model Router, Verifier System, Memory System
- Error conditions (network failures, authentication errors, rate limits)
- Configuration loading and validation
- Health check endpoints

**Property-Based Tests**: Verify universal properties across all inputs
- Generate random requests, messages, function definitions
- Verify properties hold for all generated inputs
- Minimum 100 iterations per property test
- Each test references its design document property
- Focus on adversarial scenarios and edge cases

### Property-Based Testing Configuration

**Testing Library**: Use `hypothesis` (Python) for property-based testing

**Test Configuration**:
- Minimum 100 iterations per property test
- Seed randomization for reproducibility
- Shrinking enabled to find minimal failing cases
- Timeout: 60 seconds per property test (some tests involve network calls)
- Parallel execution where possible

**Test Tagging**: Each property test must include a comment tag:
```python
# Feature: llm-runtime, Property 1: Cross-Provider Request Compatibility
# For any completion request, the request structure should work across all
# supported providers without modification, returning responses in the same
# unified format.
def test_cross_provider_request_compatibility():
    ...
```

**Generator Strategy**:
- **Requests**: Random messages (1-50), random temperatures (0.0-2.0), random max_tokens (10-4000)
- **Messages**: Random roles (system/user/assistant), random content (10-1000 chars)
- **Function Definitions**: Random names, descriptions, parameter schemas
- **Providers**: All supported providers (Ollama, OpenAI, Anthropic, Google)
- **Edge Cases**: Empty strings, very long strings, special characters, unicode
- **Adversarial**: Malformed JSON, missing fields, invalid types, extreme values

### Critical Properties to Test

**Highest Priority** (must implement):
1. Property 1: Cross-Provider Request Compatibility
2. Property 23: Provider-Specific Token Counting
3. Property 25: Context Window Pre-Validation
4. Property 37: Transient Error Retry with Backoff
5. Property 41: Circuit Breaker Pattern
6. Property 4: Incremental Token Delivery
7. Property 14: Function Argument Validation
8. Property 50: README-Only File Updates

**High Priority** (should implement):
9. Property 5: Partial Response Preservation
10. Property 19: Automatic Context Compression
11. Property 26: Token Budget Enforcement
12. Property 31: Cost Estimation Accuracy
13. Property 42: Error Classification
14. Property 60: Credential Logging Prevention
15. Property 63: TLS Certificate Validation

**Medium Priority** (nice to have):
- All remaining properties

### Unit Test Coverage

**Unified API Interface**:
- Complete request with all providers → success
- Streaming request with all providers → incremental chunks
- Embedding request with all providers → consistent format
- Invalid model name → clear error

**Context Manager**:
- Create session → track history
- Add messages → update token count
- Exceed threshold → compress context
- Multiple sessions → isolated histories

**Token Counter**:
- Count OpenAI messages → matches tiktoken
- Count Anthropic messages → matches anthropic library
- Count with special tokens → correct handling
- Count very long text → accurate within 5%

**Provider Adapters**:
- OpenAI adapter → correct request/response format
- Ollama adapter → correct request/response format
- Anthropic adapter → correct request/response format
- Function calling → correct translation per provider

**Performance Monitor**:
- Record request → metrics updated
- Slow request → warning emitted
- Multiple failures → reliability warning
- Get metrics → correct aggregation

**Error Handler**:
- Transient error → retry with backoff
- Rate limit → wait and retry
- Permanent error → no retry
- Circuit breaker → opens after threshold

**GitHub Sync**:
- Queue operation → added to queue
- Process queue → README.md updated
- GitHub failure → retry with backoff
- Batch operations → combined commit

### Adversarial Testing Scenarios

**Streaming Adversarial Tests**:
- Interrupt stream mid-response → partial content returned
- Provider returns empty chunks → handled gracefully
- Provider returns malformed JSON in stream → error with context
- Very slow stream (1 token per second) → timeout handling
- Stream with unicode and special characters → correct handling

**Function Calling Adversarial Tests**:
- Function call with invalid JSON arguments → validation error
- Function call with missing required arguments → validation error
- Function call to non-existent function → clear error
- Parallel function calls with one failure → partial results
- Multi-turn with circular function calls → loop detection

**Context Management Adversarial Tests**:
- Fill context to exactly the limit → accepted
- Exceed context by 1 token → rejected
- Compress context with only system message → preserved
- Concurrent updates to same session → serialized correctly
- Very large message (10K tokens) → handled or rejected clearly

**Token Counting Adversarial Tests**:
- Text with only special tokens → correct count
- Text with mixed languages (English, Chinese, Arabic) → accurate
- Very long text (100K characters) → efficient counting
- Empty text → zero tokens
- Text with emoji and unicode → correct handling

**Error Handling Adversarial Tests**:
- 5 consecutive failures → circuit opens
- Rate limit with no Retry-After header → default wait
- Network timeout during request → retry
- Network timeout during stream → partial response
- Provider returns 500 error → retry
- Provider returns 400 error → no retry

**Security Adversarial Tests**:
- Log request with API key in header → key redacted
- Error message contains API key → key sanitized
- Request with PII (email, phone) → redacted in logs
- Invalid TLS certificate → connection rejected
- Self-signed certificate → connection rejected

### Integration Testing

**Model Router Integration**:
- Model Router selects model → LLM Runtime uses it
- Model Router changes selection → new model used
- Model Router unavailable → graceful degradation

**Verifier System Integration**:
- Register verification hook → called on response
- Verifier rejects response → error returned
- Verifier unavailable → warning logged, continue

**Memory System Integration**:
- Memory provides context → injected into request
- Memory unavailable → continue without context
- Memory provides invalid context → validation error

**Self-Improvement Engine Integration**:
- Complete request → metrics reported
- Failed request → failure reported
- Performance degradation → alert sent

### Performance Testing

**Latency Targets**:
- Non-streaming request overhead: <500ms (95th percentile)
- Streaming first token: <1000ms (95th percentile)
- Context injection: <50ms (95th percentile)
- Token counting: <10ms for 1000 tokens (95th percentile)

**Throughput Targets**:
- Concurrent requests: 100 requests/second
- Streaming connections: 50 concurrent streams
- Context manager: 1000 sessions active

**Load Testing Scenarios**:
- Sustained load: 100 req/s for 10 minutes
- Burst load: 500 req/s for 30 seconds
- Mixed workload: 70% non-streaming, 30% streaming
- Large context: Requests with 7000+ token contexts

