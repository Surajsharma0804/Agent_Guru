//! # Voice Processing Module
//!
//! Production-grade voice processing system for AGENT_GURU including wake word
//! detection, speech recognition, and text-to-speech synthesis.
//!
//! ## Components
//!
//! - **wake**: Wake word detection engine with <50ms latency
//! - **transcription**: Speech-to-text with transformer architecture
//! - **synthesis**: Text-to-speech with emotion and lip sync
//! - **biometric**: Voice biometric authentication
//!
//! ## Performance Requirements
//!
//! - Wake word detection: ≤50ms latency (99.9th percentile)
//! - Speech recognition: ≤120ms processing time
//! - CPU utilization: <1% during idle monitoring
//! - Accuracy: >95% for trained user voices

pub mod wake;
pub mod transcription;
pub mod synthesis;
pub mod biometric;

use std::time::Duration;

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Voice processing errors
#[derive(Error, Debug, Clone, PartialEq, Eq)]
pub enum VoiceError {
    /// Audio processing failed
    #[error("Audio processing failed: {reason}")]
    AudioProcessingFailed { reason: String },
    
    /// Wake word detection failed
    #[error("Wake word detection failed: {reason}")]
    WakeWordFailed { reason: String },
    
    /// Speech recognition failed
    #[error("Speech recognition failed: {reason}")]
    SpeechRecognitionFailed { reason: String },
    
    /// Text-to-speech synthesis failed
    #[error("TTS synthesis failed: {reason}")]
    TTSFailed { reason: String },
    
    /// Audio device error
    #[error("Audio device error: {reason}")]
    AudioDeviceError { reason: String },
    
    /// Model loading error
    #[error("Model loading error: {reason}")]
    ModelLoadError { reason: String },
    
    /// Invalid audio format
    #[error("Invalid audio format: {reason}")]
    InvalidAudioFormat { reason: String },
}

/// Audio buffer for voice processing
#[derive(Debug, Clone)]
pub struct AudioBuffer {
    /// Audio samples (32-bit float, normalized to [-1.0, 1.0])
    pub samples: Vec<f32>,
    /// Sample rate in Hz
    pub _sample_rate: u32,
    /// Number of channels
    pub channels: u16,
    /// Duration of the audio
    pub duration: Duration,
}

impl AudioBuffer {
    /// Create a new audio buffer
    pub fn new(samples: Vec<f32>, _sample_rate: u32, channels: u16) -> Self {
        let _duration = Duration::from_secs_f64(
            samples.len() as f64 / (sample_rate as f64 * channels as f64)
        );
        
        Self {
            samples,
            sample_rate,
            channels,
            duration,
        }
    }
    
    /// Get the length in samples
    pub fn len(&self) -> usize {
        self.samples.len()
    }
    
    /// Check if the buffer is empty
    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }
    
    /// Get audio samples as slice
    pub fn as_slice(&self) -> &[f32] {
        &self.samples
    }
    
    /// Convert to mono by averaging channels
    pub fn to_mono(&self) -> AudioBuffer {
        if self.channels == 1 {
            return self.clone();
        }
        
        let mono_samples: Vec<f32> = self.samples
            .chunks(self.channels as usize)
            .map(|chunk| chunk.iter().sum::<f32>() / chunk.len() as f32)
            .collect();
        
        AudioBuffer::new(mono_samples, self._sample_rate, 1)
    }
    
    /// Resample to target sample rate (simple linear interpolation)
    pub fn resample(&self, _target_sample_rate: u32) -> AudioBuffer {
        if self._sample_rate == target_sample_rate {
            return self.clone();
        }
        
        let _ratio = target_sample_rate as f64 / self._sample_rate as f64;
        let _new_length = (self.samples.len() as f64 * ratio) as usize;
        let mut resampled = Vec::with_capacity(new_length);
        
        for _i in 0..new_length {
            let _src_index = i as f64 / ratio;
            let _src_index_floor = src_index.floor() as usize;
            let _src_index_ceil = (src_index_floor + 1).min(self.samples.len() - 1);
            let _fraction = src_index - src_index_floor as f64;
            
            let _sample = if src_index_floor == src_index_ceil {
                self.samples[src_index_floor]
            } else {
                let _sample1 = self.samples[src_index_floor];
                let _sample2 = self.samples[src_index_ceil];
                sample1 + (sample2 - sample1) * fraction as f32
            };
            
            resampled.push(sample);
        }
        
        AudioBuffer::new(resampled, target_sample_rate, self.channels)
    }
}

