#!/usr/bin/env python3
"""
GuruVision Training Example

This example demonstrates how to train a custom ArcFace face recognition model
on your own dataset. It shows the complete workflow from dataset preparation
through model training and ONNX export.

Requirements: 1.1, 28.1

Usage:
    python examples/train_model.py
"""

import os
import sys
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guru_vision.training.preprocess import (
    preprocess_dataset,
    validate_dataset_structure,
    check_minimum_images
)
from guru_vision.training.train import train_arcface_model, TrainingConfig
from guru_vision.training.export import export_to_onnx, validate_onnx_pytorch_equivalence


def setup_logging():
    """Configure logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def main():
    """
    Example: Train a custom face recognition model.
    
    This example demonstrates:
    1. Dataset preparation and validation
    2. Face detection and alignment preprocessing
    3. ArcFace model training with custom hyperparameters
    4. ONNX export for production deployment
    5. Model validation
    """
    setup_logging()
    
    print("=" * 80)
    print("GuruVision Custom Model Training Example")
    print("=" * 80)
    print()
    
    # =========================================================================
    # STEP 1: Prepare Your Dataset
    # =========================================================================
    print("STEP 1: Dataset Preparation")
    print("-" * 80)
    print()
    print("Dataset Structure Requirements:")
    print("  dataset/")
    print("    ├── PersonA/")
    print("    │   ├── image001.jpg")
    print("    │   ├── image002.jpg")
    print("    │   └── ... (50-300 images recommended)")
    print("    ├── PersonB/")
    print("    │   ├── image001.jpg")
    print("    │   └── ...")
    print("    └── PersonC/")
    print("        └── ...")
    print()
    print("Tips for best results:")
    print("  • Use 100-300 images per person (minimum 50)")
    print("  • Include various angles: frontal, profile, 45-degree")
    print("  • Include different lighting conditions")
    print("  • Include different expressions")
    print("  • Use high-quality images (at least 640x480)")
    print("  • Ensure faces are clearly visible")
    print()
    
    # Example dataset path (modify this to your actual dataset)
    dataset_dir = "dataset"
    output_dir = "guru_face"
    
    # Check if example dataset exists
    if not os.path.exists(dataset_dir):
        print(f"⚠ Dataset directory not found: {dataset_dir}")
        print()
        print("To run this example:")
        print(f"  1. Create a dataset directory: mkdir {dataset_dir}")
        print(f"  2. Add subdirectories for each person: mkdir {dataset_dir}/PersonName")
        print("  3. Add images to each person's directory")
        print("  4. Run this script again")
        print()
        return
    
    # Validate dataset structure
    print(f"Validating dataset structure: {dataset_dir}")
    is_valid, errors = validate_dataset_structure(dataset_dir)
    
    if not is_valid:
        print("✗ Dataset validation failed:")
        for error in errors:
            print(f"  - {error}")
        return
    
    print("✓ Dataset structure is valid")
    print()
    
    # Check minimum images
    print("Checking image counts per identity...")
    all_valid, identity_counts = check_minimum_images(dataset_dir, minimum=50)
    
    for identity, count in identity_counts.items():
        status = "✓" if count >= 50 else "⚠"
        print(f"  {status} {identity}: {count} images")
    
    if not all_valid:
        print()
        print("⚠ Warning: Some identities have fewer than 50 images.")
        print("  This may result in reduced recognition accuracy.")
        print("  Recommended: 100-300 images per identity for best results.")
    
    print()
    
    # =========================================================================
    # STEP 2: Preprocess Dataset
    # =========================================================================
    print("STEP 2: Preprocessing Dataset")
    print("-" * 80)
    print()
    print("This step will:")
    print("  • Detect faces in all images using RetinaFace")
    print("  • Align faces to standard orientation")
    print("  • Resize faces to 112x112 pixels")
    print("  • Save aligned faces for training")
    print()
    
    aligned_dataset_dir = os.path.join(output_dir, "aligned_dataset")
    
    print(f"Input: {dataset_dir}")
    print(f"Output: {aligned_dataset_dir}")
    print()
    print("Starting preprocessing...")
    
    try:
        result = preprocess_dataset(
            dataset_dir=dataset_dir,
            output_dir=aligned_dataset_dir,
            use_gpu=True  # Set to False if no GPU available
        )
        
        print()
        print("Preprocessing Results:")
        print(f"  Total images: {result.total_images}")
        print(f"  Successfully aligned: {result.successful}")
        print(f"  No face detected: {result.no_face}")
        print(f"  Multiple faces (largest used): {result.multiple_faces}")
        print(f"  Failed: {result.failed}")
        print(f"  Success rate: {(result.successful / result.total_images * 100):.1f}%")
        print()
        
        if result.successful == 0:
            print("✗ No faces were successfully preprocessed!")
            print("  Check that your images contain visible faces.")
            return
        
        print("✓ Preprocessing complete!")
        print()
        
    except Exception as e:
        print(f"✗ Preprocessing failed: {str(e)}")
        return
    
    # =========================================================================
    # STEP 3: Train ArcFace Model
    # =========================================================================
    print("STEP 3: Training ArcFace Model")
    print("-" * 80)
    print()
    print("Training Configuration:")
    
    # Create custom training configuration
    config = TrainingConfig(
        batch_size=32,           # Reduce if running out of memory
        learning_rate=0.1,       # Initial learning rate
        num_epochs=20,           # Number of training epochs
        backbone="r50",          # ResNet-50 backbone
        embedding_size=512,      # 512-dimensional embeddings
        use_gpu=True,            # Use GPU if available
        num_workers=4,           # Data loading workers
        output_dir=os.path.join(output_dir, "model"),
        checkpoint_dir=os.path.join(output_dir, "checkpoints")
    )
    
    print(f"  Batch size: {config.batch_size}")
    print(f"  Learning rate: {config.learning_rate}")
    print(f"  Epochs: {config.num_epochs}")
    print(f"  Backbone: {config.backbone} (ResNet-50)")
    print(f"  Embedding size: {config.embedding_size}")
    print(f"  GPU enabled: {config.use_gpu}")
    print()
    print("Starting training...")
    print("(This may take several hours depending on dataset size and hardware)")
    print()
    
    try:
        model_path = train_arcface_model(aligned_dataset_dir, config)
        
        print()
        print(f"✓ Training complete! Model saved to: {model_path}")
        print()
        
    except Exception as e:
        print(f"✗ Training failed: {str(e)}")
        return
    
    # =========================================================================
    # STEP 4: Export to ONNX
    # =========================================================================
    print("STEP 4: Exporting to ONNX Format")
    print("-" * 80)
    print()
    print("ONNX format provides:")
    print("  • Faster inference (50%+ speedup)")
    print("  • Cross-platform compatibility")
    print("  • Optimized for production deployment")
    print()
    
    onnx_path = os.path.join(output_dir, "model", "guru_face_model.onnx")
    
    print(f"PyTorch model: {model_path}")
    print(f"ONNX output: {onnx_path}")
    print()
    print("Exporting...")
    
    try:
        success = export_to_onnx(
            pytorch_model_path=model_path,
            output_path=onnx_path,
            verify=True
        )
        
        if not success:
            print("✗ ONNX export failed!")
            return
        
        print()
        print(f"✓ ONNX export complete! Model saved to: {onnx_path}")
        print()
        
    except Exception as e:
        print(f"✗ ONNX export failed: {str(e)}")
        return
    
    # =========================================================================
    # STEP 5: Validate ONNX Model
    # =========================================================================
    print("STEP 5: Validating ONNX Model")
    print("-" * 80)
    print()
    print("Validating that ONNX and PyTorch models produce identical embeddings...")
    print()
    
    try:
        matches = validate_onnx_pytorch_equivalence(
            pytorch_model_path=model_path,
            onnx_model_path=onnx_path,
            tolerance=0.001,
            num_samples=10
        )
        
        if not matches:
            print("✗ Validation failed! Models do not produce equivalent embeddings.")
            return
        
        print()
        print("✓ Validation passed! ONNX model is ready for production use.")
        print()
        
    except Exception as e:
        print(f"✗ Validation failed: {str(e)}")
        return
    
    # =========================================================================
    # Complete!
    # =========================================================================
    print("=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)
    print()
    print("Your custom face recognition model is ready!")
    print()
    print("Model files:")
    print(f"  PyTorch: {model_path}")
    print(f"  ONNX: {onnx_path}")
    print()
    print("Next steps:")
    print("  1. Test the model with the recognition engine")
    print("     See: examples/recognize_webcam.py")
    print()
    print("  2. Add new identities without retraining")
    print("     See: examples/add_identity.py")
    print()
    print("  3. Integrate with your AI agent")
    print("     See: guru_vision/README_ENGINE.md")
    print()
    print("For more information:")
    print("  • Training guide: TRAINING_GUIDE.md")
    print("  • API documentation: guru_vision/training/README.md")
    print("=" * 80)


if __name__ == "__main__":
    main()
