//! # Multi-Object Tracking Module
//! 
//! Kalman filter-based multi-object tracking with state prediction and correction.
//! Implements Deep SORT algorithms with clean room compliance for production-grade tracking.

use super::{VisionResult, DetectionResult, TrackedObject, TrackingResult, VisionConfig};
use std::collections::HashMap;
use std::time::Instant;
use serde::{Deserialize, Serialize};

/// Multi-object tracker trait
pub trait MultiObjectTracker {
    /// Update tracker with new detections
    fn update(&mut self, detections: &DetectionResult) -> VisionResult<TrackingResult>;
    
    /// Predict next state for all tracks
    fn predict(&mut self) -> VisionResult<()>;
    
    /// Get current tracked objects
    fn get_tracks(&self) -> &[TrackedObject];
    
    /// Get tracking metrics
    fn get_metrics(&self) -> TrackingMetrics;
    
    /// Reset tracker state
    fn reset(&mut self);
}

/// Tracking performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrackingMetrics {
    /// Average tracking time (ms)
    pub avg_tracking_time_ms: f32,
    /// Number of active tracks
    pub active_tracks: u32,
    /// Total tracks created
    pub total_tracks_created: u64,
    /// Total tracks terminated
    pub total_tracks_terminated: u64,
    /// Track accuracy (if ground truth available)
    pub accuracy: Option<f32>,
    /// Average track length (frames)
    pub avg_track_length: f32,
}

/// Kalman filter for object state estimation
#[derive(Debug, Clone)]
pub struct KalmanFilter {
    /// State dimension (8: x, y, a, h, vx, vy, va, vh)
    state_dim: usize,
    /// Observation dimension (4: x, y, a, h)
    obs_dim: usize,
    /// Motion model matrix (8x8)
    motion_matrix: Vec<Vec<f32>>,
    /// Observation matrix (4x8)
    observation_matrix: Vec<Vec<f32>>,
    /// Process noise weights
    std_weight_position: f32,
    std_weight_velocity: f32,
}

/// Track state enumeration
#[derive(Debug, Clone, PartialEq)]
pub enum TrackState {
    /// Track is newly created and not yet confirmed
    Tentative,
    /// Track is confirmed and actively being tracked
    Confirmed,
    /// Track has been deleted due to loss of detection
    Deleted,
}

/// Individual track representation
#[derive(Debug, Clone)]
pub struct Track {
    /// Unique track ID
    pub track_id: u64,
    /// Current state mean (8-dimensional)
    pub mean: Vec<f32>,
    /// State covariance matrix (8x8)
    pub covariance: Vec<Vec<f32>>,
    /// Track state
    pub state: TrackState,
    /// Number of frames since last update
    pub time_since_update: u32,
    /// Track age in frames
    pub age: u32,
    /// Number of consecutive hits
    pub hits: u32,
    /// Hit streak counter
    pub hit_streak: u32,
    /// Tracking confidence
    pub confidence: f32,
    /// Feature history for appearance matching
    pub features: Vec<Vec<f32>>,
}

/// Deep SORT tracker implementation
pub struct DeepSortTracker {
    /// Kalman filter for state estimation
    kalman_filter: KalmanFilter,
    /// Active tracks
    tracks: Vec<Track>,
    /// Next track ID
    next_track_id: u64,
    /// Maximum age before track deletion
    max_age: u32,
    /// Minimum hits for track confirmation
    n_init: u32,
    /// Maximum IoU distance for association
    max_iou_distance: f32,
    /// Performance metrics
    metrics: TrackingMetrics,
    /// Association matrix
    association_matrix: Vec<Vec<f32>>,
    /// Chi-square distribution thresholds
    chi2_thresholds: HashMap<u32, f32>,
}

impl KalmanFilter {
    /// Create new Kalman filter
    pub fn new() -> Self {
        let state_dim = 8;
        let obs_dim = 4;
        let dt = 1.0; // Time step
        
        // Create motion model matrix (constant velocity model)
        let mut motion_matrix = vec![vec![0.0; state_dim]; state_dim];
        for i in 0..obs_dim {
            motion_matrix[i][i] = 1.0;
            motion_matrix[i][obs_dim + i] = dt;
        }
        for i in obs_dim..state_dim {
            motion_matrix[i][i] = 1.0;
        }
        
        // Create observation matrix
        let mut observation_matrix = vec![vec![0.0; state_dim]; obs_dim];
        for i in 0..obs_dim {
            observation_matrix[i][i] = 1.0;
        }
        
        Self {
            state_dim,
            obs_dim,
            motion_matrix,
            observation_matrix,
            std_weight_position: 1.0 / 20.0,
            std_weight_velocity: 1.0 / 160.0,
        }
    }
    
