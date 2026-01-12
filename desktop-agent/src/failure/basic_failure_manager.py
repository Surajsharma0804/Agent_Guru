"""
Basic Failure Manager

A simplified but functional failure management system for GURU that provides
essential failure detection, monitoring, and safe degradation capabilities.

This implementation focuses on core functionality while avoiding complex
circular dependencies.
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Set, Callable, Any, Protocol
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import weakref


class BasicHealthStatus(Enum):
    """Basic component health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class BasicFailureType(Enum):
    """Basic types of component failures."""
    COMPONENT_UNRESPONSIVE = "component_unresponsive"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SECURITY_VIOLATION = "security_violation"
    CONFIGURATION_ERROR = "configuration_error"


class BasicFailureSeverity(Enum):
    """Basic severity levels for component failures."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BasicComponentFailure:
    """Basic record of a component failure."""
    component_name: str
    failure_type: BasicFailureType
    severity: BasicFailureSeverity
    timestamp: datetime
    error_message: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def is_critical(self) -> bool:
        """Check if this failure is critical."""
        return self.severity == BasicFailureSeverity.CRITICAL


@dataclass
class BasicComponentHealth:
    """Basic health information for a component."""
    component_name: str
    status: BasicHealthStatus
    last_check_time: datetime
    error_count: int = 0
    consecutive_failures: int = 0
    health_score: float = 100.0
    issues: List[str] = field(default_factory=list)


class BasicHealthCheckable(Protocol):
    """Protocol for components that can be health checked."""
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status information."""
        ...


class BasicFailureDetectable(Protocol):
    """Protocol for components that can be monitored for failures."""
    
    def get_failure_indicators(self) -> Dict[str, Any]:
        """Get current failure indicators for the component."""
        ...


