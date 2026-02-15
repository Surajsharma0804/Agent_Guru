"""
Example usage of the GuruVision Face Recognition Module.

This script demonstrates how to use the FaceRecognizer class for
embedding extraction and identity matching.
"""

import numpy as np
from guru_vision.recognition.recognizer import FaceRecognizer, MatchResult


def example_basic_usage():
    """Basic example of embedding extraction and matching."""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)
    
    # Note: This example uses mock data since we don't have a real ONNX model
    # In production, you would use an actual trained model
    
    print("\n1. Initialize FaceRecognizer")
    print("   recognizer = FaceRecognizer('model.onnx', use_gpu=True)")
    print("   (Skipped - requires actual ONNX model)")
    
    print("\n2. Extract embedding from aligned face")
    print("   aligned_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)")
    print("   embedding = recognizer.extract_embedding(aligned_face)")
    print("   Expected output shape: (512,)")
    
    print("\n3. Match against database")
    print("   result = recognizer.match_identity(embedding, database, threshold=0.6)")
    print("   Result contains: identity, confidence, permission_level")


def example_complete_pipeline():
    """Example of complete recognition pipeline."""
    print("\n" + "=" * 60)
    print("Example 2: Complete Recognition Pipeline")
    print("=" * 60)
    
    print("\nComplete pipeline flow:")
    print("1. Detect faces in frame (FaceDetector)")
    print("2. Align each detected face (FaceAligner)")
    print("3. Extract embedding (FaceRecognizer.extract_embedding)")
    print("4. Match identity (FaceRecognizer.match_identity)")
    
    print("\nCode structure:")
    print("""
    # Initialize components
    detector = FaceDetector(use_gpu=True)
    aligner = FaceAligner(output_size=(112, 112))
    recognizer = FaceRecognizer("model.onnx", use_gpu=True)
    database = FaceDatabase("identities.json")
    database.load()
    
    # Process frame
    frame = cv2.imread("image.jpg")
    detections = detector.detect(frame)
    
    for detection in detections:
        aligned_face = aligner.align(frame, detection)
        embedding = recognizer.extract_embedding(aligned_face)
        result = recognizer.match_identity(embedding, database)
        print(f"Identity: {result.identity} ({result.confidence:.2f})")
    """)


def example_gpu_vs_cpu():
    """Example of GPU vs CPU configuration."""
    print("\n" + "=" * 60)
    print("Example 3: GPU vs CPU Configuration")
    print("=" * 60)
    
    print("\nGPU Acceleration (Recommended for production):")
    print("   recognizer = FaceRecognizer('model.onnx', use_gpu=True)")
    print("   - Automatically uses CUDA if available")
    print("   - Falls back to CPU if GPU unavailable")
    print("   - Typical speed: 2-5ms per embedding")
    
    print("\nCPU Only:")
    print("   recognizer = FaceRecognizer('model.onnx', use_gpu=False)")
    print("   - Uses CPU execution provider")
    print("   - Typical speed: 20-30ms per embedding")
    
    print("\nCheck active provider:")
    print("   print(recognizer.active_provider)")
    print("   Output: 'CUDAExecutionProvider' or 'CPUExecutionProvider'")


def example_custom_thresholds():
    """Example of using custom recognition thresholds."""
    print("\n" + "=" * 60)
    print("Example 4: Custom Recognition Thresholds")
    print("=" * 60)
    
    print("\nDefault threshold (0.6):")
    print("   result = recognizer.match_identity(embedding, database)")
    print("   - Balanced between false positives and false negatives")
    
    print("\nStrict matching (0.8):")
    print("   result = recognizer.match_identity(embedding, database, threshold=0.8)")
    print("   - Fewer false positives (wrong identifications)")
    print("   - More false negatives (missed identifications)")
    print("   - Use for high-security applications")
    
    print("\nLenient matching (0.5):")
    print("   result = recognizer.match_identity(embedding, database, threshold=0.5)")
    print("   - Fewer false negatives (missed identifications)")
    print("   - More false positives (wrong identifications)")
    print("   - Use for convenience applications")


