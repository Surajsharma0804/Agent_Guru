# ArcFace Model Training Module

This module provides functionality for training custom ArcFace face recognition models using PyTorch and the InsightFace framework.

## Overview

The training module implements a complete pipeline for fine-tuning ResNet-50 backbone with ArcFace loss on custom face datasets. It supports:

- Custom dataset loading from aligned face images
- ResNet-50 backbone with ArcFace loss
- Configurable training hyperparameters
- Automatic train/validation split
- Model checkpointing and best model saving
- GPU acceleration support

## Requirements

- Python 3.8-3.11 (recommended: 3.10)
- PyTorch >= 2.0.0
- torchvision >= 0.15.0
- PIL/Pillow
- NumPy

## Dataset Structure

The training module expects aligned face images organized in the following structure:

```
aligned_dataset/
├── Identity1/
│   ├── image_001.jpg
│   ├── image_002.jpg
│   └── ...
├── Identity2/
│   ├── image_001.jpg
│   ├── image_002.jpg
│   └── ...
└── ...
```

**Requirements:**
- Minimum 50 images per identity (recommended: 100-300)
- Images should be aligned and cropped to 112x112 pixels
- Supported formats: JPEG, PNG, BMP
- Use the preprocessing module to prepare raw datasets

## Usage

### Basic Training

```python
from guru_vision.training.train import train_arcface_model, TrainingConfig

# Create configuration
config = TrainingConfig(
    batch_size=32,
    learning_rate=0.1,
    num_epochs=20,
    use_gpu=True
)

# Train model
model_path = train_arcface_model(
    aligned_dataset_dir="aligned_dataset",
    config=config
)

print(f"Model saved to: {model_path}")
```

### Command Line Training

```bash
# Basic training
python -m guru_vision.training.train --dataset aligned_dataset

# Custom parameters
python -m guru_vision.training.train \
    --dataset aligned_dataset \
    --batch-size 64 \
    --epochs 30 \
    --lr 0.05 \
    --output-dir guru_face/model

# CPU-only training
python -m guru_vision.training.train \
    --dataset aligned_dataset \
    --no-gpu
```

### Advanced Configuration

```python
from guru_vision.training.train import TrainingConfig

config = TrainingConfig(
    # Training parameters
    batch_size=32,
    learning_rate=0.1,
    num_epochs=20,
    
    # Model architecture
    backbone="r50",  # ResNet-50
    embedding_size=512,
    
    # Optimization
    momentum=0.9,
    weight_decay=5e-4,
    lr_schedule="cosine",  # or "step"
    
    # Hardware
    use_gpu=True,
    num_workers=4,
    
    # Validation
    validation_split=0.1,
    
    # Checkpointing
    save_interval=5,
    output_dir="guru_face/model",
    checkpoint_dir="guru_face/checkpoints",
    
    # ArcFace loss parameters
    arcface_scale=64.0,
    arcface_margin=0.5
)
```

## Training Configuration

### TrainingConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch_size` | int | 32 | Number of samples per batch |
| `learning_rate` | float | 0.1 | Initial learning rate |
| `num_epochs` | int | 20 | Number of training epochs |
| `backbone` | str | "r50" | Backbone architecture (ResNet-50) |
| `embedding_size` | int | 512 | Dimension of face embeddings |
| `num_workers` | int | 4 | Number of data loading workers |
| `use_gpu` | bool | True | Enable GPU acceleration |
| `momentum` | float | 0.9 | SGD momentum |
| `weight_decay` | float | 5e-4 | L2 regularization weight |
| `lr_schedule` | str | "cosine" | Learning rate schedule ("cosine" or "step") |
| `save_interval` | int | 5 | Save checkpoint every N epochs |
| `validation_split` | float | 0.1 | Fraction of data for validation |
| `arcface_scale` | float | 64.0 | ArcFace scale parameter (s) |
| `arcface_margin` | float | 0.5 | ArcFace angular margin (m) |

## Model Architecture

### Backbone: ResNet-50

The training uses ResNet-50 as the backbone architecture:

