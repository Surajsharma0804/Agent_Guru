"""
PRODUCTION-GRADE SECURITY-FIRST FAILURE DETECTOR

This is the corrected implementation of the failure detection system that ensures
security and integrity violations are detected with absolute priority over all
other failure types. This implementation addresses the critical security bug
where security violations were being misclassified as component unresponsive.

CRITICAL FIX: Security and integrity violations are now checked FIRST, before
any other failure indicators, ensuring fail-safe behavior.
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Set, Callable, Any, Protocol
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import weakref
from concurrent.futures import ThreadPoolExecutor, Future
import queue

from .exceptions import (
    ComponentFailureError,
    CriticalSystemFailureError,
    CascadeFailureError,
    SecurityViolationError,
    IntegrityViolationError
)
from .health_monitor import ComponentHealthMonitor, ComponentHealth, HealthStatus
from .failure_detector import (
    FailureType,
    FailureSeverity,
    ComponentFailure,
    FailureDetectionConfig,
    FailureDetectable
)


class SecurityFirstFailureDetector:
    """
    PRODUCTION-GRADE SECURITY-FIRST FAILURE DETECTOR
    
    This implementation ensures that security and integrity violations are
    detected with absolute priority, implementing true fail-safe behavior
    where security violations can never be masked by other failure types.
    
    SECURITY PRINCIPLES:
    1. Security violations checked FIRST, always
    2. Integrity violations checked SECOND, always  
    3. No other failure type can mask security issues
    4. Immediate critical classification for security violations
    5. Comprehensive audit logging of all security events
    """
    
    def __init__(self, config: Optional[FailureDetectionConfig] = None,
                 health_monitor: Optional[ComponentHealthMonitor] = None):
        self.config = config or FailureDetectionConfig()
        self.health_monitor = health_monitor or ComponentHealthMonitor()
        self.logger = logging.getLogger(__name__)
        
        # Component registry
        self._components: Dict[str, weakref.ReferenceType] = {}
        self._critical_components: Set[str] = set()
        self._component_dependencies: Dict[str, Set[str]] = {}
        
        # Failure tracking
        self._active_failures: Dict[str, ComponentFailure] = {}
        self._failure_history: List[ComponentFailure] = []
        self._consecutive_failures: Dict[str, int] = {}
        self._last_failure_time: Dict[str, datetime] = {}
        
        # Detection control
        self._detecting = False
        self._detection_thread: Optional[threading.Thread] = None
        self._detection_lock = threading.RLock()
        self._detection_executor = ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_detections,
            thread_name_prefix="SecurityFirstFailureDetector"
        )
        
        # Callbacks
        self._failure_callbacks: List[Callable[[ComponentFailure], None]] = []
        self._critical_failure_callbacks: List[Callable[[ComponentFailure], None]] = []
        self._security_violation_callbacks: List[Callable[[ComponentFailure], None]] = []
        
        # Security event tracking
        self._security_violations: List[ComponentFailure] = []
        self._integrity_violations: List[ComponentFailure] = []
        
        self.logger.info("SecurityFirstFailureDetector initialized with production-grade security-first monitoring")
    
    def analyze_failure_indicators_security_first(self, name: str, indicators: Dict[str, Any],
                                                 component: FailureDetectable) -> Optional[ComponentFailure]:
        """
        SECURITY-FIRST FAILURE ANALYSIS
        
        This method implements the corrected logic where security and integrity
        violations are checked with absolute priority before any other failure types.
        
        CRITICAL SECURITY FLOW:
        1. Security violations - HIGHEST PRIORITY
        2. Integrity violations - SECOND HIGHEST PRIORITY  
        3. All other failure types - LOWER PRIORITY
        
        This ensures that security violations can NEVER be masked by other failures.
        """
        self.logger.debug(f"SECURITY-FIRST analysis for {name}: {indicators}")
        
        # PRIORITY 1: SECURITY VIOLATIONS (ABSOLUTE HIGHEST PRIORITY)
        if indicators.get('security_violation', False):
            self.logger.critical(f"SECURITY VIOLATION DETECTED in {name}")
            
            security_failure = ComponentFailure(
                component_name=name,
                failure_type=FailureType.SECURITY_VIOLATION,
                severity=FailureSeverity.CRITICAL,
                timestamp=datetime.now(),
                error_message=indicators.get('security_message', 'Security violation detected'),
                context=indicators
            )
            
            # Track security violations separately
            self._security_violations.append(security_failure)
            
            # Notify security violation callbacks
            for callback in self._security_violation_callbacks:
                try:
                    callback(security_failure)
                except Exception as e:
                    self.logger.error(f"Error in security violation callback: {e}")
            
            return security_failure
        
        # PRIORITY 2: INTEGRITY VIOLATIONS (SECOND HIGHEST PRIORITY)
        if indicators.get('integrity_violation', False):
            self.logger.critical(f"INTEGRITY VIOLATION DETECTED in {name}")
            
            integrity_failure = ComponentFailure(
                component_name=name,
                failure_type=FailureType.INTEGRITY_VIOLATION,
                severity=FailureSeverity.CRITICAL,
                timestamp=datetime.now(),
                error_message=indicators.get('integrity_message', 'Data integrity violation detected'),
                context=indicators
            )
            
            # Track integrity violations separately
            self._integrity_violations.append(integrity_failure)
            
            return integrity_failure
        
        # PRIORITY 3: RESOURCE EXHAUSTION (HIGH PRIORITY)
        cpu_usage = indicators.get('cpu_usage_percent', 0)
        memory_usage = indicators.get('memory_usage_mb', 0)
        if cpu_usage > 95 or memory_usage > 2000:
            return ComponentFailure(
                component_name=name,
                failure_type=FailureType.RESOURCE_EXHAUSTION,
                severity=FailureSeverity.HIGH,
                timestamp=datetime.now(),
                error_message=f"Resource exhaustion: CPU {cpu_usage}%, Memory {memory_usage}MB",
                context=indicators
            )
        
        # PRIORITY 4: GENERAL FAILURE INDICATORS (LOWER PRIORITY)
        if indicators.get('failed', False):
            self.logger.debug(f"General failure detected in {name}")
            error_message = indicators.get('error_message', 'Component reported failure')
            failure_type = self._determine_failure_type(indicators)
            severity = self._determine_failure_severity(name, failure_type, component)
            
            return ComponentFailure(
                component_name=name,
                failure_type=failure_type,
                severity=severity,
                timestamp=datetime.now(),
                error_message=error_message,
                context=indicators,
                stack_trace=indicators.get('stack_trace')
            )
        
        return None
    
    def _determine_failure_type(self, indicators: Dict[str, Any]) -> FailureType:
        """Determine the type of failure from indicators."""
        failure_type_str = indicators.get('failure_type', '').lower()
        
        # Security and integrity violations should never reach this method
        # due to the security-first analysis, but double-check for safety
        if 'security' in failure_type_str:
            self.logger.warning("Security violation reached _determine_failure_type - this should not happen")
            return FailureType.SECURITY_VIOLATION
        
        if 'integrity' in failure_type_str:
            self.logger.warning("Integrity violation reached _determine_failure_type - this should not happen")
            return FailureType.INTEGRITY_VIOLATION
        
        type_mapping = {
            'timeout': FailureType.HEALTH_CHECK_TIMEOUT,
            'unresponsive': FailureType.COMPONENT_UNRESPONSIVE,
            'resource': FailureType.RESOURCE_EXHAUSTION,
            'dependency': FailureType.DEPENDENCY_FAILURE,
            'cascade': FailureType.CASCADE_FAILURE,
            'recovery': FailureType.RECOVERY_FAILURE,
            'config': FailureType.CONFIGURATION_ERROR,
            'external': FailureType.EXTERNAL_DEPENDENCY_FAILURE
        }
        
        for key, failure_type in type_mapping.items():
            if key in failure_type_str:
                return failure_type
        
        return FailureType.COMPONENT_UNRESPONSIVE
    
    def _determine_failure_severity(self, name: str, failure_type: FailureType,
                                  component: FailureDetectable) -> FailureSeverity:
        """Determine the severity of a failure."""
        # Security and integrity violations are always critical/fatal
        if failure_type in [FailureType.SECURITY_VIOLATION, FailureType.INTEGRITY_VIOLATION]:
            if name in self._critical_components or component.is_critical_component():
                return FailureSeverity.FATAL
            else:
                return FailureSeverity.CRITICAL
        
        # Critical components get higher severity
        if name in self._critical_components or component.is_critical_component():
            return FailureSeverity.CRITICAL
        
        # Default severity mapping
        severity_mapping = {
            FailureType.HEALTH_CHECK_TIMEOUT: FailureSeverity.MEDIUM,
            FailureType.COMPONENT_UNRESPONSIVE: FailureSeverity.HIGH,
            FailureType.RESOURCE_EXHAUSTION: FailureSeverity.HIGH,
            FailureType.DEPENDENCY_FAILURE: FailureSeverity.MEDIUM,
            FailureType.CASCADE_FAILURE: FailureSeverity.HIGH,
            FailureType.RECOVERY_FAILURE: FailureSeverity.HIGH,
            FailureType.CONFIGURATION_ERROR: FailureSeverity.LOW,
            FailureType.EXTERNAL_DEPENDENCY_FAILURE: FailureSeverity.MEDIUM
        }
        
        return severity_mapping.get(failure_type, FailureSeverity.MEDIUM)
    
    def add_security_violation_callback(self, callback: Callable[[ComponentFailure], None]) -> None:
        """Add callback specifically for security violations."""
        self._security_violation_callbacks.append(callback)
    
    def get_security_violations(self) -> List[ComponentFailure]:
        """Get all detected security violations."""
        return self._security_violations.copy()
    
    def get_integrity_violations(self) -> List[ComponentFailure]:
        """Get all detected integrity violations."""
        return self._integrity_violations.copy()
    
    def register_component(self, name: str, component: FailureDetectable,
                          is_critical: bool = False,
                          dependencies: Optional[Set[str]] = None) -> None:
        """Register a component for failure detection."""
        with self._detection_lock:
            self._components[name] = weakref.ref(component)
            self._consecutive_failures[name] = 0
            
            if is_critical:
                self._critical_components.add(name)
            
            if dependencies:
                self._component_dependencies[name] = dependencies
        
        self.logger.info(f"Registered component '{name}' for security-first failure detection "
                        f"(critical: {is_critical}, dependencies: {dependencies or 'none'})")