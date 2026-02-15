"""
Example usage of GuruVision video source functionality.

This script demonstrates how to use the video source features:
- Webcam input
- Video file input
- Image file input
- Image directory input
- Frame reading and seeking

Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7
"""

import cv2
import numpy as np
from pathlib import Path

from guru_vision.video_source import VideoSource, VideoSourceError


def example_webcam():
    """
    Example: Using webcam as video source.
    
    Requirements: 19.1
    """
    print("\n=== Example: Webcam Input ===")
    
    try:
        # Initialize video source with webcam (device index 0)
        with VideoSource(source=None, camera_index=0) as vs:
            print(f"Opened webcam successfully")
            
            # Get video info
            info = vs.get_info()
            print(f"Resolution: {info['resolution']}")
            print(f"FPS: {info['fps']:.1f}")
            
            # Read a few frames
            for i in range(5):
                success, frame = vs.read()
                if success:
                    print(f"Read frame {i+1}: shape={frame.shape}")
                else:
                    print(f"Failed to read frame {i+1}")
                    break
    
    except VideoSourceError as e:
        print(f"Webcam not available: {e}")
        print("This is expected if no webcam is connected")


def example_video_file():
    """
    Example: Using video file as source.
    
    Requirements: 19.2, 19.6, 19.7
    """
    print("\n=== Example: Video File Input ===")
    
    # Note: This example assumes you have a video file
    video_path = "path/to/your/video.mp4"
    
    if not Path(video_path).exists():
        print(f"Video file not found: {video_path}")
        print("Please provide a valid video file path")
        return
    
    try:
        with VideoSource(source=video_path) as vs:
            print(f"Opened video file: {video_path}")
            
            # Get video info
            info = vs.get_info()
            print(f"Resolution: {info['resolution']}")
            print(f"FPS: {info['fps']:.1f}")
            print(f"Total frames: {info['total_frames']}")
            
            # Read first frame
            success, frame = vs.read()
            if success:
                print(f"Read first frame: shape={frame.shape}")
            
            # Seek to middle of video
            middle_frame = info['total_frames'] // 2
            if vs.seek(middle_frame):
                print(f"Seeked to frame {middle_frame}")
                success, frame = vs.read()
                if success:
                    print(f"Read middle frame: shape={frame.shape}")
    
    except VideoSourceError as e:
        print(f"Error opening video file: {e}")


def example_image_file():
    """
    Example: Using single image file as source.
    
    Requirements: 19.3
    """
    print("\n=== Example: Single Image File ===")
    
    # Create a test image
    test_image_path = "test_image.jpg"
    test_img = np.zeros((480, 640, 3), dtype=np.uint8)
    test_img[100:200, 100:200] = [255, 0, 0]  # Blue square
    cv2.imwrite(test_image_path, test_img)
    print(f"Created test image: {test_image_path}")
    
    try:
        with VideoSource(source=test_image_path) as vs:
            print(f"Opened image file: {test_image_path}")
            
            # Get info
            info = vs.get_info()
            print(f"Resolution: {info['resolution']}")
            print(f"Total frames: {info['total_frames']}")
            
            # Read the image
            success, frame = vs.read()
            if success:
                print(f"Read image: shape={frame.shape}")
            
            # Try to read again (should fail - only one image)
            success, frame = vs.read()
            if not success:
                print("Second read failed as expected (only one image)")
    
    except VideoSourceError as e:
        print(f"Error opening image file: {e}")
    
    finally:
        # Clean up test image
        if Path(test_image_path).exists():
            Path(test_image_path).unlink()
            print(f"Cleaned up test image")


