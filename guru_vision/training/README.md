# GuruVision Training Module

This module provides dataset preprocessing and model training functionality for the GuruVision facial recognition system.

## Overview

The training module handles:
- Dataset validation and preprocessing
- Face detection and alignment for training data
- Model training (to be implemented)
- ONNX model export (to be implemented)

## Dataset Preprocessing

### Dataset Structure

Organize your training dataset as follows:

```
dataset/
├── Identity1/
│   ├── image1.jpg
│   ├── image2.jpg
│   └── ...
├── Identity2/
│   ├── image1.jpg
│   ├── image2.jpg
│   └── ...
└── ...
```

### Requirements

- **Minimum**: 50 images per identity
- **Recommended**: 100-300 images per identity
- **Supported formats**: JPG, JPEG, PNG, BMP

### Image Quality Guidelines

For best results, include images with:
- Various lighting conditions (normal, low-light, bright)
- Different head angles (frontal, profile, 45-degree)
- Multiple expressions (neutral, smiling, serious)
- Optional variations (glasses/no glasses, different hairstyles)

## Usage

### Basic Preprocessing

```python
from guru_vision.training.preprocess import preprocess_dataset

# Preprocess dataset
result = preprocess_dataset(
    dataset_dir="dataset",
    output_dir="aligned_dataset",
    use_gpu=True
)

print(f"Successfully processed: {result.successful}/{result.total_images}")
```

### Validate Dataset Structure

```python
from guru_vision.training.preprocess import validate_dataset_structure

is_valid, errors = validate_dataset_structure("dataset")

if not is_valid:
    for error in errors:
        print(f"Error: {error}")
```

### Check Minimum Images

```python
from guru_vision.training.preprocess import check_minimum_images

all_valid, counts = check_minimum_images("dataset", minimum=50)

for identity, count in counts.items():
    if count < 50:
        print(f"Warning: {identity} has only {count} images")
```

### Complete Example

See `example_preprocess.py` for a complete interactive example:

```bash
python -m guru_vision.training.example_preprocess
```

## Preprocessing Behavior

### Face Detection

- Uses RetinaFace detector for robust face detection
- Filters detections by confidence threshold (default: 0.5)
- Returns empty list if no faces detected

### No-Face Images

When an image contains no detectable face:
- Logs a warning with the image path
- Skips the image
- Continues processing remaining images
- Increments `no_face` counter in results

### Multiple-Face Images

When an image contains multiple faces:
- Logs an info message
- Selects the face with the largest bounding box area
- Uses the largest face for alignment
- Increments `multiple_faces` counter in results

### Face Alignment

- Aligns faces to standard orientation using 5-point landmarks
- Resizes to 112x112 pixels (ArcFace input size)
- Applies similarity transform (rotation, scale, translation)
- Preserves facial features during transformation

## Output

### Aligned Dataset Structure

```
aligned_dataset/
├── Identity1/
│   ├── image1.jpg  (112x112 aligned face)
│   ├── image2.jpg
│   └── ...
├── Identity2/
│   ├── image1.jpg
│   └── ...
└── ...
```

### Preprocessing Results

The `preprocess_dataset()` function returns a `PreprocessResult` object with:

- `total_images`: Total number of images processed
- `successful`: Number of successfully aligned faces
- `no_face`: Number of images with no detectable face
- `multiple_faces`: Number of images with multiple faces
- `failed`: Number of images that failed to process
- `identities_processed`: Number of identities processed
- `statistics`: Per-identity statistics dictionary

## Error Handling

### Invalid Dataset Structure

Raises `ValueError` if:
- Dataset directory doesn't exist
- No identity subdirectories found
- Identity directories contain no images

### Processing Errors

For individual image errors:
- Logs error message with image path
- Skips the problematic image
- Continues processing remaining images
- Increments `failed` counter in results

### Common Issues

**No faces detected:**
- Check image quality and resolution
- Ensure faces are clearly visible
- Verify lighting conditions
- Try adjusting confidence threshold

**Multiple faces detected:**
- Use images with single faces for best results
- System will automatically use largest face
- Consider cropping images to single face

**Alignment failures:**
- May occur with extreme head poses
- Check that facial landmarks are detectable
- Ensure face is not heavily occluded

## Performance

### CPU Mode

- Processing speed: ~1-2 images/second
- Memory usage: ~2-4 GB
- Suitable for small datasets (<1000 images)

### GPU Mode

- Processing speed: ~5-10 images/second
- Memory usage: ~4-6 GB (including GPU memory)
- Recommended for large datasets (>1000 images)

## Next Steps

After preprocessing:

1. **Review aligned faces**: Check the output directory for quality
2. **Remove bad alignments**: Delete any incorrectly aligned faces
3. **Train model**: Use aligned dataset for ArcFace training (to be implemented)
4. **Export to ONNX**: Convert trained model for inference (to be implemented)

## Requirements

This module satisfies the following requirements:
- 1.2: Dataset preprocessing before training
- 2.1: Dataset structure validation
- 2.2: Face detection and cropping
- 2.3: Saving aligned faces
- 2.4: No-face image handling
- 2.5: Multiple-face image handling
- 2.6: Image format support
- 2.7: Minimum image validation
- 29.1: Dataset quality requirements

## Dependencies

- `opencv-python`: Image loading and processing
- `numpy`: Numerical operations
- `guru_vision.detection`: Face detection
- `guru_vision.alignment`: Face alignment

## Testing

Run unit tests:

```bash
pytest guru_vision/training/test_preprocess.py -v
```

Run with coverage:

```bash
pytest guru_vision/training/test_preprocess.py --cov=guru_vision.training.preprocess
```

## Future Enhancements

- Model training implementation
- ONNX export functionality
- Data augmentation options
- Quality assessment metrics
- Parallel processing support
- Progress bar for large datasets
