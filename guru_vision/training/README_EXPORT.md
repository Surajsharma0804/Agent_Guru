# ONNX Model Export Module

This module provides functionality for exporting trained PyTorch ArcFace models to ONNX format for optimized cross-platform inference.

## Overview

The ONNX export module converts trained PyTorch models to ONNX format, which enables:
- **Fast inference** with ONNX Runtime (C++ backend)
- **Cross-platform deployment** (CPU and GPU)
- **Production-ready models** with optimized performance
- **Compatibility** with various deployment environments

## Requirements

- Requirements: 1.3, 11.1, 11.6, 28.1, 28.7

## Features

### 1. Model Export
- Export PyTorch models to ONNX format
- Support for custom opset versions (default: 11)
- Automatic model structure validation
- Dynamic batch size support

### 2. Model Verification
- Validate ONNX model structure
- Check compatibility with ONNX Runtime
- Test inference with dummy data

### 3. Equivalence Validation
- Compare PyTorch and ONNX outputs
- Ensure embeddings match within tolerance (default: 0.001)
- Test with multiple random samples

## Installation

The export module requires the following dependencies:

```bash
pip install torch torchvision onnx onnxruntime-gpu onnxscript
```

For CPU-only systems:
```bash
pip install torch torchvision onnx onnxruntime onnxscript
```

## Usage

### Basic Export

```python
from guru_vision.training.export import export_to_onnx

# Export PyTorch model to ONNX
success = export_to_onnx(
    pytorch_model_path="guru_face/model/guru_face_model.pth",
    output_path="guru_face/model/guru_face_model.onnx",
    opset_version=11,
    verify=True
)

if success:
    print("Model exported successfully!")
```

### Verify ONNX Model

```python
from guru_vision.training.export import verify_onnx_model

# Verify the exported model
is_valid = verify_onnx_model("guru_face/model/guru_face_model.onnx")

if is_valid:
    print("ONNX model is valid!")
```

### Validate Equivalence

```python
from guru_vision.training.export import validate_onnx_pytorch_equivalence

# Validate that ONNX and PyTorch produce identical outputs
matches = validate_onnx_pytorch_equivalence(
    pytorch_model_path="guru_face/model/guru_face_model.pth",
    onnx_model_path="guru_face/model/guru_face_model.onnx",
    tolerance=0.001,
    num_samples=10
)

if matches:
    print("Models are equivalent!")
```

### Command-Line Usage

The export module can be used from the command line:

```bash
# Basic export
python -m guru_vision.training.export \
    --pytorch-model guru_face/model/guru_face_model.pth \
    --output guru_face/model/guru_face_model.onnx

# Export with validation
python -m guru_vision.training.export \
    --pytorch-model guru_face/model/guru_face_model.pth \
    --output guru_face/model/guru_face_model.onnx \
    --validate \
    --tolerance 0.001

# Custom opset version
python -m guru_vision.training.export \
    --pytorch-model guru_face/model/guru_face_model.pth \
    --output guru_face/model/guru_face_model.onnx \
    --opset 12
```

## API Reference

### `export_to_onnx()`

Export trained PyTorch model to ONNX format.

**Parameters:**
- `pytorch_model_path` (str): Path to PyTorch model checkpoint (.pth file)
- `output_path` (str): Path where ONNX model will be saved (default: "guru_face/model/guru_face_model.onnx")
- `input_size` (tuple): Input tensor size as (batch, channels, height, width) (default: (1, 3, 112, 112))
- `opset_version` (int): ONNX opset version (default: 11)
- `verify` (bool): Whether to verify the exported model (default: True)

**Returns:**
- `bool`: True if export successful, False otherwise

**Raises:**
- `FileNotFoundError`: If PyTorch model file not found
- `RuntimeError`: If export fails

### `verify_onnx_model()`

Verify that the exported ONNX model is valid.

**Parameters:**
- `onnx_model_path` (str): Path to ONNX model file

**Returns:**
- `bool`: True if model is valid, False otherwise

### `validate_onnx_pytorch_equivalence()`

Validate that ONNX model produces identical embeddings to PyTorch model.

**Parameters:**
- `pytorch_model_path` (str): Path to PyTorch model checkpoint (.pth file)
- `onnx_model_path` (str): Path to ONNX model file
- `tolerance` (float): Maximum allowed difference between embeddings (default: 0.001)
- `num_samples` (int): Number of random samples to test (default: 10)

**Returns:**
- `bool`: True if embeddings match within tolerance, False otherwise

## Examples

### Example 1: Complete Export Workflow

