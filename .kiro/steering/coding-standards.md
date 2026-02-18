# Agent Guru - Coding Standards (World-Class Performance)

## Mission: Optimal Code, Zero Waste, Maximum Performance

Every line of code must be optimized for performance, maintainability, and scalability. No duplication, no inefficiencies, no compromises.

## Algorithm Complexity Standards (Non-Negotiable)

### Time Complexity Requirements

| Operation Type | Maximum Allowed | Optimal Target | Examples |
|----------------|-----------------|----------------|----------|
| Lookup/Search | O(log n) | O(1) | Hash tables, indexed access |
| Insert/Delete | O(log n) | O(1) amortized | Hash tables, dynamic arrays |
| Sort | O(n log n) | O(n log n) | Timsort, merge sort |
| Iteration | O(n) | O(n) | Single pass algorithms |
| Graph traversal | O(V + E) | O(V + E) | BFS, DFS |
| String matching | O(n + m) | O(n) | KMP, Boyer-Moore |

**FORBIDDEN**: O(n²), O(n³), O(2ⁿ) algorithms in production code
- Exception: Only if n < 100 and proven necessary
- Must document why and provide optimization plan

### Space Complexity Requirements

| Data Structure | Maximum Allowed | Optimal Target | Use Case |
|----------------|-----------------|----------------|----------|
| Cache/Index | O(n) | O(n) | Fast lookups |
| Temporary storage | O(log n) | O(1) | Sorting, recursion |
| Streaming data | O(1) | O(1) | Audio/video processing |
| Graph storage | O(V + E) | O(V + E) | Knowledge graphs |

**FORBIDDEN**: Unnecessary memory allocation, memory leaks, unbounded growth
- All data structures must have maximum size limits
- Memory must be released immediately after use
- Use generators/iterators for large datasets

### Performance Benchmarks (Must Meet)

```python
# Example: Wake word detection must be O(1) per audio frame
# Bad: O(n) - scanning entire buffer
def detect_wake_word_bad(audio_buffer: np.ndarray) -> bool:
    for i in range(len(audio_buffer)):  # O(n) - FORBIDDEN
        if matches_pattern(audio_buffer[i:i+window_size]):
            return True
    return False

# Good: O(1) - sliding window with constant-time checks
def detect_wake_word_optimal(audio_frame: np.ndarray, state: WakeWordState) -> bool:
    state.update(audio_frame)  # O(1) - update rolling buffer
    return state.check_pattern()  # O(1) - constant-time pattern match
```

## Code Duplication Standards (Zero Tolerance)

### DRY Principle (Don't Repeat Yourself)

**Rule**: No code duplication >3 lines
- Use functions for repeated logic
- Use classes for repeated patterns
- Use decorators for repeated behavior
- Use mixins for repeated functionality

### Duplication Detection

```bash
# Run duplication detection (must be <3%)
pylint --disable=all --enable=duplicate-code Agent_Guru/

# Automated check in CI/CD
# Fails build if duplication >3%
```

### Refactoring Patterns

```python
# Bad: Duplicated validation logic
def process_speech_input(audio: bytes) -> str:
    if not audio:
        raise ValueError("Audio cannot be empty")
    if len(audio) < MIN_AUDIO_LENGTH:
        raise ValueError("Audio too short")
    # ... processing

def process_vision_input(image: bytes) -> np.ndarray:
    if not image:
        raise ValueError("Image cannot be empty")
    if len(image) < MIN_IMAGE_SIZE:
        raise ValueError("Image too small")
    # ... processing

# Good: Shared validation with generic function
def validate_input(data: bytes, min_size: int, data_type: str) -> None:
    if not data:
        raise ValueError(f"{data_type} cannot be empty")
    if len(data) < min_size:
        raise ValueError(f"{data_type} too small (min: {min_size})")

def process_speech_input(audio: bytes) -> str:
    validate_input(audio, MIN_AUDIO_LENGTH, "Audio")
    # ... processing

def process_vision_input(image: bytes) -> np.ndarray:
    validate_input(image, MIN_IMAGE_SIZE, "Image")
    # ... processing
```

## Data Structure Selection (Optimal Choices)

### When to Use Each Data Structure

