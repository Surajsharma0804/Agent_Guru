# GuruVision Recognition Engine

The GuruVision Recognition Engine is the main orchestrator for the facial recognition system. It provides a high-level API for AI agent integration and manages all subsystems including detection, alignment, recognition, liveness detection, emotion recognition, and face tracking.

## Overview

The `GuruVisionEngine` class is the primary interface for using GuruVision. It handles:

- **Face Detection**: Locates faces in video frames using RetinaFace
- **Face Alignment**: Normalizes face orientation and scale
- **Face Recognition**: Extracts embeddings and matches identities
- **Liveness Detection**: Detects spoofing attempts (photos, screens, masks)
- **Emotion Recognition**: Classifies facial expressions
- **Face Tracking**: Maintains stable IDs across frames
- **Database Management**: Stores and retrieves identity embeddings
- **Event System**: Emits events for recognition callbacks

## Quick Start

### Basic Usage

```python
from guru_vision.engine import GuruVisionEngine
import cv2

# Create and initialize engine
engine = GuruVisionEngine()
engine.initialize()

# Process a frame
frame = cv2.imread('image.jpg')
result = engine.process_frame(frame)

# Access results
for face in result.faces:
    print(f"Identity: {face.identity}")
    print(f"Confidence: {face.confidence}")
    print(f"Emotion: {face.emotion}")
    print(f"Liveness: {'Live' if face.is_live else 'Spoof'}")

# Shutdown
engine.shutdown()
```

### Using Custom Configuration

```python
from guru_vision.engine import GuruVisionEngine
from guru_vision.config import GuruVisionConfig

# Create custom configuration
config = GuruVisionConfig(
    recognition_threshold=0.7,
    enable_liveness=True,
    enable_emotion=True,
    enable_tracking=True,
    log_level="DEBUG"
)

# Save configuration
config.save_to_file("config.yaml")

# Create engine with config
engine = GuruVisionEngine(config_path="config.yaml")
engine.initialize()
```

### Using Event Callbacks

```python
from guru_vision.engine import GuruVisionEngine

engine = GuruVisionEngine()

# Define callback function
def on_identity_recognized(event_data):
    print(f"Recognized: {event_data['identity']}")
    print(f"Confidence: {event_data['confidence']}")
    print(f"Permission: {event_data['permission_level']}")

# Register callback
engine.register_callback('identity_recognized', on_identity_recognized)

# Initialize (triggers system_ready event)
engine.initialize()

# Process frames (triggers identity_recognized events)
result = engine.process_frame(frame)
```

## Data Structures

### FaceResult

Represents a single detected face with all recognition information:

```python
@dataclass
class FaceResult:
    tracking_id: int                    # Unique ID across frames
    bbox: Tuple[int, int, int, int]     # Bounding box (x, y, w, h)
    identity: str                       # Name or "Unknown"
    confidence: float                   # Recognition confidence (0.0-1.0)
    permission_level: str               # admin, user, guest, denied
    emotion: str                        # Dominant emotion
    emotion_confidence: float           # Emotion confidence (0.0-1.0)
    is_live: bool                       # Liveness check result
    liveness_confidence: float          # Liveness confidence (0.0-1.0)
```

### RecognitionResult

Complete result for a processed frame:

```python
@dataclass
class RecognitionResult:
    faces: List[FaceResult]             # All detected faces
    frame_id: int                       # Sequential frame number
    timestamp: str                      # ISO format timestamp
    processing_time_ms: float           # Processing time in milliseconds
```

### IdentityInfo

Information about a stored identity:

```python
@dataclass
class IdentityInfo:
    name: str                           # Identity name
    permission_level: str               # Permission level
    num_embeddings: int                 # Number of stored embeddings
    date_added: str                     # ISO format timestamp
    metadata: Dict[str, Any]            # Custom metadata
```

## API Reference

### GuruVisionEngine

#### `__init__(config_path: Optional[str] = None)`

Create a new engine instance.

