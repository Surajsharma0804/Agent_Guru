#!/usr/bin/env python3
"""
GuruVision Real-Time Webcam Recognition Example

This example demonstrates how to use the GuruVision engine for real-time face
recognition from a webcam feed. It shows how to initialize the engine, process
frames, and handle recognition events.

Requirements: 19.1, 31.2

Usage:
    python examples/recognize_webcam.py
    python examples/recognize_webcam.py --camera 0
    python examples/recognize_webcam.py --config config.yaml
"""

import os
import sys
import argparse
import cv2
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guru_vision.engine import GuruVisionEngine


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GuruVision Real-Time Webcam Recognition",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera device index (default: 0)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (optional)"
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable video display window"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=10,
        help="Target frames per second (default: 10)"
    )
    
    return parser.parse_args()


def draw_face_box(frame, face_result):
    """
    Draw bounding box and information for a detected face.
    
    Args:
        frame: Video frame to draw on
        face_result: FaceResult object with detection information
    """
    x, y, w, h = face_result.bbox
    
    # Choose color based on identity and liveness
    if not face_result.is_live:
        color = (0, 0, 255)  # Red for spoof
        label_bg = (0, 0, 200)
    elif face_result.identity == "Unknown":
        color = (0, 255, 255)  # Yellow for unknown
        label_bg = (0, 200, 200)
    else:
        color = (0, 255, 0)  # Green for recognized
        label_bg = (0, 200, 0)
    
    # Draw bounding box
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
    
    # Prepare label text
    if not face_result.is_live:
        label = f"SPOOF ({face_result.liveness_confidence:.2f})"
    elif face_result.identity == "Unknown":
        label = f"Unknown ({face_result.confidence:.2f})"
    else:
        label = f"{face_result.identity} ({face_result.confidence:.2f})"
    
    # Add emotion if available
    if face_result.emotion and face_result.emotion != "neutral":
        label += f" | {face_result.emotion}"
    
    # Add permission level
    if face_result.permission_level:
        label += f" | {face_result.permission_level}"
    
    # Draw label background
    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(
        frame,
        (x, y - 25),
        (x + label_size[0] + 10, y),
        label_bg,
        -1
    )
    
    # Draw label text
    cv2.putText(
        frame,
        label,
        (x + 5, y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA
    )
    
    # Draw tracking ID
    cv2.putText(
        frame,
        f"ID: {face_result.tracking_id}",
        (x, y + h + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        color,
        1,
        cv2.LINE_AA
    )


def draw_stats(frame, result, fps):
    """
    Draw statistics overlay on the frame.
    
    Args:
        frame: Video frame to draw on
        result: RecognitionResult object
        fps: Current frames per second
    """
    height, width = frame.shape[:2]
    
    # Draw semi-transparent background for stats
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (300, 120), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    # Draw stats text
    stats_text = [
        f"FPS: {fps:.1f}",
        f"Faces: {len(result.faces)}",
        f"Processing: {result.processing_time_ms:.1f}ms",
        f"Frame: {result.frame_id}"
    ]
    
    y_offset = 30
    for text in stats_text:
        cv2.putText(
            frame,
            text,
            (20, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )
        y_offset += 25


def on_identity_recognized(event_data):
    """
    Callback function triggered when an identity is recognized.
    
    Args:
        event_data: Dictionary with recognition event information
    """
    print(f"[EVENT] Identity recognized: {event_data['identity']} "
          f"(confidence: {event_data['confidence']:.2f}, "
          f"permission: {event_data['permission_level']})")


def on_error(event_data):
    """
    Callback function triggered when an error occurs.
    
    Args:
        event_data: Dictionary with error information
    """
    print(f"[ERROR] {event_data['message']}")


def main():
    """
    Main function for real-time webcam recognition.
    
    This example demonstrates:
    1. Initializing the GuruVision engine
    2. Opening a webcam video stream
    3. Processing frames in real-time
    4. Displaying recognition results
    5. Handling keyboard input for control
    6. Clean shutdown
    """
    args = parse_arguments()
    
    print("=" * 80)
    print("GuruVision Real-Time Webcam Recognition")
    print("=" * 80)
    print()
    
    # =========================================================================
    # STEP 1: Initialize GuruVision Engine
    # =========================================================================
    print("Initializing GuruVision engine...")
    print()
    
    try:
        # Create engine instance
        engine = GuruVisionEngine(config_path=args.config)
        
        # Initialize all subsystems
        engine.initialize()
        
        print("✓ Engine initialized successfully!")
        print()
        
        # Register event callbacks
        engine.register_callback('identity_recognized', on_identity_recognized)
        engine.register_callback('error', on_error)
        
    except Exception as e:
        print(f"✗ Failed to initialize engine: {str(e)}")
        print()
        print("Common issues:")
        print("  • ONNX model not found (run training first)")
        print("  • Database file not found")
        print("  • Invalid configuration")
        print()
        return
    
    # =========================================================================
    # STEP 2: Open Webcam
    # =========================================================================
    print(f"Opening webcam (device {args.camera})...")
    
    cap = cv2.VideoCapture(args.camera)
    
    if not cap.isOpened():
        print(f"✗ Failed to open camera device {args.camera}")
        print()
        print("Troubleshooting:")
        print("  • Check that your webcam is connected")
        print("  • Try a different camera index (--camera 1, --camera 2, etc.)")
        print("  • Check camera permissions")
        print()
        return
    
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"✓ Camera opened: {actual_width}x{actual_height}")
    print()
    
    # =========================================================================
    # STEP 3: Display Instructions
    # =========================================================================
    print("Controls:")
    print("  • Press 'q' or ESC to quit")
    print("  • Press 's' to take a screenshot")
    print("  • Press 'p' to pause/resume")
    print()
    print("Starting recognition...")
    print("=" * 80)
    print()
    
    # =========================================================================
    # STEP 4: Main Recognition Loop
    # =========================================================================
    paused = False
    fps_counter = 0
    fps_start_time = time.time()
    current_fps = 0.0
    screenshot_counter = 0
    
    try:
        while True:
            # Read frame from camera
            ret, frame = cap.read()
            
            if not ret:
                print("Failed to read frame from camera")
                break
            
            # Process frame if not paused
            if not paused:
                # Process frame with GuruVision engine
                result = engine.process_frame(frame)
                
                # Update FPS counter
                fps_counter += 1
                if fps_counter >= 10:
                    elapsed = time.time() - fps_start_time
                    current_fps = fps_counter / elapsed
                    fps_counter = 0
                    fps_start_time = time.time()
                
                # Draw results on frame
                if not args.no_display:
                    # Draw bounding boxes for each face
                    for face in result.faces:
                        draw_face_box(frame, face)
                    
                    # Draw statistics overlay
                    draw_stats(frame, result, current_fps)
                    
                    # Draw paused indicator if paused
                    if paused:
                        cv2.putText(
                            frame,
                            "PAUSED",
                            (frame.shape[1] // 2 - 50, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 0, 255),
                            2,
                            cv2.LINE_AA
                        )
            
            # Display frame
            if not args.no_display:
                cv2.imshow("GuruVision - Webcam Recognition", frame)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # 'q' or ESC
                print("\nShutting down...")
                break
            elif key == ord('s'):  # Screenshot
                screenshot_path = f"screenshot_{screenshot_counter:04d}.jpg"
                cv2.imwrite(screenshot_path, frame)
                print(f"Screenshot saved: {screenshot_path}")
                screenshot_counter += 1
            elif key == ord('p'):  # Pause/Resume
                paused = not paused
                status = "PAUSED" if paused else "RESUMED"
                print(f"Recognition {status}")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        # =====================================================================
        # STEP 5: Cleanup
        # =====================================================================
        print("\nCleaning up...")
        
        # Release camera
        cap.release()
        
        # Close windows
        if not args.no_display:
            cv2.destroyAllWindows()
        
        # Shutdown engine
        engine.shutdown()
        
        print("✓ Cleanup complete")
        print()
        print("=" * 80)
        print("Session ended")
        print("=" * 80)


if __name__ == "__main__":
    main()
