"""
Property-Based Tests for ONNX Export Module

This module contains property-based tests using Hypothesis to validate
universal correctness properties of the ONNX export operations.

Properties tested:
- Property 15: ONNX-PyTorch Embedding Equivalence
"""

import pytest
import numpy as np
import tempfile
import os
import shutil
import torch
import torch.nn as nn
import torchvision.models as models
from hypothesis import given, strategies as st, settings, assume, HealthCheck
import onnxruntime as ort

from guru_vision.training.export import (
    export_to_onnx,
    validate_onnx_pytorch_equivalence
)


# Custom strategies for generating test data

@st.composite
def tolerance_value(draw):
    """Generate a valid tolerance value for equivalence testing."""
    # Tolerance should be small but reasonable (0.0001 to 0.01)
    return draw(st.floats(min_value=0.0001, max_value=0.01))


@st.composite
def embedding_size(draw):
    """Generate a valid embedding size."""
    # Common embedding sizes: 128, 256, 512
    return draw(st.sampled_from([128, 256, 512]))


@st.composite
def batch_size(draw):
    """Generate a valid batch size for testing."""
    return draw(st.integers(min_value=1, max_value=8))


@st.composite
def input_image_strategy(draw, batch_size=1):
    """
    Generate a random test input image for face recognition.
    
    Args:
        batch_size: Number of images in batch
    
    Returns:
        numpy array of shape (batch_size, 3, 112, 112)
    """
    # Generate random pixel values in range [-1, 1] (typical normalization)
    return draw(st.builds(
        lambda: np.random.randn(batch_size, 3, 112, 112).astype(np.float32)
    ))


def create_test_pytorch_model(embedding_size=512, temp_dir=None):
    """
    Create a test PyTorch model and save it as a checkpoint.
    
    Args:
        embedding_size: Size of the embedding vector
        temp_dir: Directory to save the model
    
    Returns:
        Path to the saved model checkpoint
    """
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp()
    
    # Create a simple ResNet-50 model
    model = models.resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, embedding_size)
    
    # Initialize with small random weights for faster testing
    for param in model.parameters():
        if param.dim() > 1:
            nn.init.xavier_uniform_(param, gain=0.1)
    
    # Save as checkpoint
    model_path = os.path.join(temp_dir, "test_model.pth")
    torch.save({
        'backbone_state_dict': model.state_dict(),
        'embedding_size': embedding_size,
        'backbone': 'r50',
        'val_acc': 95.0
    }, model_path)
    
    return model_path, model


# Property 15: ONNX-PyTorch Embedding Equivalence
# **Validates: Requirements 11.6, 28.7**

