"""
Batch processing utilities for improved throughput.

Batch processing groups multiple operations together to reduce overhead
and improve throughput by 2-5x.

Performance Impact:
    Individual operations: 100 ops/sec
    Batched operations: 200-500 ops/sec (2-5x faster)

Usage:
    from Agent_Guru.reasoning.utils.batch_processor import BatchProcessor

    processor = BatchProcessor(batch_size=32, max_wait=0.1)

    async def process_batch(items):
        # Process all items together
        return [result for item in items]

    processor.set_handler(process_batch)

    # Submit items (automatically batched)
    result = await processor.submit(item)
"""

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class BatchItem(Generic[T, R]):
    """
    Item in a batch with its result future.

    Attributes:
        data: The item data
        future: Future for the result
        timestamp: When the item was added
    """
    data: T
    future: asyncio.Future[R]
    timestamp: float


class BatchProcessor(Generic[T, R]):
    """
    Batch processor for grouping operations.

    Features:
    - Automatic batching based on size or time
    - Async processing with futures
    - Error handling per item
    - Throughput metrics

    Performance:
    - Reduces overhead by processing multiple items together
    - Improves GPU utilization (for ML models)
    - Reduces database round-trips
    - Improves network efficiency

    Example:
        >>> processor = BatchProcessor(batch_size=32, max_wait=0.1)
        >>>
        >>> async def process_batch(items):
        ...     # Process all items together (e.g., GPU inference)
        ...     return [model.predict(item) for item in items]
        >>>
        >>> processor.set_handler(process_batch)
        >>>
        >>> # Submit items (automatically batched)
        >>> results = await asyncio.gather(*[
        ...     processor.submit(item) for item in items
        ... ])
    """

    def __init__(
        self,
        batch_size: int = 32,
        max_wait: float = 0.1,
        max_queue_size: int = 1000
    ):
        """
        Initialize batch processor.

        Args:
            batch_size: Maximum items per batch
            max_wait: Maximum wait time before processing (seconds)
            max_queue_size: Maximum queue size (backpressure)
        """
        self.batch_size = batch_size
        self.max_wait = max_wait
        self.max_queue_size = max_queue_size

        self._queue: deque[BatchItem[T, R]] = deque()
        self._handler: Optional[Callable[[list[T]], Awaitable[list[R]]]] = None
        self._lock = asyncio.Lock()
        self._processing = False
        self._task: Optional[asyncio.Task[None]] = None

        # Metrics
        self._total_items = 0
        self._total_batches = 0
        self._total_time = 0.0

    def set_handler(self, handler: Callable[[list[T]], Awaitable[list[R]]]) -> None:
        """
        Set the batch processing handler.

        Args:
            handler: Async function that processes a batch of items
                    and returns a list of results
        """
        self._handler = handler

    async def submit(self, item: T) -> R:
        """
        Submit an item for batch processing.

        Args:
            item: Item to process

        Returns:
            Processing result

        Raises:
            RuntimeError: If handler not set
            asyncio.QueueFull: If queue is full
        """
        if self._handler is None:
            raise RuntimeError("Handler not set. Call set_handler() first.")

        # Check queue size (backpressure)
        if len(self._queue) >= self.max_queue_size:
            raise asyncio.QueueFull(f"Queue full ({self.max_queue_size} items)")

        # Create future for result
        future: asyncio.Future[R] = asyncio.Future()

        # Add to queue
        async with self._lock:
            self._queue.append(BatchItem(
                data=item,
                future=future,
                timestamp=time.perf_counter()
            ))
            self._total_items += 1

        # Start processing task if not running
        if not self._processing:
            self._task = asyncio.create_task(self._process_loop())

        # Wait for result
        return await future

    async def _process_loop(self):
        """Background loop for processing batches."""
        self._processing = True

        try:
            while True:
                # Wait for items or timeout
                await asyncio.sleep(0.001)  # 1ms

                # Check if we should process
                should_process = False

                async with self._lock:
                    if not self._queue:
                        # No items, stop loop
                        break

                    # Check batch size
                    if len(self._queue) >= self.batch_size:
                        should_process = True

                    # Check max wait time
                    elif self._queue:
                        oldest = self._queue[0]
                        if time.perf_counter() - oldest.timestamp >= self.max_wait:
                            should_process = True

                if should_process:
                    await self._process_batch()

        finally:
            self._processing = False

    async def _process_batch(self):
        """Process a batch of items."""
        # Extract batch
        batch: list[BatchItem[T, R]] = []

        async with self._lock:
            while self._queue and len(batch) < self.batch_size:
                batch.append(self._queue.popleft())

        if not batch:
            return

        # Process batch
        start_time = time.perf_counter()

        try:
            # Extract data
            items = [item.data for item in batch]

            # Call handler
            if self._handler is not None:
                results = await self._handler(items)
            else:
                raise RuntimeError("Handler not set")

            # Set results
            if len(results) != len(batch):
                raise ValueError(
                    f"Handler returned {len(results)} results for {len(batch)} items"
                )

            for item, result in zip(batch, results):
                if not item.future.done():
                    item.future.set_result(result)

        except Exception as e:
            # Set exception for all items
            logger.error(f"Batch processing failed: {e}")
            for item in batch:
                if not item.future.done():
                    item.future.set_exception(e)

        finally:
            # Update metrics
            elapsed = time.perf_counter() - start_time
            self._total_batches += 1
            self._total_time += elapsed

            logger.debug(
                f"Processed batch: {len(batch)} items in {elapsed*1000:.1f}ms "
                f"({len(batch)/elapsed:.0f} items/sec)"
            )

    async def flush(self):
        """Process all remaining items in queue."""
        while self._queue:
            await self._process_batch()

    def stats(self) -> dict:
        """Get processing statistics."""
        avg_batch_size = self._total_items / self._total_batches if self._total_batches > 0 else 0
        avg_time = self._total_time / self._total_batches if self._total_batches > 0 else 0
        throughput = self._total_items / self._total_time if self._total_time > 0 else 0

        return {
            'total_items': self._total_items,
            'total_batches': self._total_batches,
            'total_time': self._total_time,
            'avg_batch_size': avg_batch_size,
            'avg_batch_time': avg_time,
            'throughput': throughput,
            'queue_size': len(self._queue)
        }


