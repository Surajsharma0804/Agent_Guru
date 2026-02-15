# GuruVision Face Tracking Module

Multi-object face tracking with stable tracking IDs across video frames.

## Overview

The tracking module maintains consistent identity tracking for faces across consecutive video frames using:
- **Kalman Filter**: Predicts face positions based on motion model
- **Hungarian Algorithm**: Associates detections with existing tracks
- **Track Management**: Creates, updates, and deletes tracks based on detection history

## Features

- ✅ Stable tracking IDs that persist across frames
- ✅ Motion prediction using Kalman filter
- ✅ Optimal detection-to-track association
- ✅ Handles temporary occlusions (configurable max_age)
- ✅ Multi-face tracking support
- ✅ Automatic track creation and deletion

## Requirements

Validates requirements:
- 10.1: Consistent tracking ID assignment
- 10.2: Track persistence for temporarily absent faces
- 10.3: Position updates while preserving tracking ID
- 10.4: Recognition on tracked faces
- 10.5: Independent tracking for multiple faces
- 10.6: Track ID release after timeout
- 23.1-23.6: Advanced tracking with motion prediction

## Quick Start

```python
from guru_vision.detection import FaceDetector
from guru_vision.tracking import FaceTracker

# Initialize detector and tracker
detector = FaceDetector()
tracker = FaceTracker(max_age=30)  # Keep tracks for 30 frames without detection

# Process video frames
for frame in video_frames:
    # Detect faces
    detections = detector.detect(frame)
    
    # Update tracker
    tracks = tracker.update(detections)
    
    # Use tracking information
    for track in tracks:
        print(f"Track ID: {track.tracking_id}")
        print(f"Position: {track.bbox}")
        print(f"Age: {track.age} frames since last detection")
        print(f"Hits: {track.hits} total detections")
```

## Classes

### FaceTracker

Main tracking class that maintains tracks across frames.

**Constructor:**
```python
FaceTracker(algorithm: str = "kalman", max_age: int = 30)
```

**Parameters:**
- `algorithm`: Tracking algorithm ("kalman", "deepsort", "bytetrack")
  - Currently only "kalman" is implemented
- `max_age`: Maximum frames to keep track without detection (default: 30)
  - At 10 FPS, max_age=30 means 3 seconds
  - At 30 FPS, max_age=30 means 1 second

**Methods:**

#### update()
```python
update(detections: List[Detection], frame: Optional[np.ndarray] = None) -> List[Track]
```

Update tracks with new detections. This is the main method called each frame.

**Process:**
1. Predict track positions using Kalman filter
2. Associate detections with tracks using Hungarian algorithm
3. Update matched tracks with new measurements
4. Create new tracks for unmatched detections
5. Increment age for unmatched tracks
6. Delete tracks exceeding max_age

**Parameters:**
- `detections`: List of Detection objects from face detector
- `frame`: Optional frame image (not used in current implementation)

**Returns:**
- List of active Track objects

#### get_track_by_id()
```python
get_track_by_id(tracking_id: int) -> Optional[Track]
```

Retrieve a specific track by its ID.

#### reset()
```python
reset()
```

Clear all tracks and reset ID counter.

### Track

Dataclass representing a tracked face.

**Attributes:**
- `tracking_id` (int): Unique identifier for this track
- `bbox` (Tuple[int, int, int, int]): Current bounding box (x, y, w, h)
- `age` (int): Frames since last detection (0 = just detected)
- `hits` (int): Total successful detections
- `state` (np.ndarray): Kalman filter state vector [x, y, w, h, vx, vy, vw, vh]
- `covariance` (np.ndarray): Kalman filter covariance matrix

### KalmanFilter

Kalman filter for bounding box motion prediction.

**State Vector:** [x, y, w, h, vx, vy, vw, vh]
- x, y: Center coordinates
- w, h: Width and height
- vx, vy, vw, vh: Velocities

**Methods:**
- `initiate(measurement)`: Initialize track from first detection
- `predict(state, covariance)`: Predict next state
- `update(state, covariance, measurement)`: Update with new measurement

## Tracking Pipeline

```
Frame N
  ↓
Detect Faces → [Detection 1, Detection 2, ...]
  ↓
Predict Track Positions (Kalman Filter)
  ↓
Associate Detections ↔ Tracks (Hungarian Algorithm)
  ↓
Update Matched Tracks
  ↓
Create New Tracks (Unmatched Detections)
  ↓
Age Unmatched Tracks
  ↓
Delete Old Tracks (age > max_age)
  ↓
Return Active Tracks → [Track 1, Track 2, ...]
```

## Configuration

### max_age Parameter

Controls how long tracks persist without detection:

```python
# Short persistence (1 second at 10 FPS)
tracker = FaceTracker(max_age=10)

# Medium persistence (3 seconds at 10 FPS) - DEFAULT
tracker = FaceTracker(max_age=30)

# Long persistence (5 seconds at 10 FPS)
tracker = FaceTracker(max_age=50)
```

**Guidelines:**
- **Low max_age (10-15)**: Fast-moving scenes, minimize false tracks
- **Medium max_age (30)**: General purpose, handles brief occlusions
- **High max_age (50+)**: Slow-moving scenes, frequent occlusions

### IoU Threshold

Internal parameter for detection-track association:

```python
tracker.iou_threshold = 0.3  # Default
```

