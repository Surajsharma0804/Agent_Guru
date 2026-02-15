"""
Tests for video source management module.

This module tests the VideoSource class for handling various video input types:
- Webcam input
- Video file input
- Image file input
- Image directory input
- Error handling

Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7
"""

import pytest
import numpy as np
import cv2
import tempfile
import shutil
from pathlib import Path

from guru_vision.video_source import VideoSource, VideoSourceType, VideoSourceError


class TestVideoSourceTypeDetection:
    """Test video source type detection."""
    
    def test_webcam_by_none(self):
        """Test webcam detection when source is None."""
        vs = VideoSource(source=None, camera_index=0)
        assert vs.source_type == VideoSourceType.WEBCAM
        assert vs.source == 0
    
    def test_webcam_by_int(self):
        """Test webcam detection when source is integer."""
        vs = VideoSource(source=1)
        assert vs.source_type == VideoSourceType.WEBCAM
        assert vs.source == 1
    
    def test_webcam_by_string_number(self):
        """Test webcam detection when source is numeric string."""
        vs = VideoSource(source="0")
        assert vs.source_type == VideoSourceType.WEBCAM
        assert vs.source == 0
    
    def test_video_file_detection(self, tmp_path):
        """Test video file detection."""
        # Create a dummy video file
        video_file = tmp_path / "test.mp4"
        video_file.touch()
        
        vs = VideoSource(source=str(video_file))
        assert vs.source_type == VideoSourceType.VIDEO_FILE
    
    def test_image_file_detection(self, tmp_path):
        """Test image file detection."""
        # Create a dummy image file
        img_file = tmp_path / "test.jpg"
        img_file.touch()
        
        vs = VideoSource(source=str(img_file))
        assert vs.source_type == VideoSourceType.IMAGE_FILE
    
    def test_image_directory_detection(self, tmp_path):
        """Test image directory detection."""
        vs = VideoSource(source=str(tmp_path))
        assert vs.source_type == VideoSourceType.IMAGE_DIRECTORY
    
    def test_unsupported_file_format(self, tmp_path):
        """Test error for unsupported file format."""
        # Create a file with unsupported extension
        bad_file = tmp_path / "test.txt"
        bad_file.touch()
        
        with pytest.raises(VideoSourceError, match="Unsupported file format"):
            VideoSource(source=str(bad_file))
    
    def test_invalid_source_type(self):
        """Test error for invalid source type."""
        with pytest.raises(VideoSourceError, match="Invalid source type"):
            VideoSource(source=[1, 2, 3])


class TestVideoSourceImageFile:
    """Test video source with single image file."""
    
    def test_open_image_file(self, tmp_path):
        """Test opening a single image file."""
        # Create a test image
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(img_file))
        success = vs.open()
        
        assert success
        assert vs.is_opened
        assert vs.resolution == (640, 480)
        assert vs.total_frames == 1
        assert vs.fps == 1.0
    
    def test_read_image_file(self, tmp_path):
        """Test reading from image file."""
        # Create a test image
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        test_img[100:200, 100:200] = [255, 0, 0]  # Blue square
        cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(img_file))
        vs.open()
        
        # Read frame
        success, frame = vs.read()
        assert success
        assert frame is not None
        assert frame.shape == (480, 640, 3)
        
        # Second read should fail (only one image)
        success, frame = vs.read()
        assert not success
        assert frame is None
    
    def test_image_file_not_found(self, tmp_path):
        """Test error when image file not found."""
        img_file = tmp_path / "nonexistent.jpg"
        
        # Error should be raised during initialization, not open()
        with pytest.raises(VideoSourceError, match="Path does not exist"):
            VideoSource(source=str(img_file))
    
    def test_corrupted_image_file(self, tmp_path):
        """Test error when image file is corrupted."""
        # Create a corrupted image file
        img_file = tmp_path / "corrupted.jpg"
        img_file.write_text("not an image")
        
        vs = VideoSource(source=str(img_file))
        with pytest.raises(VideoSourceError, match="Failed to load image file"):
            vs.open()