def example_image_directory():
    """
    Example: Using image directory as source.
    
    Requirements: 19.4, 19.7
    """
    print("\n=== Example: Image Directory ===")
    
    # Create a test directory with images
    test_dir = Path("test_images")
    test_dir.mkdir(exist_ok=True)
    
    # Create test images
    num_images = 10
    for i in range(num_images):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add frame number as text
        cv2.putText(img, f"Frame {i}", (50, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        cv2.imwrite(str(test_dir / f"img_{i:03d}.jpg"), img)
    
    print(f"Created {num_images} test images in {test_dir}")
    
    try:
        with VideoSource(source=str(test_dir)) as vs:
            print(f"Opened image directory: {test_dir}")
            
            # Get info
            info = vs.get_info()
            print(f"Resolution: {info['resolution']}")
            print(f"FPS: {info['fps']:.1f}")
            print(f"Total frames: {info['total_frames']}")
            
            # Read first 3 frames
            print("\nReading first 3 frames:")
            for i in range(3):
                success, frame = vs.read()
                if success:
                    print(f"  Frame {i}: shape={frame.shape}")
            
            # Seek to frame 7
            print("\nSeeking to frame 7:")
            if vs.seek(7):
                print(f"  Seeked successfully")
                success, frame = vs.read()
                if success:
                    print(f"  Read frame 7: shape={frame.shape}")
            
            # Get current position
            pos = vs.get_position()
            print(f"\nCurrent position: frame {pos}")
    
    except VideoSourceError as e:
        print(f"Error opening image directory: {e}")
    
    finally:
        # Clean up test directory
        if test_dir.exists():
            for img_file in test_dir.glob("*.jpg"):
                img_file.unlink()
            test_dir.rmdir()
            print(f"\nCleaned up test directory")


def example_error_handling():
    """
    Example: Error handling for invalid sources.
    
    Requirements: 19.5
    """
    print("\n=== Example: Error Handling ===")
    
    # Try to open non-existent file
    print("\n1. Non-existent file:")
    try:
        vs = VideoSource(source="nonexistent.jpg")
        vs.open()
    except VideoSourceError as e:
        print(f"   Error (expected): {e}")
    
    # Try to open empty directory
    print("\n2. Empty directory:")
    empty_dir = Path("empty_dir")
    empty_dir.mkdir(exist_ok=True)
    try:
        vs = VideoSource(source=str(empty_dir))
        vs.open()
    except VideoSourceError as e:
        print(f"   Error (expected): {e}")
    finally:
        empty_dir.rmdir()
    
    # Try to open unsupported file format
    print("\n3. Unsupported file format:")
    bad_file = Path("test.txt")
    bad_file.write_text("not an image")
    try:
        vs = VideoSource(source=str(bad_file))
    except VideoSourceError as e:
        print(f"   Error (expected): {e}")
    finally:
        bad_file.unlink()


def example_engine_integration():
    """
    Example: Using video source with GuruVisionEngine.
    
    Requirements: 19.1, 19.2, 19.3, 19.4
    """
    print("\n=== Example: Engine Integration ===")
    
    # Note: This example requires a fully initialized engine
    # For demonstration, we'll show the API usage
    
    print("""
    # Initialize engine
    from guru_vision.engine import GuruVisionEngine
    
    engine = GuruVisionEngine()
    engine.initialize()
    
    # Initialize video source with image directory
    engine.init_video_source(source="path/to/images")
    
    # Get video info
    info = engine.get_video_info()
    print(f"Source type: {info['source_type']}")
    print(f"Resolution: {info['resolution']}")
    print(f"FPS: {info['fps']}")
    
    # Read and process frames
    while True:
        success, frame = engine.read_frame()
        if not success:
            break
        
        # Process frame through recognition pipeline
        result = engine.process_frame(frame)
        
        # Handle recognition results
        for face in result.faces:
            print(f"Detected: {face.identity} (confidence={face.confidence:.2f})")
    
    # Seek to specific frame (for video files and image sequences)
    engine.seek_frame(100)
    
    # Shutdown
    engine.shutdown()
    """)


def main():
    """Run all examples."""
    print("=" * 60)
    print("GuruVision Video Source Examples")
    print("=" * 60)
    
    # Run examples
    example_webcam()
    example_image_file()
    example_image_directory()
    example_error_handling()
    example_engine_integration()
    
    # Note: example_video_file() requires an actual video file
    # Uncomment and provide a valid path to test
    # example_video_file()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
