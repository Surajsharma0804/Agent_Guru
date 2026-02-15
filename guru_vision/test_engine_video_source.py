"""
Tests for GuruVisionEngine video source integration.

This module tests the integration of video source functionality with the engine:
- Video source initialization
- Frame reading
- Seeking
- Error handling

Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7
"""

import pytest
import numpy as np
import cv2
import tempfile
from pathlib import Path

from guru_vision.engine import GuruVisionEngine
from guru_vision.video_source import VideoSourceError


@pytest.fixture
def engine():
    """Create and initialize a GuruVisionEngine instance."""
    engine = GuruVisionEngine()
    # Mock initialization to avoid loading actual models
    engine.initialized = True
    engine.config = type('Config', (), {
        'camera_index': 0,
        'video_source': None
    })()
    # Mock logger
    engine.logger = type('Logger', (), {
        'info': lambda *args, **kwargs: None,
        'debug': lambda *args, **kwargs: None,
        'error': lambda *args, **kwargs: None,
        'warning': lambda *args, **kwargs: None
    })()
    return engine


@pytest.fixture
def test_images(tmp_path):
    """Create test images in a temporary directory."""
    for i in range(5):
        img_file = tmp_path / f"img_{i:03d}.jpg"
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add some variation
        test_img[i*50:(i+1)*50, :] = [i*50, i*50, i*50]
        cv2.imwrite(str(img_file), test_img)
    return tmp_path


class TestEngineVideoSourceInit:
    """Test video source initialization in engine."""
    
    def test_init_video_source_image_directory(self, engine, test_images):
        """Test initializing video source with image directory."""
        # Requirement 19.4: Support image directories
        success = engine.init_video_source(source=str(test_images))
        
        assert success
        assert engine.video_source is not None
        assert engine.video_source.is_opened
    
    def test_init_video_source_single_image(self, engine, tmp_path):
        """Test initializing video source with single image."""
        # Requirement 19.3: Support individual image files
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), test_img)
        
        success = engine.init_video_source(source=str(img_file))
        
        assert success
        assert engine.video_source is not None
        assert engine.video_source.is_opened
    
    def test_init_video_source_with_camera_index(self, engine):
        """Test initializing video source with camera index override."""
        # Requirement 19.1: Support webcam by device index
        # Note: This will fail if no camera is available, which is expected
        try:
            success = engine.init_video_source(source=None, camera_index=0)
            # If successful, verify it's opened
            if success:
                assert engine.video_source is not None
                assert engine.video_source.is_opened
        except VideoSourceError:
            # Expected if no camera available
            pass
    
    def test_init_video_source_replaces_existing(self, engine, test_images):
        """Test that initializing new source releases old one."""
        # Initialize first source
        img1 = test_images / "img_000.jpg"
        engine.init_video_source(source=str(img1))
        first_source = engine.video_source
        
        # Initialize second source
        img2 = test_images / "img_001.jpg"
        engine.init_video_source(source=str(img2))
        second_source = engine.video_source
        
        # Should be different objects
        assert first_source is not second_source
        # First source should be released
        assert not first_source.is_opened
        # Second source should be opened
        assert second_source.is_opened
    
    def test_init_video_source_not_initialized(self):
        """Test error when engine not initialized."""
        engine = GuruVisionEngine()
        # Don't initialize engine
        
        with pytest.raises(RuntimeError, match="not initialized"):
            engine.init_video_source(source=None)
    
    def test_init_video_source_invalid_path(self, engine, tmp_path):
        """Test error handling for invalid path."""
        # Requirement 19.5: Return clear error if source unavailable
        bad_path = tmp_path / "nonexistent.jpg"
        
        with pytest.raises(VideoSourceError):
            engine.init_video_source(source=str(bad_path))


class TestEngineReadFrame:
    """Test frame reading from engine."""
    
    def test_read_frame_from_image_directory(self, engine, test_images):
        """Test reading frames from image directory."""
        engine.init_video_source(source=str(test_images))
        
        # Read first frame
        success, frame = engine.read_frame()
        assert success
        assert frame is not None
        assert frame.shape == (480, 640, 3)
        
        # Read second frame
        success, frame = engine.read_frame()
        assert success
        assert frame is not None
    
    def test_read_frame_from_single_image(self, engine, tmp_path):
        """Test reading frame from single image."""
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), test_img)
        
        engine.init_video_source(source=str(img_file))
        
        # Read frame
        success, frame = engine.read_frame()
        assert success
        assert frame is not None
        
        # Second read should fail
        success, frame = engine.read_frame()
        assert not success
    
    def test_read_frame_not_initialized(self, engine):
        """Test error when video source not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            engine.read_frame()


class TestEngineSeekFrame:
    """Test frame seeking from engine."""
    
    def test_seek_frame_in_image_directory(self, engine, test_images):
        """Test seeking in image directory."""
        # Requirement 19.7: Support seeking in video files
        engine.init_video_source(source=str(test_images))
        
        # Seek to frame 3
        success = engine.seek_frame(3)
        assert success
        
        # Read frame should be frame 3
        success, frame = engine.read_frame()
        assert success
    
    def test_seek_frame_bounds(self, engine, test_images):
        """Test seeking with invalid frame numbers."""
        engine.init_video_source(source=str(test_images))
        
        # Seek to negative frame
        success = engine.seek_frame(-1)
        assert not success
        
        # Seek beyond end
        success = engine.seek_frame(100)
        assert not success
    
    def test_seek_frame_not_initialized(self, engine):
        """Test error when video source not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            engine.seek_frame(0)


class TestEngineGetVideoInfo:
    """Test getting video information from engine."""
    
    def test_get_video_info(self, engine, test_images):
        """Test getting video source information."""
        # Requirement 19.6: Auto-detect resolution and frame rate
        engine.init_video_source(source=str(test_images))
        
        info = engine.get_video_info()
        
        assert info['source_type'] == 'image_directory'
        assert info['resolution'] == (640, 480)
        assert info['fps'] == 10.0
        assert info['total_frames'] == 5
        assert info['current_frame'] == 0
    
    def test_get_video_info_not_initialized(self, engine):
        """Test error when video source not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            engine.get_video_info()


class TestEngineVideoSourceShutdown:
    """Test video source cleanup during shutdown."""
    
    def test_shutdown_releases_video_source(self, engine, test_images):
        """Test that shutdown releases video source."""
        # Requirement 20.3: Release all camera resources
        engine.init_video_source(source=str(test_images))
        
        # Mock logger to avoid errors
        engine.logger = type('Logger', (), {
            'info': lambda *args, **kwargs: None,
            'debug': lambda *args, **kwargs: None,
            'error': lambda *args, **kwargs: None,
            'warning': lambda *args, **kwargs: None
        })()
        
        # Mock database to avoid errors
        engine.database = type('Database', (), {
            'save': lambda: None
        })()
        
        # Shutdown
        engine.shutdown()
        
        # Video source should be released
        assert engine.video_source is None
    
    def test_shutdown_without_video_source(self, engine):
        """Test shutdown when no video source initialized."""
        # Mock logger and database
        engine.logger = type('Logger', (), {
            'info': lambda *args, **kwargs: None,
            'debug': lambda *args, **kwargs: None,
            'error': lambda *args, **kwargs: None,
            'warning': lambda *args, **kwargs: None
        })()
        engine.database = type('Database', (), {
            'save': lambda: None
        })()
        
        # Should not raise error
        engine.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
