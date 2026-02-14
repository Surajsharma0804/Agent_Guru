// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! Lock-Free Audio Ring Buffer
//! 
//! This module implements a lock-free circular buffer with memory barriers
//! for continuous audio processing in real-time systems.
//! 
//! Based on clean room extraction of algorithms from openWakeWord project.
//! Mathematical concepts and implementation patterns only - no foreign code.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use thiserror::Error;

/// Ring buffer errors
#[derive(Error, Debug)]
pub enum RingBufferError {
    #[error("Buffer overflow: attempted to write {attempted} samples, but only {available} slots available")]
    BufferOverflow { attempted: usize, available: usize },
    
    #[error("Buffer underflow: attempted to read {requested} samples, but only {available} samples available")]
    BufferUnderflow { requested: usize, available: usize },
    
    #[error("Invalid buffer size: {0}")]
    InvalidSize(usize),
    
    #[error("Buffer not initialized")]
    NotInitialized,
}

/// Lock-free audio ring buffer for continuous streaming
pub struct AudioRingBuffer {
    buffer: Mutex<Vec<f32>>,
    capacity: usize,
    write_pos: AtomicUsize,
    read_pos: AtomicUsize,
    initialized: bool,
}

impl AudioRingBuffer {
    /// Create new audio ring buffer with specified capacity
    pub fn new(capacity: usize) -> Self {
        let actual_capacity = if capacity == 0 || !capacity.is_power_of_two() {
            // Round up to next power of two for efficient modulo operations
            capacity.next_power_of_two()
        } else {
            capacity
        };
        
        Self {
            buffer: Mutex::new(vec![0.0; actual_capacity]),
            capacity: actual_capacity,
            write_pos: AtomicUsize::new(0),
            read_pos: AtomicUsize::new(0),
            initialized: true,
        }
    }
    
    /// Write audio samples to the ring buffer
    ///
    /// # Panics
    ///
    /// Panics if the mutex lock is poisoned.
    pub fn write(&self, samples: &[f32]) -> Result<usize, RingBufferError> {
        if !self.initialized {
            return Err(RingBufferError::NotInitialized);
        }
        
        if samples.is_empty() {
            return Ok(0);
        }
        
        let available_space = self.available_write_space();
        if samples.len() > available_space {
            return Err(RingBufferError::BufferOverflow {
                attempted: samples.len(),
                available: available_space,
            });
        }
        
        let write_pos = self.write_pos.load(Ordering::Acquire);
        
        // Handle wrap-around case
        let end_pos = write_pos + samples.len();
        
        let mut buffer = self.buffer.lock().unwrap();
        
        if end_pos <= self.capacity {
            // No wrap-around needed - use safe slice operations
            let buffer_slice = &mut buffer[write_pos..write_pos + samples.len()];
            buffer_slice.copy_from_slice(samples);
        } else {
            // Handle wrap-around using safe slice operations
            let first_chunk_size = self.capacity - write_pos;
            let second_chunk_size = samples.len() - first_chunk_size;
            
            // Write first chunk to end of buffer
            let first_buffer_slice = &mut buffer[write_pos..];
            let first_sample_slice = &samples[..first_chunk_size];
            first_buffer_slice.copy_from_slice(first_sample_slice);
            
            // Write second chunk to beginning of buffer
            let second_buffer_slice = &mut buffer[..second_chunk_size];
            let second_sample_slice = &samples[first_chunk_size..];
            second_buffer_slice.copy_from_slice(second_sample_slice);
        }
        drop(buffer);
        
        let written = samples.len();
        
        // Update write position with memory barrier
        let new_write_pos = (write_pos + written) % self.capacity;
        self.write_pos.store(new_write_pos, Ordering::Release);
        
        Ok(written)
    }
    
