"""
Example usage of the GuruVision Liveness Detection module.

This script demonstrates how to use the LivenessDetector to detect
spoofing attempts in face images.
"""

import numpy as np
import cv2
from guru_vision.liveness import LivenessDetector, LivenessResult


def example_basic_usage():
    """Basic usage example."""
    print("=" * 60)
    print("Example 1: Basic Liveness Detection")
    print("=" * 60)
    
    # Initialize detector (without GPU for this example)
    detector = LivenessDetector(use_gpu=False)
    
    # Create a synthetic aligned face (in real usage, this comes from FaceAligner)
    # For demonstration, we'll create random faces
    aligned_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    # Detect liveness
    result = detector.detect(aligned_face)
    
    print(f"Is Live: {result.is_live}")
    print(f"Confidence: {result.confidence:.3f}")
    print(f"Attack Type: {result.attack_type}")
    print()


def example_with_real_image():
    """Example with a real image file."""
    print("=" * 60)
    print("Example 2: Liveness Detection with Real Image")
    print("=" * 60)
    
    # Initialize detector
    detector = LivenessDetector(use_gpu=False)
    
    # In real usage, you would load an actual aligned face image
    # For this example, we'll create a synthetic one
    # aligned_face = cv2.imread("path/to/aligned_face.jpg")
    
    # Create a synthetic face with more realistic properties
    # Simulate a face with some texture
    face = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
    
    # Add some structure to simulate facial features
    # Draw some simple shapes to simulate eyes, nose, mouth
    cv2.circle(face, (35, 40), 8, (30, 30, 30), -1)  # Left eye
    cv2.circle(face, (77, 40), 8, (30, 30, 30), -1)  # Right eye
    cv2.ellipse(face, (56, 70), (8, 12), 0, 0, 180, (100, 80, 80), -1)  # Nose
    cv2.ellipse(face, (56, 90), (20, 10), 0, 0, 180, (150, 100, 100), 2)  # Mouth
    
    # Detect liveness
    result = detector.detect(face)
    
    print(f"Is Live: {result.is_live}")
    print(f"Confidence: {result.confidence:.3f}")
    print(f"Attack Type: {result.attack_type}")
    print()


def example_multiple_faces():
    """Example processing multiple faces."""
    print("=" * 60)
    print("Example 3: Processing Multiple Faces")
    print("=" * 60)
    
    # Initialize detector
    detector = LivenessDetector(use_gpu=False)
    
    # Simulate multiple aligned faces
    num_faces = 5
    
    for i in range(num_faces):
        # Create different types of synthetic faces
        if i % 2 == 0:
            # High texture face (more likely to be live)
            face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        else:
            # Low texture face (more likely to be spoof)
            face = np.ones((112, 112, 3), dtype=np.int16) * 128
            face += np.random.randint(-10, 10, (112, 112, 3), dtype=np.int16)
            face = np.clip(face, 0, 255).astype(np.uint8)
        
        # Detect liveness
        result = detector.detect(face)
        
        print(f"Face {i+1}:")
        print(f"  Is Live: {result.is_live}")
        print(f"  Confidence: {result.confidence:.3f}")
        print(f"  Attack Type: {result.attack_type}")
    
    print()


def example_integration_with_recognition():
    """Example showing integration with full recognition pipeline."""
    print("=" * 60)
    print("Example 4: Integration with Recognition Pipeline")
    print("=" * 60)
    
    # Initialize liveness detector
    liveness_detector = LivenessDetector(use_gpu=False)
    
    # Simulate a recognition pipeline
    print("Simulating face recognition pipeline...")
    print()
    
    # Simulate processing a frame with detected faces
    num_detected_faces = 3
    
    for i in range(num_detected_faces):
        print(f"Processing face {i+1}:")
        
        # Simulate aligned face from FaceAligner
        aligned_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        
        # Check liveness first
        liveness_result = liveness_detector.detect(aligned_face)
        
        print(f"  Liveness check: {'PASS' if liveness_result.is_live else 'FAIL'}")
        print(f"  Confidence: {liveness_result.confidence:.3f}")
        print(f"  Attack type: {liveness_result.attack_type}")
        
        if liveness_result.is_live:
            print(f"  → Proceeding with face recognition...")
            # In real code, you would:
            # embedding = recognizer.extract_embedding(aligned_face)
            # match = recognizer.match_identity(embedding, database)
        else:
            print(f"  → Rejecting: Spoof detected ({liveness_result.attack_type})")
        
        print()