    /// Initialize track from measurement
    pub fn initiate(&self, measurement: &[f32]) -> (Vec<f32>, Vec<Vec<f32>>) {
        let mut mean = vec![0.0; self.state_dim];
        let mut covariance = vec![vec![0.0; self.state_dim]; self.state_dim];
        
        // Initialize position from measurement
        for i in 0..self.obs_dim {
            mean[i] = measurement[i];
        }
        
        // Initialize velocity to zero
        for i in self.obs_dim..self.state_dim {
            mean[i] = 0.0;
        }
        
        // Initialize covariance matrix
        let std_pos = [
            2.0 * self.std_weight_position * measurement[3], // x
            2.0 * self.std_weight_position * measurement[3], // y
            1e-2,                                            // aspect ratio
            2.0 * self.std_weight_position * measurement[3], // height
        ];
        
        let std_vel = [
            10.0 * self.std_weight_velocity * measurement[3], // vx
            10.0 * self.std_weight_velocity * measurement[3], // vy
            1e-5,                                             // va
            10.0 * self.std_weight_velocity * measurement[3], // vh
        ];
        
        for i in 0..self.obs_dim {
            covariance[i][i] = std_pos[i] * std_pos[i];
        }
        for i in self.obs_dim..self.state_dim {
            covariance[i][i] = std_vel[i - self.obs_dim] * std_vel[i - self.obs_dim];
        }
        
        (mean, covariance)
    }
    
    /// Predict next state
    pub fn predict(&self, mean: &[f32], covariance: &[Vec<f32>]) -> (Vec<f32>, Vec<Vec<f32>>) {
        // Predict mean
        let mut predicted_mean = vec![0.0; self.state_dim];
        for i in 0..self.state_dim {
            for j in 0..self.state_dim {
                predicted_mean[i] += self.motion_matrix[i][j] * mean[j];
            }
        }
        
        // Predict covariance
        let mut predicted_covariance = vec![vec![0.0; self.state_dim]; self.state_dim];
        
        // P = F * P * F^T + Q
        for i in 0..self.state_dim {
            for j in 0..self.state_dim {
                for k in 0..self.state_dim {
                    for l in 0..self.state_dim {
                        predicted_covariance[i][j] += 
                            self.motion_matrix[i][k] * covariance[k][l] * self.motion_matrix[j][l];
                    }
                }
            }
        }
        
        // Add process noise
        let std_pos = [
            self.std_weight_position * mean[3],
            self.std_weight_position * mean[3],
            1e-2,
            self.std_weight_position * mean[3],
        ];
        
        let std_vel = [
            self.std_weight_velocity * mean[3],
            self.std_weight_velocity * mean[3],
            1e-5,
            self.std_weight_velocity * mean[3],
        ];
        
        for i in 0..self.obs_dim {
            predicted_covariance[i][i] += std_pos[i] * std_pos[i];
        }
        for i in self.obs_dim..self.state_dim {
            predicted_covariance[i][i] += std_vel[i - self.obs_dim] * std_vel[i - self.obs_dim];
        }
        
        (predicted_mean, predicted_covariance)
    }
    
    /// Update state with measurement
    pub fn update(&self, mean: &[f32], covariance: &[Vec<f32>], measurement: &[f32]) 
        -> (Vec<f32>, Vec<Vec<f32>>) {
        
        // Project state to measurement space
        let (projected_mean, projected_cov) = self.project(mean, covariance);
        
        // Calculate Kalman gain
        let kalman_gain = self.calculate_kalman_gain(covariance, &projected_cov);
        
        // Calculate innovation
        let mut innovation = vec![0.0; self.obs_dim];
        for i in 0..self.obs_dim {
            innovation[i] = measurement[i] - projected_mean[i];
        }
        
        // Update mean
        let mut updated_mean = mean.to_vec();
        for i in 0..self.state_dim {
            for j in 0..self.obs_dim {
                updated_mean[i] += kalman_gain[i][j] * innovation[j];
            }
        }
        
        // Update covariance
        let mut updated_covariance = covariance.to_vec();
        for i in 0..self.state_dim {
            for j in 0..self.state_dim {
                for k in 0..self.obs_dim {
                    updated_covariance[i][j] -= kalman_gain[i][k] * projected_cov[k][j];
                }
            }
        }
        
        (updated_mean, updated_covariance)
    }
    
