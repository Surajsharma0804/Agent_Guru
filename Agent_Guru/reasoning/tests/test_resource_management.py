"""
Tests for resource management components.

Tests cover:
- Memory monitoring and limits
- Connection pooling (DB, Redis, HTTP)
- Request queue management
"""

import asyncio
import pytest
import time
from unittest.mock import patch

from Agent_Guru.reasoning.utils.memory_monitor import (
    MemoryMonitor,
    ComponentMemoryStats
)
from Agent_Guru.reasoning.utils.connection_pool import (
    DatabasePool,
    HTTPPool,
    get_http_pool
)
from Agent_Guru.reasoning.utils.request_queue import (
    RequestQueue,
    Priority,
    QueuedRequest
)


class TestMemoryMonitor:
    """Tests for MemoryMonitor."""
    
    def test_initialization(self):
        """Test monitor initialization."""
        monitor = MemoryMonitor(max_memory_mb=2048, check_interval=10.0)
        
        assert monitor.max_memory_mb == 2048  # nosec B101
        assert monitor.check_interval == 10.0  # nosec B101
        assert monitor.gc_threshold_percent == 0.8  # nosec B101
        assert len(monitor.component_stats) == 0  # nosec B101
    
    def test_track_component(self):
        """Test component memory tracking."""
        monitor = MemoryMonitor()
        
        monitor.track_component("test_component", 100.5)
        monitor.track_component("test_component", 150.0)
        
        stats = monitor.get_stats()
        assert "test_component" in stats  # nosec B101
        assert stats["test_component"].current_mb == 150.0  # nosec B101
        assert stats["test_component"].peak_mb == 150.0  # nosec B101
        assert stats["test_component"].samples == 2  # nosec B101
    
    def test_get_current_usage(self):
        """Test getting current memory usage."""
        monitor = MemoryMonitor()
        
        usage = monitor.get_current_usage()
        assert usage > 0  # Should have some memory usage  # nosec B101
        assert isinstance(usage, float)  # nosec B101
    
    def test_get_usage_percent(self):
        """Usage is reported as a percentage of the configured limit.
        
        This process's real memory use depends on what the run has already
        loaded - the full suite passes 1 GB once torch and the embedding
        model are in memory - so the arithmetic is checked against controlled
        usage rather than against whatever this process happens to hold.
        """
        monitor = MemoryMonitor(max_memory_mb=1000)
        
        with patch.object(monitor, "get_current_usage", return_value=250.0):
            assert monitor.get_usage_percent() == pytest.approx(25.0)  # nosec B101
        
        # Over the limit reads above 100%, consistent with is_over_limit()
        with patch.object(monitor, "get_current_usage", return_value=1500.0):
            assert monitor.get_usage_percent() == pytest.approx(150.0)  # nosec B101
            assert monitor.is_over_limit()  # nosec B101
        
        # The real measurement is a non-negative percentage
        assert monitor.get_usage_percent() >= 0  # nosec B101
    
    def test_is_over_limit(self):
        """Test limit checking."""
        monitor = MemoryMonitor(max_memory_mb=1.0)  # 1MB limit (will be over)
        
        # Should be over limit with normal program memory
        assert monitor.is_over_limit()  # nosec B101
    
    def test_get_summary(self):
        """Test getting summary."""
        monitor = MemoryMonitor()
        monitor.track_component("comp1", 50.0)
        monitor.track_component("comp2", 75.0)
        
        summary = monitor.get_summary()
        
        assert "current_mb" in summary  # nosec B101
        assert "max_mb" in summary  # nosec B101
        assert "percent" in summary  # nosec B101
        assert "components" in summary  # nosec B101
        assert len(summary["components"]) == 2  # nosec B101
    
    def test_start_stop(self):
        """Test starting and stopping monitor."""
        monitor = MemoryMonitor(check_interval=0.1)
        
        monitor.start()
        assert monitor._monitor_thread is not None  # nosec B101
        assert monitor._monitor_thread.is_alive()  # nosec B101
        
        time.sleep(0.2)  # Let it run a bit
        
        monitor.stop()
        assert not monitor._monitor_thread.is_alive()  # nosec B101
    
    def test_component_stats_update(self):
        """Test ComponentMemoryStats update."""
        stats = ComponentMemoryStats("test")
        
        stats.update(100.0)
        assert stats.current_mb == 100.0  # nosec B101
        assert stats.peak_mb == 100.0  # nosec B101
        assert stats.avg_mb == 100.0  # nosec B101
        assert stats.samples == 1  # nosec B101
        
        stats.update(150.0)
        assert stats.current_mb == 150.0  # nosec B101
        assert stats.peak_mb == 150.0  # nosec B101
        assert stats.avg_mb == 125.0  # nosec B101
        assert stats.samples == 2  # nosec B101