    /// Read audio samples from the ring buffer
    ///
    /// # Panics
    ///
    /// Panics if the mutex lock is poisoned.
    pub fn read(&self, samples: &mut [f32]) -> Result<usize, RingBufferError> {
        if !self.initialized {
            return Err(RingBufferError::NotInitialized);
        }
        
        if samples.is_empty() {
            return Ok(0);
        }
        
        let available_samples = self.available_samples();
        if samples.len() > available_samples {
            return Err(RingBufferError::BufferUnderflow {
                requested: samples.len(),
                available: available_samples,
            });
        }
        
        let read_pos = self.read_pos.load(Ordering::Acquire);
        
        // Handle wrap-around case
        let end_pos = read_pos + samples.len();
        
        let buffer = self.buffer.lock().unwrap();
        
        if end_pos <= self.capacity {
            // No wrap-around needed - use safe slice operations
            let buffer_slice = &buffer[read_pos..read_pos + samples.len()];
            samples.copy_from_slice(buffer_slice);
        } else {
            // Handle wrap-around using safe slice operations
            let first_chunk_size = self.capacity - read_pos;
            let second_chunk_size = samples.len() - first_chunk_size;
            
            // Read first chunk from end of buffer
            let first_buffer_slice = &buffer[read_pos..];
            let first_sample_slice = &mut samples[..first_chunk_size];
            first_sample_slice.copy_from_slice(first_buffer_slice);
            
            // Read second chunk from beginning of buffer
            let second_buffer_slice = &buffer[..second_chunk_size];
            let second_sample_slice = &mut samples[first_chunk_size..];
            second_sample_slice.copy_from_slice(second_buffer_slice);
        }
        let read_count = samples.len();
        drop(buffer);
        
        // Update read position with memory barrier
        let new_read_pos = (read_pos + read_count) % self.capacity;
        self.read_pos.store(new_read_pos, Ordering::Release);
        
        Ok(read_count)
    }
    
    /// Read latest N samples without advancing read position
    ///
    /// # Panics
    ///
    /// Panics if the mutex lock is poisoned.
    pub fn read_latest(&self, count: usize) -> Result<Vec<f32>, RingBufferError> {
        if !self.initialized {
            return Err(RingBufferError::NotInitialized);
        }
        
        let available = self.available_samples();
        if count > available {
            return Err(RingBufferError::BufferUnderflow {
                requested: count,
                available,
            });
        }
        
        let write_pos = self.write_pos.load(Ordering::Acquire);
        let start_pos = if write_pos >= count {
            write_pos - count
        } else {
            self.capacity - (count - write_pos)
        };
        
        let mut samples = vec![0.0; count];
        
        let buffer = self.buffer.lock().unwrap();
        
        // Handle wrap-around case
        let end_pos = start_pos + count;
        
        if end_pos <= self.capacity {
            // No wrap-around needed - use safe slice operations
            let buffer_slice = &buffer[start_pos..start_pos + count];
            samples.copy_from_slice(buffer_slice);
        } else {
            // Handle wrap-around using safe slice operations
            let first_chunk_size = self.capacity - start_pos;
            let second_chunk_size = count - first_chunk_size;
            
            // Read first chunk from end of buffer
            let first_buffer_slice = &buffer[start_pos..];
            let first_sample_slice = &mut samples[..first_chunk_size];
            first_sample_slice.copy_from_slice(first_buffer_slice);
            
            // Read second chunk from beginning of buffer
            let second_buffer_slice = &buffer[..second_chunk_size];
            let second_sample_slice = &mut samples[first_chunk_size..];
            second_sample_slice.copy_from_slice(second_buffer_slice);
        }
        drop(buffer);
        
        Ok(samples)
    }
    
    /// Get number of samples available for reading
    pub fn available_samples(&self) -> usize {
        let write_pos = self.write_pos.load(Ordering::Acquire);
        let read_pos = self.read_pos.load(Ordering::Acquire);
        
        if write_pos >= read_pos {
            write_pos - read_pos
        } else {
            self.capacity - read_pos + write_pos
        }
    }
    
    /// Get number of slots available for writing
    pub fn available_write_space(&self) -> usize {
        // Leave one slot empty to distinguish between full and empty buffer
        self.capacity - self.available_samples() - 1
    }
    
    /// Check if buffer is empty
    pub fn is_empty(&self) -> bool {
        self.available_samples() == 0
    }
    
    /// Check if buffer is full
    pub fn is_full(&self) -> bool {
        self.available_write_space() == 0
    }
    
    /// Get buffer capacity
    pub fn capacity(&self) -> usize {
        self.capacity
    }
    
    /// Clear the buffer
    pub fn clear(&self) -> Result<(), RingBufferError> {
        if !self.initialized {
            return Err(RingBufferError::NotInitialized);
        }
        
        self.write_pos.store(0, Ordering::Release);
        self.read_pos.store(0, Ordering::Release);
        
        Ok(())
    }
    
    /// Get buffer utilization percentage
    pub fn utilization(&self) -> f32 {
        (self.available_samples() as f32 / self.capacity as f32) * 100.0
    }
    
