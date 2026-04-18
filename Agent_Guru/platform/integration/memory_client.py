"""
Module: Agent_Guru.platform.integration.memory_client
Purpose: Memory System integration client for operation metadata storage.

Performance Requirements:
- Time Complexity: O(1) per store/query
- Latency: <50ms per operation (95th percentile)
- Throughput: >1000 operations/second with connection pooling

Design Decisions:
- Circuit breaker prevents cascade failures when Memory System is down
- Exponential backoff with jitter avoids thundering herd on recovery
- Bulk store API reduces round-trips for high-throughput scenarios
- asyncio.get_running_loop() used (Python 3.10+ safe, replaces deprecated get_event_loop)
- Connection pooling via aiohttp connector (100 connections, 10 per host)

Author: Agent Guru Platform Team
Date: 2026-03-16
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

import aiohttp

logger = logging.getLogger(__name__)


# ─── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class OperationMetadata:
    """
    Metadata for a platform operation to store in memory.

    Attributes:
        operation_id: Unique identifier for the operation
        operation_type: Category (file, command, network, etc.)
        timestamp: When the operation occurred
        parameters: Sanitized operation parameters (no secrets)
        result_summary: Human-readable result description
        tags: Searchable tags for filtering
        duration_ms: Operation duration in milliseconds
        success: Whether the operation succeeded
    """

    operation_id: str
    operation_type: str
    timestamp: datetime
    parameters: dict[str, Any] = field(default_factory=dict)
    result_summary: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    success: bool = True

    def __post_init__(self) -> None:
        if not self.operation_id:
            raise ValueError("operation_id cannot be empty")
        if not self.operation_type:
            raise ValueError("operation_type cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dictionary."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "timestamp": self.timestamp.isoformat(),
            "parameters": self.parameters,
            "result_summary": self.result_summary,
            "tags": self.tags,
            "duration_ms": self.duration_ms,
            "success": self.success,
        }


@dataclass
class MemoryQueryResult:
    """
    Result of a memory query.

    Attributes:
        query_id: Unique query identifier for tracing
        entries: Matching operation records
        total_count: Total matching records (may exceed len(entries) if paginated)
        query_time_ms: Server-side query execution time
        has_more: True if more pages are available
        next_cursor: Pagination cursor for next page
    """

    query_id: UUID = field(default_factory=uuid4)
    entries: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0
    has_more: bool = False
    next_cursor: Optional[str] = None


class CircuitState(Enum):
    """Circuit breaker state machine."""

    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast, not sending requests
    HALF_OPEN = "half_open"  # Testing if service recovered


# ─── Circuit Breaker ─────────────────────────────────────────────────────────


class CircuitBreaker:
    """
    Circuit breaker for Memory System calls.

    States:
        CLOSED  → normal, requests pass through
        OPEN    → failing fast after threshold failures
        HALF_OPEN → probe request to test recovery

    Time Complexity: O(1) per check
    Space Complexity: O(1)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        if success_threshold <= 0:
            raise ValueError("success_threshold must be positive")

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Current circuit state (auto-transitions OPEN→HALF_OPEN on timeout)."""
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
            logger.info("Circuit breaker transitioning OPEN → HALF_OPEN")
        return self._state

    def is_open(self) -> bool:
        """True if circuit is open (requests should be rejected)."""
        return self.state == CircuitState.OPEN

    def allow_request(self) -> bool:
        """True if a request should be allowed through."""
        s = self.state
        return s in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._opened_at = None
                logger.info("Circuit breaker CLOSED after recovery")
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.error(
                    f"Circuit breaker OPENED after {self._failure_count} failures"
                )

    def get_stats(self) -> dict[str, Any]:
        """Return circuit breaker statistics."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
        }


# ─── Client ──────────────────────────────────────────────────────────────────


