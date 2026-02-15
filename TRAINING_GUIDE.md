# GuruVision Training Guide

This guide explains how to use the main training script (`train.py`) to train custom face recognition models for the GuruVision system.

## Overview

The `train.py` script orchestrates the complete training pipeline:

1. **Dataset Validation** - Validates dataset structure and minimum image requirements
2. **Preprocessing** - Detects, aligns, and saves faces from raw images
3. **Model Training** - Fine-tunes ArcFace model on your custom dataset
4. **ONNX Export** - Exports trained model to ONNX format for fast inference
5. **Validation** - Verifies ONNX model produces identical embeddings to PyTorch
6. **Report Generation** - Creates comprehensive training report with statistics

## Requirements

### Dataset Structure

Your dataset must follow this structure:

```
dataset/
├── Person1/
│   ├── image_001.jpg
│   ├── image_002.jpg
│   └── ...
├── Person2/
│   ├── image_001.jpg
│   ├── image_002.jpg
│   └── ...
└── Person3/
    ├── image_001.jpg
    └── ...
```

### Image Requirements

- **Minimum images per identity**: 50 (recommended: 100-300)
- **Supported formats**: JPEG, PNG, BMP
- **Image content**: Each image should contain at least one face
- **Variations**: Include different angles, lighting conditions, and expressions

### System Requirements

- **Python**: 3.8-3.11 (recommended: 3.10)
- **RAM**: 16GB minimum
- **GPU**: NVIDIA GPU with CUDA support (optional but recommended)
- **Disk Space**: ~10GB for models and intermediate files

## Basic Usage

### Simple Training

Train a model with default settings:

```bash
python train.py --dataset dataset/ --output guru_face/
```

This will:
- Preprocess all images in `dataset/`
- Train for 20 epochs with batch size 32
- Export to ONNX format
- Save everything to `guru_face/` directory

### Custom Hyperparameters

Train with custom settings:

```bash
python train.py \
  --dataset dataset/ \
  --output guru_face/ \
  --epochs 30 \
  --batch-size 64 \
  --lr 0.05
```

### CPU-Only Training

If you don't have a GPU:

```bash
python train.py \
  --dataset dataset/ \
  --output guru_face/ \
  --no-gpu
```

**Note**: CPU training is significantly slower (10-20x) than GPU training.

## Advanced Usage

### Using Configuration Files

Create a configuration file for reusable settings:

**config.yaml**:
```yaml
batch_size: 64
learning_rate: 0.05
num_epochs: 30
momentum: 0.9
weight_decay: 0.0005
arcface_scale: 64.0
arcface_margin: 0.5
```

Then use it:

```bash
python train.py \
  --dataset dataset/ \
  --output guru_face/ \
  --config config.yaml
```

### Skip Preprocessing

If you already have preprocessed data:

```bash
python train.py \
  --dataset dataset/ \
  --output guru_face/ \
  --skip-preprocess
```

This expects aligned faces in `guru_face/aligned_dataset/`.

### Skip ONNX Export

To only train the PyTorch model:

```bash
python train.py \
  --dataset dataset/ \
  --output guru_face/ \
  --skip-export
```

### Debug Mode

Enable detailed logging:

```bash
python train.py \
  --dataset dataset/ \
  --output guru_face/ \
  --log-level DEBUG
```

## Command-Line Options

### Required Arguments

- `--dataset DATASET` - Path to dataset directory
- `--output OUTPUT` - Output directory for models, logs, and reports

### Training Hyperparameters

- `--batch-size N` - Batch size for training (default: 32)
- `--epochs N` - Number of training epochs (default: 20)
- `--lr RATE` - Learning rate (default: 0.1)
- `--backbone {r50}` - Backbone architecture (default: r50 for ResNet-50)

### Hardware Options

- `--no-gpu` - Disable GPU acceleration (use CPU only)
- `--num-workers N` - Number of data loading workers (default: 4)

### Pipeline Control

- `--skip-preprocess` - Skip preprocessing step
- `--skip-export` - Skip ONNX export step
- `--skip-validation` - Skip ONNX-PyTorch equivalence validation

### Configuration

- `--config PATH` - Path to training configuration file (YAML or JSON)
- `--log-level LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Output Structure

After training, the output directory will contain:

```
guru_face/
├── aligned_dataset/          # Preprocessed aligned faces
│   ├── Person1/
│   ├── Person2/
│   └── ...
├── model/                    # Trained models
│   ├── guru_face_model.pth   # PyTorch model
│   └── guru_face_model.onnx  # ONNX model
├── checkpoints/              # Training checkpoints
│   ├── checkpoint_epoch_5.pth
│   ├── checkpoint_epoch_10.pth
│   └── ...
├── logs/                     # Training logs
│   └── training_YYYYMMDD_HHMMSS.log
└── reports/                  # Training reports
    └── training_report_YYYYMMDD_HHMMSS.json
