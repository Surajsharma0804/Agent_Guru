"""
Component Registry and Discovery System

Production-grade component registry for GURU Personal Assistant providing:
- Centralized component discovery and registration
- Component lifecycle management
- Health monitoring integration
- Dependency tracking and resolution
- Service capability advertisement
- Security boundary enforcement
"""

import logging
import threading
import time
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

from .exceptions import ComponentLifecycleError, ComponentNotFoundError, RegistrationError


class ComponentStatus(Enum):
    """Component lifecycle status."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Component type classification."""
    CORE_SERVICE = "core_service"          # Essential system components
    SECURITY_SERVICE = "security_service"  # Security-related components
    INPUT_SERVICE = "input_service"        # Input handling components
    COMMUNICATION = "communication"        # Communication components
    STORAGE = "storage"                    # Data storage components
    MONITORING = "monitoring"              # Health and monitoring
    SKILL = "skill"                        # Skill execution components
    ADAPTER = "adapter"                    # External service adapters
    UTILITY = "utility"                    # Utility components


@dataclass
class ComponentCapability:
    """Component capability description."""
    name: str
    version: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    security_level: str = "standard"  # standard, elevated, critical
    dependencies: Set[str] = field(default_factory=set)


@dataclass
class ComponentInfo:
    """Comprehensive component information."""
    name: str
    component_type: ComponentType
    version: str
    description: str
    status: ComponentStatus = ComponentStatus.INITIALIZING
    capabilities: List[ComponentCapability] = field(default_factory=list)
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Lifecycle tracking
    registered_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    startup_time: Optional[datetime] = None
    shutdown_time: Optional[datetime] = None
    
    # Health and performance
    health_score: float = 100.0
    error_count: int = 0
    restart_count: int = 0
    
    # Security
    security_level: str = "standard"
    trusted: bool = False
    isolation_required: bool = False
    
    def is_healthy(self) -> bool:
        """Check if component is in healthy state."""
        return self.status in [ComponentStatus.READY, ComponentStatus.RUNNING]
    
    def is_available(self) -> bool:
        """Check if component is available for requests."""
        return self.status in [ComponentStatus.READY, ComponentStatus.RUNNING, ComponentStatus.DEGRADED]
    
    def time_since_heartbeat(self) -> timedelta:
        """Get time since last heartbeat."""
        return datetime.now() - self.last_heartbeat
    
    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        self.last_heartbeat = datetime.now()


class ComponentLifecycle(Protocol):
    """Protocol for components with lifecycle management."""
    
    def initialize(self) -> bool:
        """Initialize component."""
        ...
    
    def start(self) -> bool:
        """Start component."""
        ...
    
    def stop(self) -> bool:
        """Stop component."""
        ...
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        ...


