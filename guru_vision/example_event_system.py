"""
Example usage of GuruVision event system and callbacks.

This script demonstrates how to register callbacks for various events
and how they are triggered during engine operation.

Requirements: 13.3, 13.5
"""

import numpy as np
from datetime import datetime
from guru_vision.engine import GuruVisionEngine


def on_identity_recognized(event_data):
    """
    Callback for identity_recognized events.
    
    This is called whenever a known identity is recognized in a frame.
    """
    print(f"\n[IDENTITY RECOGNIZED]")
    print(f"  Identity: {event_data['identity']}")
    print(f"  Confidence: {event_data['confidence']:.3f}")
    print(f"  Permission Level: {event_data['permission_level']}")
    print(f"  Emotion: {event_data['emotion']} (confidence: {event_data['emotion_confidence']:.3f})")
    print(f"  Is Live: {event_data['is_live']}")
    print(f"  Tracking ID: {event_data['tracking_id']}")
    print(f"  Timestamp: {event_data['timestamp']}")


def on_new_identity(event_data):
    """
    Callback for new_identity events.
    
    This is called whenever a new identity is added to the database.
    """
    print(f"\n[NEW IDENTITY ADDED]")
    print(f"  Identity: {event_data['identity']}")
    print(f"  Permission Level: {event_data['permission_level']}")
    print(f"  Number of Embeddings: {event_data['num_embeddings']}")
    print(f"  Timestamp: {event_data['timestamp']}")


def on_permission_changed(event_data):
    """
    Callback for permission_changed events.
    
    This is called whenever an identity's permission level is updated.
    """
    print(f"\n[PERMISSION CHANGED]")
    print(f"  Identity: {event_data['identity']}")
    print(f"  New Permission Level: {event_data['new_permission_level']}")
    print(f"  Timestamp: {event_data['timestamp']}")


def on_error(event_data):
    """
    Callback for error events.
    
    This is called whenever an error occurs in any component.
    """
    print(f"\n[ERROR OCCURRED]")
    print(f"  Component: {event_data['component']}")
    print(f"  Error Type: {event_data['error_type']}")
    print(f"  Error Message: {event_data['error_message']}")
    print(f"  Timestamp: {event_data['timestamp']}")
    if 'frame_id' in event_data:
        print(f"  Frame ID: {event_data['frame_id']}")


def on_system_ready(event_data):
    """
    Callback for system_ready events.
    
    This is called when the engine completes initialization.
    """
    print(f"\n[SYSTEM READY]")
    print(f"  Number of Identities: {event_data['num_identities']}")
    print(f"  Timestamp: {event_data['timestamp']}")
    print(f"  Configuration loaded successfully")


def example_basic_callbacks():
    """
    Example 1: Basic callback registration and usage.
    
    This example shows how to register callbacks for different event types
    and demonstrates how they are triggered.
    """
    print("=" * 70)
    print("Example 1: Basic Callback Registration")
    print("=" * 70)
    
    # Create engine instance
    engine = GuruVisionEngine()
    
    # Register callbacks for all event types
    engine.register_callback('identity_recognized', on_identity_recognized)
    engine.register_callback('new_identity', on_new_identity)
    engine.register_callback('permission_changed', on_permission_changed)
    engine.register_callback('error', on_error)
    engine.register_callback('system_ready', on_system_ready)
    
    print("\nCallbacks registered for all event types:")
    print("  - identity_recognized")
    print("  - new_identity")
    print("  - permission_changed")
    print("  - error")
    print("  - system_ready")
    
    # Note: In a real application, you would call engine.initialize() here
    # which would trigger the system_ready event
    print("\nNote: Call engine.initialize() to trigger system_ready event")
    print("      Then use engine.process_frame() to trigger recognition events")


def example_multiple_callbacks():
    """
    Example 2: Multiple callbacks for the same event.
    
    This example shows how to register multiple callbacks for the same event type.
    All registered callbacks will be called when the event is emitted.
    """
    print("\n" + "=" * 70)
    print("Example 2: Multiple Callbacks for Same Event")
    print("=" * 70)
    
    engine = GuruVisionEngine()
    
    # Register multiple callbacks for identity_recognized event
    def callback1(data):
        print(f"\n[Callback 1] Identity: {data['identity']}")
    
    def callback2(data):
        print(f"[Callback 2] Confidence: {data['confidence']:.3f}")
    
    def callback3(data):
        print(f"[Callback 3] Permission: {data['permission_level']}")
    
    engine.register_callback('identity_recognized', callback1)
    engine.register_callback('identity_recognized', callback2)
    engine.register_callback('identity_recognized', callback3)
    
    print("\nRegistered 3 callbacks for 'identity_recognized' event")
    print("All 3 callbacks will be called when an identity is recognized")


