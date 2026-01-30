// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! Wake Word Engine Module
//! 
//! This module provides real-time wake word detection capabilities with:
//! - MFCC-based audio feature extraction
//! - Neural network inference for wake word classification
//! - Lock-free ring buffer for continuous audio streaming
//! - Statistical false positive suppression
//! - Adaptive sensitivity adjustment
//! 
//! Performance Requirements:
//! - Wake word detection latency: ≤50ms (99.9th percentile)
//! - CPU utilization during idle: <1% (continuous monitoring)
//! - Memory footprint: <50MB including models
//! - False positive rate: <1 per 24 hours of operation
//! - Audio processing latency: <10ms per frame

pub mod audio_features;
pub mod neural_gate;
pub mod ring_buffer;
pub mod false_positive_filter;

pub use audio_features::MFCCExtractor;
pub use neural_gate::NeuralClassifier;
pub use ring_buffer::AudioRingBuffer;
pub use false_positive_filter::ConfidenceFilter;

use std::time::{Duration, Instant};
use thiserror::Error;

/// Wake word detection errors
#[derive(Error, Debug)]
pub enum WakeWordError {
    #[error("Audio processing error: {0}")]
    AudioProcessing(String),
    
    #[error("Neural network inference error: {0}")]
    NeuralInference(String),
    
    #[error("Buffer overflow: {0}")]
    BufferOverflow(String),
    
    #[error("Configuration error: {0}")]
    Configuration(String),
    
    #[error("Performance constraint violation: {0}")]
    PerformanceViolation(String),
}

/// Wake word detection event
#[derive(Debug, Clone)]
pub struct WakeWordEvent {
    pub wake_word: String,
    pub confidence: f32,
    pub timestamp: Instant,
    pub detection_latency: Duration,
    pub audio_features: Vec<f32>,
}

/// Performance metrics for wake word engine
#[derive(Debug, Clone)]
pub struct WakeWordMetrics {
    pub detection_latency_ms: f32,
    pub cpu_utilization_percent: f32,
    pub memory_usage_mb: f32,
    pub false_positive_rate: f32,
    pub audio_processing_latency_ms: f32,
    pub total_detections: u64,
    pub false_positives: u64,
    pub uptime_hours: f32,
}

/// Wake word engine trait for production-grade implementations
pub trait WakeWordEngine {
    /// Initialize the wake word engine with specified wake words
    fn initialize(&mut self, wake_words: &[String]) -> Result<(), WakeWordError>;
    
    /// Process incoming audio stream and return detection events
    fn process_audio_stream(&mut self, audio_buffer: &[f32]) -> Result<Option<WakeWordEvent>, WakeWordError>;
    
    /// Adjust detection sensitivity (0.0 = least sensitive, 1.0 = most sensitive)
    fn set_sensitivity(&mut self, sensitivity: f32) -> Result<(), WakeWordError>;
    
    /// Get current performance metrics
    fn get_performance_metrics(&self) -> WakeWordMetrics;
    
    /// Reset internal state and buffers
    fn reset(&mut self) -> Result<(), WakeWordError>;
    
    /// Enable/disable adaptive sensitivity based on noise levels
    fn set_adaptive_sensitivity(&mut self, enabled: bool) -> Result<(), WakeWordError>;
}

/// Production-grade MFCC-based wake word engine
pub struct MFCCWakeWordEngine {
    feature_extractor: MFCCExtractor,
    neural_classifier: NeuralClassifier,
    ring_buffer: AudioRingBuffer,
    confidence_filter: ConfidenceFilter,
    
    // Configuration
    wake_words: Vec<String>,
    sensitivity: f32,
    adaptive_sensitivity: bool,
    
    // Performance tracking
    metrics: WakeWordMetrics,
    start_time: Instant,
    last_detection: Option<Instant>,
    
    // State management
    initialized: bool,
    processing_times: Vec<Duration>,
}