| Data Structure | Time Complexity | Space | Use When |
|----------------|-----------------|-------|----------|
| **dict** | O(1) avg lookup | O(n) | Fast key-value lookups, caching |
| **set** | O(1) avg lookup | O(n) | Membership testing, deduplication |
| **list** | O(1) append, O(n) search | O(n) | Ordered sequences, stacks |
| **deque** | O(1) both ends | O(n) | Queues, sliding windows |
| **heapq** | O(log n) insert/pop | O(n) | Priority queues, top-k elements |
| **bisect** | O(log n) search | O(n) | Sorted sequences, binary search |
| **array.array** | O(1) access | O(n) | Numeric data, memory efficiency |
| **numpy.ndarray** | O(1) access | O(n) | Vectorized operations, ML |

### Anti-Patterns (FORBIDDEN)

```python
# Bad: O(n) membership testing with list
if item in my_list:  # O(n) - SLOW
    process(item)

# Good: O(1) membership testing with set
if item in my_set:  # O(1) - FAST
    process(item)

# Bad: O(n²) nested loops for matching
for item1 in list1:  # O(n)
    for item2 in list2:  # O(n)
        if item1 == item2:  # O(n²) total - FORBIDDEN
            process(item1, item2)

# Good: O(n) with set intersection
set1 = set(list1)  # O(n)
set2 = set(list2)  # O(n)
for item in set1 & set2:  # O(n) total - OPTIMAL
    process(item)
```

## Memory Management (Zero Leaks)

### Memory Allocation Rules

1. **Preallocate**: Allocate memory once, reuse
2. **Pool**: Use object pools for frequent allocations
3. **Stream**: Process data in chunks, not all at once
4. **Release**: Explicitly release large objects
5. **Monitor**: Track memory usage in production

### Memory Optimization Patterns

```python
# Bad: Creating new arrays in loop (memory thrashing)
def process_audio_frames_bad(audio_stream: Iterator[bytes]) -> List[np.ndarray]:
    results = []
    for frame in audio_stream:
        # Creates new array every iteration - SLOW
        processed = np.array(frame, dtype=np.float32)
        results.append(processed)
    return results

# Good: Preallocated buffer, in-place operations
def process_audio_frames_optimal(
    audio_stream: Iterator[bytes],
    buffer: np.ndarray
) -> Iterator[np.ndarray]:
    for frame in audio_stream:
        # Reuse preallocated buffer - FAST
        np.copyto(buffer, frame)
        yield buffer  # Generator - memory efficient
```

### Memory Profiling (Mandatory)

```python
# Use memory_profiler for critical paths
from memory_profiler import profile

@profile
def critical_function():
    # Memory usage tracked line-by-line
    pass

# Run profiling
python -m memory_profiler script.py
```

## Caching Strategies (Intelligent Caching)

### Cache Levels

1. **L1 Cache**: In-memory dict (fastest, limited size)
2. **L2 Cache**: Redis (fast, larger size)
3. **L3 Cache**: Disk (slower, unlimited size)

### Caching Patterns

```python
from functools import lru_cache
from typing import Tuple
import hashlib

# Pattern 1: LRU Cache for pure functions
@lru_cache(maxsize=1024)
def compute_embedding(text: str) -> np.ndarray:
    # Expensive computation cached
    return model.encode(text)

# Pattern 2: Custom cache with TTL
class TTLCache:
    def __init__(self, maxsize: int, ttl: float):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.maxsize = maxsize
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if len(self.cache) >= self.maxsize:
            # Evict oldest entry
            oldest = min(self.cache.items(), key=lambda x: x[1][1])
            del self.cache[oldest[0]]
        self.cache[key] = (value, time.time())

# Pattern 3: Memoization with hash-based keys
def memoize_with_hash(func):
    cache = {}

    def wrapper(*args, **kwargs):
        # Create hash of arguments
        key = hashlib.sha256(
            str((args, sorted(kwargs.items()))).encode()
        ).hexdigest()

        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return wrapper
```

### Cache Invalidation (Critical)

