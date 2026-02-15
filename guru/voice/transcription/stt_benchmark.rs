//! STT Performance Benchmarking and Optimization
//!
//! This module provides benchmarking tools to measure and optimize STT performance
//! according to the requirement: ≤120ms per second of audio processing time.

use std::time::Instant;
use serde::{Deserialize, Serialize};

/// Performance metrics for STT operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct STTPerformanceMetrics {
    /// Total number of transcriptions performed
    pub total_transcriptions: u64,
    
    /// Total audio duration processed (milliseconds)
    pub total_audio_duration_ms: u64,
    
    /// Total processing time (milliseconds)
    pub total_processing_time_ms: u64,
    
    /// Average processing time per transcription (milliseconds)
    pub avg_processing_time_ms: f32,
    
    /// Real-time factor (processing_time / audio_duration)
    /// Target: ≤0.12 (120ms per second of audio)
    pub real_time_factor: f32,
    
    /// Minimum processing time observed (milliseconds)
    pub min_processing_time_ms: u64,
    
    /// Maximum processing time observed (milliseconds)
    pub max_processing_time_ms: u64,
    
    /// 95th percentile processing time (milliseconds)
    pub p95_processing_time_ms: u64,
    
    /// 99th percentile processing time (milliseconds)
    pub p99_processing_time_ms: u64,
    
    /// Number of times performance target was met
    pub target_met_count: u64,
    
    /// Number of times performance target was exceeded
    pub target_exceeded_count: u64,
}

impl Default for STTPerformanceMetrics {
    fn default() -> Self {
        Self {
            total_transcriptions: 0,
            total_audio_duration_ms: 0,
            total_processing_time_ms: 0,
            avg_processing_time_ms: 0.0,
            real_time_factor: 0.0,
            min_processing_time_ms: u64::MAX,
            max_processing_time_ms: 0,
            p95_processing_time_ms: 0,
            p99_processing_time_ms: 0,
            target_met_count: 0,
            target_exceeded_count: 0,
        }
    }
}

impl STTPerformanceMetrics {
    /// Creates a new metrics tracker
    pub fn new() -> Self {
        Self::default()
    }
    
    /// Records a transcription operation
    pub fn record_transcription(&mut self, audio_duration_ms: u64, processing_time_ms: u64) {
        self.total_transcriptions += 1;
        self.total_audio_duration_ms += audio_duration_ms;
        self.total_processing_time_ms += processing_time_ms;
        
        // Update min/max
        self.min_processing_time_ms = self.min_processing_time_ms.min(processing_time_ms);
        self.max_processing_time_ms = self.max_processing_time_ms.max(processing_time_ms);
        
        // Check if target was met (≤120ms per second of audio)
        let target_time_ms = (audio_duration_ms as f32 * 0.12) as u64;
        if processing_time_ms <= target_time_ms {
            self.target_met_count += 1;
        } else {
            self.target_exceeded_count += 1;
        }
        
        // Recalculate averages
        self.avg_processing_time_ms = 
            self.total_processing_time_ms as f32 / self.total_transcriptions as f32;
        
        self.real_time_factor = if self.total_audio_duration_ms > 0 {
            self.total_processing_time_ms as f32 / self.total_audio_duration_ms as f32
        } else {
            0.0
        };
    }
    
    /// Returns whether the performance target is being met
    pub fn is_target_met(&self) -> bool {
        self.real_time_factor <= 0.12
    }
    
    /// Returns the percentage of transcriptions that met the target
    pub fn target_met_percentage(&self) -> f32 {
        if self.total_transcriptions == 0 {
            return 0.0;
        }
        (self.target_met_count as f32 / self.total_transcriptions as f32) * 100.0
    }
    
    /// Generates a performance report
    pub fn generate_report(&self) -> String {
        format!(
            "STT Performance Report:\n\
             =====================\n\
             Total Transcriptions: {}\n\
             Total Audio Duration: {:.2}s\n\
             Total Processing Time: {:.2}s\n\
             Average Processing Time: {:.2}ms\n\
             Real-Time Factor: {:.4} (target: ≤0.12)\n\
             Min Processing Time: {}ms\n\
             Max Processing Time: {}ms\n\
             Target Met: {:.1}% ({}/{})\n\
             Performance Status: {}\n",
            self.total_transcriptions,
            self.total_audio_duration_ms as f32 / 1000.0,
            self.total_processing_time_ms as f32 / 1000.0,
            self.avg_processing_time_ms,
            self.real_time_factor,
            self.min_processing_time_ms,
            self.max_processing_time_ms,
            self.target_met_percentage(),
            self.target_met_count,
            self.total_transcriptions,
            if self.is_target_met() { "✅ PASS" } else { "❌ FAIL" }
        )
    }
}