def example_error_handling():
    """Example showing error handling."""
    print("=" * 60)
    print("Example 5: Error Handling")
    print("=" * 60)
    
    # Initialize detector
    detector = LivenessDetector(use_gpu=False)
    
    # Test 1: Invalid shape
    print("Test 1: Invalid input shape")
    try:
        invalid_face = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = detector.detect(invalid_face)
    except ValueError as e:
        print(f"  ✓ Caught expected error: {e}")
    print()
    
    # Test 2: All zeros
    print("Test 2: All-zero input")
    try:
        zero_face = np.zeros((112, 112, 3), dtype=np.uint8)
        result = detector.detect(zero_face)
    except ValueError as e:
        print(f"  ✓ Caught expected error: {e}")
    print()
    
    # Test 3: NaN values
    print("Test 3: NaN input")
    try:
        nan_face = np.full((112, 112, 3), np.nan, dtype=np.float32)
        result = detector.detect(nan_face)
    except ValueError as e:
        print(f"  ✓ Caught expected error: {e}")
    print()


def example_threshold_tuning():
    """Example showing threshold tuning for different security levels."""
    print("=" * 60)
    print("Example 6: Threshold Tuning")
    print("=" * 60)
    
    # Create a test face
    test_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
    
    # Test with different thresholds
    thresholds = [0.3, 0.5, 0.7, 0.9]
    
    for threshold in thresholds:
        detector = LivenessDetector(use_gpu=False)
        detector.liveness_threshold = threshold
        
        result = detector.detect(test_face)
        
        print(f"Threshold: {threshold:.1f}")
        print(f"  Is Live: {result.is_live}")
        print(f"  Confidence: {result.confidence:.3f}")
        print()
    
    print("Note: Higher thresholds = stricter security (more false rejections)")
    print("      Lower thresholds = more permissive (more false acceptances)")
    print()


def example_batch_processing():
    """Example showing batch processing of multiple faces."""
    print("=" * 60)
    print("Example 7: Batch Processing")
    print("=" * 60)
    
    # Initialize detector
    detector = LivenessDetector(use_gpu=False)
    
    # Simulate a batch of faces
    batch_size = 10
    faces = [np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8) 
             for _ in range(batch_size)]
    
    # Process batch
    results = []
    live_count = 0
    spoof_count = 0
    
    for i, face in enumerate(faces):
        result = detector.detect(face)
        results.append(result)
        
        if result.is_live:
            live_count += 1
        else:
            spoof_count += 1
    
    # Summary statistics
    print(f"Processed {batch_size} faces:")
    print(f"  Live faces: {live_count} ({live_count/batch_size*100:.1f}%)")
    print(f"  Spoof faces: {spoof_count} ({spoof_count/batch_size*100:.1f}%)")
    print()
    
    # Show attack type distribution
    attack_types = {}
    for result in results:
        attack_types[result.attack_type] = attack_types.get(result.attack_type, 0) + 1
    
    print("Attack type distribution:")
    for attack_type, count in attack_types.items():
        print(f"  {attack_type}: {count}")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("=" * 60)
    print("GuruVision Liveness Detection - Example Usage")
    print("=" * 60)
    print("\n")
    
    example_basic_usage()
    example_with_real_image()
    example_multiple_faces()
    example_integration_with_recognition()
    example_error_handling()
    example_threshold_tuning()
    example_batch_processing()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
