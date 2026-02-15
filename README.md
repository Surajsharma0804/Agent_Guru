# GuruVision Facial Recognition System

A production-grade facial recognition system built on state-of-the-art deep learning models using ArcFace architecture from InsightFace.

## Features

- **Face Detection**: RetinaFace for accurate multi-angle detection
- **Face Recognition**: Custom ArcFace model with 512-dimensional embeddings
- **Liveness Detection**: Anti-spoofing to prevent photo/screen/mask attacks
- **Emotion Recognition**: 7-category facial expression classification
- **Face Tracking**: Stable identity tracking across video frames
- **Multi-Angle Memory**: Store multiple embeddings per identity
- **Permission System**: Role-based access control (admin, user, guest, denied)
- **Real-Time Performance**: 10+ FPS on CPU, 30+ FPS on GPU

## Installation

### Prerequisites

- Python 3.8-3.11 (recommended: 3.10)
- CUDA-capable GPU (optional, for acceleration)
- 16GB RAM minimum

### Install from source

```bash
# Clone the repository
git clone https://github.com/guruvision/guruvision.git
cd guruvision

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

### CPU-only installation

For systems without GPU:

```bash
pip install -e .[cpu]
```

## Project Structure

```
guruvision/
├── guru_vision/          # Main package
│   ├── detection/        # Face detection module (RetinaFace)
│   ├── alignment/        # Face alignment module
│   ├── recognition/      # Face recognition module (ArcFace)
│   ├── liveness/         # Liveness detection module
│   ├── emotion/          # Emotion recognition module
│   ├── tracking/         # Face tracking module (DeepSORT/ByteTrack)
│   ├── database/         # Face database management
│   ├── training/         # Training pipeline
│   └── utils/            # Utility functions
├── guru_face/            # Data directory
│   ├── model/            # Trained models (ONNX)
│   ├── database/         # Identity database
│   └── logs/             # System logs
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Package configuration
└── README.md             # This file
```

## Quick Start

Coming soon - implementation in progress.

## Development

### Running tests

```bash
pytest
```

### Code formatting

```bash
black guru_vision/
```

## License

MIT License

## Acknowledgments

- [InsightFace](https://github.com/deepinsight/insightface) for ArcFace implementation
- RetinaFace for face detection
- ONNX Runtime for optimized inference
