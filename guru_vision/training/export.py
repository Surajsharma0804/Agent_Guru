"""
GuruVision ONNX Model Export Module

This module provides functions for exporting trained PyTorch ArcFace models to ONNX format
for optimized cross-platform inference using ONNX Runtime.

Requirements: 1.3, 11.1, 11.6, 28.1, 28.7
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

import torch
import torch.nn as nn
import onnx
import onnxruntime as ort


# Configure logging
logger = logging.getLogger(__name__)


def export_to_onnx(
    pytorch_model_path: str,
    output_path: str = "guru_face/model/guru_face_model.onnx",
    input_size: Tuple[int, int, int, int] = (1, 3, 112, 112),
    opset_version: int = 11,
    verify: bool = True
) -> bool:
    """
    Export trained PyTorch model to ONNX format.
    
    This function:
    1. Loads the PyTorch model from checkpoint
    2. Sets the model to evaluation mode
    3. Creates a dummy input tensor
    4. Exports using torch.onnx.export() with specified opset version
    5. Optionally verifies the exported model
    
    Requirements: 1.3, 11.1, 28.1
    
    Args:
        pytorch_model_path: Path to PyTorch model checkpoint (.pth file)
        output_path: Path where ONNX model will be saved (default: guru_face/model/guru_face_model.onnx)
        input_size: Input tensor size as (batch, channels, height, width) (default: (1, 3, 112, 112))
        opset_version: ONNX opset version (default: 11)
        verify: Whether to verify the exported model (default: True)
    
    Returns:
        True if export successful, False otherwise
    
    Raises:
        FileNotFoundError: If PyTorch model file not found
        RuntimeError: If export fails
    
    Example:
        >>> success = export_to_onnx(
        ...     "guru_face/model/guru_face_model.pth",
        ...     "guru_face/model/guru_face_model.onnx"
        ... )
        >>> if success:
        ...     print("Model exported successfully!")
    """
    logger.info("=" * 80)
    logger.info("Starting ONNX Model Export")
    logger.info("=" * 80)
    logger.info(f"PyTorch model: {pytorch_model_path}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Input size: {input_size}")
    logger.info(f"Opset version: {opset_version}")
    
    # Check if PyTorch model exists
    if not os.path.exists(pytorch_model_path):
        error_msg = f"PyTorch model not found: {pytorch_model_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    try:
        # Load PyTorch model
        logger.info("Loading PyTorch model...")
        checkpoint = torch.load(pytorch_model_path, map_location='cpu')
        
        # Get model configuration
        embedding_size = checkpoint.get('embedding_size', 512)
        backbone_type = checkpoint.get('backbone', 'r50')
        
        logger.info(f"Model configuration: backbone={backbone_type}, embedding_size={embedding_size}")
        
        # Initialize backbone architecture
        import torchvision.models as models
        if backbone_type == "r50":
            model = models.resnet50(weights=None)
            model.fc = nn.Linear(model.fc.in_features, embedding_size)
        else:
            raise ValueError(f"Unsupported backbone: {backbone_type}")
        
        # Load trained weights
        model.load_state_dict(checkpoint['backbone_state_dict'])
        
        # Set model to evaluation mode
        model.eval()
        logger.info("Model loaded and set to evaluation mode")
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Create dummy input tensor
        dummy_input = torch.randn(*input_size)
        logger.info(f"Created dummy input tensor: {dummy_input.shape}")
        
        # Export to ONNX
        logger.info("Exporting model to ONNX format...")
        torch.onnx.export(
            model,                          # Model to export
            dummy_input,                    # Dummy input
            output_path,                    # Output file path
            export_params=True,             # Store trained parameters
            opset_version=opset_version,    # ONNX opset version
            do_constant_folding=True,       # Optimize constant folding
            input_names=['input'],          # Input tensor name
            output_names=['output'],        # Output tensor name
            dynamic_axes={                  # Dynamic batch size
                'input': {0: 'batch_size'},
                'output': {0: 'batch_size'}
            }
        )
        
        logger.info(f"Model exported successfully to: {output_path}")
        
        # Verify the exported model if requested
        if verify:
            logger.info("Verifying exported ONNX model...")
            is_valid = verify_onnx_model(output_path)
            if not is_valid:
                logger.error("ONNX model verification failed!")
                return False
            logger.info("ONNX model verification passed!")
        
        logger.info("=" * 80)
        logger.info("ONNX Export Complete!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to export model to ONNX: {str(e)}")
        raise RuntimeError(f"ONNX export failed: {str(e)}")


def verify_onnx_model(onnx_model_path: str) -> bool:
    """
    Verify that the exported ONNX model is valid.
    
    This function:
    1. Loads the ONNX model
    2. Checks the model structure using onnx.checker
    3. Verifies the model can be loaded with ONNX Runtime
    
    Args:
        onnx_model_path: Path to ONNX model file
    
    Returns:
        True if model is valid, False otherwise
    
    Example:
        >>> is_valid = verify_onnx_model("guru_face/model/guru_face_model.onnx")
        >>> if is_valid:
        ...     print("Model is valid!")
    """
    try:
        # Load ONNX model
        logger.info(f"Loading ONNX model from: {onnx_model_path}")
        onnx_model = onnx.load(onnx_model_path)
        
        # Check model structure
        logger.info("Checking ONNX model structure...")
        onnx.checker.check_model(onnx_model)
        logger.info("ONNX model structure is valid")
        
        # Try to load with ONNX Runtime
        logger.info("Loading model with ONNX Runtime...")
        session = ort.InferenceSession(
            onnx_model_path,
            providers=['CPUExecutionProvider']
        )
        
        # Get input/output information
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        output_name = session.get_outputs()[0].name
        output_shape = session.get_outputs()[0].shape
        
        logger.info(f"Input: {input_name}, shape: {input_shape}")
        logger.info(f"Output: {output_name}, shape: {output_shape}")
        
        # Test inference with dummy data
        logger.info("Testing inference with dummy data...")
        # Handle dynamic batch size
        batch_size = 1 if input_shape[0] == 'batch_size' else input_shape[0]
        dummy_input = np.random.randn(batch_size, 3, 112, 112).astype(np.float32)
        
        outputs = session.run([output_name], {input_name: dummy_input})
        logger.info(f"Inference successful! Output shape: {outputs[0].shape}")
        
        return True
        
    except Exception as e:
        logger.error(f"ONNX model verification failed: {str(e)}")
        return False


def validate_onnx_pytorch_equivalence(
    pytorch_model_path: str,
    onnx_model_path: str,
    tolerance: float = 0.001,
    num_samples: int = 10
) -> bool:
    """
    Validate that ONNX model produces identical embeddings to PyTorch model.
    
    This function:
    1. Loads both PyTorch and ONNX models
    2. Runs the same random inputs through both models
    3. Compares the outputs and checks they match within tolerance
    
    Requirements: 11.6, 28.7
    
    Args:
        pytorch_model_path: Path to PyTorch model checkpoint (.pth file)
        onnx_model_path: Path to ONNX model file
        tolerance: Maximum allowed difference between embeddings (default: 0.001)
        num_samples: Number of random samples to test (default: 10)
    
    Returns:
        True if embeddings match within tolerance, False otherwise
    
    Example:
        >>> matches = validate_onnx_pytorch_equivalence(
        ...     "guru_face/model/guru_face_model.pth",
        ...     "guru_face/model/guru_face_model.onnx",
        ...     tolerance=0.001
        ... )
        >>> if matches:
        ...     print("Models produce identical embeddings!")
    """
    logger.info("=" * 80)
    logger.info("Validating ONNX-PyTorch Equivalence")
    logger.info("=" * 80)
    logger.info(f"PyTorch model: {pytorch_model_path}")
    logger.info(f"ONNX model: {onnx_model_path}")
    logger.info(f"Tolerance: {tolerance}")
    logger.info(f"Test samples: {num_samples}")
    
    try:
        # Load PyTorch model
        logger.info("Loading PyTorch model...")
        checkpoint = torch.load(pytorch_model_path, map_location='cpu')
        
        embedding_size = checkpoint.get('embedding_size', 512)
        backbone_type = checkpoint.get('backbone', 'r50')
        
        import torchvision.models as models
        if backbone_type == "r50":
            pytorch_model = models.resnet50(weights=None)
            pytorch_model.fc = nn.Linear(pytorch_model.fc.in_features, embedding_size)
        else:
            raise ValueError(f"Unsupported backbone: {backbone_type}")
        
        pytorch_model.load_state_dict(checkpoint['backbone_state_dict'])
        pytorch_model.eval()
        logger.info("PyTorch model loaded")
        
        # Load ONNX model
        logger.info("Loading ONNX model...")
        ort_session = ort.InferenceSession(
            onnx_model_path,
            providers=['CPUExecutionProvider']
        )
        input_name = ort_session.get_inputs()[0].name
        output_name = ort_session.get_outputs()[0].name
        logger.info("ONNX model loaded")
        
        # Test with multiple random samples
        max_diff = 0.0
        all_passed = True
        
        logger.info(f"Testing with {num_samples} random samples...")
        
        for i in range(num_samples):
            # Generate random input
            test_input = np.random.randn(1, 3, 112, 112).astype(np.float32)
            
            # PyTorch inference
            with torch.no_grad():
                pytorch_input = torch.from_numpy(test_input)
                pytorch_output = pytorch_model(pytorch_input).numpy()
            
            # ONNX inference
            onnx_output = ort_session.run(
                [output_name],
                {input_name: test_input}
            )[0]
            
            # Compute difference
            diff = np.abs(pytorch_output - onnx_output).max()
            max_diff = max(max_diff, diff)
            
            # Check if within tolerance
            if diff > tolerance:
                logger.warning(
                    f"Sample {i+1}: Difference {diff:.6f} exceeds tolerance {tolerance}"
                )
                all_passed = False
            else:
                logger.debug(f"Sample {i+1}: Difference {diff:.6f} (OK)")
        
        # Log results
        logger.info("-" * 80)
        logger.info(f"Maximum difference across all samples: {max_diff:.6f}")
        logger.info(f"Tolerance threshold: {tolerance}")
        
        if all_passed:
            logger.info("✓ All samples passed! ONNX and PyTorch models are equivalent.")
            logger.info("=" * 80)
            return True
        else:
            logger.error("✗ Some samples failed! Models are NOT equivalent.")
            logger.info("=" * 80)
            return False
            
    except Exception as e:
        logger.error(f"Validation failed with error: {str(e)}")
        logger.info("=" * 80)
        return False


if __name__ == "__main__":
    """
    Example usage for ONNX export and validation.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Export PyTorch model to ONNX format")
    parser.add_argument("--pytorch-model", type=str, required=True,
                       help="Path to PyTorch model checkpoint (.pth)")
    parser.add_argument("--output", type=str, default="guru_face/model/guru_face_model.onnx",
                       help="Output path for ONNX model")
    parser.add_argument("--opset", type=int, default=11,
                       help="ONNX opset version")
    parser.add_argument("--no-verify", action="store_true",
                       help="Skip verification after export")
    parser.add_argument("--validate", action="store_true",
                       help="Validate ONNX-PyTorch equivalence")
    parser.add_argument("--tolerance", type=float, default=0.001,
                       help="Tolerance for equivalence validation")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Export model
    success = export_to_onnx(
        pytorch_model_path=args.pytorch_model,
        output_path=args.output,
        opset_version=args.opset,
        verify=not args.no_verify
    )
    
    if not success:
        print("\nExport failed!")
        exit(1)
    
    # Validate equivalence if requested
    if args.validate:
        print("\nValidating ONNX-PyTorch equivalence...")
        matches = validate_onnx_pytorch_equivalence(
            pytorch_model_path=args.pytorch_model,
            onnx_model_path=args.output,
            tolerance=args.tolerance
        )
        
        if matches:
            print("\n✓ Validation passed! Models are equivalent.")
        else:
            print("\n✗ Validation failed! Models are NOT equivalent.")
            exit(1)
    
    print(f"\nONNX model saved to: {args.output}")
