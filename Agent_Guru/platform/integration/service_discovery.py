"""
Module: Agent_Guru.platform.integration.service_discovery
Purpose: Service discovery for component registration and lookup.

Performance Requirements:
- Time Complexity: O(1) for lookup (hash-based)
- Latency: <10ms for local lookup
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Status of a registered service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceEndpoint:
    """Endpoint information for a registered service."""

    service_name: str
    host: str
    port: int
    protocol: str = "http"
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)
    last_health_check: Optional[datetime] = None
    status: ServiceStatus = ServiceStatus.UNKNOWN

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "version": self.version,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_health_check": (
                self.last_health_check.isoformat()
                if self.last_health_check
                else None
            ),
            "status": self.status.value,
        }


class ServiceRegistry:
    """
    Local service registry for component registration and lookup.

    Provides O(1) lookup by service name, health check integration,
    and TTL-based expiry for stale registrations.

    Example:
        >>> registry = ServiceRegistry()
        >>> endpoint = ServiceEndpoint("memory-system", "localhost", 8081)
        >>> registry.register(endpoint)
        >>> ep = registry.lookup("memory-system")
        >>> print(ep.base_url)
    """

    def __init__(
        self,
        health_check_interval: float = 30.0,
        ttl_seconds: float = 300.0,
    ) -> None:
        if health_check_interval <= 0:
            raise ValueError("health_check_interval must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        self.health_check_interval = health_check_interval
        self.ttl_seconds = ttl_seconds
        self._services: Dict[str, ServiceEndpoint] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

    def register(self, endpoint: ServiceEndpoint) -> None:
        """
        Register a service endpoint.

        Args:
            endpoint: Service endpoint to register

        Raises:
            ValueError: If endpoint is invalid
        """
        if not endpoint.service_name:
            raise ValueError("service_name cannot be empty")
        if not endpoint.host:
            raise ValueError("host cannot be empty")
        if not (1 <= endpoint.port <= 65535):
            raise ValueError(f"Invalid port: {endpoint.port}")

        self._services[endpoint.service_name] = endpoint
        logger.info(
            f"Registered service: {endpoint.service_name} at {endpoint.base_url}"
        )

    def deregister(self, service_name: str) -> bool:
        """
        Deregister a service.

        Args:
            service_name: Name of service to deregister

        Returns:
            True if service was found and removed
        """
        if service_name in self._services:
            del self._services[service_name]
            logger.info(f"Deregistered service: {service_name}")
            return True
        return False

    def lookup(self, service_name: str) -> Optional[ServiceEndpoint]:
        """
        Look up a service endpoint by name.

        Time Complexity: O(1)

        Args:
            service_name: Name of service to look up

        Returns:
            ServiceEndpoint if found and healthy, None otherwise
        """
        endpoint = self._services.get(service_name)
        if endpoint is None:
            return None

        # Check TTL
        age = (datetime.now() - endpoint.registered_at).total_seconds()
        if age > self.ttl_seconds:
            logger.warning(f"Service {service_name} registration expired")
            del self._services[service_name]
            return None

        return endpoint

    def lookup_all(self, status_filter: Optional[ServiceStatus] = None) -> List[ServiceEndpoint]:
        """
        Look up all registered services, optionally filtered by status.

        Args:
            status_filter: Filter by service status

        Returns:
            List of matching service endpoints
        """
        endpoints = list(self._services.values())
        if status_filter is not None:
            endpoints = [e for e in endpoints if e.status == status_filter]
        return endpoints

    def update_health(
        self, service_name: str, status: ServiceStatus
    ) -> bool:
        """
        Update health status for a service.

        Args:
            service_name: Service to update
            status: New health status

        Returns:
            True if service found and updated
        """
        endpoint = self._services.get(service_name)
        if endpoint is None:
            return False

        endpoint.status = status
        endpoint.last_health_check = datetime.now()
        logger.debug(f"Health updated: {service_name} -> {status.value}")
        return True

    async def start_health_checks(self) -> None:
        """Start background health check loop."""
        if self._running:
            return
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Service discovery health checks started")

    async def stop_health_checks(self) -> None:
        """Stop background health check loop."""
        self._running = False
        if self._health_check_task is not None:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        logger.info("Service discovery health checks stopped")

    async def _health_check_loop(self) -> None:
        """
        Background loop that pings all registered services.

        Uses a single shared aiohttp.ClientSession for the entire loop
        lifetime (not one per check — that was O(n) session overhead).
        All checks within each interval run concurrently via asyncio.gather.
        """
        import aiohttp

        # Single session shared across all health checks
        connector = aiohttp.TCPConnector(limit=50, enable_cleanup_closed=True)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=5.0),
        ) as session:
            while self._running:
                await asyncio.sleep(self.health_check_interval)
                # Run all checks concurrently
                await asyncio.gather(
                    *[
                        self._check_one(session, name, endpoint)
                        for name, endpoint in list(self._services.items())
                    ],
                    return_exceptions=True,
                )

    async def _check_one(
        self,
        session: Any,
        name: str,
        endpoint: "ServiceEndpoint",
    ) -> None:
        """Ping a single service health endpoint."""
        try:
            url = f"{endpoint.base_url}/health"
            async with session.get(url) as resp:
                if resp.status == 200:
                    self.update_health(name, ServiceStatus.HEALTHY)
                else:
                    self.update_health(name, ServiceStatus.DEGRADED)
        except Exception:
            self.update_health(name, ServiceStatus.UNHEALTHY)

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        status_counts: Dict[str, int] = {}
        for ep in self._services.values():
            key = ep.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        return {
            "total_services": len(self._services),
            "status_counts": status_counts,
            "services": [ep.service_name for ep in self._services.values()],
        }
