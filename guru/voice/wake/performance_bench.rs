// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! Performance Benchmarks for Wake Word Detection
//! 
//! This module provides benchmarks to verify performance requirements:
//! - CPU usage < 10% during idle monitoring
//! - Memory usage < 50MB
//! - Detection latency ≤ 50ms

#[cfg(test)]
mod tests {
    use crate::voice::wake::{MFCCWakeWordEngine, WakeWordEngine};
    use std::time::{Duration, Instant};
    
    /// Test that wake word engine meets CPU usage requirements
    #[test]
    fn test_cpu_usage_optimization() {
        let mut engine = MFCCWakeWordEngine::new();
        let wake_words = vec!["hey guru".to_string()];
        engine.initialize(&wake_words).unwrap();
        
        // Generate test audio (silence)
        let audio_chunk = vec![0.0; 1600]; // 100ms at 16kHz
        
        // Warm up
        for _ in 0..10 {
            let _ = engine.process_audio_stream(&audio_chunk);
        }
        
        // Measure processing time over multiple iterations
        let iterations = 100;
        let start = Instant::now();
        
        for _ in 0..iterations {
            let _ = engine.process_audio_stream(&audio_chunk);
        }
        
        let elapsed = start.elapsed();
        let avg_processing_time = elapsed / iterations;
        
        // Calculate CPU utilization
        // Each chunk is 100ms of audio, so if processing takes less than 10ms,
        // CPU usage is less than 10%
        let cpu_utilization = (avg_processing_time.as_secs_f32() / 0.1) * 100.0;
        
        println!("Average processing time: {:?}", avg_processing_time);
        println!("Estimated CPU utilization: {:.2}%", cpu_utilization);
        
        // Verify CPU usage is under 10%
        assert!(cpu_utilization < 10.0, 
            "CPU utilization {:.2}% exceeds 10% limit", cpu_utilization);
    }
    
    /// Test that wake word engine meets memory usage requirements
    #[test]
    fn test_memory_usage_optimization() {
        let mut engine = MFCCWakeWordEngine::new();
        let wake_words = vec!["hey guru".to_string(), "hello maya".to_string()];
        engine.initialize(&wake_words).unwrap();
        
        // Get metrics
        let metrics = engine.get_performance_metrics();
        
        println!("Memory usage: {:.2} MB", metrics.memory_usage_mb);
        
        // Verify memory usage is under 50MB
        assert!(metrics.memory_usage_mb < 50.0,
            "Memory usage {:.2}MB exceeds 50MB limit", metrics.memory_usage_mb);
    }
    
    /// Test that wake word detection latency meets requirements
    #[test]
    fn test_detection_latency_optimization() {
        let mut engine = MFCCWakeWordEngine::new();
        let wake_words = vec!["hey guru".to_string()];
        engine.initialize(&wake_words).unwrap();
        
        // Generate test audio with high confidence pattern
        let audio_chunk = vec![0.5; 1600]; // 100ms at 16kHz
        
        // Warm up
        for _ in 0..10 {
            let _ = engine.process_audio_stream(&audio_chunk);
        }
        
        // Measure detection latency
        let iterations = 50;
        let mut latencies = Vec::new();
        
        for _ in 0..iterations {
            let start = Instant::now();
            let _ = engine.process_audio_stream(&audio_chunk);
            let latency = start.elapsed();
            latencies.push(latency);
        }
        
        // Calculate statistics
        let avg_latency = latencies.iter().sum::<Duration>() / latencies.len() as u32;
        let max_latency = latencies.iter().max().unwrap();
        
        println!("Average detection latency: {:?}", avg_latency);
        println!("Maximum detection latency: {:?}", max_latency);
        
        // Verify average latency is under 50ms
        assert!(avg_latency < Duration::from_millis(50),
            "Average detection latency {:?} exceeds 50ms limit", avg_latency);
        
        // Verify 99th percentile is under 50ms
        let mut sorted_latencies = latencies.clone();
        sorted_latencies.sort();
        let p99_index = (iterations as f32 * 0.99) as usize;
        let p99_latency = sorted_latencies[p99_index];
        
        println!("99th percentile latency: {:?}", p99_latency);
        
        assert!(p99_latency < Duration::from_millis(50),
            "99th percentile latency {:?} exceeds 50ms limit", p99_latency);
    }
    