class MemorySystemClient:
    """
    Production-grade async client for Memory System integration.

    Features:
    - Circuit breaker (5 failures → open, 60s recovery, 2 successes to close)
    - Exponential backoff with ±20% jitter on retries
    - Connection pooling (100 total, 10 per host)
    - Bulk store API for high-throughput scenarios
    - Paginated query with cursor support
    - Per-attempt timeout (not just total)
    - Full statistics for observability

    Time Complexity: O(1) per store/query
    Space Complexity: O(1) (no local buffering)

    Example:
        >>> async with MemorySystemClient(base_url="http://memory:8081") as client:
        ...     await client.store_operation(metadata)
        ...     results = await client.query_operations(operation_type="file")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8081",
        timeout: float = 30.0,
        per_attempt_timeout: float = 10.0,
        max_retries: int = 3,
        base_retry_delay: float = 0.5,
        max_retry_delay: float = 30.0,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 60.0,
        connection_limit: int = 100,
        connection_limit_per_host: int = 10,
    ) -> None:
        """
        Initialize Memory System client.

        Args:
            base_url: Memory System service base URL
            timeout: Total request timeout in seconds
            per_attempt_timeout: Per-attempt timeout (prevents single slow request blocking all retries)
            max_retries: Maximum retry attempts (0 = no retries)
            base_retry_delay: Initial retry delay in seconds (doubles each attempt)
            max_retry_delay: Maximum retry delay cap in seconds
            circuit_failure_threshold: Consecutive failures before circuit opens
            circuit_recovery_timeout: Seconds before circuit attempts recovery
            connection_limit: Total connection pool s
