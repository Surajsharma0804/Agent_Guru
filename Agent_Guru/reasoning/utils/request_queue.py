"""
Request queue management with priority levels and backpressure.

This module provides a priority-based request queue with overflow handling
to manage concurrent requests and prevent system overload.

Performance Requirements:
- Enqueue: O(log n) for priority queue
- Dequeue: O(log n) for priority queue
- Queue depth check: O(1)

Design:
- Priority-based queue (high, normal, low)
- Maximum depth limit (1000 requests)
- Backpressure when queue is full
- Metrics tracking (depth, wait time, throughput)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional
from collections import deque
import heapq

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Request priority levels."""
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True)
class QueuedRequest:
    """A request in the queue with priority."""
    
    priority: int = field(compare=True)
    timestamp: float = field(compare=True)
    request_id: str = field(compare=False)
    handler: Callable = field(compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    future: asyncio.Future = field(default_factory=asyncio.Future, compare=False)


@dataclass
class QueueMetrics:
    """Metrics for request queue."""
    
    total_enqueued: int = 0
    total_dequeued: int = 0
    total_rejected: int = 0
    total_timeouts: int = 0
    current_depth: int = 0
    peak_depth: int = 0
    avg_wait_time_ms: float = 0.0
    throughput_per_sec: float = 0.0
    
    # Per-priority metrics
    high_priority_count: int = 0
    normal_priority_count: int = 0
    low_priority_count: int = 0


class RequestQueue:
    """
    Priority-based request queue with backpressure and overflow handling.
    
    Features:
    - Three priority levels (high, normal, low)
    - Maximum queue depth (1000 default)
    - Backpressure when full (reject low priority)
    - Metrics tracking
    - Timeout support
    
    Time Complexity:
    - Enqueue: O(log n)
    - Dequeue: O(log n)
    - Check depth: O(1)
    
    Space Complexity: O(n) where n is queue depth
    
    Example:
        >>> queue = RequestQueue(max_depth=1000)
        >>> queue.start()
        >>> result = await queue.enqueue(handler, Priority.HIGH, arg1, arg2)
        >>> queue.stop()
    """
    
    def __init__(
        self,
        max_depth: int = 1000,
        worker_count: int = 10,
        timeout: float = 30.0,
        backpressure_threshold: float = 0.9  # 90% full
    ):
        """
        Initialize request queue.
        
        Args:
            max_depth: Maximum queue depth
            worker_count: Number of worker tasks
            timeout: Request timeout in seconds
            backpressure_threshold: Threshold to trigger backpressure (0-1)
        """
        self.max_depth = max_depth
        self.worker_count = worker_count
        self.timeout = timeout
        self.backpressure_threshold = backpressure_threshold
        
        # Priority queue (min-heap)
        self._queue: list[QueuedRequest] = []
        self._queue_lock = asyncio.Lock()
        
        # Wait times for metrics
        self._wait_times: deque = deque(maxlen=1000)
        
        # Metrics
        self.metrics = QueueMetrics()
        self._metrics_lock = asyncio.Lock()
        
        # Workers
        self._workers: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        
        # Request ID counter
        self._request_counter = 0
        
        logger.info(
            f"RequestQueue initialized: max_depth={max_depth}, "
            f"workers={worker_count}, timeout={timeout}s"
        )
    
    def start(self) -> None:
        """Start worker tasks."""
        if self._workers:
            logger.warning("Request queue already started")
            return
        
        self._stop_event.clear()
        
        for i in range(self.worker_count):
            worker = asyncio.create_task(
                self._worker_loop(i),
                name=f"RequestQueueWorker-{i}"
            )
            self._workers.append(worker)
        
        logger.info(f"Request queue started with {self.worker_count} workers")
    
    async def stop(self) -> None:
        """Stop worker tasks."""
        if not self._workers:
            return
        
        self._stop_event.set()
        
        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info("Request queue stopped")
    
    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop to process requests."""
        logger.info(f"Worker {worker_id} started")
        
        while not self._stop_event.is_set():
            try:
                # Get next request
                request = await self._dequeue()
                
                if request is None:
                    # No requests, wait a bit
                    await asyncio.sleep(0.01)
                    continue
                
                # Calculate wait time
                wait_time = time.time() - request.timestamp
                self._wait_times.append(wait_time)
                
                # Process request
                try:
                    result = await asyncio.wait_for(
                        request.handler(*request.args, **request.kwargs),
                        timeout=self.timeout
                    )
                    request.future.set_result(result)
                    
                except asyncio.TimeoutError:
                    async with self._metrics_lock:
                        self.metrics.total_timeouts += 1
                    request.future.set_exception(
                        TimeoutError(f"Request timed out after {self.timeout}s")
                    )
                    logger.warning(f"Request {request.request_id} timed out")
                    
                except Exception as e:
                    request.future.set_exception(e)
                    logger.error(f"Error processing request {request.request_id}: {e}")
                
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def enqueue(
        self,
        handler: Callable,
        priority: Priority = Priority.NORMAL,
        *args,
        **kwargs
    ) -> Any:
        """
        Enqueue a request for processing.
        
        Args:
            handler: Async function to execute
            priority: Request priority
            *args: Positional arguments for handler
            **kwargs: Keyword arguments for handler
            
        Returns:
            Result from handler
            
        Raises:
            RuntimeError: If queue is full and backpressure applied
            TimeoutError: If request times out
        """
        # Check if queue is full
        async with self._queue_lock:
            current_depth = len(self._queue)
            
            # Apply backpressure
            if current_depth >= self.max_depth:
                async with self._metrics_lock:
                    self.metrics.total_rejected += 1
                raise RuntimeError(
                    f"Request queue full ({current_depth}/{self.max_depth})"
                )
            
            # Reject low priority if approaching limit
            if (current_depth >= self.max_depth * self.backpressure_threshold and
                priority == Priority.LOW):
                async with self._metrics_lock:
                    self.metrics.total_rejected += 1
                raise RuntimeError(
                    f"Request queue under backpressure, rejecting low priority "
                    f"({current_depth}/{self.max_depth})"
                )
        
        # Create request
        self._request_counter += 1
        request = QueuedRequest(
            priority=priority.value,
            timestamp=time.time(),
            request_id=f"req_{self._request_counter}",
            handler=handler,
            args=args,
            kwargs=kwargs,
            future=asyncio.Future()
        )
        
        # Add to queue
        async with self._queue_lock:
            heapq.heappush(self._queue, request)
            
            # Update metrics
            async with self._metrics_lock:
                self.metrics.total_enqueued += 1
                self.metrics.current_depth = len(self._queue)
                self.metrics.peak_depth = max(
                    self.metrics.peak_depth,
                    self.metrics.current_depth
                )
                
                # Update priority counts
                if priority == Priority.HIGH:
                    self.metrics.high_priority_count += 1
                elif priority == Priority.NORMAL:
                    self.metrics.normal_priority_count += 1
                else:
                    self.metrics.low_priority_count += 1
        
        # Wait for result
        return await request.future
    
    async def _dequeue(self) -> Optional[QueuedRequest]:
        """
        Dequeue next request (highest priority first).
        
        Returns:
            Next request or None if queue is empty
        """
        async with self._queue_lock:
            if not self._queue:
                return None
            
            request = heapq.heappop(self._queue)
            
            # Update metrics
            async with self._metrics_lock:
                self.metrics.total_dequeued += 1
                self.metrics.current_depth = len(self._queue)
            
            return request
    
    def get_depth(self) -> int:
        """
        Get current queue depth.
        
        Returns:
            Number of requests in queue
        """
        return len(self._queue)
    
    def is_full(self) -> bool:
        """
        Check if queue is full.
        
        Returns:
            True if queue is at max depth
        """
        return len(self._queue) >= self.max_depth
    
    def is_under_pressure(self) -> bool:
        """
        Check if queue is under backpressure.
        
        Returns:
            True if queue depth exceeds backpressure threshold
        """
        return len(self._queue) >= self.max_depth * self.backpressure_threshold
    
    async def get_metrics(self) -> QueueMetrics:
        """
        Get queue metrics.
        
        Returns:
            Current queue metrics
        """
        async with self._metrics_lock:
            # Calculate average wait time
            if self._wait_times:
                self.metrics.avg_wait_time_ms = (
                    sum(self._wait_times) / len(self._wait_times) * 1000
                )
            
            # Calculate throughput
            if self.metrics.total_dequeued > 0:
                # Rough estimate based on recent activity
                self.metrics.throughput_per_sec = (
                    len(self._wait_times) / max(1, len(self._wait_times) * 0.1)
                )
            
            return QueueMetrics(**self.metrics.__dict__)
    
    async def get_summary(self) -> Dict:
        """
        Get summary of queue status.
        
        Returns:
            Dictionary with queue summary
        """
        metrics = await self.get_metrics()
        
        return {
            "current_depth": metrics.current_depth,
            "max_depth": self.max_depth,
            "utilization_percent": (metrics.current_depth / self.max_depth) * 100,
            "is_full": self.is_full(),
            "is_under_pressure": self.is_under_pressure(),
            "total_enqueued": metrics.total_enqueued,
            "total_dequeued": metrics.total_dequeued,
            "total_rejected": metrics.total_rejected,
            "total_timeouts": metrics.total_timeouts,
            "peak_depth": metrics.peak_depth,
            "avg_wait_time_ms": metrics.avg_wait_time_ms,
            "throughput_per_sec": metrics.throughput_per_sec,
            "priority_distribution": {
                "high": metrics.high_priority_count,
                "normal": metrics.normal_priority_count,
                "low": metrics.low_priority_count
            },
            "worker_count": self.worker_count
        }


# Global request queue instance
_global_queue: Optional[RequestQueue] = None


def get_request_queue(
    max_depth: int = 1000,
    worker_count: int = 10
) -> RequestQueue:
    """
    Get global request queue instance.
    
    Args:
        max_depth: Maximum queue depth
        worker_count: Number of worker tasks
        
    Returns:
        Global RequestQueue instance
    """
    global _global_queue
    if _global_queue is None:
        _global_queue = RequestQueue(max_depth, worker_count)
        _global_queue.start()
    return _global_queue


async def enqueue_request(
    handler: Callable,
    priority: Priority = Priority.NORMAL,
    *args,
    **kwargs
) -> Any:
    """
    Enqueue a request (convenience function).
    
    Args:
        handler: Async function to execute
        priority: Request priority
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Result from handler
    """
    queue = get_request_queue()
    return await queue.enqueue(handler, priority, *args, **kwargs)
