"""
Tests for GuruVision Engine Identity Management Methods

This test file verifies the identity management functionality including:
- add_identity()
- remove_identity()
- get_identities()
- update_permission()

Requirements tested: 16.1, 16.2, 16.3, 16.4, 16.5, 12.3, 12.4, 9.5, 12.2
"""

import pytest
import numpy as np
import tempfile
import shutil
import os
from pathlib import Path
from guru_vision.engine import GuruVisionEngine, IdentityInfo


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_config_file(temp_dir):
    """Create a minimal config file for testing."""
    config_path = os.path.join(temp_dir, "test_config.yaml")
    config_content = f"""
onnx_model_path: "test_model.onnx"
database_path: "{os.path.join(temp_dir, 'test_db.json')}"
use_gpu: false
enable_liveness: false
enable_emotion: false
enable_tracking: false
log_level: "ERROR"
log_file: "{os.path.join(temp_dir, 'test.log')}"
"""
    with open(config_path, 'w') as f:
        f.write(config_content)
    return config_path


@pytest.fixture
def sample_face_image():
    """Create a sample face image for testing."""
    # Create a simple 112x112x3 BGR image
    image = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    return image


def test_add_identity_not_initialized():
    """Test that add_identity raises error when engine not initialized."""
    engine = GuruVisionEngine()
    
    with pytest.raises(RuntimeError, match="Engine not initialized"):
        engine.add_identity("test_user", [np.zeros((112, 112, 3), dtype=np.uint8)])


def test_add_identity_invalid_name():
    """Test that add_identity validates identity name."""
    engine = GuruVisionEngine()
    engine.initialized = True  # Mock initialization
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        engine.add_identity("", [np.zeros((112, 112, 3), dtype=np.uint8)])
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        engine.add_identity(None, [np.zeros((112, 112, 3), dtype=np.uint8)])


def test_add_identity_invalid_images():
    """Test that add_identity validates images list."""
    engine = GuruVisionEngine()
    engine.initialized = True  # Mock initialization
    
    with pytest.raises(ValueError, match="Images must be a non-empty list"):
        engine.add_identity("test_user", [])
    
    with pytest.raises(ValueError, match="Images must be a non-empty list"):
        engine.add_identity("test_user", None)


def test_add_identity_invalid_permission():
    """Test that add_identity validates permission level."""
    from guru_vision.utils.logging import get_logger
    
    engine = GuruVisionEngine()
    engine.initialized = True  # Mock initialization
    engine.logger = get_logger(__name__)  # Add logger
    
    with pytest.raises(ValueError, match="Invalid permission_level"):
        engine.add_identity(
            "test_user",
            [np.zeros((112, 112, 3), dtype=np.uint8)],
            permission_level="invalid"
        )


def test_remove_identity_not_initialized():
    """Test that remove_identity raises error when engine not initialized."""
    engine = GuruVisionEngine()
    
    with pytest.raises(RuntimeError, match="Engine not initialized"):
        engine.remove_identity("test_user")


def test_remove_identity_invalid_name():
    """Test that remove_identity validates identity name."""
    engine = GuruVisionEngine()
    engine.initialized = True  # Mock initialization
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        engine.remove_identity("")
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        engine.remove_identity(None)


def test_get_identities_not_initialized():
    """Test that get_identities raises error when engine not initialized."""
    engine = GuruVisionEngine()
    
    with pytest.raises(RuntimeError, match="Engine not initialized"):
        engine.get_identities()


def test_update_permission_not_initialized():
    """Test that update_permission raises error when engine not initialized."""
    engine = GuruVisionEngine()
    
    with pytest.raises(RuntimeError, match="Engine not initialized"):
        engine.update_permission("test_user", "admin")


def test_update_permission_invalid_name():
    """Test that update_permission validates identity name."""
    engine = GuruVisionEngine()
    engine.initialized = True  # Mock initialization
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        engine.update_permission("", "admin")
    
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        engine.update_permission(None, "admin")


def test_update_permission_invalid_level():
    """Test that update_permission validates permission level."""
    engine = GuruVisionEngine()
    engine.initialized = True  # Mock initialization
    
    with pytest.raises(ValueError, match="Invalid permission_level"):
        engine.update_permission("test_user", "invalid")


def test_identity_info_structure():
    """Test IdentityInfo dataclass structure."""
    info = IdentityInfo(
        name="John Doe",
        permission_level="user",
        num_embeddings=10,
        date_added="2024-01-15T10:30:00Z",
        metadata={"source": "webcam"}
    )
    
    assert info.name == "John Doe"
    assert info.permission_level == "user"
    assert info.num_embeddings == 10
    assert info.date_added == "2024-01-15T10:30:00Z"
    assert info.metadata["source"] == "webcam"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