```python
# Pattern: Cache with dependency tracking
class DependencyCache:
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.dependencies: Dict[str, Set[str]] = {}

    def get(self, key: str) -> Optional[Any]:
        return self.cache.get(key)

    def set(self, key: str, value: Any, depends_on: Set[str]) -> None:
        self.cache[key] = value
        self.dependencies[key] = depends_on

    def invalidate(self, key: str) -> None:
        # Invalidate key and all dependents
        to_invalidate = {key}
        for cached_key, deps in self.dependencies.items():
            if key in deps:
                to_invalidate.add(cached_key)

        for k in to_invalidate:
            self.cache.pop(k, None)
            self.dependencies.pop(k, None)
```

## Async/Await Patterns (Maximum Concurrency)

### Async Best Practices

```python
import asyncio
from typing import List, Coroutine

# Pattern 1: Concurrent execution with gather
async def process_multiple_requests(requests: List[str]) -> List[str]:
    # Execute all requests concurrently - FAST
    tasks = [process_request(req) for req in requests]
    return await asyncio.gather(*tasks)

# Pattern 2: Streaming with async generators
async def stream_audio_processing(
    audio_stream: AsyncIterator[bytes]
) -> AsyncIterator[str]:
    async for frame in audio_stream:
        # Process and yield immediately - LOW LATENCY
        result = await process_frame(frame)
        yield result

# Pattern 3: Timeout and cancellation
async def process_with_timeout(data: bytes, timeout: float) -> str:
    try:
        return await asyncio.wait_for(
            process_data(data),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        # Graceful timeout handling
        return "TIMEOUT"

# Pattern 4: Semaphore for rate limiting
class RateLimiter:
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, coro: Coroutine) -> Any:
        async with self.semaphore:
            return await coro

# Usage
limiter = RateLimiter(max_concurrent=10)
results = await asyncio.gather(*[
    limiter.execute(process(item))
    for item in items
])
```

### Async Anti-Patterns (FORBIDDEN)

```python
# Bad: Blocking I/O in async function
async def bad_async():
    result = requests.get(url)  # BLOCKS event loop - FORBIDDEN
    return result

# Good: Use async HTTP client
async def good_async():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

# Bad: Sequential execution (defeats purpose of async)
async def bad_sequential():
    result1 = await task1()  # Waits
    result2 = await task2()  # Waits
    return result1, result2

# Good: Concurrent execution
async def good_concurrent():
    result1, result2 = await asyncio.gather(
        task1(),  # Runs concurrently
        task2()   # Runs concurrently
    )
    return result1, result2
```

## GPU Optimization (Maximum Throughput)

### GPU Best Practices

```python
import torch
import numpy as np

# Pattern 1: Batch processing for GPU efficiency
def process_batch_gpu(
    inputs: List[np.ndarray],
    model: torch.nn.Module,
    batch_size: int = 32
) -> List[np.ndarray]:
    results = []

    # Process in batches for GPU efficiency
    for i in range(0, len(inputs), batch_size):
        batch = inputs[i:i + batch_size]

        # Convert to tensor once
        batch_tensor = torch.tensor(
            np.stack(batch),
            device='cuda',
            dtype=torch.float32
        )

        # GPU inference
        with torch.no_grad():  # Disable gradients for inference
            output = model(batch_tensor)

        # Convert back to numpy
        results.extend(output.cpu().numpy())

    return results

# Pattern 2: Pinned memory for faster CPU-GPU transfer
def create_pinned_buffer(shape: Tuple[int, ...]) -> np.ndarray:
    # Pinned memory for faster transfers
    return torch.zeros(shape, pin_memory=True).numpy()

# Pattern 3: Async GPU operations
def async_gpu_processing(
    inputs: torch.Tensor,
    model: torch.nn.Module
) -> torch.Tensor:
    # Non-blocking transfer to GPU
    inputs_gpu = inputs.to('cuda', non_blocking=True)

    # Async GPU computation
    with torch.cuda.stream(torch.cuda.Stream()):
        output = model(inputs_gpu)

    return output

# Pattern 4: Mixed precision for 2x speedup
from torch.cuda.amp import autocast, GradScaler

def mixed_precision_inference(
    inputs: torch.Tensor,
    model: torch.nn.Module
) -> torch.Tensor:
    with autocast():  # Automatic mixed precision
        output = model(inputs)
    return output
```

### GPU Memory Management