def example_lambda_callbacks():
    """
    Example 3: Using lambda functions as callbacks.
    
    This example shows how to use lambda functions for simple callbacks.
    """
    print("\n" + "=" * 70)
    print("Example 3: Lambda Function Callbacks")
    print("=" * 70)
    
    engine = GuruVisionEngine()
    
    # Register lambda callbacks
    engine.register_callback(
        'identity_recognized',
        lambda data: print(f"Recognized: {data['identity']}")
    )
    
    engine.register_callback(
        'new_identity',
        lambda data: print(f"Added: {data['identity']}")
    )
    
    engine.register_callback(
        'error',
        lambda data: print(f"Error in {data['component']}: {data['error_message']}")
    )
    
    print("\nRegistered lambda callbacks for quick event handling")


def example_stateful_callback():
    """
    Example 4: Stateful callback with class.
    
    This example shows how to use a class-based callback that maintains state.
    """
    print("\n" + "=" * 70)
    print("Example 4: Stateful Callback with Class")
    print("=" * 70)
    
    class RecognitionLogger:
        """Logger that tracks recognition statistics."""
        
        def __init__(self):
            self.recognition_count = {}
            self.total_recognitions = 0
        
        def on_recognition(self, event_data):
            """Handle identity_recognized events."""
            identity = event_data['identity']
            
            # Update statistics
            if identity not in self.recognition_count:
                self.recognition_count[identity] = 0
            self.recognition_count[identity] += 1
            self.total_recognitions += 1
            
            # Log the recognition
            print(f"\n[Recognition #{self.total_recognitions}]")
            print(f"  Identity: {identity}")
            print(f"  Times seen: {self.recognition_count[identity]}")
            print(f"  Confidence: {event_data['confidence']:.3f}")
    
    # Create logger and register callback
    logger = RecognitionLogger()
    engine = GuruVisionEngine()
    engine.register_callback('identity_recognized', logger.on_recognition)
    
    print("\nRegistered stateful callback that tracks recognition statistics")


def example_conditional_callback():
    """
    Example 5: Conditional callback that filters events.
    
    This example shows how to create a callback that only acts on certain conditions.
    """
    print("\n" + "=" * 70)
    print("Example 5: Conditional Callback")
    print("=" * 70)
    
    def high_confidence_only(event_data):
        """Only log recognitions with confidence > 0.9."""
        if event_data['confidence'] > 0.9:
            print(f"\n[HIGH CONFIDENCE RECOGNITION]")
            print(f"  Identity: {event_data['identity']}")
            print(f"  Confidence: {event_data['confidence']:.3f}")
    
    def admin_only(event_data):
        """Only log admin-level recognitions."""
        if event_data['permission_level'] == 'admin':
            print(f"\n[ADMIN DETECTED]")
            print(f"  Identity: {event_data['identity']}")
            print(f"  Granting full access")
    
    engine = GuruVisionEngine()
    engine.register_callback('identity_recognized', high_confidence_only)
    engine.register_callback('identity_recognized', admin_only)
    
    print("\nRegistered conditional callbacks:")
    print("  - high_confidence_only: Only logs if confidence > 0.9")
    print("  - admin_only: Only logs if permission_level is 'admin'")


def example_error_handling():
    """
    Example 6: Error handling in callbacks.
    
    This example shows that exceptions in callbacks are caught and logged,
    and don't prevent other callbacks from executing.
    """
    print("\n" + "=" * 70)
    print("Example 6: Error Handling in Callbacks")
    print("=" * 70)
    
    def failing_callback(event_data):
        """This callback will raise an exception."""
        raise RuntimeError("Intentional error in callback")
    
    def working_callback(event_data):
        """This callback works normally."""
        print(f"\n[Working Callback] Identity: {event_data['identity']}")
    
    engine = GuruVisionEngine()
    engine.register_callback('identity_recognized', failing_callback)
    engine.register_callback('identity_recognized', working_callback)
    
    print("\nRegistered two callbacks:")
    print("  1. failing_callback: Will raise an exception")
    print("  2. working_callback: Will execute normally")
    print("\nThe exception in callback 1 will be caught and logged,")
    print("and callback 2 will still execute.")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("GuruVision Event System Examples")
    print("=" * 70)
    
    # Run all examples
    example_basic_callbacks()
    example_multiple_callbacks()
    example_lambda_callbacks()
    example_stateful_callback()
    example_conditional_callback()
    example_error_handling()
    
    print("\n" + "=" * 70)
    print("Examples Complete")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  1. Register callbacks using engine.register_callback(event_type, callback)")
    print("  2. Callbacks receive event data as a dictionary")
    print("  3. Multiple callbacks can be registered for the same event")
    print("  4. Callbacks can be functions, lambdas, or class methods")
    print("  5. Exceptions in callbacks are caught and logged")
    print("  6. Events are emitted automatically during engine operation")
    print("\nSupported Event Types:")
    print("  - identity_recognized: When an identity is recognized")
    print("  - new_identity: When a new identity is added")
    print("  - permission_changed: When permission level changes")
    print("  - error: When an error occurs")
    print("  - system_ready: When initialization completes")


if __name__ == '__main__':
    main()