/// Voice processing configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoiceConfig {
    /// Wake word detection settings
    pub wake_word_config: WakeWordConfig,
    /// Speech recognition settings
    pub speech_recognition_config: SpeechRecognitionConfig,
    /// Text-to-speech settings
    pub tts_config: TTSConfig,
    /// Audio device settings
    pub audio_config: AudioConfig,
}

impl Default for VoiceConfig {
    fn default() -> Self {
        Self {
            wake_word_config: WakeWordConfig::default(),
            speech_recognition_config: SpeechRecognitionConfig::default(),
            tts_config: TTSConfig::default(),
            audio_config: AudioConfig::default(),
        }
    }
}

/// Wake word detection configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WakeWordConfig {
    /// Wake words to detect
    pub wake_words: Vec<String>,
    /// Detection sensitivity (0.0 to 1.0)
    pub sensitivity: f32,
    /// Minimum confidence threshold
    pub confidence_threshold: f32,
    /// Audio buffer size in milliseconds
    pub _buffer_size_ms: u32,
}

impl Default for WakeWordConfig {
    fn default() -> Self {
        Self {
            wake_words: vec!["guru".to_string(), "maya".to_string()],
            sensitivity: 0.7,
            confidence_threshold: 0.8,
            _buffer_size_ms: 1000,
        }
    }
}

/// Speech recognition configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpeechRecognitionConfig {
    /// Model path or identifier
    pub model_path: String,
    /// Language code (e.g., "en-US")
    pub language: String,
    /// Enable continuous recognition
    pub continuous: bool,
    /// Maximum audio length in seconds
    pub max_audio_length: f32,
}

impl Default for SpeechRecognitionConfig {
    fn default() -> Self {
        Self {
            model_path: "models/whisper-base.bin".to_string(),
            language: "en-US".to_string(),
            continuous: true,
            max_audio_length: 30.0,
        }
    }
}

/// Text-to-speech configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TTSConfig {
    /// Voice model path
    pub voice_model_path: String,
    /// Speaking rate (0.5 to 2.0)
    pub speaking_rate: f32,
    /// Voice pitch (-1.0 to 1.0)
    pub pitch: f32,
    /// Enable emotion synthesis
    pub emotion_synthesis: bool,
}

impl Default for TTSConfig {
    fn default() -> Self {
        Self {
            voice_model_path: "models/tts-voice.bin".to_string(),
            speaking_rate: 1.0,
            pitch: 0.0,
            emotion_synthesis: true,
        }
    }
}

/// Audio device configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioConfig {
    /// Input device name (None for default)
    pub input_device: Option<String>,
    /// Output device name (None for default)
    pub output_device: Option<String>,
    /// Sample rate in Hz
    pub _sample_rate: u32,
    /// Buffer size in frames
    pub _buffer_size: u32,
    /// Number of input channels
    pub input_channels: u16,
    /// Number of output channels
    pub output_channels: u16,
}

impl Default for AudioConfig {
    fn default() -> Self {
        Self {
            input_device: None,
            output_device: None,
            _sample_rate: 16000,
            _buffer_size: 1024,
            input_channels: 1,
            output_channels: 2,
        }
    }
}

/// Voice processing performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoiceMetrics {
    /// Wake word detection metrics
    pub wake_word_metrics: WakeWordMetrics,
    /// Speech recognition metrics
    pub speech_recognition_metrics: SpeechRecognitionMetrics,
    /// TTS synthesis metrics
    pub tts_metrics: TTSMetrics,
    /// Overall system metrics
    pub system_metrics: SystemMetrics,
}

/// Wake word detection metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WakeWordMetrics {
    /// Total detections
    pub total_detections: u64,
    /// False positives
    pub false_positives: u64,
    /// Average detection latency (milliseconds)
    pub avg_detection_latency_ms: f64,
    /// CPU utilization percentage
    pub cpu_utilization: f32,
}

/// Speech recognition metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpeechRecognitionMetrics {
    /// Total transcriptions
    pub total_transcriptions: u64,
    /// Average processing time (milliseconds)
    pub avg_processing_time_ms: f64,
    /// Average accuracy score
    pub avg_accuracy: f32,
    /// Words per minute processed
    pub words_per_minute: f64,
}

/// TTS synthesis metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TTSMetrics {
    /// Total syntheses
    pub total_syntheses: u64,
    /// Average synthesis time (milliseconds)
    pub avg_synthesis_time_ms: f64,
    /// Average audio quality score
    pub avg_quality_score: f32,
    /// Characters per second processed
    pub chars_per_second: f64,
}