class TestDatabasePool:
    """Tests for DatabasePool."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test pool initialization."""
        pool = DatabasePool(":memory:", min_size=2, max_size=5)
        await pool.initialize()
        
        assert pool._initialized  # nosec B101
        assert len(pool._pool) == 2  # nosec B101
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_acquire_release(self):
        """Test acquiring and releasing connections."""
        pool = DatabasePool(":memory:", min_size=1, max_size=3)
        await pool.initialize()
        
        async with pool.acquire() as conn:
            assert conn is not None  # nosec B101
            # Connection should be in use
            assert conn in pool._in_use  # nosec B101
        
        # Connection should be back in pool
        assert conn not in pool._in_use  # nosec B101
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_multiple_acquires(self):
        """Test multiple concurrent acquires."""
        pool = DatabasePool(":memory:", min_size=2, max_size=5)
        await pool.initialize()
        
        async def use_connection():
            async with pool.acquire() as conn:
                await asyncio.sleep(0.01)
                return conn
        
        # Acquire multiple connections concurrently
        results = await asyncio.gather(*[use_connection() for _ in range(3)])
        
        assert len(results) == 3  # nosec B101
        assert all(r is not None for r in results)  # nosec B101
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_stats(self):
        """Test pool statistics."""
        pool = DatabasePool(":memory:", min_size=2, max_size=5)
        await pool.initialize()
        
        stats = pool.stats()
        
        assert stats['pool_size'] == 2  # nosec B101
        assert stats['in_use'] == 0  # nosec B101
        assert stats['max_size'] == 5  # nosec B101
        
        await pool.close()


class TestHTTPPool:
    """Tests for HTTPPool."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test HTTP pool initialization."""
        pool = HTTPPool(max_connections=50, max_connections_per_host=10)
        await pool.initialize()
        
        assert pool._initialized  # nosec B101
        assert pool._session is not None  # nosec B101
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_stats(self):
        """Test HTTP pool statistics."""
        pool = HTTPPool()
        await pool.initialize()
        
        stats = pool.stats()
        
        assert 'request_count' in stats  # nosec B101
        assert 'error_count' in stats  # nosec B101
        assert 'max_connections' in stats  # nosec B101
        
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_get_http_pool(self):
        """Test getting global HTTP pool."""
        pool = get_http_pool()
        await pool.initialize()
        
        assert pool is not None  # nosec B101
        assert pool._initialized  # nosec B101
        
        await pool.close()