@given(
    tolerance=tolerance_value(),
    num_test_samples=st.integers(min_value=1, max_value=10)
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_15_onnx_pytorch_embedding_equivalence(tolerance, num_test_samples):
    """
    Property 15: ONNX-PyTorch Embedding Equivalence
    
    For any input face image, when processed by both the PyTorch model and
    the exported ONNX model, the resulting embeddings should be identical
    within 0.001 tolerance.
    
    **Validates: Requirements 11.6, 28.7**
    """
    # Create temporary directory for models
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create and save PyTorch model
        pytorch_model_path, pytorch_model = create_test_pytorch_model(
            embedding_size=512,
            temp_dir=temp_dir
        )
        
        # Export to ONNX
        onnx_model_path = os.path.join(temp_dir, "test_model.onnx")
        export_success = export_to_onnx(
            pytorch_model_path=pytorch_model_path,
            output_path=onnx_model_path,
            verify=False  # Skip verification for speed
        )
        
        assert export_success, "ONNX export should succeed"
        assert os.path.exists(onnx_model_path), "ONNX model file should be created"
        
        # Load ONNX model
        ort_session = ort.InferenceSession(
            onnx_model_path,
            providers=['CPUExecutionProvider']
        )
        input_name = ort_session.get_inputs()[0].name
        output_name = ort_session.get_outputs()[0].name
        
        # Set PyTorch model to eval mode
        pytorch_model.eval()
        
        # Test with multiple random samples
        max_diff = 0.0
        
        for i in range(num_test_samples):
            # Generate random input (face image)
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
            
            # Property: Embeddings should be identical within tolerance
            assert diff <= tolerance, \
                f"Sample {i+1}: Embedding difference {diff:.6f} exceeds tolerance {tolerance:.6f}"
            
            # Property: Output shapes should match
            assert pytorch_output.shape == onnx_output.shape, \
                f"Output shapes should match: PyTorch {pytorch_output.shape} vs ONNX {onnx_output.shape}"
            
            # Property: Embedding dimension should be 512
            assert pytorch_output.shape[1] == 512, \
                f"Embedding dimension should be 512, got {pytorch_output.shape[1]}"
            assert onnx_output.shape[1] == 512, \
                f"ONNX embedding dimension should be 512, got {onnx_output.shape[1]}"
        
        # Property: Maximum difference across all samples should be within tolerance
        assert max_diff <= tolerance, \
            f"Maximum difference {max_diff:.6f} across all samples exceeds tolerance {tolerance:.6f}"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@given(
    embedding_dim=embedding_size(),
    batch_sz=batch_size()
)
@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_15_equivalence_with_different_configs(embedding_dim, batch_sz):
    """
    Property 15 Extension: ONNX-PyTorch Equivalence with Different Configurations
    
    For any embedding dimension and batch size, the ONNX and PyTorch models
    should produce equivalent embeddings within tolerance.
    
    **Validates: Requirements 11.6, 28.7**
    """
    # Create temporary directory for models
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create and save PyTorch model with specific embedding size
        pytorch_model_path, pytorch_model = create_test_pytorch_model(
            embedding_size=embedding_dim,
            temp_dir=temp_dir
        )
        
        # Export to ONNX
        onnx_model_path = os.path.join(temp_dir, "test_model.onnx")
        export_success = export_to_onnx(
            pytorch_model_path=pytorch_model_path,
            output_path=onnx_model_path,
            verify=False
        )
        
        assert export_success, "ONNX export should succeed"
        
        # Load ONNX model
        ort_session = ort.InferenceSession(
            onnx_model_path,
            providers=['CPUExecutionProvider']
        )
        input_name = ort_session.get_inputs()[0].name
        output_name = ort_session.get_outputs()[0].name
        
        # Set PyTorch model to eval mode
        pytorch_model.eval()
        
        # Generate random input with specified batch size
        test_input = np.random.randn(batch_sz, 3, 112, 112).astype(np.float32)
        
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
        
        # Property: Embeddings should be identical within 0.001 tolerance
        tolerance = 0.001
        assert diff <= tolerance, \
            f"Embedding difference {diff:.6f} exceeds tolerance {tolerance:.6f} " \
            f"for embedding_dim={embedding_dim}, batch_size={batch_sz}"
        
        # Property: Output shapes should match
        assert pytorch_output.shape == onnx_output.shape, \
            f"Output shapes should match: PyTorch {pytorch_output.shape} vs ONNX {onnx_output.shape}"
        
        # Property: Batch dimension should match input
        assert pytorch_output.shape[0] == batch_sz, \
            f"PyTorch output batch size should be {batch_sz}, got {pytorch_output.shape[0]}"
        assert onnx_output.shape[0] == batch_sz, \
            f"ONNX output batch size should be {batch_sz}, got {onnx_output.shape[0]}"
        
        # Property: Embedding dimension should match configuration
        assert pytorch_output.shape[1] == embedding_dim, \
            f"PyTorch embedding dimension should be {embedding_dim}, got {pytorch_output.shape[1]}"
        assert onnx_output.shape[1] == embedding_dim, \
            f"ONNX embedding dimension should be {embedding_dim}, got {onnx_output.shape[1]}"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@given(num_samples=st.integers(min_value=5, max_value=20))
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_15_validate_function_equivalence(num_samples):
    """
    Property 15 Validation: validate_onnx_pytorch_equivalence Function
    
    The validate_onnx_pytorch_equivalence function should correctly identify
    when models produce equivalent embeddings within tolerance.
    
    **Validates: Requirements 11.6, 28.7**
    """
    # Create temporary directory for models
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create and save PyTorch model
        pytorch_model_path, _ = create_test_pytorch_model(
            embedding_size=512,
            temp_dir=temp_dir
        )
        
        # Export to ONNX
        onnx_model_path = os.path.join(temp_dir, "test_model.onnx")
        export_success = export_to_onnx(
            pytorch_model_path=pytorch_model_path,
            output_path=onnx_model_path,
            verify=False
        )
        
        assert export_success, "ONNX export should succeed"
        
        # Validate equivalence with standard tolerance
        tolerance = 0.001
        matches = validate_onnx_pytorch_equivalence(
            pytorch_model_path=pytorch_model_path,
            onnx_model_path=onnx_model_path,
            tolerance=tolerance,
            num_samples=num_samples
        )
        
        # Property: Validation should pass (models are equivalent)
        assert matches is True, \
            f"validate_onnx_pytorch_equivalence should return True for equivalent models " \
            f"with {num_samples} samples and tolerance {tolerance}"
        
        # Test with very tight tolerance (should still pass for identical models)
        tight_tolerance = 0.0001
        matches_tight = validate_onnx_pytorch_equivalence(
            pytorch_model_path=pytorch_model_path,
            onnx_model_path=onnx_model_path,
            tolerance=tight_tolerance,
            num_samples=min(num_samples, 5)  # Use fewer samples for tight tolerance
        )
        
        # Property: Should still pass with tight tolerance
        assert matches_tight is True, \
            f"validate_onnx_pytorch_equivalence should return True even with tight tolerance {tight_tolerance}"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@given(
    input_variation=st.floats(min_value=-2.0, max_value=2.0),
    num_tests=st.integers(min_value=1, max_value=5)
)
@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_15_equivalence_with_input_variations(input_variation, num_tests):
    """
    Property 15 Robustness: Equivalence Across Input Variations
    
    For any input variation (different pixel value ranges), the ONNX and
    PyTorch models should produce equivalent embeddings.
    
    **Validates: Requirements 11.6, 28.7**
    """
    # Create temporary directory for models
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create and save PyTorch model
        pytorch_model_path, pytorch_model = create_test_pytorch_model(
            embedding_size=512,
            temp_dir=temp_dir
        )
        
        # Export to ONNX
        onnx_model_path = os.path.join(temp_dir, "test_model.onnx")
        export_success = export_to_onnx(
            pytorch_model_path=pytorch_model_path,
            output_path=onnx_model_path,
            verify=False
        )
        
        assert export_success, "ONNX export should succeed"
        
        # Load ONNX model
        ort_session = ort.InferenceSession(
            onnx_model_path,
            providers=['CPUExecutionProvider']
        )
        input_name = ort_session.get_inputs()[0].name
        output_name = ort_session.get_outputs()[0].name
        
        # Set PyTorch model to eval mode
        pytorch_model.eval()
        
        # Test with different input variations
        tolerance = 0.001
        
        for i in range(num_tests):
            # Generate input with variation
            # Base input + variation offset
            test_input = (np.random.randn(1, 3, 112, 112) + input_variation).astype(np.float32)
            
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
            
            # Property: Embeddings should be equivalent regardless of input variation
            assert diff <= tolerance, \
                f"Test {i+1}: Embedding difference {diff:.6f} exceeds tolerance {tolerance:.6f} " \
                f"with input_variation={input_variation:.3f}"
            
            # Property: Both models should produce valid embeddings
            assert not np.isnan(pytorch_output).any(), \
                "PyTorch output should not contain NaN values"
            assert not np.isnan(onnx_output).any(), \
                "ONNX output should not contain NaN values"
            assert not np.isinf(pytorch_output).any(), \
                "PyTorch output should not contain infinite values"
            assert not np.isinf(onnx_output).any(), \
                "ONNX output should not contain infinite values"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


# Additional property: Consistency across multiple exports
@given(seed=st.integers(min_value=0, max_value=1000))
@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
def test_property_15_export_consistency(seed):
    """
    Property 15 Consistency: Multiple Exports Produce Equivalent Models
    
    Exporting the same PyTorch model multiple times should produce ONNX models
    that all give equivalent results.
    
    **Validates: Requirements 11.6, 28.7**
    """
    # Create temporary directory for models
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create and save PyTorch model
        pytorch_model_path, pytorch_model = create_test_pytorch_model(
            embedding_size=512,
            temp_dir=temp_dir
        )
        
        # Export to ONNX multiple times
        onnx_paths = []
        for i in range(3):
            onnx_path = os.path.join(temp_dir, f"test_model_{i}.onnx")
            export_success = export_to_onnx(
                pytorch_model_path=pytorch_model_path,
                output_path=onnx_path,
                verify=False
            )
            assert export_success, f"Export {i+1} should succeed"
            onnx_paths.append(onnx_path)
        
        # Load all ONNX models
        sessions = []
        for onnx_path in onnx_paths:
            session = ort.InferenceSession(
                onnx_path,
                providers=['CPUExecutionProvider']
            )
            sessions.append(session)
        
        # Test with random input (use seed for reproducibility)
        np.random.seed(seed)
        test_input = np.random.randn(1, 3, 112, 112).astype(np.float32)
        
        # Get outputs from all ONNX models
        onnx_outputs = []
        for session in sessions:
            input_name = session.get_inputs()[0].name
            output_name = session.get_outputs()[0].name
            output = session.run([output_name], {input_name: test_input})[0]
            onnx_outputs.append(output)
        
        # Property: All ONNX exports should produce identical results
        tolerance = 1e-6  # Very tight tolerance for identical exports
        for i in range(len(onnx_outputs) - 1):
            diff = np.abs(onnx_outputs[i] - onnx_outputs[i + 1]).max()
            assert diff <= tolerance, \
                f"ONNX exports {i} and {i+1} differ by {diff:.9f}, exceeds tolerance {tolerance:.9f}"
    
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
