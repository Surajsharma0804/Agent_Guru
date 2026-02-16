# GuruVision Facial Recognition System

A production-grade facial recognition system built on state-of-the-art deep learning models using ArcFace architecture from InsightFace. GuruVision provides real-time face recognition, liveness detection, emotion recognition, and face tracking for AI agent integration.

## Features

- **Face Detection**: RetinaFace for accurate multi-angle, low-light detection
- **Face Recognition**: Custom ArcFace model with 512-dimensional embeddings
- **Liveness Detection**: Silent-Face anti-spoofing to prevent photo/screen/mask attacks
- **Emotion Recognition**: 7-category facial expression classification
- **Face Tracking**: DeepSORT/ByteTrack for stable identity tracking across frames
- **Multi-Angle Memory**: Store multiple embeddings per identity for improved accuracy
- **Permission System**: Role-based access control (admin, user, guest, denied)
- **Incremental Updates**: Add new identities without retraining the model
- **Real-Time Performance**: 10+ FPS on CPU, 30+ FPS on GPU
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Training a Custom Model](#training-a-custom-model)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Installation

### Prerequisites

- **Python**: 3.8-3.11 (recommended: 3.10)
- **RAM**: 16GB minimum
- **GPU**: CUDA-capable NVIDIA GPU (optional, for acceleration)
- **OS**: Windows, Linux, or macOS

### Step 1: Create Virtual Environment

It's recommended to use a Python virtual environment to avoid dependency conflicts:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
# Clone the repository
git clone https://github.com/guruvision/guruvision.git
cd guruvision

# Install core dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

### Step 3: Verify Installation

```bash
# Run verification script
python verify_installation.py
```

This will check:
- Python version compatibility
- All dependencies are installed correctly
- GPU availability (if applicable)
- Basic functionality tests

### GPU Acceleration (Optional)

For GPU acceleration with CUDA:

```bash
# Install CUDA-enabled packages
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install onnxruntime-gpu
```

Verify GPU is available:

```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")
```

### CPU-Only Installation

For systems without GPU:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install onnxruntime
```

## Quick Start

### 1. Train Your Custom Model

First, prepare your dataset and train a custom face recognition model:

```bash
# Prepare dataset structure:
# dataset/
#   ├── PersonA/
#   │   ├── image001.jpg
#   │   ├── image002.jpg
#   │   └── ... (50-300 images recommended)
#   ├── PersonB/
#   │   └── ...
#   └── PersonC/
#       └── ...

# Run training pipeline
python train.py --dataset dataset/ --output guru_face/ --epochs 20
```

See [Training a Custom Model](#training-a-custom-model) for detailed instructions.

### 2. Real-Time Webcam Recognition

Once your model is trained, test it with your webcam:

```bash
python examples/recognize_webcam.py
```

### 3. Add New Identities (No Retraining Required)

Add new people to the system without retraining:

```bash
python examples/add_identity.py --name "John Doe" --images person_images/
```

### 4. Python API Usage

```python
from guru_vision.engine import GuruVisionEngine
import cv2

# Initialize engine
engine = GuruVisionEngine(config_path="config.yaml")
engine.initialize()

# Process a frame
cap = cv2.VideoCapture(0)
ret, frame = cap.read()

result = engine.process_frame(frame)

# Access recognition results
for face in result.faces:
    print(f"Identity: {face.identity}")
    print(f"Confidence: {face.confidence:.2f}")
    print(f"Permission: {face.permission_level}")
    print(f"Emotion: {face.emotion}")
    print(f"Is Live: {face.is_live}")

# Cleanup
engine.shutdown()
cap.release()
```

## Training a Custom Model

### Dataset Preparation

1. **Organize your dataset**:
   ```
   dataset/
     ├── PersonA/
     │   ├── image001.jpg
     │   ├── image002.jpg
     │   └── ... (50-300 images)
     ├── PersonB/
     │   └── ...
     └── PersonC/
         └── ...
   ```

2. **Dataset requirements**:
   - **Minimum**: 50 images per person
   - **Recommended**: 100-300 images per person
   - **Image quality**: At least 640x480 pixels
   - **Variety**: Include different angles, lighting, and expressions
   - **Formats**: JPEG, PNG, or BMP

3. **Tips for best results**:
   - Include frontal, profile, and 45-degree angles
   - Capture in various lighting conditions
   - Include different facial expressions
   - Ensure faces are clearly visible
   - Avoid heavy occlusions

### Training Pipeline

Run the complete training pipeline:

```bash
python train.py --dataset dataset/ --output guru_face/
```

**Options**:
```bash
# Custom hyperparameters
python train.py --dataset dataset/ --output guru_face/ \
  --epochs 30 --batch-size 64 --lr 0.05

# CPU-only training
python train.py --dataset dataset/ --output guru_face/ --no-gpu

# Skip preprocessing (if already done)
python train.py --dataset dataset/ --output guru_face/ --skip-preprocess
```

The training pipeline will:
1. Validate dataset structure
2. Detect and align faces (preprocessing)
3. Train ArcFace model with ResNet-50 backbone
4. Export model to ONNX format
5. Validate ONNX model equivalence
6. Generate training report

**Training time**: 2-6 hours depending on dataset size and hardware.

### Training Output

After training completes, you'll have:
- `guru_face/model/guru_face_model.pth` - PyTorch model
- `guru_face/model/guru_face_model.onnx` - ONNX model (for production)
- `guru_face/aligned_dataset/` - Preprocessed faces
- `guru_face/checkpoints/` - Training checkpoints
- `guru_face/reports/` - Training statistics
- `guru_face/logs/` - Training logs

## Usage Examples

### Example 1: Real-Time Webcam Recognition

```bash
python examples/recognize_webcam.py
```

**Controls**:
- Press `q` or `ESC` to quit
- Press `s` to take a screenshot
- Press `p` to pause/resume

### Example 2: Add New Identity

```bash
# Interactive mode
python examples/add_identity.py

# Command-line mode
python examples/add_identity.py --name "Jane Smith" --images person_images/ --permission admin
```

### Example 3: Process Video File

```python
from guru_vision.engine import GuruVisionEngine
import cv2

engine = GuruVisionEngine()
engine.initialize()

cap = cv2.VideoCapture("video.mp4")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    result = engine.process_frame(frame)
    
    # Process results
    for face in result.faces:
        print(f"{face.identity}: {face.confidence:.2f}")

engine.shutdown()
cap.release()
```

### Example 4: Event Callbacks

```python
from guru_vision.engine import GuruVisionEngine

def on_identity_recognized(event_data):
    print(f"Recognized: {event_data['identity']}")
    print(f"Permission: {event_data['permission_level']}")

engine = GuruVisionEngine()
engine.initialize()

# Register callback
engine.register_callback('identity_recognized', on_identity_recognized)

# Process frames...
```

## Configuration

GuruVision can be configured via YAML or JSON files:

### Example Configuration (config.yaml)

```yaml
# Model paths
onnx_model_path: "guru_face/model/guru_face_model.onnx"
database_path: "guru_face/database/identities.json"

# Recognition settings
recognition_threshold: 0.6  # 0.4-0.9
detection_confidence: 0.5

# Performance settings
use_gpu: true
target_fps: 10

# Feature toggles
enable_liveness: true
enable_emotion: true
enable_tracking: true
enable_low_light_enhancement: true

# Tracking settings
tracker_algorithm: "deepsort"  # or "bytetrack"
tracker_max_age: 30  # frames

# Logging
log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
log_file: "guru_face/logs/guruvision.log"
log_max_size_mb: 100

# Camera settings
camera_index: 0
video_source: null  # or path to video file
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `recognition_threshold` | float | 0.6 | Minimum similarity for identity match (0.4-0.9) |
| `detection_confidence` | float | 0.5 | Minimum confidence for face detection |
| `use_gpu` | bool | true | Enable GPU acceleration |
| `enable_liveness` | bool | true | Enable anti-spoofing detection |
| `enable_emotion` | bool | true | Enable emotion recognition |
| `enable_tracking` | bool | true | Enable face tracking |
| `tracker_algorithm` | string | "deepsort" | Tracking algorithm (deepsort/bytetrack) |
| `log_level` | string | "INFO" | Logging level |

## API Reference

### GuruVisionEngine

Main API class for face recognition operations.

#### Methods

**`initialize()`**
- Initialize all subsystems and load models
- Raises: `RuntimeError` if initialization fails

**`process_frame(frame: np.ndarray) -> RecognitionResult`**
- Process a single video frame
- Args: `frame` - BGR image array from OpenCV
- Returns: `RecognitionResult` with detected faces

**`add_identity(name: str, images: List[np.ndarray], permission_level: str = "user") -> bool`**
- Add new identity without retraining
- Args:
  - `name` - Identity name
  - `images` - List of face images
  - `permission_level` - Permission level (admin/user/guest/denied)
- Returns: `True` if successful

**`remove_identity(name: str) -> bool`**
- Remove identity and all embeddings
- Returns: `True` if successful

**`get_identities() -> List[IdentityInfo]`**
- Query all stored identities
- Returns: List of identity information

**`update_permission(name: str, permission_level: str) -> bool`**
- Update permission level for an identity
- Returns: `True` if successful

**`register_callback(event_type: str, callback: Callable) -> None`**
- Register callback for recognition events
- Event types: `identity_recognized`, `new_identity`, `permission_changed`, `error`

**`shutdown() -> None`**
- Clean shutdown and release resources

### Data Structures

**`RecognitionResult`**
```python
@dataclass
class RecognitionResult:
    faces: List[FaceResult]
    frame_id: int
    timestamp: str
    processing_time_ms: float
```

**`FaceResult`**
```python
@dataclass
class FaceResult:
    tracking_id: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    identity: str
    confidence: float
    permission_level: str
    emotion: str
    emotion_confidence: float
    is_live: bool
    liveness_confidence: float
```

## Project Structure

```
guruvision/
├── guru_vision/              # Main package
│   ├── detection/            # Face detection (RetinaFace)
│   │   ├── detector.py
│   │   └── test_detector.py
│   ├── alignment/            # Face alignment
│   │   ├── aligner.py
│   │   └── test_aligner.py
│   ├── recognition/          # Face recognition (ArcFace)
│   │   ├── recognizer.py
│   │   └── test_recognizer.py
│   ├── liveness/             # Liveness detection
│   │   ├── detector.py
│   │   └── test_detector.py
│   ├── emotion/              # Emotion recognition
│   │   ├── recognizer.py
│   │   └── test_recognizer.py
│   ├── tracking/             # Face tracking
│   │   ├── tracker.py
│   │   └── test_tracker.py
│   ├── database/             # Database management
│   │   ├── face_db.py
│   │   └── test_face_db.py
│   ├── training/             # Training pipeline
│   │   ├── preprocess.py
│   │   ├── train.py
│   │   ├── export.py
│   │   └── tests/
│   ├── utils/                # Utilities
│   │   ├── logging.py
│   │   ├── preprocessing.py
│   │   └── tests/
│   ├── config.py             # Configuration management
│   ├── engine.py             # Main recognition engine
│   └── exceptions.py         # Custom exceptions
├── guru_face/                # Data directory
│   ├── model/                # Trained models
│   ├── database/             # Identity database
│   ├── logs/                 # System logs
│   └── checkpoints/          # Training checkpoints
├── examples/                 # Usage examples
│   ├── train_model.py
│   ├── recognize_webcam.py
│   └── add_identity.py
├── train.py                  # Main training script
├── requirements.txt          # Dependencies
├── pyproject.toml            # Package configuration
└── README.md                 # This file
```

## Performance

### Benchmarks

| Hardware | FPS | Latency | Memory |
|----------|-----|---------|--------|
| CPU (Intel i7) | 10-15 | 80ms | 2.5GB |
| GPU (RTX 3060) | 30-40 | 25ms | 3.5GB |
| GPU (RTX 4090) | 60+ | 15ms | 4.0GB |

### Performance Tips

1. **Use GPU acceleration** for 3x faster processing
2. **Disable unused features** (emotion, liveness) if not needed
3. **Adjust target FPS** based on your requirements
4. **Use ONNX model** instead of PyTorch for 50% speedup
5. **Reduce detection confidence** for faster but less accurate detection

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'insightface'`
- **Solution**: Install InsightFace: `pip install insightface`

**Issue**: `CUDA out of memory`
- **Solution**: Reduce batch size or use CPU mode

**Issue**: `No faces detected in images`
- **Solution**: Check image quality, ensure faces are visible and well-lit

**Issue**: `Model file not found`
- **Solution**: Run training first: `python train.py --dataset dataset/ --output guru_face/`

**Issue**: `Camera not opening`
- **Solution**: Try different camera index: `--camera 1` or check camera permissions

**Issue**: `Low FPS performance`
- **Solution**: Enable GPU, reduce target FPS, or disable optional features

### Debug Mode

Enable debug logging for troubleshooting:

```python
from guru_vision.engine import GuruVisionEngine

engine = GuruVisionEngine()
engine.config.log_level = "DEBUG"
engine.initialize()
```

Or via configuration file:
```yaml
log_level: "DEBUG"
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific module tests
pytest guru_vision/detection/

# Run with coverage
pytest --cov=guru_vision --cov-report=html
```

### Code Formatting

```bash
# Format code
black guru_vision/

# Check formatting
black --check guru_vision/

# Sort imports
isort guru_vision/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run tests and formatting
6. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [InsightFace](https://github.com/deepinsight/insightface) - ArcFace implementation and research
- [RetinaFace](https://github.com/serengil/retinaface) - Face detection
- [ONNX Runtime](https://onnxruntime.ai/) - Optimized inference
- [DeepSORT](https://github.com/nwojke/deep_sort) - Multi-object tracking
- [PyTorch](https://pytorch.org/) - Deep learning framework

## Citation

If you use GuruVision in your research, please cite:

```bibtex
@software{guruvision2024,
  title={GuruVision: Production-Grade Facial Recognition System},
  author={GuruVision Team},
  year={2024},
  url={https://github.com/guruvision/guruvision}
}
```

## Support

- **Documentation**: See module-specific README files in each directory
- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Join GitHub Discussions for questions

## Roadmap

- [ ] Multi-GPU training support
- [ ] Real-time video streaming support
- [ ] REST API for remote recognition
- [ ] Docker containerization
- [ ] Model quantization for edge devices
- [ ] Additional backbone architectures
- [ ] Face attribute recognition (age, gender)
- [ ] 3D face reconstruction
