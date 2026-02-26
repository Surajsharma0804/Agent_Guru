"""
Module: Agent_Guru.platform.integration.goal_manager_client
Purpose: Goal Manager integration client for task completion notifications

This module provides async client for notifying Goal Manager about task
completions and operation results from the Platform Integration System.

Performance Requirements:
- Time Complexity: O(1) per notification
- Space Complexity: O(1) (no buffering)
- Latency: <100ms per notification (95th percentile)

Design Decisions:
- Async-first API for non-blocking notifications
- Retry logic with exponential backoff for transient failures
- Circuit breaker pattern for Goal Manager unavailability
- Structured notification format for consistency

Author: Agent Guru Platform Team
Date: 2026-02-26
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import aiohttp

logger = logging.getLogger(__name__)


class NotificationStatus(Enum):
    """Status of notification delivery."""
    
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class OperationStatus(Enum):
    """Status of platform operation."""
    
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass
class OperationResult:
    """
    Result of a platform operation.
    
    Attributes:
        operation_id: Unique operation identifier
        operation_type: Type of operation (file, command, network, etc.)
        status: Operation status
        start_time: Operation start timestamp
        end_time: Operation end timestamp
        execution_time: Execution time in seconds
        parameters: Operation parameters (sanitized)
        result_data: Operation result data
        error_message: Error message if failed
        resource_usage: Resource usage metrics
    """
    
    operation_id: str
    operation_type: str
    status: OperationStatus
    start_time: datetime
    end_time: datetime
    execution_time: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    resource_usage: Optional[Dict[str, float]] = None


@dataclass
class TaskCompletionNotification:
    """
    Notification for task completion.
    
    Attributes:
        notification_id: Unique notification identifier
        task_id: Task identifier from Goal Manager
        task_description: Human-readable task description
        completion_time: Task completion timestamp
        operations: List of operations performed
        overall_status: Overall task status
        metadata: Additional metadata
    """
    
    notification_id: UUID = field(default_factory=uuid4)
    task_id: str = ""
    task_description: str = ""
    completion_time: datetime = field(default_factory=datetime.now)
    operations: List[OperationResult] = field(default_factory=list)
    overall_status: OperationStatus = OperationStatus.SUCCESS
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary for serialization."""
        return {
            "notification_id": str(self.notification_id),
            "task_id": self.task_id,
            "task_description": self.task_description,
            "completion_time": self.completion_time.isoformat(),
            "operations": [
                {
                    "operation_id": op.operation_id,
                    "operation_type": op.operation_type,
                    "status": op.status.value,
                    "start_time": op.start_time.isoformat(),
                    "end_time": op.end_time.isoformat(),
                    "execution_time": op.execution_time,
                    "parameters": op.parameters,
                    "result_data": op.result_data,
                    "error_message": op.error_message,
                    "resource_usage": op.resource_usage,
                }
                for op in self.operations
            ],
            "overall_status": self.overall_status.value,
            "metadata": self.metadata,
        }