```python
# Pattern: GPU memory pool
class GPUMemoryPool:
    def __init__(self, max_size: int):
        self.pool: Dict[Tuple[int, ...], List[torch.Tensor]] = {}
        self.max_size = max_size

    def get_tensor(self, shape: Tuple[int, ...]) -> torch.Tensor:
        if shape in self.pool and self.pool[shape]:
            return self.pool[shape].pop()
        return torch.zeros(shape, device='cuda')

    def return_tensor(self, tensor: torch.Tensor) -> None:
        shape = tuple(tensor.shape)
        if shape not in self.pool:
            self.pool[shape] = []
        if len(self.pool[shape]) < self.max_size:
            tensor.zero_()  # Clear data
            self.pool[shape].append(tensor)
```

## String Operations (Optimized)

### String Best Practices

```python
# Bad: String concatenation in loop - O(n²)
def build_string_bad(items: List[str]) -> str:
    result = ""
    for item in items:
        result += item  # Creates new string each time - SLOW
    return result

# Good: Join with list - O(n)
def build_string_optimal(items: List[str]) -> str:
    return "".join(items)  # Single allocation - FAST

# Bad: Multiple replace calls
def clean_text_bad(text: str) -> str:
    text = text.replace("a", "")
    text = text.replace("b", "")
    text = text.replace("c", "")
    return text

# Good: Single pass with translate
def clean_text_optimal(text: str) -> str:
    translation_table = str.maketrans("", "", "abc")
    return text.translate(translation_table)

# Pattern: String interning for repeated strings
import sys

def intern_string(s: str) -> str:
    # Reuse string objects for memory efficiency
    return sys.intern(s)
```

## Error Handling (Robust & Fast)

### Error Handling Patterns

```python
from typing import Union, Optional
from dataclasses import dataclass

# Pattern 1: Result type (no exceptions in hot path)
@dataclass
class Result:
    success: bool
    value: Optional[Any] = None
    error: Optional[str] = None

def safe_operation(data: bytes) -> Result:
    try:
        value = process(data)
        return Result(success=True, value=value)
    except Exception as e:
        return Result(success=False, error=str(e))

# Pattern 2: Early return for validation
def process_input(data: Optional[bytes]) -> str:
    # Fast path: early validation
    if not data:
        return "ERROR: No data"
    if len(data) < MIN_SIZE:
        return "ERROR: Data too small"

    # Main processing
    return process(data)

# Pattern 3: Context manager for resource cleanup
from contextlib import contextmanager

@contextmanager
def managed_resource(resource_id: str):
    resource = acquire_resource(resource_id)
    try:
        yield resource
    finally:
        release_resource(resource)  # Always cleanup

# Usage
with managed_resource("audio_device") as device:
    process_audio(device)
```

## Profiling & Optimization (Continuous)

### Profiling Tools (Mandatory Use)

```python
# 1. cProfile for CPU profiling
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()

    # Code to profile
    critical_function()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 functions

# 2. line_profiler for line-by-line profiling
from line_profiler import LineProfiler

def profile_line_by_line():
    profiler = LineProfiler()
    profiler.add_function(critical_function)
    profiler.enable()

    critical_function()

    profiler.disable()
    profiler.print_stats()

# 3. py-spy for production profiling (no overhead)
# Run: py-spy record -o profile.svg -- python script.py

# 4. memory_profiler for memory profiling
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Memory usage tracked
    pass
```

### Optimization Checklist

Before optimizing, profile to find bottlenecks:

1. **Measure**: Profile to identify hot paths
2. **Analyze**: Understand why it's slow
3. **Optimize**: Apply appropriate optimization
4. **Verify**: Profile again to confirm improvement
5. **Document**: Document optimization and reasoning

### Common Optimizations

