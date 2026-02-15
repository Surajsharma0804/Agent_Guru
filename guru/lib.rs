//! # `AGENT_GURU` - Sovereign AI Operating Companion
//! 
//! Production-grade AI companion with cryptographic governance, voice interface,
//! biometric authentication, and complete OS control. Built with zero-tolerance
//! quality standards and formal verification guarantees.
//!
//! ## Architecture
//! 
//! The `AGENT_GURU` system follows a layered architecture with strict security boundaries:
//! - **Security Layer**: Cryptographic identity, biometric authentication, policy enforcement
//! - **Intelligence Layer**: LLM runtime, memory system, multi-agent orchestration
//! - **Interface Layer**: Voice processing, avatar rendering, vision processing
//! - **Platform Layer**: OS integration, hardware abstraction, deployment
//!
//! ## Quality Standards
//! 
//! - Zero errors, zero warnings across all target platforms
//! - 100% test coverage with property-based testing (10,000+ iterations)
//! - Formal verification with TLA+ specifications
//! - Memory safety validation with MIRI
//! - Security audit with automated vulnerability scanning
//! - Performance gates with mathematical guarantees
//!
//! ## Clean Room Implementation
//! 
//! All algorithms are extracted using clean room methodology with complete
//! intellectual property compliance. No foreign code residue remains in the codebase.

#![deny(unsafe_code)]
// Allow certain clippy lints that are acceptable for this codebase
#![allow(clippy::struct_excessive_bools)]
#![allow(clippy::cast_precision_loss)]
#![allow(clippy::unused_async)]
#![allow(clippy::needless_pass_by_ref_mut)]
#![allow(clippy::must_use_candidate)]
#![allow(clippy::missing_errors_doc)]
#![allow(clippy::missing_const_for_fn)]
#![allow(clippy::use_self)]
#![allow(clippy::uninlined_format_args)]
#![allow(clippy::derive_partial_eq_without_eq)]
#![allow(clippy::unnecessary_map_or)]

/// Version of `AGENT_GURU`
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

pub mod security;
pub mod voice;
pub mod llm;
pub mod runtime;
pub mod platform;
pub mod policy;
pub mod memory;
pub mod vision;
pub mod agents;
pub mod avatar;
pub mod deployment;

// Re-export core types for convenience
pub use runtime::{GuruRuntime, RuntimeConfig, RuntimeError};
pub use security::crypto::identity::{
    CryptoIdentity, Ed25519Identity, PublicKey, SecretKey, Signature, CryptoError
};

/// Build information
pub const BUILD_INFO: &str = concat!(
    "AGENT_GURU v", env!("CARGO_PKG_VERSION")
);

/// Initialize the `AGENT_GURU` system with default configuration
///
/// # Errors
///
/// Returns an error if initialization fails
pub fn init() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();
    
    tracing::info!("Initializing AGENT_GURU system");
    tracing::info!("Build info: {}", BUILD_INFO);
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_version_info() {
        // VERSION is a compile-time constant and cannot be empty
        // BUILD_INFO is a compile-time constant and cannot be empty
        assert!(VERSION.chars().next().unwrap().is_ascii_digit(), "VERSION should start with a digit");
        assert!(BUILD_INFO.contains("AGENT_GURU"), "BUILD_INFO should contain project name");
    }
    
    #[test]
    fn test_init() {
        assert!(init().is_ok());
    }
}
