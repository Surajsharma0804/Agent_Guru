"""
Video source management module for GuruVision facial recognition system.

This module provides the VideoSource class for handling various video input types:
- Webcam input by device index or name
- Video file input (MP4, AVI, MOV)
- Image file input
- Image directory input

Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7
"""

import cv2
import os
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np
from enum import Enum

from guru_vision.exceptions import GuruVisionError


class VideoSourceType(Enum):
    """Enumeration of supported video source types."""
    WEBCAM = "webcam"
    VIDEO_FILE = "video_file"
    IMAGE_FILE = "image_file"
    IMAGE_DIRECTORY = "image_directory"


class VideoSourceError(GuruVisionError):
    """Exception raised for video source errors."""
    pass


class VideoSource:
    """
    Video source manager for camera, video files, and image inputs.
    
    This class provides a unified interface for different video input types:
    - Webcam by device index or name
    - Video files (MP4, AVI, MOV)
    - Single image files
    - Image directories (processed as sequences)
    
    Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7
    """
    
    # Supported video file extensions
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
    
    # Supported image file extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    
    def __init__(self, source: Optional[str] = None, camera_index: int = 0):
        """
        Initialize video source.
        
        Args:
            source: Video source specification:
                   - None: Use webcam with camera_index
                   - Integer string (e.g., "0"): Webcam device index
                   - File path: Video file or image file
                   - Directory path: Image directory
            camera_index: Default camera device index if source is None
        
        Requirements: 19.1, 19.2, 19.3, 19.4
        """
        self.source = source
        self.camera_index = camera_index
        self.source_type = None
        self.capture = None
        self.image_files = []
        self.current_image_index = 0
        self.resolution = None
        self.fps = None
        self.total_frames = None
        self.is_opened = False
        
        # Determine source type
        self._determine_source_type()
    
    def _determine_source_type(self) -> None:
        """
        Determine the type of video source.
        
        This method analyzes the source parameter to determine whether it's
        a webcam, video file, image file, or image directory.
        """
        if self.source is None:
            # Default to webcam
            self.source_type = VideoSourceType.WEBCAM
            self.source = self.camera_index
        elif isinstance(self.source, int):
            # Webcam by device index
            self.source_type = VideoSourceType.WEBCAM
        elif isinstance(self.source, str):
            # Check if it's a numeric string (webcam index)
            if self.source.isdigit():
                self.source_type = VideoSourceType.WEBCAM
                self.source = int(self.source)
            else:
                # Check if it's a file or directory
                path = Path(self.source)
                
                if path.is_file():
                    # Check file extension
                    ext = path.suffix.lower()
                    if ext in self.VIDEO_EXTENSIONS:
                        self.source_type = VideoSourceType.VIDEO_FILE
                    elif ext in self.IMAGE_EXTENSIONS:
                        self.source_type = VideoSourceType.IMAGE_FILE
                    else:
                        raise VideoSourceError(
                            f"Unsupported file format: {ext}. "
                            f"Supported video formats: {self.VIDEO_EXTENSIONS}. "
                            f"Supported image formats: {self.IMAGE_EXTENSIONS}"
                        )
                elif path.is_dir():
                    self.source_type = VideoSourceType.IMAGE_DIRECTORY
                elif path.exists():
                    # Path exists but is neither file nor directory
                    raise VideoSourceError(
                        f"Path exists but is neither a file nor directory: {self.source}"
                    )
                else:
                    # Path doesn't exist - raise error instead of assuming webcam
                    raise VideoSourceError(
                        f"Path does not exist: {self.source}"
                    )
        else:
            raise VideoSourceError(
                f"Invalid source type: {type(self.source)}. "
                "Expected None, int, or str"
            )
    
    def open(self) -> bool:
        """
        Open the video source and initialize capture.
        
        Returns:
            True if source opened successfully, False otherwise
        
        Raises:
            VideoSourceError: If source is unavailable or cannot be opened
        
        Requirements: 19.5, 19.6
        """
        try:
            if self.source_type == VideoSourceType.WEBCAM:
                return self._open_webcam()
            elif self.source_type == VideoSourceType.VIDEO_FILE:
                return self._open_video_file()
            elif self.source_type == VideoSourceType.IMAGE_FILE:
                return self._open_image_file()
            elif self.source_type == VideoSourceType.IMAGE_DIRECTORY:
                return self._open_image_directory()
            else:
                raise VideoSourceError(f"Unknown source type: {self.source_type}")
        except VideoSourceError:
            raise
        except Exception as e:
            raise VideoSourceError(f"Failed to open video source: {e}") from e
    
    def _open_webcam(self) -> bool:
        """
        Open webcam source.
        
        Returns:
            True if webcam opened successfully
        
        Raises:
            VideoSourceError: If webcam is unavailable
        
        Requirements: 19.1, 19.5
        """
        # Requirement 19.1: Support webcam input using device index or device name
        self.capture = cv2.VideoCapture(self.source)
        
        if not self.capture.isOpened():
            # Requirement 19.5: Return clear error if source unavailable
            raise VideoSourceError(
                f"Webcam not available: device index {self.source}. "
                "Please check that the camera is connected and not in use by another application."
            )
        
        # Requirement 19.6: Auto-detect resolution and frame rate
        self.resolution = (
            int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        
        # Some webcams report 0 FPS, use default of 30
        if self.fps == 0:
            self.fps = 30.0
        
        self.total_frames = None  # Webcam has no fixed frame count
        self.is_opened = True
        
        return True
    
    def _open_video_file(self) -> bool:
        """
        Open video file source.
        
        Returns:
            True if video file opened successfully
        
        Raises:
            VideoSourceError: If video file is unavailable or invalid
        
        Requirements: 19.2, 19.5, 19.6
        """
        # Requirement 19.2: Support video file input in common formats
        if not Path(self.source).exists():
            # Requirement 19.5: Return clear error if source unavailable
            raise VideoSourceError(
                f"Video file not found: {self.source}"
            )
        
        self.capture = cv2.VideoCapture(self.source)
        
        if not self.capture.isOpened():
            raise VideoSourceError(
                f"Failed to open video file: {self.source}. "
                "The file may be corrupted or in an unsupported format."
            )
        
        # Requirement 19.6: Auto-detect resolution and frame rate
        self.resolution = (
            int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.is_opened = True
        
        return True
    
    def _open_image_file(self) -> bool:
        """
        Open single image file source.
        
        Returns:
            True if image file opened successfully
        
        Raises:
            VideoSourceError: If image file is unavailable or invalid
        
        Requirements: 19.3, 19.5
        """
        # Requirement 19.3: Support processing individual image files
        if not Path(self.source).exists():
            # Requirement 19.5: Return clear error if source unavailable
            raise VideoSourceError(
                f"Image file not found: {self.source}"
            )
        
        # Store as single-item list
        self.image_files = [self.source]
        self.current_image_index = 0
        self.total_frames = 1
        self.fps = 1.0  # Single image, arbitrary FPS
        
        # Load image to get resolution
        img = cv2.imread(self.source)
        if img is None:
            raise VideoSourceError(
                f"Failed to load image file: {self.source}. "
                "The file may be corrupted or in an unsupported format."
            )
        
        self.resolution = (img.shape[1], img.shape[0])
        self.is_opened = True
        
        return True
    
    def _open_image_directory(self) -> bool:
        """
        Open image directory source.
        
        Returns:
            True if image directory opened successfully
        
        Raises:
            VideoSourceError: If directory is unavailable or contains no images
        
        Requirements: 19.4, 19.5
        """
        # Requirement 19.4: Support processing directories of images as image sequences
        dir_path = Path(self.source)
        
        if not dir_path.exists():
            # Requirement 19.5: Return clear error if source unavailable
            raise VideoSourceError(
                f"Image directory not found: {self.source}"
            )
        
        if not dir_path.is_dir():
            raise VideoSourceError(
                f"Path is not a directory: {self.source}"
            )
        
        # Find all image files in directory
        # Use a set to avoid duplicates (glob is case-insensitive on Windows)
        image_files_set = set()
        for ext in self.IMAGE_EXTENSIONS:
            image_files_set.update(dir_path.glob(f"*{ext}"))
            image_files_set.update(dir_path.glob(f"*{ext.upper()}"))
        
        # Sort files by name for consistent ordering
        self.image_files = sorted([str(f) for f in image_files_set])
        
        if len(self.image_files) == 0:
            raise VideoSourceError(
                f"No image files found in directory: {self.source}. "
                f"Supported formats: {self.IMAGE_EXTENSIONS}"
            )
        
        self.current_image_index = 0
        self.total_frames = len(self.image_files)
        self.fps = 10.0  # Default FPS for image sequences
        
        # Load first image to get resolution
        img = cv2.imread(self.image_files[0])
        if img is None:
            raise VideoSourceError(
                f"Failed to load first image: {self.image_files[0]}"
            )
        
        self.resolution = (img.shape[1], img.shape[0])
        self.is_opened = True
        
        return True
    
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read the next frame from the video source.
        
        Returns:
            Tuple of (success, frame):
                - success: True if frame was read successfully
                - frame: Frame as numpy array in BGR format, or None if failed
        
        Requirements: 19.1, 19.2, 19.3, 19.4
        """
        if not self.is_opened:
            return False, None
        
        if self.source_type in [VideoSourceType.WEBCAM, VideoSourceType.VIDEO_FILE]:
            # Read from video capture
            ret, frame = self.capture.read()
            return ret, frame
        
        elif self.source_type in [VideoSourceType.IMAGE_FILE, VideoSourceType.IMAGE_DIRECTORY]:
            # Read from image file list
            if self.current_image_index >= len(self.image_files):
                # No more images
                return False, None
            
            # Load current image
            img_path = self.image_files[self.current_image_index]
            frame = cv2.imread(img_path)
            
            if frame is None:
                # Failed to load image, skip to next
                self.current_image_index += 1
                return self.read()
            
            # Increment index for next read
            self.current_image_index += 1
            return True, frame
        
        else:
            return False, None
    
    def seek(self, frame_number: int) -> bool:
        """
        Seek to a specific frame number in the video.
        
        This method is only supported for video files and image sequences.
        Webcam sources cannot seek.
        
        Args:
            frame_number: Frame number to seek to (0-indexed)
        
        Returns:
            True if seek was successful, False otherwise
        
        Requirements: 19.7
        """
        # Requirement 19.7: Support seeking in video files
        
        if self.source_type == VideoSourceType.WEBCAM:
            # Cannot seek in webcam
            return False
        
        elif self.source_type == VideoSourceType.VIDEO_FILE:
            if self.capture is None:
                return False
            
            # Validate frame number
            if frame_number < 0 or (self.total_frames and frame_number >= self.total_frames):
                return False
            
            # Seek to frame
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            return True
        
        elif self.source_type in [VideoSourceType.IMAGE_FILE, VideoSourceType.IMAGE_DIRECTORY]:
            # Validate frame number
            if frame_number < 0 or frame_number >= len(self.image_files):
                return False
            
            # Set current index
            self.current_image_index = frame_number
            return True
        
        return False
    
    def get_position(self) -> int:
        """
        Get the current frame position.
        
        Returns:
            Current frame number (0-indexed), or -1 if unavailable
        """
        if not self.is_opened:
            return -1
        
        if self.source_type == VideoSourceType.WEBCAM:
            # Webcam doesn't have a position
            return -1
        
        elif self.source_type == VideoSourceType.VIDEO_FILE:
            if self.capture is None:
                return -1
            return int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))
        
        elif self.source_type in [VideoSourceType.IMAGE_FILE, VideoSourceType.IMAGE_DIRECTORY]:
            return self.current_image_index
        
        return -1
    
    def get_info(self) -> dict:
        """
        Get information about the video source.
        
        Returns:
            Dictionary with source information:
                - source_type: Type of video source
                - resolution: (width, height) tuple
                - fps: Frames per second
                - total_frames: Total number of frames (None for webcam)
                - current_frame: Current frame position (-1 for webcam)
        
        Requirements: 19.6
        """
        return {
            'source_type': self.source_type.value if self.source_type else None,
            'resolution': self.resolution,
            'fps': self.fps,
            'total_frames': self.total_frames,
            'current_frame': self.get_position()
        }
    
    def release(self) -> None:
        """
        Release the video source and free resources.
        """
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        
        self.is_opened = False
        self.image_files = []
        self.current_image_index = 0
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False
    
    def __del__(self):
        """Destructor to ensure resources are released."""
        self.release()