- **Input:** 112x112 RGB images
- **Output:** 512-dimensional embeddings
- **Layers:** 50 convolutional layers with residual connections
- **Parameters:** ~25M trainable parameters

### ArcFace Loss

ArcFace (Additive Angular Margin Loss) improves face recognition by:

1. Normalizing embeddings and weight vectors
2. Computing cosine similarity
3. Adding angular margin to target class
4. Scaling the output

**Formula:**
```
L = -log(exp(s * cos(θ_yi + m)) / (exp(s * cos(θ_yi + m)) + Σ exp(s * cos(θ_j))))
```

Where:
- `s` = scale parameter (default: 64.0)
- `m` = angular margin (default: 0.5)
- `θ_yi` = angle between embedding and target class weight

## Training Process

### 1. Data Loading

```python
# Dataset structure is loaded
# Class mappings are created
# Images are loaded with transformations
```

### 2. Model Initialization

```python
# ResNet-50 backbone is initialized
# ArcFace head is created
# SGD optimizer is configured
```

### 3. Training Loop

For each epoch:
1. **Training Phase:**
   - Forward pass through backbone and ArcFace head
   - Compute cross-entropy loss
   - Backward pass and parameter update
   - Track training loss and accuracy

2. **Validation Phase:**
   - Evaluate on validation set
   - Track validation loss and accuracy
   - No gradient computation

3. **Checkpointing:**
   - Save checkpoint every N epochs
   - Save best model based on validation accuracy

### 4. Model Saving

The best model is saved as `guru_face_model.pth` containing:
- Backbone state dict
- Training metadata (epoch, accuracy, etc.)
- Model configuration
- Training history

## Data Augmentation

### Training Transforms

- Random horizontal flip (50% probability)
- Color jitter (brightness, contrast, saturation ±20%)
- Normalization to [-1, 1] range

### Validation Transforms

- No augmentation
- Only normalization to [-1, 1] range

## Output Files

### Model Checkpoint

**Location:** `guru_face/model/guru_face_model.pth`

**Contents:**
```python
{
    'epoch': int,
    'backbone_state_dict': OrderedDict,
    'embedding_size': int,
    'backbone': str,
    'val_acc': float,
    'num_classes': int,
    'training_history': dict
}
```

### Training Checkpoints

**Location:** `guru_face/checkpoints/checkpoint_epoch_N.pth`

**Contents:**
```python
{
    'epoch': int,
    'backbone_state_dict': OrderedDict,
    'arcface_head_state_dict': OrderedDict,
    'optimizer_state_dict': OrderedDict,
    'train_loss': float,
    'val_loss': float,
    'val_acc': float,
    'config': TrainingConfig
}
```

## Loading Trained Models

```python
from guru_vision.training.train import load_trained_model

# Load model for inference
model = load_trained_model(
    model_path="guru_face/model/guru_face_model.pth",
    device="cuda"  # or "cpu"
)

# Model is ready for embedding extraction
model.eval()
```

## Performance Considerations

### GPU Training

**Recommended:**
- NVIDIA RTX 3060 or better
- 6GB+ VRAM
- CUDA 11.8 or 12.1

**Expected Performance:**
- Training speed: ~100-200 images/second
- Memory usage: ~2-4GB VRAM
- Training time: ~1-2 hours for 20 epochs (1000 images)

### CPU Training

**Minimum:**
- Intel i5/i7 or AMD Ryzen 5/7
- 4+ cores
- 16GB RAM

**Expected Performance:**
- Training speed: ~10-30 images/second
- Memory usage: ~2-4GB RAM
- Training time: ~10-20 hours for 20 epochs (1000 images)

## Troubleshooting

### Out of Memory (OOM)

**Solution:** Reduce batch size
```python
config = TrainingConfig(batch_size=16)  # or 8
```

### Slow Training

**Solutions:**
1. Enable GPU acceleration
2. Increase `num_workers` for data loading
3. Reduce image resolution (if using custom preprocessing)

### Poor Accuracy

