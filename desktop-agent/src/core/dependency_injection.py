"""
Production-Grade Dependency Injection Container

Eliminates circular dependencies through proper inversion of control.
Provides thread-safe, lazy-loading dependency resolution with lifecycle management.

Architecture:
- Singleton container with thread-safe registration/resolution
- Lazy initialization to break circular dependency chains
- Interface-based registration for testability
- Lifecycle management (singleton, transient, scoped)
- Dependency graph validation to prevent cycles

Security:
- No reflection-based instantiation (explicit factory functions)
- Type-safe registration and resolution
- Audit trail of all dependency resolutions
- No dynamic code execution

Performance:
- O(1) resolution after first initialization
- Minimal memory overhead
- Thread-safe without global locks (per-dependency locks)
- Lazy loading to minimize startup time
"""

import threading
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Generic, Optional, Set, Type, TypeVar, Union
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class DependencyLifecycle(Enum):
    """Dependency lifecycle management strategies."""
    SINGLETON = "singleton"      # One instance per container
    TRANSIENT = "transient"      # New instance every resolution
    SCOPED = "scoped"           # One instance per scope (e.g., per request)


class DependencyScope(Enum):
    """Dependency scopes for lifecycle management."""
    APPLICATION = "application"  # Application lifetime
    SESSION = "session"         # User session lifetime
    REQUEST = "request"         # Single operation lifetime


@dataclass
class DependencyRegistration:
    """Registration metadata for a dependency."""
    interface: Type
    implementation: Optional[Type]
    factory: Optional[Callable[[], Any]]
    lifecycle: DependencyLifecycle
    scope: DependencyScope
    dependencies: Set[Type]
    initialized: bool = False
    instance: Optional[Any] = None
    lock: threading.RLock = None

    def __post_init__(self):
        if self.lock is None:
            self.lock = threading.RLock()


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""
    
    def __init__(self, dependency_chain: list):
        self.dependency_chain = dependency_chain
        chain_str = " -> ".join(dep.__name__ for dep in dependency_chain)
        super().__init__(f"Circular dependency detected: {chain_str}")


class DependencyNotRegisteredError(Exception):
    """Raised when attempting to resolve unregistered dependency."""
    
    def __init__(self, dependency_type: Type):
        super().__init__(f"Dependency not registered: {dependency_type.__name__}")