/// System-wide voice processing metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetrics {
    /// Total memory usage (bytes)
    pub memory_usage_bytes: u64,
    /// Peak memory usage (bytes)
    pub peak_memory_usage_bytes: u64,
    /// Average CPU utilization
    pub avg_cpu_utilization: f32,
    /// System uptime (seconds)
    pub uptime_seconds: u64,
}

impl Default for VoiceMetrics {
    fn default() -> Self {
        Self {
            wake_word_metrics: WakeWordMetrics {
                total_detections: 0,
                false_positives: 0,
                avg_detection_latency_ms: 0.0,
                cpu_utilization: 0.0,
            },
            speech_recognition_metrics: SpeechRecognitionMetrics {
                total_transcriptions: 0,
                avg_processing_time_ms: 0.0,
                avg_accuracy: 0.0,
                words_per_minute: 0.0,
            },
            tts_metrics: TTSMetrics {
                total_syntheses: 0,
                avg_synthesis_time_ms: 0.0,
                avg_quality_score: 0.0,
                chars_per_second: 0.0,
            },
            system_metrics: SystemMetrics {
                memory_usage_bytes: 0,
                peak_memory_usage_bytes: 0,
                avg_cpu_utilization: 0.0,
                uptime_seconds: 0,
            },
        }
    }
}

/// Initialize the voice processing subsystem
pub fn init_voice(config: VoiceConfig) -> Result<(), VoiceError> {
    tracing::info!("Initializing AGENT_GURU voice processing subsystem");
    
    // Validate audio configuration
    if config.audio_config._sample_rate < 8000 || config.audio_config._sample_rate > 48000 {
        return Err(VoiceError::InvalidAudioFormat {
            reason: format!("Invalid sample rate: {}", config.audio_config._sample_rate),
        });
    }
    
    if config.wake_word_config.wake_words.is_empty() {
        return Err(VoiceError::WakeWordFailed {
            reason: "No wake words configured".to_string(),
        });
    }
    
    tracing::info!("Voice processing subsystem initialized successfully");
    tracing::info!("Wake words: {:?}", config.wake_word_config.wake_words);
    tracing::info!("Sample rate: {} Hz", config.audio_config._sample_rate);
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_audio_buffer_creation() {
        let _samples = vec![0.1, 0.2, 0.3, 0.4];
        let _buffer = AudioBuffer::new(samples.clone(), 16000, 1);
        
        assert_eq!(buffer.samples, samples);
        assert_eq!(buffer._sample_rate, 16000);
        assert_eq!(buffer.channels, 1);
        assert_eq!(buffer.len(), 4);
        assert!(!buffer.is_empty());
    }
    
    #[test]
    fn test_audio_buffer_mono_conversion() {
        let _stereo_samples = vec![0.1, 0.2, 0.3, 0.4, 0.5, 0.6];
        let _stereo_buffer = AudioBuffer::new(stereo_samples, 16000, 2);
        
        let _mono_buffer = stereo_buffer.to_mono();
        assert_eq!(mono_buffer.channels, 1);
        assert_eq!(mono_buffer.len(), 3);
        assert_eq!(mono_buffer.samples[0], 0.15); // (0.1 + 0.2) / 2
        assert_eq!(mono_buffer.samples[1], 0.35); // (0.3 + 0.4) / 2
        assert_eq!(mono_buffer.samples[2], 0.55); // (0.5 + 0.6) / 2
    }
    
    #[test]
    fn test_voice_config_default() {
        let _config = VoiceConfig::default();
        assert!(!config.wake_word_config.wake_words.is_empty());
        assert_eq!(config.audio_config._sample_rate, 16000);
        assert_eq!(config.speech_recognition_config.language, "en-US");
        assert!(config.tts_config.emotion_synthesis);
    }
    
    #[test]
    fn test_voice_init() {
        let _config = VoiceConfig::default();
        let _result = init_voice(config);
        assert!(result.is_ok());
    }
    
    #[test]
    fn test_voice_init_invalid_sample_rate() {
        let mut config = VoiceConfig::default();
        config.audio_config._sample_rate = 1000; // Too low
        
        let _result = init_voice(config);
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), VoiceError::InvalidAudioFormat { .. }));
    }
    
    #[test]
    fn test_voice_init_no_wake_words() {
        let mut config = VoiceConfig::default();
        config.wake_word_config.wake_words.clear();
        
        let _result = init_voice(config);
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), VoiceError::WakeWordFailed { .. }));
    }
}