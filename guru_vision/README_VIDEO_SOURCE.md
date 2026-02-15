# GuruVision Video Source Support

This document describes the video source functionality in GuruVision, which provides unified support for multiple input types including webcams, video files, images, and image directories.

## Overview

The video source module provides a flexible interface for capturing frames from various sources:

- **Webcam**: Real-time capture from camera devices
- **Video Files**: Playback from MP4, AVI, MOV, and other formats
- **Image Files**: Single image processing
- **Image Directories**: Sequential processing of image collections

## Requirements

This implementation satisfies the following requirements:

- **Requirement 19.1**: Support webcam input using device index or device name
- **Requirement 19.2**: Support video file input in common formats (MP4, AVI, MOV)
- **Requirement 19.3**: Support processing individual image files
- **Requirement 19.4**: Support processing directories of images as image sequences
- **Requirement 19.5**: Return clear error if source unavailable
- **Requirement 19.6**: Auto-detect resolution and frame rate
- **Requirement 19.7**: Support seeking in video files

## Basic Usage

### Using VideoSource Directly

```python
from guru_vision.video_source import VideoSource

# Webcam input
with VideoSource(source=None, camera_index=0) as vs:
    success, frame = vs.read()
    if success:
        # Process frame
        pass

# Video file input
with VideoSource(source="video.mp4") as vs:
    info = vs.get_info()
    print(f"Resolution: {info['resolution']}, FPS: {info['fps']}")
    
    # Read frames
    while True:
        success, frame = vs.read()
        if not success:
            break
        # Process frame

# Image file input
with VideoSource(source="image.jpg") as vs:
    success, frame = vs.read()
    # Process single image

# Image directory input
with VideoSource(source="images/") as vs:
    # Read all images in sequence
    while True:
        success, frame = vs.read()
        if not success:
            break
        # Process frame
```

### Using with GuruVisionEngine

```python
from guru_vision.engine import GuruVisionEngine

# Initialize engine
engine = GuruVisionEngine()
engine.initialize()

# Initialize video source
engine.init_video_source(source="path/to/images")

# Get video information
info = engine.get_video_info()
print(f"Source type: {info['source_type']}")
print(f"Resolution: {info['resolution']}")
print(f"Total frames: {info['total_frames']}")

# Read and process frames
while True:
    success, frame = engine.read_frame()
    if not success:
        break
    
    # Process through recognition pipeline
    result = engine.process_frame(frame)
    
    # Handle results
    for face in result.faces:
        print(f"{face.identity}: {face.confidence:.2f}")

# Seek to specific frame (video files and image sequences only)
engine.seek_frame(100)

# Shutdown
engine.shutdown()
```

## Supported Source Types

### 1. Webcam Input

**Requirement 19.1**: Support webcam by device index or name

```python
# By device index (default camera)
vs = VideoSource(source=None, camera_index=0)

# By device index (second camera)
vs = VideoSource(source=1)

# By numeric string
vs = VideoSource(source="0")
```

**Features**:
- Auto-detects resolution and frame rate
- Real-time capture
- No seeking support (live stream)

### 2. Video File Input

**Requirement 19.2**: Support video file paths (MP4, AVI, MOV)

```python
vs = VideoSource(source="video.mp4")
```

**Supported formats**:
- MP4 (.mp4)
- AVI (.avi)
- MOV (.mov)
- MKV (.mkv)
- FLV (.flv)
- WMV (.wmv)

**Features**:
- Auto-detects resolution, frame rate, and total frames
- Supports seeking to specific frames
- Frame-by-frame playback

### 3. Image File Input

**Requirement 19.3**: Support image files

```python
vs = VideoSource(source="image.jpg")
```

**Supported formats**:
- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- TIFF (.tiff, .tif)

**Features**:
- Single frame read
- Auto-detects resolution
- Supports seeking to frame 0

### 4. Image Directory Input

**Requirement 19.4**: Support image directories

```python
vs = VideoSource(source="images/")
```

**Features**:
- Processes all images in directory
- Images sorted alphabetically by filename
- Auto-detects resolution from first image
- Supports seeking to any frame
- Default FPS: 10.0

## Video Source Information

**Requirement 19.6**: Auto-detect resolution and frame rate

```python
info = vs.get_info()

# Returns dictionary with:
# - source_type: Type of video source
# - resolution: (width, height) tuple
# - fps: Frames per second
# - total_frames: Total number of frames (None for webcam)
# - current_frame: Current frame position (-1 for webcam)
```

## Seeking

**Requirement 19.7**: Support seeking in video files

```python
# Seek to frame 100
success = vs.seek(100)

# Get current position
position = vs.get_position()

# Seeking is supported for:
# - Video files
# - Image files (frame 0 only)
# - Image directories

# Seeking is NOT supported for:
# - Webcam (live stream)
```