impl MFCCWakeWordEngine {
    /// Create a new MFCC-based wake word engine
    pub fn new() -> Self {
        Self {
            feature_extractor: MFCCExtractor::new(),
            neural_classifier: NeuralClassifier::new(),
            ring_buffer: AudioRingBuffer::new(16000 * 10), // 10 seconds buffer
            confidence_filter: ConfidenceFilter::new(),
            
            wake_words: Vec::new(),
            sensitivity: 0.5,
            adaptive_sensitivity: true,
            
            metrics: WakeWordMetrics {
                detection_latency_ms: 0.0,
                cpu_utilization_percent: 0.0,
                memory_usage_mb: 0.0,
                false_positive_rate: 0.0,
                audio_processing_latency_ms: 0.0,
                total_detections: 0,
                false_positives: 0,
                uptime_hours: 0.0,
            },
            start_time: Instant::now(),
            last_detection: None,
            
            initialized: false,
            processing_times: Vec::with_capacity(1000),
        }
    }
    
    /// Update performance metrics
    fn update_metrics(&mut self, processing_time: Duration) {
        self.processing_times.push(processing_time);
        
        // Keep only last 1000 measurements for rolling average
        if self.processing_times.len() > 1000 {
            self.processing_times.remove(0);
        }
        
        // Calculate average processing time
        let avg_processing_time: Duration = self.processing_times.iter().sum::<Duration>() / self.processing_times.len() as u32;
        self.metrics.audio_processing_latency_ms = avg_processing_time.as_secs_f32() * 1000.0;
        
        // Update uptime
        self.metrics.uptime_hours = self.start_time.elapsed().as_secs_f32() / 3600.0;
        
        // Calculate false positive rate (per 24 hours)
        if self.metrics.uptime_hours > 0.0 {
            self.metrics.false_positive_rate = (self.metrics.false_positives as f32) / (self.metrics.uptime_hours / 24.0);
        }
        
        // Estimate CPU utilization based on processing time vs real time
        let frame_duration = Duration::from_millis(80); // 80ms frames
        self.metrics.cpu_utilization_percent = (avg_processing_time.as_secs_f32() / frame_duration.as_secs_f32()) * 100.0;
        
        // Memory usage estimation (simplified)
        self.metrics.memory_usage_mb = 45.0; // Base model size + buffers
    }
    
    /// Validate performance constraints
    fn validate_performance(&self) -> Result<(), WakeWordError> {
        if self.metrics.detection_latency_ms > 50.0 {
            return Err(WakeWordError::PerformanceViolation(
                format!("Detection latency {}ms exceeds 50ms limit", self.metrics.detection_latency_ms)
            ));
        }
        
        if self.metrics.cpu_utilization_percent > 1.0 {
            return Err(WakeWordError::PerformanceViolation(
                format!("CPU utilization {}% exceeds 1% limit", self.metrics.cpu_utilization_percent)
            ));
        }
        
        if self.metrics.memory_usage_mb > 50.0 {
            return Err(WakeWordError::PerformanceViolation(
                format!("Memory usage {}MB exceeds 50MB limit", self.metrics.memory_usage_mb)
            ));
        }
        
        if self.metrics.audio_processing_latency_ms > 10.0 {
            return Err(WakeWordError::PerformanceViolation(
                format!("Audio processing latency {}ms exceeds 10ms limit", self.metrics.audio_processing_latency_ms)
            ));
        }
        
        Ok(())
    }
}

impl WakeWordEngine for MFCCWakeWordEngine {
    fn initialize(&mut self, wake_words: &[String]) -> Result<(), WakeWordError> {
        if wake_words.is_empty() {
            return Err(WakeWordError::Configuration("No wake words provided".to_string()));
        }
        
        // Initialize components
        self.feature_extractor.initialize()
            .map_err(|e| WakeWordError::AudioProcessing(e.to_string()))?;
        
        self.neural_classifier.load_models(wake_words)
            .map_err(|e| WakeWordError::NeuralInference(e.to_string()))?;
        
        self.confidence_filter.configure(wake_words.len())
            .map_err(|e| WakeWordError::Configuration(e.to_string()))?;
        
        self.wake_words = wake_words.to_vec();
        self.initialized = true;
        self.start_time = Instant::now();
        
        Ok(())
    }
    