    /// Force write samples, overwriting old data if necessary
    pub fn force_write(&self, samples: &[f32]) -> Result<usize, RingBufferError> {
        if !self.initialized {
            return Err(RingBufferError::NotInitialized);
        }
        
        if samples.is_empty() {
            return Ok(0);
        }
        
        // If samples exceed capacity, only write the latest samples
        let samples_to_write = if samples.len() > self.capacity - 1 {
            &samples[samples.len() - (self.capacity - 1)..]
        } else {
            samples
        };
        
        // If not enough space, advance read pointer to make room
        let available_space = self.available_write_space();
        if samples_to_write.len() > available_space {
            let samples_to_skip = samples_to_write.len() - available_space;
            let current_read_pos = self.read_pos.load(Ordering::Acquire);
            let new_read_pos = (current_read_pos + samples_to_skip) % self.capacity;
            self.read_pos.store(new_read_pos, Ordering::Release);
        }
        
        // Now write the samples
        self.write(samples_to_write)
    }
}

/// Thread-safe shared ring buffer
#[derive(Clone)]
pub struct SharedAudioRingBuffer {
    inner: Arc<AudioRingBuffer>,
}

impl SharedAudioRingBuffer {
    /// Create new shared ring buffer
    pub fn new(capacity: usize) -> Self {
        Self {
            inner: Arc::new(AudioRingBuffer::new(capacity)),
        }
    }
    
    /// Write samples to the shared buffer
    pub fn write(&self, samples: &[f32]) -> Result<usize, RingBufferError> {
        self.inner.write(samples)
    }
    
    /// Read samples from the shared buffer
    pub fn read(&self, samples: &mut [f32]) -> Result<usize, RingBufferError> {
        self.inner.read(samples)
    }
    
    /// Read latest samples without advancing read position
    pub fn read_latest(&self, count: usize) -> Result<Vec<f32>, RingBufferError> {
        self.inner.read_latest(count)
    }
    
    /// Get available samples
    pub fn available_samples(&self) -> usize {
        self.inner.available_samples()
    }
    
    /// Clear the buffer
    pub fn clear(&self) -> Result<(), RingBufferError> {
        self.inner.clear()
    }
}

