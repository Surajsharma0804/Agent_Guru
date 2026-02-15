"""
Example usage of the dataset preprocessing module.

This script demonstrates how to:
1. Validate dataset structure
2. Check minimum image requirements
3. Preprocess a dataset for training

Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 29.1
"""

import os
import logging
from guru_vision.training.preprocess import (
    validate_dataset_structure,
    check_minimum_images,
    preprocess_dataset
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main example function."""
    
    # Define paths
    dataset_dir = "dataset"  # Input dataset directory
    output_dir = "aligned_dataset"  # Output directory for aligned faces
    
    print("=" * 60)
    print("GuruVision Dataset Preprocessing Example")
    print("=" * 60)
    print()
    
    # Step 1: Validate dataset structure
    print("Step 1: Validating dataset structure...")
    print(f"Dataset directory: {dataset_dir}")
    print()
    
    is_valid, errors = validate_dataset_structure(dataset_dir)
    
    if not is_valid:
        print("❌ Dataset structure validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        print()
        print("Please organize your dataset as follows:")
        print("  dataset/")
        print("    ├── Identity1/")
        print("    │   ├── image1.jpg")
        print("    │   ├── image2.jpg")
        print("    │   └── ...")
        print("    ├── Identity2/")
        print("    │   ├── image1.jpg")
        print("    │   └── ...")
        print("    └── ...")
        return
    
    print("✓ Dataset structure is valid")
    print()
    
    # Step 2: Check minimum image requirements
    print("Step 2: Checking minimum image requirements...")
    print("Recommended: 100-300 images per identity")
    print("Minimum: 50 images per identity")
    print()
    
    all_valid, identity_counts = check_minimum_images(dataset_dir, minimum=50)
    
    print("Image counts per identity:")
    for identity_name, count in identity_counts.items():
        status = "✓" if count >= 50 else "⚠"
        recommendation = ""
        if count < 50:
            recommendation = " (below minimum - may reduce accuracy)"
        elif count < 100:
            recommendation = " (consider adding more images for better accuracy)"
        
        print(f"  {status} {identity_name}: {count} images{recommendation}")
    print()
    
    if not all_valid:
        print("⚠ Warning: Some identities have fewer than 50 images")
        print("  This may result in reduced recognition accuracy.")
        print()
        
        response = input("Continue with preprocessing? (y/n): ")
        if response.lower() != 'y':
            print("Preprocessing cancelled.")
            return
        print()
    
    # Step 3: Preprocess dataset
    print("Step 3: Preprocessing dataset...")
    print(f"Input directory: {dataset_dir}")
    print(f"Output directory: {output_dir}")
    print()
    print("This will:")
    print("  1. Detect faces in each image")
    print("  2. Align faces to standard orientation")
    print("  3. Resize to 112x112 pixels")
    print("  4. Save aligned faces to output directory")
    print()
    
    # Ask about GPU usage
    use_gpu_input = input("Use GPU acceleration if available? (y/n, default: y): ")
    use_gpu = use_gpu_input.lower() != 'n'
    print()
    
    print("Starting preprocessing...")
    print("-" * 60)
    
    try:
        result = preprocess_dataset(
            dataset_dir=dataset_dir,
            output_dir=output_dir,
            use_gpu=use_gpu
        )
        
        # Display results
        print()
        print("=" * 60)
        print("Preprocessing Results")
        print("=" * 60)
        print(f"Total images processed: {result.total_images}")
        print(f"Successfully aligned: {result.successful}")
        print(f"No face detected: {result.no_face}")
        print(f"Multiple faces (largest used): {result.multiple_faces}")
        print(f"Failed: {result.failed}")
        print(f"Identities processed: {result.identities_processed}")
        print()
        
        # Display per-identity statistics
        print("Per-Identity Statistics:")
        print("-" * 60)
        for identity_name, stats in result.statistics.items():
            success_rate = (stats['successful'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"{identity_name}:")
            print(f"  Total: {stats['total']}")
            print(f"  Successful: {stats['successful']} ({success_rate:.1f}%)")
            print(f"  No face: {stats['no_face']}")
            print(f"  Multiple faces: {stats['multiple_faces']}")
            print(f"  Failed: {stats['failed']}")
            print()
        
        print("=" * 60)
        print(f"✓ Preprocessing complete!")
        print(f"Aligned faces saved to: {output_dir}")
        print()
        print("Next steps:")
        print("  1. Review the aligned faces in the output directory")
        print("  2. Remove any incorrectly aligned faces")
        print("  3. Use the aligned dataset for model training")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Preprocessing failed!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print()
        print("Please check:")
        print("  - Dataset directory exists and is accessible")
        print("  - Images are in supported formats (jpg, jpeg, png, bmp)")
        print("  - Face detection model is properly installed")
        print("  - Sufficient disk space for output directory")
        return


if __name__ == "__main__":
    main()