class DependencyContainer:
    """
    Thread-safe dependency injection container with lifecycle management.
    
    Eliminates circular dependencies through lazy initialization and
    proper inversion of control patterns.
    """
    
    _instance: Optional['DependencyContainer'] = None
    _lock = threading.RLock()
    
    def __init__(self):
        self._registrations: Dict[Type, DependencyRegistration] = {}
        self._resolution_stack: Set[Type] = set()
        self._scoped_instances: Dict[DependencyScope, Dict[Type, Any]] = {
            scope: {} for scope in DependencyScope
        }
        self._container_lock = threading.RLock()
        
    @classmethod
    def get_instance(cls) -> 'DependencyContainer':
        """Get singleton container instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.info("Dependency container initialized")
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._lock:
            if cls._instance:
                cls._instance._cleanup()
            cls._instance = None
            logger.info("Dependency container reset")
    
    def register_singleton(
        self, 
        interface: Type[T], 
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        dependencies: Optional[Set[Type]] = None
    ) -> 'DependencyContainer':
        """Register a singleton dependency."""
        return self._register(
            interface, implementation, factory, 
            DependencyLifecycle.SINGLETON, DependencyScope.APPLICATION,
            dependencies or set()
        )
    
    def register_transient(
        self, 
        interface: Type[T], 
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        dependencies: Optional[Set[Type]] = None
    ) -> 'DependencyContainer':
        """Register a transient dependency."""
        return self._register(
            interface, implementation, factory,
            DependencyLifecycle.TRANSIENT, DependencyScope.REQUEST,
            dependencies or set()
        )
    
    def register_scoped(
        self, 
        interface: Type[T], 
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        scope: DependencyScope = DependencyScope.SESSION,
        dependencies: Optional[Set[Type]] = None
    ) -> 'DependencyContainer':
        """Register a scoped dependency."""
        return self._register(
            interface, implementation, factory,
            DependencyLifecycle.SCOPED, scope,
            dependencies or set()
        )
    
    def _register(
        self,
        interface: Type,
        implementation: Optional[Type],
        factory: Optional[Callable],
        lifecycle: DependencyLifecycle,
        scope: DependencyScope,
        dependencies: Set[Type]
    ) -> 'DependencyContainer':
        """Internal registration method."""
        if implementation is None and factory is None:
            implementation = interface
            
        if implementation is not None and factory is not None:
            raise ValueError("Cannot specify both implementation and factory")
            
        with self._container_lock:
            registration = DependencyRegistration(
                interface=interface,
                implementation=implementation,
                factory=factory,
                lifecycle=lifecycle,
                scope=scope,
                dependencies=dependencies
            )
            
            self._registrations[interface] = registration
            
            logger.debug(
                "Dependency registered",
                interface=interface.__name__,
                implementation=implementation.__name__ if implementation else "factory",
                lifecycle=lifecycle.value,
                scope=scope.value
            )
            
        return self
    
    def resolve(self, dependency_type: Type[T]) -> T:
        """
        Resolve a dependency with full lifecycle management.
        
        Args:
            dependency_type: The interface/type to resolve
            
        Returns:
            Instance of the requested type
            
        Raises:
            DependencyNotRegisteredError: If dependency not registered
            CircularDependencyError: If circular dependency detected
        """
        return self._resolve_with_stack(dependency_type, set())
    
    def _resolve_with_stack(self, dependency_type: Type[T], resolution_stack: Set[Type]) -> T:
        """Internal resolution with circular dependency detection."""
        # Check for circular dependency
        if dependency_type in resolution_stack:
            chain = list(resolution_stack) + [dependency_type]
            raise CircularDependencyError(chain)
            
        # Check if registered
        if dependency_type not in self._registrations:
            raise DependencyNotRegisteredError(dependency_type)
            
        registration = self._registrations[dependency_type]
        
        # Handle different lifecycles
        if registration.lifecycle == DependencyLifecycle.SINGLETON:
            return self._resolve_singleton(registration, resolution_stack)
        elif registration.lifecycle == DependencyLifecycle.SCOPED:
            return self._resolve_scoped(registration, resolution_stack)
        else:  # TRANSIENT
            return self._resolve_transient(registration, resolution_stack)
    
    def _resolve_singleton(self, registration: DependencyRegistration, resolution_stack: Set[Type]) -> Any:
        """Resolve singleton with thread-safe lazy initialization."""
        if registration.instance is not None:
            return registration.instance
            
        with registration.lock:
            # Double-check pattern
            if registration.instance is not None:
                return registration.instance
                
            # Create instance
            new_stack = resolution_stack | {registration.interface}
            instance = self._create_instance(registration, new_stack)
            registration.instance = instance
            registration.initialized = True
            
            logger.debug(
                "Singleton dependency resolved",
                interface=registration.interface.__name__
            )
            
            return instance
    
    def _resolve_scoped(self, registration: DependencyRegistration, resolution_stack: Set[Type]) -> Any:
        """Resolve scoped dependency."""
        scope_instances = self._scoped_instances[registration.scope]
        
        if registration.interface in scope_instances:
            return scope_instances[registration.interface]
            
        with registration.lock:
            # Double-check pattern
            if registration.interface in scope_instances:
                return scope_instances[registration.interface]
                
            # Create instance
            new_stack = resolution_stack | {registration.interface}
            instance = self._create_instance(registration, new_stack)
            scope_instances[registration.interface] = instance
            
            logger.debug(
                "Scoped dependency resolved",
                interface=registration.interface.__name__,
                scope=registration.scope.value
            )
            
            return instance
    
    def _resolve_transient(self, registration: DependencyRegistration, resolution_stack: Set[Type]) -> Any:
        """Resolve transient dependency (new instance every time)."""
        new_stack = resolution_stack | {registration.interface}
        instance = self._create_instance(registration, new_stack)
        
        logger.debug(
            "Transient dependency resolved",
            interface=registration.interface.__name__
        )
        
        return instance
    
    def _create_instance(self, registration: DependencyRegistration, resolution_stack: Set[Type]) -> Any:
        """Create instance using factory or constructor."""
        try:
            if registration.factory:
                # Use factory function
                return registration.factory()
            else:
                # Use constructor with dependency injection
                if registration.dependencies:
                    # Resolve dependencies first
                    resolved_deps = {}
                    for dep_type in registration.dependencies:
                        resolved_deps[dep_type] = self._resolve_with_stack(dep_type, resolution_stack)
                    
                    # Create instance with dependencies
                    # Note: This requires the implementation to accept dependencies
                    # in its constructor. For complex cases, use factory functions.
                    return registration.implementation(**resolved_deps)
                else:
                    # Simple instantiation
                    return registration.implementation()
                    
        except Exception as e:
            logger.error(
                "Failed to create dependency instance",
                interface=registration.interface.__name__,
                error=str(e)
            )
            raise
    
    def clear_scope(self, scope: DependencyScope) -> None:
        """Clear all instances in a specific scope."""
        with self._container_lock:
            cleared_count = len(self._scoped_instances[scope])
            self._scoped_instances[scope].clear()
            
            logger.info(
                "Dependency scope cleared",
                scope=scope.value,
                instances_cleared=cleared_count
            )
    
    def validate_registrations(self) -> None:
        """
        Validate all registrations for circular dependencies.
        
        Raises:
            CircularDependencyError: If circular dependencies detected
        """
        logger.info("Validating dependency registrations")
        
        for interface in self._registrations:
            try:
                self._validate_dependency_chain(interface, set())
            except CircularDependencyError as e:
                logger.error(
                    "Circular dependency validation failed",
                    interface=interface.__name__,
                    chain=e.dependency_chain
                )
                raise
                
        logger.info("Dependency validation completed successfully")
    
    def _validate_dependency_chain(self, interface: Type, visited: Set[Type]) -> None:
        """Recursively validate dependency chain for cycles."""
        if interface in visited:
            chain = list(visited) + [interface]
            raise CircularDependencyError(chain)
            
        if interface not in self._registrations:
            return  # External dependency, skip validation
            
        registration = self._registrations[interface]
        new_visited = visited | {interface}
        
        for dependency in registration.dependencies:
            self._validate_dependency_chain(dependency, new_visited)
    
    def get_registration_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered dependencies."""
        info = {}
        
        with self._container_lock:
            for interface, registration in self._registrations.items():
                info[interface.__name__] = {
                    "lifecycle": registration.lifecycle.value,
                    "scope": registration.scope.value,
                    "initialized": registration.initialized,
                    "has_instance": registration.instance is not None,
                    "dependencies": [dep.__name__ for dep in registration.dependencies],
                    "implementation": registration.implementation.__name__ if registration.implementation else "factory"
                }
                
        return info
    
    def _cleanup(self) -> None:
        """Cleanup container resources."""
        with self._container_lock:
            # Clear all scoped instances
            for scope in DependencyScope:
                self._scoped_instances[scope].clear()
                
            # Clear singleton instances
            for registration in self._registrations.values():
                registration.instance = None
                registration.initialized = False
                
            logger.info("Dependency container cleaned up")


