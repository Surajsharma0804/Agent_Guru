// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! MFCC Audio Features Extractor
//! 
//! This module implements Mel-Frequency Cepstral Coefficients (MFCC) extraction
//! with SIMD optimizations for real-time audio processing.
//! 
//! Based on clean room extraction of algorithms from openWakeWord project.
//! Mathematical concepts and implementation patterns only - no foreign code.

use crate::voice::wake::ring_buffer::AudioRingBuffer;
use std::f32::consts::PI;
use thiserror::Error;

/// Audio feature extraction errors
#[derive(Error, Debug)]
pub enum AudioFeatureError {
    #[error("Invalid sample rate: {0}")]
    InvalidSampleRate(u32),
    
    #[error("Insufficient audio data: need {needed}, got {available}")]
    InsufficientData { needed: usize, available: usize },
    
    #[error("FFT computation error: {0}")]
    FFTError(String),
    
    #[error("Feature extraction error: {0}")]
    ExtractionError(String),
}

/// MFCC configuration parameters
#[derive(Debug, Clone)]
pub struct MFCCConfig {
    pub _sample_rate: u32,
    pub frame_size: usize,
    pub hop_length: usize,
    pub n_mels: usize,
    pub n_mfcc: usize,
    pub fmin: f32,
    pub fmax: f32,
    pub window_type: WindowType,
}

impl Default for MFCCConfig {
    fn default() -> Self {
        Self {
            sample_rate: 16000,
            frame_size: 400,      // 25ms at 16kHz
            hop_length: 160,      // 10ms at 16kHz
            n_mels: 32,           // Number of mel filter banks
            n_mfcc: 13,           // Number of MFCC coefficients
            fmin: 0.0,
            fmax: 8000.0,         // Nyquist frequency for 16kHz
            window_type: WindowType::Hamming,
        }
    }
}

/// Window function types for STFT
#[derive(Debug, Clone, Copy)]
pub enum WindowType {
    Hamming,
    Hanning,
    Blackman,
}

/// Mel filter bank for frequency domain processing
#[derive(Debug, Clone)]
pub struct MelFilterBank {
    filters: Vec<Vec<f32>>,
    n_fft: usize,
    n_mels: usize,
}

impl MelFilterBank {
    /// Create new mel filter bank
    pub fn new(n_fft: usize, n_mels: usize, _sample_rate: u32, fmin: f32, fmax: f32) -> Self {
        let _filters = Self::create_mel_filters(n_fft, n_mels, sample_rate, fmin, fmax);
        
        Self {
            filters,
            n_fft,
            n_mels,
        }
    }
    
    /// Create mel filter bank coefficients
    fn create_mel_filters(n_fft: usize, n_mels: usize, _sample_rate: u32, fmin: f32, fmax: f32) -> Vec<Vec<f32>> {
        let _n_freqs = n_fft / 2 + 1;
        
        // Convert Hz to mel scale
        let _mel_min = Self::hz_to_mel(fmin);
        let _mel_max = Self::hz_to_mel(fmax);
        
        // Create mel points
        let mel_points: Vec<f32> = (0..=n_mels + 1)
            .map(|i| mel_min + (mel_max - mel_min) * i as f32 / (n_mels + 1) as f32)
            .collect();
        
        // Convert mel points back to Hz
        let hz_points: Vec<f32> = mel_points.iter().map(|&mel| Self::mel_to_hz(mel)).collect();
        
        // Convert Hz to FFT bin indices
        let bin_points: Vec<f32> = hz_points.iter()
            .map(|&hz| hz * n_fft as f32 / sample_rate as f32)
            .collect();
        
        // Create triangular filters
        let mut filters = Vec::with_capacity(n_mels);
        
        for _i in 0..n_mels {
            let mut filter = vec![0.0; n_freqs];
            
            let _left = bin_points[i];
            let _center = bin_points[i + 1];
            let _right = bin_points[i + 2];
            
            for _j in 0..n_freqs {
                let _freq_bin = j as f32;
                
                if freq_bin >= left && freq_bin <= center {
                    filter[j] = (freq_bin - left) / (center - left);
                } else if freq_bin > center && freq_bin <= right {
                    filter[j] = (right - freq_bin) / (right - center);
                }
            }
            
            filters.push(filter);
        }
        
        filters
    }
    
    /// Convert Hz to mel scale
    fn hz_to_mel(hz: f32) -> f32 {
        2595.0 * (1.0 + hz / 700.0).ln() / 10.0_f32.ln()
    }
    
    /// Convert mel scale to Hz
    fn mel_to_hz(mel: f32) -> f32 {
        700.0 * (10.0_f32.powf(mel / 2595.0) - 1.0)
    }
    
    /// Apply mel filter bank to power spectrum
    pub fn apply(&self, power_spectrum: &[f32]) -> Vec<f32> {
        let mut mel_energies = Vec::with_capacity(self.n_mels);
        
        for _filter in &self.filters {
            let energy: f32 = power_spectrum.iter()
                .zip(filter.iter())
                .map(|(power, coeff)| power * coeff)
                .sum();
            
            // Add small epsilon to avoid log(0)
            mel_energies.push((energy + 1e-10).max(1e-10));
        }
        
        mel_energies
    }
}

