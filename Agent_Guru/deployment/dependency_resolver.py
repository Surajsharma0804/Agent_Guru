"""Dependency resolution for the Guru Deployment System.

Resolves package dependencies, detects conflicts and cycles, and
produces a topological installation order.

Time Complexity: O(V + E) for graph traversal
Space Complexity: O(V + E) for the dependency graph
"""

from __future__ import annotations

from collections import defaultdict

import structlog
from packaging.requirements import Requirement
from packaging.version import Version

from .exceptions import CircularDependencyError
from .models import Conflict, DependencyGraph, PackageInfo, PackageNode

logger = structlog.get_logger(__name__)


class DependencyResolver:
    """Resolves package dependencies using a topological sort approach.

    Caches resolution results to avoid redundant computation (Property 36).
    """

    def __init__(self) -> None:
        # Cache: (package_name, version) -> DependencyGraph
        self._cache: dict[tuple[str, str], DependencyGraph] = {}

    def resolve_dependencies(
        self,
        package_name: str,
        version: str,
        installed_packages: list[PackageInfo],
        available_packages: dict[str, list[str]] | None = None,
    ) -> DependencyGraph:
        """Resolve all dependencies for a package.

        Args:
            package_name: Name of the package to resolve.
            version: Version of the package.
            installed_packages: Currently installed packages.
            available_packages: Map of package_name -> [available versions].

        Returns:
            DependencyGraph with all resolved dependencies.

        Raises:
            DependencyConflictError: If version conflict detected.
            CircularDependencyError: If circular dependency detected.

        """
        cache_key = (package_name, version)
        if cache_key in self._cache:
            logger.debug("dependency_cache_hit", package=package_name, version=version)
            return self._cache[cache_key]

        installed_map: dict[str, str] = {p.name: p.version for p in installed_packages}
        graph = DependencyGraph()
        self._build_graph(
            package_name,
            version,
            installed_map,
            available_packages or {},
            graph,
            set(),
        )

        if graph.has_cycle():
            msg = f"Circular dependency detected involving '{package_name}'"
            raise CircularDependencyError(
                msg,
            )

        self._cache[cache_key] = graph
        logger.info(
            "dependencies_resolved",
            package=package_name,
            version=version,
            total_nodes=len(graph.nodes),
        )
        return graph

    def check_conflicts(
        self,
        packages: list[tuple[str, str]],
        installed_packages: list[PackageInfo],
    ) -> list[Conflict]:
        """Check for version conflicts in a list of packages.

        Returns a list of Conflict objects (empty if no conflicts).
        """
        # Build a map: package_name -> list of (required_version, required_by)
        requirements: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for pkg_name, pkg_version in packages:
            requirements[pkg_name].append((pkg_version, "requested"))

        for pkg in installed_packages:
            requirements[pkg.name].append((pkg.version, "installed"))

        conflicts = []
        for pkg_name, reqs in requirements.items():
            versions = [r[0] for r in reqs]
            if len(set(versions)) > 1:
                # Check if any two versions are incompatible
                if not self._versions_compatible(versions):
                    conflicts.append(
                        Conflict(
                            package_name=pkg_name,
                            required_versions=versions,
                            required_by=[r[1] for r in reqs],
                        ),
                    )
        return conflicts

    def get_installation_order(self, dependency_graph: DependencyGraph) -> list[str]:
        """Compute topological sort of the dependency graph.

        Raises:
            CircularDependencyError: If cycle detected.

        """
        if dependency_graph.has_cycle():
            msg = "Dependency graph contains a cycle"
            raise CircularDependencyError(msg)
        return dependency_graph.topological_sort()

    def find_dependents(
        self,
        package_name: str,
        installed_packages: list[PackageInfo],
    ) -> list[str]:
        """Find all packages that depend on the given package.

        Returns list of dependent package names.
        """
        dependents: set[str] = set()
        for pkg in installed_packages:
            if package_name in pkg.dependencies:
                dependents.add(pkg.name)
                # Recursively find transitive dependents
                transitive = self.find_dependents(pkg.name, installed_packages)
                dependents.update(transitive)
        return list(dependents)

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_graph(
        self,
        package_name: str,
        version: str,
        installed_map: dict[str, str],
        available_packages: dict[str, list[str]],
        graph: DependencyGraph,
        visiting: set[str],
    ) -> None:
        """Recursively build the dependency graph using DFS."""
        if package_name in visiting:
            msg = f"Circular dependency detected: '{package_name}' is already being resolved"
            raise CircularDependencyError(
                msg,
            )
        if package_name in graph.nodes:
            return  # Already resolved

        visiting.add(package_name)
        node = PackageNode(name=package_name, version=version)
        graph.nodes[package_name] = node

        # Resolve dependencies from metadata (simplified: use installed_map)
        deps = self._get_package_deps(package_name, version, installed_map, available_packages)
        for dep_name, dep_version in deps:
            node.dependencies.append(dep_name)
            graph.edges.append((package_name, dep_name))
            self._build_graph(
                dep_name,
                dep_version,
                installed_map,
                available_packages,
                graph,
                visiting,
            )

        visiting.discard(package_name)

    def _get_package_deps(
        self,
        package_name: str,
        version: str,
        installed_map: dict[str, str],
        available_packages: dict[str, list[str]],
    ) -> list[tuple[str, str]]:
        """Get direct dependencies for a package.

        In production this would query PyPI metadata. Here we use
        available_packages as a mock dependency registry.
        """
        # available_packages can carry dep info as: {pkg: [version, "dep:other_pkg==1.0"]}
        deps = []
        pkg_info = available_packages.get(package_name, [])
        for entry in pkg_info:
            if entry.startswith("dep:"):
                dep_spec = entry[4:]
                try:
                    req = Requirement(dep_spec)
                    dep_name = req.name
                    # Resolve version: prefer installed, else first available
                    if dep_name in installed_map:
                        dep_version = installed_map[dep_name]
                    elif dep_name in available_packages:
                        candidates = [
                            v for v in available_packages[dep_name] if not v.startswith("dep:")
                        ]
                        dep_version = candidates[0] if candidates else "0.0.0"
                    else:
                        dep_version = "0.0.0"
                    deps.append((dep_name, dep_version))
                except (KeyError, ValueError):
                    logger.exception("Dependency resolution skipped for entry")
        return deps

    @staticmethod
    def _versions_compatible(versions: list[str]) -> bool:
        """Check if all versions in the list are the same (simple compatibility check)."""
        try:
            parsed = [Version(v) for v in versions]
            return len({str(v) for v in parsed}) <= 1
        except Exception:
            return len(set(versions)) <= 1