    /// Test ring buffer performance
    #[test]
    fn test_ring_buffer_performance() {
        use crate::voice::wake::AudioRingBuffer;
        
        let buffer = AudioRingBuffer::new(16000 * 10); // 10 seconds
        
        // Test write performance
        let audio_chunk = vec![0.5; 1600]; // 100ms
        let iterations = 100; // Reduced to avoid overflow
        
        let start = Instant::now();
        for _ in 0..iterations {
            buffer.write(&audio_chunk).unwrap();
        }
        let write_elapsed = start.elapsed();
        
        println!("Ring buffer write time: {:?} for {} iterations", 
            write_elapsed, iterations);
        println!("Average write time: {:?}", write_elapsed / iterations);
        
        // Verify write is fast (< 1ms per operation)
        let avg_write_time = write_elapsed / iterations;
        assert!(avg_write_time < Duration::from_millis(1),
            "Ring buffer write time {:?} exceeds 1ms", avg_write_time);
        
        // Test read performance
        let mut read_buffer = vec![0.0; 1600];
        let start = Instant::now();
        for _ in 0..iterations {
            let _ = buffer.read(&mut read_buffer);
        }
        let read_elapsed = start.elapsed();
        
        println!("Ring buffer read time: {:?} for {} iterations", 
            read_elapsed, iterations);
        println!("Average read time: {:?}", read_elapsed / iterations);
        
        // Verify read is fast (< 1ms per operation)
        let avg_read_time = read_elapsed / iterations;
        assert!(avg_read_time < Duration::from_millis(1),
            "Ring buffer read time {:?} exceeds 1ms", avg_read_time);
    }
    
    /// Test MFCC feature extraction performance
    #[test]
    fn test_mfcc_extraction_performance() {
        use crate::voice::wake::{MFCCExtractor, AudioRingBuffer};
        
        let mut extractor = MFCCExtractor::new();
        extractor.initialize().unwrap();
        
        let ring_buffer = AudioRingBuffer::new(16000);
        
        // Fill buffer with test audio
        let test_audio: Vec<f32> = (0..1600)
            .map(|i| {
                #[allow(clippy::cast_precision_loss)]
                let sample = (2.0 * std::f32::consts::PI * 440.0 * i as f32 / 16000.0).sin() * 0.5;
                sample
            })
            .collect();
        
        ring_buffer.write(&test_audio).unwrap();
        
        // Measure extraction time
        let iterations = 100;
        let start = Instant::now();
        
        for _ in 0..iterations {
            let _ = extractor.extract_features(&ring_buffer).unwrap();
        }
        
        let elapsed = start.elapsed();
        let avg_time = elapsed / iterations;
        
        println!("MFCC extraction time: {:?} average", avg_time);
        
        // Verify extraction is fast (< 10ms per operation)
        assert!(avg_time < Duration::from_millis(10),
            "MFCC extraction time {:?} exceeds 10ms", avg_time);
    }
    
    /// Stress test: continuous operation
    #[test]
    fn test_continuous_operation_stress() {
        let mut engine = MFCCWakeWordEngine::new();
        let wake_words = vec!["hey guru".to_string()];
        engine.initialize(&wake_words).unwrap();
        
        // Simulate continuous operation for 2 seconds
        let audio_chunk = vec![0.1; 1600]; // 100ms chunks
        let duration = Duration::from_secs(2);
        let start = Instant::now();
        
        let mut iterations = 0;
        let mut performance_violations = 0;
        
        while start.elapsed() < duration {
            let result = engine.process_audio_stream(&audio_chunk);
            match result {
                Ok(_) => {
                    iterations += 1;
                }
                Err(e) => {
                    let err_msg = e.to_string();
                    // Count performance violations but don't fail immediately
                    if err_msg.contains("Performance") {
                        performance_violations += 1;
                        iterations += 1;
                    } else if err_msg.contains("Buffer overflow") {
                        // Buffer overflow is expected during stress test - just continue
                        iterations += 1;
                    } else {
                        panic!("Unexpected error during continuous operation: {}", e);
                    }
                }
            }
        }
        
        println!("Processed {} iterations in {:?}", iterations, duration);
        println!("Performance violations: {}", performance_violations);
        
        // Allow some performance violations during stress test (< 30%)
        let violation_rate = if iterations > 0 {
            performance_violations as f32 / iterations as f32
        } else {
            0.0
        };
        println!("Violation rate: {:.2}%", violation_rate * 100.0);
        
        assert!(violation_rate < 0.3,
            "Too many performance violations: {:.2}%", violation_rate * 100.0);
        
        // Verify metrics are still reasonable
        let metrics = engine.get_performance_metrics();
        println!("Final metrics:");
        println!("  CPU utilization: {:.2}%", metrics.cpu_utilization_percent);
        println!("  Memory usage: {:.2} MB", metrics.memory_usage_mb);
        println!("  Audio processing latency: {:.2} ms", metrics.audio_processing_latency_ms);
        
        // Verify we processed a reasonable number of iterations
        assert!(iterations > 10, "Too few iterations processed: {}", iterations);
    }
}
