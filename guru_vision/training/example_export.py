"""
Example script demonstrating ONNX model export functionality.

This script shows how to:
1. Export a trained PyTorch model to ONNX format
2. Verify the exported ONNX model
3. Validate ONNX-PyTorch equivalence

Requirements: 1.3, 11.1, 11.6, 28.1, 28.7
"""

import os
import logging
from guru_vision.training.export import (
    export_to_onnx,
    verify_onnx_model,
    validate_onnx_pytorch_equivalence
)


def main():
    """
    Example workflow for exporting and validating ONNX models.
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("GuruVision ONNX Export Example")
    print("=" * 80)
    print()
    
    # Define paths
    pytorch_model_path = "guru_face/model/guru_face_model.pth"
    onnx_model_path = "guru_face/model/guru_face_model.onnx"
    
    # Check if PyTorch model exists
    if not os.path.exists(pytorch_model_path):
        print(f"Error: PyTorch model not found at {pytorch_model_path}")
        print("Please train a model first using the training pipeline.")
        print()
        print("Example:")
        print("  python guru_vision/training/example_train.py --dataset aligned_dataset")
        return
    
    print(f"Found PyTorch model: {pytorch_model_path}")
    print()
    
    # =========================================================================
    # Step 1: Export PyTorch model to ONNX format
    # =========================================================================
    print("Step 1: Exporting PyTorch model to ONNX format...")
    print("-" * 80)
    
    success = export_to_onnx(
        pytorch_model_path=pytorch_model_path,
        output_path=onnx_model_path,
        opset_version=11,
        verify=True  # Automatically verify after export
    )
    
    if not success:
        print("Export failed! Check the logs for details.")
        return
    
    print()
    print(f"✓ Model exported successfully to: {onnx_model_path}")
    print()
    
    # =========================================================================
    # Step 2: Verify the exported ONNX model (optional, already done above)
    # =========================================================================
    print("Step 2: Verifying ONNX model structure...")
    print("-" * 80)
    
    is_valid = verify_onnx_model(onnx_model_path)
    
    if is_valid:
        print("✓ ONNX model is valid and can be loaded with ONNX Runtime")
    else:
        print("✗ ONNX model verification failed")
        return
    
    print()
    
    # =========================================================================
    # Step 3: Validate ONNX-PyTorch equivalence
    # =========================================================================
    print("Step 3: Validating ONNX-PyTorch equivalence...")
    print("-" * 80)
    
    matches = validate_onnx_pytorch_equivalence(
        pytorch_model_path=pytorch_model_path,
        onnx_model_path=onnx_model_path,
        tolerance=0.001,
        num_samples=10
    )
    
    if matches:
        print("✓ ONNX and PyTorch models produce identical embeddings!")
        print("  The models are equivalent within tolerance of 0.001")
    else:
        print("✗ Models are NOT equivalent")
        print("  Consider re-exporting or checking the model")
        return
    
    print()
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 80)
    print("Export Complete!")
    print("=" * 80)
    print()
    print("Your ONNX model is ready for production deployment:")
    print(f"  Model path: {onnx_model_path}")
    print()
    print("Next steps:")
    print("  1. Use the ONNX model with ONNX Runtime for fast inference")
    print("  2. Deploy to production systems (CPU or GPU)")
    print("  3. Integrate with the GuruVision recognition engine")
    print()
    print("Example usage:")
    print("  from guru_vision.recognition.recognizer import FaceRecognizer")
    print(f"  recognizer = FaceRecognizer('{onnx_model_path}')")
    print("  embedding = recognizer.extract_embedding(aligned_face)")
    print()


def export_with_custom_settings():
    """
    Example of exporting with custom settings.
    """
    print("=" * 80)
    print("Custom Export Settings Example")
    print("=" * 80)
    print()
    
    # Custom paths
    pytorch_model = "guru_face/checkpoints/checkpoint_epoch_20.pth"
    onnx_output = "guru_face/model/custom_model.onnx"
    
    # Export with custom opset version
    success = export_to_onnx(
        pytorch_model_path=pytorch_model,
        output_path=onnx_output,
        opset_version=12,  # Use opset version 12
        verify=False  # Skip automatic verification
    )
    
    if success:
        print(f"✓ Custom model exported to: {onnx_output}")
        
        # Manually verify with custom tolerance
        matches = validate_onnx_pytorch_equivalence(
            pytorch_model_path=pytorch_model,
            onnx_model_path=onnx_output,
            tolerance=0.0001,  # Tighter tolerance
            num_samples=20  # More test samples
        )
        
        if matches:
            print("✓ Validation passed with tight tolerance!")
        else:
            print("✗ Validation failed")
    else:
        print("✗ Export failed")


def batch_export_checkpoints():
    """
    Example of exporting multiple checkpoint files.
    """
    print("=" * 80)
    print("Batch Export Example")
    print("=" * 80)
    print()
    
    checkpoint_dir = "guru_face/checkpoints"
    output_dir = "guru_face/onnx_models"
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all checkpoint files
    if not os.path.exists(checkpoint_dir):
        print(f"Checkpoint directory not found: {checkpoint_dir}")
        return
    
    checkpoints = [
        f for f in os.listdir(checkpoint_dir)
        if f.endswith('.pth')
    ]
    
    if not checkpoints:
        print(f"No checkpoint files found in {checkpoint_dir}")
        return
    
    print(f"Found {len(checkpoints)} checkpoint(s) to export")
    print()
    
    # Export each checkpoint
    for checkpoint_file in checkpoints:
        checkpoint_path = os.path.join(checkpoint_dir, checkpoint_file)
        onnx_file = checkpoint_file.replace('.pth', '.onnx')
        onnx_path = os.path.join(output_dir, onnx_file)
        
        print(f"Exporting {checkpoint_file}...")
        
        try:
            success = export_to_onnx(
                pytorch_model_path=checkpoint_path,
                output_path=onnx_path,
                verify=True
            )
            
            if success:
                print(f"  ✓ Exported to {onnx_file}")
            else:
                print(f"  ✗ Export failed")
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
        
        print()
    
    print("Batch export complete!")


if __name__ == "__main__":
    # Run the main example
    main()
    
    # Uncomment to try other examples:
    # export_with_custom_settings()
    # batch_export_checkpoints()
