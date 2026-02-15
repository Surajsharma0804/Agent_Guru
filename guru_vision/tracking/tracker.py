"""
GuruVision Face Tracking Module

This module provides face tracking across video frames using motion prediction
and data association algorithms. Maintains stable tracking IDs for faces across
consecutive frames.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 23.1, 23.2, 23.3, 23.4, 23.5, 23.6
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
from scipy.optimize import linear_sum_assignment


@dataclass
class Track:
    """
    Represents a tracked face across frames.
    
    Attributes:
        tracking_id: Unique identifier for this track
        bbox: Current bounding box coordinates as (x, y, w, h)
        age: Number of frames since last detection (0 = just detected)
        hits: Total number of successful detections for this track
        state: Kalman filter state vector [x, y, w, h, vx, vy, vw, vh]
        covariance: Kalman filter covariance matrix
    """
    tracking_id: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    age: int
    hits: int
    state: np.ndarray  # (8,) - [x, y, w, h, vx, vy, vw, vh]
    covariance: np.ndarray  # (8, 8)


class KalmanFilter:
    """
    Kalman filter for tracking bounding box motion.
    
    State vector: [x, y, w, h, vx, vy, vw, vh]
    - x, y: center coordinates
    - w, h: width and height
    - vx, vy, vw, vh: velocities
    """
    
    def __init__(self):
        """Initialize Kalman filter with constant velocity model."""
        # State dimension: 8 (x, y, w, h, vx, vy, vw, vh)
        # Measurement dimension: 4 (x, y, w, h)
        
        # State transition matrix (constant velocity model)
        self.F = np.eye(8)
        self.F[0, 4] = 1  # x += vx
        self.F[1, 5] = 1  # y += vy
        self.F[2, 6] = 1  # w += vw
        self.F[3, 7] = 1  # h += vh
        
        # Measurement matrix (we only observe position and size)
        self.H = np.zeros((4, 8))
        self.H[0, 0] = 1  # measure x
        self.H[1, 1] = 1  # measure y
        self.H[2, 2] = 1  # measure w
        self.H[3, 3] = 1  # measure h
        
        # Process noise covariance
        self.Q = np.eye(8)
        self.Q[4:, 4:] *= 0.01  # Lower noise for velocities
        
        # Measurement noise covariance
        self.R = np.eye(4) * 10.0
        
        # Initial covariance
        self.P_init = np.eye(8)
        self.P_init[4:, 4:] *= 1000.0  # High uncertainty for initial velocities
    
    def initiate(self, measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Initialize track from first measurement.
        
        Args:
            measurement: Initial bounding box [x, y, w, h]
            
        Returns:
            Tuple of (state, covariance)
        """
        state = np.zeros(8)
        state[:4] = measurement
        # Velocities initialized to zero
        
        return state, self.P_init.copy()
    
    def predict(self, state: np.ndarray, covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict next state using motion model.
        
        Args:
            state: Current state vector
            covariance: Current covariance matrix
            
        Returns:
            Tuple of (predicted_state, predicted_covariance)
        """
        # Predict state: x' = F * x
        predicted_state = self.F @ state
        
        # Predict covariance: P' = F * P * F^T + Q
        predicted_covariance = self.F @ covariance @ self.F.T + self.Q
        
        return predicted_state, predicted_covariance
    
    def update(self, state: np.ndarray, covariance: np.ndarray, 
               measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Update state with new measurement.
        
        Args:
            state: Predicted state vector
            covariance: Predicted covariance matrix
            measurement: New measurement [x, y, w, h]
            
        Returns:
            Tuple of (updated_state, updated_covariance)
        """
        # Innovation: y = z - H * x
        innovation = measurement - self.H @ state
        
        # Innovation covariance: S = H * P * H^T + R
        innovation_covariance = self.H @ covariance @ self.H.T + self.R
        
        # Kalman gain: K = P * H^T * S^-1
        kalman_gain = covariance @ self.H.T @ np.linalg.inv(innovation_covariance)
        
        # Update state: x' = x + K * y
        updated_state = state + kalman_gain @ innovation
        
        # Update covariance: P' = (I - K * H) * P
        updated_covariance = (np.eye(8) - kalman_gain @ self.H) @ covariance
        
        return updated_state, updated_covariance


class FaceTracker:
    """
    Multi-object face tracker using Kalman filter and Hungarian algorithm.
    
    Maintains stable tracking IDs across frames by predicting motion and
    associating detections with existing tracks.
    """
    
    def __init__(self, algorithm: str = "kalman", max_age: int = 30):
        """
        Initialize face tracker.
        
        Args:
            algorithm: Tracking algorithm ("kalman", "deepsort", "bytetrack")
                      Currently only "kalman" is implemented
            max_age: Maximum number of frames to keep a track without detection
                    Default 30 frames (3 seconds at 10 FPS)
        """
        self.algorithm = algorithm
        self.max_age = max_age
        self.kalman_filter = KalmanFilter()
        
        self.tracks: List[Track] = []
        self.next_id = 1
        
        # IOU threshold for association
        self.iou_threshold = 0.3
    
    def _bbox_to_measurement(self, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """
        Convert bounding box to measurement vector.
        
        Args:
            bbox: Bounding box as (x, y, w, h)
            
        Returns:
            Measurement vector [x, y, w, h]
        """
        return np.array(bbox, dtype=np.float64)
    
    def _measurement_to_bbox(self, measurement: np.ndarray) -> Tuple[int, int, int, int]:
        """
        Convert measurement vector to bounding box.
        
        Args:
            measurement: Measurement vector [x, y, w, h]
            
        Returns:
            Bounding box as (x, y, w, h)
        """
        return tuple(measurement[:4].astype(int))
    
    def _compute_iou(self, bbox1: Tuple[int, int, int, int], 
                     bbox2: Tuple[int, int, int, int]) -> float:
        """
        Compute Intersection over Union (IoU) between two bounding boxes.
        
        Args:
            bbox1: First bounding box (x, y, w, h)
            bbox2: Second bounding box (x, y, w, h)
            
        Returns:
            IoU score between 0.0 and 1.0
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Convert to (x1, y1, x2, y2) format
        box1 = [x1, y1, x1 + w1, y1 + h1]
        box2 = [x2, y2, x2 + w2, y2 + h2]
        
        # Compute intersection
        x_left = max(box1[0], box2[0])
        y_top = max(box1[1], box2[1])
        x_right = min(box1[2], box2[2])
        y_bottom = min(box1[3], box2[3])
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Compute union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _associate_detections_to_tracks(self, detections: List[Tuple[int, int, int, int]],
                                       tracks: List[Track]) -> Tuple[List[Tuple[int, int]], 
                                                                     List[int], 
                                                                     List[int]]:
        """
        Associate detections to existing tracks using Hungarian algorithm.
        
        Args:
            detections: List of detection bounding boxes
            tracks: List of existing tracks
            
        Returns:
            Tuple of (matches, unmatched_detections, unmatched_tracks)
            - matches: List of (detection_idx, track_idx) pairs
            - unmatched_detections: List of detection indices
            - unmatched_tracks: List of track indices
        """
        if len(tracks) == 0:
            return [], list(range(len(detections))), []
        
        if len(detections) == 0:
            return [], [], list(range(len(tracks)))
        
        # Compute cost matrix (1 - IoU)
        cost_matrix = np.zeros((len(detections), len(tracks)))
        
        for d, det_bbox in enumerate(detections):
            for t, track in enumerate(tracks):
                iou = self._compute_iou(det_bbox, track.bbox)
                cost_matrix[d, t] = 1 - iou
        
        # Apply Hungarian algorithm
        det_indices, track_indices = linear_sum_assignment(cost_matrix)
        
        # Filter matches by IoU threshold
        matches = []
        unmatched_detections = list(range(len(detections)))
        unmatched_tracks = list(range(len(tracks)))
        
        for d, t in zip(det_indices, track_indices):
            if cost_matrix[d, t] < (1 - self.iou_threshold):
                matches.append((d, t))
                unmatched_detections.remove(d)
                unmatched_tracks.remove(t)
        
        return matches, unmatched_detections, unmatched_tracks
    
    def update(self, detections: List, frame: Optional[np.ndarray] = None) -> List[Track]:
        """
        Update tracks with new detections.
        
        This method implements the complete tracking pipeline:
        1. Predict track positions using motion model (Kalman filter)
        2. Associate detections with existing tracks (Hungarian algorithm)
        3. Update matched tracks with new measurements
        4. Create new tracks for unmatched detections
        5. Delete tracks exceeding max_age
        
        Args:
            detections: List of Detection objects from face detector
            frame: Optional frame image (not used in current implementation)
            
        Returns:
            List of active Track objects
        """
        # Extract bounding boxes from detections
        detection_bboxes = [det.bbox for det in detections]
        
        # Step 1: Predict track positions
        for track in self.tracks:
            track.state, track.covariance = self.kalman_filter.predict(
                track.state, track.covariance
            )
            # Update bbox from predicted state
            track.bbox = self._measurement_to_bbox(track.state)
        
        # Step 2: Associate detections with tracks
        matches, unmatched_detections, unmatched_tracks = \
            self._associate_detections_to_tracks(detection_bboxes, self.tracks)
        
        # Step 3: Update matched tracks
        for det_idx, track_idx in matches:
            track = self.tracks[track_idx]
            measurement = self._bbox_to_measurement(detection_bboxes[det_idx])
            
            track.state, track.covariance = self.kalman_filter.update(
                track.state, track.covariance, measurement
            )
            track.bbox = self._measurement_to_bbox(track.state)
            track.age = 0  # Reset age since we got a detection
            track.hits += 1
        
        # Step 4: Create new tracks for unmatched detections
        for det_idx in unmatched_detections:
            measurement = self._bbox_to_measurement(detection_bboxes[det_idx])
            state, covariance = self.kalman_filter.initiate(measurement)
            
            new_track = Track(
                tracking_id=self.next_id,
                bbox=detection_bboxes[det_idx],
                age=0,
                hits=1,
                state=state,
                covariance=covariance
            )
            self.tracks.append(new_track)
            self.next_id += 1
        
        # Step 5: Increment age for unmatched tracks and delete old tracks
        for track_idx in unmatched_tracks:
            self.tracks[track_idx].age += 1
        
        # Remove tracks that exceed max_age
        self.tracks = [track for track in self.tracks if track.age <= self.max_age]
        
        return self.tracks
    
    def get_track_by_id(self, tracking_id: int) -> Optional[Track]:
        """
        Get track by tracking ID.
        
        Args:
            tracking_id: Tracking ID to search for
            
        Returns:
            Track object if found, None otherwise
        """
        for track in self.tracks:
            if track.tracking_id == tracking_id:
                return track
        return None
    
    def reset(self):
        """Reset tracker, clearing all tracks."""
        self.tracks = []
        self.next_id = 1
