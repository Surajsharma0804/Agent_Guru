//! # GURU Production Audit System
//!
//! A comprehensive, zero-tolerance quality enforcement framework designed to ensure
//! absolute production readiness for the AGENT_GURU project. This system implements
//! a mandatory 10-phase audit process with mathematical guarantees, cryptographic
//! verification, and formal proof requirements.
//!
//! ## Architecture Overview
//!
//! The audit system follows maximum engineering principles with:
//! - Zero tolerance for warnings, errors, or compromises
//! - Cryptographic verification using Ed25519 signatures and SHA-256 checksums
//! - Formal verification with TLA+ specifications
//! - Property-based testing with 10,000+ iterations per property
//! - Real-time performance monitoring with 99.9th percentile guarantees
//!
//! ## Core Components
//!
//! - [`core::controller`] - Audit orchestration with formal verification
//! - [`core::phase_manager`] - Sequential phase execution with checkpoints
//! - [`core::quality_gates`] - Mathematical quality validation
//! - [`core::checkpoint`] - Cryptographic state management
//! - [`core::metrics`] - Performance monitoring and analytics

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod core;
pub mod types;
pub mod error;
pub mod crypto;
pub mod config;
pub mod inventory;
/// Humanized naming system for semantic file naming with comprehensive reference updating
pub mod naming;
pub mod purge;
pub mod integration;
pub mod testing;
pub mod performance;
/// Formal verification system with TLA+ integration and mathematical correctness guarantees
pub mod formal;
/// Reproducible build proof system with determinism enforcement and supply chain security
pub mod build;
/// Runtime self-attestation system with continuous integrity monitoring and threat detection
pub mod runtime;

/// Final certification system with quality validation, compliance checking, and executive reporting
pub mod certification;

/// Comprehensive monitoring and observability system with privacy-preserving monitoring
pub mod observability;

/// Automated remediation and recovery system with comprehensive issue detection and fixing
pub mod remediation;

/// Comprehensive system validation for verifying all audit components are integrated correctly
pub mod validation;

// Re-export core types for convenience
pub use crate::core::{
    controller::AuditController,
    phase_manager::PhaseManager,
    quality_gates::QualityGates,
    checkpoint::CheckpointManager,
    metrics::MetricsCollector,
};

pub use crate::types::{
    AuditConfig, AuditResult, PhaseResult, QualityMetrics,
    PerformanceMetrics, SecurityMetrics, ComplianceStatus,
};

pub use crate::error::{AuditError, AuditResult as Result};

/// Current version of the GURU Production Audit System
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Minimum supported Rust version
pub const MSRV: &str = "1.75";

/// Maximum engineering mandate - zero tolerance policy
pub const ZERO_TOLERANCE_POLICY: &str = "NO MINIMALISM, NO SHORTCUTS, NO COMPROMISES";