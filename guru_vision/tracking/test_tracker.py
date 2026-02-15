"""
Unit tests for face tracking module.

Tests the FaceTracker class and its tracking functionality.
"""

import pytest
import numpy as np
from guru_vision.tracking import FaceTracker, Track
from guru_vision.detection.detector import Detection


class TestKalmanFilter:
    """Test Kalman filter functionality."""
    
    def test_initiate(self):
        """Test Kalman filter initialization."""
        from guru_vision.tracking.tracker import KalmanFilter
        
        kf = KalmanFilter()
        measurement = np.array([100, 100, 50, 50])
        
        state, covariance = kf.initiate(measurement)
        
        assert state.shape == (8,)
        assert covariance.shape == (8, 8)
        assert np.allclose(state[:4], measurement)
        assert np.allclose(state[4:], 0)  # Velocities should be zero
    
    def test_predict(self):
        """Test Kalman filter prediction."""
        from guru_vision.tracking.tracker import KalmanFilter
        
        kf = KalmanFilter()
        state = np.array([100, 100, 50, 50, 5, 5, 0, 0])  # Moving right and down
        covariance = np.eye(8)
        
        predicted_state, predicted_covariance = kf.predict(state, covariance)
        
        # Position should update based on velocity
        assert predicted_state[0] > state[0]  # x increased
        assert predicted_state[1] > state[1]  # y increased
        assert predicted_state.shape == (8,)
        assert predicted_covariance.shape == (8, 8)
    
    def test_update(self):
        """Test Kalman filter update with measurement."""
        from guru_vision.tracking.tracker import KalmanFilter
        
        kf = KalmanFilter()
        state = np.array([100, 100, 50, 50, 5, 5, 0, 0])
        covariance = np.eye(8)
        measurement = np.array([105, 105, 50, 50])
        
        updated_state, updated_covariance = kf.update(state, covariance, measurement)
        
        # State should be updated towards measurement
        assert updated_state.shape == (8,)
        assert updated_covariance.shape == (8, 8)