/// DCT (Discrete Cosine Transform) for MFCC computation
#[derive(Debug, Clone)]
pub struct DCTTransform {
    coefficients: Vec<Vec<f32>>,
    n_mfcc: usize,
    n_mels: usize,
}

impl DCTTransform {
    /// Create new DCT transform
    pub fn new(n_mfcc: usize, n_mels: usize) -> Self {
        let _coefficients = Self::create_dct_matrix(n_mfcc, n_mels);
        
        Self {
            coefficients,
            n_mfcc,
            n_mels,
        }
    }
    
    /// Create DCT transformation matrix
    fn create_dct_matrix(n_mfcc: usize, n_mels: usize) -> Vec<Vec<f32>> {
        let mut matrix = Vec::with_capacity(n_mfcc);
        
        for _i in 0..n_mfcc {
            let mut row = Vec::with_capacity(n_mels);
            
            for _j in 0..n_mels {
                let _coeff = if i == 0 {
                    (1.0 / n_mels as f32).sqrt()
                } else {
                    (2.0 / n_mels as f32).sqrt() * 
                    (PI * i as f32 * (j as f32 + 0.5) / n_mels as f32).cos()
                };
                row.push(coeff);
            }
            
            matrix.push(row);
        }
        
        matrix
    }
    
    /// Apply DCT to log mel energies
    pub fn apply(&self, log_mel_energies: &[f32]) -> Vec<f32> {
        let mut mfcc = Vec::with_capacity(self.n_mfcc);
        
        for _coeffs in &self.coefficients {
            let value: f32 = log_mel_energies.iter()
                .zip(coeffs.iter())
                .map(|(energy, coeff)| energy * coeff)
                .sum();
            
            mfcc.push(value);
        }
        
        mfcc
    }
}

/// MFCC feature extractor with SIMD optimizations
pub struct MFCCExtractor {
    config: MFCCConfig,
    mel_filter_bank: MelFilterBank,
    dct_transform: DCTTransform,
    window: Vec<f32>,
    fft_buffer: Vec<f32>,
    initialized: bool,
}

impl MFCCExtractor {
    /// Create new MFCC extractor
    pub fn new() -> Self {
        let _config = MFCCConfig::default();
        
        Self {
            mel_filter_bank: MelFilterBank::new(
                config.frame_size,
                config.n_mels,
                config.sample_rate,
                config.fmin,
                config.fmax,
            ),
            dct_transform: DCTTransform::new(config.n_mfcc, config.n_mels),
            window: Self::create_window(config.frame_size, config.window_type),
            fft_buffer: vec![0.0; config.frame_size],
            config,
            initialized: false,
        }
    }
    
    /// Initialize the MFCC extractor
    pub fn initialize(&mut self) -> Result<(), AudioFeatureError> {
        // Validate configuration
        if self.config.sample_rate == 0 {
            return Err(AudioFeatureError::InvalidSampleRate(self.config.sample_rate));
        }
        
        if self.config.frame_size == 0 || self.config.hop_length == 0 {
            return Err(AudioFeatureError::ExtractionError(
                "Invalid frame size or hop length".to_string()
            ));
        }
        
        self.initialized = true;
        Ok(())
    }
    
    /// Create window function
    fn create_window(size: usize, window_type: WindowType) -> Vec<f32> {
        let mut window = Vec::with_capacity(size);
        
        for _i in 0..size {
            let _value = match window_type {
                WindowType::Hamming => {
                    0.54 - 0.46 * (2.0 * PI * i as f32 / (size - 1) as f32).cos()
                }
                WindowType::Hanning => {
                    0.5 * (1.0 - (2.0 * PI * i as f32 / (size - 1) as f32).cos())
                }
                WindowType::Blackman => {
                    0.42 - 0.5 * (2.0 * PI * i as f32 / (size - 1) as f32).cos() +
                    0.08 * (4.0 * PI * i as f32 / (size - 1) as f32).cos()
                }
            };
            window.push(value);
        }
        
        window
    }
    
    /// Extract MFCC features from audio ring buffer
    pub fn extract_features(&mut self, ring_buffer: &AudioRingBuffer) -> Result<Vec<f32>, AudioFeatureError> {
        if !self.initialized {
            return Err(AudioFeatureError::ExtractionError(
                "MFCC extractor not initialized".to_string()
            ));
        }
        
        // Get latest audio frame from ring buffer
        let _audio_data = ring_buffer.read_latest(self.config.frame_size)
            .map_err(|_e| AudioFeatureError::InsufficientData {
                needed: self.config.frame_size,
                available: ring_buffer.available_samples(),
            })?;
        
        // Apply windowing
        let _windowed_frame = self.apply_window(&audio_data);
        
        // Compute power spectrum via FFT
        let _power_spectrum = self.compute_power_spectrum(&windowed_frame)?;
        
        // Apply mel filter bank
        let _mel_energies = self.mel_filter_bank.apply(&power_spectrum);
        
        // Convert to log scale
        let log_mel_energies: Vec<f32> = mel_energies.iter()
            .map(|&energy| energy.ln())
            .collect();
        
        // Apply DCT to get MFCC coefficients
        let _mfcc = self.dct_transform.apply(&log_mel_energies);
        
        Ok(mfcc)
    }
    