```

## Training Report

The training report (`reports/training_report_*.json`) contains:

- **Training Configuration**: All hyperparameters used
- **Preprocessing Statistics**: Images processed, success rate, per-identity stats
- **Training Metrics**: Duration, model path, validation accuracy
- **ONNX Export Status**: Export success, validation results

Example report:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "training_configuration": {
    "batch_size": 32,
    "learning_rate": 0.1,
    "num_epochs": 20,
    "backbone": "r50",
    "embedding_size": 512
  },
  "preprocessing": {
    "total_images": 500,
    "successful": 485,
    "no_face": 10,
    "multiple_faces": 5,
    "identities_processed": 5,
    "success_rate": "97.00%"
  },
  "training": {
    "duration_seconds": 3600,
    "model_path": "guru_face/model/guru_face_model.pth"
  },
  "onnx_export": {
    "performed": true,
    "validation_passed": true
  }
}
```

## Troubleshooting

### "No face detected" warnings

**Problem**: Many images have no detectable faces.

**Solutions**:
- Ensure images contain clear, visible faces
- Check image quality (not too blurry or low resolution)
- Verify faces are not too small in the image
- Try different lighting conditions

### "Insufficient images" warnings

**Problem**: Some identities have fewer than 50 images.

**Solutions**:
- Collect more images for those identities
- Training will still proceed but accuracy may be reduced
- Recommended: 100-300 images per identity for best results

### Out of memory errors

**Problem**: GPU runs out of memory during training.

**Solutions**:
- Reduce batch size: `--batch-size 16` or `--batch-size 8`
- Reduce number of workers: `--num-workers 2`
- Use CPU training: `--no-gpu` (slower but uses system RAM)

### Slow training on CPU

**Problem**: Training is very slow without GPU.

**Solutions**:
- Use a GPU if available (10-20x faster)
- Reduce number of epochs: `--epochs 10`
- Reduce batch size: `--batch-size 16`
- Use a smaller dataset for testing

### ONNX validation fails

**Problem**: ONNX model doesn't match PyTorch model.

**Solutions**:
- This is rare but can happen with certain operations
- Check PyTorch and ONNX versions are compatible
- Try re-exporting: delete ONNX file and run again
- Report issue if problem persists

## Best Practices

### Dataset Collection

1. **Quantity**: Collect 100-300 images per identity
2. **Variety**: Include different:
   - Angles (frontal, profile, 45-degree)
   - Lighting conditions (bright, normal, low-light)
   - Expressions (neutral, smiling, serious)
   - Accessories (glasses, hats - if relevant)
3. **Quality**: Use high-resolution images (at least 640x480)
4. **Consistency**: Use similar camera/device for all images

### Training Strategy

1. **Start Small**: Test with 2-3 identities first
2. **Validate Dataset**: Check preprocessing results before full training
3. **Monitor Training**: Watch validation accuracy during training
4. **Save Checkpoints**: Keep checkpoint files for recovery
5. **Test Incrementally**: Test model after training before deployment

### Performance Optimization

1. **Use GPU**: Always use GPU if available (30+ FPS vs 10 FPS on CPU)
2. **Batch Size**: Larger batches train faster but need more memory
3. **Workers**: More workers speed up data loading (4-8 recommended)
4. **Mixed Precision**: Consider using mixed precision training for faster GPU training

## Next Steps

After training:

1. **Test the Model**: Use the recognition engine to test on new images
2. **Add Identities**: Add new identities incrementally without retraining
3. **Deploy**: Integrate with your AI agent or application
4. **Monitor**: Track recognition accuracy in production
5. **Retrain**: Periodically retrain with new data to improve accuracy

## Examples

### Example 1: Quick Test Training

Train quickly with minimal data for testing:

```bash
python train.py \
  --dataset test_dataset/ \
  --output test_output/ \
  --epochs 5 \
  --batch-size 16 \
  --no-gpu
```

### Example 2: Production Training

Train for production with optimal settings:

```bash
python train.py \
  --dataset production_dataset/ \
  --output guru_face/ \
  --epochs 30 \
  --batch-size 64 \
  --lr 0.1 \
  --num-workers 8
```

### Example 3: Resume from Preprocessing

If preprocessing completed but training failed:

```bash
python train.py \
  --dataset dataset/ \
  --output guru_face/ \
  --skip-preprocess \
  --epochs 20
```

### Example 4: Export Only

If you have a trained PyTorch model and need ONNX:

```bash
python -m guru_vision.training.export \
  --pytorch-model guru_face/model/guru_face_model.pth \
  --output guru_face/model/guru_face_model.onnx \
  --validate
```

## Support

For issues or questions:

1. Check the training log in `guru_face/logs/`
2. Review the training report in `guru_face/reports/`
3. See the main README.md for general documentation
4. Check guru_vision/training/README.md for module details

## References

- **ArcFace Paper**: "ArcFace: Additive Angular Margin Loss for Deep Face Recognition"
- **InsightFace**: https://github.com/deepinsight/insightface
- **ONNX Runtime**: https://onnxruntime.ai/
- **PyTorch**: https://pytorch.org/
