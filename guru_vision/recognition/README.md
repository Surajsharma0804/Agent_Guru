# GuruVision Face Recognition Module

This module provides face embedding extraction and identity matching using ONNX Runtime for fast, cross-platform inference.

## Overview

The recognition module is responsible for:
1. **Embedding Extraction**: Converting aligned face images into 512-dimensional feature vectors
2. **Identity Matching**: Comparing embeddings against a face database to identify individuals

## Components

### FaceRecognizer

The main class that handles embedding extraction and identity matching.

**Key Features:**
- ONNX Runtime inference for fast, cross-platform execution
- Support for both CPU and GPU acceleration
- L2-normalized embeddings for consistent similarity computation
- Integration with FaceDatabase for identity matching

### MatchResult

A dataclass representing the result of an identity matching operation.

**Attributes:**
- `identity`: Name of the matched identity or "Unknown"
- `confidence`: Similarity score (0.0 to 1.0)
- `permission_level`: Permission level of the matched identity

## Usage

### Basic Usage

```python
from guru_vision.recognition.recognizer import FaceRecognizer
from guru_vision.database.face_db import FaceDatabase
import numpy as np

# Initialize recognizer with ONNX model
recognizer = FaceRecognizer(
    model_path="guru_face/model/guru_face_model.onnx",
    use_gpu=True  # Use GPU if available
)

# Load face database
database = FaceDatabase("guru_face/database/identities.json")
database.load()

# Extract embedding from aligned face
aligned_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
embedding = recognizer.extract_embedding(aligned_face)

# Match against database
result = recognizer.match_identity(
    embedding=embedding,
    database=database,
    threshold=0.6
)

print(f"Identity: {result.identity}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Permission: {result.permission_level}")
```

### Complete Pipeline

```python
from guru_vision.detection.detector import FaceDetector
from guru_vision.alignment.aligner import FaceAligner
from guru_vision.recognition.recognizer import FaceRecognizer
from guru_vision.database.face_db import FaceDatabase
import cv2

# Initialize all components
detector = FaceDetector(use_gpu=True)
aligner = FaceAligner(output_size=(112, 112))
recognizer = FaceRecognizer("guru_face/model/guru_face_model.onnx", use_gpu=True)
database = FaceDatabase("guru_face/database/identities.json")
database.load()

# Process a frame
frame = cv2.imread("test_image.jpg")

# Detect faces
detections = detector.detect(frame)

for detection in detections:
    # Align face
    aligned_face = aligner.align(frame, detection)
    
    # Extract embedding
    embedding = recognizer.extract_embedding(aligned_face)
    
    # Match identity
    result = recognizer.match_identity(embedding, database, threshold=0.6)
    
    print(f"Detected: {result.identity} ({result.confidence:.2f})")
```

### GPU vs CPU

```python
# GPU acceleration (recommended for production)
recognizer_gpu = FaceRecognizer("model.onnx", use_gpu=True)

# CPU only (for systems without GPU)
recognizer_cpu = FaceRecognizer("model.onnx", use_gpu=False)

# Check which provider is active
print(f"Active provider: {recognizer_gpu.active_provider}")
```

### Custom Thresholds

```python
# Strict matching (fewer false positives)
result = recognizer.match_identity(embedding, database, threshold=0.8)

# Lenient matching (fewer false negatives)
result = recognizer.match_identity(embedding, database, threshold=0.5)

# Default threshold
result = recognizer.match_identity(embedding, database)  # threshold=0.6
```

## Requirements

### Dependencies

- `onnxruntime` or `onnxruntime-gpu`: ONNX Runtime for inference
- `numpy`: Numerical operations
- `opencv-python`: Image processing (for aligned face input)

### Model Requirements

The ONNX model must:
- Accept input shape: `(1, 3, 112, 112)` (batch, channels, height, width)
- Produce output shape: `(1, 512)` (batch, embedding_dim)
- Use normalized input range: `[-1, 1]`

## Technical Details

### Preprocessing

The `extract_embedding()` method performs the following preprocessing:

1. **Normalization**: Convert pixel values from `[0, 255]` to `[-1, 1]`
   - Formula: `(pixel / 127.5) - 1.0`

2. **Format Conversion**: Convert from HWC to CHW format
   - Input: `(112, 112, 3)` - Height, Width, Channels
   - Output: `(3, 112, 112)` - Channels, Height, Width

3. **Batch Dimension**: Add batch dimension
   - Output: `(1, 3, 112, 112)`

4. **L2 Normalization**: Normalize embedding to unit length
   - Ensures consistent cosine similarity computation

### Identity Matching

The `match_identity()` method:

1. Validates the embedding shape (must be 512-dimensional)
2. Calls `database.search()` with the embedding and threshold
3. Returns a `MatchResult` with:
   - Matched identity if similarity ≥ threshold
   - "Unknown" with guest permission if no match

### Performance

**Typical Performance:**
- CPU (Intel i7): ~20-30ms per embedding extraction
- GPU (RTX 3060): ~2-5ms per embedding extraction

**Memory Usage:**
- Model size: ~100-200MB (depending on architecture)
- Per-inference memory: ~10MB

## Error Handling

The module raises specific exceptions for different error conditions:

- `ImportError`: ONNX Runtime not installed
- `RuntimeError`: Model file not found or loading failed
- `ValueError`: Invalid input shape, threshold, or embedding

## Testing

Run the test suite:

```bash
pytest guru_vision/recognition/test_recognizer.py -v
```

## Related Modules

- **Detection Module**: Detects faces in images
- **Alignment Module**: Aligns faces to standard orientation
- **Database Module**: Stores and retrieves identity embeddings

## References

- ONNX Runtime: https://onnxruntime.ai/
- ArcFace Paper: https://arxiv.org/abs/1801.07698
- InsightFace: https://github.com/deepinsight/insightface