ize
            connection_limit_per_host: Per-host connection pool size

        Raises:
            ValueError: If any parameter is invalid
        """
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout}")
        if per_attempt_timeout <= 0:
            raise ValueError(f"per_attempt_timeout must be positive, got {per_attempt_timeout}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {max_retries}")
        if base_retry_delay <= 0:
            raise ValueError(f"base_retry_delay must be positive, got {base_retry_delay}")
        if connection_limit <= 0:
            raise ValueError(f"connection_limit must be positive, got {connection_limit}")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.per_attempt_timeout = per_attempt_timeout
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        self._connection_limit = connection_limit
        self._connection_limit_per_host = connection_limit_per_host

        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._circuit = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout,
        )

        # Statistics
        self._stored_count = 0
        self._query_count = 0
        self._retry_count = 0
        self._circuit_rejected_count = 0

    async def connect(self) -> None:
        """
        Establish connection pool to Memory System.

        Creates a shared TCPConnector with connection pooling for
        efficient reuse across requests.

        Raises:
            RuntimeError: If already connected
        """
        if self._session is not None:
            raise RuntimeError("Client already connected. Call disconnect() first.")

        self._connector = aiohttp.TCPConnector(
            limit=self._connection_limit,
            limit_per_host=self._connection_limit_per_host,
            enable_cleanup_closed=True,
            force_close=False,  # Keep-alive for connection reuse
        )
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=aiohttp.ClientTimeout(
                total=self.timeout,
                connect=5.0,
                sock_read=self.per_attempt_timeout,
            ),
            headers={"Content-Type": "application/json", "User-Agent": "AgentGuru-Platform/1.0"},
        )
        logger.info(
            f"Connected to Memory System at {self.base_url} "
            f"(pool: {self._connection_limit} total, {self._connection_limit_per_host}/host)"
        )

    async def disconnect(self) -> None:
        """
        Close connection pool and release all resources.

        Safe to call multiple times.
        """
        if self._session is not None:
            await self._session.close()
            self._session = None
        if self._connector is not None:
            await self._connector.close()
            self._connector = None
        logger.info("Disconnected from Memory System")

    # ─── Store Operations ─────────────────────────────────────────────────

    async def store_operation(self, metadata: OperationMetadata) -> bool:
        """
        Store a single operation metadata record.

        Uses circuit breaker + exponential backoff with jitter.

        Time Complexity: O(1)

        Args:
            metadata: Operation metadata to persist

        Returns:
            True if stored successfully

        Raises:
            RuntimeError: If not connected
        """
        return await self._store_batch([metadata])

    async def store_operations_bulk(
        self, metadata_list: list[OperationMetadata]
    ) -> int:
        """
        Bulk store multiple operation records in a single request.

        More efficient than individual store_operation calls for
        high-throughput scenarios.

        Time Complexity: O(n) where n = len(metadata_list)

        Args:
            metadata_list: List of operation metadata to store

        Returns:
            Number of records successfully stored

        Raises:
            RuntimeError: If not connected
            ValueError: If metadata_list is empty
        """
        if not metadata_list:
            raise ValueError("metadata_list cannot be empty")

        # Chunk into batches of 100 to avoid oversized payloads
        chunk_size = 100
        total_stored = 0
        for i in range(0, len(metadata_list), chunk_size):
            chunk = metadata_list[i : i + chunk_size]
            if await self._store_batch(chunk):
                total_stored += len(chunk)
        return total_stored

    async def _store_batch(self, batch: list[OperationMetadata]) -> bool:
        """Internal: store a batch with circuit breaker + retry."""
        self._require_connected()

        if not self._circuit.allow_request():
            self._circuit_rejected_count += 1
            logger.warning(
                f"Circuit breaker OPEN — rejecting store of {len(batch)} records"
            )
            return False

        url = f"{self.base_url}/api/v1/memory/operations"
        payload: dict[str, Any] = (
            {"operations": [m.to_dict() for m in batch]}
            if len(batch) > 1
            else batch[0].to_dict()
        )
        method = "POST"

        for attempt in range(self.max_retries + 1):
            try:
                async with self._session.request(  # type: ignore[union-attr]
                    method, url, json=payload
                ) as resp:
                    if resp.status in (200, 201):
                        self._circuit.record_success()
                        self._stored_count += len(batch)
                        logger.debug(
                            f"Stored {len(batch)} operation(s) "
                            f"[attempt {attempt + 1}]"
                        )
                        return True

                    if resp.status == 429:
                        # Rate limited — always retry with backoff
                        retry_after = float(resp.headers.get("Retry-After", 1.0))
                        logger.warning(
                            f"Memory System rate limited, retrying in {retry_after}s"
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500:
                        # Server error — retryable
                        body = await resp.text()
                        logger.warning(
                            f"Memory System server error {resp.status}: {body[:200]}"
                        )
                        self._circuit.record_failure()
                    else:
                        # 4xx client error — not retryable
                        body = await resp.text()
                        logger.error(
                            f"Memory System client error {resp.status}: {body[:200]}"
                        )
                        return False

            except asyncio.TimeoutError:
                logger.warning(
                    f"Memory System timeout on attempt {attempt + 1}/{self.max_retries + 1}"
                )
                self._circuit.record_failure()
            except aiohttp.ClientConnectionError as e:
                logger.warning(
                    f"Memory System connection error attempt {attempt + 1}: {e}"
                )
                self._circuit.record_failure()
            except Exception as e:
                logger.error("Unexpected error storing to Memory System: %s", e)
                self._circuit.record_failure()
                return False

            if attempt < self.max_retries:
                delay = self._backoff_delay(attempt)
                self._retry_count += 1
                logger.debug("Retrying in %.2fs (attempt %d)", delay, attempt + 2)
                await asyncio.sleep(delay)

        logger.error(
            f"Failed to store {len(batch)} record(s) after "
            f"{self.max_retries + 1} attempts"
        )
        return False

    # ─── Historical Data ──────────────────────────────────────────────────

    async def store_historical_data(
        self, data_type: str, data: dict[str, Any]
    ) -> bool:
        """
        Store arbitrary historical data (metrics, snapshots, etc.).

        Args:
            data_type: Category label for the data
            data: JSON-serializable data payload

        Returns:
            True if stored successfully

        Raises:
            RuntimeError: If not connected
            ValueError: If data_type is empty
        """
        if not data_type:
            raise ValueError("data_type cannot be empty")
        self._require_connected()

        if not self._circuit.allow_request():
            self._circuit_rejected_count += 1
            return False

        payload = {
            "data_type": data_type,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "data": data,
        }
        url = f"{self.base_url}/api/v1/memory/historical"

        for attempt in range(self.max_retries + 1):
            try:
                async with self._session.post(url, json=payload) as resp:  # type: ignore[union-attr]
                    if resp.status in (200, 201):
                        self._circuit.record_success()
                        self._stored_count += 1
                        return True
                    if resp.status >= 500:
                        self._circuit.record_failure()
                    else:
                        return False
            except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
                logger.warning("Historical store attempt %d failed: %s", attempt + 1, e)
                self._circuit.record_failure()
            except Exception as e:
                logger.error("Unexpected error storing historical data: %s", e)
                return False

            if attempt < self.max_retries:
                await asyncio.sleep(self._backoff_delay(attempt))

        return False

    # ─── Query Operations ─────────────────────────────────────────────────

    async def query_operations(
        self,
        operation_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[list[str]] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> MemoryQueryResult:
        """
        Query stored operations with filtering and pagination.

        Time Complexity: O(1) per call (server handles filtering)

        Args:
            operation_type: Filter by operation category
            start_time: Filter records after this time
            end_time: Filter records before this time
            tags: Filter records containing all specified tags
            success_only: If True, return only successful operations
            limit: Maximum records per page (1–1000)
            cursor: Pagination cursor from previous result's next_cursor

        Returns:
            MemoryQueryResult with entries and pagination info

        Raises:
            RuntimeError: If not connected
            ValueError: If limit is out of range
        """
        if not 1 <= limit <= 1000:
            raise ValueError(f"limit must be 1–1000, got {limit}")
        self._require_connected()

        if not self._circuit.allow_request():
            self._circuit_rejected_count += 1
            return MemoryQueryResult()

        params: dict[str, Any] = {"limit": limit}
        if operation_type:
            params["operation_type"] = operation_type
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if tags:
            params["tags"] = ",".join(tags)
        if success_only is not None:
            params["success_only"] = str(success_only).lower()
        if cursor:
            params["cursor"] = cursor

        t0 = time.monotonic()
        url = f"{self.base_url}/api/v1/memory/operations"

        try:
            async with self._session.get(url, params=params) as resp:  # type: ignore[union-attr]
                query_time_ms = (time.monotonic() - t0) * 1000
                self._query_count += 1

                if resp.status == 200:
                    body = await resp.json()
                    self._circuit.record_success()
                    return MemoryQueryResult(
                        entries=body.get("entries", []),
                        total_count=body.get("total_count", 0),
                        query_time_ms=query_time_ms,
                        has_more=body.get("has_more", False),
                        next_cursor=body.get("next_cursor"),
                    )

                logger.warning(
                    f"Memory query returned {resp.status} in {query_time_ms:.1f}ms"
                )
                self._circuit.record_failure()
                return MemoryQueryResult(query_time_ms=query_time_ms)

        except asyncio.TimeoutError:
            logger.warning("Memory query timed out")
            self._circuit.record_failure()
            return MemoryQueryResult()
        except Exception as e:
            logger.error("Memory query failed: %s", e)
            self._circuit.record_failure()
            return MemoryQueryResult()

    async def query_all_pages(
        self,
        operation_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_records: int = 10_000,
    ) -> list[dict[str, Any]]:
        """
        Fetch all pages of query results up to max_records.

        Args:
            operation_type: Filter by operation category
            start_time: Filter records after this time
            end_time: Filter records before this time
            max_records: Hard cap on total records returned

        Returns:
            All matching records across pages
        """
        all_entries: list[dict[str, Any]] = []
        cursor: Optional[str] = None

        while len(all_entries) < max_records:
            remaining = max_records - len(all_entries)
            page_limit = min(remaining, 1000)

            result = await self.query_operations(
                operation_type=operation_type,
                start_time=start_time,
                end_time=end_time,
                limit=page_limit,
                cursor=cursor,
            )
            all_entries.extend(result.entries)

            if not result.has_more or not result.next_cursor:
                break
            cursor = result.next_cursor

        return all_entries

    # ─── Health Check ─────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """
        Ping Memory System health endpoint.

        Returns:
            True if service is healthy
        """
        if self._session is None:
            return False
        try:
            async with self._session.get(
                f"{self.base_url}/health",
                timeout=aiohttp.ClientTimeout(total=5.0),
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    # ─── Observability ────────────────────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """
        Return client statistics for monitoring.

        Returns:
            Dict with stored_count, query_count, retry_count,
            circuit_rejected_count, and circuit breaker state.
        """
        return {
            "stored_count": self._stored_count,
            "query_count": self._query_count,
            "retry_count": self._retry_count,
            "circuit_rejected_count": self._circuit_rejected_count,
            "circuit_breaker": self._circuit.get_stats(),
            "connected": self._session is not None,
        }

    # ─── Internals ────────────────────────────────────────────────────────

    def _require_connected(self) -> None:
        """Raise RuntimeError if not connected."""
        if self._session is None:
            raise RuntimeError(
                "MemorySystemClient not connected. Call connect() or use as async context manager."
            )

    def _backoff_delay(self, attempt: int) -> float:
        """
        Compute exponential backoff delay with ±20% jitter.

        Time Complexity: O(1)

        Args:
            attempt: Zero-based attempt index

        Returns:
            Delay in seconds, capped at max_retry_delay
        """
        base = self.base_retry_delay * (2 ** attempt)
        capped = min(base, self.max_retry_delay)
        jitter = capped * 0.2 * (random.random() * 2 - 1)  # ±20%
        return max(0.0, capped + jitter)

    # ─── Context Manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "MemorySystemClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.disconnect()
        return False
