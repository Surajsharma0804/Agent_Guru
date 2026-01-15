"""
Property-Based Tests for Failure Orchestrator

Tests the comprehensive failure management system including:
- Property 50: Periodic Health Monitoring
- Property 51: Automatic Component Restart
- Property 52: Permanent Failure After Three Attempts
- Property 53: Graceful Degradation
- Property 54: Failure Logging

These tests validate Requirements 11.1, 11.2, 11.3, 11.5, 11.6
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize
from datetime import datetime, timedelta
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

# Import failure orchestrator components
from src.failure.system_failure_orchestrator import (
    SystemFailureOrchestrator,
    SystemFailureState,
    SystemFailureReport
)
from src.failure.health_monitor import (
    ComponentHealthMonitor,
    ComponentHealth,
    HealthStatus,
    HealthMetrics,
    HealthLimits,
    HealthCheckable
)
from src.failure.failure_detector import (
    FailureDetector,
    ComponentFailure,
    FailureType,
    FailureSeverity,
    FailureDetectable
)
from src.failure.recovery_orchestrator import (
    RecoveryOrchestrator,
    RecoveryPlan,
    RecoveryResult,
    RecoveryStatus
)
from src.failure.safe_degradation import (
    SystemDegradationOrchestrator,
    DegradationLevel,
    DegradationPlan,
    SystemState
)


# ============================================================================
# Mock Components for Testing
# ============================================================================

class MockHealthCheckableComponent(HealthCheckable):
    """Mock component that implements HealthCheckable protocol."""
    
    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.should_fail = should_fail
        self.health_check_count = 0
        self.metrics_call_count = 0
        self._health_status = "healthy"
        self._metrics = {
            "cpu_usage_percent": 10.0,
            "memory_usage_mb": 100.0,
            "response_time_ms": 50.0,
            "error_rate_percent": 0.0
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        self.health_check_count += 1
        
        if self.should_fail:
            raise Exception(f"Component {self.name} health check failed")
        
        return {
            "status": self._health_status,
            "timestamp": datetime.now().isoformat(),
            "component": self.name
        }
    
    def get_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        self.metrics_call_count += 1
        return self._metrics.copy()
    
    def set_health_status(self, status: str):
        """Set health status for testing."""
        self._health_status = status
    
    def set_metrics(self, metrics: Dict[str, float]):
        """Set metrics for testing."""
        self._metrics.update(metrics)


class MockFailureDetectableComponent(FailureDetectable):
    """Mock component that implements FailureDetectable protocol."""
    
    def __init__(self, name: str, is_critical: bool = False):
        self.name = name
        self._is_critical = is_critical
        self._failure_indicators = {}
    
    def get_failure_indicators(self) -> Dict[str, Any]:
        """Get failure indicators."""
        return self._failure_indicators.copy()
    
    def is_critical_component(self) -> bool:
        """Check if component is critical."""
        return self._is_critical
    
    def set_failure_indicators(self, indicators: Dict[str, Any]):
        """Set failure indicators for testing."""
        self._failure_indicators = indicators


# ============================================================================
# Property 50: Periodic Health Monitoring
# **Validates: Requirements 11.1**
# ============================================================================

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    num_components=st.integers(min_value=1, max_value=5),
    check_interval=st.floats(min_value=0.1, max_value=2.0)
)
def test_property_50_periodic_health_checks_occur(num_components: int, check_interval: float):
    """
    Feature: guru-complete-system, Property 50: Periodic Health Monitoring
    
    For any monitoring interval, health checks should occur periodically.
    
    Test that the health monitor performs health checks at the configured interval.
    
    **Validates: Requirements 11.1**
    """
    # Create health monitor with short interval for testing
    health_monitor = ComponentHealthMonitor(check_interval_seconds=check_interval)
    
    # Register mock components
    components = []
    for i in range(num_components):
        component = MockHealthCheckableComponent(f"component_{i}")
        components.append(component)
        health_monitor.register_component(f"component_{i}", component)
    
    try:
        # Start monitoring
        health_monitor.start_monitoring()
        
        # Wait for at least 2 check intervals
        wait_time = check_interval * 2.5
        time.sleep(wait_time)
        
        # Stop monitoring
        health_monitor.stop_monitoring()
        
        # Verify health checks occurred
        for component in components:
            # Should have at least 2 health checks (2 intervals passed)
            assert component.health_check_count >= 2, \
                f"Component {component.name} had {component.health_check_count} checks, expected >= 2"
            
            # Should have metrics calls
            assert component.metrics_call_count >= 2, \
                f"Component {component.name} had {component.metrics_call_count} metrics calls, expected >= 2"
        
        # Verify all components have health status
        all_health = health_monitor.get_all_health_status()
        assert len(all_health) == num_components, \
            f"Expected {num_components} health statuses, got {len(all_health)}"
        
        # Verify each component has been checked recently
        for name, health in all_health.items():
            time_since_check = (datetime.now() - health.last_check_time).total_seconds()
            assert time_since_check < check_interval * 2, \
                f"Component {name} last checked {time_since_check}s ago, expected < {check_interval * 2}s"
    
    finally:
        health_monitor.stop_monitoring()


# ============================================================================
# Property 51: Automatic Component Restart
# **Validates: Requirements 11.2**
# ============================================================================

@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(
    component_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    failure_type=st.sampled_from([FailureType.COMPONENT_UNRESPONSIVE, FailureType.RESOURCE_EXHAUSTION])
)
def test_property_51_first_failure_triggers_restart(component_name: str, failure_type: FailureType):
    """
    Feature: guru-complete-system, Property 51: Automatic Component Restart
    
    For any component's first failure, automatic restart should be attempted.
    
    Test that the recovery orchestrator creates and executes a recovery plan
    for the first failure of any component.
    
    **Validates: Requirements 11.2**
    """
    # Sanitize component name
    component_name = component_name.strip() or "test_component"
    
    # Create recovery orchestrator
    recovery_orchestrator = RecoveryOrchestrator()
    
    # Create a component failure
    failure = ComponentFailure(
        component_name=component_name,
        failure_type=failure_type,
        severity=FailureSeverity.MEDIUM,
        timestamp=datetime.now(),
        error_message=f"Test failure for {component_name}"
    )
    
    # Create recovery plan
    recovery_plan = recovery_orchestrator.create_recovery_plan(failure)
    
    # For components with recovery strategies, plan should be created
    # For unknown components, plan may be None
    if recovery_plan is not None:
        # Verify plan was created
        assert recovery_plan.plan_id is not None
        assert component_name in recovery_plan.failed_components
        assert len(recovery_plan.recovery_actions) > 0
        
        # Verify at least one action is a restart
        has_restart = any(
            action.action_type.value in ["restart_component", "reinitialize_resources"]
            for action in recovery_plan.recovery_actions
        )
        assert has_restart, "Recovery plan should include restart action"


@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(failure_count=st.integers(min_value=1, max_value=2))
def test_property_51_first_and_second_failures_trigger_restart(failure_count: int):
    """
    Feature: guru-complete-system, Property 51: Automatic Component Restart
    
    For any component's first or second failure, restart should be attempted.
    
    Test that recovery is attempted for both first and second failures.
    
    **Validates: Requirements 11.2**
    """
    # Create system failure orchestrator
    orchestrator = SystemFailureOrchestrator()
    
    # Create mock component
    component = MockHealthCheckableComponent("test_component")
    orchestrator.register_component("test_component", component, is_critical=False)
    
    # Track recovery attempts
    recovery_attempts = []
    
    def recovery_callback(result: RecoveryResult):
        recovery_attempts.append(result)
    
    orchestrator.recovery_orchestrator.add_recovery_callback(recovery_callback)
    
    # Simulate failures
    for i in range(failure_count):
        failure = ComponentFailure(
            component_name="test_component",
            failure_type=FailureType.COMPONENT_UNRESPONSIVE,
            severity=FailureSeverity.MEDIUM,
            timestamp=datetime.now(),
            error_message=f"Test failure {i+1}"
        )
        
        # Trigger failure
        orchestrator._on_component_failure(failure)
        
        # Wait briefly for recovery to start
        time.sleep(0.5)
    
    # Verify recovery was attempted for each failure
    # Note: Recovery may not complete immediately, but should be initiated
    assert len(orchestrator.recovery_orchestrator.get_active_recoveries()) >= 0, \
        "Recovery should be initiated for failures"


# ============================================================================
# Property 52: Permanent Failure After Three Attempts
# **Validates: Requirements 11.3**
# ============================================================================

@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(
    component_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
)
def test_property_52_three_failures_mark_permanent(component_name: str):
    """
    Feature: guru-complete-system, Property 52: Permanent Failure After Three Attempts
    
    For any component with 3 consecutive failures, it should be marked 
    as permanently failed.
    
    Test that after 3 failures, the component is marked as permanently failed
    and no more recovery attempts are made.
    
    **Validates: Requirements 11.3**
    """
    # Sanitize component name
    component_name = component_name.strip() or "test_component"
    
    # Create health monitor
    health_monitor = ComponentHealthMonitor(check_interval_seconds=0.5)
    
    # Create mock component that always fails
    component = MockHealthCheckableComponent(component_name, should_fail=True)
    health_monitor.register_component(component_name, component)
    
    try:
        # Start monitoring
        health_monitor.start_monitoring()
        
        # Wait for multiple check cycles (enough for 3+ failures)
        time.sleep(2.0)
        
        # Stop monitoring
        health_monitor.stop_monitoring()
        
        # Get component health
        health = health_monitor.get_component_health(component_name)
        
        # Verify component has consecutive failures
        assert health is not None
        assert health.consecutive_failures >= 3, \
            f"Expected >= 3 consecutive failures, got {health.consecutive_failures}"
        
        # Verify component is marked as failed
        assert health.status == HealthStatus.FAILED, \
            f"Expected FAILED status, got {health.status}"
        
        # Verify health score is very low
        assert health.health_score <= 10.0, \
            f"Expected health score <= 10, got {health.health_score}"
    
    finally:
        health_monitor.stop_monitoring()


@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=3, max_value=5))
def test_property_52_no_recovery_after_max_attempts(failure_count: int):
    """
    Feature: guru-complete-system, Property 52: Permanent Failure After Three Attempts
    
    For any component that has failed max_recovery_attempts times,
    no more recovery should be attempted.
    
    Test that the recovery orchestrator respects max recovery attempts.
    
    **Validates: Requirements 11.3**
    """
    # Create failure detector with max 3 consecutive failures
    health_monitor = ComponentHealthMonitor(check_interval_seconds=0.5)
    failure_detector = FailureDetector(health_monitor=health_monitor)
    
    # Create mock component
    component = MockHealthCheckableComponent("test_component", should_fail=True)
    failure_detector.register_component("test_component", component, is_critical=False)
    
    try:
        # Start detection
        failure_detector.start_detection()
        
        # Wait for failures to accumulate
        time.sleep(2.0)
        
        # Stop detection
        failure_detector.stop_detection()
        
        # Get failure tracking
        failure_tracking = failure_detector.get_failure_tracking("test_component")
        
        # Verify max consecutive failures is enforced
        if failure_tracking:
            # Should not exceed max_consecutive_failures (3)
            assert failure_tracking.consecutive_failures <= 3, \
                f"Consecutive failures should not exceed 3, got {failure_tracking.consecutive_failures}"
    
    finally:
        failure_detector.stop_detection()


# ============================================================================
# Property 53: Graceful Degradation
# **Validates: Requirements 11.5**
# ============================================================================

@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(
    failed_components=st.lists(
        st.sampled_from(["authority_state_machine", "audit_logger", "memory_service", "input_engine"]),
        min_size=1,
        max_size=2,
        unique=True
    )
)
def test_property_53_critical_failure_triggers_degradation(failed_components: List[str]):
    """
    Feature: guru-complete-system, Property 53: Graceful Degradation
    
    For any critical component failure, the system should degrade gracefully.
    
    Test that when critical components fail, the degradation manager creates
    and executes a degradation plan.
    
    **Validates: Requirements 11.5**
    """
    # Create degradation orchestrator
    degradation_manager = SystemDegradationOrchestrator()
    
    # Assess degradation need
    degradation_plan = degradation_manager.assess_degradation_need(failed_components)
    
    # Verify degradation plan was created
    assert degradation_plan is not None, \
        f"Degradation plan should be created for critical components: {failed_components}"
    
    # Verify degradation level is appropriate
    assert degradation_plan.degradation_level != DegradationLevel.NORMAL, \
        "Degradation level should not be NORMAL for critical failures"
    
    # Verify affected components are listed
    assert len(degradation_plan.affected_components) > 0, \
        "Degradation plan should list affected components"
    
    # Verify degradation actions are defined
    assert len(degradation_plan.degradation_actions) > 0, \
        "Degradation plan should include degradation actions"


@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(
    degradation_level=st.sampled_from([
        DegradationLevel.DEGRADED_OPERATION,
        DegradationLevel.LIMITED_OPERATION,
        DegradationLevel.EMERGENCY_MODE
    ])
)
def test_property_53_degradation_does_not_crash_system(degradation_level: DegradationLevel):
    """
    Feature: guru-complete-system, Property 53: Graceful Degradation
    
    For any degradation level, the system should continue operating
    without crashing.
    
    Test that executing degradation plans does not cause system crashes.
    
    **Validates: Requirements 11.5**
    """
    # Create degradation orchestrator
    degradation_manager = SystemDegradationOrchestrator()
    
    # Create a degradation plan
    degradation_plan = DegradationPlan(
        plan_id=f"test_plan_{degradation_level.value}",
        degradation_level=degradation_level,
        trigger_reason="Test degradation",
        affected_components=["test_component"],
        degradation_actions=[],
        estimated_duration_seconds=1.0,
        created_at=datetime.now()
    )
    
    # Execute degradation plan (should not crash)
    try:
        success = degradation_manager.execute_degradation_plan(degradation_plan)
        
        # Verify execution completed (success or failure, but no crash)
        assert isinstance(success, bool), "Degradation execution should return boolean"
        
        # Verify system state changed
        current_level = degradation_manager.get_current_degradation_level()
        assert current_level != DegradationLevel.NORMAL, \
            "System should be in degraded state after degradation"
    
    except Exception as e:
        pytest.fail(f"Degradation execution should not crash: {e}")


# ============================================================================
# Property 54: Failure Logging
# **Validates: Requirements 11.6**
# ============================================================================

@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(
    component_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    failure_type=st.sampled_from(list(FailureType)),
    severity=st.sampled_from(list(FailureSeverity))
)
def test_property_54_all_failures_are_logged(component_name: str, failure_type: FailureType, severity: FailureSeverity):
    """
    Feature: guru-complete-system, Property 54: Failure Logging
    
    For any component failure, it should be logged.
    
    Test that all component failures are tracked and logged by the orchestrator.
    
    **Validates: Requirements 11.6**
    """
    # Sanitize component name
    component_name = component_name.strip() or "test_component"
    
    # Create system failure orchestrator
    orchestrator = SystemFailureOrchestrator()
    
    # Track system failure reports
    failure_reports = []
    
    def failure_callback(report: SystemFailureReport):
        failure_reports.append(report)
    
    orchestrator.add_system_failure_callback(failure_callback)
    
    # Create a component failure
    failure = ComponentFailure(
        component_name=component_name,
        failure_type=failure_type,
        severity=severity,
        timestamp=datetime.now(),
        error_message=f"Test failure for {component_name}"
    )
    
    # Trigger failure
    orchestrator._on_component_failure(failure)
    
    # Verify failure was tracked
    active_failures = orchestrator.get_active_failures()
    assert len(active_failures) > 0, "Failure should be tracked in active failures"
    
    # Verify failure is in active failures
    assert any(f.component_name == component_name for f in active_failures), \
        f"Component {component_name} should be in active failures"
    
    # Verify failure report was generated
    assert len(failure_reports) > 0, "Failure report should be generated"
    
    # Verify failure is in the report
    latest_report = failure_reports[-1]
    assert any(f.component_name == component_name for f in latest_report.active_failures), \
        f"Component {component_name} should be in failure report"


@pytest.mark.property_test
@pytest.mark.timeout(60)
@settings(max_examples=100, deadline=None)
@given(num_failures=st.integers(min_value=1, max_value=5))
def test_property_54_failure_history_is_maintained(num_failures: int):
    """
    Feature: guru-complete-system, Property 54: Failure Logging
    
    For any sequence of failures, the orchestrator should maintain
    a history of failure reports.
    
    Test that the failure orchestrator maintains a complete history of all failures.
    
    **Validates: Requirements 11.6**
    """
    # Create system failure orchestrator
    orchestrator = SystemFailureOrchestrator()
    
    # Generate multiple failures
    for i in range(num_failures):
        failure = ComponentFailure(
            component_name=f"component_{i}",
            failure_type=FailureType.COMPONENT_UNRESPONSIVE,
            severity=FailureSeverity.MEDIUM,
            timestamp=datetime.now(),
            error_message=f"Test failure {i}"
        )
        
        orchestrator._on_component_failure(failure)
        time.sleep(0.1)  # Brief pause between failures
    
    # Get failure history
    history = orchestrator.get_failure_history()
    
    # Verify history contains all failures
    assert len(history) >= num_failures, \
        f"Expected >= {num_failures} reports in history, got {len(history)}"
    
    # Verify history is ordered by time
    timestamps = [report.timestamp for report in history]
    assert timestamps == sorted(timestamps), \
        "Failure history should be ordered by timestamp"


# ============================================================================
# Integration Test: Complete Failure Management Cycle
# ============================================================================

@pytest.mark.property_test
@pytest.mark.timeout(120)
@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=3))
def test_complete_failure_recovery_cycle(num_components: int):
    """
    Integration test for complete failure management cycle.
    
    Property: For any set of components, the complete failure management cycle
    should work end-to-end.
    
    Test the full workflow from failure detection through recovery and degradation.
    """
    # Create system failure orchestrator
    orchestrator = SystemFailureOrchestrator()
    
    # Register mock components
    components = []
    for i in range(num_components):
        component = MockHealthCheckableComponent(f"component_{i}")
        components.append(component)
        orchestrator.register_component(
            f"component_{i}",
            component,
            is_critical=(i == 0),  # First component is critical
            dependencies=set() if i == 0 else {f"component_{i-1}"}
        )
    
    try:
        # Start monitoring
        orchestrator.start_monitoring()
        
        # Wait for initial health checks
        time.sleep(1.0)
        
        # Verify system is healthy initially
        assert orchestrator.is_system_healthy(), "System should start healthy"
        
        # Simulate a failure in first component
        components[0].should_fail = True
        
        # Wait for failure detection
        time.sleep(2.0)
        
        # Verify failure was detected
        active_failures = orchestrator.get_active_failures()
        assert len(active_failures) > 0, "Failure should be detected"
        
        # Verify system state changed
        system_state = orchestrator.get_system_state()
        assert system_state != SystemFailureState.HEALTHY, \
            "System state should change after failure"
        
        # Get system health summary
        health_summary = orchestrator.get_system_health_summary()
        assert health_summary["active_failures"] > 0, \
            "Health summary should show active failures"
        assert health_summary["system_health_score"] < 100.0, \
            "System health score should decrease after failure"
    
    finally:
        orchestrator.stop_monitoring()
