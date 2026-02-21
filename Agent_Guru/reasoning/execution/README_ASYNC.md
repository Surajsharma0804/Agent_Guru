# Asynchronous Execution Engine

## Overview

The asynchronous execution engine provides support for long-running operations using Celery with Redis as the message broker. This enables:

- Non-blocking task execution
- Progress tracking with real-time updates
- Task cancellation support
- Result storage with 1-hour TTL
- Automatic retry for failed tasks

## Architecture

```
┌─────────────────┐
│  Application    │
│  (Submit Task)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  Celery Broker  │◄────►│    Redis     │
│  (Task Queue)   │      │  (Results)   │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐
│  Celery Worker  │
│  (Execute Task) │
└─────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
pip install celery redis
```

### 2. Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install locally
# Windows: Download from https://github.com/microsoftarchive/redis/releases
# Linux: sudo apt-get install redis-server
# macOS: brew install redis
```

### 3. Start Celery Worker

```bash
# From project root
celery -A Agent_Guru.reasoning.execution.async_executor worker --loglevel=info

# With concurrency control
celery -A Agent_Guru.reasoning.execution.async_executor worker --loglevel=info --concurrency=4

# With autoscaling
celery -A Agent_Guru.reasoning.execution.async_executor worker --loglevel=info --autoscale=10,3
```

### 4. Monitor Tasks (Optional)

```bash
# Install Flower for web-based monitoring
pip install flower

# Start Flower
celery -A Agent_Guru.reasoning.execution.async_executor flower
# Access at http://localhost:5555
```

## Usage

### Basic Async Execution

```python
from Agent_Guru.reasoning.execution.async_executor import AsyncExecutionController
from Agent_Guru.reasoning.models.action import Action

# Initialize controller
controller = AsyncExecutionController()

# Create action
action = Action(
    action_id="action_1",
    tool_id="long_running_tool",
    parameters={"input": "data"},
)

# Submit async task
result = controller.execute_async(
    action,
    tool_module="Agent_Guru.reasoning.tools.examples.timer",
    tool_function_name="execute_timer",
)

print(f"Task submitted: {result.task_id}")
print(f"Status: {result.status}")
```

### Check Task Status

```python
# Get current status
status = controller.get_status(result.task_id)

print(f"Status: {status.status}")
print(f"Progress: {status.progress}%")

if status.status == TaskStatus.SUCCESS:
    print(f"Result: {status.result_data}")
elif status.status == TaskStatus.FAILURE:
    print(f"Error: {status.error}")
```

### Wait for Completion

```python
# Wait for task to complete (with timeout)
try:
    final_result = controller.wait(result.task_id, timeout=60.0)
    print(f"Task completed: {final_result.result_data}")
except TimeoutError:
    print("Task did not complete within 60 seconds")
```

### Cancel Task

```python
# Cancel running task
success = controller.cancel(result.task_id)
if success:
    print("Task cancellation requested")
```

### Progress Tracking

Tasks can report progress during execution:

```python
# In your tool function
from Agent_Guru.reasoning.execution.async_executor import ProgressTask

@celery_app.task(bind=True, base=ProgressTask)
def my_long_task(self, params):
    # Update progress
    self.update_progress(25, "Step 1 complete")
    
    # Do work...
    
    self.update_progress(50, "Step 2 complete")
    
    # More work...
    
    self.update_progress(100, "All done")
    
    return {"result": "success"}
```

## Configuration

### Celery Configuration

Edit `async_executor.py` to customize Celery settings:

```python
celery_app.conf.update(
    broker_url="redis://localhost:6379/0",  # Redis broker
    result_backend="redis://localhost:6379/0",  # Result storage
    result_expires=3600,  # 1 hour TTL
    task_acks_late=True,  # Acknowledge after completion
    worker_prefetch_multiplier=1,  # Prefetch 1 task at a time
)
```

### Redis Configuration

For production, configure Redis with:
- Persistence (RDB or AOF)
- Memory limits
- Authentication
- Replication for high availability

## Performance

### Latency

- Task submission: <100ms
- Status check: <10ms (Redis lookup)
- Progress update: <50ms

### Throughput

- Tasks per second: 100+ (depends on task complexity)
- Concurrent tasks: Limited by worker concurrency

### Resource Usage

- Memory: ~50MB per worker + task data
- CPU: Depends on task workload
- Redis: ~1KB per task result

## Monitoring

### Metrics to Track

1. **Task Metrics**
   - Tasks submitted per minute
   - Tasks completed per minute
   - Task success rate
   - Average task duration

2. **Queue Metrics**
   - Queue depth (pending tasks)
   - Queue processing rate
   - Queue wait time

3. **Worker Metrics**
   - Active workers
   - Worker CPU/memory usage
   - Worker task throughput

### Logging

Celery logs include:
- Task submission
- Task start/completion
- Task failures
- Worker events

Configure logging level:
```bash
celery -A Agent_Guru.reasoning.execution.async_executor worker --loglevel=debug
```

## Error Handling

### Task Failures

Tasks automatically retry on failure:
- Transient errors: Retry with exponential backoff
- Permanent errors: Fail immediately

### Worker Failures

If a worker crashes:
- Tasks are requeued automatically (with `task_acks_late=True`)
- Other workers pick up the tasks
- No task loss

### Broker Failures

If Redis goes down:
- Task submission fails immediately
- Running tasks continue
- Results may be lost (use persistent Redis)

## Best Practices

1. **Task Design**
   - Keep tasks idempotent (safe to retry)
   - Avoid long-running tasks (>5 minutes)
   - Break large tasks into smaller chunks
   - Report progress for long tasks

2. **Resource Management**
   - Set appropriate worker concurrency
   - Monitor memory usage
   - Use task time limits
   - Clean up resources in tasks

3. **Error Handling**
   - Handle exceptions in tasks
   - Return structured error information
   - Log errors for debugging
   - Implement retry logic

4. **Monitoring**
   - Use Flower for real-time monitoring
   - Set up alerts for failures
   - Track queue depth
   - Monitor worker health

## Troubleshooting

### Task Not Executing

1. Check Celery worker is running
2. Check Redis is accessible
3. Check task is in queue: `celery -A ... inspect active`
4. Check worker logs for errors

### Task Stuck

1. Check task timeout settings
2. Check worker is not overloaded
3. Cancel and resubmit task
4. Check for deadlocks in task code

### High Memory Usage

1. Reduce worker concurrency
2. Implement task result cleanup
3. Use task time limits
4. Monitor task memory usage

### Slow Performance

1. Increase worker concurrency
2. Add more workers
3. Optimize task code
4. Use task prefetching

## Production Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  redis:
    image: redis:latest
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  celery-worker:
    build: .
    command: celery -A Agent_Guru.reasoning.execution.async_executor worker --loglevel=info --concurrency=4
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0

  flower:
    build: .
    command: celery -A Agent_Guru.reasoning.execution.async_executor flower
    ports:
      - "5555:5555"
    depends_on:
      - redis
      - celery-worker

volumes:
  redis-data:
```

### Kubernetes

Deploy with:
- Redis StatefulSet for persistence
- Celery worker Deployment with autoscaling
- Flower Deployment for monitoring
- Service for Redis access

## References

- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [Flower Documentation](https://flower.readthedocs.io/)
