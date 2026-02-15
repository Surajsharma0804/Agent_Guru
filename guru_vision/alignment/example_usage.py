"""
Example usage of the FaceAligner module.

This script demonstrates how to use the face alignment functionality
with the detection module to align detected faces.
"""

import numpy as np
import cv2
from guru_vision.detection import FaceDetector, Detection
from guru_vision.alignment import FaceAligner


def example_align_from_image():
    """Example: Detect and align faces from an image"""
    
    # Initialize detector and aligner
    detector = FaceDetector(use_gpu=False)
    aligner = FaceAligner(output_size=(112, 112))
    
    # Load an image (replace with your image path)
    # For this example, we'll create a dummy image
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Detect faces
    detections = detector.detect(frame, confidence_threshold=0.5)
    
    print(f"Detected {len(detections)} face(s)")
    
    # Align each detected face
    aligned_faces = []
    for i, detection in enumerate(detections):
        try:
            aligned_face = aligner.align(frame, detection)
            aligned_faces.append(aligned_face)
            print(f"Face {i+1}: Aligned to {aligned_face.shape}")
        except ValueError as e:
            print(f"Face {i+1}: Alignment failed - {e}")
    
    return aligned_faces


def example_align_with_custom_size():
    """Example: Align faces to a custom output size"""
    
    # Create aligner with custom output size
    aligner = FaceAligner(output_size=(224, 224))
    
    # Create a dummy frame and detection
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    landmarks = np.array([
        [250, 200],  # left eye
        [390, 200],  # right eye
        [320, 280],  # nose
        [270, 350],  # left mouth
        [370, 350]   # right mouth
    ], dtype=np.float32)
    
    detection = Detection(
        bbox=(200, 150, 240, 300),
        landmarks=landmarks,
        confidence=0.95
    )
    
    # Align the face
    aligned_face = aligner.align(frame, detection)
    
    print(f"Aligned face shape: {aligned_face.shape}")
    print(f"Expected: (224, 224, 3)")
    
    return aligned_face


def example_batch_alignment():
    """Example: Align multiple faces in batch"""
    
    detector = FaceDetector(use_gpu=False)
    aligner = FaceAligner()
    
    # Simulate processing multiple frames
    frames = [
        np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        for _ in range(3)
    ]
    
    all_aligned_faces = []
    
    for frame_idx, frame in enumerate(frames):
        detections = detector.detect(frame)
        
        for det_idx, detection in enumerate(detections):
            try:
                aligned_face = aligner.align(frame, detection)
                all_aligned_faces.append(aligned_face)
                print(f"Frame {frame_idx}, Face {det_idx}: Aligned successfully")
            except ValueError as e:
                print(f"Frame {frame_idx}, Face {det_idx}: Failed - {e}")
    
    print(f"\nTotal aligned faces: {len(all_aligned_faces)}")
    return all_aligned_faces


if __name__ == "__main__":
    print("=" * 60)
    print("Example 1: Align faces from image")
    print("=" * 60)
    example_align_from_image()
    
    print("\n" + "=" * 60)
    print("Example 2: Align with custom size")
    print("=" * 60)
    example_align_with_custom_size()
    
    print("\n" + "=" * 60)
    print("Example 3: Batch alignment")
    print("=" * 60)
    example_batch_alignment()