class TestFaceTracker:
    """Test FaceTracker functionality."""
    
    def test_initialization(self):
        """Test tracker initialization."""
        tracker = FaceTracker(max_age=30)
        
        assert tracker.max_age == 30
        assert len(tracker.tracks) == 0
        assert tracker.next_id == 1
    
    def test_single_detection_creates_track(self):
        """Test that a single detection creates a new track."""
        tracker = FaceTracker()
        
        # Create a detection
        detection = Detection(
            bbox=(100, 100, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        
        tracks = tracker.update([detection])
        
        assert len(tracks) == 1
        assert tracks[0].tracking_id == 1
        assert tracks[0].bbox == (100, 100, 50, 50)
        assert tracks[0].age == 0
        assert tracks[0].hits == 1
    
    def test_multiple_detections_create_multiple_tracks(self):
        """Test that multiple detections create multiple tracks."""
        tracker = FaceTracker()
        
        detections = [
            Detection(bbox=(100, 100, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(200, 200, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(300, 300, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
        ]
        
        tracks = tracker.update(detections)
        
        assert len(tracks) == 3
        assert tracks[0].tracking_id == 1
        assert tracks[1].tracking_id == 2
        assert tracks[2].tracking_id == 3
    
    def test_tracking_id_persistence(self):
        """Test that tracking IDs persist across frames."""
        tracker = FaceTracker()
        
        # Frame 1: Create track
        detection1 = Detection(
            bbox=(100, 100, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        tracks1 = tracker.update([detection1])
        track_id = tracks1[0].tracking_id
        
        # Frame 2: Same face, slightly moved
        detection2 = Detection(
            bbox=(105, 105, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        tracks2 = tracker.update([detection2])
        
        # Should maintain same tracking ID
        assert len(tracks2) == 1
        assert tracks2[0].tracking_id == track_id
        assert tracks2[0].hits == 2
    
    def test_track_deletion_after_max_age(self):
        """Test that tracks are deleted after exceeding max_age."""
        tracker = FaceTracker(max_age=2)
        
        # Frame 1: Create track
        detection = Detection(
            bbox=(100, 100, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        tracker.update([detection])
        
        # Frames 2-4: No detections (track ages)
        for _ in range(3):
            tracks = tracker.update([])
        
        # Track should be deleted after max_age
        assert len(tracks) == 0
    
    def test_track_age_increments_without_detection(self):
        """Test that track age increments when not detected."""
        tracker = FaceTracker(max_age=5)
        
        # Frame 1: Create track
        detection = Detection(
            bbox=(100, 100, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        tracks = tracker.update([detection])
        assert tracks[0].age == 0
        
        # Frame 2: No detection
        tracks = tracker.update([])
        assert len(tracks) == 1
        assert tracks[0].age == 1
        
        # Frame 3: No detection
        tracks = tracker.update([])
        assert len(tracks) == 1
        assert tracks[0].age == 2
    
    def test_track_age_resets_on_detection(self):
        """Test that track age resets when detected again."""
        tracker = FaceTracker(max_age=5)
        
        # Frame 1: Create track
        detection1 = Detection(
            bbox=(100, 100, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        tracker.update([detection1])
        
        # Frame 2: No detection (age = 1)
        tracker.update([])
        
        # Frame 3: Detected again
        detection2 = Detection(
            bbox=(105, 105, 50, 50),
            landmarks=np.zeros((5, 2)),
            confidence=0.9
        )
        tracks = tracker.update([detection2])
        
        # Age should reset to 0
        assert tracks[0].age == 0
    
    def test_iou_computation(self):
        """Test IoU computation between bounding boxes."""
        tracker = FaceTracker()
        
        # Identical boxes
        iou1 = tracker._compute_iou((100, 100, 50, 50), (100, 100, 50, 50))
        assert iou1 == 1.0
        
        # No overlap
        iou2 = tracker._compute_iou((100, 100, 50, 50), (200, 200, 50, 50))
        assert iou2 == 0.0
        
        # Partial overlap
        iou3 = tracker._compute_iou((100, 100, 50, 50), (125, 125, 50, 50))
        assert 0.0 < iou3 < 1.0
    
    def test_get_track_by_id(self):
        """Test retrieving track by ID."""
        tracker = FaceTracker()
        
        detections = [
            Detection(bbox=(100, 100, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(200, 200, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
        ]
        tracker.update(detections)
        
        track = tracker.get_track_by_id(1)
        assert track is not None
        assert track.tracking_id == 1
        
        track = tracker.get_track_by_id(2)
        assert track is not None
        assert track.tracking_id == 2
        
        track = tracker.get_track_by_id(999)
        assert track is None
    
    def test_reset(self):
        """Test tracker reset."""
        tracker = FaceTracker()
        
        # Create some tracks
        detections = [
            Detection(bbox=(100, 100, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(200, 200, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
        ]
        tracker.update(detections)
        
        assert len(tracker.tracks) == 2
        
        # Reset
        tracker.reset()
        
        assert len(tracker.tracks) == 0
        assert tracker.next_id == 1
    
    def test_multiple_faces_tracking(self):
        """Test tracking multiple faces simultaneously."""
        tracker = FaceTracker()
        
        # Frame 1: Three faces
        detections1 = [
            Detection(bbox=(100, 100, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(200, 200, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(300, 300, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
        ]
        tracks1 = tracker.update(detections1)
        assert len(tracks1) == 3
        
        # Frame 2: Same three faces, slightly moved
        detections2 = [
            Detection(bbox=(105, 105, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(205, 205, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
            Detection(bbox=(305, 305, 50, 50), landmarks=np.zeros((5, 2)), confidence=0.9),
        ]
        tracks2 = tracker.update(detections2)
        
        # Should maintain same tracking IDs
        assert len(tracks2) == 3
        assert set(t.tracking_id for t in tracks2) == {1, 2, 3}
        
        # All tracks should have 2 hits
        for track in tracks2:
            assert track.hits == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
