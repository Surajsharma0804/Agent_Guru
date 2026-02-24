# Reasoning Engine Utility Scripts

This directory contains utility scripts for training, profiling, and optimizing the reasoning engine.

**Note:** These are development/maintenance scripts, NOT part of the core reasoning engine package.

---

## Training Scripts

### `train_all.py`
Train all models (intent classifier, NER, etc.) in one go.

```bash
python -m Agent_Guru.reasoning.scripts.train_all
```

### `train_intent_classifier.py`
Train the intent classification model.

```bash
python -m Agent_Guru.reasoning.scripts.train_intent_classifier
```

### `train_ner_model.py`
Train the Named Entity Recognition model.

```bash
python -m Agent_Guru.reasoning.scripts.train_ner_model
```

---

## Optimization Scripts

### `optimize_models.py`
Optimize trained models for production (quantization, pruning, etc.).

```bash
python -m Agent_Guru.reasoning.scripts.optimize_models
```

### `convert_to_onnx.py`
Convert PyTorch models to ONNX format for faster inference.

```bash
python -m Agent_Guru.reasoning.scripts.convert_to_onnx
```

---

## Profiling Scripts

### `profile_pipeline.py`
Profile the complete reasoning pipeline to identify bottlenecks.

```bash
python -m Agent_Guru.reasoning.scripts.profile_pipeline
```

### `profile_components.py`
Profile individual components (intent detection, tool selection, etc.).

```bash
python -m Agent_Guru.reasoning.scripts.profile_components
```

---

## Evaluation Scripts

### `evaluate_models.py`
Evaluate model accuracy on test datasets.

```bash
python -m Agent_Guru.reasoning.scripts.evaluate_models
```

---

## Maintenance Scripts

### `cleanup_model_checkpoints.py`
Clean up old model checkpoints to free disk space.

```bash
python -m Agent_Guru.reasoning.scripts.cleanup_model_checkpoints
```

### `check_gpu.py`
Check GPU availability and CUDA setup.

```bash
python -m Agent_Guru.reasoning.scripts.check_gpu
```

---

## Usage Notes

1. **Run from project root:** All scripts should be run as modules from the project root directory
2. **Virtual environment:** Ensure you're in the correct virtual environment with all dependencies installed
3. **GPU required:** Training and optimization scripts require NVIDIA GPU with CUDA
4. **Data required:** Training scripts require training data in `Agent_Guru/reasoning/data/`

---

## Development Workflow

### 1. Train Models
```bash
# Train all models
python -m Agent_Guru.reasoning.scripts.train_all

# Or train individually
python -m Agent_Guru.reasoning.scripts.train_intent_classifier
python -m Agent_Guru.reasoning.scripts.train_ner_model
```

### 2. Evaluate Performance
```bash
python -m Agent_Guru.reasoning.scripts.evaluate_models
```

### 3. Optimize for Production
```bash
# Optimize models
python -m Agent_Guru.reasoning.scripts.optimize_models

# Convert to ONNX
python -m Agent_Guru.reasoning.scripts.convert_to_onnx
```

### 4. Profile Performance
```bash
# Profile full pipeline
python -m Agent_Guru.reasoning.scripts.profile_pipeline

# Profile individual components
python -m Agent_Guru.reasoning.scripts.profile_components
```

### 5. Cleanup
```bash
python -m Agent_Guru.reasoning.scripts.cleanup_model_checkpoints
```

---

## Requirements

- Python 3.11+
- PyTorch 2.0+ with CUDA support
- All dependencies from `requirements.txt`
- Training data in `Agent_Guru/reasoning/data/`

---

## Troubleshooting

### GPU Not Detected
```bash
python -m Agent_Guru.reasoning.scripts.check_gpu
```

### Import Errors
Ensure you're running from project root:
```bash
cd /path/to/Agent_Guru
python -m Agent_Guru.reasoning.scripts.script_name
```

### Out of Memory
Reduce batch size in training scripts or use CPU-only mode.

---

**Note:** These scripts are for development and maintenance only. They are NOT imported by the core reasoning engine.
