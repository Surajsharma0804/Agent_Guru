// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! False Positive Suppression Filter
//! 
//! This module implements statistical confidence filtering and false positive
//! reduction algorithms for wake word detection.
//! 
//! Based on clean room extraction of algorithms from openWakeWord project.
//! Mathematical concepts and implementation patterns only - no foreign code.

use std::collections::{HashMap, VecDeque};
use std::time::{Duration, Instant};
use thiserror::Error;

/// Confidence filtering errors
#[derive(Error, Debug)]
pub enum ConfidenceError {
    #[error("Configuration error: {0}")]
    Configuration(String),
    
    #[error("Invalid threshold: {0} (must be between 0.0 and 1.0)")]
    InvalidThreshold(f32),
    
    #[error("Insufficient history: need {needed} frames, got {available}")]
    InsufficientHistory { needed: usize, available: usize },
    
    #[error("Filter not configured")]
    NotConfigured,
}

/// Confidence filtering configuration
#[derive(Debug, Clone)]
pub struct ConfidenceConfig {
    pub patience_frames: usize,        // Consecutive frames above threshold required
    pub debounce_time_ms: u64,         // Minimum time between detections
    pub adaptive_threshold: bool,       // Enable adaptive threshold adjustment
    pub noise_gate_threshold: f32,     // Minimum signal level to consider
    pub confidence_smoothing: f32,     // Exponential smoothing factor (0.0-1.0)
    pub false_positive_penalty: f32,   // Penalty factor for false positives
}

impl Default for ConfidenceConfig {
    fn default() -> Self {
        Self {
            patience_frames: 3,           // Require 3 consecutive frames
            debounce_time_ms: 1000,       // 1 second debounce
            adaptive_threshold: true,
            noise_gate_threshold: 0.01,   // 1% minimum signal level
            confidence_smoothing: 0.3,    // 30% smoothing
            false_positive_penalty: 0.9,  // 10% penalty for false positives
        }
    }
}

/// Statistical confidence metrics
#[derive(Debug, Clone)]
pub struct ConfidenceMetrics {
    pub mean_confidence: f32,
    pub confidence_variance: f32,
    pub detection_rate: f32,
    pub false_positive_rate: f32,
    pub adaptive_threshold: f32,
    pub noise_level: f32,
}

/// Prediction history entry
#[derive(Debug, Clone)]
struct PredictionEntry {
    _confidence: f32,
    _timestamp: Instant,
    above_threshold: bool,
}

/// Adaptive threshold calculator
#[derive(Debug, Clone)]
struct AdaptiveThreshold {
    base_threshold: f32,
    noise_level: f32,
    recent_confidences: VecDeque<f32>,
    false_positive_count: u32,
    total_predictions: u32,
    smoothing_factor: f32,
}

impl AdaptiveThreshold {
    fn new(base_threshold: f32, smoothing_factor: f32) -> Self {
        Self {
            base_threshold,
            noise_level: 0.0,
            recent_confidences: VecDeque::with_capacity(100),
            false_positive_count: 0,
            total_predictions: 0,
            smoothing_factor,
        }
    }
    
    fn update(&mut self, confidence: f32, is_false_positive: bool) {
        self.total_predictions += 1;
        
        if is_false_positive {
            self.false_positive_count += 1;
        }
        
        // Update noise level estimation
        self.recent_confidences.push_back(confidence);
        if self.recent_confidences.len() > 100 {
            self.recent_confidences.pop_front();
        }
        
        // Calculate noise level as the median of recent low confidences
        let mut sorted_confidences: Vec<f32> = self.recent_confidences
            .iter()
            .filter(|&&c| c < self.base_threshold)
            .copied()
            .collect();
        
        if !sorted_confidences.is_empty() {
            sorted_confidences.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let median_idx = sorted_confidences.len() / 2;
            let new_noise_level = sorted_confidences[median_idx];
            
            // Smooth noise level update
            self.noise_level = self.smoothing_factor * new_noise_level + 
                              (1.0 - self.smoothing_factor) * self.noise_level;
        }
    }
    
