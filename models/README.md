# Agent Guru — Production ONNX Models

This directory holds all ONNX model files required by the Agent Guru vision system.
**Model files are not committed to git** (they are listed in `.gitignore`).

## Quick Start

```bash
# Download all models
python models/download_models.py

# Download specific models
python models/download_models.py --models yolov8n arcface emotion liveness

# List status of all models
python models/download_models.py --list

# Force re-download
python models/download_models.py --force
```

## Model Inventory

| File | Model | Source | Size | License |
|------|-------|--------|------|---------|
| `yolov8n.onnx` | YOLOv8n object detection | [Ultralytics](https://github.com/ultralytics/ultralytics) | ~6 MB | AGPL-3.0 |
| `arcface_r100.onnx` | ArcFace R100 face recognition | [InsightFace buffalo_l](https://github.com/deepinsight/insightface) | ~248 MB | MIT |
| `emotion_model.onnx` | HSEmotion 7-class emotion | [HSE-asavchenko](https://github.com/HSE-asavchenko/face-emotion-recognition) | ~28 MB | MIT |
| `liveness_minifasnet.onnx` | MiniFASNet anti-spoofing | [minivision-group](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) | ~1 MB | Apache-2.0 |
| `midas_v31.onnx` | MiDaS v3.1 depth estimation | [Intel ISL](https://github.com/isl-org/MiDaS) | ~1.3 GB | MIT |
| `trocr_handwritten.onnx` | TrOCR handwriting recognition | [Microsoft](https://huggingface.co/microsoft/trocr-base-handwritten) | ~330 MB | MIT |
| `scene_efficientnet.onnx` | EfficientNet-B4 scene classification | [timm](https://github.com/huggingface/pytorch-image-models) | ~74 MB | Apache-2.0 |

## Model Details

### yolov8n.onnx
- Input: `float32 [1, 3, 640, 640]` (RGB, normalised 0–1)
- Output: `float32 [1, 84, 8400]` (cx, cy, w, h + 80 class scores)
- Used by: `Agent_Guru/vision/scene.py` → `ObjectDetector`

### arcface_r100.onnx
- Input: `float32 [1, 3, 112, 112]` (RGB, normalised −1 to 1)
- Output: `float32 [1, 512]` (L2-normalised embedding)
- Used by: `Agent_Guru/vision/recognition/recognizer.py` → `FaceRecognizer`

### emotion_model.onnx
- Input: `float32 [1, 3, 112, 112]` (RGB, normalised 0–1)
- Output: `float32 [1, 7]` (logits for 7 emotions)
- Classes: neutral, happy, sad, angry, surprised, fearful, disgusted
- Used by: `Agent_Guru/vision/emotion/recognizer.py` → `EmotionRecognizer`

### liveness_minifasnet.onnx
- Input: `float32 [1, 3, 80, 80]` (BGR, normalised −1 to 1)
- Output: `float32 [1, 2]` (spoof_score, live_score)
- Used by: `Agent_Guru/vision/liveness/detector.py` → `LivenessDetector`

### midas_v31.onnx
- Input: `float32 [1, 3, 384, 384]` (RGB, normalised 0–1)
- Output: `float32 [1, 384, 384]` (inverse relative depth)
- Used by: `Agent_Guru/vision/depth.py` → `DepthEstimator`

### trocr_handwritten.onnx
- Input: `float32 [1, 3, 384, 384]` (RGB, normalised −1 to 1)
- Output: `float32 [1, seq_len, vocab_size]` (token logits)
- Used by: `Agent_Guru/vision/handwriting.py` → `HandwritingRecognizer`

### scene_efficientnet.onnx
- Input: `float32 [1, 3, 224, 224]` (RGB, normalised 0–1)
- Output: `float32 [1, 30]` (logits for 30 scene categories)
- Used by: `Agent_Guru/vision/scene.py` → `SceneClassifier`

## Production Notes

- **ArcFace**: The download script extracts `w600k_r50.onnx` from the InsightFace
  `buffalo_l.zip` pack and saves it as `arcface_r100.onnx`.
- **MiDaS**: No official pre-exported ONNX is available; the script exports from
  PyTorch via `torch.onnx.export`. Requires PyTorch + timm.
- **TrOCR**: Exported via `optimum[exporters]`. Only the encoder is used for
  feature extraction; the decoder runs via the HuggingFace tokenizer.
- **Scene EfficientNet**: The script exports an ImageNet-pretrained EfficientNet-B4
  with a 30-class head. For best accuracy, fine-tune on Places365 and replace this file.

## GPU Acceleration

All models run on GPU when `CUDAExecutionProvider` is available in ONNX Runtime:

```bash
pip install onnxruntime-gpu
```

CPU-only fallback is automatic when CUDA is not available.