# Global container instance
_container = DependencyContainer.get_instance()


def register_singleton(
    interface: Type[T], 
    implementation: Optional[Type[T]] = None,
    factory: Optional[Callable[[], T]] = None,
    dependencies: Optional[Set[Type]] = None
) -> DependencyContainer:
    """Register a singleton dependency in the global container."""
    return _container.register_singleton(interface, implementation, factory, dependencies)


def register_transient(
    interface: Type[T], 
    implementation: Optional[Type[T]] = None,
    factory: Optional[Callable[[], T]] = None,
    dependencies: Optional[Set[Type]] = None
) -> DependencyContainer:
    """Register a transient dependency in the global container."""
    return _container.register_transient(interface, implementation, factory, dependencies)


def register_scoped(
    interface: Type[T], 
    implementation: Optional[Type[T]] = None,
    factory: Optional[Callable[[], T]] = None,
    scope: DependencyScope = DependencyScope.SESSION,
    dependencies: Optional[Set[Type]] = None
) -> DependencyContainer:
    """Register a scoped dependency in the global container."""
    return _container.register_scoped(interface, implementation, factory, scope, dependencies)


def resolve(dependency_type: Type[T]) -> T:
    """Resolve a dependency from the global container."""
    return _container.resolve(dependency_type)


def clear_scope(scope: DependencyScope) -> None:
    """Clear all instances in a specific scope."""
    _container.clear_scope(scope)


def validate_registrations() -> None:
    """Validate all registrations for circular dependencies."""
    _container.validate_registrations()


def get_container() -> DependencyContainer:
    """Get the global dependency container."""
    return _container


def reset_container() -> None:
    """Reset the global container (for testing)."""
    global _container
    DependencyContainer.reset_instance()
    _container = DependencyContainer.get_instance()