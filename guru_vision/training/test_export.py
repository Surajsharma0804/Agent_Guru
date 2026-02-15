"""
Unit tests for ONNX export functionality.

Tests the export_to_onnx and validate_onnx_pytorch_equivalence functions.
"""

import os
import tempfile
import shutil
import pytest
import torch
import torch.nn as nn
import numpy as np

from guru_vision.training.export import (
    export_to_onnx,
    verify_onnx_model,
    validate_onnx_pytorch_equivalence
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def dummy_pytorch_model(temp_dir):
    """Create a dummy PyTorch model for testing."""
    import torchvision.models as models
    
    # Create a simple ResNet-50 model
    model = models.resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 512)
    
    # Save as checkpoint
    model_path = os.path.join(temp_dir, "test_model.pth")
    torch.save({
        'backbone_state_dict': model.state_dict(),
        'embedding_size': 512,
        'backbone': 'r50',
        'val_acc': 95.0
    }, model_path)
    
    return model_path


def test_export_to_onnx_basic(dummy_pytorch_model, temp_dir):
    """Test basic ONNX export functionality."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model
    success = export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False  # Skip verification for speed
    )
    
    assert success, "Export should succeed"
    assert os.path.exists(output_path), "ONNX file should be created"


def test_export_to_onnx_with_verification(dummy_pytorch_model, temp_dir):
    """Test ONNX export with verification enabled."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model with verification
    success = export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=True
    )
    
    assert success, "Export with verification should succeed"
    assert os.path.exists(output_path), "ONNX file should be created"


def test_export_to_onnx_missing_file(temp_dir):
    """Test export with non-existent PyTorch model."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    with pytest.raises(FileNotFoundError):
        export_to_onnx(
            pytorch_model_path="nonexistent_model.pth",
            output_path=output_path
        )


def test_export_to_onnx_custom_opset(dummy_pytorch_model, temp_dir):
    """Test ONNX export with custom opset version."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export with opset version 12
    success = export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        opset_version=12,
        verify=False
    )
    
    assert success, "Export with custom opset should succeed"
    assert os.path.exists(output_path), "ONNX file should be created"


def test_verify_onnx_model(dummy_pytorch_model, temp_dir):
    """Test ONNX model verification."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model first
    export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False
    )
    
    # Verify the exported model
    is_valid = verify_onnx_model(output_path)
    
    assert is_valid, "Exported ONNX model should be valid"


def test_verify_onnx_model_invalid_file(temp_dir):
    """Test verification with invalid ONNX file."""
    invalid_path = os.path.join(temp_dir, "invalid.onnx")
    
    # Create an invalid file
    with open(invalid_path, 'w') as f:
        f.write("This is not a valid ONNX file")
    
    # Verification should fail
    is_valid = verify_onnx_model(invalid_path)
    
    assert not is_valid, "Invalid ONNX file should fail verification"


def test_validate_onnx_pytorch_equivalence(dummy_pytorch_model, temp_dir):
    """Test ONNX-PyTorch equivalence validation."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model
    export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False
    )
    
    # Validate equivalence
    matches = validate_onnx_pytorch_equivalence(
        pytorch_model_path=dummy_pytorch_model,
        onnx_model_path=output_path,
        tolerance=0.001,
        num_samples=5
    )
    
    assert matches, "ONNX and PyTorch models should produce equivalent embeddings"


def test_validate_equivalence_with_tight_tolerance(dummy_pytorch_model, temp_dir):
    """Test equivalence validation with very tight tolerance."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model
    export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False
    )
    
    # Validate with tight tolerance
    matches = validate_onnx_pytorch_equivalence(
        pytorch_model_path=dummy_pytorch_model,
        onnx_model_path=output_path,
        tolerance=0.0001,  # Very tight tolerance
        num_samples=3
    )
    
    # Should still pass with tight tolerance
    assert matches, "Models should match even with tight tolerance"


def test_export_creates_output_directory(dummy_pytorch_model, temp_dir):
    """Test that export creates output directory if it doesn't exist."""
    output_path = os.path.join(temp_dir, "subdir", "nested", "test_model.onnx")
    
    # Export should create the directory structure
    success = export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False
    )
    
    assert success, "Export should succeed"
    assert os.path.exists(output_path), "ONNX file should be created"
    assert os.path.exists(os.path.dirname(output_path)), "Output directory should be created"


def test_export_output_shape(dummy_pytorch_model, temp_dir):
    """Test that exported ONNX model has correct output shape."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model
    export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False
    )
    
    # Load ONNX model and check output shape
    import onnxruntime as ort
    session = ort.InferenceSession(output_path, providers=['CPUExecutionProvider'])
    
    # Get output shape
    output_shape = session.get_outputs()[0].shape
    
    # Should be (batch_size, 512) where batch_size is dynamic
    assert len(output_shape) == 2, "Output should be 2D"
    assert output_shape[1] == 512, "Embedding dimension should be 512"


def test_export_input_shape(dummy_pytorch_model, temp_dir):
    """Test that exported ONNX model has correct input shape."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model
    export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False
    )
    
    # Load ONNX model and check input shape
    import onnxruntime as ort
    session = ort.InferenceSession(output_path, providers=['CPUExecutionProvider'])
    
    # Get input shape
    input_shape = session.get_inputs()[0].shape
    
    # Should be (batch_size, 3, 112, 112) where batch_size is dynamic
    assert len(input_shape) == 4, "Input should be 4D"
    assert input_shape[1] == 3, "Should have 3 color channels"
    assert input_shape[2] == 112, "Height should be 112"
    assert input_shape[3] == 112, "Width should be 112"


def test_export_dynamic_batch_size(dummy_pytorch_model, temp_dir):
    """Test that exported ONNX model supports dynamic batch sizes."""
    output_path = os.path.join(temp_dir, "test_model.onnx")
    
    # Export model
    export_to_onnx(
        pytorch_model_path=dummy_pytorch_model,
        output_path=output_path,
        verify=False
    )
    
    # Load ONNX model
    import onnxruntime as ort
    session = ort.InferenceSession(output_path, providers=['CPUExecutionProvider'])
    
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    
    # Test with different batch sizes
    for batch_size in [1, 2, 4, 8]:
        test_input = np.random.randn(batch_size, 3, 112, 112).astype(np.float32)
        outputs = session.run([output_name], {input_name: test_input})
        
        assert outputs[0].shape[0] == batch_size, f"Output batch size should be {batch_size}"
        assert outputs[0].shape[1] == 512, "Embedding dimension should be 512"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
