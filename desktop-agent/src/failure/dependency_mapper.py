"""
Component Dependency Mapper

Maps dependencies between GURU components and analyzes cascade failure
patterns to prevent system-wide failures from propagating uncontrolled.

This system provides:
- Component dependency graph construction
- Cascade failure analysis and prediction
- Dependency-based failure impact assessment
- Critical path identification for system stability
- Isolation boundary enforcement
"""

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class DependencyType(Enum):
    """Types of component dependencies."""
    HARD_DEPENDENCY = "hard"      # Component cannot function without dependency
    SOFT_DEPENDENCY = "soft"      # Component has reduced functionality without dependency
    DATA_DEPENDENCY = "data"      # Component needs data from dependency
    CONTROL_DEPENDENCY = "control" # Component is controlled by dependency
    SECURITY_DEPENDENCY = "security" # Component relies on dependency for security


class ComponentCriticality(Enum):
    """Criticality levels for components."""
    CRITICAL = "critical"         # System cannot function without this component
    IMPORTANT = "important"       # System has reduced functionality without this component
    OPTIONAL = "optional"         # System can function normally without this component
    ENHANCEMENT = "enhancement"   # Component only provides additional features


@dataclass(frozen=True)
class ComponentDependency:
    """Represents a dependency relationship between components."""
    dependent: str                # Component that depends on another
    dependency: str              # Component that is depended upon
    dependency_type: DependencyType
    criticality: ComponentCriticality
    description: str
    failure_impact: str          # Description of what happens if dependency fails
    isolation_boundary: bool = False  # Whether this crosses an isolation boundary


@dataclass
class CascadeAnalysis:
    """Analysis of potential cascade failure patterns."""
    root_component: str
    affected_components: List[str]
    cascade_depth: int
    estimated_impact_score: float  # 0-100 scale
    critical_path: List[str]
    isolation_boundaries_crossed: int
    mitigation_strategies: List[str]
    analysis_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DependencyGraph:
    """Complete dependency graph for the system."""
    components: Set[str]
    dependencies: List[ComponentDependency]
    adjacency_list: Dict[str, List[str]] = field(default_factory=dict)
    reverse_adjacency_list: Dict[str, List[str]] = field(default_factory=dict)
    component_criticality: Dict[str, ComponentCriticality] = field(default_factory=dict)
    isolation_boundaries: Set[Tuple[str, str]] = field(default_factory=set)