class TestRequestQueue:
    """Tests for RequestQueue."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test queue initialization."""
        queue = RequestQueue(max_depth=100, worker_count=2)
        
        assert queue.max_depth == 100  # nosec B101
        assert queue.worker_count == 2  # nosec B101
        assert len(queue._queue) == 0  # nosec B101
    
    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self):
        """Test enqueuing and processing requests."""
        queue = RequestQueue(max_depth=10, worker_count=2)
        queue.start()
        
        async def test_handler(value):
            await asyncio.sleep(0.01)
            return value * 2
        
        result = await queue.enqueue(test_handler, Priority.NORMAL, 5)
        
        assert result == 10  # nosec B101
        
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that high priority requests are processed first."""
        queue = RequestQueue(max_depth=100, worker_count=1)
        queue.start()
        
        results = []
        
        async def test_handler(value):
            await asyncio.sleep(0.01)
            results.append(value)
            return value
        
        # Enqueue in reverse priority order
        tasks = [
            queue.enqueue(test_handler, Priority.LOW, 3),
            queue.enqueue(test_handler, Priority.NORMAL, 2),
            queue.enqueue(test_handler, Priority.HIGH, 1)
        ]
        
        await asyncio.gather(*tasks)
        
        # High priority should be processed first
        assert results[0] == 1  # nosec B101
        
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_queue_full(self):
        """Test queue overflow handling."""
        # Create queue with no workers to prevent processing
        queue = RequestQueue(max_depth=2, worker_count=0)
        # Don't start workers
        
        async def slow_handler():
            await asyncio.sleep(1.0)
            return "done"
        
        # Manually add requests to queue to fill it
        async with queue._queue_lock:
            for i in range(2):
                request = QueuedRequest(
                    priority=Priority.NORMAL.value,
                    timestamp=time.time(),
                    request_id=f"req_{i}",
                    handler=slow_handler,
                    args=(),
                    kwargs={},
                    future=asyncio.Future()
                )
                queue._queue.append(request)
        
        # Now queue should be full
        assert queue.is_full()  # nosec B101
        
        # This should fail (queue full)
        with pytest.raises(RuntimeError, match="queue full"):
            await queue.enqueue(slow_handler, Priority.NORMAL)
    
    @pytest.mark.asyncio
    async def test_backpressure(self):
        """Test backpressure on low priority requests."""
        queue = RequestQueue(max_depth=10, worker_count=1, backpressure_threshold=0.5)
        queue.start()
        
        async def slow_handler():
            await asyncio.sleep(1.0)
            return "done"
        
        # Fill queue to trigger backpressure (>50%)
        tasks = []
        for _ in range(6):
            task = asyncio.create_task(queue.enqueue(slow_handler, Priority.NORMAL))
            tasks.append(task)
        
        await asyncio.sleep(0.1)  # Let them enqueue
        
        # Low priority should be rejected
        with pytest.raises(RuntimeError, match="backpressure"):
            await queue.enqueue(slow_handler, Priority.LOW)
        
        # High priority should still work
        high_task = asyncio.create_task(queue.enqueue(slow_handler, Priority.HIGH))
        
        # Cancel all tasks
        for task in tasks + [high_task]:
            task.cancel()
        
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test request timeout."""
        queue = RequestQueue(max_depth=10, worker_count=1, timeout=0.1)
        queue.start()
        
        async def slow_handler():
            await asyncio.sleep(1.0)  # Longer than timeout
            return "done"
        
        with pytest.raises(TimeoutError):
            await queue.enqueue(slow_handler, Priority.NORMAL)
        
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_get_depth(self):
        """Test getting queue depth."""
        queue = RequestQueue(max_depth=10, worker_count=1)
        
        assert queue.get_depth() == 0  # nosec B101
        assert not queue.is_full()  # nosec B101
        assert not queue.is_under_pressure()  # nosec B101
    
    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Test getting queue metrics."""
        queue = RequestQueue(max_depth=10, worker_count=2)
        queue.start()
        
        async def test_handler(value):
            await asyncio.sleep(0.01)
            return value
        
        # Process some requests
        await queue.enqueue(test_handler, Priority.HIGH, 1)
        await queue.enqueue(test_handler, Priority.NORMAL, 2)
        await queue.enqueue(test_handler, Priority.LOW, 3)
        
        metrics = await queue.get_metrics()
        
        assert metrics.total_enqueued == 3  # nosec B101
        assert metrics.total_dequeued == 3  # nosec B101
        assert metrics.high_priority_count == 1  # nosec B101
        assert metrics.normal_priority_count == 1  # nosec B101
        assert metrics.low_priority_count == 1  # nosec B101
        
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_get_summary(self):
        """Test getting queue summary."""
        queue = RequestQueue(max_depth=100, worker_count=2)
        queue.start()
        
        summary = await queue.get_summary()
        
        assert "current_depth" in summary  # nosec B101
        assert "max_depth" in summary  # nosec B101
        assert "utilization_percent" in summary  # nosec B101
        assert "total_enqueued" in summary  # nosec B101
        assert "priority_distribution" in summary  # nosec B101
        
        await queue.stop()


class TestIntegration:
    """Integration tests for resource management."""
    
    @pytest.mark.asyncio
    async def test_memory_monitor_with_queue(self):
        """Test memory monitoring with request queue."""
        monitor = MemoryMonitor(check_interval=0.1)
        monitor.start()
        
        queue = RequestQueue(max_depth=10, worker_count=2)
        queue.start()
        
        async def test_handler(value):
            # Track memory explicitly
            current_mb = monitor.get_current_usage()
            monitor.track_component("test_handler", current_mb)
            await asyncio.sleep(0.01)
            return value * 2
        
        # Process some requests
        results = await asyncio.gather(*[
            queue.enqueue(test_handler, Priority.NORMAL, i)
            for i in range(5)
        ])
        
        assert len(results) == 5  # nosec B101
        
        # Check memory was tracked
        stats = monitor.get_stats()
        assert "test_handler" in stats  # nosec B101
        assert stats["test_handler"].samples >= 5  # nosec B101
        
        await queue.stop()
        monitor.stop()
    
    @pytest.mark.asyncio
    async def test_connection_pool_with_queue(self):
        """Test connection pooling with request queue."""
        db_pool = DatabasePool(":memory:", min_size=2, max_size=5)
        await db_pool.initialize()
        
        queue = RequestQueue(max_depth=10, worker_count=2)
        queue.start()
        
        async def db_operation(value):
            async with db_pool.acquire() as conn:
                cursor = conn.execute("SELECT ?", (value,))
                result = cursor.fetchone()
                return result[0]
        
        # Process database operations through queue
        results = await asyncio.gather(*[
            queue.enqueue(db_operation, Priority.NORMAL, i)
            for i in range(5)
        ])
        
        assert results == [0, 1, 2, 3, 4]  # nosec B101
        
        await queue.stop()
        await db_pool.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
