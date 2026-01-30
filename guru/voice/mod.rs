//! # Voice Processing Module
//! 
//! Production-grade voice processing with wake word detection and speech recognition.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![allow(missing_docs, dead_code)]

pub mod wake;
pub mod transcription;

pub use wake::{
    WakeWordEngine, MFCCWakeWordEngine, WakeWordEvent, WakeWordMetrics, WakeWordError
};

pub use transcription::{
    TransformerDecoder, DecoderConfig, DecoderError, DecoderResult,
    StreamingKVCache, KVCacheConfig, KVCacheError, KVCacheResult,
    SpectrogramGenerator, SpectrogramConfig, SpectrogramError, SpectrogramResult,
    TokenData, GeneratedSequence, WindowType
};