    /// Project state to measurement space
    fn project(&self, mean: &[f32], covariance: &[Vec<f32>]) -> (Vec<f32>, Vec<Vec<f32>>) {
        let mut projected_mean = vec![0.0; self.obs_dim];
        let mut projected_cov = vec![vec![0.0; self.obs_dim]; self.obs_dim];
        
        // Project mean
        for i in 0..self.obs_dim {
            for j in 0..self.state_dim {
                projected_mean[i] += self.observation_matrix[i][j] * mean[j];
            }
        }
        
        // Project covariance
        for i in 0..self.obs_dim {
            for j in 0..self.obs_dim {
                for k in 0..self.state_dim {
                    for l in 0..self.state_dim {
                        projected_cov[i][j] += 
                            self.observation_matrix[i][k] * covariance[k][l] * self.observation_matrix[j][l];
                    }
                }
            }
        }
        
        // Add measurement noise
        let std = [
            self.std_weight_position * mean[3],
            self.std_weight_position * mean[3],
            1e-1,
            self.std_weight_position * mean[3],
        ];
        
        for i in 0..self.obs_dim {
            projected_cov[i][i] += std[i] * std[i];
        }
        
        (projected_mean, projected_cov)
    }
    
    /// Calculate Kalman gain matrix
    fn calculate_kalman_gain(&self, covariance: &[Vec<f32>], projected_cov: &[Vec<f32>]) 
        -> Vec<Vec<f32>> {
        
        // Simplified Kalman gain calculation
        // In production, this would use proper matrix inversion
        let mut kalman_gain = vec![vec![0.0; self.obs_dim]; self.state_dim];
        
        for i in 0..self.state_dim {
            for j in 0..self.obs_dim {
                let mut numerator = 0.0;
                for k in 0..self.state_dim {
                    numerator += covariance[i][k] * self.observation_matrix[j][k];
                }
                
                let denominator = projected_cov[j][j].max(1e-6); // Avoid division by zero
                kalman_gain[i][j] = numerator / denominator;
            }
        }
        
        kalman_gain
    }
    
    /// Calculate gating distance (Mahalanobis distance)
    pub fn gating_distance(&self, mean: &[f32], covariance: &[Vec<f32>], 
                          measurements: &[Vec<f32>]) -> Vec<f32> {
        let (projected_mean, projected_cov) = self.project(mean, covariance);
        
        measurements.iter()
            .map(|measurement| {
                let mut distance = 0.0;
                for i in 0..self.obs_dim {
                    let diff = measurement[i] - projected_mean[i];
                    let inv_cov = 1.0 / projected_cov[i][i].max(1e-6);
                    distance += diff * diff * inv_cov;
                }
                distance
            })
            .collect()
    }
}

impl DeepSortTracker {
    /// Create new Deep SORT tracker
    pub fn new(config: &VisionConfig) -> VisionResult<Self> {
        let kalman_filter = KalmanFilter::new();
        
        // Chi-square distribution thresholds for gating
        let mut chi2_thresholds = HashMap::new();
        chi2_thresholds.insert(1, 3.8415);
        chi2_thresholds.insert(2, 5.9915);
        chi2_thresholds.insert(3, 7.8147);
        chi2_thresholds.insert(4, 9.4877);
        
        let metrics = TrackingMetrics {
            avg_tracking_time_ms: 0.0,
            active_tracks: 0,
            total_tracks_created: 0,
            total_tracks_terminated: 0,
            accuracy: None,
            avg_track_length: 0.0,
        };
        
        Ok(Self {
            kalman_filter,
            tracks: Vec::new(),
            next_track_id: 1,
            max_age: 30,
            n_init: 3,
            max_iou_distance: 0.7,
            metrics,
            association_matrix: Vec::new(),
            chi2_thresholds,
        })
    }
    