class DatabaseBatchWriter:
    """
    Batch writer for database operations.

    Groups multiple INSERT/UPDATE operations into a single transaction
    for 5-10x performance improvement.

    Example:
        >>> writer = DatabaseBatchWriter(conn, batch_size=100)
        >>>
        >>> for item in items:
        ...     await writer.insert("table", {"col": item})
        >>>
        >>> await writer.flush()  # Commit remaining items
    """

    def __init__(
        self,
        connection: Any,
        batch_size: int = 100,
        max_wait: float = 1.0
    ):
        """
        Initialize database batch writer.

        Args:
            connection: Database connection
            batch_size: Items per batch
            max_wait: Maximum wait before commit (seconds)
        """
        self.connection = connection
        self.batch_size = batch_size
        self.max_wait = max_wait

        self._operations: list[tuple[str, dict]] = []
        self._last_commit = time.perf_counter()
        self._lock = asyncio.Lock()

    async def insert(self, table: str, data: dict):
        """
        Queue an INSERT operation.

        Args:
            table: Table name
            data: Column-value mapping
        """
        async with self._lock:
            self._operations.append(('INSERT', {'table': table, 'data': data}))

            if len(self._operations) >= self.batch_size:
                await self._flush_internal()
            elif time.perf_counter() - self._last_commit >= self.max_wait:
                await self._flush_internal()

    async def _flush_internal(self):
        """Flush operations to database."""
        if not self._operations:
            return

        # Group by table
        by_table: dict[str, list[dict]] = {}
        for op_type, op_data in self._operations:
            if op_type == 'INSERT':
                table = op_data['table']
                if table not in by_table:
                    by_table[table] = []
                by_table[table].append(op_data['data'])

        # Execute batch inserts
        for table, rows in by_table.items():
            if not rows:
                continue

            # Validate table name — must be a simple identifier (letters, digits, underscores)
            if not table.replace("_", "").isalnum():
                raise ValueError(f"Invalid table name: {table!r}")

            # Build batch INSERT — table name is validated above; values are parameterized
            columns = list(rows[0].keys())
            # Validate column names as well
            for col in columns:
                if not col.replace("_", "").isalnum():
                    raise ValueError(f"Invalid column name: {col!r}")

            col_list = ", ".join(columns)
            row_placeholders = "(" + ", ".join("?" * len(columns)) + ")"
            all_placeholders = ", ".join([row_placeholders] * len(rows))
            values: list[Any] = []
            for row in rows:
                values.extend(row[col] for col in columns)

            # Table and column names are validated identifiers; values are parameterized
            query = "INSERT INTO " + table + " (" + col_list + ") VALUES " + all_placeholders  # nosec B608

            # Execute
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.connection.execute(query, values)
            )

        # Commit
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.connection.commit)

        self._operations.clear()
        self._last_commit = time.perf_counter()

    async def flush(self):
        """Flush all pending operations."""
        async with self._lock:
            await self._flush_internal()


if __name__ == "__main__":
    # Example usage and benchmarking
    async def benchmark_batch_processing():
        """Benchmark batch processing performance."""
        print("Batch Processing Performance Benchmark")
        print("=" * 80)

        # Simulate processing function
        async def process_batch(items: list[int]) -> list[int]:
            # Simulate some processing time
            await asyncio.sleep(0.01)  # 10ms per batch
            return [item * 2 for item in items]

        # Test without batching
        print("\nWithout batching:")
        start = time.perf_counter()
        results = []
        for i in range(100):
            await asyncio.sleep(0.01)  # 10ms per item
            results.append(i * 2)
        no_batch_time = time.perf_counter() - start
        print(f"  Time: {no_batch_time*1000:.1f}ms")
        print(f"  Throughput: {100/no_batch_time:.0f} items/sec")

        # Test with batching
        print("\nWith batching (batch_size=10):")
        processor: BatchProcessor[int, int] = BatchProcessor(batch_size=10, max_wait=0.1)
        processor.set_handler(process_batch)

        start = time.perf_counter()
        results = await asyncio.gather(*[
            processor.submit(i) for i in range(100)
        ])
        batch_time = time.perf_counter() - start

        print(f"  Time: {batch_time*1000:.1f}ms")
        print(f"  Throughput: {100/batch_time:.0f} items/sec")
        print(f"  Speedup: {no_batch_time/batch_time:.1f}x faster")
        print(f"  Stats: {processor.stats()}")

    asyncio.run(benchmark_batch_processing())