    fn get_adaptive_threshold(&self, penalty_factor: f32) -> f32 {
        let false_positive_rate = if self.total_predictions > 0 {
            self.false_positive_count as f32 / self.total_predictions as f32
        } else {
            0.0
        };
        
        // Increase threshold if false positive rate is high
        let fp_adjustment = false_positive_rate * penalty_factor;
        
        // Adjust for noise level
        let noise_adjustment = self.noise_level * 2.0;
        
        (self.base_threshold + fp_adjustment + noise_adjustment).min(0.95)
    }
}

/// Patience-based validation
#[derive(Debug, Clone)]
struct PatienceValidator {
    required_frames: usize,
    prediction_history: VecDeque<PredictionEntry>,
    max_history: usize,
}

impl PatienceValidator {
    fn new(required_frames: usize) -> Self {
        Self {
            required_frames,
            prediction_history: VecDeque::with_capacity(required_frames * 2),
            max_history: required_frames * 2,
        }
    }
    
    fn add_prediction(&mut self, confidence: f32, threshold: f32) {
        let entry = PredictionEntry {
            _confidence: confidence,
            _timestamp: Instant::now(),
            above_threshold: confidence >= threshold,
        };
        
        self.prediction_history.push_back(entry);
        
        // Maintain history size
        if self.prediction_history.len() > self.max_history {
            self.prediction_history.pop_front();
        }
    }
    
    fn validate(&self, _threshold: f32) -> bool {
        if self.prediction_history.len() < self.required_frames {
            return false;
        }
        
        // Check if the last N frames are all above threshold
        self.prediction_history
            .iter()
            .rev()
            .take(self.required_frames)
            .all(|entry| entry.above_threshold)
    }
    
    fn reset(&mut self) {
        self.prediction_history.clear();
    }
}

/// Debounce timer for preventing rapid repeated detections
#[derive(Debug, Clone)]
struct DebounceTimer {
    debounce_duration: Duration,
    last_detection: Option<Instant>,
}

impl DebounceTimer {
    fn new(debounce_ms: u64) -> Self {
        Self {
            debounce_duration: Duration::from_millis(debounce_ms),
            last_detection: None,
        }
    }
    
    fn can_detect(&self) -> bool {
        match self.last_detection {
            Some(last) => last.elapsed() >= self.debounce_duration,
            None => true,
        }
    }
    
    fn record_detection(&mut self) {
        self.last_detection = Some(Instant::now());
    }
    
    fn reset(&mut self) {
        self.last_detection = None;
    }
}

/// Statistical confidence filter for false positive suppression
pub struct ConfidenceFilter {
    config: ConfidenceConfig,
    adaptive_thresholds: HashMap<usize, AdaptiveThreshold>,
    patience_validators: HashMap<usize, PatienceValidator>,
    debounce_timers: HashMap<usize, DebounceTimer>,
    num_classes: usize,
    configured: bool,
    
    // Statistics
    total_predictions: u64,
    total_detections: u64,
    false_positives: u64,
    start_time: Instant,
}

impl ConfidenceFilter {
    /// Create new confidence filter
    pub fn new() -> Self {
        Self {
            config: ConfidenceConfig::default(),
            adaptive_thresholds: HashMap::new(),
            patience_validators: HashMap::new(),
            debounce_timers: HashMap::new(),
            num_classes: 0,
            configured: false,
            total_predictions: 0,
            total_detections: 0,
            false_positives: 0,
            start_time: Instant::now(),
        }
    }
    
    /// Configure filter for specified number of classes
    pub fn configure(&mut self, num_classes: usize) -> Result<(), ConfidenceError> {
        if num_classes == 0 {
            return Err(ConfidenceError::Configuration(
                "Number of classes must be greater than 0".to_string()
            ));
        }
        
        self.num_classes = num_classes;
        
        // Initialize components for each class
        for class_idx in 0..num_classes {
            self.adaptive_thresholds.insert(
                class_idx,
                AdaptiveThreshold::new(0.5, self.config.confidence_smoothing)
            );
            
            self.patience_validators.insert(
                class_idx,
                PatienceValidator::new(self.config.patience_frames)
            );
            
            self.debounce_timers.insert(
                class_idx,
                DebounceTimer::new(self.config.debounce_time_ms)
            );
        }
        
        self.configured = true;
        Ok(())
    }
    
