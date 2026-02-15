"""
Example usage of GuruVision Engine

This script demonstrates how to use the GuruVisionEngine for face recognition.
"""

import cv2
import numpy as np
from guru_vision.engine import GuruVisionEngine


def example_basic_usage():
    """
    Example: Basic engine initialization and usage.
    
    This example shows how to:
    1. Create and initialize the engine
    2. Process a frame
    3. Handle recognition results
    """
    print("=" * 60)
    print("Example 1: Basic Engine Usage")
    print("=" * 60)
    
    # Create engine instance
    engine = GuruVisionEngine()
    
    # Initialize the engine
    # Note: This will fail if models are not available, which is expected
    # In production, you would have the models downloaded and configured
    try:
        engine.initialize()
        print("✓ Engine initialized successfully")
    except Exception as e:
        print(f"✗ Engine initialization failed (expected if models not available): {e}")
        print("  In production, ensure models are downloaded and paths are configured")
        return
    
    # Create a test frame (in production, this would come from a camera)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Process the frame
    try:
        result = engine.process_frame(frame)
        
        print(f"\nFrame {result.frame_id} processed:")
        print(f"  Timestamp: {result.timestamp}")
        print(f"  Processing time: {result.processing_time_ms:.2f} ms")
        print(f"  Faces detected: {len(result.faces)}")
        
        # Display results for each face
        for i, face in enumerate(result.faces):
            print(f"\n  Face {i + 1}:")
            print(f"    Tracking ID: {face.tracking_id}")
            print(f"    Identity: {face.identity}")
            print(f"    Confidence: {face.confidence:.3f}")
            print(f"    Permission: {face.permission_level}")
            print(f"    Emotion: {face.emotion} ({face.emotion_confidence:.3f})")
            print(f"    Liveness: {'Live' if face.is_live else 'Spoof'} ({face.liveness_confidence:.3f})")
            print(f"    Bounding box: {face.bbox}")
        
    except Exception as e:
        print(f"✗ Frame processing failed: {e}")
    
    # Shutdown the engine
    try:
        engine.shutdown()
        print("\n✓ Engine shutdown successfully")
    except Exception as e:
        print(f"✗ Engine shutdown failed: {e}")


def example_with_callbacks():
    """
    Example: Using callbacks for recognition events.
    
    This example shows how to register callbacks to receive
    notifications when identities are recognized.
    """
    print("\n" + "=" * 60)
    print("Example 2: Using Callbacks")
    print("=" * 60)
    
    # Create engine instance
    engine = GuruVisionEngine()
    
    # Define callback function
    def on_identity_recognized(event_data):
        print(f"\n🔔 Identity Recognized Event:")
        print(f"   Identity: {event_data['identity']}")
        print(f"   Confidence: {event_data['confidence']:.3f}")
        print(f"   Permission: {event_data['permission_level']}")
        print(f"   Emotion: {event_data['emotion']}")
    
    def on_system_ready(event_data):
        print(f"\n✓ System Ready Event:")
        print(f"   Timestamp: {event_data['timestamp']}")
        print(f"   Identities loaded: {event_data['num_identities']}")
    
    # Register callbacks
    engine.register_callback('identity_recognized', on_identity_recognized)
    engine.register_callback('system_ready', on_system_ready)
    
    print("✓ Callbacks registered")
    
    # Initialize the engine (this will trigger system_ready event)
    try:
        engine.initialize()
    except Exception as e:
        print(f"✗ Engine initialization failed: {e}")
        return
    
    # Process frames (this will trigger identity_recognized events)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    try:
        result = engine.process_frame(frame)
        print(f"\nProcessed frame with {len(result.faces)} faces")
    except Exception as e:
        print(f"✗ Frame processing failed: {e}")
    
    # Shutdown
    try:
        engine.shutdown()
    except Exception as e:
        print(f"✗ Engine shutdown failed: {e}")