/// Benchmark runner for STT performance testing
pub struct STTBenchmark {
    /// Metrics tracker
    metrics: STTPerformanceMetrics,
    
    /// Individual sample timings for percentile calculation
    sample_timings: Vec<(u64, u64)>, // (audio_duration_ms, processing_time_ms)
}

impl STTBenchmark {
    /// Creates a new benchmark runner
    pub fn new() -> Self {
        Self {
            metrics: STTPerformanceMetrics::new(),
            sample_timings: Vec::new(),
        }
    }
    
    /// Records a benchmark sample
    pub fn record_sample(&mut self, audio_duration_ms: u64, processing_time_ms: u64) {
        self.metrics.record_transcription(audio_duration_ms, processing_time_ms);
        self.sample_timings.push((audio_duration_ms, processing_time_ms));
    }
    
    /// Calculates percentile metrics
    pub fn calculate_percentiles(&mut self) {
        if self.sample_timings.is_empty() {
            return;
        }
        
        // Sort by processing time
        let mut timings: Vec<u64> = self.sample_timings.iter().map(|(_, pt)| *pt).collect();
        timings.sort_unstable();
        
        // Calculate percentiles
        let p95_index = (timings.len() as f32 * 0.95) as usize;
        let p99_index = (timings.len() as f32 * 0.99) as usize;
        
        self.metrics.p95_processing_time_ms = timings[p95_index.min(timings.len() - 1)];
        self.metrics.p99_processing_time_ms = timings[p99_index.min(timings.len() - 1)];
    }
    
    /// Returns the metrics
    pub fn get_metrics(&mut self) -> STTPerformanceMetrics {
        self.calculate_percentiles();
        self.metrics.clone()
    }
    
    /// Generates a detailed report
    pub fn generate_report(&mut self) -> String {
        self.calculate_percentiles();
        
        let mut report = self.metrics.generate_report();
        report.push_str(&format!(
            "P95 Processing Time: {}ms\n\
             P99 Processing Time: {}ms\n",
            self.metrics.p95_processing_time_ms,
            self.metrics.p99_processing_time_ms
        ));
        
        report
    }
}

impl Default for STTBenchmark {
    fn default() -> Self {
        Self::new()
    }
}

/// Timer for measuring STT operations
pub struct STTTimer {
    start_time: Instant,
    audio_duration_ms: u64,
}

impl STTTimer {
    /// Starts a new timer
    pub fn start(audio_duration_ms: u64) -> Self {
        Self {
            start_time: Instant::now(),
            audio_duration_ms,
        }
    }
    
    /// Stops the timer and returns (audio_duration_ms, processing_time_ms)
    pub fn stop(self) -> (u64, u64) {
        let processing_time_ms = self.start_time.elapsed().as_millis() as u64;
        (self.audio_duration_ms, processing_time_ms)
    }
    
    /// Checks if the current operation is within the performance target
    pub fn is_within_target(&self) -> bool {
        let elapsed_ms = self.start_time.elapsed().as_millis() as u64;
        let target_ms = (self.audio_duration_ms as f32 * 0.12) as u64;
        elapsed_ms <= target_ms
    }
    
    /// Returns the current real-time factor
    pub fn current_rtf(&self) -> f32 {
        let elapsed_ms = self.start_time.elapsed().as_millis() as u64;
        if self.audio_duration_ms == 0 {
            return 0.0;
        }
        elapsed_ms as f32 / self.audio_duration_ms as f32
    }
}

/// Audio preprocessing optimizations with SIMD-friendly operations
pub struct AudioPreprocessor {
    /// Sample rate
    #[allow(dead_code)]
    sample_rate: u32,
}

impl AudioPreprocessor {
    /// Creates a new audio preprocessor
    pub fn new(sample_rate: u32) -> Self {
        Self { sample_rate }
    }
    
    /// Optimized audio normalization with SIMD-friendly operations
    /// Time Complexity: O(n) - single pass
    /// Space Complexity: O(1) - in-place modification
    pub fn normalize(&self, audio: &mut [f32]) {
        if audio.is_empty() {
            return;
        }
        
        // Find max absolute value using iterator (compiler can auto-vectorize)
        let max_val = audio.iter()
            .map(|&x| x.abs())
            .fold(0.0f32, f32::max);
        
        if max_val > 0.0 && max_val != 1.0 {
            let scale = 1.0 / max_val;
            // SIMD-friendly: compiler can vectorize this loop
            for sample in audio.iter_mut() {
                *sample *= scale;
            }
        }
    }
    
