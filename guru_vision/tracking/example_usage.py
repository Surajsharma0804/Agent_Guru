"""
Example usage of the GuruVision Face Tracking Module.

This script demonstrates how to use the FaceTracker to maintain stable
tracking IDs across video frames.
"""

import numpy as np
import cv2
from guru_vision.detection.detector import FaceDetector, Detection
from guru_vision.tracking import FaceTracker


def draw_tracks(frame: np.ndarray, tracks, color=(0, 255, 0)):
    """
    Draw tracking boxes and IDs on frame.
    
    Args:
        frame: Input frame
        tracks: List of Track objects
        color: Box color (BGR)
    """
    for track in tracks:
        x, y, w, h = track.bbox
        
        # Draw bounding box
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        
        # Draw tracking ID
        label = f"ID: {track.tracking_id}"
        cv2.putText(frame, label, (x, y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw age and hits info
        info = f"Age: {track.age}, Hits: {track.hits}"
        cv2.putText(frame, info, (x, y + h + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)


def example_webcam_tracking():
    """
    Example: Track faces from webcam feed.
    
    This demonstrates real-time face tracking with stable IDs.
    """
    print("Initializing face detector and tracker...")
    
    # Initialize detector and tracker
    detector = FaceDetector(use_gpu=False)
    tracker = FaceTracker(max_age=30)
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    print("Starting tracking... Press 'q' to quit")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Detect faces
        detections = detector.detect(frame)
        
        # Update tracker
        tracks = tracker.update(detections)
        
        # Draw tracks
        draw_tracks(frame, tracks)
        
        # Display info
        info_text = f"Frame: {frame_count} | Faces: {len(detections)} | Tracks: {len(tracks)}"
        cv2.putText(frame, info_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Show frame
        cv2.imshow('Face Tracking', frame)
        
        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"Processed {frame_count} frames")
    print(f"Total unique tracks: {tracker.next_id - 1}")


def example_video_tracking(video_path: str):
    """
    Example: Track faces in a video file.
    
    Args:
        video_path: Path to video file
    """
    print(f"Processing video: {video_path}")
    
    # Initialize detector and tracker
    detector = FaceDetector(use_gpu=False)
    tracker = FaceTracker(max_age=30)
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return
    
    frame_count = 0
    total_detections = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Detect faces
        detections = detector.detect(frame)
        total_detections += len(detections)
        
        # Update tracker
        tracks = tracker.update(detections)
        
        # Draw tracks
        draw_tracks(frame, tracks)
        
        # Display info
        info_text = f"Frame: {frame_count} | Tracks: {len(tracks)}"
        cv2.putText(frame, info_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Show frame
        cv2.imshow('Face Tracking', frame)
        
        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"\nProcessing complete:")
    print(f"  Total frames: {frame_count}")
    print(f"  Total detections: {total_detections}")
    print(f"  Unique tracks: {tracker.next_id - 1}")
    print(f"  Avg detections per frame: {total_detections / frame_count:.2f}")


def example_synthetic_tracking():
    """
    Example: Track synthetic faces (for testing without camera).
    
    This creates synthetic detections and demonstrates tracking behavior.
    """
    print("Running synthetic tracking example...")
    
    tracker = FaceTracker(max_age=5)
    
    # Simulate 20 frames
    for frame_num in range(20):
        print(f"\n--- Frame {frame_num + 1} ---")
        
        # Create synthetic detections
        detections = []
        
        if frame_num < 10:
            # Face 1: Moving right
            x = 100 + frame_num * 10
            detections.append(Detection(
                bbox=(x, 100, 50, 50),
                landmarks=np.zeros((5, 2)),
                confidence=0.9
            ))
        
        if frame_num >= 5 and frame_num < 15:
            # Face 2: Moving down
            y = 100 + (frame_num - 5) * 10
            detections.append(Detection(
                bbox=(300, y, 50, 50),
                landmarks=np.zeros((5, 2)),
                confidence=0.9
            ))
        
        if frame_num >= 10:
            # Face 3: Stationary
            detections.append(Detection(
                bbox=(500, 300, 50, 50),
                landmarks=np.zeros((5, 2)),
                confidence=0.9
            ))
        
        # Update tracker
        tracks = tracker.update(detections)
        
        # Print tracking info
        print(f"Detections: {len(detections)}")
        print(f"Active tracks: {len(tracks)}")
        
        for track in tracks:
            print(f"  Track {track.tracking_id}: bbox={track.bbox}, "
                  f"age={track.age}, hits={track.hits}")
    
    print(f"\nTotal unique tracks created: {tracker.next_id - 1}")


def example_track_persistence():
    """
    Example: Demonstrate track persistence across temporary occlusions.
    
    This shows how tracks are maintained even when faces temporarily disappear.
    """
    print("Demonstrating track persistence...")
    
    tracker = FaceTracker(max_age=5)
    
    # Frame 1-3: Face present
    print("\nFrames 1-3: Face present")
    for i in range(3):
        detection = Detection(
            bbox=(100 + i * 5, 100, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        tracks = tracker.update([detection])
        print(f"  Frame {i + 1}: Track ID={tracks[0].tracking_id}, Age={tracks[0].age}")
    
    # Frame 4-6: Face occluded (no detection)
    print("\nFrames 4-6: Face occluded")
    for i in range(3, 6):
        tracks = tracker.update([])
        if len(tracks) > 0:
            print(f"  Frame {i + 1}: Track ID={tracks[0].tracking_id}, Age={tracks[0].age} (predicted)")
        else:
            print(f"  Frame {i + 1}: Track deleted (exceeded max_age)")
    
    # Frame 7: Face reappears
    print("\nFrame 7: Face reappears")
    detection = Detection(
        bbox=(120, 100, 50, 50),
        landmarks=np.zeros((5, 2)),
        confidence=0.9
    )
    tracks = tracker.update([detection])
    if len(tracks) > 0:
        print(f"  Track ID={tracks[0].tracking_id}, Age={tracks[0].age}")
        if tracks[0].tracking_id == 1:
            print("  ✓ Same track maintained!")
        else:
            print("  ✗ New track created (old track was deleted)")


if __name__ == "__main__":
    print("GuruVision Face Tracking Examples\n")
    print("Available examples:")
    print("1. Synthetic tracking (no camera required)")
    print("2. Track persistence demonstration")
    print("3. Webcam tracking (requires camera)")
    print("4. Video file tracking (requires video file)")
    
    choice = input("\nSelect example (1-4): ")
    
    if choice == "1":
        example_synthetic_tracking()
    elif choice == "2":
        example_track_persistence()
    elif choice == "3":
        example_webcam_tracking()
    elif choice == "4":
        video_path = input("Enter video file path: ")
        example_video_tracking(video_path)
    else:
        print("Invalid choice. Running synthetic tracking example...")
        example_synthetic_tracking()