## Error Handling

**Requirement 19.5**: Return clear error if source unavailable

```python
from guru_vision.video_source import VideoSourceError

try:
    vs = VideoSource(source="nonexistent.mp4")
    vs.open()
except VideoSourceError as e:
    print(f"Error: {e}")
    # Clear error message indicating the problem
```

**Common errors**:
- `Path does not exist`: File or directory not found
- `Unsupported file format`: File extension not supported
- `No image files found`: Empty directory
- `Webcam not available`: Camera not connected or in use
- `Failed to load image file`: Corrupted image file

## Context Manager Support

VideoSource supports Python's context manager protocol for automatic resource cleanup:

```python
with VideoSource(source="video.mp4") as vs:
    # Use video source
    success, frame = vs.read()
    # Resources automatically released on exit
```

## Resource Management

Always release video sources when done:

```python
vs = VideoSource(source="video.mp4")
vs.open()

try:
    # Use video source
    pass
finally:
    vs.release()  # Release resources
```

Or use context manager (recommended):

```python
with VideoSource(source="video.mp4") as vs:
    # Automatic cleanup
    pass
```

## Integration with GuruVisionEngine

The GuruVisionEngine provides high-level methods for video source management:

### Initialization

```python
# Initialize with default config
engine.init_video_source()

# Initialize with specific source
engine.init_video_source(source="video.mp4")

# Initialize with camera index override
engine.init_video_source(source=None, camera_index=1)
```

### Reading Frames

```python
success, frame = engine.read_frame()
```

### Seeking

```python
success = engine.seek_frame(100)
```

### Getting Information

```python
info = engine.get_video_info()
```

### Shutdown

The engine automatically releases video sources during shutdown:

```python
engine.shutdown()  # Releases video source
```

## Examples

See `example_video_source.py` for complete working examples of:

1. Webcam input
2. Video file input
3. Image file input
4. Image directory input
5. Error handling
6. Engine integration

Run the examples:

```bash
python guru_vision/example_video_source.py
```

## Testing

Comprehensive tests are provided in:

- `test_video_source.py`: Tests for VideoSource class
- `test_engine_video_source.py`: Tests for engine integration

Run tests:

```bash
# Test VideoSource class
pytest guru_vision/test_video_source.py -v

# Test engine integration
pytest guru_vision/test_engine_video_source.py -v

# Run all video source tests
pytest guru_vision/test_*video_source.py -v
```

## Performance Considerations

### Webcam

- Real-time capture depends on camera capabilities
- Default FPS reported by camera (typically 30 FPS)
- No buffering - always reads latest frame

### Video Files

- Seeking may be slow for some formats
- Frame-accurate seeking depends on video codec
- Consider using keyframe-aligned seeking for better performance

### Image Directories

- All images loaded on-demand (not pre-loaded)
- Seeking is instant (just changes index)
- Memory efficient for large image collections

## Troubleshooting

### Webcam not detected

```python
# Try different camera indices
for i in range(5):
    try:
        vs = VideoSource(source=None, camera_index=i)
        vs.open()
        print(f"Camera found at index {i}")
        vs.release()
        break
    except VideoSourceError:
        continue
```

### Video file won't open

- Check file exists and path is correct
- Verify file format is supported
- Ensure file is not corrupted
- Check OpenCV installation includes video codec support

### Image directory empty

- Verify directory contains image files
- Check file extensions match supported formats
- Ensure files are readable

## API Reference

### VideoSource Class

```python
class VideoSource:
    def __init__(self, source: Optional[str] = None, camera_index: int = 0)
    def open(self) -> bool
    def read(self) -> Tuple[bool, Optional[np.ndarray]]
    def seek(self, frame_number: int) -> bool
    def get_position(self) -> int
    def get_info(self) -> dict
    def release(self) -> None
```

### GuruVisionEngine Methods

```python
def init_video_source(self, source: Optional[str] = None, 
                     camera_index: Optional[int] = None) -> bool
def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]
def seek_frame(self, frame_number: int) -> bool
def get_video_info(self) -> dict
```

## Configuration

Video source settings in `GuruVisionConfig`:

```python
@dataclass
class GuruVisionConfig:
    # Camera settings
    camera_index: int = 0          # Default camera device index
    video_source: Optional[str] = None  # Path to video file or None for webcam
```

Load from config file:

```yaml
# config.yaml
camera_index: 0
video_source: null  # or "path/to/video.mp4"
```

## Future Enhancements

Potential future additions:

- RTSP stream support
- HTTP video stream support
- Frame buffering for smoother playback
- Multi-camera support
- Video recording/saving
- Frame rate limiting
- Resolution scaling

## Related Documentation

- [Engine Documentation](README_ENGINE.md)
- [Configuration Management](../config.py)
- [Error Handling](../exceptions.py)
