"""
Module: agent_guru.platform.network.connection_pool
Purpose: Advanced connection pooling with per-host limits and idle cleanup
Author: Agent Guru Team
Date: 2026-02-26

Performance Requirements:
- Time Complexity: O(1) for connection acquisition
- Space Complexity: O(n) where n is number of active connections
- Connection reuse: >95% for repeated requests to same host
- Idle cleanup: <1s overhead per cleanup cycle

Design Decisions:
- Per-host connection pools for isolation
- LRU eviction for idle connections
- Automatic cleanup of stale connections
- Connection statistics tracking
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import aiohttp

# Configure structured logging
logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolConfig:
    """Configuration for connection pool.
    
    Attributes:
        max_connections_per_host: Maximum connections per host (100 recommended)
        max_connections_total: Total maximum connections (1000 recommended)
        idle_timeout: Idle connection timeout in seconds (60s recommended)
        cleanup_interval: Cleanup interval in seconds (30s recommended)
        ttl_dns_cache: DNS cache TTL in seconds (300s recommended)
        enable_cleanup_closed: Whether to enable automatic cleanup of closed connections
    """
    
    max_connections_per_host: int = 100
    max_connections_total: int = 1000
    idle_timeout: float = 60.0
    cleanup_interval: float = 30.0
    ttl_dns_cache: int = 300
    enable_cleanup_closed: bool = True


@dataclass
class ConnectionStats:
    """Statistics for a connection pool.
    
    Attributes:
        host: Host name
        active_connections: Number of active connections
        idle_connections: Number of idle connections
        total_connections: Total connections created
        reused_connections: Number of connection reuses
        closed_connections: Number of connections closed
        last_activity: Last activity timestamp
        reuse_rate: Connection reuse rate (0.0-1.0)
    """
    
    host: str
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    reused_connections: int = 0
    closed_connections: int = 0
    last_activity: float = field(default_factory=time.time)
    
    @property
    def reuse_rate(self) -> float:
        """Calculate connection reuse rate.
        
        Returns:
            Reuse rate as percentage (0.0-1.0)
        """
        if self.total_connections == 0:
            return 0.0
        return self.reused_connections / self.total_connections


@dataclass
class PoolStatistics:
    """Overall connection pool statistics.
    
    Attributes:
        total_hosts: Number of hosts with connections
        total_active: Total active connections across all hosts
        total_idle: Total idle connections across all hosts
        total_created: Total connections created
        total_reused: Total connection reuses
        total_closed: Total connections closed
        average_reuse_rate: Average reuse rate across all hosts
        per_host_stats: Per-host connection statistics
    """
    
    total_hosts: int
    total_active: int
    total_idle: int
    total_created: int
    total_reused: int
    total_closed: int
    average_reuse_rate: float
    per_host_stats: Dict[str, ConnectionStats]


class ConnectionPoolManager:
    """Advanced connection pool manager with per-host limits.
    
    Time Complexity: O(1) for connection operations
    Space Complexity: O(n) where n is number of active connections
    
    Features:
    - Per-host connection pools
    - Pool size limit (100 connections per host)
    - Idle connection cleanup
    - Connection reuse tracking
    - Automatic stale connection removal
    
    Example:
        >>> config = ConnectionPoolConfig(max_connections_per_host=100)
        >>> pool_manager = ConnectionPoolManager(config)
        >>> connector = pool_manager.create_connector(ssl_context)
        >>> # Use connector with aiohttp.ClientSession
        >>> session = aiohttp.ClientSession(connector=connector)
    """
    
    def __init__(self, config: ConnectionPoolConfig) -> None:
        """Initialize connection pool manager.
        
        Args:
            config: Connection pool configuration
        """
        self.config = config
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        # Per-host statistics
        self._host_stats: Dict[str, ConnectionStats] = {}
        self._stats_lock = asyncio.Lock()
        
        logger.info(
            "ConnectionPoolManager initialized",
            extra={
                "max_per_host": config.max_connections_per_host,
                "max_total": config.max_connections_total,
                "idle_timeout": config.idle_timeout,
                "cleanup_interval": config.cleanup_interval,
            }
        )
    
    def create_connector(
        self,
        ssl_context: Optional[object] = None
    ) -> aiohttp.TCPConnector:
        """Create TCP connector with connection pooling.
        
        Args:
            ssl_context: SSL context for HTTPS connections
        
        Returns:
            Configured TCP connector
        
        Example:
            >>> import ssl
            >>> ssl_context = ssl.create_default_context()
            >>> connector = pool_manager.create_connector(ssl_context)
        """
        self._connector = aiohttp.TCPConnector(
            limit=self.config.max_connections_total,
            limit_per_host=self.config.max_connections_per_host,
            ttl_dns_cache=self.config.ttl_dns_cache,
            enable_cleanup_closed=self.config.enable_cleanup_closed,
            ssl=ssl_context,
            force_close=False,  # Enable connection reuse
            keepalive_timeout=self.config.idle_timeout,
        )
        
        logger.info("TCP connector created with connection pooling")
        return self._connector
    
    async def start_cleanup(self) -> None:
        """Start automatic cleanup of idle connections.
        
        Runs periodic cleanup task in background.
        
        Example:
            >>> await pool_manager.start_cleanup()
        """
        if self._is_running:
            logger.warning("Cleanup task already running")
            return
        
        self._is_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Connection cleanup task started")
    
    async def stop_cleanup(self) -> None:
        """Stop automatic cleanup task.
        
        Example:
            >>> await pool_manager.stop_cleanup()
        """
        if not self._is_running:
            return
        
        self._is_running = False
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        logger.info("Connection cleanup task stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background task for cleaning up idle connections.
        
        Runs every cleanup_interval seconds.
        """
        logger.info("Cleanup loop started")
        
        while self._is_running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Error in cleanup loop",
                    extra={"error": str(e)},
                    exc_info=True
                )
        
        logger.info("Cleanup loop stopped")
    
    async def _cleanup_idle_connections(self) -> None:
        """Clean up idle connections that exceed timeout.
        
        Time Complexity: O(1) - connector handles cleanup internally
        """
        if self._connector is None:
            return
        
        start_time = time.perf_counter()
        
        # Get connector statistics before cleanup
        before_stats = self._get_connector_stats()
        
        # Trigger connector cleanup (closes idle connections)
        # Note: aiohttp.TCPConnector handles this automatically via keepalive_timeout
        # We just need to track statistics
        
        # Get connector statistics after cleanup
        after_stats = self._get_connector_stats()
        
        cleanup_time = time.perf_counter() - start_time
        closed_count = before_stats.get('total', 0) - after_stats.get('total', 0)
        
        if closed_count > 0:
            logger.info(
                "Idle connections cleaned up",
                extra={
                    "closed_count": closed_count,
                    "cleanup_time": cleanup_time,
                    "remaining_connections": after_stats.get('total', 0),
                }
            )
    
    def _get_connector_stats(self) -> Dict[str, int]:
        """Get current connector statistics.
        
        Returns:
            Dictionary with connection counts
        """
        if self._connector is None:
            return {}
        
        # Access internal connector statistics
        # Note: This uses private API, may need adjustment for different aiohttp versions
        try:
            # Get connection counts from connector
            stats = {
                'total': len(self._connector._conns),  # Total connections
                'acquired': len(self._connector._acquired),  # Active connections
            }
            return stats
        except AttributeError:
            # Fallback if internal API changes
            return {}
    
    async def record_connection_activity(
        self,
        host: str,
        is_new: bool = False,
        is_reused: bool = False,
        is_closed: bool = False
    ) -> None:
        """Record connection activity for statistics.
        
        Args:
            host: Host name
            is_new: Whether this is a new connection
            is_reused: Whether this is a reused connection
            is_closed: Whether connection was closed
        
        Example:
            >>> await pool_manager.record_connection_activity(
            ...     "api.example.com",
            ...     is_new=True
            ... )
        """
        async with self._stats_lock:
            if host not in self._host_stats:
                self._host_stats[host] = ConnectionStats(host=host)
            
            stats = self._host_stats[host]
            stats.last_activity = time.time()
            
            if is_new:
                stats.total_connections += 1
                stats.active_connections += 1
            
            if is_reused:
                stats.reused_connections += 1
            
            if is_closed:
                stats.closed_connections += 1
                stats.active_connections = max(0, stats.active_connections - 1)
    
    async def get_host_stats(self, host: str) -> Optional[ConnectionStats]:
        """Get connection statistics for specific host.
        
        Args:
            host: Host name
        
        Returns:
            Connection statistics or None if host not found
        
        Example:
            >>> stats = await pool_manager.get_host_stats("api.example.com")
            >>> if stats:
            ...     print(f"Reuse rate: {stats.reuse_rate:.2%}")
        """
        async with self._stats_lock:
            return self._host_stats.get(host)
    
    async def get_all_stats(self) -> PoolStatistics:
        """Get overall connection pool statistics.
        
        Returns:
            Pool statistics
        
        Example:
            >>> stats = await pool_manager.get_all_stats()
            >>> print(f"Total hosts: {stats.total_hosts}")
            >>> print(f"Average reuse rate: {stats.average_reuse_rate:.2%}")
        """
        async with self._stats_lock:
            total_active = sum(s.active_connections for s in self._host_stats.values())
            total_idle = sum(s.idle_connections for s in self._host_stats.values())
            total_created = sum(s.total_connections for s in self._host_stats.values())
            total_reused = sum(s.reused_connections for s in self._host_stats.values())
            total_closed = sum(s.closed_connections for s in self._host_stats.values())
            
            # Calculate average reuse rate
            reuse_rates = [s.reuse_rate for s in self._host_stats.values() if s.total_connections > 0]
            avg_reuse_rate = sum(reuse_rates) / len(reuse_rates) if reuse_rates else 0.0
            
            return PoolStatistics(
                total_hosts=len(self._host_stats),
                total_active=total_active,
                total_idle=total_idle,
                total_created=total_created,
                total_reused=total_reused,
                total_closed=total_closed,
                average_reuse_rate=avg_reuse_rate,
                per_host_stats=self._host_stats.copy(),
            )
    
    async def reset_stats(self) -> None:
        """Reset all connection statistics.
        
        Example:
            >>> await pool_manager.reset_stats()
        """
        async with self._stats_lock:
            self._host_stats.clear()
        
        logger.info("Connection pool statistics reset")
    
    async def close(self) -> None:
        """Close connection pool and cleanup resources.
        
        Example:
            >>> await pool_manager.close()
        """
        await self.stop_cleanup()
        
        if self._connector is not None:
            await self._connector.close()
            self._connector = None
        
        logger.info("ConnectionPoolManager closed")
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.start_cleanup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