Lower values = more strict matching (fewer false associations)
Higher values = more lenient matching (better for fast motion)

## Examples

### Example 1: Basic Tracking

```python
from guru_vision.detection import FaceDetector
from guru_vision.tracking import FaceTracker
import cv2

detector = FaceDetector()
tracker = FaceTracker()

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Detect and track
    detections = detector.detect(frame)
    tracks = tracker.update(detections)
    
    # Draw tracks
    for track in tracks:
        x, y, w, h = track.bbox
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, f"ID: {track.tracking_id}", (x, y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    cv2.imshow('Tracking', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### Example 2: Track-Specific Recognition

```python
from guru_vision.detection import FaceDetector
from guru_vision.tracking import FaceTracker
from guru_vision.recognition import FaceRecognizer
from guru_vision.database import FaceDatabase

detector = FaceDetector()
tracker = FaceTracker()
recognizer = FaceRecognizer("model.onnx")
database = FaceDatabase()

# Track recognition results per ID
track_identities = {}

for frame in video_frames:
    detections = detector.detect(frame)
    tracks = tracker.update(detections)
    
    for track, detection in zip(tracks, detections):
        # Only recognize once per second (every 10 frames at 10 FPS)
        if track.hits % 10 == 1:
            # Extract and recognize
            aligned_face = aligner.align(frame, detection)
            embedding = recognizer.extract_embedding(aligned_face)
            match = recognizer.match_identity(embedding, database)
            
            # Store result for this track
            track_identities[track.tracking_id] = match.identity
        
        # Use stored identity
        identity = track_identities.get(track.tracking_id, "Unknown")
        print(f"Track {track.tracking_id}: {identity}")
```

### Example 3: Track Statistics

```python
tracker = FaceTracker()

# Process video
for frame in video_frames:
    detections = detector.detect(frame)
    tracks = tracker.update(detections)

# Get statistics
print(f"Total unique tracks: {tracker.next_id - 1}")
print(f"Currently active tracks: {len(tracker.tracks)}")

for track in tracker.tracks:
    print(f"Track {track.tracking_id}:")
    print(f"  Total detections: {track.hits}")
    print(f"  Frames since last seen: {track.age}")
    print(f"  Current position: {track.bbox}")
```

## Performance

### Computational Complexity

- **Prediction**: O(n) where n = number of tracks
- **Association**: O(n³) for Hungarian algorithm
- **Update**: O(n)
- **Overall**: O(n³) per frame

### Typical Performance

- **10 tracks**: ~1-2ms per frame
- **50 tracks**: ~5-10ms per frame
- **100 tracks**: ~20-30ms per frame

For most applications (1-10 faces), tracking overhead is negligible.

## Troubleshooting

### Issue: Tracks switch between faces

**Cause:** IoU threshold too high or faces too close together

**Solution:**
```python
tracker.iou_threshold = 0.2  # Lower threshold for stricter matching
```

### Issue: Tracks deleted too quickly

**Cause:** max_age too low for frame rate

**Solution:**
```python
# Increase max_age based on FPS
# For 30 FPS and 3-second persistence:
tracker = FaceTracker(max_age=90)
```

### Issue: Too many false tracks

**Cause:** max_age too high, creating tracks for noise

**Solution:**
```python
# Reduce max_age
tracker = FaceTracker(max_age=15)

# Or filter tracks by minimum hits
active_tracks = [t for t in tracks if t.hits >= 3]
```

### Issue: Tracks don't persist through occlusions

**Cause:** max_age too low for occlusion duration

**Solution:**
```python
# Increase max_age to handle longer occlusions
tracker = FaceTracker(max_age=50)
```

## Integration with GuruVision Pipeline

The tracking module integrates seamlessly with other GuruVision components:

```python
from guru_vision.detection import FaceDetector
from guru_vision.alignment import FaceAligner
from guru_vision.recognition import FaceRecognizer
from guru_vision.tracking import FaceTracker
from guru_vision.database import FaceDatabase

# Initialize all components
detector = FaceDetector()
aligner = FaceAligner()
recognizer = FaceRecognizer("model.onnx")
tracker = FaceTracker()
database = FaceDatabase()

# Process frame
detections = detector.detect(frame)
tracks = tracker.update(detections)

for track, detection in zip(tracks, detections):
    # Align and recognize
    aligned_face = aligner.align(frame, detection)
    embedding = recognizer.extract_embedding(aligned_face)
    match = recognizer.match_identity(embedding, database)
    
    print(f"Track {track.tracking_id}: {match.identity} ({match.confidence:.2f})")
```

## Future Enhancements

Potential improvements for future versions:

1. **DeepSORT Integration**: Use appearance features for better association
2. **ByteTrack Integration**: Faster tracking for real-time applications
3. **Multi-Camera Tracking**: Track across multiple camera views
4. **Track Smoothing**: Temporal smoothing of bounding boxes
5. **Trajectory Analysis**: Analyze movement patterns
6. **Re-identification**: Match tracks after long absences

## References

- **SORT**: Simple Online and Realtime Tracking
- **DeepSORT**: Deep Learning for Multi-Object Tracking
- **ByteTrack**: Multi-Object Tracking by Associating Every Detection Box
- **Kalman Filter**: Optimal state estimation for linear systems
- **Hungarian Algorithm**: Optimal assignment problem solution

## License

Part of the GuruVision Facial Recognition System.
