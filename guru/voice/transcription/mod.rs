//! # Speech Recognition Transcription Module
//! 
//! Production-grade speech recognition with transformer decoder, KV-cache streaming,
//! and log-mel spectrogram generation. All components are designed for real-time
//! performance with formal verification guarantees.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
pub mod decoder;
pub mod kv_cache;
pub mod spectrogram;

pub use decoder::{
    TransformerDecoder, DecoderConfig, DecoderError, DecoderResult,
    TokenData, GeneratedSequence, DecoderMetrics
};

pub use kv_cache::{
    StreamingKVCache, KVCacheConfig, KVCacheError, KVCacheResult,
    KVCacheConfigBuilder, EvictionPolicy, KVCacheMetrics
};

pub use spectrogram::{
    SpectrogramGenerator, SpectrogramConfig, SpectrogramError, SpectrogramResult,
    WindowType, MelFilterBank, FFTProcessor, Complex
};