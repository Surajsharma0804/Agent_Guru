"""
Graceful degradation for self-improvement engine.

Ensures system continues functioning even if self-improvement engine fails.
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging


class DegradationMode(Enum):
    """Degradation modes."""
    NORMAL = "normal"  # Full functionality
    DEGRADED = "degraded"  # Limited functionality
    FALLBACK = "fallback"  # Minimal functionality


@dataclass
class FallbackStrategy:
    """Fallback strategy when engine fails."""
    strategy_id: str = "default"
    name: str = "Default Strategy"
    description: str = "Basic fallback strategy"
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class GracefulDegradationHandler:
    """
    Handles graceful degradation when self-improvement engine fails.
    
    Ensures Agent Guru continues functioning with baseline capabilities
    even if learning system is unavailable.
    """
    
    def __init__(
        self,
        fallback_strategy: Optional[FallbackStrategy] = None,
        error_callback: Optional[Callable[[Exception], None]] = None
    ):
        """
        Initialize graceful degradation handler.
        
        Args:
            fallback_strategy: Strategy to use when engine fails
            error_callback: Optional callback for error notifications
        """
        self.fallback_strategy = fallback_strategy or FallbackStrategy()
        self.error_callback = error_callback
        self.mode = DegradationMode.NORMAL
        self.failure_count = 0
        self.last_failure: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)
    
    def wrap_operation(
        self,
        operation: Callable[[], Any],
        fallback_value: Any = None,
        operation_name: str = "operation"
    ) -> Any:
        """
        Wrap an operation with graceful degradation.
        
        If operation fails, logs error and returns fallback value.
        
        Args:
            operation: Function to execute
            fallback_value: Value to return on failure
            operation_name: Name for logging
            
        Returns:
            Operation result or fallback value
        """
        try:
            result = operation()
            
            # Reset failure count on success
            if self.failure_count > 0:
                self.logger.info(f"{operation_name} recovered after {self.failure_count} failures")
                self.failure_count = 0
                self.mode = DegradationMode.NORMAL
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure = datetime.now()
            
            # Update degradation mode based on failure count
            if self.failure_count >= 10:
                self.mode = DegradationMode.FALLBACK
            elif self.failure_count >= 3:
                self.mode = DegradationMode.DEGRADED
            
            self.logger.error(
                f"{operation_name} failed (count: {self.failure_count}): {e}",
                exc_info=True
            )
            
            # Notify error callback
            if self.error_callback:
                try:
                    self.error_callback(e)
                except Exception as callback_error:
                    self.logger.error(f"Error callback failed: {callback_error}")
            
            return fallback_value
    
    def get_strategy_with_fallback(
        self,
        get_strategy_func: Callable[[], Any],
        task_type: str
    ) -> Any:
        """
        Get optimal strategy with fallback.
        
        Args:
            get_strategy_func: Function to get optimal strategy
            task_type: Type of task
            
        Returns:
            Strategy or fallback strategy
        """
        return self.wrap_operation(
            operation=get_strategy_func,
            fallback_value=self.fallback_strategy,
            operation_name=f"get_strategy({task_type})"
        )
    
    def record_execution_with_fallback(
        self,
        record_func: Callable[[], None],
        task_id: str
    ) -> bool:
        """
        Record task execution with fallback.
        
        Args:
            record_func: Function to record execution
            task_id: Task identifier
            
        Returns:
            True if recorded successfully, False otherwise
        """
        result = self.wrap_operation(
            operation=record_func,
            fallback_value=False,
            operation_name=f"record_execution({task_id})"
        )
        
        return result is not False
    
    def get_metrics_with_fallback(
        self,
        get_metrics_func: Callable[[], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get metrics with fallback.
        
        Args:
            get_metrics_func: Function to get metrics
            
        Returns:
            Metrics dictionary or empty dict
        """
        return self.wrap_operation(
            operation=get_metrics_func,
            fallback_value={
                "mode": self.mode.value,
                "failure_count": self.failure_count,
                "last_failure": self.last_failure.isoformat() if self.last_failure else None,
                "message": "Self-improvement engine unavailable, using fallback"
            },
            operation_name="get_metrics"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get degradation handler status.
        
        Returns:
            Status dictionary
        """
        return {
            "mode": self.mode.value,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "fallback_strategy": {
                "id": self.fallback_strategy.strategy_id,
                "name": self.fallback_strategy.name,
                "description": self.fallback_strategy.description
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def reset(self) -> None:
        """Reset degradation handler to normal mode."""
        self.mode = DegradationMode.NORMAL
        self.failure_count = 0
        self.last_failure = None
        self.logger.info("Degradation handler reset to normal mode")


class SelfImprovementEngineWrapper:
    """
    Wrapper for self-improvement engine with graceful degradation.
    
    Provides same interface as SelfImprovementEngine but with fallback behavior.
    """
    
    def __init__(
        self,
        engine: Any,
        degradation_handler: Optional[GracefulDegradationHandler] = None
    ):
        """
        Initialize wrapper.
        
        Args:
            engine: SelfImprovementEngine instance
            degradation_handler: Optional degradation handler
        """
        self.engine = engine
        self.degradation_handler = degradation_handler or GracefulDegradationHandler()
        self.logger = logging.getLogger(__name__)
    
    def record_task_execution(
        self,
        task_id: str,
        task_type: str,
        strategy_used: str,
        success: bool,
        execution_time_ms: float,
        error_details: Optional[Dict] = None,
        context: Optional[Dict] = None
    ) -> None:
        """Record task execution with fallback."""
        def record():
            self.engine.record_task_execution(
                task_id=task_id,
                task_type=task_type,
                strategy_used=strategy_used,
                success=success,
                execution_time_ms=execution_time_ms,
                error_details=error_details,
                context=context
            )
        
        self.degradation_handler.record_execution_with_fallback(
            record_func=record,
            task_id=task_id
        )
    
    def get_optimal_strategy(
        self,
        task_type: str,
        context: Optional[Dict] = None
    ) -> Any:
        """Get optimal strategy with fallback."""
        def get_strategy():
            return self.engine.get_optimal_strategy(task_type, context)
        
        return self.degradation_handler.get_strategy_with_fallback(
            get_strategy_func=get_strategy,
            task_type=task_type
        )
    
    def get_improvement_metrics(self) -> Dict[str, Any]:
        """Get improvement metrics with fallback."""
        def get_metrics():
            return self.engine.get_improvement_metrics()
        
        return self.degradation_handler.get_metrics_with_fallback(
            get_metrics_func=get_metrics
        )
    
    def get_evolved_prompt(
        self,
        prompt_type: str,
        context: Dict[str, Any]
    ) -> str:
        """Get evolved prompt with fallback."""
        def get_prompt():
            return self.engine.get_evolved_prompt(prompt_type, context)
        
        return self.degradation_handler.wrap_operation(
            operation=get_prompt,
            fallback_value=f"Default prompt for {prompt_type}",
            operation_name=f"get_evolved_prompt({prompt_type})"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get wrapper status including degradation info."""
        return {
            "engine_status": self.degradation_handler.wrap_operation(
                operation=lambda: {"available": True},
                fallback_value={"available": False},
                operation_name="engine_status"
            ),
            "degradation": self.degradation_handler.get_status(),
            "timestamp": datetime.now().isoformat()
        }