**Solutions:**
1. Increase number of training images per identity
2. Ensure dataset has good variation (angles, lighting, expressions)
3. Train for more epochs
4. Adjust learning rate

### CUDA Out of Memory

**Solutions:**
1. Reduce batch size
2. Use gradient accumulation
3. Enable mixed precision training (future enhancement)

## Best Practices

### Dataset Quality

1. **Minimum Images:** 50 per identity (warning issued if less)
2. **Recommended Images:** 100-300 per identity
3. **Variation:** Include different angles, lighting, expressions
4. **Quality:** Use aligned, cropped faces (112x112)

### Training Parameters

1. **Batch Size:** 32 (adjust based on GPU memory)
2. **Learning Rate:** 0.1 with cosine annealing
3. **Epochs:** 20 (increase for larger datasets)
4. **Validation Split:** 10% (adjust for small datasets)

### Hardware

1. **GPU Training:** Strongly recommended for production
2. **CPU Training:** Acceptable for small datasets or testing
3. **Memory:** 16GB RAM minimum, 32GB recommended

## Integration with Other Modules

### Preprocessing Pipeline

```python
from guru_vision.training.preprocess import preprocess_dataset
from guru_vision.training.train import train_arcface_model

# Step 1: Preprocess raw dataset
preprocess_dataset(
    dataset_dir="dataset",
    output_dir="aligned_dataset"
)

# Step 2: Train model
model_path = train_arcface_model(
    aligned_dataset_dir="aligned_dataset"
)
```

### ONNX Export

After training, export to ONNX format for inference:

```python
from guru_vision.training.export import export_to_onnx

export_to_onnx(
    pytorch_model_path="guru_face/model/guru_face_model.pth",
    output_path="guru_face/model/guru_face_model.onnx"
)
```

## API Reference

### Functions

#### `train_arcface_model(aligned_dataset_dir, config=None)`

Train ArcFace model on aligned dataset.

**Parameters:**
- `aligned_dataset_dir` (str): Path to aligned dataset directory
- `config` (TrainingConfig, optional): Training configuration

**Returns:**
- `str`: Path to saved model checkpoint

#### `setup_arcface_training(num_classes, config)`

Initialize ResNet-50 backbone with ArcFace loss.

**Parameters:**
- `num_classes` (int): Number of identity classes
- `config` (TrainingConfig): Training configuration

**Returns:**
- `tuple`: (backbone, arcface_head, optimizer)

#### `load_trained_model(model_path, device="cpu")`

Load trained model from checkpoint.

**Parameters:**
- `model_path` (str): Path to model checkpoint
- `device` (str): Device to load model on

**Returns:**
- `nn.Module`: Loaded backbone model

### Classes

#### `TrainingConfig`

Configuration dataclass for training parameters.

#### `FaceDataset`

PyTorch Dataset for loading aligned face images.

#### `ArcFaceHead`

ArcFace loss head module.

## References

1. **ArcFace Paper:** "ArcFace: Additive Angular Margin Loss for Deep Face Recognition"
   - https://arxiv.org/abs/1801.07698

2. **InsightFace Repository:** Official implementation
   - https://github.com/deepinsight/insightface

3. **ResNet Paper:** "Deep Residual Learning for Image Recognition"
   - https://arxiv.org/abs/1512.03385

## Requirements Validation

This module satisfies the following requirements:

- **Requirement 1.1:** Fine-tune ArcFace model on custom datasets
- **Requirement 1.5:** Support datasets with multiple identities
- **Requirement 1.6:** Incorporate variations in lighting, angles, expressions
- **Requirement 1.7:** Preserve base ArcFace architecture
- **Requirement 26.1-26.3:** Use official InsightFace implementation
- **Requirement 28.1:** Execute training pipeline steps in sequence
- **Requirement 28.3:** Use R50 (ResNet-50) backbone
- **Requirement 28.4:** Support configurable hyperparameters
- **Requirement 28.5:** Use default hyperparameters (batch_size=32, lr=0.1, epochs=20)

## License

This module is part of the GuruVision facial recognition system.