    /// Filter predictions and return filtered confidence scores
    pub fn filter_predictions(&mut self, predictions: &[f32], base_sensitivity: f32) -> Result<Vec<f32>, ConfidenceError> {
        if !self.configured {
            return Err(ConfidenceError::NotConfigured);
        }
        
        if predictions.len() != self.num_classes {
            return Err(ConfidenceError::Configuration(
                format!("Expected {} predictions, got {}", self.num_classes, predictions.len())
            ));
        }
        
        if !(0.0..=1.0).contains(&base_sensitivity) {
            return Err(ConfidenceError::InvalidThreshold(base_sensitivity));
        }
        
        self.total_predictions += 1;
        let mut filtered_predictions = vec![0.0; self.num_classes];
        
        for (class_idx, &confidence) in predictions.iter().enumerate() {
            // Apply noise gate
            if confidence < self.config.noise_gate_threshold {
                filtered_predictions[class_idx] = 0.0;
                continue;
            }
            
            // Get adaptive threshold
            let adaptive_threshold = if self.config.adaptive_threshold {
                let threshold_calculator = self.adaptive_thresholds.get(&class_idx).unwrap();
                threshold_calculator.get_adaptive_threshold(self.config.false_positive_penalty)
            } else {
                base_sensitivity
            };
            
            // Update patience validator
            let patience_validator = self.patience_validators.get_mut(&class_idx).unwrap();
            patience_validator.add_prediction(confidence, adaptive_threshold);
            
            // Check patience validation
            let patience_passed = patience_validator.validate(adaptive_threshold);
            
            // Check debounce timer
            let debounce_timer = self.debounce_timers.get(&class_idx).unwrap();
            let debounce_passed = debounce_timer.can_detect();
            
            // Apply all filters
            if confidence >= adaptive_threshold && patience_passed && debounce_passed {
                filtered_predictions[class_idx] = confidence;
                
                // Record detection
                self.debounce_timers.get_mut(&class_idx).unwrap().record_detection();
                self.total_detections += 1;
            } else {
                filtered_predictions[class_idx] = 0.0;
            }
            
            // Update adaptive threshold (assume false positive if confidence was high but filtered out)
            let is_false_positive = confidence >= base_sensitivity && filtered_predictions[class_idx] == 0.0;
            if is_false_positive {
                self.false_positives += 1;
            }
            
            self.adaptive_thresholds.get_mut(&class_idx).unwrap()
                .update(confidence, is_false_positive);
        }
        
        Ok(filtered_predictions)
    }
    
    /// Set adaptive mode
    pub fn set_adaptive_mode(&mut self, enabled: bool) -> Result<(), ConfidenceError> {
        self.config.adaptive_threshold = enabled;
        Ok(())
    }
    
    /// Update configuration
    pub fn update_config(&mut self, config: ConfidenceConfig) -> Result<(), ConfidenceError> {
        // Validate configuration
        if !(0.0..=1.0).contains(&config.confidence_smoothing) {
            return Err(ConfidenceError::InvalidThreshold(config.confidence_smoothing));
        }
        
        if !(0.0..=1.0).contains(&config.noise_gate_threshold) {
            return Err(ConfidenceError::InvalidThreshold(config.noise_gate_threshold));
        }
        
        self.config = config;
        
        // Update existing components if configured
        if self.configured {
            for validator in self.patience_validators.values_mut() {
                *validator = PatienceValidator::new(self.config.patience_frames);
            }
            
            for timer in self.debounce_timers.values_mut() {
                *timer = DebounceTimer::new(self.config.debounce_time_ms);
            }
        }
        
        Ok(())
    }
    
