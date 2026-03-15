# GuruVision — Facial Recognition System

Real-time face detection, recognition, liveness detection, emotion recognition,
and multi-face tracking — all in one engine.

## Requirements

- Python 3.10+
- CUDA 11.8+ (recommended for GPU acceleration)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install onnxruntime-gpu opencv-python insightface numpy scikit-learn
```

CPU-only:
```bash
pip install torch torchvision onnxruntime opencv-python insightface numpy scikit-learn
```

## Quick Start

### 1. Train a model

```bash
python -m Agent_Guru.vision.examples.train_model \
    --dataset_dir path/to/dataset \
    --output_dir path/to/output
```

Dataset layout:
```
dataset/
    Alice/        # 50+ images per identity
        001.jpg
        002.jpg
    Bob/
        001.jpg
```

### 2. Add identities (no retraining needed)

```bash
python -m Agent_Guru.vision.examples.add_identity \
    --name "Alice" \
    --images photos/alice/*.jpg \
    --permission user
```

### 3. Real-time webcam recognition

```bash
python -m Agent_Guru.vision.examples.recognize_webcam --camera 0
```

Press `q` to quit.

## Python API

```python
from Agent_Guru.vision.engine import GuruVisionEngine
import numpy as np

engine = GuruVisionEngine()          # optional: config_path="config.yaml"
engine.initialize()

# Add an identity
import cv2
img = cv2.imread("alice.jpg")
engine.add_identity("Alice", [img], permission_level="user")

# Process a frame
frame = cv2.imread("frame.jpg")
result = engine.process_frame(frame)

for face in result.faces:
    print(face.identity, face.confidence, face.emotion)

engine.shutdown()
```

## Configuration

Create a `config.yaml` (all fields optional — defaults shown):

```yaml
onnx_model_path: Agent_Guru/vision/data/model/vision_model.onnx
database_path: Agent_Guru/vision/data/database/identities.json
recognition_threshold: 0.6      # 0.4–0.9
detection_confidence: 0.5       # 0.0–1.0
use_gpu: true
enable_liveness: true
enable_emotion: true
enable_tracking: true
enable_low_light_enhancement: true
tracker_max_age: 30
log_level: INFO
```

## Permission Levels

| Level   | Description                        |
|---------|------------------------------------|
| admin   | Full access                        |
| user    | Standard access                    |
| guest   | Read-only / limited access         |
| denied  | Access explicitly denied           |

## Event Callbacks

```python
engine.register_callback("identity_recognized", lambda d: print("Recognized:", d))
engine.register_callback("new_identity",        lambda d: print("New identity:", d))
engine.register_callback("permission_changed",  lambda d: print("Permission:", d))
engine.register_callback("error",               lambda d: print("Error:", d))
engine.register_callback("system_ready",        lambda d: print("Ready"))
```

## Performance Targets

| Metric              | Target      |
|---------------------|-------------|
| Face detection      | 30–60 FPS   |
| Recognition latency | < 50 ms     |
| Emotion latency     | < 50 ms     |
| Liveness detection  | Real-time   |

GPU (CUDA) is required to meet these targets in production.