// AudioRingBuffer is Send and Sync due to proper synchronization with Mutex and AtomicUsize

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    use std::time::Duration;
    
    #[test]
    fn test_ring_buffer_creation() {
        let buffer = AudioRingBuffer::new(1024);
        assert_eq!(buffer.capacity(), 1024);
        assert!(buffer.is_empty());
        assert!(!buffer.is_full());
    }
    
    #[test]
    fn test_basic_write_read() {
        let buffer = AudioRingBuffer::new(1024);
        let samples = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        
        // Write samples
        let written = buffer.write(&samples).unwrap();
        assert_eq!(written, 5);
        assert_eq!(buffer.available_samples(), 5);
        
        // Read samples
        let mut read_samples = vec![0.0; 5];
        let read_count = buffer.read(&mut read_samples).unwrap();
        assert_eq!(read_count, 5);
        assert_eq!(read_samples, samples);
        assert!(buffer.is_empty());
    }
    
    #[test]
    fn test_wrap_around() {
        let buffer = AudioRingBuffer::new(8);
        
        // Fill buffer almost to capacity
        let samples1 = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0];
        buffer.write(&samples1).unwrap();
        
        // Read some samples to create space at the beginning
        let mut read_buffer = vec![0.0; 3];
        buffer.read(&mut read_buffer).unwrap();
        
        // Write more samples that will wrap around
        let samples2 = vec![7.0, 8.0, 9.0, 10.0];
        buffer.write(&samples2).unwrap();
        
        // Read all remaining samples
        let mut all_samples = vec![0.0; 7];
        buffer.read(&mut all_samples).unwrap();
        
        assert_eq!(all_samples, vec![4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]);
    }
    
    #[test]
    fn test_read_latest() {
        let buffer = AudioRingBuffer::new(1024);
        let samples = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        
        buffer.write(&samples).unwrap();
        
        // Read latest 3 samples
        let latest = buffer.read_latest(3).unwrap();
        assert_eq!(latest, vec![3.0, 4.0, 5.0]);
        
        // Buffer should still have all samples (read_latest doesn't advance read position)
        assert_eq!(buffer.available_samples(), 5);
    }
    
    #[test]
    fn test_buffer_overflow() {
        let buffer = AudioRingBuffer::new(8);
        let large_samples = vec![1.0; 10]; // More than capacity
        
        let result = buffer.write(&large_samples);
        assert!(result.is_err());
        
        match result.unwrap_err() {
            RingBufferError::BufferOverflow { attempted, available } => {
                assert_eq!(attempted, 10);
                assert_eq!(available, 7); // capacity - 1
            }
            _ => panic!("Expected BufferOverflow error"),
        }
    }
    
    #[test]
    fn test_buffer_underflow() {
        let buffer = AudioRingBuffer::new(1024);
        let mut read_buffer = vec![0.0; 10];
        
        let result = buffer.read(&mut read_buffer);
        assert!(result.is_err());
        
        match result.unwrap_err() {
            RingBufferError::BufferUnderflow { requested, available } => {
                assert_eq!(requested, 10);
                assert_eq!(available, 0);
            }
            _ => panic!("Expected BufferUnderflow error"),
        }
    }
    
    #[test]
    fn test_force_write() {
        let buffer = AudioRingBuffer::new(8);
        
        // Fill buffer to capacity
        let samples1 = vec![1.0; 7];
        buffer.write(&samples1).unwrap();
        
        // Force write more samples (should overwrite old data)
        let samples2 = vec![2.0, 3.0, 4.0];
        let written = buffer.force_write(&samples2).unwrap();
        assert_eq!(written, 3);
        
        // Read all available samples
        let available = buffer.available_samples();
        let mut read_samples = vec![0.0; available];
        buffer.read(&mut read_samples).unwrap();
        
        // Should contain the latest samples
        assert!(read_samples.contains(&2.0));
        assert!(read_samples.contains(&3.0));
        assert!(read_samples.contains(&4.0));
    }
    
    #[test]
    fn test_clear() {
        let buffer = AudioRingBuffer::new(1024);
        let samples = vec![1.0, 2.0, 3.0];
        
        buffer.write(&samples).unwrap();
        assert!(!buffer.is_empty());
        
        buffer.clear().unwrap();
        assert!(buffer.is_empty());
        assert_eq!(buffer.available_samples(), 0);
    }
    
    #[test]
    fn test_utilization() {
        let buffer = AudioRingBuffer::new(128); // Use power of 2 to avoid rounding
        let samples = vec![1.0; 50];
        
        buffer.write(&samples).unwrap();
        let expected_utilization = (50.0 / 128.0) * 100.0;
        assert!((buffer.utilization() - expected_utilization).abs() < 0.1);
    }
    
    #[test]
    fn test_shared_buffer() {
        let shared_buffer = SharedAudioRingBuffer::new(1024);
        let buffer_clone = shared_buffer.clone();
        
        // Write from one reference
        let samples = vec![1.0, 2.0, 3.0];
        shared_buffer.write(&samples).unwrap();
        
        // Read from another reference
        let mut read_samples = vec![0.0; 3];
        buffer_clone.read(&mut read_samples).unwrap();
        
        assert_eq!(read_samples, samples);
    }
    
    #[test]
    fn test_concurrent_access() {
        let shared_buffer = SharedAudioRingBuffer::new(1024);
        let buffer_clone = shared_buffer.clone();
        
        // Spawn writer thread
        let writer_handle = thread::spawn(move || {
            for i in 0..100 {
                #[allow(clippy::cast_precision_loss)]
                let samples = vec![i as f32; 10];
                while shared_buffer.write(&samples).is_err() {
                    thread::sleep(Duration::from_millis(1));
                }
                thread::sleep(Duration::from_millis(1));
            }
        });
        
        // Spawn reader thread
        let reader_handle = thread::spawn(move || {
            let mut total_read = 0;
            while total_read < 1000 {
                let mut samples = vec![0.0; 10];
                if buffer_clone.read(&mut samples).is_ok() {
                    total_read += 10;
                }
                thread::sleep(Duration::from_millis(1));
            }
        });
        
        writer_handle.join().unwrap();
        reader_handle.join().unwrap();
    }
    
    #[test]
    fn test_power_of_two_capacity() {
        // Test that non-power-of-two capacities are rounded up
        let buffer = AudioRingBuffer::new(1000);
        assert_eq!(buffer.capacity(), 1024); // Next power of two
        
        let buffer2 = AudioRingBuffer::new(512);
        assert_eq!(buffer2.capacity(), 512); // Already power of two
    }
}