    /// Optimized DC offset removal with single-pass algorithm
    /// Time Complexity: O(n) - two passes (one for mean, one for subtraction)
    /// Space Complexity: O(1) - in-place modification
    pub fn remove_dc_offset(&self, audio: &mut [f32]) {
        if audio.is_empty() {
            return;
        }
        
        // Calculate mean using Kahan summation for numerical stability
        let mut sum = 0.0f32;
        let mut compensation = 0.0f32;
        
        for &sample in audio.iter() {
            let y = sample - compensation;
            let t = sum + y;
            compensation = (t - sum) - y;
            sum = t;
        }
        
        let mean = sum / audio.len() as f32;
        
        // Subtract mean from all samples (SIMD-friendly)
        for sample in audio.iter_mut() {
            *sample -= mean;
        }
    }
    
    /// Optimized pre-emphasis filter with reverse iteration
    /// Time Complexity: O(n) - single pass
    /// Space Complexity: O(1) - in-place modification
    pub fn apply_preemphasis(&self, audio: &mut [f32], coefficient: f32) {
        if audio.len() < 2 {
            return;
        }
        
        // Apply pre-emphasis filter: y[n] = x[n] - coefficient * x[n-1]
        // Reverse iteration to avoid temporary buffer
        for i in (1..audio.len()).rev() {
            audio[i] -= coefficient * audio[i - 1];
        }
    }
    
    /// Complete preprocessing pipeline - optimized single-pass where possible
    /// Time Complexity: O(n) - three linear passes
    /// Space Complexity: O(1) - all operations are in-place
    pub fn preprocess(&self, audio: &mut [f32]) {
        // Pipeline order optimized for best results:
        // 1. Remove DC offset first (centers signal around zero)
        // 2. Apply pre-emphasis (boosts high frequencies for better speech recognition)
        // 3. Normalize last (ensures consistent amplitude)
        self.remove_dc_offset(audio);
        self.apply_preemphasis(audio, 0.97);
        self.normalize(audio);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    
    #[test]
    fn test_performance_metrics() {
        let mut metrics = STTPerformanceMetrics::new();
        
        // Record some samples
        metrics.record_transcription(1000, 100); // 100ms for 1s audio (0.1 RTF) - PASS
        metrics.record_transcription(1000, 150); // 150ms for 1s audio (0.15 RTF) - FAIL
        metrics.record_transcription(1000, 80);  // 80ms for 1s audio (0.08 RTF) - PASS
        
        assert_eq!(metrics.total_transcriptions, 3);
        assert_eq!(metrics.target_met_count, 2);
        assert_eq!(metrics.target_exceeded_count, 1);
        assert!((metrics.target_met_percentage() - 66.67).abs() < 0.1);
    }
    
    #[test]
    fn test_benchmark_runner() {
        let mut benchmark = STTBenchmark::new();
        
        // Record samples
        for i in 0..100 {
            let audio_duration = 1000;
            let processing_time = 50 + i; // Increasing processing times
            benchmark.record_sample(audio_duration, processing_time);
        }
        
        let metrics = benchmark.get_metrics();
        assert_eq!(metrics.total_transcriptions, 100);
        assert!(metrics.p95_processing_time_ms > 0);
        assert!(metrics.p99_processing_time_ms >= metrics.p95_processing_time_ms);
    }
    
    #[test]
    fn test_stt_timer() {
        let timer = STTTimer::start(1000);
        std::thread::sleep(Duration::from_millis(50));
        
        let (audio_duration, processing_time) = timer.stop();
        assert_eq!(audio_duration, 1000);
        assert!(processing_time >= 50);
        assert!(processing_time < 200); // Should be close to 50ms
    }
    
    #[test]
    fn test_audio_preprocessor() {
        let preprocessor = AudioPreprocessor::new(16000);
        
        // Test normalization
        let mut audio = vec![0.5, 1.0, -0.5, -1.0];
        preprocessor.normalize(&mut audio);
        assert!((audio.iter().map(|&x| x.abs()).fold(0.0f32, f32::max) - 1.0).abs() < 1e-6);
        
        // Test DC offset removal
        let mut audio = vec![1.0, 1.1, 0.9, 1.0];
        preprocessor.remove_dc_offset(&mut audio);
        let mean: f32 = audio.iter().sum::<f32>() / audio.len() as f32;
        assert!(mean.abs() < 1e-6);
    }
}