class BasicFailureManager:
    """
    Basic failure management system for GURU components.
    
    Provides essential failure detection, health monitoring, and safe
    degradation capabilities without complex dependencies.
    """
    
    def __init__(self, check_interval_seconds: float = 5.0):
        self.check_interval_seconds = check_interval_seconds
        self.logger = logging.getLogger(__name__)
        
        # Component registry
        self._components: Dict[str, weakref.ReferenceType] = {}
        self._component_health: Dict[str, BasicComponentHealth] = {}
        self._critical_components: Set[str] = set()
        
        # Failure tracking
        self._active_failures: List[BasicComponentFailure] = []
        self._failure_history: List[BasicComponentFailure] = []
        
        # Monitoring control
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_lock = threading.RLock()
        
        # Callbacks
        self._failure_callbacks: List[Callable[[BasicComponentFailure], None]] = []
        self._health_callbacks: List[Callable[[str, BasicComponentHealth], None]] = []
        
        # System state
        self._system_healthy = True
        self._emergency_halt = False
        
    def register_component(self, name: str, component: Any, is_critical: bool = False) -> None:
        """Register a component for failure management."""
        with self._monitor_lock:
            self._components[name] = weakref.ref(component)
            
            if is_critical:
                self._critical_components.add(name)
            
            # Initialize health status
            self._component_health[name] = BasicComponentHealth(
                component_name=name,
                status=BasicHealthStatus.UNKNOWN,
                last_check_time=datetime.now()
            )
        
        self.logger.info(f"Registered component '{name}' for failure management "
                        f"(critical: {is_critical})")
    
    def unregister_component(self, name: str) -> None:
        """Unregister a component from failure management."""
        with self._monitor_lock:
            self._components.pop(name, None)
            self._component_health.pop(name, None)
            self._critical_components.discard(name)
        
        self.logger.info(f"Unregistered component '{name}' from failure management")
    
    def add_failure_callback(self, callback: Callable[[BasicComponentFailure], None]) -> None:
        """Add callback for component failures."""
        self._failure_callbacks.append(callback)
    
    def add_health_callback(self, callback: Callable[[str, BasicComponentHealth], None]) -> None:
        """Add callback for health changes."""
        self._health_callbacks.append(callback)
    
    def start_monitoring(self) -> None:
        """Start failure monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="BasicFailureManager"
        )
        self._monitor_thread.start()
        
        self.logger.info("Started failure monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop failure monitoring."""
        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
        
        self.logger.info("Stopped failure monitoring")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                self._check_all_components()
                time.sleep(self.check_interval_seconds)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval_seconds)
    
    def _check_all_components(self) -> None:
        """Check health and failures for all registered components."""
        with self._monitor_lock:
            components_to_check = list(self._components.items())
        
        for name, component_ref in components_to_check:
            try:
                component = component_ref()
                if component is None:
                    # Component has been garbage collected
                    self.unregister_component(name)
                    continue
                
                self._check_component_health(name, component)
                self._check_component_failures(name, component)
                
            except Exception as e:
                self.logger.error(f"Error checking component '{name}': {e}")
                self._record_component_failure(name, str(e))
    
    def _check_component_health(self, name: str, component: Any) -> None:
        """Check health of a specific component."""
        if not hasattr(component, 'health_check'):
            return
        
        try:
            health_data = component.health_check()
            status = self._determine_health_status(health_data)
            
            # Update component health
            with self._monitor_lock:
                if name in self._component_health:
                    health = self._component_health[name]
                    old_status = health.status
                    
                    health.status = status
                    health.last_check_time = datetime.now()
                    
                    if status == BasicHealthStatus.FAILED:
                        health.error_count += 1
                        health.consecutive_failures += 1
                        health.health_score = max(0, health.health_score - 20)
                    else:
                        health.consecutive_failures = 0
                        if status == BasicHealthStatus.HEALTHY:
                            health.health_score = min(100, health.health_score + 5)
                    
                    # Notify callbacks if status changed
                    if old_status != status:
                        self._notify_health_callbacks(name, health)
        
        except Exception as e:
            self.logger.error(f"Health check failed for component '{name}': {e}")
            self._record_component_failure(name, f"Health check failed: {e}")
    
    def _check_component_failures(self, name: str, component: Any) -> None:
        """Check for failures in a specific component."""
        if not hasattr(component, 'get_failure_indicators'):
            return
        
        try:
            indicators = component.get_failure_indicators()
            
            if indicators.get('failed', False):
                error_message = indicators.get('error_message', 'Component reported failure')
                failure_type = self._determine_failure_type(indicators)
                severity = self._determine_failure_severity(name, indicators)
                
                failure = BasicComponentFailure(
                    component_name=name,
                    failure_type=failure_type,
                    severity=severity,
                    timestamp=datetime.now(),
                    error_message=error_message,
                    context=indicators
                )
                
                self._handle_component_failure(failure)
        
        except Exception as e:
            self.logger.error(f"Failure check failed for component '{name}': {e}")
            self._record_component_failure(name, f"Failure check failed: {e}")
    
    def _determine_health_status(self, health_data: Dict[str, Any]) -> BasicHealthStatus:
        """Determine health status from health data."""
        status_str = health_data.get('status', '').lower()
        
        if status_str in ['failed', 'error', 'critical']:
            return BasicHealthStatus.FAILED
        elif status_str in ['degraded', 'warning']:
            return BasicHealthStatus.DEGRADED
        elif status_str == 'healthy':
            return BasicHealthStatus.HEALTHY
        else:
            return BasicHealthStatus.UNKNOWN
    
    def _determine_failure_type(self, indicators: Dict[str, Any]) -> BasicFailureType:
        """Determine failure type from indicators."""
        failure_type_str = indicators.get('failure_type', '').lower()
        
        if 'security' in failure_type_str:
            return BasicFailureType.SECURITY_VIOLATION
        elif 'resource' in failure_type_str:
            return BasicFailureType.RESOURCE_EXHAUSTION
        elif 'config' in failure_type_str:
            return BasicFailureType.CONFIGURATION_ERROR
        else:
            return BasicFailureType.COMPONENT_UNRESPONSIVE
    
    def _determine_failure_severity(self, name: str, indicators: Dict[str, Any]) -> BasicFailureSeverity:
        """Determine failure severity."""
        if name in self._critical_components:
            return BasicFailureSeverity.CRITICAL
        
        if indicators.get('security_violation', False):
            return BasicFailureSeverity.CRITICAL
        
        severity_str = indicators.get('severity', '').lower()
        if severity_str == 'critical':
            return BasicFailureSeverity.CRITICAL
        elif severity_str == 'high':
            return BasicFailureSeverity.HIGH
        elif severity_str == 'medium':
            return BasicFailureSeverity.MEDIUM
        else:
            return BasicFailureSeverity.LOW
    
    def _record_component_failure(self, name: str, error_message: str) -> None:
        """Record a component failure."""
        failure = BasicComponentFailure(
            component_name=name,
            failure_type=BasicFailureType.COMPONENT_UNRESPONSIVE,
            severity=BasicFailureSeverity.CRITICAL if name in self._critical_components else BasicFailureSeverity.HIGH,
            timestamp=datetime.now(),
            error_message=error_message
        )
        
        self._handle_component_failure(failure)
    
    def _handle_component_failure(self, failure: BasicComponentFailure) -> None:
        """Handle a component failure."""
        with self._monitor_lock:
            self._active_failures.append(failure)
            self._failure_history.append(failure)
            
            # Keep history manageable
            if len(self._failure_history) > 1000:
                self._failure_history = self._failure_history[-1000:]
        
        self.logger.error(f"Component failure: {failure.component_name} - "
                         f"{failure.failure_type.value} ({failure.severity.value}): "
                         f"{failure.error_message}")
        
        # Handle critical failures
        if failure.is_critical():
            self._handle_critical_failure(failure)
        
        # Update system state
        self._update_system_state()
        
        # Notify callbacks
        self._notify_failure_callbacks(failure)
    
    def _handle_critical_failure(self, failure: BasicComponentFailure) -> None:
        """Handle critical failures."""
        self.logger.critical(f"CRITICAL FAILURE: {failure.component_name} - {failure.error_message}")
        
        # If it's a security violation or critical component, trigger emergency halt
        if (failure.failure_type == BasicFailureType.SECURITY_VIOLATION or
            failure.component_name in self._critical_components):
            self._trigger_emergency_halt(failure)
    
    def _trigger_emergency_halt(self, failure: BasicComponentFailure) -> None:
        """Trigger emergency system halt."""
        self.logger.critical(f"EMERGENCY HALT TRIGGERED: {failure.error_message}")
        
        with self._monitor_lock:
            self._emergency_halt = True
            self._system_healthy = False
    
    def _update_system_state(self) -> None:
        """Update overall system state."""
        with self._monitor_lock:
            if self._emergency_halt:
                self._system_healthy = False
                return
            
            # Check if we have any critical failures
            critical_failures = [f for f in self._active_failures if f.is_critical()]
            
            if critical_failures:
                self._system_healthy = False
            else:
                # Check if we have too many failures
                if len(self._active_failures) >= 3:
                    self._system_healthy = False
                else:
                    self._system_healthy = True
    
    def _notify_failure_callbacks(self, failure: BasicComponentFailure) -> None:
        """Notify failure callbacks."""
        for callback in self._failure_callbacks:
            try:
                callback(failure)
            except Exception as e:
                self.logger.error(f"Error in failure callback: {e}")
    
    def _notify_health_callbacks(self, name: str, health: BasicComponentHealth) -> None:
        """Notify health callbacks."""
        for callback in self._health_callbacks:
            try:
                callback(name, health)
            except Exception as e:
                self.logger.error(f"Error in health callback: {e}")
    
    # Public API methods
    
    def get_component_health(self, name: str) -> Optional[BasicComponentHealth]:
        """Get health status of a component."""
        with self._monitor_lock:
            return self._component_health.get(name)
    
    def get_all_health_status(self) -> Dict[str, BasicComponentHealth]:
        """Get health status of all components."""
        with self._monitor_lock:
            return self._component_health.copy()
    
    def get_active_failures(self) -> List[BasicComponentFailure]:
        """Get all active failures."""
        with self._monitor_lock:
            return self._active_failures.copy()
    
    def get_failure_history(self, limit: Optional[int] = None) -> List[BasicComponentFailure]:
        """Get failure history."""
        with self._monitor_lock:
            if limit:
                return self._failure_history[-limit:]
            return self._failure_history.copy()
    
    def is_system_healthy(self) -> bool:
        """Check if system is healthy."""
        with self._monitor_lock:
            return self._system_healthy and not self._emergency_halt
    
    def is_emergency_halt(self) -> bool:
        """Check if system is in emergency halt."""
        with self._monitor_lock:
            return self._emergency_halt
    
    def force_emergency_halt(self, reason: str) -> None:
        """Force emergency system halt."""
        failure = BasicComponentFailure(
            component_name="system",
            failure_type=BasicFailureType.SECURITY_VIOLATION,
            severity=BasicFailureSeverity.CRITICAL,
            timestamp=datetime.now(),
            error_message=f"Manual emergency halt: {reason}"
        )
        
        self._trigger_emergency_halt(failure)
    
    def clear_component_failures(self, component_name: str) -> None:
        """Clear failures for a specific component."""
        with self._monitor_lock:
            self._active_failures = [
                f for f in self._active_failures 
                if f.component_name != component_name
            ]
        
        self._update_system_state()
        self.logger.info(f"Cleared failures for component '{component_name}'")
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get system health summary."""
        with self._monitor_lock:
            healthy_components = sum(
                1 for health in self._component_health.values()
                if health.status == BasicHealthStatus.HEALTHY
            )
            
            failed_components = sum(
                1 for health in self._component_health.values()
                if health.status == BasicHealthStatus.FAILED
            )
            
            return {
                "system_healthy": self._system_healthy,
                "emergency_halt": self._emergency_halt,
                "total_components": len(self._component_health),
                "healthy_components": healthy_components,
                "failed_components": failed_components,
                "active_failures": len(self._active_failures),
                "critical_failures": len([f for f in self._active_failures if f.is_critical()]),
                "total_failure_history": len(self._failure_history)
            }