class TestVideoSourceImageDirectory:
    """Test video source with image directory."""
    
    def test_open_image_directory(self, tmp_path):
        """Test opening an image directory."""
        # Create test images
        for i in range(5):
            img_file = tmp_path / f"img_{i:03d}.jpg"
            test_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        success = vs.open()
        
        assert success
        assert vs.is_opened
        assert vs.resolution == (640, 480)
        assert vs.total_frames == 5
        assert vs.fps == 10.0
        assert len(vs.image_files) == 5
    
    def test_read_image_directory(self, tmp_path):
        """Test reading from image directory."""
        # Create test images with different colors
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        for i, color in enumerate(colors):
            img_file = tmp_path / f"img_{i}.jpg"
            test_img = np.full((100, 100, 3), color, dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        vs.open()
        
        # Read all frames
        frames = []
        for _ in range(3):
            success, frame = vs.read()
            assert success
            assert frame is not None
            frames.append(frame)
        
        # Fourth read should fail
        success, frame = vs.read()
        assert not success
        assert frame is None
    
    def test_image_directory_sorted(self, tmp_path):
        """Test that images are read in sorted order."""
        # Create images with names that would sort differently
        names = ["img_10.jpg", "img_2.jpg", "img_1.jpg"]
        for name in names:
            img_file = tmp_path / name
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        vs.open()
        
        # Check that files are sorted
        expected_order = ["img_1.jpg", "img_10.jpg", "img_2.jpg"]
        actual_order = [Path(f).name for f in vs.image_files]
        assert actual_order == expected_order
    
    def test_empty_directory(self, tmp_path):
        """Test error when directory contains no images."""
        vs = VideoSource(source=str(tmp_path))
        with pytest.raises(VideoSourceError, match="No image files found"):
            vs.open()
    
    def test_directory_not_found(self, tmp_path):
        """Test error when directory not found."""
        bad_dir = tmp_path / "nonexistent"
        
        # Error should be raised during initialization, not open()
        with pytest.raises(VideoSourceError, match="Path does not exist"):
            VideoSource(source=str(bad_dir))
    
    def test_mixed_image_formats(self, tmp_path):
        """Test directory with mixed image formats."""
        # Create images with different formats
        formats = [".jpg", ".png", ".bmp"]
        for i, fmt in enumerate(formats):
            img_file = tmp_path / f"img_{i}{fmt}"
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        vs.open()
        
        assert vs.total_frames == 3
        assert len(vs.image_files) == 3


class TestVideoSourceSeeking:
    """Test seeking functionality."""
    
    def test_seek_in_image_directory(self, tmp_path):
        """Test seeking in image directory."""
        # Create test images
        for i in range(10):
            img_file = tmp_path / f"img_{i:03d}.jpg"
            test_img = np.full((100, 100, 3), i * 25, dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        vs.open()
        
        # Seek to frame 5
        success = vs.seek(5)
        assert success
        assert vs.get_position() == 5
        
        # Read frame 5
        success, frame = vs.read()
        assert success
        assert vs.get_position() == 6
    
    def test_seek_bounds_checking(self, tmp_path):
        """Test seeking with invalid frame numbers."""
        # Create test images
        for i in range(5):
            img_file = tmp_path / f"img_{i}.jpg"
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        vs.open()
        
        # Seek to negative frame
        success = vs.seek(-1)
        assert not success
        
        # Seek beyond end
        success = vs.seek(10)
        assert not success
        
        # Seek to valid frame
        success = vs.seek(2)
        assert success
    
    def test_seek_in_image_file(self, tmp_path):
        """Test seeking in single image file."""
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(img_file))
        vs.open()
        
        # Can seek to frame 0
        success = vs.seek(0)
        assert success
        
        # Cannot seek to frame 1
        success = vs.seek(1)
        assert not success


class TestVideoSourceInfo:
    """Test video source information retrieval."""
    
    def test_get_info_image_directory(self, tmp_path):
        """Test getting info for image directory."""
        # Create test images
        for i in range(3):
            img_file = tmp_path / f"img_{i}.jpg"
            test_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        vs.open()
        
        info = vs.get_info()
        assert info['source_type'] == 'image_directory'
        assert info['resolution'] == (640, 480)
        assert info['fps'] == 10.0
        assert info['total_frames'] == 3
        assert info['current_frame'] == 0
    
    def test_get_position(self, tmp_path):
        """Test getting current position."""
        # Create test images
        for i in range(5):
            img_file = tmp_path / f"img_{i}.jpg"
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(tmp_path))
        vs.open()
        
        # Initial position
        assert vs.get_position() == 0
        
        # Read a frame
        vs.read()
        assert vs.get_position() == 1
        
        # Read another frame
        vs.read()
        assert vs.get_position() == 2


class TestVideoSourceContextManager:
    """Test context manager functionality."""
    
    def test_context_manager(self, tmp_path):
        """Test using VideoSource as context manager."""
        # Create test image
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), test_img)
        
        # Use as context manager
        with VideoSource(source=str(img_file)) as vs:
            assert vs.is_opened
            success, frame = vs.read()
            assert success
        
        # Should be closed after context
        assert not vs.is_opened


class TestVideoSourceRelease:
    """Test resource release."""
    
    def test_release(self, tmp_path):
        """Test releasing video source."""
        # Create test image
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(img_file))
        vs.open()
        assert vs.is_opened
        
        vs.release()
        assert not vs.is_opened
        assert vs.capture is None
        assert len(vs.image_files) == 0
    
    def test_multiple_release(self, tmp_path):
        """Test that multiple release calls don't cause errors."""
        img_file = tmp_path / "test.jpg"
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(img_file), test_img)
        
        vs = VideoSource(source=str(img_file))
        vs.open()
        
        # Release multiple times
        vs.release()
        vs.release()
        vs.release()
        
        assert not vs.is_opened


class TestVideoSourceErrorHandling:
    """Test error handling and clear error messages."""
    
    def test_clear_error_file_not_found(self, tmp_path):
        """Test clear error message when file not found."""
        # Requirement 19.5: Return clear error if source unavailable
        img_file = tmp_path / "nonexistent.jpg"
        
        # Error should be raised during initialization
        with pytest.raises(VideoSourceError) as exc_info:
            VideoSource(source=str(img_file))
        
        assert "does not exist" in str(exc_info.value).lower()
    
    def test_clear_error_empty_directory(self, tmp_path):
        """Test clear error message for empty directory."""
        # Requirement 19.5: Return clear error if source unavailable
        vs = VideoSource(source=str(tmp_path))
        with pytest.raises(VideoSourceError) as exc_info:
            vs.open()
        
        error_msg = str(exc_info.value).lower()
        assert "no image files found" in error_msg
    
    def test_clear_error_unsupported_format(self, tmp_path):
        """Test clear error message for unsupported format."""
        # Requirement 19.5: Return clear error if source unavailable
        bad_file = tmp_path / "test.xyz"
        bad_file.touch()
        
        with pytest.raises(VideoSourceError) as exc_info:
            VideoSource(source=str(bad_file))
        
        error_msg = str(exc_info.value).lower()
        assert "unsupported" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