def example_with_config():
    """
    Example: Using custom configuration.
    
    This example shows how to create a custom configuration
    and use it with the engine.
    """
    print("\n" + "=" * 60)
    print("Example 3: Custom Configuration")
    print("=" * 60)
    
    from guru_vision.config import GuruVisionConfig
    
    # Create custom configuration
    config = GuruVisionConfig(
        recognition_threshold=0.7,  # Higher threshold for more strict matching
        enable_liveness=True,
        enable_emotion=True,
        enable_tracking=True,
        enable_low_light_enhancement=True,
        log_level="DEBUG"
    )
    
    print("Custom configuration:")
    print(f"  Recognition threshold: {config.recognition_threshold}")
    print(f"  Liveness detection: {config.enable_liveness}")
    print(f"  Emotion recognition: {config.enable_emotion}")
    print(f"  Face tracking: {config.enable_tracking}")
    print(f"  Low-light enhancement: {config.enable_low_light_enhancement}")
    print(f"  Log level: {config.log_level}")
    
    # Save configuration to file
    try:
        config.save_to_file("example_config.json")
        print("\n✓ Configuration saved to example_config.json")
    except Exception as e:
        print(f"✗ Failed to save configuration: {e}")
    
    # Create engine with config file
    engine = GuruVisionEngine(config_path="example_config.json")
    
    print("✓ Engine created with custom configuration")


def example_data_structures():
    """
    Example: Working with GuruVision data structures.
    
    This example shows the structure of recognition results.
    """
    print("\n" + "=" * 60)
    print("Example 4: Data Structures")
    print("=" * 60)
    
    from guru_vision.engine import FaceResult, RecognitionResult, IdentityInfo
    
    # Create a FaceResult
    face = FaceResult(
        tracking_id=1,
        bbox=(100, 100, 50, 50),
        identity="John Doe",
        confidence=0.87,
        permission_level="user",
        emotion="happy",
        emotion_confidence=0.75,
        is_live=True,
        liveness_confidence=0.92
    )
    
    print("FaceResult structure:")
    print(f"  Tracking ID: {face.tracking_id}")
    print(f"  Bounding box: {face.bbox}")
    print(f"  Identity: {face.identity}")
    print(f"  Confidence: {face.confidence}")
    print(f"  Permission level: {face.permission_level}")
    print(f"  Emotion: {face.emotion} (confidence: {face.emotion_confidence})")
    print(f"  Liveness: {'Live' if face.is_live else 'Spoof'} (confidence: {face.liveness_confidence})")
    
    # Create a RecognitionResult
    result = RecognitionResult(
        faces=[face],
        frame_id=42,
        timestamp="2024-01-15T10:30:00Z",
        processing_time_ms=45.5
    )
    
    print("\nRecognitionResult structure:")
    print(f"  Frame ID: {result.frame_id}")
    print(f"  Timestamp: {result.timestamp}")
    print(f"  Processing time: {result.processing_time_ms} ms")
    print(f"  Number of faces: {len(result.faces)}")
    
    # Create an IdentityInfo
    identity = IdentityInfo(
        name="John Doe",
        permission_level="user",
        num_embeddings=5,
        date_added="2024-01-15T10:30:00Z",
        metadata={"department": "engineering", "employee_id": "12345"}
    )
    
    print("\nIdentityInfo structure:")
    print(f"  Name: {identity.name}")
    print(f"  Permission level: {identity.permission_level}")
    print(f"  Number of embeddings: {identity.num_embeddings}")
    print(f"  Date added: {identity.date_added}")
    print(f"  Metadata: {identity.metadata}")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("GuruVision Engine Examples")
    print("=" * 60)
    
    # Run examples
    example_data_structures()
    example_with_config()
    
    # These examples require models to be available
    # Uncomment to run when models are set up
    # example_basic_usage()
    # example_with_callbacks()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nNote: Some examples are commented out because they require")
    print("trained models to be available. Uncomment them once you have:")
    print("  1. Trained a face recognition model")
    print("  2. Exported it to ONNX format")
    print("  3. Configured the model paths in the configuration")


if __name__ == "__main__":
    main()