    fn process_audio_stream(&mut self, audio_buffer: &[f32]) -> Result<Option<WakeWordEvent>, WakeWordError> {
        if !self.initialized {
            return Err(WakeWordError::Configuration("Engine not initialized".to_string()));
        }
        
        let start_time = Instant::now();
        
        // Add audio to ring buffer
        self.ring_buffer.write(audio_buffer)
            .map_err(|e| WakeWordError::BufferOverflow(e.to_string()))?;
        
        // Extract MFCC features
        let features = self.feature_extractor.extract_features(&self.ring_buffer)
            .map_err(|e| WakeWordError::AudioProcessing(e.to_string()))?;
        
        // Run neural network inference
        let predictions = self.neural_classifier.predict(&features)
            .map_err(|e| WakeWordError::NeuralInference(e.to_string()))?;
        
        // Apply confidence filtering
        let filtered_predictions = self.confidence_filter.filter_predictions(&predictions, self.sensitivity)
            .map_err(|e| WakeWordError::AudioProcessing(e.to_string()))?;
        
        let processing_time = start_time.elapsed();
        self.update_metrics(processing_time);
        
        // Validate performance constraints
        self.validate_performance()?;
        
        // Check for wake word detection
        if let Some((wake_word, confidence)) = filtered_predictions.iter()
            .enumerate()
            .find(|(_, &conf)| conf > self.sensitivity)
            .map(|(idx, &conf)| (self.wake_words[idx].clone(), conf))
        {
            let detection_latency = start_time.elapsed();
            self.metrics.total_detections += 1;
            self.metrics.detection_latency_ms = detection_latency.as_secs_f32() * 1000.0;
            self.last_detection = Some(Instant::now());
            
            Ok(Some(WakeWordEvent {
                wake_word,
                confidence,
                timestamp: Instant::now(),
                detection_latency,
                audio_features: features,
            }))
        } else {
            Ok(None)
        }
    }
    
    fn set_sensitivity(&mut self, sensitivity: f32) -> Result<(), WakeWordError> {
        if !(0.0..=1.0).contains(&sensitivity) {
            return Err(WakeWordError::Configuration(
                "Sensitivity must be between 0.0 and 1.0".to_string()
            ));
        }
        
        self.sensitivity = sensitivity;
        Ok(())
    }
    
    fn get_performance_metrics(&self) -> WakeWordMetrics {
        self.metrics.clone()
    }
    
    fn reset(&mut self) -> Result<(), WakeWordError> {
        self.ring_buffer.clear()
            .map_err(|e| WakeWordError::BufferOverflow(e.to_string()))?;
        
        self.feature_extractor.reset()
            .map_err(|e| WakeWordError::AudioProcessing(e.to_string()))?;
        
        self.confidence_filter.reset()
            .map_err(|e| WakeWordError::AudioProcessing(e.to_string()))?;
        
        self.processing_times.clear();
        self.last_detection = None;
        
        Ok(())
    }
    
    fn set_adaptive_sensitivity(&mut self, enabled: bool) -> Result<(), WakeWordError> {
        self.adaptive_sensitivity = enabled;
        self.confidence_filter.set_adaptive_mode(enabled)
            .map_err(|e| WakeWordError::Configuration(e.to_string()))?;
        Ok(())
    }
}

impl Default for MFCCWakeWordEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_wake_word_engine_initialization() {
        let mut engine = MFCCWakeWordEngine::new();
        let wake_words = vec!["hey guru".to_string(), "hello maya".to_string()];
        
        assert!(engine.initialize(&wake_words).is_ok());
        assert_eq!(engine.wake_words, wake_words);
        assert!(engine.initialized);
    }
    
    #[test]
    fn test_sensitivity_validation() {
        let mut engine = MFCCWakeWordEngine::new();
        
        assert!(engine.set_sensitivity(0.5).is_ok());
        assert!(engine.set_sensitivity(-0.1).is_err());
        assert!(engine.set_sensitivity(1.1).is_err());
    }
    
    #[test]
    fn test_performance_metrics() {
        let engine = MFCCWakeWordEngine::new();
        let metrics = engine.get_performance_metrics();
        
        assert_eq!(metrics.total_detections, 0);
        assert_eq!(metrics.false_positives, 0);
        assert!(metrics.uptime_hours >= 0.0);
    }
}