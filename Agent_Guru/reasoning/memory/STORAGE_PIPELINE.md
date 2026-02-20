# Memory Storage Pipeline

## Overview

The Memory Storage Pipeline provides automatic memory creation and storage after various events in the reasoning engine. It handles episodic, semantic, preference, and task memories with intelligent deduplication and relevance scoring.

## Features

- **Automatic Memory Creation**: Stores memories after task execution, user corrections, behavioral learning, and multi-step tasks
- **Smart Deduplication**: Prevents redundant memories using semantic similarity (95% threshold) and temporal windows (24 hours)
- **Type-Specific Storage**: Handles four memory types with appropriate metadata
- **Async Support**: Non-blocking storage operations for optimal performance
- **Privacy-Preserving**: User-isolated storage with strict access controls
- **Configurable Retention**: Customizable limits and policies

## Memory Types

### 1. Episodic Memory
Stores specific events and experiences from user interactions.

**When to Store**:
- After each task execution
- After user commands
- After system actions

**Example**:
```python
memory_id = await pipeline.store_episodic(
    user_id="user_123",
    content="User set a timer for 5 minutes while cooking",
    action_taken="set_timer",
    result="Timer set successfully for 5 minutes",
    success=True,
    context={"location": "kitchen", "time_of_day": "evening"}
)
```

### 2. Semantic Memory
Stores facts and knowledge from user corrections and feedback.

**When to Store**:
- After user corrections
- After user provides information
- After system learns new facts

**Example**:
```python
memory_id = await pipeline.store_semantic(
    user_id="user_123",
    content="User's favorite color is blue",
    fact="favorite_color=blue",
    source="user_stated",
    confidence=1.0
)
```

### 3. Preference Memory
Stores user preferences and behavioral patterns.

**When to Store**:
- After explicit user preferences
- After inferred preferences from behavior
- After observed patterns

**Example**:
```python
memory_id = await pipeline.store_preference(
    user_id="user_123",
    content="User prefers morning notifications",
    preference_key="notification_time",
    preference_value="morning",
    learned_from="explicit"
)
```

### 4. Task Memory
Stores multi-step task executions and lessons learned.

**When to Store**:
- After multi-step task completion
- After complex workflows
- After task failures (to learn)

**Example**:
```python
memory_id = await pipeline.store_task(
    user_id="user_123",
    content="Multi-step task to book restaurant and set reminder",
    task_id="task_456",
    task_description="Book restaurant for 7pm and set reminder 1 hour before",
    outcome="success",
    lessons_learned=["User prefers Italian restaurants", "Needs 1 hour prep time"]
)
```

## Deduplication Logic

The pipeline prevents redundant memories using two criteria:

1. **Semantic Similarity**: Memories with similarity >= 95% are considered duplicates
2. **Temporal Window**: Only memories within 24 hours are checked for duplication

This ensures:
- No duplicate memories for the same event
- Similar events can be stored if separated by time
- Different users can have identical memories (user-isolated)

## Configuration

```python
pipeline = MemoryStoragePipeline(
    vector_db=None,  # Auto-creates if None
    embedding_generator=None,  # Auto-creates if None
    deduplication_threshold=0.95,  # Similarity threshold (0.0-1.0)
    deduplication_window_hours=24,  # Time window for deduplication
    min_content_length=10,  # Minimum content length (chars)
    max_memories_per_user=10000,  # Maximum memories per user
)
```

## Performance Characteristics

- **Storage Latency**: <10ms per memory (target)
- **Deduplication Check**: O(log n) with HNSW search
- **Embedding Generation**: <50ms per text (GPU accelerated)
- **Concurrent Storage**: Thread-safe with async locks
- **Memory Overhead**: O(n * d) where n=memories, d=embedding_dim (384)

## Usage Examples

### Basic Usage

```python
from Agent_Guru.reasoning.memory import MemoryStoragePipeline

# Initialize pipeline
pipeline = MemoryStoragePipeline()

# Store episodic memory after task execution
memory_id = await pipeline.store_episodic(
    user_id="user_123",
    content="User set a timer for 5 minutes",
    action_taken="set_timer",
    result="Success",
    success=True
)

# Get storage statistics
stats = pipeline.get_storage_stats()
print(f"Episodic memories: {stats['episodic']}")
```

### Integration with Reasoning Engine

```python
# After task execution
async def execute_task(user_id: str, action: Action) -> ExecutionResult:
    # Execute the action
    result = await action_executor.execute(action)

    # Store episodic memory
    await memory_pipeline.store_episodic(
        user_id=user_id,
        content=f"User executed {action.tool_id}",
        action_taken=action.tool_id,
        result=result.result_data,
        success=result.success,
        context=action.parameters
    )

    return result
```

### Concurrent Storage

```python
# Store multiple memories concurrently
tasks = [
    pipeline.store_episodic(
        user_id=f"user_{i}",
        content=f"User {i} performed action",
        action_taken="test_action",
        result="Success",
        success=True
    )
    for i in range(10)
]

memory_ids = await asyncio.gather(*tasks)
```

## Storage Statistics

```python
# Get overall statistics
stats = pipeline.get_storage_stats()
print(f"Episodic: {stats['episodic']}")
print(f"Semantic: {stats['semantic']}")
print(f"Preference: {stats['preference']}")
print(f"Task: {stats['task']}")

# Clear cache (periodic maintenance)
pipeline.clear_cache()
```

## Error Handling

The pipeline handles errors gracefully:

- **Short Content**: Memories with content < min_content_length are skipped
- **Duplicates**: Duplicate memories return None (not an error)
- **Storage Failures**: Logged and return None (fail open)
- **User Limits**: Memories beyond max_memories_per_user are skipped

## Best Practices

1. **Store Immediately**: Store memories right after events for accurate timestamps
2. **Provide Context**: Include relevant context in episodic memories
3. **Use Appropriate Types**: Choose the correct memory type for the event
4. **Monitor Statistics**: Track storage stats to detect issues
5. **Clear Cache Periodically**: Call `clear_cache()` to prevent unbounded growth
6. **Handle None Returns**: Check for None (duplicate or error) and handle appropriately

## Testing

The pipeline includes comprehensive tests:

```bash
# Run all tests
pytest Agent_Guru/reasoning/tests/test_memory_storage_pipeline.py -v

# Run with coverage
pytest Agent_Guru/reasoning/tests/test_memory_storage_pipeline.py --cov=Agent_Guru.reasoning.memory.storage_pipeline --cov-report=term-missing
```

**Coverage**: 87% (exceeds 80% target)

## Future Enhancements

- **Batch Storage**: Store multiple memories in a single operation
- **Priority Queues**: Prioritize important memories for storage
- **Automatic Pruning**: Remove low-relevance memories automatically
- **Cross-Device Sync**: Sync memories across user devices
- **Memory Compression**: Compress old memories to save space
- **Analytics**: Track memory usage patterns and insights

## References

- Memory Models: `Agent_Guru/reasoning/models/memory.py`
- Vector Database: `Agent_Guru/reasoning/memory/vector_db.py`
- Embedding Generator: `Agent_Guru/reasoning/memory/embedding.py`
- Design Document: `.kiro/specs/core-reasoning-engine/design.md`
- Requirements: `.kiro/specs/core-reasoning-engine/requirements.md` (Requirement 33.2)