**Parameters:**
- `config_path`: Optional path to configuration file (YAML or JSON)

#### `initialize() -> None`

Initialize all subsystems and load models.

**Raises:**
- `RuntimeError`: If initialization fails

**Process:**
1. Loads configuration
2. Initializes logging
3. Loads ONNX model
4. Initializes all modules
5. Loads face database
6. Emits "system_ready" event

#### `process_frame(frame: np.ndarray) -> RecognitionResult`

Process a single frame and return recognition results.

**Parameters:**
- `frame`: Input frame in BGR format (OpenCV format)

**Returns:**
- `RecognitionResult`: Complete recognition results

**Raises:**
- `RuntimeError`: If engine is not initialized
- `ValueError`: If frame is invalid

**Pipeline:**
1. Check brightness and apply low-light enhancement if needed
2. Run face detection
3. Update tracker with detections
4. For each face:
   - Align face
   - Extract embedding
   - Match identity
   - Run liveness detection (if enabled)
   - Run emotion recognition (if enabled)
   - Reject recognition if liveness fails
5. Combine results and add metadata
6. Emit recognition events

#### `add_identity(name: str, images: List[np.ndarray], permission_level: str = "user") -> bool`

Add a new identity without retraining the model.

**Parameters:**
- `name`: Unique identifier for the identity
- `images`: List of face images (BGR format)
- `permission_level`: Permission level (admin, user, guest, denied)

**Returns:**
- `bool`: True if successful, False otherwise

**Note:** This method is a placeholder and will be implemented in task 20.

#### `remove_identity(name: str) -> bool`

Remove an identity and all associated embeddings.

**Parameters:**
- `name`: Identity name to remove

**Returns:**
- `bool`: True if removed, False if not found

**Note:** This method is a placeholder and will be implemented in task 20.

#### `get_identities() -> List[IdentityInfo]`

Get information about all stored identities.

**Returns:**
- `List[IdentityInfo]`: List of identity information

**Note:** This method is a placeholder and will be implemented in task 20.

#### `update_permission(name: str, permission_level: str) -> bool`

Update the permission level for an identity.

**Parameters:**
- `name`: Identity name
- `permission_level`: New permission level

**Returns:**
- `bool`: True if updated, False if not found

**Note:** This method is a placeholder and will be implemented in task 20.

#### `register_callback(event_type: str, callback: Callable) -> None`

Register a callback function for recognition events.

**Parameters:**
- `event_type`: Event type to listen for
- `callback`: Callable that accepts event data dictionary

**Event Types:**
- `identity_recognized`: When an identity is recognized
- `new_identity`: When a new identity is added
- `permission_changed`: When permission level changes
- `error`: When an error occurs
- `system_ready`: When system initialization completes

**Note:** This method is a placeholder and will be implemented in task 21.

#### `shutdown() -> None`

Gracefully shutdown the engine and release resources.

**Process:**
1. Releases camera resources
2. Saves pending database changes
3. Closes ONNX Runtime sessions
4. Completes within 3 seconds

**Note:** This method is a placeholder and will be implemented in task 22.

## Configuration

The engine uses `GuruVisionConfig` for configuration. Key settings:

### Model Paths
- `onnx_model_path`: Path to ONNX recognition model
- `database_path`: Path to face database JSON file
- `liveness_model_path`: Path to liveness detection model
- `emotion_model_path`: Path to emotion recognition model

### Recognition Settings
- `recognition_threshold`: Minimum similarity for identity match (0.4-0.9, default: 0.6)
- `detection_confidence`: Minimum confidence for face detection (0.0-1.0, default: 0.5)

### Performance Settings
- `use_gpu`: Enable GPU acceleration (default: True)
- `target_fps`: Target frames per second (default: 10)

### Feature Toggles
- `enable_liveness`: Enable liveness detection (default: True)
- `enable_emotion`: Enable emotion recognition (default: True)
- `enable_tracking`: Enable face tracking (default: True)
- `enable_low_light_enhancement`: Enable low-light preprocessing (default: True)