class ComponentRegistry:
    """
    Production-grade component registry and discovery system.
    
    Provides centralized management of all GURU components with:
    - Component registration and discovery
    - Lifecycle management and monitoring
    - Dependency tracking and resolution
    - Health monitoring integration
    - Security boundary enforcement
    - Service capability advertisement
    """
    
    def __init__(self, 
                 heartbeat_timeout_seconds: float = 60.0,
                 enable_dependency_checking: bool = True,
                 enable_health_monitoring: bool = True):
        """
        Initialize component registry.
        
        Args:
            heartbeat_timeout_seconds: Timeout for component heartbeats
            enable_dependency_checking: Enable dependency validation
            enable_health_monitoring: Enable health monitoring integration
        """
        self.logger = logging.getLogger(__name__)
        self.heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self.enable_dependency_checking = enable_dependency_checking
        self.enable_health_monitoring = enable_health_monitoring
        
        # Component storage
        self._components: Dict[str, ComponentInfo] = {}
        self._component_refs: Dict[str, weakref.ReferenceType] = {}
        self._component_handlers: Dict[str, ComponentLifecycle] = {}
        
        # Capability and service discovery
        self._capabilities: Dict[str, List[str]] = {}  # capability -> [component_names]
        self._service_endpoints: Dict[str, Dict[str, Any]] = {}
        
        # Dependency management
        self._dependency_graph: Dict[str, Set[str]] = {}
        self._reverse_dependencies: Dict[str, Set[str]] = {}
        
        # Event handling
        self._lifecycle_callbacks: List[Callable[[str, ComponentStatus, ComponentStatus], None]] = []
        self._registration_callbacks: List[Callable[[ComponentInfo], None]] = []
        self._health_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Monitoring and maintenance
        self._registry_lock = threading.RLock()
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Statistics
        self._registration_stats: Dict[str, int] = {
            "total_registered": 0,
            "currently_active": 0,
            "total_unregistered": 0,
            "failed_components": 0,
            "lifecycle_transitions": 0
        }
        
        self.logger.info("ComponentRegistry initialized with comprehensive component management")
    
    def start_monitoring(self) -> None:
        """Start component monitoring and health checking."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="ComponentRegistry-Monitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        self.logger.info("Component registry monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop component monitoring."""
        self._monitoring_active = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
        
        self.logger.info("Component registry monitoring stopped")
    
    def register_component(self, 
                          component_info: ComponentInfo,
                          component_ref: Optional[Any] = None,
                          lifecycle_handler: Optional[ComponentLifecycle] = None) -> None:
        """
        Register component in the registry.
        
        Args:
            component_info: Component information
            component_ref: Optional weak reference to component
            lifecycle_handler: Optional lifecycle management handler
            
        Raises:
            RegistrationError: If registration fails
        """
        with self._registry_lock:
            component_name = component_info.name
            
            # Check if component already registered
            if component_name in self._components:
                existing_info = self._components[component_name]
                if existing_info.status not in [ComponentStatus.STOPPED, ComponentStatus.FAILED]:
                    raise RegistrationError(
                        component_name,
                        "Component already registered and active",
                        existing_component=existing_info.name
                    )
            
            # Validate dependencies if enabled
            if self.enable_dependency_checking:
                self._validate_dependencies(component_info)
            
            # Store component information
            self._components[component_name] = component_info
            
            if component_ref:
                self._component_refs[component_name] = weakref.ref(component_ref)
            
            if lifecycle_handler:
                self._component_handlers[component_name] = lifecycle_handler
            
            # Register capabilities
            self._register_capabilities(component_name, component_info.capabilities)
            
            # Update dependency graph
            self._update_dependency_graph(component_name, component_info.dependencies)
            
            # Update statistics
            self._registration_stats["total_registered"] += 1
            self._registration_stats["currently_active"] += 1
            
            # Set initial status
            component_info.status = ComponentStatus.READY
            component_info.registered_at = datetime.now()
            component_info.update_heartbeat()
        
        self.logger.info(f"Registered component '{component_name}' (type: {component_info.component_type.value})")
        
        # Notify registration callbacks
        for callback in self._registration_callbacks:
            try:
                callback(component_info)
            except Exception as e:
                self.logger.error(f"Error in registration callback: {e}")
    
    def unregister_component(self, component_name: str) -> None:
        """
        Unregister component from registry.
        
        Args:
            component_name: Name of component to unregister
        """
        with self._registry_lock:
            component_info = self._components.get(component_name)
            if not component_info:
                self.logger.warning(f"Attempted to unregister unknown component '{component_name}'")
                return
            
            # Update status before removal
            old_status = component_info.status
            component_info.status = ComponentStatus.STOPPED
            component_info.shutdown_time = datetime.now()
            
            # Remove from active tracking
            self._component_refs.pop(component_name, None)
            self._component_handlers.pop(component_name, None)
            
            # Unregister capabilities
            self._unregister_capabilities(component_name)
            
            # Update dependency graph
            self._remove_from_dependency_graph(component_name)
            
            # CRITICAL: Remove component from registry completely
            self._components.pop(component_name, None)
            
            # Update statistics
            self._registration_stats["currently_active"] -= 1
            self._registration_stats["total_unregistered"] += 1
            
            # Notify lifecycle callbacks
            self._notify_lifecycle_callbacks(component_name, old_status, ComponentStatus.STOPPED)
        
        self.logger.info(f"Unregistered and removed component '{component_name}' from registry")
    
    def get_component(self, component_name: str) -> Optional[ComponentInfo]:
        """Get component information by name."""
        with self._registry_lock:
            return self._components.get(component_name)
    
    def get_all_components(self) -> Dict[str, ComponentInfo]:
        """Get all registered components."""
        with self._registry_lock:
            return self._components.copy()
    
    def get_components_by_type(self, component_type: ComponentType) -> List[ComponentInfo]:
        """Get components by type."""
        with self._registry_lock:
            return [
                info for info in self._components.values()
                if info.component_type == component_type
            ]
    
    def get_components_by_status(self, status: ComponentStatus) -> List[ComponentInfo]:
        """Get components by status."""
        with self._registry_lock:
            return [
                info for info in self._components.values()
                if info.status == status
            ]
    
    def find_components_with_capability(self, capability_name: str) -> List[str]:
        """Find components that provide a specific capability."""
        with self._registry_lock:
            return self._capabilities.get(capability_name, []).copy()
    
    def get_component_dependencies(self, component_name: str) -> Set[str]:
        """Get dependencies for a component."""
        with self._registry_lock:
            return self._dependency_graph.get(component_name, set()).copy()
    
    def get_component_dependents(self, component_name: str) -> Set[str]:
        """Get components that depend on the specified component."""
        with self._registry_lock:
            return self._reverse_dependencies.get(component_name, set()).copy()
    
    def update_component_status(self, component_name: str, new_status: ComponentStatus) -> None:
        """Update component status."""
        with self._registry_lock:
            component_info = self._components.get(component_name)
            if not component_info:
                raise ComponentNotFoundError(component_name, len(self._components))
            
            old_status = component_info.status
            component_info.status = new_status
            component_info.update_heartbeat()
            
            # Update lifecycle timestamps
            if new_status == ComponentStatus.RUNNING and not component_info.startup_time:
                component_info.startup_time = datetime.now()
            elif new_status in [ComponentStatus.STOPPED, ComponentStatus.FAILED]:
                component_info.shutdown_time = datetime.now()
                if new_status == ComponentStatus.FAILED:
                    component_info.error_count += 1
                    self._registration_stats["failed_components"] += 1
            
            # Update statistics
            self._registration_stats["lifecycle_transitions"] += 1
            
            # Notify callbacks
            self._notify_lifecycle_callbacks(component_name, old_status, new_status)
        
        self.logger.info(f"Component '{component_name}' status: {old_status.value} -> {new_status.value}")
    
    def heartbeat(self, component_name: str, health_data: Optional[Dict[str, Any]] = None) -> None:
        """Record component heartbeat."""
        with self._registry_lock:
            component_info = self._components.get(component_name)
            if not component_info:
                self.logger.warning(f"Heartbeat from unknown component '{component_name}'")
                return
            
            component_info.update_heartbeat()
            
            # Update health data if provided
            if health_data:
                component_info.health_score = health_data.get("health_score", component_info.health_score)
                
                # Notify health callbacks
                for callback in self._health_callbacks:
                    try:
                        callback(component_name, health_data)
                    except Exception as e:
                        self.logger.error(f"Error in health callback: {e}")
    
    def start_component(self, component_name: str) -> bool:
        """Start a component using its lifecycle handler."""
        with self._registry_lock:
            component_info = self._components.get(component_name)
            if not component_info:
                raise ComponentNotFoundError(component_name, len(self._components))
            
            handler = self._component_handlers.get(component_name)
            if not handler:
                raise ComponentLifecycleError(component_name, "start", "No lifecycle handler registered")
            
            try:
                # Update status to starting
                self.update_component_status(component_name, ComponentStatus.INITIALIZING)
                
                # Initialize and start component
                if handler.initialize():
                    if handler.start():
                        self.update_component_status(component_name, ComponentStatus.RUNNING)
                        return True
                    else:
                        self.update_component_status(component_name, ComponentStatus.FAILED)
                        return False
                else:
                    self.update_component_status(component_name, ComponentStatus.FAILED)
                    return False
                    
            except Exception as e:
                self.logger.error(f"Error starting component '{component_name}': {e}")
                self.update_component_status(component_name, ComponentStatus.FAILED)
                return False
    
    def stop_component(self, component_name: str) -> bool:
        """Stop a component using its lifecycle handler."""
        with self._registry_lock:
            component_info = self._components.get(component_name)
            if not component_info:
                raise ComponentNotFoundError(component_name, len(self._components))
            
            handler = self._component_handlers.get(component_name)
            if not handler:
                # Component can be stopped without handler
                self.update_component_status(component_name, ComponentStatus.STOPPED)
                return True
            
            try:
                # Update status to stopping
                self.update_component_status(component_name, ComponentStatus.STOPPING)
                
                # Stop component
                if handler.stop():
                    self.update_component_status(component_name, ComponentStatus.STOPPED)
                    return True
                else:
                    self.update_component_status(component_name, ComponentStatus.FAILED)
                    return False
                    
            except Exception as e:
                self.logger.error(f"Error stopping component '{component_name}': {e}")
                self.update_component_status(component_name, ComponentStatus.FAILED)
                return False
    
    def restart_component(self, component_name: str) -> bool:
        """Restart a component."""
        component_info = self._components.get(component_name)
        if not component_info:
            raise ComponentNotFoundError(component_name, len(self._components))
        
        self.logger.info(f"Restarting component '{component_name}'")
        
        # Stop component
        if not self.stop_component(component_name):
            return False
        
        # Wait briefly for cleanup
        time.sleep(0.5)
        
        # Start component
        if self.start_component(component_name):
            component_info.restart_count += 1
            return True
        
        return False
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop for component health."""
        while self._monitoring_active:
            try:
                self._check_component_heartbeats()
                self._perform_health_checks()
                self._cleanup_dead_references()
                
                # Sleep for monitoring interval
                time.sleep(10.0)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in component monitoring loop: {e}")
                time.sleep(5.0)
    
    def _check_component_heartbeats(self) -> None:
        """Check component heartbeats and mark stale components."""
        current_time = datetime.now()
        
        with self._registry_lock:
            for component_name, component_info in self._components.items():
                if component_info.status in [ComponentStatus.STOPPED, ComponentStatus.FAILED]:
                    continue
                
                time_since_heartbeat = current_time - component_info.last_heartbeat
                if time_since_heartbeat > self.heartbeat_timeout:
                    self.logger.warning(f"Component '{component_name}' heartbeat timeout ({time_since_heartbeat})")
                    
                    # Mark as failed if it was running
                    if component_info.status in [ComponentStatus.RUNNING, ComponentStatus.READY]:
                        self.update_component_status(component_name, ComponentStatus.FAILED)
    
    def _perform_health_checks(self) -> None:
        """Perform health checks on components with handlers."""
        if not self.enable_health_monitoring:
            return
        
        with self._registry_lock:
            components_to_check = [
                (name, handler) for name, handler in self._component_handlers.items()
                if self._components[name].status in [ComponentStatus.RUNNING, ComponentStatus.READY]
            ]
        
        for component_name, handler in components_to_check:
            try:
                health_data = handler.health_check()
                self.heartbeat(component_name, health_data)
                
            except Exception as e:
                self.logger.error(f"Health check failed for '{component_name}': {e}")
                self.update_component_status(component_name, ComponentStatus.DEGRADED)
    
    def _cleanup_dead_references(self) -> None:
        """Clean up dead weak references."""
        with self._registry_lock:
            dead_refs = []
            for component_name, ref in self._component_refs.items():
                if ref() is None:
                    dead_refs.append(component_name)
            
            for component_name in dead_refs:
                self.logger.info(f"Cleaning up dead reference for '{component_name}'")
                self._component_refs.pop(component_name, None)
                
                # Mark component as failed if it was active
                component_info = self._components.get(component_name)
                if component_info and component_info.status in [ComponentStatus.RUNNING, ComponentStatus.READY]:
                    self.update_component_status(component_name, ComponentStatus.FAILED)
    
    def _validate_dependencies(self, component_info: ComponentInfo) -> None:
        """Validate component dependencies."""
        for dependency in component_info.dependencies:
            if dependency not in self._components:
                raise RegistrationError(
                    component_info.name,
                    f"Dependency '{dependency}' not found",
                    existing_component=None
                )
            
            dep_info = self._components[dependency]
            if not dep_info.is_available():
                raise RegistrationError(
                    component_info.name,
                    f"Dependency '{dependency}' is not available (status: {dep_info.status.value})",
                    existing_component=dependency
                )
    
    def _register_capabilities(self, component_name: str, capabilities: List[ComponentCapability]) -> None:
        """Register component capabilities."""
        for capability in capabilities:
            if capability.name not in self._capabilities:
                self._capabilities[capability.name] = []
            self._capabilities[capability.name].append(component_name)
    
    def _unregister_capabilities(self, component_name: str) -> None:
        """Unregister component capabilities."""
        for capability_name, component_list in self._capabilities.items():
            if component_name in component_list:
                component_list.remove(component_name)
        
        # Clean up empty capability lists
        empty_capabilities = [name for name, components in self._capabilities.items() if not components]
        for capability_name in empty_capabilities:
            del self._capabilities[capability_name]
    
    def _update_dependency_graph(self, component_name: str, dependencies: Set[str]) -> None:
        """Update dependency graph."""
        self._dependency_graph[component_name] = dependencies.copy()
        
        # Update reverse dependencies
        for dependency in dependencies:
            if dependency not in self._reverse_dependencies:
                self._reverse_dependencies[dependency] = set()
            self._reverse_dependencies[dependency].add(component_name)
    
    def _remove_from_dependency_graph(self, component_name: str) -> None:
        """Remove component from dependency graph."""
        # Remove from dependency graph
        dependencies = self._dependency_graph.pop(component_name, set())
        
        # Remove from reverse dependencies
        for dependency in dependencies:
            if dependency in self._reverse_dependencies:
                self._reverse_dependencies[dependency].discard(component_name)
        
        # Remove as dependency for others
        self._reverse_dependencies.pop(component_name, None)
    
    def _notify_lifecycle_callbacks(self, component_name: str, 
                                   old_status: ComponentStatus, 
                                   new_status: ComponentStatus) -> None:
        """Notify lifecycle change callbacks."""
        for callback in self._lifecycle_callbacks:
            try:
                callback(component_name, old_status, new_status)
            except Exception as e:
                self.logger.error(f"Error in lifecycle callback: {e}")
    
    # Public API methods for callbacks and monitoring
    
    def add_lifecycle_callback(self, callback: Callable[[str, ComponentStatus, ComponentStatus], None]) -> None:
        """Add component lifecycle change callback."""
        self._lifecycle_callbacks.append(callback)
    
    def add_registration_callback(self, callback: Callable[[ComponentInfo], None]) -> None:
        """Add component registration callback."""
        self._registration_callbacks.append(callback)
    
    def add_health_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add component health callback."""
        self._health_callbacks.append(callback)
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._registry_lock:
            status_counts = {}
            for status in ComponentStatus:
                status_counts[status.value] = len(self.get_components_by_status(status))
            
            type_counts = {}
            for comp_type in ComponentType:
                type_counts[comp_type.value] = len(self.get_components_by_type(comp_type))
            
            return {
                "registration_stats": self._registration_stats.copy(),
                "status_distribution": status_counts,
                "type_distribution": type_counts,
                "total_capabilities": len(self._capabilities),
                "dependency_relationships": len(self._dependency_graph),
                "monitoring_active": self._monitoring_active
            }
    
    def get_dependency_tree(self, component_name: str, max_depth: int = 10) -> Dict[str, Any]:
        """Get dependency tree for a component."""
        def build_tree(name: str, depth: int) -> Dict[str, Any]:
            if depth >= max_depth:
                return {"name": name, "max_depth_reached": True}
            
            dependencies = self.get_component_dependencies(name)
            tree = {
                "name": name,
                "status": self._components[name].status.value if name in self._components else "unknown",
                "dependencies": []
            }
            
            for dep in dependencies:
                tree["dependencies"].append(build_tree(dep, depth + 1))
            
            return tree
        
        return build_tree(component_name, 0)
    
    def validate_system_dependencies(self) -> Dict[str, List[str]]:
        """Validate all system dependencies and return issues."""
        issues = {}
        
        with self._registry_lock:
            for component_name, component_info in self._components.items():
                component_issues = []
                
                for dependency in component_info.dependencies:
                    if dependency not in self._components:
                        component_issues.append(f"Missing dependency: {dependency}")
                    else:
                        dep_info = self._components[dependency]
                        if not dep_info.is_available():
                            component_issues.append(f"Unavailable dependency: {dependency} (status: {dep_info.status.value})")
                
                if component_issues:
                    issues[component_name] = component_issues
        
        return issues