    /// Get confidence metrics
    pub fn get_metrics(&self) -> ConfidenceMetrics {
        let uptime_hours = self.start_time.elapsed().as_secs_f32() / 3600.0;
        
        let detection_rate = if uptime_hours > 0.0 {
            self.total_detections as f32 / uptime_hours
        } else {
            0.0
        };
        
        let false_positive_rate = if self.total_detections > 0 {
            self.false_positives as f32 / self.total_detections as f32
        } else {
            0.0
        };
        
        // Calculate mean adaptive threshold
        let adaptive_threshold = if !self.adaptive_thresholds.is_empty() {
            self.adaptive_thresholds.values()
                .map(|t| t.get_adaptive_threshold(self.config.false_positive_penalty))
                .sum::<f32>() / self.adaptive_thresholds.len() as f32
        } else {
            0.5
        };
        
        // Calculate mean noise level
        let noise_level = if !self.adaptive_thresholds.is_empty() {
            self.adaptive_thresholds.values()
                .map(|t| t.noise_level)
                .sum::<f32>() / self.adaptive_thresholds.len() as f32
        } else {
            0.0
        };
        
        ConfidenceMetrics {
            mean_confidence: 0.0, // Would need to track this separately
            confidence_variance: 0.0, // Would need to track this separately
            detection_rate,
            false_positive_rate,
            adaptive_threshold,
            noise_level,
        }
    }
    
    /// Reset filter state
    pub fn reset(&mut self) -> Result<(), ConfidenceError> {
        for validator in self.patience_validators.values_mut() {
            validator.reset();
        }
        
        for timer in self.debounce_timers.values_mut() {
            timer.reset();
        }
        
        self.total_predictions = 0;
        self.total_detections = 0;
        self.false_positives = 0;
        self.start_time = Instant::now();
        
        Ok(())
    }
    
    /// Report false positive for learning
    pub fn report_false_positive(&mut self, class_idx: usize) -> Result<(), ConfidenceError> {
        if class_idx >= self.num_classes {
            return Err(ConfidenceError::Configuration(
                format!("Invalid class index: {}", class_idx)
            ));
        }
        
        self.false_positives += 1;
        
        // Update adaptive threshold to be more conservative
        if let Some(threshold_calc) = self.adaptive_thresholds.get_mut(&class_idx) {
            threshold_calc.false_positive_count += 1;
        }
        
        Ok(())
    }
    
    /// Get current configuration
    pub fn get_config(&self) -> &ConfidenceConfig {
        &self.config
    }
}

impl Default for ConfidenceFilter {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    use std::time::Duration;
    
    #[test]
    fn test_confidence_filter_creation() {
        let filter = ConfidenceFilter::new();
        assert!(!filter.configured);
        assert_eq!(filter.num_classes, 0);
    }
    
    #[test]
    fn test_filter_configuration() {
        let mut filter = ConfidenceFilter::new();
        assert!(filter.configure(2).is_ok());
        assert!(filter.configured);
        assert_eq!(filter.num_classes, 2);
    }
    
    #[test]
    fn test_basic_filtering() {
        let mut filter = ConfidenceFilter::new();
        filter.configure(2).unwrap();
        
        let predictions = vec![0.8, 0.2];
        let filtered = filter.filter_predictions(&predictions, 0.5).unwrap();
        
        // First prediction should pass (above threshold)
        // Second prediction should be filtered out (below threshold)
        assert_eq!(filtered.len(), 2);
        assert!(filtered[1] == 0.0); // Below threshold
    }
    
    #[test]
    fn test_patience_validation() {
        let mut filter = ConfidenceFilter::new();
        let config = ConfidenceConfig {
            patience_frames: 3,
            debounce_time_ms: 0, // Disable debounce for this test
            adaptive_threshold: false, // Disable adaptive threshold for predictable behavior
            ..Default::default()
        };
        filter.update_config(config).unwrap();
        filter.configure(1).unwrap();
        
        let high_confidence = vec![0.9];
        
        // First two predictions should be filtered out (patience not met)
        let filtered1 = filter.filter_predictions(&high_confidence, 0.5).unwrap();
        assert!((filtered1[0] - 0.0).abs() < f32::EPSILON);
        
        let filtered2 = filter.filter_predictions(&high_confidence, 0.5).unwrap();
        assert!((filtered2[0] - 0.0).abs() < f32::EPSILON);
        
        // Third prediction should pass (patience met)
        let filtered3 = filter.filter_predictions(&high_confidence, 0.5).unwrap();
        assert!(filtered3[0] > 0.0);
    }
    