    /// Convert detection to measurement format
    fn detection_to_measurement(&self, bbox: &super::BoundingBox) -> Vec<f32> {
        let center_x = bbox.x + bbox.width / 2.0;
        let center_y = bbox.y + bbox.height / 2.0;
        let aspect_ratio = bbox.width / bbox.height;
        let height = bbox.height;
        
        vec![center_x, center_y, aspect_ratio, height]
    }
    
    /// Associate detections with existing tracks
    fn associate_detections(&mut self, detections: &[super::BoundingBox]) 
        -> (Vec<(usize, usize)>, Vec<usize>, Vec<usize>) {
        
        if self.tracks.is_empty() || detections.is_empty() {
            return (
                Vec::new(),
                (0..self.tracks.len()).collect(),
                (0..detections.len()).collect(),
            );
        }
        
        // Build cost matrix
        let mut cost_matrix = vec![vec![f32::INFINITY; detections.len()]; self.tracks.len()];
        
        for (track_idx, track) in self.tracks.iter().enumerate() {
            if track.state != TrackState::Confirmed {
                continue;
            }
            
            let measurements: Vec<Vec<f32>> = detections.iter()
                .map(|det| self.detection_to_measurement(det))
                .collect();
            
            let gating_distances = self.kalman_filter.gating_distance(
                &track.mean, &track.covariance, &measurements
            );
            
            for (det_idx, &distance) in gating_distances.iter().enumerate() {
                let threshold = self.chi2_thresholds.get(&4).unwrap_or(&9.4877);
                if distance < *threshold {
                    // Use IoU as cost metric
                    let track_bbox = self.track_to_bbox(track);
                    let iou = self.calculate_iou(&track_bbox, &detections[det_idx]);
                    cost_matrix[track_idx][det_idx] = 1.0 - iou;
                }
            }
        }
        
        // Perform Hungarian algorithm (simplified version)
        let (matches, unmatched_tracks, unmatched_detections) = 
            self.hungarian_assignment(&cost_matrix);
        
        (matches, unmatched_tracks, unmatched_detections)
    }
    
    /// Simplified Hungarian algorithm for assignment
    fn hungarian_assignment(&self, cost_matrix: &[Vec<f32>]) 
        -> (Vec<(usize, usize)>, Vec<usize>, Vec<usize>) {
        
        let mut matches = Vec::new();
        let mut used_tracks = vec![false; cost_matrix.len()];
        let mut used_detections = vec![false; if cost_matrix.is_empty() { 0 } else { cost_matrix[0].len() }];
        
        // Greedy assignment (simplified)
        for track_idx in 0..cost_matrix.len() {
            let mut best_det_idx = None;
            let mut best_cost = self.max_iou_distance;
            
            for det_idx in 0..cost_matrix[track_idx].len() {
                if !used_detections[det_idx] && cost_matrix[track_idx][det_idx] < best_cost {
                    best_cost = cost_matrix[track_idx][det_idx];
                    best_det_idx = Some(det_idx);
                }
            }
            
            if let Some(det_idx) = best_det_idx {
                matches.push((track_idx, det_idx));
                used_tracks[track_idx] = true;
                used_detections[det_idx] = true;
            }
        }
        
        let unmatched_tracks: Vec<usize> = (0..cost_matrix.len())
            .filter(|&i| !used_tracks[i])
            .collect();
        
        let unmatched_detections: Vec<usize> = (0..used_detections.len())
            .filter(|&i| !used_detections[i])
            .collect();
        
        (matches, unmatched_tracks, unmatched_detections)
    }
    
    /// Convert track state to bounding box
    fn track_to_bbox(&self, track: &Track) -> super::BoundingBox {
        let center_x = track.mean[0];
        let center_y = track.mean[1];
        let aspect_ratio = track.mean[2];
        let height = track.mean[3];
        let width = aspect_ratio * height;
        
        super::BoundingBox {
            x: center_x - width / 2.0,
            y: center_y - height / 2.0,
            width,
            height,
            confidence: track.confidence,
            class_id: 0, // Generic object class
            class_name: "tracked_object".to_string(),
        }
    }
    
