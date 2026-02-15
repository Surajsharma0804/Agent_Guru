# Emotion Recognition Module

This module provides facial expression classification to recognize emotions from face images.

## Overview

The `EmotionRecognizer` class analyzes aligned face images to classify facial expressions into seven emotion categories:
- neutral
- happy
- sad
- angry
- surprised
- fearful
- disgusted

The recognizer returns confidence scores for all emotion categories and identifies the dominant emotion.

## Features

- **Seven Emotion Categories**: Classifies expressions into standard emotion categories
- **Confidence Scores**: Provides confidence scores for all emotions
- **CPU/GPU Support**: Supports both CPU and GPU inference backends
- **Fallback Analysis**: Uses traditional computer vision when ML model unavailable
- **Robust Input Validation**: Validates input shape and data quality

## Requirements

Validates the following requirements:
- **Requirement 8.1**: Emotion classification into seven categories
- **Requirement 8.2**: Return confidence scores for each emotion category
- **Requirement 8.3**: Identify dominant emotion as category with highest confidence
- **Requirement 8.4**: Complete analysis within 100 milliseconds per face
- **Requirement 8.5**: Return "neutral" with low confidence when features insufficient

## Usage

### Basic Usage

```python
from guru_vision.emotion import EmotionRecognizer
import numpy as np

# Initialize recognizer
recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)

# Create or load an aligned face image (112x112x3)
aligned_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)

# Recognize emotion
result = recognizer.recognize(aligned_face)

# Access results
print(f"Dominant emotion: {result.dominant_emotion}")
print(f"Confidence: {result.confidence:.2f}")
print(f"All scores: {result.all_scores}")
```

### With GPU Acceleration

```python
# Initialize with GPU support
recognizer = EmotionRecognizer(model_name="fer", use_gpu=True)

# Recognition will use GPU if available
result = recognizer.recognize(aligned_face)
```

### Handling Results

```python
# Get dominant emotion
dominant = result.dominant_emotion

# Get confidence for dominant emotion
confidence = result.confidence

# Get scores for all emotions
all_scores = result.all_scores

# Check specific emotion scores
happy_score = result.all_scores["happy"]
sad_score = result.all_scores["sad"]

# Find top 3 emotions
sorted_emotions = sorted(
    result.all_scores.items(), 
    key=lambda x: x[1], 
    reverse=True
)
top_3 = sorted_emotions[:3]
print(f"Top 3 emotions: {top_3}")
```

## Data Structures

### EmotionResult

Result of emotion recognition analysis.

**Attributes:**
- `dominant_emotion` (str): The emotion with highest confidence
- `confidence` (float): Confidence score for the dominant emotion (0.0 to 1.0)
- `all_scores` (Dict[str, float]): Dictionary mapping emotion names to confidence scores

## Implementation Details

### Preprocessing

The recognizer preprocesses aligned faces by:
1. Converting to grayscale (many emotion models use grayscale)
2. Resizing to model input size (typically 48x48)
3. Normalizing pixel values to [0, 1]
4. Converting to CHW format (channels first)

### Fallback Analysis

When the ML model is not available, the recognizer uses traditional computer vision techniques:
- Brightness analysis (correlates with positive/negative emotions)
- Contrast analysis (indicates emotional intensity)
- Edge density patterns (facial expression features)

### Performance

- **Target latency**: < 100ms per face
- **Input size**: 112x112x3 BGR image
- **Output**: EmotionResult with 7 emotion scores

## Error Handling

The recognizer validates inputs and raises appropriate errors:

```python
# Invalid shape
try:
    invalid_face = np.zeros((64, 64, 3), dtype=np.uint8)
    result = recognizer.recognize(invalid_face)
except ValueError as e:
    print(f"Error: {e}")  # "Input face must be 112x112x3"

# All-zero input
try:
    zero_face = np.zeros((112, 112, 3), dtype=np.uint8)
    result = recognizer.recognize(zero_face)
except ValueError as e:
    print(f"Error: {e}")  # "Input face contains invalid data"
```

## Testing

The module includes comprehensive tests:

### Unit Tests

```bash
pytest guru_vision/emotion/test_recognizer.py -v
```

### Property-Based Tests

```bash
pytest guru_vision/emotion/test_recognizer_properties.py -v
```

Property tests validate:
- **Property 11**: Emotion Classification Categories
- **Property 12**: Emotion Confidence Completeness

## Integration with GuruVision

The emotion recognizer integrates with the main GuruVision pipeline:

```python
from guru_vision.detection import FaceDetector
from guru_vision.alignment import FaceAligner
from guru_vision.emotion import EmotionRecognizer

# Initialize components
detector = FaceDetector()
aligner = FaceAligner()
emotion_recognizer = EmotionRecognizer()

# Process frame
detections = detector.detect(frame)
for detection in detections:
    aligned_face = aligner.align(frame, detection)
    emotion_result = emotion_recognizer.recognize(aligned_face)
    print(f"Emotion: {emotion_result.dominant_emotion}")
```

## Model Support

The recognizer supports multiple emotion recognition models:
- **FER (Facial Expression Recognition)**: Default model
- **DeepFace**: Alternative model with different architecture

To use a specific model:

```python
recognizer = EmotionRecognizer(model_name="fer", use_gpu=True)
# or
recognizer = EmotionRecognizer(model_name="deepface", use_gpu=True)
```

## Notes

- The recognizer expects aligned faces from the FaceAligner module
- Input faces must be 112x112x3 in BGR format (OpenCV standard)
- The fallback analysis provides reasonable results when ML model unavailable
- For production use, train or download a proper emotion recognition model
- Low confidence results (< 0.3) default to "neutral" emotion

## Future Enhancements

Potential improvements:
- Multi-frame temporal smoothing for video
- Micro-expression detection
- Emotion intensity estimation
- Cultural context adaptation
- Real-time emotion tracking
