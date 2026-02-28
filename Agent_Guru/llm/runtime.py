"""
LLM Runtime - Language model execution with self-improvement integration.

This module provides the runtime layer for executing language models with
integration hooks for the self-improvement engine.

**Integration with Self-Improvement Engine**:
- Prompt retrieval from evolution system
- Hallucination detection callbacks
- Response quality recording

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


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
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None


@dataclass
class LLMRequest:
    """LLM request."""
    messages: List[Message]
    model: str
    provider: ModelProvider
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    functions: Optional[List[Dict[str, Any]]] = None


@dataclass
class LLMResponse:
    """LLM response."""
    content: str
    model: str
    provider: ModelProvider
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    finish_reason: str
    function_call: Optional[Dict[str, Any]] = None


class LLMRuntime:
    """
    LLM Runtime with self-improvement integration.
    
    This class provides language model execution with hooks for:
    1. Prompt retrieval from evolution system
    2. Hallucination detection callbacks
    3. Response quality recording
    
    Time Complexity: O(1) for runtime overhead
    Space Complexity: O(n) where n is number of active sessions
    
    Example:
        >>> from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
        >>> 
        >>> # Initialize with self-improvement engine
        >>> engine = SelfImprovementEngine("data/learning.db")
        >>> runtime = LLMRuntime(self_improvement_engine=engine)
        >>> 
        >>> # Execute LLM request with learning
        >>> request = LLMRequest(
        ...     messages=[Message(role="user", content="Hello")],
        ...     model="gpt-3.5-turbo",
        ...     provider=ModelProvider.OPENAI
        ... )
        >>> response = runtime.execute(request)
        >>> 
        >>> print(f"Response: {response.content}")
        >>> print(f"Tokens: {response.total_tokens}")
    """
    
    def __init__(
        self,
        self_improvement_engine: Optional[Any] = None,
        enable_learning: bool = True,
        hallucination_detector: Optional[Callable[[str], bool]] = None
    ):
        """
        Initialize LLM runtime.
        
        Args:
            self_improvement_engine: Optional SelfImprovementEngine instance
            enable_learning: Whether to enable self-improvement learning
            hallucination_detector: Optional hallucination detection callback
            
        Time Complexity: O(1)
        """
        self.self_improvement_engine = self_improvement_engine
        self.enable_learning = enable_learning
        self.hallucination_detector = hallucination_detector
        
        # Active sessions
        self.active_sessions: Dict[str, List[Message]] = {}
    
    def execute(
        self,
        request: LLMRequest,
        session_id: Optional[str] = None,
        prompt_type: Optional[str] = None
    ) -> LLMResponse:
        """
        Execute LLM request with self-improvement integration.
        
        This method:
        1. Retrieves evolved prompt if available
        2. Executes the LLM request
        3. Detects hallucinations if detector provided
        4. Records response quality for learning
        
        Args:
            request: LLM request to execute
            session_id: Optional session identifier
            prompt_type: Optional prompt type for evolution
            
        Returns:
            LLMResponse with execution outcome
            
        Time Complexity: O(1) + O(llm_execution)
        Performance Target: <500ms overhead
        
        Validates: Requirements 16.1, 16.2, 16.3, 16.4
        """
        # Phase 1: Prompt retrieval (before execution)
        evolved_request = self._get_evolved_prompt(request, prompt_type)
        
        # Phase 2: LLM execution with instrumentation
        start_time = time.perf_counter()
        
        try:
            # Execute LLM request (mock for now)
            response = self._execute_llm(evolved_request)
            
            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            response.latency_ms = latency_ms
            
            # Phase 3: Hallucination detection (after execution)
            hallucination_detected = self._detect_hallucination(response)
            
            # Phase 4: Response quality recording (after execution)
            self._record_response_quality(
                request=evolved_request,
                response=response,
                hallucination_detected=hallucination_detected,
                prompt_type=prompt_type
            )
            
            # Update session history
            if session_id:
                self._update_session(session_id, request.messages, response)
            
            return response
            
        except Exception as e:
            # Record failure
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._record_failure(
                request=evolved_request,
                error=str(e),
                latency_ms=latency_ms,
                prompt_type=prompt_type
            )
            raise
    
    def _get_evolved_prompt(
        self,
        request: LLMRequest,
        prompt_type: Optional[str]
    ) -> LLMRequest:
        """
        Get evolved prompt from self-improvement engine.
        
        Queries self-improvement engine for improved prompt version
        based on historical performance.
        
        Args:
            request: Original LLM request
            prompt_type: Type of prompt for evolution
            
        Returns:
            Request with evolved prompt if available
            
        Time Complexity: O(1)
        Performance Target: <10ms
        
        Validates: Requirement 16.2
        """
        if not self.enable_learning or not self.self_improvement_engine:
            return request
        
        if not prompt_type:
            return request
        
        try:
            # Get evolved prompt from self-improvement engine
            evolved_content = self.self_improvement_engine.get_evolved_prompt(
                prompt_type=prompt_type,
                context={"provider": request.provider.value}
            )
            
            if evolved_content:
                # Replace system message with evolved prompt
                messages = request.messages.copy()
                if messages and messages[0].role == "system":
                    messages[0] = Message(
                        role="system",
                        content=evolved_content
                    )
                else:
                    # Insert evolved system message at start
                    messages.insert(0, Message(
                        role="system",
                        content=evolved_content
                    ))
                
                return LLMRequest(
                    messages=messages,
                    model=request.model,
                    provider=request.provider,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=request.stream,
                    functions=request.functions
                )
            
            return request
            
        except Exception as e:
            # Fallback to original if error
            print(f"Warning: Prompt evolution failed: {e}")
            return request
    
    def _execute_llm(self, request: LLMRequest) -> LLMResponse:
        """
        Execute LLM request (mock implementation).
        
        This is a placeholder that will be replaced with actual
        provider-specific implementations.
        
        Args:
            request: LLM request to execute
            
        Returns:
            LLM response
            
        Time Complexity: O(llm_execution)
        """
        # Mock response for testing
        return LLMResponse(
            content="This is a mock response",
            model=request.model,
            provider=request.provider,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=0.0,  # Will be set by caller
            finish_reason="stop"
        )
    
    def _detect_hallucination(self, response: LLMResponse) -> bool:
        """
        Detect hallucinations in LLM response.
        
        Uses hallucination detector callback if provided.
        
        Args:
            response: LLM response to check
            
        Returns:
            True if hallucination detected, False otherwise
            
        Time Complexity: O(detector)
        Performance Target: <50ms
        
        Validates: Requirement 16.3
        """
        if not self.hallucination_detector:
            return False
        
        try:
            return self.hallucination_detector(response.content)
        except Exception as e:
            print(f"Warning: Hallucination detection failed: {e}")
            return False
    
    def _record_response_quality(
        self,
        request: LLMRequest,
        response: LLMResponse,
        hallucination_detected: bool,
        prompt_type: Optional[str]
    ) -> None:
        """
        Record response quality for learning.
        
        Sends response quality metrics to self-improvement engine
        for prompt evolution.
        
        Args:
            request: Original LLM request
            response: LLM response
            hallucination_detected: Whether hallucination was detected
            prompt_type: Type of prompt used
            
        Time Complexity: O(1)
        Performance Target: <10ms
        
        Validates: Requirement 16.4
        """
        if not self.enable_learning or not self.self_improvement_engine:
            return
        
        if not prompt_type:
            return
        
        try:
            # Get active prompt to get prompt_id
            prompt_version = self.self_improvement_engine.prompt_evolution.get_active_prompt(prompt_type)
            if not prompt_version:
                return
            
            # Calculate success (not hallucinated)
            was_successful = not hallucination_detected
            
            # Record in self-improvement engine
            self.self_improvement_engine.record_llm_response(
                prompt_id=prompt_version.prompt_id,
                response=response.content,
                was_successful=was_successful,
                hallucination_detected=hallucination_detected
            )
            
        except Exception as e:
            # Don't fail request if recording fails
            print(f"Warning: Response quality recording failed: {e}")
    
    def _record_failure(
        self,
        request: LLMRequest,
        error: str,
        latency_ms: float,
        prompt_type: Optional[str]
    ) -> None:
        """
        Record LLM execution failure.
        
        Args:
            request: LLM request that failed
            error: Error message
            latency_ms: Time until failure
            prompt_type: Type of prompt used
        """
        if not self.enable_learning or not self.self_improvement_engine:
            return
        
        if not prompt_type:
            return
        
        try:
            # Get active prompt to get prompt_id
            prompt_version = self.self_improvement_engine.prompt_evolution.get_active_prompt(prompt_type)
            if not prompt_version:
                return
            
            # Record failure with quality score 0
            self.self_improvement_engine.record_llm_response(
                prompt_id=prompt_version.prompt_id,
                response="",
                was_successful=False,
                hallucination_detected=False
            )
        except Exception as e:
            print(f"Warning: Failure recording failed: {e}")
    
    def _update_session(
        self,
        session_id: str,
        request_messages: List[Message],
        response: LLMResponse
    ) -> None:
        """
        Update session history.
        
        Args:
            session_id: Session identifier
            request_messages: Request messages
            response: LLM response
        """
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = []
        
        # Add request messages
        self.active_sessions[session_id].extend(request_messages)
        
        # Add response message
        self.active_sessions[session_id].append(
            Message(role="assistant", content=response.content)
        )
    
    def get_session_history(self, session_id: str) -> List[Message]:
        """
        Get session history.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of messages in session
            
        Time Complexity: O(1)
        """
        return self.active_sessions.get(session_id, []).copy()
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear session history.
        
        Args:
            session_id: Session identifier
            
        Time Complexity: O(1)
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]


# Integration helper functions

def create_runtime_with_learning(
    storage_path: str,
    improvement_threshold: float = 0.15,
    measurement_window: int = 100,
    hallucination_detector: Optional[Callable[[str], bool]] = None
) -> LLMRuntime:
    """
    Create an LLM runtime with self-improvement learning enabled.
    
    This is a convenience function that initializes both the self-improvement
    engine and the runtime with proper integration.
    
    Args:
        storage_path: Path to SQLite database for learning data
        improvement_threshold: Minimum improvement required (15%)
        measurement_window: Number of tasks for improvement measurement (100)
        hallucination_detector: Optional hallucination detection callback
        
    Returns:
        Configured LLMRuntime instance
        
    Example:
        >>> runtime = create_runtime_with_learning("data/learning.db")
        >>> request = LLMRequest(
        ...     messages=[Message(role="user", content="Hello")],
        ...     model="gpt-3.5-turbo",
        ...     provider=ModelProvider.OPENAI
        ... )
        >>> response = runtime.execute(request, prompt_type="greeting")
        >>> print(f"Response: {response.content}")
    """
    from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
    
    # Initialize self-improvement engine
    engine = SelfImprovementEngine(
        storage_path=storage_path,
        improvement_threshold=improvement_threshold,
        measurement_window=measurement_window,
        enable_git_commits=False  # Disable for production
    )
    
    # Create runtime with engine
    runtime = LLMRuntime(
        self_improvement_engine=engine,
        enable_learning=True,
        hallucination_detector=hallucination_detector
    )
    
    return runtime