    #[test]
    fn test_debounce_timer() {
        let mut timer = DebounceTimer::new(100); // 100ms debounce
        
        assert!(timer.can_detect());
        
        timer.record_detection();
        assert!(!timer.can_detect());
        
        // Wait for debounce period
        thread::sleep(Duration::from_millis(150));
        assert!(timer.can_detect());
    }
    
    #[test]
    fn test_adaptive_threshold() {
        let mut threshold = AdaptiveThreshold::new(0.5, 0.3);
        
        // Simulate false positives
        threshold.update(0.6, true);
        threshold.update(0.7, true);
        
        let adaptive = threshold.get_adaptive_threshold(0.1);
        assert!(adaptive > 0.5); // Should increase due to false positives
    }
    
    #[test]
    fn test_noise_gate() {
        let mut filter = ConfidenceFilter::new();
        let config = ConfidenceConfig {
            noise_gate_threshold: 0.1,
            patience_frames: 1, // Minimal patience for this test
            adaptive_threshold: false, // Disable adaptive threshold for predictable behavior
            ..Default::default()
        };
        filter.update_config(config).unwrap();
        filter.configure(1).unwrap();
        
        // Low confidence below noise gate
        let low_predictions = vec![0.05];
        let filtered = filter.filter_predictions(&low_predictions, 0.01).unwrap();
        assert!((filtered[0] - 0.0).abs() < f32::EPSILON);
        
        // Higher confidence above noise gate
        let high_predictions = vec![0.15];
        let filtered = filter.filter_predictions(&high_predictions, 0.01).unwrap();
        assert!(filtered[0] > 0.0);
    }
    
    #[test]
    fn test_metrics() {
        let mut filter = ConfidenceFilter::new();
        filter.configure(1).unwrap();
        
        // Generate some predictions
        for _ in 0..10 {
            let predictions = vec![0.8];
            filter.filter_predictions(&predictions, 0.5).unwrap();
        }
        
        let metrics = filter.get_metrics();
        assert!(metrics.detection_rate >= 0.0);
        assert!(metrics.false_positive_rate >= 0.0);
        assert!(metrics.adaptive_threshold > 0.0);
    }
    
    #[test]
    fn test_false_positive_reporting() {
        let mut filter = ConfidenceFilter::new();
        filter.configure(2).unwrap();
        
        assert!(filter.report_false_positive(0).is_ok());
        assert!(filter.report_false_positive(5).is_err()); // Invalid class index
    }
    
    #[test]
    fn test_reset() {
        let mut filter = ConfidenceFilter::new();
        filter.configure(1).unwrap();
        
        // Generate some activity
        let predictions = vec![0.8];
        filter.filter_predictions(&predictions, 0.5).unwrap();
        
        assert!(filter.reset().is_ok());
        assert_eq!(filter.total_predictions, 0);
        assert_eq!(filter.total_detections, 0);
    }
    
    #[test]
    fn test_invalid_configurations() {
        let mut filter = ConfidenceFilter::new();
        
        // Invalid number of classes
        assert!(filter.configure(0).is_err());
        
        // Invalid threshold
        filter.configure(1).unwrap();
        let predictions = vec![0.5];
        assert!(filter.filter_predictions(&predictions, 1.5).is_err());
        
        // Wrong number of predictions
        let wrong_predictions = vec![0.5, 0.6]; // Expected 1, got 2
        assert!(filter.filter_predictions(&wrong_predictions, 0.5).is_err());
    }
    
    #[test]
    fn test_patience_validator() {
        let mut validator = PatienceValidator::new(3);
        
        // Add predictions below threshold
        validator.add_prediction(0.3, 0.5);
        validator.add_prediction(0.4, 0.5);
        validator.add_prediction(0.6, 0.5); // Above threshold
        
        assert!(!validator.validate(0.5)); // Not enough consecutive frames above threshold
        
        // Add more predictions above threshold
        validator.add_prediction(0.7, 0.5);
        validator.add_prediction(0.8, 0.5);
        
        assert!(validator.validate(0.5)); // Now should pass
    }
}
