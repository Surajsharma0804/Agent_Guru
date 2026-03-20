"""
LLM Runtime Integration Layer.

Provides a higher-level synchronous interface over LLMRuntime with
self-improvement engine integration, session management, and prompt evolution.

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from Agent_Guru.llm.models import Message, ModelProvider, RuntimeConfig


@dataclass
class LLMRequest:
    """Synchronous LLM request model."""

    messages: List[Message]
    model: str
    provider: "ModelProvider" = None  # type: ignore[assignment]
    max_tokens: int = 1024
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.provider is None:
            self.provider = ModelProvider.OPENAI


@dataclass
class LLMResponse:
    """Synchronous LLM response model."""

    content: str
    model: str
    provider: str
    latency_ms: float
    total_tokens: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class _StandalonePromptVersion:
    """Lightweight prompt version for standalone (no-engine) mode."""

    def __init__(self, prompt_type: str, content: str, version: int = 1) -> None:
        self.prompt_id = f"{prompt_type}_v{version}"
        self.prompt_type = prompt_type
        self.content = content
        self.version = version
        self.total_uses: int = 0
        self.success_count: int = 0
        self.failure_count: int = 0
        self.success_rate: float = 0.0
        self.is_active: bool = True


class _StandalonePromptEvolution:
    """Lightweight prompt registry used when no external engine is provided."""

    def __init__(self) -> None:
        self._prompts: Dict[str, _StandalonePromptVersion] = {}
        self._lock = threading.Lock()

    def register_prompt(
        self,
        prompt_type: str,
        content: str,
        version: int = 1,
        force: bool = False,
    ) -> str:
        with self._lock:
            existing = self._prompts.get(prompt_type)
            if existing is None or version > existing.version or force:
                pv = _StandalonePromptVersion(prompt_type, content, version)
                self._prompts[prompt_type] = pv
                return pv.prompt_id
            return existing.prompt_id

    def get_active_prompt(self, prompt_type: str) -> Optional[_StandalonePromptVersion]:
        return self._prompts.get(prompt_type)

    def record_prompt_outcome(
        self, prompt_id: str, success: bool, hallucination_detected: bool = False
    ) -> None:
        with self._lock:
            for pv in self._prompts.values():
                if pv.prompt_id == prompt_id:
                    pv.total_uses += 1
                    if success:
                        pv.success_count += 1
                    else:
                        pv.failure_count += 1
                    if pv.total_uses > 0:
                        pv.success_rate = pv.success_count / pv.total_uses
                    break


class LLMRuntime:
    """
    Synchronous LLM runtime with self-improvement integration.

    Wraps the async LLMRuntime to provide a synchronous interface suitable
    for integration with the SelfImprovementEngine and other synchronous
    components.

    Features:
    - Synchronous execute() interface
    - Session history management
    - Prompt evolution tracking
    - Hallucination detection callbacks
    - Self-improvement engine integration

    Example:
        >>> runtime = LLMRuntime(enable_learning=False)
        >>> request = LLMRequest(
        ...     messages=[Message(role="user", content="Hello")],
        ...     model="gpt-3.5-turbo",
        ...     provider=ModelProvider.OPENAI
        ... )
        >>> response = runtime.execute(request)
        >>> print(response.content)
    """

    def __init__(
        self,
        self_improvement_engine: Optional[Any] = None,
        enable_learning: bool = False,
        hallucination_detector: Optional[Callable[[str], bool]] = None,
        config: Optional[RuntimeConfig] = None,
        degradation_controller: Optional[Any] = None,
    ) -> None:
        self.self_improvement_engine = self_improvement_engine
        self.enable_learning = enable_learning
        self.hallucination_detector = hallucination_detector
        # Requirement 7.1, 7.6: offline resilience and LLM failover
        self.degradation_controller = degradation_controller

        # Session history: session_id -> List[Message]
        self.active_sessions: Dict[str, List[Message]] = {}
        self._sessions_lock = threading.Lock()

        # Prompt evolution — use engine's if available, else standalone
        if self_improvement_engine is not None and hasattr(
            self_improvement_engine, "prompt_evolution"
        ):
            self.prompt_evolution = self_improvement_engine.prompt_evolution
        else:
            self.prompt_evolution = _StandalonePromptEvolution()

    def execute(
        self,
        request: LLMRequest,
        session_id: Optional[str] = None,
        prompt_type: Optional[str] = None,
    ) -> LLMResponse:
        """
        Execute an LLM request synchronously.

        Args:
            request: LLM request to execute
            session_id: Optional session ID for history tracking
            prompt_type: Optional prompt type for evolution tracking

        Returns:
            LLM response

        Raises:
            Exception: If execution fails (after recording the failure)
        """
        start = time.perf_counter()

        # Requirement 7.1: Check network/degradation state before LLM call
        if self.degradation_controller is not None:
            try:
                mode = self.degradation_controller.current_mode
                if hasattr(mode, "value") and mode.value in ("minimal", "safe"):
                    # Use offline cache lookup instead of LLM
                    cached = self.degradation_controller.lookup_offline(
                        str(request.messages[-1].content if request.messages else "")
                    )
                    if cached:
                        return LLMResponse(
                            content=cached,
                            model="offline_cache",
                            provider="cache",
                            latency_ms=(time.perf_counter() - start) * 1000,
                            total_tokens=0,
                        )
            except Exception:
                pass  # Degradation check is best-effort

        # Resolve active prompt_id for recording
        active_prompt_id: Optional[str] = None
        if prompt_type:
            pv = self.prompt_evolution.get_active_prompt(prompt_type)
            if pv is not None:
                active_prompt_id = pv.prompt_id

        # Build messages with session history
        messages = self._build_messages(request, session_id)

        try:
            content = self._execute_llm(request, messages)
            latency_ms = (time.perf_counter() - start) * 1000

            # Detect hallucinations
            hallucination = False
            if self.hallucination_detector is not None:
                hallucination = self.hallucination_detector(content)

            # Update session history
            if session_id is not None:
                self._update_session(session_id, request.messages, content)

            # Record prompt outcome
            if active_prompt_id:
                try:
                    self.prompt_evolution.record_prompt_outcome(
                        prompt_id=active_prompt_id,
                        success=True,
                        hallucination_detected=hallucination,
                    )
                except Exception:
                    pass

            return LLMResponse(
                content=content,
                model=request.model,
                provider=request.provider.value if hasattr(request.provider, "value") else str(request.provider),
                latency_ms=latency_ms,
                total_tokens=len(content.split()) * 2,
            )

        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000

            if active_prompt_id:
                try:
                    self.prompt_evolution.record_prompt_outcome(
                        prompt_id=active_prompt_id,
                        success=False,
                        hallucination_detected=False,
                    )
                except Exception:
                    pass

            if self.enable_learning and self.self_improvement_engine is not None:
                pass  # Learning recorded via prompt_evolution above

            raise

    def _execute_llm(self, request: LLMRequest, messages: List[Message]) -> str:
        """
        Execute the actual LLM call.

        Mockable for testing. In production this would call the async LLMRuntime.

        Args:
            request: Original request
            messages: Messages including session history

        Returns:
            Response content string
        """
        last_content = messages[-1].content if messages else "empty"
        return f"Response to: {last_content}"

    def _build_messages(
        self, request: LLMRequest, session_id: Optional[str]
    ) -> List[Message]:
        if session_id is None:
            return list(request.messages)
        with self._sessions_lock:
            history = self.active_sessions.get(session_id, [])
            return list(history) + list(request.messages)

    def _update_session(
        self,
        session_id: str,
        user_messages: List[Message],
        assistant_content: str,
    ) -> None:
        with self._sessions_lock:
            if session_id not in self.active_sessions:
                self.active_sessions[session_id] = []
            self.active_sessions[session_id].extend(user_messages)
            self.active_sessions[session_id].append(
                Message(role="assistant", content=assistant_content)
            )

    def get_session_history(self, session_id: str) -> List[Message]:
        """Get message history for a session."""
        with self._sessions_lock:
            return list(self.active_sessions.get(session_id, []))

    def clear_session(self, session_id: str) -> None:
        """Clear session history."""
        with self._sessions_lock:
            self.active_sessions.pop(session_id, None)

    def close(self) -> None:
        """Release resources."""
        pass


def create_runtime_with_learning(
    storage_path: str,
    improvement_threshold: float = 0.15,
    measurement_window: int = 100,
) -> LLMRuntime:
    """
    Convenience factory for creating a learning-enabled runtime.

    Args:
        storage_path: Path to SQLite database for self-improvement engine
        improvement_threshold: Minimum improvement threshold (default 0.15 = 15%)
        measurement_window: Number of tasks to measure over (default 100)

    Returns:
        LLMRuntime with self-improvement engine attached
    """
    from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine

    engine = SelfImprovementEngine(
        storage_path=storage_path,
        improvement_threshold=improvement_threshold,
        measurement_window=measurement_window,
        enable_git_commits=False,
    )

    return LLMRuntime(
        self_improvement_engine=engine,
        enable_learning=True,
    )
