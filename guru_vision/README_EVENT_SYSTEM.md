# GuruVision Event System

This document describes the event system and callback functionality in GuruVision.

## Overview

The GuruVision event system allows AI agents and applications to subscribe to events that occur during recognition operations. This enables reactive programming patterns where your application can respond to specific events like identity recognition, errors, or system state changes.

**Requirements:** 13.3, 13.5

## Supported Event Types

The GuruVision engine supports the following event types:

### 1. `identity_recognized`

Emitted when a known identity is recognized in a frame.

**Event Data:**
```python
{
    'timestamp': str,           # ISO format timestamp
    'frame_id': int,            # Sequential frame identifier
    'tracking_id': int,         # Unique tracking ID for this face
    'identity': str,            # Name of recognized identity
    'confidence': float,        # Recognition confidence (0.0 to 1.0)
    'permission_level': str,    # Permission level (admin, user, guest, denied)
    'emotion': str,             # Dominant emotion
    'emotion_confidence': float,# Emotion confidence (0.0 to 1.0)
    'is_live': bool,           # Whether face passed liveness detection
    'liveness_confidence': float,# Liveness confidence (0.0 to 1.0)
    'bbox': tuple              # Bounding box (x, y, w, h)
}
```

**When Emitted:**
- During `process_frame()` when a face is recognized with identity != "Unknown"
- Only emitted for faces that pass liveness detection (if enabled)

### 2. `new_identity`

Emitted when a new identity is added to the database.

**Event Data:**
```python
{
    'timestamp': str,           # ISO format timestamp
    'identity': str,            # Name of new identity
    'permission_level': str,    # Permission level assigned
    'num_embeddings': int       # Number of embeddings extracted
}
```

**When Emitted:**
- During `add_identity()` after successfully adding identity to database

### 3. `permission_changed`

Emitted when an identity's permission level is updated.

**Event Data:**
```python
{
    'timestamp': str,              # ISO format timestamp
    'identity': str,               # Name of identity
    'new_permission_level': str    # New permission level
}
```

**When Emitted:**
- During `update_permission()` after successfully updating permission

### 4. `error`

Emitted when an error occurs in any component.

**Event Data:**
```python
{
    'timestamp': str,           # ISO format timestamp
    'component': str,           # Component where error occurred
    'error_type': str,          # Exception type name
    'error_message': str,       # Error message
    'frame_id': int,           # Frame ID (if applicable)
    'tracking_id': int         # Tracking ID (if applicable)
}
```

**When Emitted:**
- During `initialize()` if initialization fails
- During `process_frame()` if face detection fails
- During `process_frame()` if face tracking fails
- During `process_frame()` if liveness detection fails
- During `process_frame()` if emotion recognition fails

**Component Values:**
- `initialization`: Error during engine initialization
- `face_detection`: Error during face detection
- `face_tracking`: Error during face tracking
- `liveness_detection`: Error during liveness detection
- `emotion_recognition`: Error during emotion recognition

### 5. `system_ready`

Emitted when the engine completes initialization.

**Event Data:**
```python
{
    'timestamp': str,           # ISO format timestamp
    'config': dict,             # Configuration dictionary
    'num_identities': int       # Number of identities loaded
}
```

**When Emitted:**
- At the end of `initialize()` after all modules are loaded

## Usage

### Basic Callback Registration

```python
from guru_vision.engine import GuruVisionEngine

# Create engine
engine = GuruVisionEngine()

# Define callback function
def on_identity_recognized(event_data):
    print(f"Recognized: {event_data['identity']}")
    print(f"Confidence: {event_data['confidence']:.3f}")

# Register callback
engine.register_callback('identity_recognized', on_identity_recognized)

# Initialize and use engine
engine.initialize()
# ... process frames ...
```

### Multiple Callbacks

You can register multiple callbacks for the same event type:

```python
def callback1(data):
    print(f"Callback 1: {data['identity']}")

def callback2(data):
    print(f"Callback 2: Confidence {data['confidence']:.3f}")

engine.register_callback('identity_recognized', callback1)
engine.register_callback('identity_recognized', callback2)

# Both callbacks will be called when event is emitted
```

### Lambda Callbacks

For simple callbacks, you can use lambda functions:

```python
engine.register_callback(
    'identity_recognized',
    lambda data: print(f"Recognized: {data['identity']}")
)
```

### Class-Based Callbacks

You can use class methods as callbacks to maintain state:

