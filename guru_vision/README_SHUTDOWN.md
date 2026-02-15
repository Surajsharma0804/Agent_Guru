# GuruVision Engine Shutdown and Resource Management

This document describes the shutdown and resource management functionality of the GuruVision engine.

## Overview

The GuruVision engine implements graceful shutdown with proper resource cleanup to ensure:
- Database changes are persisted
- ONNX Runtime sessions are closed
- All module references are cleared
- Shutdown completes within 3 seconds
- Signal handlers (SIGINT, SIGTERM) trigger graceful shutdown

## Requirements

- **20.3**: Release camera resources
- **20.4**: Save pending database changes
- **20.5**: Close ONNX Runtime sessions and complete within 3 seconds
- **20.6**: Handle SIGINT and SIGTERM signals
- **20.7**: Complete current frame before shutting down

## Shutdown Method

The `shutdown()` method performs the following steps:

1. **Check shutdown flag**: Prevents duplicate shutdowns
2. **Save database**: Persists any pending changes to disk
3. **Close ONNX sessions**: Releases recognizer, liveness, and emotion model sessions
4. **Clear module references**: Sets all module instances to None
5. **Mark as not initialized**: Sets `initialized` flag to False
6. **Log timing**: Warns if shutdown exceeds 3 seconds

### Usage

```python
from guru_vision.engine import GuruVisionEngine

# Create and initialize engine
engine = GuruVisionEngine()
engine.initialize()

# ... use the engine ...

# Gracefully shutdown
engine.shutdown()
```

## Signal Handling

The engine automatically registers signal handlers during initialization:

- **SIGINT** (Ctrl+C): Triggers graceful shutdown
- **SIGTERM**: Triggers graceful shutdown
- **atexit**: Fallback handler ensures shutdown is called at program exit

### Signal Handler Behavior

When a signal is received:
1. Log the signal type (SIGINT or SIGTERM)
2. Set the shutdown flag
3. Call the `shutdown()` method
4. Exit with appropriate code (0 for success, 1 for error)

## Frame Processing During Shutdown

When shutdown is requested, the `process_frame()` method:
1. Checks the `_shutdown_requested` flag
2. Returns an empty `RecognitionResult` if shutdown is in progress
3. Prevents new frame processing after shutdown

This ensures the current frame completes before shutdown proceeds (Requirement 20.7).

## Resource Cleanup

### Database
- Calls `database.save()` to persist changes
- Handles save errors gracefully (logs error but continues shutdown)

### ONNX Runtime Sessions
The engine closes sessions for:
- Face recognition model (`recognizer.session`)
- Liveness detection model (`liveness_detector.session`)
- Emotion recognition model (`emotion_recognizer.session`)

### Module References
All module instances are set to None:
- `detector`
- `aligner`
- `recognizer`
- `liveness_detector`
- `emotion_recognizer`
- `tracker`
- `database`

## Idempotency

The shutdown method is idempotent - calling it multiple times is safe:
- The `_shutdown_requested` flag prevents duplicate execution
- Subsequent calls return immediately without error

## Error Handling

The shutdown method handles errors gracefully:
- Database save errors are logged but don't prevent shutdown
- ONNX session cleanup errors are logged but don't prevent shutdown
- Critical errors are re-raised after logging

## Performance

The shutdown method is designed to complete within 3 seconds:
- Timing is logged for monitoring
- Warning is issued if shutdown exceeds 3 seconds
- Most operations complete in milliseconds

## Testing

The shutdown functionality is tested in `test_shutdown.py`:

- `test_shutdown_basic`: Verifies basic shutdown behavior
- `test_shutdown_timing`: Ensures shutdown completes within 3 seconds
- `test_shutdown_saves_database`: Verifies database persistence
- `test_shutdown_closes_onnx_sessions`: Verifies session cleanup
- `test_shutdown_clears_module_references`: Verifies reference cleanup
- `test_shutdown_idempotent`: Verifies multiple calls are safe
- `test_shutdown_handles_database_error`: Verifies error handling
- `test_signal_handler_registration`: Verifies signal handlers are registered
- `test_process_frame_after_shutdown`: Verifies frame processing stops
- `test_shutdown_during_frame_processing`: Verifies shutdown flag behavior

## Example: Graceful Shutdown with Signal Handling

```python
import signal
import time
from guru_vision.engine import GuruVisionEngine
import numpy as np

# Create and initialize engine
engine = GuruVisionEngine()
engine.initialize()

print("Engine initialized. Press Ctrl+C to shutdown gracefully.")

try:
    # Process frames in a loop
    while True:
        # Create test frame (in production, this would come from a camera)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Process frame
        result = engine.process_frame(frame)
        
        # Check if shutdown was requested
        if engine._shutdown_requested:
            print("Shutdown requested, exiting loop")
            break
        
        time.sleep(0.1)  # Simulate frame rate

except KeyboardInterrupt:
    print("\nKeyboard interrupt received")

finally:
    # Shutdown is automatically called by signal handler
    # But we can also call it explicitly if needed
    if not engine._shutdown_requested:
        engine.shutdown()
    print("Engine shutdown complete")
```

## Example: Manual Shutdown

```python
from guru_vision.engine import GuruVisionEngine
import numpy as np

# Create and initialize engine
engine = GuruVisionEngine()
engine.initialize()

# Process some frames
for i in range(10):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.process_frame(frame)
    print(f"Frame {i}: {len(result.faces)} faces detected")

# Manually shutdown when done
engine.shutdown()
print("Engine shutdown complete")
```

## Best Practices

1. **Always call shutdown**: Ensure `shutdown()` is called when done with the engine
2. **Use try-finally**: Wrap engine usage in try-finally to ensure shutdown
3. **Check shutdown flag**: Check `_shutdown_requested` in long-running loops
4. **Handle signals**: Let the engine's signal handlers manage graceful shutdown
5. **Monitor timing**: Check logs for shutdown timing warnings

## Troubleshooting

### Shutdown takes longer than 3 seconds
- Check database size (large databases take longer to save)
- Check for slow disk I/O
- Review logs for specific slow operations

### Database not saved
- Check file permissions on database path
- Check disk space
- Review error logs for save failures

### Signal handlers not working
- Ensure engine is initialized (handlers registered during init)
- Check for conflicting signal handlers
- Review logs for handler registration errors

## Implementation Notes

### Camera Resources
The engine doesn't directly manage camera resources (they are managed externally by the user). The shutdown method logs this step for completeness.

### ONNX Runtime Cleanup
ONNX Runtime sessions are automatically cleaned up by Python's garbage collector, but we explicitly delete references to help with cleanup timing.

### Thread Safety
The shutdown method is not thread-safe. Ensure it's called from a single thread or use appropriate locking.

## Related Documentation

- [Engine Documentation](README_ENGINE.md)
- [Configuration Management](../config.py)
- [Database Management](../database/README.md)
- [Logging Utilities](../utils/README_LOGGING.md)
