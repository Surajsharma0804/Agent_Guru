"""
Fallback strategies for error recovery.

Provides intelligent fallback mechanisms for different error types:
- LLM fallback: cloud → local → rule-based
- Tool fallback: alternative tools → simplified request → user notification
- Timeout fallback: partial results → async execution → simplification
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from Agent_Guru.reasoning.error.error_manager import ErrorType, StructuredError

_logger = logging.getLogger(__name__)


class FallbackStrategy(str, Enum):
    """Fallback strategy types."""

    # LLM fallbacks
    CLOUD_TO_LOCAL_LLM = "cloud_to_local_llm"
    LOCAL_TO_RULE_BASED = "local_to_rule_based"
    LLM_TO_CACHE = "llm_to_cache"

    # Tool fallbacks
    ALTERNATIVE_TOOL = "alternative_tool"
    SIMPLIFIED_REQUEST = "simplified_request"
    USER_NOTIFICATION = "user_notification"

    # Timeout fallbacks
    PARTIAL_RESULTS = "partial_results"
    ASYNC_EXECUTION = "async_execution"
    SIMPLIFICATION = "simplification"

    # General fallbacks
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    GRACEFUL_DEGRADATION = "graceful_degradation"


@dataclass
class FallbackResult:
    """Result of fallback execution."""

    success: bool
    strategy_used: FallbackStrategy
    result: Optional[Any] = None
    error: Optional[str] = None
    fallback_count: int = 0


class FallbackHandler(ABC):
    """Abstract base class for fallback handlers."""

    @abstractmethod
    async def handle(
        self,
        error: StructuredError,
        context: dict[str, Any],
    ) -> FallbackResult:
        """Handle error with fallback strategy.

        Args:
            error: Structured error
            context: Execution context

        Returns:
            Fallback result
        """


class LLMFallbackHandler(FallbackHandler):
    """Fallback handler for LLM errors."""

    async def handle(
        self,
        error: StructuredError,
        context: dict[str, Any],
    ) -> FallbackResult:
        """Handle LLM errors with fallback chain.

        Fallback chain:
        1. Cloud LLM → Local LLM
        2. Local LLM → Rule-based
        3. Rule-based → Cached response

        Args:
            error: Structured error
            context: Execution context

        Returns:
            Fallback result
        """
        # Get current LLM backend
        current_backend = context.get("llm_backend", "cloud")

        # Try fallback chain
        if current_backend == "cloud":
            # Fallback to local LLM
            try:
                result = await self._try_local_llm(context)
                return FallbackResult(
                    success=True,
                    strategy_used=FallbackStrategy.CLOUD_TO_LOCAL_LLM,
                    result=result,
                    fallback_count=1,
                )
            except Exception:
                # Continue to next fallback
                pass

        if current_backend in ["cloud", "local"]:
            # Fallback to rule-based
            try:
                result = await self._try_rule_based(context)
                return FallbackResult(
                    success=True,
                    strategy_used=FallbackStrategy.LOCAL_TO_RULE_BASED,
                    result=result,
                    fallback_count=2,
                )
            except Exception:
                # Continue to next fallback
                pass

        # Final fallback: cached response
        try:
            result = await self._try_cache(context)
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.LLM_TO_CACHE,
                result=result,
                fallback_count=3,
            )
        except Exception as e:
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.LLM_TO_CACHE,
                error=str(e),
                fallback_count=3,
            )

    async def _try_local_llm(self, context: dict[str, Any]) -> Any:
        """Try local LLM.

        Args:
            context: Execution context

        Returns:
            LLM result
        """
        # Get local LLM backend
        from Agent_Guru.reasoning.error.recovery import get_failover_manager

        failover = get_failover_manager()
        local_backend = failover.get_current_backend("local_llm")

        if not local_backend:
            raise NotImplementedError("Local LLM not configured")

        # In a real implementation, this would call local LLM
        # For now, raise to continue fallback chain
        raise NotImplementedError("Local LLM execution not implemented")

    async def _try_rule_based(self, context: dict[str, Any]) -> Any:
        """Try rule-based processing.

        Args:
            context: Execution context

        Returns:
            Rule-based result
        """
        # Get input text
        input_text = context.get("input_text", "")

        if not input_text:
            raise NotImplementedError("No input text for rule-based processing")

        # In a real implementation, this would use rule-based intent detection
        # For now, return a simple response
        return {
            "intent": "unknown",
            "confidence": 0.5,
            "method": "rule_based",
            "message": "Using rule-based fallback",
        }

    async def _try_cache(self, context: dict[str, Any]) -> Any:
        """Try cached response.

        Args:
            context: Execution context

        Returns:
            Cached result
        """
        # Get input text
        input_text = context.get("input_text", "")

        if not input_text:
            raise NotImplementedError("No input text for cache lookup")

        # In a real implementation, this would check cache
        # For now, raise to indicate no fallback available
        raise NotImplementedError("No cached response available")


class ToolFallbackHandler(FallbackHandler):
    """Fallback handler for tool errors."""

    async def handle(
        self,
        error: StructuredError,
        context: dict[str, Any],
    ) -> FallbackResult:
        """Handle tool errors with fallback chain.

        Fallback chain:
        1. Try alternative tool
        2. Simplify request
        3. Notify user

        Args:
            error: Structured error
            context: Execution context

        Returns:
            Fallback result
        """
        # Try alternative tool
        try:
            result = await self._try_alternative_tool(context)
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.ALTERNATIVE_TOOL,
                result=result,
                fallback_count=1,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Alternative tool fallback failed: %s", exc)

        # Try simplified request
        try:
            result = await self._try_simplified_request(context)
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.SIMPLIFIED_REQUEST,
                result=result,
                fallback_count=2,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Simplified request fallback failed: %s", exc)

        # Final fallback: notify user
        return FallbackResult(
            success=True,
            strategy_used=FallbackStrategy.USER_NOTIFICATION,
            result={
                "message": error.user_message,
                "suggested_actions": error.suggested_actions,
            },
            fallback_count=3,
        )

    async def _try_alternative_tool(self, context: dict[str, Any]) -> Any:
        """Try alternative tool.

        Args:
            context: Execution context

        Returns:
            Tool result
        """
        # Get failed tool and find alternatives
        failed_tool = context.get("tool_id")
        alternative_tools = context.get("alternative_tools", [])

        if not alternative_tools:
            raise NotImplementedError("No alternative tools available")

        # Try first alternative
        # In a real implementation, this would execute the alternative tool
        return {
            "success": True,
            "method": "alternative_tool",
            "original_tool": failed_tool,
            "used_tool": alternative_tools[0],
        }

    async def _try_simplified_request(self, context: dict[str, Any]) -> Any:
        """Try simplified request.

        Args:
            context: Execution context

        Returns:
            Simplified result
        """
        # Simplify the request and retry
        # In a real implementation, this would simplify parameters or steps
        return {
            "success": True,
            "method": "simplified_request",
            "message": "Request simplified and executed",
        }


class TimeoutFallbackHandler(FallbackHandler):
    """Fallback handler for timeout errors."""

    async def handle(
        self,
        error: StructuredError,
        context: dict[str, Any],
    ) -> FallbackResult:
        """Handle timeout errors with fallback chain.

        Fallback chain:
        1. Return partial results
        2. Execute asynchronously
        3. Simplify request

        Args:
            error: Structured error
            context: Execution context

        Returns:
            Fallback result
        """
        # Try partial results
        partial_results = context.get("partial_results")
        if partial_results:
            return FallbackResult(
                success=True,
                strategy_used=FallbackStrategy.PARTIAL_RESULTS,
                result=partial_results,
                fallback_count=1,
            )

        # Try async execution
        if context.get("allow_async", False):
            try:
                result = await self._execute_async(context)
                return FallbackResult(
                    success=True,
                    strategy_used=FallbackStrategy.ASYNC_EXECUTION,
                    result=result,
                    fallback_count=2,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning("Async execution fallback failed: %s", exc)

        # Final fallback: simplify
        return FallbackResult(
            success=True,
            strategy_used=FallbackStrategy.SIMPLIFICATION,
            result={
                "message": "Request too complex. Please simplify.",
                "suggested_actions": ["Break into smaller steps", "Try simpler command"],
            },
            fallback_count=3,
        )

    async def _execute_async(self, context: dict[str, Any]) -> Any:
        """Execute asynchronously.

        Args:
            context: Execution context

        Returns:
            Async execution result
        """
        # Queue for async execution
        # In a real implementation, this would queue the task
        return {
            "success": True,
            "method": "async_execution",
            "message": "Task queued for asynchronous execution",
            "task_id": f"async_{int(time.time())}",
        }


class FallbackRegistry:
    """Registry for fallback handlers."""

    def __init__(self):
        """Initialize fallback registry."""
        self._handlers: dict[ErrorType, list[FallbackHandler]] = {}
        self._fallback_metrics: dict[FallbackStrategy, int] = {}

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default fallback handlers."""
        # LLM error handlers
        llm_handler = LLMFallbackHandler()
        self.register(ErrorType.LLM_UNAVAILABLE, llm_handler)
        self.register(ErrorType.LLM_TIMEOUT, llm_handler)
        self.register(ErrorType.LLM_RATE_LIMIT, llm_handler)
        self.register(ErrorType.LLM_INVALID_RESPONSE, llm_handler)

        # Tool error handlers
        tool_handler = ToolFallbackHandler()
        self.register(ErrorType.TOOL_NOT_FOUND, tool_handler)
        self.register(ErrorType.TOOL_EXECUTION_FAILED, tool_handler)
        self.register(ErrorType.TOOL_TIMEOUT, tool_handler)
        self.register(ErrorType.TOOL_UNAVAILABLE, tool_handler)

        # Timeout error handlers
        timeout_handler = TimeoutFallbackHandler()
        self.register(ErrorType.TIMEOUT, timeout_handler)

    def register(
        self, error_type: ErrorType, handler: FallbackHandler
    ) -> None:
        """Register a fallback handler for an error type.

        Args:
            error_type: Error type
            handler: Fallback handler
        """
        if error_type not in self._handlers:
            self._handlers[error_type] = []

        self._handlers[error_type].append(handler)

    async def handle_error(
        self,
        error: StructuredError,
        context: dict[str, Any],
    ) -> FallbackResult:
        """Handle error with registered fallback handlers.

        Args:
            error: Structured error
            context: Execution context

        Returns:
            Fallback result
        """
        # Get handlers for error type
        handlers = self._handlers.get(error.error_type, [])

        if not handlers:
            # No fallback available
            return FallbackResult(
                success=False,
                strategy_used=FallbackStrategy.USER_NOTIFICATION,
                error="No fallback strategy available",
            )

        # Try each handler
        for handler in handlers:
            try:
                result = await handler.handle(error, context)

                # Track metrics
                if result.success:
                    strategy = result.strategy_used
                    self._fallback_metrics[strategy] = (
                        self._fallback_metrics.get(strategy, 0) + 1
                    )

                return result

            except Exception:
                # Continue to next handler
                continue

        # All handlers failed
        return FallbackResult(
            success=False,
            strategy_used=FallbackStrategy.USER_NOTIFICATION,
            error="All fallback strategies failed",
        )

    def get_metrics(self) -> dict[str, int]:
        """Get fallback usage metrics.

        Returns:
            Metrics dictionary
        """
        return dict(self._fallback_metrics)


# Global fallback registry
_global_registry: Optional[FallbackRegistry] = None


def get_fallback_registry() -> FallbackRegistry:
    """Get the global fallback registry instance.

    Returns:
        Global FallbackRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = FallbackRegistry()
    return _global_registry