### Tracking Settings
- `tracker_algorithm`: Tracking algorithm ("deepsort" or "bytetrack", default: "deepsort")
- `tracker_max_age`: Maximum frames to maintain track without detection (default: 30)

### Logging Settings
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL, default: "INFO")
- `log_file`: Path to log file (default: "guru_face/logs/guruvision.log")
- `log_max_size_mb`: Maximum log file size before rotation (default: 100)

## Event System

The engine emits events that can be subscribed to via callbacks:

### identity_recognized

Emitted when a known identity is recognized in a frame.

**Event Data:**
```python
{
    'timestamp': str,           # ISO format timestamp
    'frame_id': int,            # Frame number
    'tracking_id': int,         # Face tracking ID
    'identity': str,            # Identity name
    'confidence': float,        # Recognition confidence
    'permission_level': str,    # Permission level
    'emotion': str,             # Dominant emotion
    'emotion_confidence': float,# Emotion confidence
    'is_live': bool,            # Liveness result
    'liveness_confidence': float,# Liveness confidence
    'bbox': tuple               # Bounding box (x, y, w, h)
}
```

### system_ready

Emitted when the engine completes initialization.

**Event Data:**
```python
{
    'timestamp': str,           # ISO format timestamp
    'config': dict,             # Configuration dictionary
    'num_identities': int       # Number of loaded identities
}
```

### new_identity

Emitted when a new identity is added to the database.

**Note:** Implementation pending in task 20.

### permission_changed

Emitted when an identity's permission level is updated.

**Note:** Implementation pending in task 20.

### error

Emitted when an error occurs during processing.

**Note:** Implementation pending in task 23.

## Error Handling

The engine implements graceful degradation:

- **Liveness detection fails**: Continues without liveness check, logs warning
- **Emotion recognition fails**: Returns "neutral" with low confidence
- **Tracking fails**: Processes frames independently without tracking
- **Detection fails**: Returns empty result, logs error

All errors are logged with context for debugging.

## Performance

Expected performance metrics:

- **CPU-only**: 10+ FPS on modern CPU (16GB RAM)
- **GPU-accelerated**: 30+ FPS on NVIDIA RTX series
- **Initialization time**: < 5 seconds
- **Per-frame latency**: < 100ms
- **Memory usage**: < 4GB during normal operation

## Requirements

The engine satisfies the following requirements:

- **13.1, 13.2**: Python API for all recognition operations
- **31.1, 31.2**: Modular recognition engine with clear interfaces
- **20.1, 20.2**: System initialization and component loading
- **14.4**: Fast initialization (< 5 seconds)
- **3.1**: Real-time face detection
- **4.1**: Face alignment and normalization
- **5.1, 5.3**: Embedding extraction and identity matching
- **7.1, 7.4**: Liveness detection and recognition rejection
- **8.1**: Emotion recognition
- **10.1**: Face tracking across frames
- **22.1**: Low-light enhancement
- **13.2, 31.3**: Structured recognition results

## Examples

See `example_engine.py` for complete examples including:

1. Basic engine usage
2. Using callbacks for events
3. Custom configuration
4. Working with data structures

## Testing

Run the basic tests:

```bash
pytest guru_vision/test_engine_basic.py -v
```

## Next Steps

The following functionality will be implemented in subsequent tasks:

- **Task 20**: Identity management methods (add, remove, update)
- **Task 21**: Event system and callback registration
- **Task 22**: Shutdown and resource management
- **Task 23**: Error handling and recovery
- **Task 24**: Camera and video input support

## See Also

- [Configuration Module](../config.py)
- [Detection Module](detection/README.md)
- [Alignment Module](alignment/README.md)
- [Recognition Module](recognition/README.md)
- [Liveness Module](liveness/README.md)
- [Emotion Module](emotion/README.md)
- [Tracking Module](tracking/README.md)
- [Database Module](database/README.md)
