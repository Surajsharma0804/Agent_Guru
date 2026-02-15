# Preprocessing Utilities

This module provides image preprocessing utilities for the GuruVision facial recognition system, with a focus on low-light enhancement to improve recognition accuracy in challenging lighting conditions.

## Features

- **Low-Light Enhancement**: Automatically detects and enhances dark images using CLAHE (Contrast Limited Adaptive Histogram Equalization)
- **Brightness Detection**: Calculate mean brightness of frames
- **Adaptive Processing**: Only applies enhancement when needed (brightness < 50)
- **Performance Optimized**: Completes enhancement within 50ms per frame

## Requirements Satisfied

- **22.1**: Apply enhancement when mean pixel value < 50
- **22.2**: Use adaptive histogram equalization (CLAHE)
- **22.3**: Preserve facial features without artifacts
- **22.4**: Complete within 50ms per frame
- **22.5**: Skip enhancement when lighting is adequate

## Usage

### Basic Low-Light Enhancement

```python
import cv2
from guru_vision.utils import enhance_low_light

# Load a dark image
frame = cv2.imread('dark_image.jpg')

# Apply low-light enhancement
enhanced_frame, was_enhanced = enhance_low_light(frame)

if was_enhanced:
    print("Enhancement was applied")
    cv2.imwrite('enhanced_image.jpg', enhanced_frame)
else:
    print("Image was bright enough, no enhancement needed")
```

### Check Frame Brightness

```python
from guru_vision.utils import check_brightness

brightness = check_brightness(frame)
print(f"Mean brightness: {brightness:.2f}")

if brightness < 50:
    print("Frame is dark and would benefit from enhancement")
```

### Complete Preprocessing Pipeline

```python
from guru_vision.utils import preprocess_frame

# Apply all preprocessing with metadata
processed_frame, metadata = preprocess_frame(
    frame,
    enable_low_light_enhancement=True,
    brightness_threshold=50.0
)

print(f"Original brightness: {metadata['original_brightness']:.2f}")
if metadata['low_light_enhanced']:
    print(f"Enhanced brightness: {metadata['enhanced_brightness']:.2f}")
```

### Custom CLAHE Parameters

```python
# Fine-tune CLAHE parameters for specific use cases
enhanced_frame, was_enhanced = enhance_low_light(
    frame,
    brightness_threshold=50.0,  # Brightness threshold
    clip_limit=2.0,             # Contrast limiting
    tile_grid_size=(8, 8)       # Grid size for local enhancement
)
```

## API Reference

### `enhance_low_light(frame, brightness_threshold=50.0, clip_limit=2.0, tile_grid_size=(8, 8))`

Enhance low-light images using CLAHE.

**Parameters:**
- `frame` (np.ndarray): Input image in BGR format
- `brightness_threshold` (float): Mean brightness threshold (default: 50.0)
- `clip_limit` (float): Contrast limiting threshold (default: 2.0)
- `tile_grid_size` (tuple): Grid size for histogram equalization (default: (8, 8))

**Returns:**
- `enhanced_frame` (np.ndarray): Enhanced image or original if not needed
- `was_enhanced` (bool): Whether enhancement was applied

### `check_brightness(frame)`

Calculate the mean brightness of a frame.

**Parameters:**
- `frame` (np.ndarray): Input image in BGR or grayscale format

**Returns:**
- `brightness` (float): Mean brightness value (0-255)

### `preprocess_frame(frame, enable_low_light_enhancement=True, brightness_threshold=50.0)`

Apply all preprocessing steps to a frame.

**Parameters:**
- `frame` (np.ndarray): Input image in BGR format
- `enable_low_light_enhancement` (bool): Whether to apply enhancement
- `brightness_threshold` (float): Brightness threshold

**Returns:**
- `processed_frame` (np.ndarray): Preprocessed image
- `metadata` (dict): Preprocessing information including:
  - `low_light_enhanced` (bool): Whether enhancement was applied
  - `original_brightness` (float): Original brightness value
  - `enhanced_brightness` (float): Enhanced brightness (if applied)

## How CLAHE Works

CLAHE (Contrast Limited Adaptive Histogram Equalization) is an advanced image enhancement technique that:

1. **Divides the image into tiles**: The image is split into small regions (default 8x8 grid)
2. **Applies histogram equalization locally**: Each tile gets its own histogram equalization
3. **Limits contrast**: The `clip_limit` parameter prevents over-amplification of noise
4. **Interpolates boundaries**: Smooth transitions between tiles prevent visible grid artifacts

For color images, CLAHE is applied only to the L (lightness) channel in LAB color space, preserving color information while enhancing brightness and contrast.

## Performance Considerations

- **Processing Time**: Typically 10-30ms per frame on modern CPUs
- **Memory**: Minimal overhead, processes in-place when possible
- **Color Preservation**: Uses LAB color space to maintain natural colors
- **Artifact Prevention**: Contrast limiting prevents noise amplification

## Integration with GuruVision Pipeline

The preprocessing module integrates seamlessly with the GuruVision recognition pipeline:

```python
from guru_vision.utils import preprocess_frame
from guru_vision.detection import FaceDetector

# Initialize detector
detector = FaceDetector()

# Process frame with preprocessing
processed_frame, metadata = preprocess_frame(frame)

# Detect faces on enhanced frame
detections = detector.detect(processed_frame)
```

## Testing

Run the test suite:

```bash
pytest guru_vision/utils/test_preprocessing.py -v
```

## References

- CLAHE: Zuiderveld, K. (1994). "Contrast Limited Adaptive Histogram Equalization"
- OpenCV CLAHE Documentation: https://docs.opencv.org/master/d5/daf/tutorial_py_histogram_equalization.html