class DependencyMapper:
    """
    Maps and analyzes component dependencies for cascade failure prevention.
    
    Maintains a comprehensive dependency graph of all GURU components and
    provides analysis capabilities for understanding failure propagation
    patterns and implementing effective isolation strategies.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Dependency graph
        self._dependency_graph = DependencyGraph(set(), [])
        self._graph_lock = threading.RLock()
        
        # Analysis cache
        self._cascade_analysis_cache: Dict[str, CascadeAnalysis] = {}
        self._cache_lock = threading.RLock()
        
        # Initialize with known GURU component dependencies
        self._initialize_guru_dependencies()
        
    def _initialize_guru_dependencies(self) -> None:
        """Initialize dependency graph with known GURU component relationships."""
        # Define core GURU components and their dependencies
        guru_dependencies = [
            # Authority system dependencies
            ComponentDependency(
                dependent="authority_state_machine",
                dependency="biometric_verifier",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Authority system requires biometric verification for identity confirmation",
                failure_impact="Cannot verify user identity, system locks down"
            ),
            ComponentDependency(
                dependent="authority_state_machine",
                dependency="audit_logger",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Authority system requires audit logging for all state transitions",
                failure_impact="Cannot log authority changes, system halts for security"
            ),
            ComponentDependency(
                dependent="authority_state_machine",
                dependency="cryptographic_engine",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Authority system requires cryptographic operations for security",
                failure_impact="Cannot perform secure operations, system halts"
            ),
            
            # Input system dependencies
            ComponentDependency(
                dependent="input_engine",
                dependency="authority_state_machine",
                dependency_type=DependencyType.CONTROL_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Input engine requires authority verification before any simulation",
                failure_impact="Cannot verify authority, all input simulation disabled"
            ),
            ComponentDependency(
                dependent="input_engine",
                dependency="audit_logger",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Input engine must log all simulation events for audit",
                failure_impact="Cannot log input events, input simulation disabled"
            ),
            
            # Memory system dependencies
            ComponentDependency(
                dependent="memory_service",
                dependency="cryptographic_engine",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.IMPORTANT,
                description="Memory service requires encryption for sensitive data storage",
                failure_impact="Cannot encrypt sensitive memories, reduced functionality"
            ),
            ComponentDependency(
                dependent="memory_service",
                dependency="audit_logger",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.IMPORTANT,
                description="Memory service logs access to sensitive memories",
                failure_impact="Cannot log memory access, sensitive operations disabled"
            ),
            
            # LLM system dependencies
            ComponentDependency(
                dependent="llm_adapter",
                dependency="authority_state_machine",
                dependency_type=DependencyType.CONTROL_DEPENDENCY,
                criticality=ComponentCriticality.IMPORTANT,
                description="LLM adapter requires authority verification for intent routing",
                failure_impact="Cannot route intents through authority gates, LLM disabled"
            ),
            ComponentDependency(
                dependent="llm_adapter",
                dependency="audit_logger",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.IMPORTANT,
                description="LLM adapter logs all intent processing for audit",
                failure_impact="Cannot log LLM operations, LLM functionality disabled"
            ),
            
            # Skill system dependencies
            ComponentDependency(
                dependent="skill_runner",
                dependency="authority_state_machine",
                dependency_type=DependencyType.CONTROL_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Skill runner requires authority verification before execution",
                failure_impact="Cannot verify authority for skill execution, all skills disabled"
            ),
            ComponentDependency(
                dependent="skill_runner",
                dependency="audit_logger",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Skill runner must log all skill executions for audit",
                failure_impact="Cannot log skill execution, all skills disabled"
            ),
            ComponentDependency(
                dependent="skill_runner",
                dependency="cryptographic_engine",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.IMPORTANT,
                description="Skill runner uses cryptographic verification for skill integrity",
                failure_impact="Cannot verify skill integrity, high-risk skills disabled"
            ),
            
            # Intrusion detection dependencies
            ComponentDependency(
                dependent="intrusion_detector",
                dependency="biometric_verifier",
                dependency_type=DependencyType.DATA_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Intrusion detector monitors biometric verification failures",
                failure_impact="Cannot detect biometric intrusion attempts"
            ),
            ComponentDependency(
                dependent="intrusion_detector",
                dependency="audit_logger",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Intrusion detector logs all security events",
                failure_impact="Cannot log intrusion events, security monitoring compromised"
            ),
            
            # Audit system dependencies (minimal - audit is foundational)
            ComponentDependency(
                dependent="audit_logger",
                dependency="cryptographic_engine",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Audit logger requires cryptographic signing for log integrity",
                failure_impact="Cannot sign audit logs, system halts for security"
            ),
            
            # Biometric system dependencies
            ComponentDependency(
                dependent="biometric_verifier",
                dependency="audit_logger",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Biometric verifier logs all verification attempts",
                failure_impact="Cannot log biometric events, verification disabled"
            ),
            
            # Cross-boundary dependencies (with isolation boundaries)
            ComponentDependency(
                dependent="phone_agent",
                dependency="cryptographic_engine",
                dependency_type=DependencyType.SECURITY_DEPENDENCY,
                criticality=ComponentCriticality.CRITICAL,
                description="Phone agent requires secure communication with desktop",
                failure_impact="Cannot establish secure communication channel",
                isolation_boundary=True
            ),
            ComponentDependency(
                dependent="desktop_agent",
                dependency="phone_agent",
                dependency_type=DependencyType.SOFT_DEPENDENCY,
                criticality=ComponentCriticality.OPTIONAL,
                description="Desktop agent can receive commands from phone agent",
                failure_impact="Reduced functionality, local operation only",
                isolation_boundary=True
            )
        ]
        
        # Add all dependencies to the graph
        for dependency in guru_dependencies:
            self.add_dependency(dependency)
    
    def add_dependency(self, dependency: ComponentDependency) -> None:
        """Add a dependency relationship to the graph."""
        with self._graph_lock:
            # Add components to the graph
            self._dependency_graph.components.add(dependency.dependent)
            self._dependency_graph.components.add(dependency.dependency)
            
            # Add dependency to the list
            self._dependency_graph.dependencies.append(dependency)
            
            # Update adjacency lists
            if dependency.dependent not in self._dependency_graph.adjacency_list:
                self._dependency_graph.adjacency_list[dependency.dependent] = []
            self._dependency_graph.adjacency_list[dependency.dependent].append(dependency.dependency)
            
            if dependency.dependency not in self._dependency_graph.reverse_adjacency_list:
                self._dependency_graph.reverse_adjacency_list[dependency.dependency] = []
            self._dependency_graph.reverse_adjacency_list[dependency.dependency].append(dependency.dependent)
            
            # Update component criticality
            self._dependency_graph.component_criticality[dependency.dependent] = dependency.criticality
            
            # Track isolation boundaries
            if dependency.isolation_boundary:
                self._dependency_graph.isolation_boundaries.add(
                    (dependency.dependent, dependency.dependency)
                )
            
            # Clear analysis cache since graph changed
            with self._cache_lock:
                self._cascade_analysis_cache.clear()
        
        self.logger.debug(f"Added dependency: {dependency.dependent} -> {dependency.dependency} "
                         f"({dependency.dependency_type.value}, {dependency.criticality.value})")
    
    def remove_dependency(self, dependent: str, dependency: str) -> bool:
        """Remove a dependency relationship from the graph."""
        with self._graph_lock:
            # Find and remove the dependency
            dependencies_to_remove = [
                dep for dep in self._dependency_graph.dependencies
                if dep.dependent == dependent and dep.dependency == dependency
            ]
            
            if not dependencies_to_remove:
                return False
            
            for dep in dependencies_to_remove:
                self._dependency_graph.dependencies.remove(dep)
                
                # Update adjacency lists
                if dependent in self._dependency_graph.adjacency_list:
                    if dependency in self._dependency_graph.adjacency_list[dependent]:
                        self._dependency_graph.adjacency_list[dependent].remove(dependency)
                
                if dependency in self._dependency_graph.reverse_adjacency_list:
                    if dependent in self._dependency_graph.reverse_adjacency_list[dependency]:
                        self._dependency_graph.reverse_adjacency_list[dependency].remove(dependent)
                
                # Remove isolation boundary if it exists
                boundary = (dependent, dependency)
                self._dependency_graph.isolation_boundaries.discard(boundary)
            
            # Clear analysis cache
            with self._cache_lock:
                self._cascade_analysis_cache.clear()
        
        self.logger.debug(f"Removed dependency: {dependent} -> {dependency}")
        return True
    
    def analyze_cascade_failure(self, root_component: str) -> CascadeAnalysis:
        """Analyze potential cascade failure starting from a root component."""
        # Check cache first
        with self._cache_lock:
            if root_component in self._cascade_analysis_cache:
                cached_analysis = self._cascade_analysis_cache[root_component]
                # Return cached result if it's recent (within 5 minutes)
                if (datetime.now() - cached_analysis.analysis_timestamp).total_seconds() < 300:
                    return cached_analysis
        
        with self._graph_lock:
            # Perform cascade analysis
            affected_components = self._find_cascade_affected_components(root_component)
            cascade_depth = self._calculate_cascade_depth(root_component, affected_components)
            impact_score = self._calculate_impact_score(root_component, affected_components)
            critical_path = self._find_critical_path(root_component, affected_components)
            boundaries_crossed = self._count_isolation_boundaries_crossed(root_component, affected_components)
            mitigation_strategies = self._generate_mitigation_strategies(root_component, affected_components)
            
            analysis = CascadeAnalysis(
                root_component=root_component,
                affected_components=affected_components,
                cascade_depth=cascade_depth,
                estimated_impact_score=impact_score,
                critical_path=critical_path,
                isolation_boundaries_crossed=boundaries_crossed,
                mitigation_strategies=mitigation_strategies
            )
            
            # Cache the analysis
            with self._cache_lock:
                self._cascade_analysis_cache[root_component] = analysis
            
            return analysis
    
    def _find_cascade_affected_components(self, root_component: str) -> List[str]:
        """Find all components that would be affected by a cascade failure."""
        affected = set()
        queue = deque([root_component])
        visited = set()
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            
            visited.add(current)
            
            # Find all components that depend on the current component
            dependents = self._dependency_graph.reverse_adjacency_list.get(current, [])
            
            for dependent in dependents:
                if dependent not in visited:
                    # Check if this dependency would cause failure
                    dependency_info = self._get_dependency_info(dependent, current)
                    if dependency_info and self._would_cause_failure(dependency_info):
                        affected.add(dependent)
                        queue.append(dependent)
        
        return list(affected)
    
    def _get_dependency_info(self, dependent: str, dependency: str) -> Optional[ComponentDependency]:
        """Get dependency information between two components."""
        for dep in self._dependency_graph.dependencies:
            if dep.dependent == dependent and dep.dependency == dependency:
                return dep
        return None
    
    def _would_cause_failure(self, dependency: ComponentDependency) -> bool:
        """Determine if a dependency failure would cause the dependent to fail."""
        # Hard dependencies and critical security dependencies always cause failure
        if dependency.dependency_type == DependencyType.HARD_DEPENDENCY:
            return True
        
        if (dependency.dependency_type == DependencyType.SECURITY_DEPENDENCY and
            dependency.criticality == ComponentCriticality.CRITICAL):
            return True
        
        # Control dependencies with critical or important criticality cause failure
        if (dependency.dependency_type == DependencyType.CONTROL_DEPENDENCY and
            dependency.criticality in [ComponentCriticality.CRITICAL, ComponentCriticality.IMPORTANT]):
            return True
        
        return False
    
    def _calculate_cascade_depth(self, root_component: str, affected_components: List[str]) -> int:
        """Calculate the maximum depth of the cascade failure."""
        if not affected_components:
            return 0
        
        # Use BFS to find the maximum depth
        queue = deque([(root_component, 0)])
        visited = set()
        max_depth = 0
        
        while queue:
            current, depth = queue.popleft()
            if current in visited:
                continue
            
            visited.add(current)
            max_depth = max(max_depth, depth)
            
            # Find dependents
            dependents = self._dependency_graph.reverse_adjacency_list.get(current, [])
            for dependent in dependents:
                if dependent in affected_components and dependent not in visited:
                    queue.append((dependent, depth + 1))
        
        return max_depth
    
    def _calculate_impact_score(self, root_component: str, affected_components: List[str]) -> float:
        """Calculate the estimated impact score (0-100) of the cascade failure."""
        if not affected_components:
            return 0.0
        
        # Base score based on number of affected components
        base_score = min(len(affected_components) * 10, 50)
        
        # Criticality multiplier
        criticality_scores = {
            ComponentCriticality.CRITICAL: 30,
            ComponentCriticality.IMPORTANT: 20,
            ComponentCriticality.OPTIONAL: 10,
            ComponentCriticality.ENHANCEMENT: 5
        }
        
        criticality_bonus = 0
        for component in [root_component] + affected_components:
            criticality = self._dependency_graph.component_criticality.get(
                component, ComponentCriticality.OPTIONAL
            )
            criticality_bonus += criticality_scores.get(criticality, 10)
        
        # Isolation boundary penalty (crossing boundaries is worse)
        boundary_penalty = self._count_isolation_boundaries_crossed(root_component, affected_components) * 5
        
        total_score = min(base_score + criticality_bonus + boundary_penalty, 100.0)
        return total_score
    
    def _find_critical_path(self, root_component: str, affected_components: List[str]) -> List[str]:
        """Find the critical path through the cascade failure."""
        if not affected_components:
            return [root_component]
        
        # Find the path that affects the most critical components
        critical_components = [
            comp for comp in affected_components
            if self._dependency_graph.component_criticality.get(comp) == ComponentCriticality.CRITICAL
        ]
        
        if not critical_components:
            # If no critical components, find path to most important components
            important_components = [
                comp for comp in affected_components
                if self._dependency_graph.component_criticality.get(comp) == ComponentCriticality.IMPORTANT
            ]
            target_components = important_components if important_components else affected_components[:3]
        else:
            target_components = critical_components
        
        # Build path using BFS to first critical/important component
        if target_components:
            queue = deque([(root_component, [root_component])])
            visited = set()
            
            while queue:
                current, path = queue.popleft()
                if current in visited:
                    continue
                
                visited.add(current)
                
                if current in target_components:
                    return path
                
                dependents = self._dependency_graph.reverse_adjacency_list.get(current, [])
                for dependent in dependents:
                    if dependent in affected_components and dependent not in visited:
                        queue.append((dependent, path + [dependent]))
        
        return [root_component] + affected_components[:3]  # Fallback
    
    def _count_isolation_boundaries_crossed(self, root_component: str, 
                                          affected_components: List[str]) -> int:
        """Count how many isolation boundaries are crossed in the cascade."""
        boundaries_crossed = 0
        all_components = [root_component] + affected_components
        
        for boundary in self._dependency_graph.isolation_boundaries:
            dependent, dependency = boundary
            if dependent in all_components and dependency in all_components:
                boundaries_crossed += 1
        
        return boundaries_crossed
    
    def _generate_mitigation_strategies(self, root_component: str, 
                                      affected_components: List[str]) -> List[str]:
        """Generate mitigation strategies for the cascade failure."""
        strategies = []
        
        # Strategy 1: Isolate the root component
        strategies.append(f"Isolate '{root_component}' to prevent cascade propagation")
        
        # Strategy 2: Strengthen critical dependencies
        critical_deps = [
            comp for comp in affected_components
            if self._dependency_graph.component_criticality.get(comp) == ComponentCriticality.CRITICAL
        ]
        if critical_deps:
            strategies.append(f"Implement redundancy for critical components: {', '.join(critical_deps[:3])}")
        
        # Strategy 3: Add circuit breakers at isolation boundaries
        if self._count_isolation_boundaries_crossed(root_component, affected_components) > 0:
            strategies.append("Add circuit breakers at isolation boundaries to prevent cross-boundary failures")
        
        # Strategy 4: Implement graceful degradation
        optional_components = [
            comp for comp in affected_components
            if self._dependency_graph.component_criticality.get(comp) in [
                ComponentCriticality.OPTIONAL, ComponentCriticality.ENHANCEMENT
            ]
        ]
        if optional_components:
            strategies.append(f"Implement graceful degradation for optional components: {', '.join(optional_components[:3])}")
        
        # Strategy 5: Add health monitoring
        strategies.append("Enhance health monitoring and early warning systems for cascade detection")
        
        return strategies
    
    def get_component_dependencies(self, component: str) -> List[ComponentDependency]:
        """Get all dependencies for a specific component."""
        with self._graph_lock:
            return [
                dep for dep in self._dependency_graph.dependencies
                if dep.dependent == component
            ]
    
    def get_component_dependents(self, component: str) -> List[ComponentDependency]:
        """Get all components that depend on the specified component."""
        with self._graph_lock:
            return [
                dep for dep in self._dependency_graph.dependencies
                if dep.dependency == component
            ]
    
    def get_critical_components(self) -> List[str]:
        """Get all components marked as critical."""
        with self._graph_lock:
            return [
                comp for comp, criticality in self._dependency_graph.component_criticality.items()
                if criticality == ComponentCriticality.CRITICAL
            ]
    
    def get_isolation_boundaries(self) -> List[Tuple[str, str]]:
        """Get all isolation boundaries in the system."""
        with self._graph_lock:
            return list(self._dependency_graph.isolation_boundaries)
    
    def validate_dependency_graph(self) -> List[str]:
        """Validate the dependency graph for consistency and detect issues."""
        issues = []
        
        with self._graph_lock:
            # Check for circular dependencies
            circular_deps = self._detect_circular_dependencies()
            if circular_deps:
                issues.extend([f"Circular dependency detected: {' -> '.join(cycle)}" 
                              for cycle in circular_deps])
            
            # Check for orphaned components
            all_referenced = set()
            for dep in self._dependency_graph.dependencies:
                all_referenced.add(dep.dependent)
                all_referenced.add(dep.dependency)
            
            orphaned = self._dependency_graph.components - all_referenced
            if orphaned:
                issues.append(f"Orphaned components (no dependencies): {', '.join(orphaned)}")
            
            # Check for missing critical dependencies
            critical_components = self.get_critical_components()
            for component in critical_components:
                deps = self.get_component_dependencies(component)
                if not deps:
                    issues.append(f"Critical component '{component}' has no dependencies - may be isolated")
        
        return issues
    
    def _detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in the graph."""
        def dfs(node: str, path: List[str], visited: Set[str], rec_stack: Set[str]) -> List[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            cycles = []
            
            for neighbor in self._dependency_graph.adjacency_list.get(node, []):
                if neighbor not in visited:
                    cycles.extend(dfs(neighbor, path + [neighbor], visited, rec_stack))
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            
            rec_stack.remove(node)
            return cycles
        
        visited = set()
        all_cycles = []
        
        for component in self._dependency_graph.components:
            if component not in visited:
                cycles = dfs(component, [component], visited, set())
                all_cycles.extend(cycles)
        
        return all_cycles
    
    def export_dependency_graph(self) -> Dict[str, Any]:
        """Export the dependency graph for visualization or analysis."""
        with self._graph_lock:
            return {
                "components": list(self._dependency_graph.components),
                "dependencies": [
                    {
                        "dependent": dep.dependent,
                        "dependency": dep.dependency,
                        "type": dep.dependency_type.value,
                        "criticality": dep.criticality.value,
                        "description": dep.description,
                        "failure_impact": dep.failure_impact,
                        "isolation_boundary": dep.isolation_boundary
                    }
                    for dep in self._dependency_graph.dependencies
                ],
                "component_criticality": {
                    comp: crit.value for comp, crit in self._dependency_graph.component_criticality.items()
                },
                "isolation_boundaries": [
                    {"dependent": dep, "dependency": dep_on}
                    for dep, dep_on in self._dependency_graph.isolation_boundaries
                ],
                "graph_stats": {
                    "total_components": len(self._dependency_graph.components),
                    "total_dependencies": len(self._dependency_graph.dependencies),
                    "critical_components": len(self.get_critical_components()),
                    "isolation_boundaries": len(self._dependency_graph.isolation_boundaries)
                }
            }