```python
class RecognitionLogger:
    def __init__(self):
        self.count = 0
    
    def on_recognition(self, event_data):
        self.count += 1
        print(f"Recognition #{self.count}: {event_data['identity']}")

logger = RecognitionLogger()
engine.register_callback('identity_recognized', logger.on_recognition)
```

### Conditional Callbacks

Callbacks can filter events based on conditions:

```python
def high_confidence_only(event_data):
    if event_data['confidence'] > 0.9:
        print(f"High confidence: {event_data['identity']}")

def admin_only(event_data):
    if event_data['permission_level'] == 'admin':
        print(f"Admin detected: {event_data['identity']}")

engine.register_callback('identity_recognized', high_confidence_only)
engine.register_callback('identity_recognized', admin_only)
```

## Error Handling

Exceptions raised in callbacks are caught and logged, but do not prevent other callbacks from executing:

```python
def failing_callback(event_data):
    raise RuntimeError("Oops!")

def working_callback(event_data):
    print("This will still execute")

engine.register_callback('identity_recognized', failing_callback)
engine.register_callback('identity_recognized', working_callback)

# Both callbacks are called, exception in first is caught and logged
```

## AI Agent Integration

The event system is designed for AI agent integration. Here's an example of how an AI agent might use callbacks:

```python
class AIAgent:
    def __init__(self):
        self.engine = GuruVisionEngine()
        self.current_user = None
        
        # Register callbacks
        self.engine.register_callback('identity_recognized', self.on_user_recognized)
        self.engine.register_callback('error', self.on_error)
        self.engine.register_callback('system_ready', self.on_system_ready)
    
    def on_user_recognized(self, event_data):
        """Handle user recognition."""
        identity = event_data['identity']
        permission = event_data['permission_level']
        
        # Update current user
        self.current_user = identity
        
        # Personalize interaction based on permission level
        if permission == 'admin':
            self.grant_full_access()
        elif permission == 'user':
            self.grant_standard_access()
        elif permission == 'guest':
            self.grant_limited_access()
        elif permission == 'denied':
            self.deny_access()
        
        # Respond to emotion
        emotion = event_data['emotion']
        if emotion == 'happy':
            self.respond_cheerfully()
        elif emotion == 'sad':
            self.respond_empathetically()
    
    def on_error(self, event_data):
        """Handle errors."""
        component = event_data['component']
        message = event_data['error_message']
        self.log_error(f"Error in {component}: {message}")
    
    def on_system_ready(self, event_data):
        """Handle system ready."""
        num_identities = event_data['num_identities']
        print(f"System ready with {num_identities} known identities")
    
    def start(self):
        """Start the agent."""
        self.engine.initialize()
        # ... start processing frames ...
```

## Best Practices

1. **Keep Callbacks Fast**: Callbacks are executed synchronously during event emission. Keep them fast to avoid blocking the recognition pipeline.

2. **Handle Exceptions**: Always handle potential exceptions in your callbacks to prevent disrupting the event system.

3. **Use Conditional Logic**: Filter events in your callbacks rather than processing every event.

4. **Maintain State Externally**: If you need to track state across events, use class-based callbacks or closures.

5. **Log Important Events**: Use callbacks to log important events for monitoring and debugging.

6. **Separate Concerns**: Use different callbacks for different concerns (logging, access control, UI updates, etc.).

## API Reference

### `register_callback(event_type: str, callback: Callable) -> None`

Register a callback function for an event type.

**Parameters:**
- `event_type`: One of: `'identity_recognized'`, `'new_identity'`, `'permission_changed'`, `'error'`, `'system_ready'`
- `callback`: Callable that accepts event data dictionary

**Raises:**
- `ValueError`: If event_type is invalid or callback is not callable

**Example:**
```python
def my_callback(event_data):
    print(event_data)

engine.register_callback('identity_recognized', my_callback)
```

## Examples

See `example_event_system.py` for complete examples demonstrating:
- Basic callback registration
- Multiple callbacks for same event
- Lambda function callbacks
- Stateful callbacks with classes
- Conditional callbacks
- Error handling in callbacks

## Testing

See `test_event_system.py` for comprehensive tests of the event system functionality.

## Requirements Traceability

This implementation satisfies the following requirements:

- **Requirement 13.3**: Support callback functions that trigger when specific identities are recognized
- **Requirement 13.5**: Emit events that the AI_Agent can subscribe to

## Related Documentation

- [Main Engine Documentation](README_ENGINE.md)
- [Identity Management](README_IDENTITY_MANAGEMENT.md)
- [Configuration Management](../config.py)
