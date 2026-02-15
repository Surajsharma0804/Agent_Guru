"""
Example usage of the EmotionRecognizer module.

This script demonstrates how to use the emotion recognition functionality
to classify facial expressions from images.
"""

import numpy as np
import cv2
from guru_vision.emotion import EmotionRecognizer, EmotionResult


def example_basic_usage():
    """Basic emotion recognition example."""
    print("=" * 60)
    print("Example 1: Basic Emotion Recognition")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Create a test face (in practice, this would come from FaceAligner)
    test_face = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
    
    # Recognize emotion
    result = recognizer.recognize(test_face)
    
    # Display results
    print(f"\nDominant emotion: {result.dominant_emotion}")
    print(f"Confidence: {result.confidence:.3f}")
    print("\nAll emotion scores:")
    for emotion, score in sorted(result.all_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"  {emotion:12s}: {score:.3f}")


def example_multiple_faces():
    """Process multiple faces and compare emotions."""
    print("\n" + "=" * 60)
    print("Example 2: Multiple Face Emotion Recognition")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Simulate multiple faces
    num_faces = 3
    faces = []
    for i in range(num_faces):
        # Create faces with different characteristics
        seed = i * 100
        rng = np.random.RandomState(seed)
        face = rng.randint(30, 220, (112, 112, 3), dtype=np.uint8)
        faces.append(face)
    
    # Process each face
    print(f"\nProcessing {num_faces} faces:")
    for i, face in enumerate(faces):
        result = recognizer.recognize(face)
        print(f"\nFace {i+1}:")
        print(f"  Dominant emotion: {result.dominant_emotion}")
        print(f"  Confidence: {result.confidence:.3f}")


def example_emotion_filtering():
    """Filter faces by specific emotions."""
    print("\n" + "=" * 60)
    print("Example 3: Emotion Filtering")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Simulate multiple faces
    num_faces = 5
    faces = []
    for i in range(num_faces):
        rng = np.random.RandomState(i * 50)
        face = rng.randint(20, 230, (112, 112, 3), dtype=np.uint8)
        faces.append(face)
    
    # Process and filter
    happy_faces = []
    neutral_faces = []
    other_faces = []
    
    for i, face in enumerate(faces):
        result = recognizer.recognize(face)
        
        if result.dominant_emotion == "happy":
            happy_faces.append((i, result))
        elif result.dominant_emotion == "neutral":
            neutral_faces.append((i, result))
        else:
            other_faces.append((i, result))
    
    print(f"\nProcessed {num_faces} faces:")
    print(f"  Happy faces: {len(happy_faces)}")
    print(f"  Neutral faces: {len(neutral_faces)}")
    print(f"  Other emotions: {len(other_faces)}")
    
    if happy_faces:
        print("\nHappy faces:")
        for idx, result in happy_faces:
            print(f"  Face {idx}: confidence {result.confidence:.3f}")


def example_emotion_statistics():
    """Calculate emotion statistics across multiple faces."""
    print("\n" + "=" * 60)
    print("Example 4: Emotion Statistics")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Simulate a batch of faces
    num_faces = 10
    faces = []
    for i in range(num_faces):
        rng = np.random.RandomState(i * 25)
        face = rng.randint(40, 210, (112, 112, 3), dtype=np.uint8)
        faces.append(face)
    
    # Collect emotion counts
    emotion_counts = {emotion: 0 for emotion in EmotionRecognizer.EMOTION_CATEGORIES}
    
    for face in faces:
        result = recognizer.recognize(face)
        emotion_counts[result.dominant_emotion] += 1
    
    # Display statistics
    print(f"\nEmotion distribution across {num_faces} faces:")
    for emotion, count in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / num_faces) * 100
        bar = "█" * int(percentage / 5)
        print(f"  {emotion:12s}: {count:2d} ({percentage:5.1f}%) {bar}")