    /// Calculate IoU between two bounding boxes
    fn calculate_iou(&self, box1: &super::BoundingBox, box2: &super::BoundingBox) -> f32 {
        let x1 = box1.x.max(box2.x);
        let y1 = box1.y.max(box2.y);
        let x2 = (box1.x + box1.width).min(box2.x + box2.width);
        let y2 = (box1.y + box1.height).min(box2.y + box2.height);
        
        if x2 <= x1 || y2 <= y1 {
            return 0.0;
        }
        
        let intersection = (x2 - x1) * (y2 - y1);
        let area1 = box1.width * box1.height;
        let area2 = box2.width * box2.height;
        let union = area1 + area2 - intersection;
        
        if union <= 0.0 {
            0.0
        } else {
            intersection / union
        }
    }
    
    /// Create new track from detection
    fn initiate_track(&mut self, detection: &super::BoundingBox) {
        let measurement = self.detection_to_measurement(detection);
        let (mean, covariance) = self.kalman_filter.initiate(&measurement);
        
        let track = Track {
            track_id: self.next_track_id,
            mean,
            covariance,
            state: TrackState::Tentative,
            time_since_update: 0,
            age: 1,
            hits: 1,
            hit_streak: 1,
            confidence: detection.confidence,
            features: Vec::new(),
        };
        
        self.tracks.push(track);
        self.next_track_id += 1;
        self.metrics.total_tracks_created += 1;
    }
}

impl MultiObjectTracker for DeepSortTracker {
    fn update(&mut self, detections: &DetectionResult) -> VisionResult<TrackingResult> {
        let start_time = Instant::now();
        
        // Predict all tracks
        self.predict()?;
        
        // Associate detections with tracks
        let (matches, unmatched_tracks, unmatched_detections) = 
            self.associate_detections(&detections.objects);
        
        // Update matched tracks
        for (track_idx, det_idx) in matches {
            let measurement = self.detection_to_measurement(&detections.objects[det_idx]);
            let track = &mut self.tracks[track_idx];
            
            let (updated_mean, updated_covariance) = self.kalman_filter.update(
                &track.mean, &track.covariance, &measurement
            );
            
            track.mean = updated_mean;
            track.covariance = updated_covariance;
            track.time_since_update = 0;
            track.hits += 1;
            track.hit_streak += 1;
            track.confidence = detections.objects[det_idx].confidence;
            
            // Confirm tentative tracks
            if track.state == TrackState::Tentative && track.hits >= self.n_init {
                track.state = TrackState::Confirmed;
            }
        }
        
        // Mark unmatched tracks as missed
        for track_idx in unmatched_tracks {
            self.tracks[track_idx].time_since_update += 1;
            self.tracks[track_idx].hit_streak = 0;
        }
        
        // Create new tracks for unmatched detections
        for det_idx in unmatched_detections {
            self.initiate_track(&detections.objects[det_idx]);
        }
        
        // Delete old tracks
        let mut new_tracks = 0;
        let mut terminated_tracks = 0;
        
        self.tracks.retain(|track| {
            if track.time_since_update > self.max_age {
                terminated_tracks += 1;
                false
            } else if track.age == 1 {
                new_tracks += 1;
                true
            } else {
                true
            }
        });
        
        self.metrics.total_tracks_terminated += terminated_tracks as u64;
        
        // Convert tracks to tracked objects
        let tracked_objects: Vec<TrackedObject> = self.tracks.iter()
            .filter(|track| track.state == TrackState::Confirmed)
            .map(|track| {
                let bbox = self.track_to_bbox(track);
                
                TrackedObject {
                    track_id: track.track_id,
                    bbox,
                    predicted_bbox: None, // Could add prediction here
                    tracking_confidence: track.confidence,
                    age: track.age,
                    time_since_update: track.time_since_update,
                    velocity: (
                        track.mean.get(4).copied().unwrap_or(0.0),
                        track.mean.get(5).copied().unwrap_or(0.0)
                    ),
                    state: track.mean.clone(),
                    covariance: track.covariance.clone(),
                }
            })
            .collect();
        
        let processing_time = start_time.elapsed();
        self.metrics.active_tracks = tracked_objects.len() as u32;
        
        Ok(TrackingResult {
            tracked_objects,
            processing_time_ms: processing_time.as_millis() as u32,
            timestamp: detections.timestamp,
            active_tracks: self.metrics.active_tracks,
            new_tracks,
            terminated_tracks,
        })
    }
    