def example_match_result():
    """Example of working with MatchResult."""
    print("\n" + "=" * 60)
    print("Example 5: Working with MatchResult")
    print("=" * 60)
    
    # Create example match results
    match_found = MatchResult(
        identity="John Doe",
        confidence=0.87,
        permission_level="admin"
    )
    
    match_not_found = MatchResult(
        identity="Unknown",
        confidence=0.0,
        permission_level="guest"
    )
    
    print("\nWhen identity is found:")
    print(f"   Identity: {match_found.identity}")
    print(f"   Confidence: {match_found.confidence:.2f}")
    print(f"   Permission: {match_found.permission_level}")
    
    print("\nWhen identity is not found:")
    print(f"   Identity: {match_not_found.identity}")
    print(f"   Confidence: {match_not_found.confidence:.2f}")
    print(f"   Permission: {match_not_found.permission_level}")
    
    print("\nUsing the result:")
    print("""
    if result.identity != "Unknown":
        print(f"Welcome back, {result.identity}!")
        if result.permission_level == "admin":
            grant_admin_access()
        elif result.permission_level == "user":
            grant_user_access()
    else:
        print("Unknown person detected")
        grant_guest_access()
    """)


def example_error_handling():
    """Example of error handling."""
    print("\n" + "=" * 60)
    print("Example 6: Error Handling")
    print("=" * 60)
    
    print("\nCommon errors and how to handle them:")
    
    print("\n1. ImportError - ONNX Runtime not installed:")
    print("""
    try:
        recognizer = FaceRecognizer("model.onnx")
    except ImportError as e:
        print("Please install: pip install onnxruntime-gpu")
    """)
    
    print("\n2. RuntimeError - Model file not found:")
    print("""
    try:
        recognizer = FaceRecognizer("nonexistent.onnx")
    except RuntimeError as e:
        print(f"Model error: {e}")
    """)
    
    print("\n3. ValueError - Invalid input shape:")
    print("""
    try:
        wrong_size = np.zeros((100, 100, 3), dtype=np.uint8)
        embedding = recognizer.extract_embedding(wrong_size)
    except ValueError as e:
        print(f"Input error: {e}")
    """)
    
    print("\n4. ValueError - Invalid threshold:")
    print("""
    try:
        result = recognizer.match_identity(embedding, database, threshold=1.5)
    except ValueError as e:
        print(f"Threshold error: {e}")
    """)


def example_preprocessing_details():
    """Example showing preprocessing details."""
    print("\n" + "=" * 60)
    print("Example 7: Preprocessing Details")
    print("=" * 60)
    
    print("\nInput requirements:")
    print("   - Shape: (112, 112, 3)")
    print("   - Format: BGR (OpenCV format)")
    print("   - Data type: uint8")
    print("   - Value range: [0, 255]")
    
    print("\nPreprocessing steps:")
    print("   1. Convert to float32")
    print("   2. Normalize: (pixel / 127.5) - 1.0  →  [-1, 1]")
    print("   3. Transpose: HWC → CHW  →  (3, 112, 112)")
    print("   4. Add batch: (3, 112, 112) → (1, 3, 112, 112)")
    
    print("\nPost-processing:")
    print("   1. Remove batch dimension: (1, 512) → (512,)")
    print("   2. L2 normalize: embedding / ||embedding||")
    print("   3. Result: Unit-length 512-dimensional vector")
    
    # Demonstrate normalization
    print("\nExample normalization:")
    pixel_value = 127
    normalized = (pixel_value / 127.5) - 1.0
    print(f"   Pixel value: {pixel_value}")
    print(f"   Normalized: {normalized:.4f}")


def example_performance_tips():
    """Example of performance optimization tips."""
    print("\n" + "=" * 60)
    print("Example 8: Performance Tips")
    print("=" * 60)
    
    print("\n1. Use GPU acceleration:")
    print("   recognizer = FaceRecognizer('model.onnx', use_gpu=True)")
    print("   Speed improvement: 5-10x faster than CPU")
    
    print("\n2. Batch processing (if supported by model):")
    print("   Process multiple faces in a single inference call")
    print("   (Current implementation processes one face at a time)")
    
    print("\n3. Reuse recognizer instance:")
    print("   Create once, use many times")
    print("   Avoid recreating for each frame")
    
    print("\n4. Optimize threshold:")
    print("   Lower threshold = faster rejection of non-matches")
    print("   Higher threshold = more accurate but slower")
    
    print("\n5. Database optimization:")
    print("   Keep database in memory (don't reload each time)")
    print("   Limit number of identities for faster search")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("GuruVision Face Recognition Module - Examples")
    print("=" * 60)
    
    example_basic_usage()
    example_complete_pipeline()
    example_gpu_vs_cpu()
    example_custom_thresholds()
    example_match_result()
    example_error_handling()
    example_preprocessing_details()
    example_performance_tips()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nFor more information, see:")
    print("- README.md: Module documentation")
    print("- test_recognizer.py: Unit tests")
    print("- recognizer.py: Source code with detailed docstrings")
    print()


if __name__ == "__main__":
    main()