class GoalManagerClient:
    """
    Async client for Goal Manager integration.
    
    Provides:
    - Task completion notifications
    - Operation result reporting
    - Async notification support
    - Retry logic with exponential backoff
    - Circuit breaker for unavailability
    
    Time Complexity: O(1) per notification
    Space Complexity: O(1) (no buffering)
    
    Example:
        >>> client = GoalManagerClient(base_url="http://localhost:8080")
        >>> await client.connect()
        >>> 
        >>> notification = TaskCompletionNotification(
        ...     task_id="task-123",
        ...     task_description="Create user profile",
        ...     operations=[operation_result]
        ... )
        >>> await client.notify_task_completion(notification)
        >>> 
        >>> await client.disconnect()
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 60.0,
    ) -> None:
        """
        Initialize Goal Manager client.
        
        Args:
            base_url: Goal Manager service base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Initial retry delay in seconds (exponential backoff)
            circuit_breaker_threshold: Failures before circuit opens
            circuit_breaker_timeout: Circuit breaker timeout in seconds
        
        Raises:
            ValueError: If configuration parameters are invalid
        """
        self._validate_config(
            base_url, timeout, max_retries, retry_delay,
            circuit_breaker_threshold, circuit_breaker_timeout
        )
        
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Circuit breaker state
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_open_time: Optional[datetime] = None
        
        # Statistics
        self._notifications_sent = 0
        self._notifications_failed = 0
        self._total_retry_attempts = 0
    
    async def connect(self) -> None:
        """
        Establish connection to Goal Manager.
        
        Creates HTTP session for async requests.
        
        Raises:
            RuntimeError: If already connected
        """
        if self._session is not None:
            raise RuntimeError("Client already connected")
        
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        
        logger.info(f"Connected to Goal Manager at {self.base_url}")
    
    async def disconnect(self) -> None:
        """
        Disconnect from Goal Manager.
        
        Closes HTTP session and cleans up resources.
        """
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("Disconnected from Goal Manager")
    
    async def notify_task_completion(
        self,
        notification: TaskCompletionNotification
    ) -> NotificationStatus:
        """
        Notify Goal Manager of task completion.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            notification: Task completion notification
        
        Returns:
            Notification delivery status
        
        Raises:
            RuntimeError: If not connected
            CircuitBreakerOpenError: If circuit breaker is open
        """
        if self._session is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        # Check circuit breaker
        if self._circuit_open:
            if self._should_attempt_reset():
                logger.info("Circuit breaker attempting reset")
                self._circuit_open = False
                self._failure_count = 0
            else:
                logger.warning("Circuit breaker is open, failing fast")
                self._notifications_failed += 1
                return NotificationStatus.FAILED
        
        # Attempt notification with retries
        for attempt in range(self.max_retries):
            try:
                status = await self._send_notification(notification)
                
                if status == NotificationStatus.SENT:
                    self._on_success()
                    self._notifications_sent += 1
                    logger.info(
                        f"Task completion notification sent: {notification.task_id}"
                    )
                    return status
                
            except Exception as e:
                logger.warning(
                    f"Notification attempt {attempt + 1} failed: {e}"
                )
                self._total_retry_attempts += 1
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter
                    delay = self.retry_delay * (2 ** attempt)
                    jitter = delay * 0.2 * (2 * asyncio.get_event_loop().time() % 1 - 1)
                    await asyncio.sleep(delay + jitter)
        
        # All retries failed
        self._on_failure()
        self._notifications_failed += 1
        logger.error(
            f"Failed to send notification after {self.max_retries} attempts: "
            f"{notification.task_id}"
        )
        return NotificationStatus.FAILED
    
    async def report_operation_result(
        self,
        operation: OperationResult
    ) -> NotificationStatus:
        """
        Report individual operation result to Goal Manager.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            operation: Operation result to report
        
        Returns:
            Notification delivery status
        
        Raises:
            RuntimeError: If not connected
        """
        if self._session is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        # Create notification with single operation
        notification = TaskCompletionNotification(
            task_id=operation.operation_id,
            task_description=f"{operation.operation_type} operation",
            operations=[operation],
            overall_status=operation.status,
        )
        
        return await self.notify_task_completion(notification)
    
    async def _send_notification(
        self,
        notification: TaskCompletionNotification
    ) -> NotificationStatus:
        """
        Send notification to Goal Manager.
        
        Args:
            notification: Notification to send
        
        Returns:
            Notification status
        
        Raises:
            aiohttp.ClientError: If HTTP request fails
        """
        url = f"{self.base_url}/api/v1/notifications/task-completion"
        payload = notification.to_dict()
        
        async with self._session.post(url, json=payload) as response:
            if response.status == 200:
                return NotificationStatus.SENT
            elif response.status == 429:
                # Rate limited, should retry
                logger.warning("Goal Manager rate limit exceeded")
                return NotificationStatus.RETRYING
            else:
                # Other error
                error_text = await response.text()
                logger.error(
                    f"Goal Manager returned error {response.status}: {error_text}"
                )
                return NotificationStatus.FAILED
    
    def _on_success(self) -> None:
        """Handle successful notification."""
        self._failure_count = 0
    
    def _on_failure(self) -> None:
        """Handle failed notification."""
        self._failure_count += 1
        
        if self._failure_count >= self.circuit_breaker_threshold:
            self._circuit_open = True
            self._circuit_open_time = datetime.now()
            logger.error(
                f"Circuit breaker opened after {self._failure_count} failures"
            )
    
    def _should_attempt_reset(self) -> bool:
        """
        Check if circuit breaker should attempt reset.
        
        Returns:
            True if enough time has passed since circuit opened
        """
        if not self._circuit_open or self._circuit_open_time is None:
            return False
        
        elapsed = (datetime.now() - self._circuit_open_time).total_seconds()
        return elapsed >= self.circuit_breaker_timeout
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get client statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "notifications_sent": self._notifications_sent,
            "notifications_failed": self._notifications_failed,
            "total_retry_attempts": self._total_retry_attempts,
            "circuit_open": self._circuit_open,
            "failure_count": self._failure_count,
        }
    
    @staticmethod
    def _validate_config(
        base_url: str,
        timeout: float,
        max_retries: int,
        retry_delay: float,
        circuit_breaker_threshold: int,
        circuit_breaker_timeout: float,
    ) -> None:
        """
        Validate configuration parameters.
        
        Args:
            base_url: Goal Manager service base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay in seconds
            circuit_breaker_threshold: Failures before circuit opens
            circuit_breaker_timeout: Circuit breaker timeout in seconds
        
        Raises:
            ValueError: If any parameter is invalid
        """
        if not base_url:
            raise ValueError("base_url cannot be empty")
        
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout}")
        
        if max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {max_retries}")
        
        if retry_delay <= 0:
            raise ValueError(f"retry_delay must be positive, got {retry_delay}")
        
        if circuit_breaker_threshold <= 0:
            raise ValueError(
                f"circuit_breaker_threshold must be positive, "
                f"got {circuit_breaker_threshold}"
            )
        
        if circuit_breaker_timeout <= 0:
            raise ValueError(
                f"circuit_breaker_timeout must be positive, "
                f"got {circuit_breaker_timeout}"
            )
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