def example_confidence_thresholding():
    """Filter results by confidence threshold."""
    print("\n" + "=" * 60)
    print("Example 5: Confidence Thresholding")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Confidence threshold
    confidence_threshold = 0.4
    
    # Simulate faces
    num_faces = 8
    faces = []
    for i in range(num_faces):
        rng = np.random.RandomState(i * 30)
        face = rng.randint(35, 215, (112, 112, 3), dtype=np.uint8)
        faces.append(face)
    
    # Process with confidence filtering
    high_confidence = []
    low_confidence = []
    
    for i, face in enumerate(faces):
        result = recognizer.recognize(face)
        
        if result.confidence >= confidence_threshold:
            high_confidence.append((i, result))
        else:
            low_confidence.append((i, result))
    
    print(f"\nConfidence threshold: {confidence_threshold}")
    print(f"High confidence results: {len(high_confidence)}")
    print(f"Low confidence results: {len(low_confidence)}")
    
    if high_confidence:
        print("\nHigh confidence emotions:")
        for idx, result in high_confidence:
            print(f"  Face {idx}: {result.dominant_emotion} ({result.confidence:.3f})")
    
    if low_confidence:
        print("\nLow confidence emotions (uncertain):")
        for idx, result in low_confidence:
            print(f"  Face {idx}: {result.dominant_emotion} ({result.confidence:.3f})")


def example_top_emotions():
    """Get top N emotions for each face."""
    print("\n" + "=" * 60)
    print("Example 6: Top N Emotions")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Create test face
    test_face = np.random.randint(60, 190, (112, 112, 3), dtype=np.uint8)
    
    # Recognize emotion
    result = recognizer.recognize(test_face)
    
    # Get top 3 emotions
    top_n = 3
    sorted_emotions = sorted(
        result.all_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    print(f"\nTop {top_n} emotions:")
    for i, (emotion, score) in enumerate(sorted_emotions[:top_n], 1):
        print(f"  {i}. {emotion:12s}: {score:.3f}")


def example_error_handling():
    """Demonstrate error handling."""
    print("\n" + "=" * 60)
    print("Example 7: Error Handling")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Test 1: Invalid shape
    print("\nTest 1: Invalid shape")
    try:
        invalid_face = np.zeros((64, 64, 3), dtype=np.uint8)
        result = recognizer.recognize(invalid_face)
    except ValueError as e:
        print(f"  Caught error: {e}")
    
    # Test 2: All-zero input
    print("\nTest 2: All-zero input")
    try:
        zero_face = np.zeros((112, 112, 3), dtype=np.uint8)
        result = recognizer.recognize(zero_face)
    except ValueError as e:
        print(f"  Caught error: {e}")
    
    # Test 3: Valid input
    print("\nTest 3: Valid input")
    try:
        valid_face = np.random.randint(10, 245, (112, 112, 3), dtype=np.uint8)
        result = recognizer.recognize(valid_face)
        print(f"  Success! Emotion: {result.dominant_emotion}")
    except ValueError as e:
        print(f"  Unexpected error: {e}")


def example_deterministic_behavior():
    """Verify deterministic behavior."""
    print("\n" + "=" * 60)
    print("Example 8: Deterministic Behavior")
    print("=" * 60)
    
    # Initialize recognizer
    recognizer = EmotionRecognizer(model_name="fer", use_gpu=False)
    
    # Create a specific test face
    rng = np.random.RandomState(42)
    test_face = rng.randint(50, 200, (112, 112, 3), dtype=np.uint8)
    
    # Run recognition multiple times
    results = []
    for i in range(3):
        result = recognizer.recognize(test_face)
        results.append(result)
    
    # Verify consistency
    print("\nRunning recognition 3 times on same face:")
    all_same = all(
        r.dominant_emotion == results[0].dominant_emotion and
        r.confidence == results[0].confidence
        for r in results
    )
    
    if all_same:
        print("  ✓ Results are consistent (deterministic)")
        print(f"  Emotion: {results[0].dominant_emotion}")
        print(f"  Confidence: {results[0].confidence:.3f}")
    else:
        print("  ✗ Results differ (non-deterministic)")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("GuruVision Emotion Recognition Examples")
    print("=" * 60)
    
    try:
        example_basic_usage()
        example_multiple_faces()
        example_emotion_filtering()
        example_emotion_statistics()
        example_confidence_thresholding()
        example_top_emotions()
        example_error_handling()
        example_deterministic_behavior()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