```python
import logging
from guru_vision.training.export import (
    export_to_onnx,
    verify_onnx_model,
    validate_onnx_pytorch_equivalence
)

# Setup logging
logging.basicConfig(level=logging.INFO)

# Step 1: Export model
success = export_to_onnx(
    pytorch_model_path="guru_face/model/guru_face_model.pth",
    output_path="guru_face/model/guru_face_model.onnx",
    verify=True
)

if not success:
    print("Export failed!")
    exit(1)

# Step 2: Validate equivalence
matches = validate_onnx_pytorch_equivalence(
    pytorch_model_path="guru_face/model/guru_face_model.pth",
    onnx_model_path="guru_face/model/guru_face_model.onnx",
    tolerance=0.001,
    num_samples=10
)

if matches:
    print("✓ Export successful! Models are equivalent.")
else:
    print("✗ Models are NOT equivalent!")
```

### Example 2: Batch Export Checkpoints

```python
import os
from guru_vision.training.export import export_to_onnx

checkpoint_dir = "guru_face/checkpoints"
output_dir = "guru_face/onnx_models"

os.makedirs(output_dir, exist_ok=True)

# Export all checkpoints
for checkpoint_file in os.listdir(checkpoint_dir):
    if checkpoint_file.endswith('.pth'):
        checkpoint_path = os.path.join(checkpoint_dir, checkpoint_file)
        onnx_file = checkpoint_file.replace('.pth', '.onnx')
        onnx_path = os.path.join(output_dir, onnx_file)
        
        print(f"Exporting {checkpoint_file}...")
        export_to_onnx(checkpoint_path, onnx_path, verify=True)
```

### Example 3: Custom Opset Version

```python
from guru_vision.training.export import export_to_onnx

# Export with opset version 12 for newer ONNX features
success = export_to_onnx(
    pytorch_model_path="guru_face/model/guru_face_model.pth",
    output_path="guru_face/model/guru_face_model_v12.onnx",
    opset_version=12,
    verify=True
)
```

## Model Format

### PyTorch Model Checkpoint

The PyTorch model checkpoint (.pth file) should contain:

```python
{
    'backbone_state_dict': <model weights>,
    'embedding_size': 512,
    'backbone': 'r50',
    'val_acc': <validation accuracy>,
    'num_classes': <number of identities>,
    'training_history': <training metrics>
}
```

### ONNX Model

The exported ONNX model has:
- **Input**: `input` tensor with shape `(batch_size, 3, 112, 112)`
- **Output**: `output` tensor with shape `(batch_size, 512)`
- **Dynamic batch size**: Supports variable batch sizes
- **Opset version**: 11 (default) or custom

## Performance

### Export Time
- Small models (ResNet-50): ~5-10 seconds
- Large models: ~10-30 seconds

### Inference Speed (ONNX vs PyTorch)
- CPU: ~50% faster with ONNX Runtime
- GPU: ~30% faster with ONNX Runtime

### Model Size
- PyTorch checkpoint: ~100-200 MB
- ONNX model: ~90-180 MB (slightly smaller due to optimization)

## Troubleshooting

### Issue: "No module named 'onnxscript'"

**Solution:** Install the onnxscript package:
```bash
pip install onnxscript
```

### Issue: "ONNX model verification failed"

**Possible causes:**
1. Corrupted export process
2. Incompatible opset version
3. Model architecture not supported by ONNX

**Solution:** Try re-exporting with a different opset version or check the model architecture.

### Issue: "Models are NOT equivalent"

**Possible causes:**
1. Numerical precision differences
2. Different random number generators
3. Model not in eval mode

**Solution:** 
- Increase tolerance (e.g., 0.01 instead of 0.001)
- Ensure model is in eval mode before export
- Check for non-deterministic operations

### Issue: "Export takes too long"

**Solution:**
- Use GPU for faster export
- Reduce model size
- Disable verification during export (verify separately)

## Integration with Recognition Engine

After exporting to ONNX, use the model with the recognition engine:

```python
from guru_vision.recognition.recognizer import FaceRecognizer

# Initialize recognizer with ONNX model
recognizer = FaceRecognizer(
    model_path="guru_face/model/guru_face_model.onnx",
    use_gpu=True
)

# Extract embeddings
embedding = recognizer.extract_embedding(aligned_face)
```

## Best Practices

1. **Always verify after export**: Use `verify=True` to catch issues early
2. **Validate equivalence**: Ensure ONNX and PyTorch produce identical outputs
3. **Use appropriate opset**: Opset 11 is stable, newer versions may have compatibility issues
4. **Test inference**: Run test inputs through the ONNX model before deployment
5. **Backup PyTorch model**: Keep the original PyTorch checkpoint for future exports
6. **Document export settings**: Record opset version and export date for reproducibility

## See Also

- [Training Module](README_TRAINING.md) - Train custom ArcFace models
- [Preprocessing Module](README.md) - Prepare datasets for training
- [Recognition Module](../recognition/README.md) - Use ONNX models for inference

## References

- [ONNX Documentation](https://onnx.ai/)
- [ONNX Runtime](https://onnxruntime.ai/)
- [PyTorch ONNX Export](https://pytorch.org/docs/stable/onnx.html)
- [InsightFace](https://github.com/deepinsight/insightface)
