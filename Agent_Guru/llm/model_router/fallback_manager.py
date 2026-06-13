"""Module: Agent_Guru.llm.model_router.fallback_manager
Purpose: Manages fallback strategies when primary model selection fails.

Implements circuit-breaker pattern and sequential fallback execution.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from Agent_Guru.llm.model_router.models import FallbackEvent, TaskType

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger("model_router.fallback_manager")

_MAX_EVENTS = 5_000
_CIRCUIT_BREAKER_THRESHOLD = 0.5  # 50% failure rate opens circuit
_CIRCUIT_BREAKER_WINDOW = 10  # Over last N requests
_CIRCUIT_BREAKER_TIMEOUT_S = 60.0  # Seconds before half-open


class FallbackManager:
    """Manages fallback sequences and circuit-breaker state for models.

    Args:
        max_events: Maximum number of fallback events to retain.
        circuit_breaker_threshold: Failure rate that opens the circuit.
        circuit_breaker_window: Number of recent requests to evaluate.
        circuit_breaker_timeout: Seconds before a tripped circuit goes half-open.

    """

    def __init__(
        self,
        max_events: int = _MAX_EVENTS,
        circuit_breaker_threshold: float = _CIRCUIT_BREAKER_THRESHOLD,
        circuit_breaker_window: int = _CIRCUIT_BREAKER_WINDOW,
        circuit_breaker_timeout: float = _CIRCUIT_BREAKER_TIMEOUT_S,
    ) -> None:
        self._events: deque[FallbackEvent] = deque(maxlen=max_events)
        self._lock = threading.RLock()

        # task_type → ordered fallback sequence
        self._strategies: dict[str, list[str]] = {}

        # model_id → deque of (timestamp, success) for circuit breaker
        self._model_outcomes: dict[str, deque[tuple[float, bool]]] = {}

        # model_id → timestamp when circuit was opened (None = closed)
        self._circuit_open_at: dict[str, float | None] = {}

        # model_id → deprioritized until timestamp
        self._deprioritized_until: dict[str, float] = {}

        self._cb_threshold = circuit_breaker_threshold
        self._cb_window = circuit_breaker_window
        self._cb_timeout = circuit_breaker_timeout

    # ------------------------------------------------------------------
    # Strategy management
    # ------------------------------------------------------------------

    def set_fallback_sequence(self, task_type: TaskType, sequence: list[str]) -> None:
        """Configure the fallback sequence for a task type.

        Args:
            task_type: Task type this sequence applies to.
            sequence: Ordered list of model IDs to try on failure.

        """
        with self._lock:
            self._strategies[task_type.value] = list(sequence)

    def get_fallback_sequence(self, task_type: TaskType, exclude: str | None = None) -> list[str]:
        """Get the fallback sequence for a task type, excluding a model.

        Args:
            task_type: Task type.
            exclude: Model ID to exclude (typically the failed primary).

        Returns:
            Ordered list of fallback model IDs.

        """
        with self._lock:
            seq = list(self._strategies.get(task_type.value, []))
        if exclude:
            seq = [m for m in seq if m != exclude]
        return seq

    # ------------------------------------------------------------------
    # Fallback execution
    # ------------------------------------------------------------------

    def get_next_fallback(
        self,
        original_model: str,
        task_type: TaskType,
        reason: str,
        is_available: Callable[[str], bool],
    ) -> str | None:
        """Get the next available fallback model.

        Args:
            original_model: The model that failed.
            task_type: Task type being processed.
            reason: Reason for the fallback.
            is_available: Callable that returns True if a model is available.

        Returns:
            Model ID of the next fallback, or None if all exhausted.

        """
        sequence = self.get_fallback_sequence(task_type, exclude=original_model)

        for candidate in sequence:
            if self._is_circuit_open(candidate):
                logger.debug("circuit_open_skipping", model_id=candidate)
                continue
            if self.is_deprioritized(candidate):
                logger.debug("deprioritized_skipping", model_id=candidate)
                continue
            if not is_available(candidate):
                continue

            # Record the fallback event
            event = FallbackEvent(
                original_model=original_model,
                fallback_model=candidate,
                task_type=task_type,
                reason=reason,
                timestamp=datetime.now(UTC),
            )
            with self._lock:
                self._events.append(event)

            logger.info(
                "fallback_selected",
                original=original_model,
                fallback=candidate,
                task_type=task_type.value,
                reason=reason,
            )
            return candidate

        logger.warning("fallback_exhausted", original=original_model, task_type=task_type.value)
        return None

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def record_outcome(self, model_id: str, success: bool) -> None:
        """Record a success/failure outcome for circuit-breaker tracking.

        Args:
            model_id: Model that was used.
            success: Whether the request succeeded.

        """
        now = time.monotonic()
        with self._lock:
            if model_id not in self._model_outcomes:
                self._model_outcomes[model_id] = deque(maxlen=self._cb_window)
            self._model_outcomes[model_id].append((now, success))

            # Check if circuit should open
            outcomes = list(self._model_outcomes[model_id])
            if len(outcomes) >= self._cb_window:
                failure_rate = sum(1 for _, s in outcomes if not s) / len(outcomes)
                if failure_rate > self._cb_threshold:
                    if self._circuit_open_at.get(model_id) is None:
                        self._circuit_open_at[model_id] = now
                        logger.warning(
                            "circuit_opened",
                            model_id=model_id,
                            failure_rate=failure_rate,
                        )

    def _is_circuit_open(self, model_id: str) -> bool:
        """Check if the circuit breaker is open for a model."""
        with self._lock:
            opened_at = self._circuit_open_at.get(model_id)
            if opened_at is None:
                return False
            elapsed = time.monotonic() - opened_at
            if elapsed >= self._cb_timeout:
                # Half-open: allow one attempt
                self._circuit_open_at[model_id] = None
                logger.info("circuit_half_open", model_id=model_id)
                return False
            return True

    def reset_circuit(self, model_id: str) -> None:
        """Manually reset the circuit breaker for a model."""
        with self._lock:
            self._circuit_open_at[model_id] = None
            if model_id in self._model_outcomes:
                self._model_outcomes[model_id].clear()

    # ------------------------------------------------------------------
    # Deprioritization
    # ------------------------------------------------------------------

    def deprioritize(self, model_id: str, duration_s: float) -> None:
        """Deprioritize a model for a given duration.

        Args:
            model_id: Model to deprioritize.
            duration_s: Duration in seconds.

        """
        until = time.monotonic() + duration_s
        with self._lock:
            self._deprioritized_until[model_id] = until
        logger.info("model_deprioritized", model_id=model_id, duration_s=duration_s)

    def is_deprioritized(self, model_id: str) -> bool:
        """Check if a model is currently deprioritized."""
        with self._lock:
            until = self._deprioritized_until.get(model_id)
        if until is None:
            return False
        return time.monotonic() < until

    # ------------------------------------------------------------------
    # Event access
    # ------------------------------------------------------------------

    def get_events(
        self,
        model_id: str | None = None,
        task_type: TaskType | None = None,
    ) -> list[FallbackEvent]:
        """Retrieve recorded fallback events with optional filtering.

        Args:
            model_id: Filter by original model ID.
            task_type: Filter by task type.

        Returns:
            List of matching FallbackEvent objects.

        """
        with self._lock:
            events = list(self._events)

        if model_id:
            events = [e for e in events if e.original_model == model_id]
        if task_type:
            events = [e for e in events if e.task_type == task_type]
        return events

    def total_events(self) -> int:
        """Return the total number of recorded fallback events."""
        with self._lock:
            return len(self._events)
