"""
Recovery Orchestrator

Coordinates recovery procedures for failed components with comprehensive
recovery planning, execution monitoring, and rollback capabilities.

This system provides:
- Automated recovery plan generation
- Recovery action execution and monitoring
- Recovery rollback on failure
- Recovery success validation
- Recovery history and analytics
"""

import logging
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Import types at runtime to avoid circular imports
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .failure_detector import ComponentFailure

from .dependency_mapper import DependencyMapper


class RecoveryActionType(Enum):
    """Types of recovery actions."""
    RESTART_COMPONENT = "restart_component"
    RESET_CONFIGURATION = "reset_configuration"
    CLEAR_CACHE = "clear_cache"
    RESTORE_BACKUP = "restore_backup"
    REINITIALIZE_RESOURCES = "reinitialize_resources"
    REPAIR_DATA = "repair_data"
    ESCALATE_TO_ADMIN = "escalate_to_admin"
    SAFE_SHUTDOWN = "safe_shutdown"
    ROLLBACK_CHANGES = "rollback_changes"
    VALIDATE_INTEGRITY = "validate_integrity"


class RecoveryStatus(Enum):
    """Status of recovery operations."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


@dataclass
class RecoveryAction:
    """Represents a single recovery action."""
    action_id: str
    action_type: RecoveryActionType
    component_name: str
    description: str
    estimated_duration_seconds: float
    risk_level: str  # "low", "medium", "high", "critical"
    prerequisites: List[str] = field(default_factory=list)
    rollback_action: Optional['RecoveryAction'] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class RecoveryPlan:
    """Complete recovery plan for one or more failed components."""
    plan_id: str
    failed_components: List[str]
    root_failure: 'ComponentFailure'
    recovery_actions: List[RecoveryAction]
    estimated_total_duration: float
    success_criteria: List[str]
    rollback_plan: List[RecoveryAction]
    created_at: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1=highest, 5=lowest


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    plan_id: str
    action_id: str
    status: RecoveryStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    recovery_data: Dict[str, Any] = field(default_factory=dict)
    rollback_performed: bool = False


class RecoveryOrchestrator:
    """
    Orchestrates recovery procedures for failed GURU components.
    
    Provides comprehensive recovery planning, execution monitoring,
    and rollback capabilities to restore system functionality after
    component failures while maintaining security boundaries.
    """
    
    def __init__(self, dependency_mapper: Optional[DependencyMapper] = None):
        self.dependency_mapper = dependency_mapper or DependencyMapper()
        self.logger = logging.getLogger(__name__)
        
        # Recovery state
        self._active_recoveries: Dict[str, RecoveryPlan] = {}
        self._recovery_history: List[RecoveryResult] = []
        self._recovery_lock = threading.RLock()
        
        # Recovery execution
        self._recovery_executor = ThreadPoolExecutor(
            max_workers=3,  # Limit concurrent recoveries
            thread_name_prefix="RecoveryOrchestrator"
        )
        self._active_futures: Dict[str, Future] = {}
        
        # Recovery callbacks
        self._recovery_callbacks: List[Callable[[RecoveryResult], None]] = []
        self._plan_callbacks: List[Callable[[RecoveryPlan], None]] = []
        
        # Recovery strategies
        self._recovery_strategies = self._initialize_recovery_strategies()
        
        # Performance tracking
        self._recovery_stats = {
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "average_recovery_time": 0.0
        }
        
    def _initialize_recovery_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Initialize recovery strategies for different component types."""
        # Import at runtime to avoid circular imports
        from .failure_detector import FailureType
        
        return {
            # Authority system recovery
            "authority_state_machine": {
                "strategies": [
                    {
                        "failure_types": [FailureType.COMPONENT_UNRESPONSIVE],
                        "actions": [
                            RecoveryAction(
                                action_id="restart_authority",
                                action_type=RecoveryActionType.RESTART_COMPONENT,
                                component_name="authority_state_machine",
                                description="Restart authority state machine with current state preservation",
                                estimated_duration_seconds=5.0,
                                risk_level="high",
                                timeout_seconds=10.0
                            ),
                            RecoveryAction(
                                action_id="validate_authority_integrity",
                                action_type=RecoveryActionType.VALIDATE_INTEGRITY,
                                component_name="authority_state_machine",
                                description="Validate authority state integrity after restart",
                                estimated_duration_seconds=3.0,
                                risk_level="medium",
                                timeout_seconds=5.0
                            )
                        ]
                    }
                ],
                "critical": True,
                "max_recovery_attempts": 2
            },
            
            # Input engine recovery
            "input_engine": {
                "strategies": [
                    {
                        "failure_types": [FailureType.COMPONENT_UNRESPONSIVE, FailureType.RESOURCE_EXHAUSTION],
                        "actions": [
                            RecoveryAction(
                                action_id="clear_input_cache",
                                action_type=RecoveryActionType.CLEAR_CACHE,
                                component_name="input_engine",
                                description="Clear input event cache and reset state",
                                estimated_duration_seconds=2.0,
                                risk_level="low",
                                timeout_seconds=5.0
                            ),
                            RecoveryAction(
                                action_id="restart_input_engine",
                                action_type=RecoveryActionType.RESTART_COMPONENT,
                                component_name="input_engine",
                                description="Restart input simulation engine",
                                estimated_duration_seconds=3.0,
                                risk_level="medium",
                                timeout_seconds=10.0
                            )
                        ]
                    }
                ],
                "critical": False,
                "max_recovery_attempts": 3
            },
            
            # Memory service recovery
            "memory_service": {
                "strategies": [
                    {
                        "failure_types": [FailureType.COMPONENT_UNRESPONSIVE],
                        "actions": [
                            RecoveryAction(
                                action_id="repair_memory_database",
                                action_type=RecoveryActionType.REPAIR_DATA,
                                component_name="memory_service",
                                description="Repair memory database integrity",
                                estimated_duration_seconds=10.0,
                                risk_level="medium",
                                timeout_seconds=30.0
                            ),
                            RecoveryAction(
                                action_id="restart_memory_service",
                                action_type=RecoveryActionType.RESTART_COMPONENT,
                                component_name="memory_service",
                                description="Restart memory service with database validation",
                                estimated_duration_seconds=5.0,
                                risk_level="medium",
                                timeout_seconds=15.0
                            )
                        ]
                    },
                    {
                        "failure_types": [FailureType.INTEGRITY_VIOLATION],
                        "actions": [
                            RecoveryAction(
                                action_id="restore_memory_backup",
                                action_type=RecoveryActionType.RESTORE_BACKUP,
                                component_name="memory_service",
                                description="Restore memory service from last known good backup",
                                estimated_duration_seconds=15.0,
                                risk_level="high",
                                timeout_seconds=60.0
                            )
                        ]
                    }
                ],
                "critical": False,
                "max_recovery_attempts": 2
            },
            
            # LLM adapter recovery
            "llm_adapter": {
                "strategies": [
                    {
                        "failure_types": [FailureType.EXTERNAL_DEPENDENCY_FAILURE],
                        "actions": [
                            RecoveryAction(
                                action_id="reset_llm_connections",
                                action_type=RecoveryActionType.RESET_CONFIGURATION,
                                component_name="llm_adapter",
                                description="Reset LLM provider connections and authentication",
                                estimated_duration_seconds=5.0,
                                risk_level="low",
                                timeout_seconds=10.0
                            ),
                            RecoveryAction(
                                action_id="fallback_to_local_llm",
                                action_type=RecoveryActionType.RESET_CONFIGURATION,
                                component_name="llm_adapter",
                                description="Switch to local LLM provider as fallback",
                                estimated_duration_seconds=3.0,
                                risk_level="low",
                                timeout_seconds=5.0
                            )
                        ]
                    }
                ],
                "critical": False,
                "max_recovery_attempts": 3
            },
            
            # Skill runner recovery
            "skill_runner": {
                "strategies": [
                    {
                        "failure_types": [FailureType.COMPONENT_UNRESPONSIVE, FailureType.RESOURCE_EXHAUSTION],
                        "actions": [
                            RecoveryAction(
                                action_id="terminate_running_skills",
                                action_type=RecoveryActionType.SAFE_SHUTDOWN,
                                component_name="skill_runner",
                                description="Safely terminate all running skills",
                                estimated_duration_seconds=5.0,
                                risk_level="medium",
                                timeout_seconds=10.0
                            ),
                            RecoveryAction(
                                action_id="reinitialize_skill_sandbox",
                                action_type=RecoveryActionType.REINITIALIZE_RESOURCES,
                                component_name="skill_runner",
                                description="Reinitialize skill execution sandbox",
                                estimated_duration_seconds=8.0,
                                risk_level="medium",
                                timeout_seconds=15.0
                            )
                        ]
                    }
                ],
                "critical": False,
                "max_recovery_attempts": 2
            },
            
            # Audit logger recovery (critical)
            "audit_logger": {
                "strategies": [
                    {
                        "failure_types": [FailureType.INTEGRITY_VIOLATION],
                        "actions": [
                            RecoveryAction(
                                action_id="escalate_audit_failure",
                                action_type=RecoveryActionType.ESCALATE_TO_ADMIN,
                                component_name="audit_logger",
                                description="Escalate audit logger integrity violation to administrator",
                                estimated_duration_seconds=1.0,
                                risk_level="critical",
                                timeout_seconds=5.0
                            )
                        ]
                    }
                ],
                "critical": True,
                "max_recovery_attempts": 1  # Audit failures are not automatically recoverable
            }
        }
    
    def add_recovery_callback(self, callback: Callable[[RecoveryResult], None]) -> None:
        """Add callback for recovery completion events."""
        self._recovery_callbacks.append(callback)
    
    def add_plan_callback(self, callback: Callable[[RecoveryPlan], None]) -> None:
        """Add callback for recovery plan creation events."""
        self._plan_callbacks.append(callback)
    
    def create_recovery_plan(self, failure: 'ComponentFailure') -> Optional[RecoveryPlan]:
        """Create a recovery plan for a component failure."""
        component_name = failure.component_name
        
        # Get recovery strategy for this component
        strategy = self._recovery_strategies.get(component_name)
        if not strategy:
            self.logger.warning(f"No recovery strategy defined for component '{component_name}'")
            return None
        
        # Import at runtime to avoid circular imports
        
        # Find matching strategy for this failure type
        matching_strategy = None
        for strat in strategy["strategies"]:
            if failure.failure_type in strat["failure_types"]:
                matching_strategy = strat
                break
        
        if not matching_strategy:
            self.logger.warning(f"No recovery strategy for failure type {failure.failure_type.value} "
                              f"in component '{component_name}'")
            return None
        
        # Create recovery actions
        recovery_actions = []
        total_duration = 0.0
        
        for action_template in matching_strategy["actions"]:
            # Create a copy of the action with unique ID
            action = RecoveryAction(
                action_id=f"{action_template.action_id}_{int(time.time())}",
                action_type=action_template.action_type,
                component_name=action_template.component_name,
                description=action_template.description,
                estimated_duration_seconds=action_template.estimated_duration_seconds,
                risk_level=action_template.risk_level,
                prerequisites=action_template.prerequisites.copy(),
                parameters=action_template.parameters.copy(),
                timeout_seconds=action_template.timeout_seconds,
                max_retries=action_template.max_retries
            )
            
            recovery_actions.append(action)
            total_duration += action.estimated_duration_seconds
        
        # Create rollback plan
        rollback_plan = self._create_rollback_plan(recovery_actions)
        
        # Create success criteria
        success_criteria = self._create_success_criteria(component_name, failure)
        
        # Determine priority based on component criticality and failure severity
        priority = self._determine_recovery_priority(failure, strategy.get("critical", False))
        
        plan = RecoveryPlan(
            plan_id=f"recovery_{component_name}_{int(time.time())}",
            failed_components=[component_name],
            root_failure=failure,
            recovery_actions=recovery_actions,
            estimated_total_duration=total_duration,
            success_criteria=success_criteria,
            rollback_plan=rollback_plan,
            priority=priority
        )
        
        # Notify plan callbacks
        for callback in self._plan_callbacks:
            try:
                callback(plan)
            except Exception as e:
                self.logger.error(f"Error in plan callback: {e}")
        
        self.logger.info(f"Created recovery plan '{plan.plan_id}' for component '{component_name}' "
                        f"with {len(recovery_actions)} actions (estimated {total_duration:.1f}s)")
        
        return plan
    
    def _create_rollback_plan(self, recovery_actions: List[RecoveryAction]) -> List[RecoveryAction]:
        """Create rollback plan for recovery actions."""
        rollback_actions = []
        
        for action in reversed(recovery_actions):  # Rollback in reverse order
            if action.action_type == RecoveryActionType.RESTART_COMPONENT:
                # Rollback: Stop component
                rollback_action = RecoveryAction(
                    action_id=f"rollback_{action.action_id}",
                    action_type=RecoveryActionType.SAFE_SHUTDOWN,
                    component_name=action.component_name,
                    description=f"Rollback: Stop {action.component_name} after failed restart",
                    estimated_duration_seconds=3.0,
                    risk_level="medium",
                    timeout_seconds=10.0
                )
                rollback_actions.append(rollback_action)
            
            elif action.action_type == RecoveryActionType.RESET_CONFIGURATION:
                # Rollback: Restore previous configuration
                rollback_action = RecoveryAction(
                    action_id=f"rollback_{action.action_id}",
                    action_type=RecoveryActionType.RESTORE_BACKUP,
                    component_name=action.component_name,
                    description=f"Rollback: Restore previous configuration for {action.component_name}",
                    estimated_duration_seconds=5.0,
                    risk_level="medium",
                    timeout_seconds=15.0
                )
                rollback_actions.append(rollback_action)
            
            elif action.action_type == RecoveryActionType.RESTORE_BACKUP:
                # Rollback: This is already a restore operation, log the attempt
                rollback_action = RecoveryAction(
                    action_id=f"rollback_{action.action_id}",
                    action_type=RecoveryActionType.ESCALATE_TO_ADMIN,
                    component_name=action.component_name,
                    description=f"Rollback: Escalate failed backup restore for {action.component_name}",
                    estimated_duration_seconds=1.0,
                    risk_level="critical",
                    timeout_seconds=5.0
                )
                rollback_actions.append(rollback_action)
        
        return rollback_actions
    
    def _create_success_criteria(self, component_name: str, failure: 'ComponentFailure') -> List[str]:
        """Create success criteria for recovery validation."""
        # Import at runtime to avoid circular imports
        from .failure_detector import FailureType
        
        criteria = [
            f"Component '{component_name}' responds to health checks",
            f"Component '{component_name}' passes basic functionality tests",
            f"No active failures reported for component '{component_name}'"
        ]
        
        # Add failure-specific criteria
        if failure.failure_type == FailureType.RESOURCE_EXHAUSTION:
            criteria.append(f"Resource usage for '{component_name}' is within normal limits")
        
        if failure.failure_type == FailureType.INTEGRITY_VIOLATION:
            criteria.append(f"Data integrity verified for component '{component_name}'")
        
        if failure.failure_type == FailureType.SECURITY_VIOLATION:
            criteria.append(f"Security boundaries verified for component '{component_name}'")
        
        return criteria
    
    def _determine_recovery_priority(self, failure: 'ComponentFailure', is_critical: bool) -> int:
        """Determine recovery priority (1=highest, 5=lowest)."""
        # Import at runtime to avoid circular imports
        from .failure_detector import FailureSeverity
        
        if failure.severity == FailureSeverity.FATAL:
            return 1
        elif failure.severity == FailureSeverity.CRITICAL or is_critical:
            return 1
        elif failure.severity == FailureSeverity.HIGH:
            return 2
        elif failure.severity == FailureSeverity.MEDIUM:
            return 3
        else:
            return 4
    
    def execute_recovery_plan(self, plan: RecoveryPlan) -> Future[List[RecoveryResult]]:
        """Execute a recovery plan asynchronously."""
        with self._recovery_lock:
            self._active_recoveries[plan.plan_id] = plan
        
        # Submit recovery execution to thread pool
        future = self._recovery_executor.submit(self._execute_recovery_plan_sync, plan)
        self._active_futures[plan.plan_id] = future
        
        self.logger.info(f"Started execution of recovery plan '{plan.plan_id}'")
        return future
    
    def _execute_recovery_plan_sync(self, plan: RecoveryPlan) -> List[RecoveryResult]:
        """Execute recovery plan synchronously."""
        results = []
        
        try:
            self.logger.info(f"Executing recovery plan '{plan.plan_id}' with {len(plan.recovery_actions)} actions")
            
            for action in plan.recovery_actions:
                result = self._execute_recovery_action(plan.plan_id, action)
                results.append(result)
                
                # If action failed and we can't continue, stop execution
                if not result.success and action.risk_level in ["high", "critical"]:
                    self.logger.error(f"Critical recovery action failed, stopping plan execution: {result.error_message}")
                    break
                
                # Brief pause between actions
                time.sleep(0.5)
            
            # Validate recovery success
            success = self._validate_recovery_success(plan, results)
            
            if success:
                self.logger.info(f"Recovery plan '{plan.plan_id}' completed successfully")
                self._recovery_stats["successful_recoveries"] += 1
            else:
                self.logger.error(f"Recovery plan '{plan.plan_id}' failed validation")
                self._recovery_stats["failed_recoveries"] += 1
                
                # Execute rollback if needed
                if plan.rollback_plan:
                    self._execute_rollback_plan(plan, results)
            
        except Exception as e:
            self.logger.error(f"Error executing recovery plan '{plan.plan_id}': {e}")
            self.logger.error(traceback.format_exc())
            
            # Create error result
            error_result = RecoveryResult(
                plan_id=plan.plan_id,
                action_id="plan_execution",
                status=RecoveryStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                success=False,
                error_message=str(e)
            )
            results.append(error_result)
            
            self._recovery_stats["failed_recoveries"] += 1
        
        finally:
            # Clean up
            with self._recovery_lock:
                self._active_recoveries.pop(plan.plan_id, None)
                self._active_futures.pop(plan.plan_id, None)
            
            # Update stats
            self._recovery_stats["total_recoveries"] += 1
            self._update_recovery_stats(results)
            
            # Store results in history
            self._recovery_history.extend(results)
            if len(self._recovery_history) > 1000:
                self._recovery_history = self._recovery_history[-1000:]
        
        return results
    
    def _execute_recovery_action(self, plan_id: str, action: RecoveryAction) -> RecoveryResult:
        """Execute a single recovery action."""
        start_time = datetime.now()
        
        self.logger.info(f"Executing recovery action '{action.action_id}': {action.description}")
        
        result = RecoveryResult(
            plan_id=plan_id,
            action_id=action.action_id,
            status=RecoveryStatus.IN_PROGRESS,
            start_time=start_time
        )
        
        try:
            # Execute the action based on its type
            success = self._perform_recovery_action(action)
            
            result.end_time = datetime.now()
            result.success = success
            result.status = RecoveryStatus.COMPLETED if success else RecoveryStatus.FAILED
            
            if success:
                self.logger.info(f"Recovery action '{action.action_id}' completed successfully")
            else:
                result.error_message = f"Recovery action '{action.action_type.value}' failed"
                self.logger.error(f"Recovery action '{action.action_id}' failed")
            
        except Exception as e:
            result.end_time = datetime.now()
            result.success = False
            result.status = RecoveryStatus.FAILED
            result.error_message = str(e)
            
            self.logger.error(f"Error executing recovery action '{action.action_id}': {e}")
        
        # Notify callbacks
        for callback in self._recovery_callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Error in recovery callback: {e}")
        
        return result
    
    def _perform_recovery_action(self, action: RecoveryAction) -> bool:
        """Perform the actual recovery action."""
        # This is where the actual recovery logic would be implemented
        # For now, we simulate the actions
        
        if action.action_type == RecoveryActionType.RESTART_COMPONENT:
            # Simulate component restart
            self.logger.info(f"Restarting component '{action.component_name}'")
            time.sleep(action.estimated_duration_seconds)
            return True
        
        elif action.action_type == RecoveryActionType.CLEAR_CACHE:
            # Simulate cache clearing
            self.logger.info(f"Clearing cache for component '{action.component_name}'")
            time.sleep(action.estimated_duration_seconds)
            return True
        
        elif action.action_type == RecoveryActionType.RESET_CONFIGURATION:
            # Simulate configuration reset
            self.logger.info(f"Resetting configuration for component '{action.component_name}'")
            time.sleep(action.estimated_duration_seconds)
            return True
        
        elif action.action_type == RecoveryActionType.VALIDATE_INTEGRITY:
            # Simulate integrity validation
            self.logger.info(f"Validating integrity for component '{action.component_name}'")
            time.sleep(action.estimated_duration_seconds)
            return True
        
        elif action.action_type == RecoveryActionType.ESCALATE_TO_ADMIN:
            # Simulate admin escalation
            self.logger.critical(f"ESCALATING TO ADMIN: Recovery needed for '{action.component_name}'")
            return True
        
        else:
            # Default simulation
            self.logger.info(f"Performing {action.action_type.value} for '{action.component_name}'")
            time.sleep(action.estimated_duration_seconds)
            return True
    
    def _validate_recovery_success(self, plan: RecoveryPlan, results: List[RecoveryResult]) -> bool:
        """Validate that recovery was successful."""
        # Check if all actions succeeded
        all_actions_succeeded = all(result.success for result in results)
        
        if not all_actions_succeeded:
            return False
        
        # Check success criteria (simplified validation)
        for criterion in plan.success_criteria:
            self.logger.debug(f"Checking success criterion: {criterion}")
            # In a real implementation, this would perform actual validation
            # For now, we assume success if all actions completed
        
        return True
    
    def _execute_rollback_plan(self, plan: RecoveryPlan, failed_results: List[RecoveryResult]) -> None:
        """Execute rollback plan after recovery failure."""
        if not plan.rollback_plan:
            return
        
        self.logger.warning(f"Executing rollback plan for '{plan.plan_id}'")
        
        for action in plan.rollback_plan:
            try:
                result = self._execute_recovery_action(plan.plan_id, action)
                result.rollback_performed = True
                failed_results.append(result)
                
                if not result.success:
                    self.logger.error(f"Rollback action failed: {action.action_id}")
                
            except Exception as e:
                self.logger.error(f"Error during rollback action '{action.action_id}': {e}")
    
    def _update_recovery_stats(self, results: List[RecoveryResult]) -> None:
        """Update recovery performance statistics."""
        if not results:
            return
        
        # Calculate average recovery time
        total_time = 0.0
        completed_actions = 0
        
        for result in results:
            if result.end_time and result.start_time:
                duration = (result.end_time - result.start_time).total_seconds()
                total_time += duration
                completed_actions += 1
        
        if completed_actions > 0:
            avg_time = total_time / completed_actions
            
            # Update running average
            current_avg = self._recovery_stats["average_recovery_time"]
            total_recoveries = self._recovery_stats["total_recoveries"]
            
            if total_recoveries > 0:
                self._recovery_stats["average_recovery_time"] = (
                    (current_avg * (total_recoveries - 1) + avg_time) / total_recoveries
                )
            else:
                self._recovery_stats["average_recovery_time"] = avg_time
    
    # Public API methods
    
    def get_active_recoveries(self) -> Dict[str, RecoveryPlan]:
        """Get all currently active recovery plans."""
        with self._recovery_lock:
            return self._active_recoveries.copy()
    
    def get_recovery_history(self, limit: Optional[int] = None) -> List[RecoveryResult]:
        """Get recovery history."""
        if limit:
            return self._recovery_history[-limit:]
        return self._recovery_history.copy()
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery performance statistics."""
        return self._recovery_stats.copy()
    
    def cancel_recovery(self, plan_id: str) -> bool:
        """Cancel an active recovery plan."""
        with self._recovery_lock:
            if plan_id not in self._active_recoveries:
                return False
            
            # Cancel the future if it's still running
            future = self._active_futures.get(plan_id)
            if future and not future.done():
                future.cancel()
                
                # Create cancellation result
                cancel_result = RecoveryResult(
                    plan_id=plan_id,
                    action_id="plan_cancellation",
                    status=RecoveryStatus.CANCELLED,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    success=False,
                    error_message="Recovery plan cancelled by user"
                )
                
                self._recovery_history.append(cancel_result)
                
                # Clean up
                self._active_recoveries.pop(plan_id, None)
                self._active_futures.pop(plan_id, None)
                
                self.logger.info(f"Cancelled recovery plan '{plan_id}'")
                return True
        
        return False
    
    def is_component_recovering(self, component_name: str) -> bool:
        """Check if a component is currently undergoing recovery."""
        with self._recovery_lock:
            for plan in self._active_recoveries.values():
                if component_name in plan.failed_components:
                    return True
        return False
    
    def get_component_recovery_history(self, component_name: str, 
                                     limit: Optional[int] = None) -> List[RecoveryResult]:
        """Get recovery history for a specific component."""
        component_results = [
            result for result in self._recovery_history
            if any(component_name in plan.failed_components 
                  for plan in self._active_recoveries.values() 
                  if plan.plan_id == result.plan_id)
        ]
        
        if limit:
            return component_results[-limit:]
        return component_results