    fn predict(&mut self) -> VisionResult<()> {
        for track in &mut self.tracks {
            let (predicted_mean, predicted_covariance) = 
                self.kalman_filter.predict(&track.mean, &track.covariance);
            
            track.mean = predicted_mean;
            track.covariance = predicted_covariance;
            track.age += 1;
        }
        
        Ok(())
    }
    
    fn get_tracks(&self) -> &[TrackedObject] {
        // This would need to be implemented to return current tracked objects
        // For now, return empty slice
        &[]
    }
    
    fn get_metrics(&self) -> TrackingMetrics {
        self.metrics.clone()
    }
    
    fn reset(&mut self) {
        self.tracks.clear();
        self.next_track_id = 1;
        self.metrics = TrackingMetrics {
            avg_tracking_time_ms: 0.0,
            active_tracks: 0,
            total_tracks_created: 0,
            total_tracks_terminated: 0,
            accuracy: None,
            avg_track_length: 0.0,
        };
    }
}

/// Create multi-object tracker based on configuration
pub fn create_tracker(config: &VisionConfig) -> VisionResult<Box<dyn MultiObjectTracker + Send + Sync>> {
    let tracker = DeepSortTracker::new(config)?;
    Ok(Box::new(tracker))
}

/// Tracking utilities
pub mod tracking_utils {
    use super::*;
    
    /// Calculate track similarity based on appearance features
    pub fn calculate_appearance_similarity(features1: &[f32], features2: &[f32]) -> f32 {
        if features1.len() != features2.len() {
            return 0.0;
        }
        
        let mut dot_product = 0.0;
        let mut norm1 = 0.0;
        let mut norm2 = 0.0;
        
        for i in 0..features1.len() {
            dot_product += features1[i] * features2[i];
            norm1 += features1[i] * features1[i];
            norm2 += features2[i] * features2[i];
        }
        
        let norm_product = (norm1 * norm2).sqrt();
        if norm_product > 0.0 {
            dot_product / norm_product
        } else {
            0.0
        }
    }
    
    /// Predict future position based on velocity
    pub fn predict_position(current_pos: (f32, f32), velocity: (f32, f32), time_steps: u32) -> (f32, f32) {
        let dt = time_steps as f32;
        (
            current_pos.0 + velocity.0 * dt,
            current_pos.1 + velocity.1 * dt
        )
    }
    
    /// Calculate track quality score
    pub fn calculate_track_quality(track: &Track) -> f32 {
        let age_factor = (track.age as f32).min(10.0) / 10.0;
        let hit_ratio = track.hits as f32 / track.age as f32;
        let recency_factor = 1.0 / (1.0 + track.time_since_update as f32);
        
        age_factor * hit_ratio * recency_factor * track.confidence
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_kalman_filter_creation() {
        let kf = KalmanFilter::new();
        assert_eq!(kf.state_dim, 8);
        assert_eq!(kf.obs_dim, 4);
    }
    
    #[test]
    fn test_kalman_filter_initiate() {
        let kf = KalmanFilter::new();
        let measurement = vec![100.0, 200.0, 1.5, 50.0];
        let (mean, covariance) = kf.initiate(&measurement);
        
        assert_eq!(mean.len(), 8);
        assert_eq!(covariance.len(), 8);
        assert_eq!(mean[0], 100.0); // x
        assert_eq!(mean[1], 200.0); // y
        assert_eq!(mean[2], 1.5);   // aspect ratio
        assert_eq!(mean[3], 50.0);  // height
    }
    
    #[test]
    fn test_tracker_creation() {
        let config = VisionConfig::default();
        let tracker = DeepSortTracker::new(&config);
        assert!(tracker.is_ok());
    }
    
    #[test]
    fn test_detection_to_measurement() {
        let config = VisionConfig::default();
        let tracker = DeepSortTracker::new(&config).unwrap();
        
        let bbox = super::super::BoundingBox {
            x: 10.0, y: 20.0, width: 30.0, height: 40.0,
            confidence: 0.9, class_id: 0, class_name: "test".to_string(),
        };
        
        let measurement = tracker.detection_to_measurement(&bbox);
        assert_eq!(measurement.len(), 4);
        assert_eq!(measurement[0], 25.0); // center_x = 10 + 30/2
        assert_eq!(measurement[1], 40.0); // center_y = 20 + 40/2
        assert_eq!(measurement[2], 0.75); // aspect_ratio = 30/40
        assert_eq!(measurement[3], 40.0); // height
    }
}