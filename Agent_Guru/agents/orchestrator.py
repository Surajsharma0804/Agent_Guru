"""
Agent Orchestrator - Multi-agent coordination with self-improvement integration.

This module provides the orchestration layer for Agent Guru, coordinating
multiple agents and integrating with the self-improvement engine for
continuous learning and optimization.

**Integration with Self-Improvement Engine**:
- Strategy selection before task execution
- Outcome recording after task completion
- Performance tracking and optimization

Author: Agent Guru Team
Date: 2026-02-28
Version: 1.0.0
"""

import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    """Status of a task execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Represents a task to be executed."""
    task_id: str
    task_type: str
    description: str
    parameters: Dict[str, Any]
    created_at: datetime
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    success: bool
    result: Optional[Any]
    error: Optional[str]
    execution_time_ms: float
    strategy_used: str


class AgentOrchestrator:
    """
    Orchestrates multi-agent task execution with self-improvement integration.
    
    This class coordinates task execution across multiple agents and integrates
    with the self-improvement engine to:
    1. Select optimal strategies before task execution
    2. Record outcomes after task completion
    3. Track performance and enable continuous learning
    
    Time Complexity: O(1) for task execution overhead
    Space Complexity: O(n) where n is number of active tasks
    
    Example:
        >>> from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
        >>> 
        >>> # Initialize with self-improvement engine
        >>> engine = SelfImprovementEngine("data/learning.db")
        >>> orchestrator = AgentOrchestrator(self_improvement_engine=engine)
        >>> 
        >>> # Execute task with learning
        >>> result = orchestrator.execute_task(
        ...     task_id="task_1",
        ...     task_type="analysis",
        ...     description="Analyze data",
        ...     parameters={"data": [1, 2, 3]},
        ...     executor=my_analysis_function
        ... )
        >>> 
        >>> print(f"Success: {result.success}")
        >>> print(f"Strategy used: {result.strategy_used}")
    """
    
    def __init__(
        self,
        self_improvement_engine: Optional[Any] = None,
        enable_learning: bool = True
    ):
        """
        Initialize agent orchestrator.
        
        Args:
            self_improvement_engine: Optional SelfImprovementEngine instance
            enable_learning: Whether to enable self-improvement learning
            
        Time Complexity: O(1)
        """
        self.self_improvement_engine = self_improvement_engine
        self.enable_learning = enable_learning
        self.active_tasks: Dict[str, Task] = {}
        
        # Default strategy if no engine provided
        self.default_strategy = "default_strategy"
    
    def execute_task(
        self,
        task_id: str,
        task_type: str,
        description: str,
        parameters: Dict[str, Any],
        executor: Callable[[Dict[str, Any]], Any],
        context: Optional[Dict[str, Any]] = None
    ) -> TaskResult:
        """
        Execute a task with self-improvement integration.
        
        This method:
        1. Gets optimal strategy from self-improvement engine
        2. Executes the task with instrumentation
        3. Records outcome for learning
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task (e.g., "analysis", "generation")
            description: Human-readable task description
            parameters: Task parameters
            executor: Function to execute the task
            context: Optional context for strategy selection
            
        Returns:
            TaskResult with execution outcome
            
        Time Complexity: O(1) + O(executor)
        Performance Target: <10% overhead on task execution
        
        Validates: Requirements 15.2, 15.3, 15.4
        """
        # Create task
        task = Task(
            task_id=task_id,
            task_type=task_type,
            description=description,
            parameters=parameters,
            created_at=datetime.now(),
            status=TaskStatus.PENDING
        )
        
        self.active_tasks[task_id] = task
        
        # Phase 1: Strategy selection (before execution)
        strategy_id = self._select_strategy(task_type, context)
        
        # Phase 2: Task execution with instrumentation
        task.status = TaskStatus.IN_PROGRESS
        start_time = time.perf_counter()
        
        try:
            # Execute task
            result = executor(parameters)
            
            # Calculate execution time
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.execution_time_ms = execution_time_ms
            
            # Create result
            task_result = TaskResult(
                task_id=task_id,
                success=True,
                result=result,
                error=None,
                execution_time_ms=execution_time_ms,
                strategy_used=strategy_id
            )
            
        except Exception as e:
            # Calculate execution time
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Mark as failed
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.execution_time_ms = execution_time_ms
            
            # Create result
            task_result = TaskResult(
                task_id=task_id,
                success=False,
                result=None,
                error=str(e),
                execution_time_ms=execution_time_ms,
                strategy_used=strategy_id
            )
        
        # Phase 3: Outcome recording (after execution)
        self._record_outcome(task_result, task_type, context)
        
        # Cleanup
        del self.active_tasks[task_id]
        
        return task_result
    
    def _select_strategy(
        self,
        task_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Select optimal strategy for task execution.
        
        Queries self-improvement engine for best strategy based on
        historical performance.
        
        Args:
            task_type: Type of task
            context: Optional context for selection
            
        Returns:
            Strategy ID to use
            
        Time Complexity: O(log n) where n is strategies
        Performance Target: <5ms
        
        Validates: Requirement 15.3
        """
        if not self.enable_learning or not self.self_improvement_engine:
            return self.default_strategy
        
        try:
            # Get optimal strategy from self-improvement engine
            strategy = self.self_improvement_engine.get_optimal_strategy(
                task_type=task_type,
                context=context
            )
            
            if strategy:
                return strategy.strategy_id
            else:
                return self.default_strategy
                
        except Exception as e:
            # Fallback to default if error
            print(f"Warning: Strategy selection failed: {e}")
            return self.default_strategy
    
    def _record_outcome(
        self,
        result: TaskResult,
        task_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record task outcome for learning.
        
        Sends execution outcome to self-improvement engine for analysis
        and continuous learning.
        
        Args:
            result: Task execution result
            task_type: Type of task that was executed
            context: Optional execution context
            
        Time Complexity: O(1)
        Performance Target: <5ms
        
        Validates: Requirement 15.4
        """
        if not self.enable_learning or not self.self_improvement_engine:
            return
        
        try:
            # Prepare error details if failed
            error_details = None
            if not result.success and result.error:
                error_details = {
                    "type": "execution_error",
                    "error": result.error,
                    "task_id": result.task_id
                }
            
            # Record in self-improvement engine
            self.self_improvement_engine.record_task_execution(
                task_id=result.task_id,
                task_type=task_type,
                strategy_used=result.strategy_used,
                success=result.success,
                execution_time_ms=result.execution_time_ms,
                error_details=error_details,
                context=context
            )
            
        except Exception as e:
            # Don't fail task if recording fails
            print(f"Warning: Outcome recording failed: {e}")
    
    def get_active_tasks(self) -> Dict[str, Task]:
        """
        Get currently active tasks.
        
        Returns:
            Dictionary of active tasks by task_id
            
        Time Complexity: O(1)
        """
        return self.active_tasks.copy()
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        Get status of a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status or None if not found
            
        Time Complexity: O(1)
        """
        task = self.active_tasks.get(task_id)
        return task.status if task else None


# Integration helper functions

def create_orchestrator_with_learning(
    storage_path: str,
    improvement_threshold: float = 0.15,
    measurement_window: int = 100
) -> AgentOrchestrator:
    """
    Create an orchestrator with self-improvement learning enabled.
    
    This is a convenience function that initializes both the self-improvement
    engine and the orchestrator with proper integration.
    
    Args:
        storage_path: Path to SQLite database for learning data
        improvement_threshold: Minimum improvement required (15%)
        measurement_window: Number of tasks for improvement measurement (100)
        
    Returns:
        Configured AgentOrchestrator instance
        
    Example:
        >>> orchestrator = create_orchestrator_with_learning("data/learning.db")
        >>> result = orchestrator.execute_task(
        ...     task_id="task_1",
        ...     task_type="analysis",
        ...     description="Analyze data",
        ...     parameters={"data": [1, 2, 3]},
        ...     executor=lambda p: sum(p["data"])
        ... )
        >>> print(f"Result: {result.result}")
    """
    from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
    
    # Initialize self-improvement engine
    engine = SelfImprovementEngine(
        storage_path=storage_path,
        improvement_threshold=improvement_threshold,
        measurement_window=measurement_window,
        enable_git_commits=False  # Disable for production
    )
    
    # Create orchestrator with engine
    orchestrator = AgentOrchestrator(
        self_improvement_engine=engine,
        enable_learning=True
    )
    
    return orchestrator