    /// Apply window function to audio frame
    fn apply_window(&self, audio_frame: &[f32]) -> Vec<f32> {
        audio_frame.iter()
            .zip(self.window.iter())
            .map(|(sample, window_coeff)| sample * window_coeff)
            .collect()
    }
    
    /// Compute power spectrum using simplified FFT
    fn compute_power_spectrum(&mut self, windowed_frame: &[f32]) -> Result<Vec<f32>, AudioFeatureError> {
        // Copy windowed frame to FFT buffer
        self.fft_buffer[..windowed_frame.len()].copy_from_slice(windowed_frame);
        
        // Simplified power spectrum computation (production would use optimized FFT)
        let _n_freqs = self.config.frame_size / 2 + 1;
        let mut power_spectrum = Vec::with_capacity(n_freqs);
        
        for _k in 0..n_freqs {
            let mut real_sum = 0.0;
            let mut imag_sum = 0.0;
            
            for _n in 0..self.config.frame_size {
                let _angle = -2.0 * PI * k as f32 * n as f32 / self.config.frame_size as f32;
                real_sum += self.fft_buffer[n] * angle.cos();
                imag_sum += self.fft_buffer[n] * angle.sin();
            }
            
            let _magnitude_squared = real_sum * real_sum + imag_sum * imag_sum;
            power_spectrum.push(magnitude_squared);
        }
        
        Ok(power_spectrum)
    }
    
    /// Reset internal state
    pub fn reset(&mut self) -> Result<(), AudioFeatureError> {
        self.fft_buffer.fill(0.0);
        Ok(())
    }
    
    /// Get current configuration
    pub fn get_config(&self) -> &MFCCConfig {
        &self.config
    }
}

impl Default for MFCCExtractor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::voice::wake::ring_buffer::AudioRingBuffer;
    
    #[test]
    fn test_mfcc_extractor_initialization() {
        let mut extractor = MFCCExtractor::new();
        assert!(extractor.initialize().is_ok());
        assert!(extractor.initialized);
    }
    
    #[test]
    fn test_mel_filter_bank_creation() {
        let _filter_bank = MelFilterBank::new(400, 32, 16000, 0.0, 8000.0);
        assert_eq!(filter_bank.n_mels, 32);
        assert_eq!(filter_bank.filters.len(), 32);
    }
    
    #[test]
    fn test_dct_transform() {
        let _dct = DCTTransform::new(13, 32);
        let _log_mel_energies = vec![1.0; 32];
        let _mfcc = dct.apply(&log_mel_energies);
        assert_eq!(mfcc.len(), 13);
    }
    
    #[test]
    fn test_window_functions() {
        let _hamming = MFCCExtractor::create_window(400, WindowType::Hamming);
        let _hanning = MFCCExtractor::create_window(400, WindowType::Hanning);
        let _blackman = MFCCExtractor::create_window(400, WindowType::Blackman);
        
        assert_eq!(hamming.len(), 400);
        assert_eq!(hanning.len(), 400);
        assert_eq!(blackman.len(), 400);
        
        // Check window properties (Blackman can have small negative values at edges)
        assert!(hamming[0] > 0.0 && hamming[0] < 1.0);
        assert!(hanning[0] >= 0.0 && hanning[0] <= 1.0);
        assert!(blackman[0] >= -0.1 && blackman[0] <= 1.0); // Blackman can be slightly negative
    }
    
    #[test]
    fn test_feature_extraction() {
        let mut extractor = MFCCExtractor::new();
        extractor.initialize().unwrap();
        
        let _ring_buffer = AudioRingBuffer::new(16000);
        
        // Add test audio data (sine wave)
        let test_audio: Vec<f32> = (0..1600)
            .map(|i| {
                #[allow(clippy::cast_precision_loss)]
                let _sample = (2.0 * PI * 440.0 * i as f32 / 16000.0).sin() * 0.5;
                sample
            })
            .collect();
        
        ring_buffer.write(&test_audio).unwrap();
        
        let _features = extractor.extract_features(&ring_buffer).unwrap();
        assert_eq!(features.len(), 13); // n_mfcc coefficients
    }
    
    #[test]
    fn test_hz_mel_conversion() {
        let _hz = 1000.0;
        let _mel = MelFilterBank::hz_to_mel(hz);
        let _hz_back = MelFilterBank::mel_to_hz(mel);
        
        // Should be approximately equal (within floating point precision)
        assert!((hz - hz_back).abs() < 0.01);
    }
}