```python
# Optimization 1: Use NumPy for numerical operations
# Bad: Python loops - SLOW
def sum_bad(numbers: List[float]) -> float:
    total = 0.0
    for num in numbers:
        total += num
    return total

# Good: NumPy vectorization - 10-100x FASTER
def sum_optimal(numbers: np.ndarray) -> float:
    return np.sum(numbers)

# Optimization 2: Use built-in functions (implemented in C)
# Bad: Manual implementation
def max_bad(numbers: List[int]) -> int:
    max_val = numbers[0]
    for num in numbers[1:]:
        if num > max_val:
            max_val = num
    return max_val

# Good: Built-in max - FASTER
def max_optimal(numbers: List[int]) -> int:
    return max(numbers)

# Optimization 3: List comprehension vs loops
# Bad: Append in loop
def process_bad(items: List[int]) -> List[int]:
    result = []
    for item in items:
        result.append(item * 2)
    return result

# Good: List comprehension - FASTER
def process_optimal(items: List[int]) -> List[int]:
    return [item * 2 for item in items]

# Optimization 4: Generator for memory efficiency
# Bad: Create entire list in memory
def process_large_bad(items: List[int]) -> List[int]:
    return [expensive_operation(item) for item in items]

# Good: Generator - memory efficient
def process_large_optimal(items: List[int]) -> Iterator[int]:
    return (expensive_operation(item) for item in items)
```

## Code Review Checklist (Mandatory)

### Performance Review

- [ ] Time complexity documented and optimal (O(1), O(log n), O(n))
- [ ] Space complexity documented and minimal
- [ ] No O(n²) or worse algorithms (unless n < 100 and justified)
- [ ] Appropriate data structures used (dict for lookups, set for membership)
- [ ] No unnecessary memory allocations
- [ ] Caching used for expensive operations
- [ ] Async/await used for I/O operations
- [ ] GPU used for parallel operations
- [ ] Profiling results included for critical paths

### Code Quality Review

- [ ] No code duplication (DRY principle)
- [ ] Functions <50 lines
- [ ] Classes <300 lines
- [ ] Cyclomatic complexity <10
- [ ] Type hints complete (mypy strict)
- [ ] Docstrings for all public APIs
- [ ] Error handling robust
- [ ] Resource cleanup guaranteed (context managers)
- [ ] Thread-safe if concurrent access

### Optimization Review

- [ ] Profiled before optimization
- [ ] Optimization justified with measurements
- [ ] No premature optimization
- [ ] Readability maintained
- [ ] Tests still pass
- [ ] Performance improvement documented

## Forbidden Patterns (Never Use)

### Anti-Patterns (BANNED)

```python
# 1. FORBIDDEN: Mutable default arguments
def bad_function(items=[]):  # BUG: Shared mutable default
    items.append(1)
    return items

def good_function(items=None):  # CORRECT
    if items is None:
        items = []
    items.append(1)
    return items

# 2. FORBIDDEN: Bare except
try:
    risky_operation()
except:  # FORBIDDEN: Catches everything including KeyboardInterrupt
    pass

try:
    risky_operation()
except Exception as e:  # CORRECT: Specific exception
    logger.error(f"Operation failed: {e}")

# 3. FORBIDDEN: Using 'is' for value comparison
if x is True:  # FORBIDDEN: Identity check
    pass

if x == True:  # CORRECT: Value comparison
    pass

# 4. FORBIDDEN: Modifying list while iterating
for item in items:  # FORBIDDEN: Undefined behavior
    if condition(item):
        items.remove(item)

items = [item for item in items if not condition(item)]  # CORRECT

# 5. FORBIDDEN: Global variables
global_counter = 0  # FORBIDDEN: Global state

class Counter:  # CORRECT: Encapsulated state
    def __init__(self):
        self.count = 0
```

## Performance Targets (Must Meet)

### Critical Path Performance

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Wake word detection | <200ms | 95th percentile |
| Speech recognition | <1s | 95th percentile |
| Face recognition | <50ms | 95th percentile |
| LLM inference | <2s | 95th percentile |
| Memory lookup | <1ms | 99th percentile |
| Disk I/O | <10ms | 95th percentile |
| Network request | <100ms | 95th percentile |

### Resource Limits

| Resource | Limit | Monitoring |
|----------|-------|------------|
| Memory (idle) | <500MB | Continuous |
| Memory (active) | <2GB | Continuous |
| CPU (idle) | <15% | Continuous |
| CPU (active) | <80% | Continuous |
| GPU (active) | >80% utilization | Continuous |
| Disk I/O | <100 MB/s | Continuous |
| Network | <10 MB/s | Continuous |

---

**Remember**: Every millisecond counts. Every byte matters. Every algorithm must be optimal. Agent Guru must be the fastest, most efficient voice assistant ever built.

**Performance is not negotiable. Optimization is mandatory.**
