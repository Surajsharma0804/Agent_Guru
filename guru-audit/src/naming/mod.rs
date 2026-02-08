//! Naming System Module for GURU Production Audit System
//!
//! This module provides comprehensive file naming capabilities with semantic analysis,
//! reference updating, and compilation verification.
//!
//! MAXIMUM ENGINEERING MANDATE:
//! - Full semantic analysis engine with natural language processing
//! - Complete reference updating with dependency tracking
//! - Production-grade implementation for millions of files over 20+ years
//! - Zero tolerance for simplified or demo implementations

/// Reference updater with comprehensive dependency tracking and verification
pub mod reference_updater;
/// Naming validator with style guide enforcement and consistency checking
pub mod naming_validator;
/// Conflict resolver with hierarchical naming conventions and disambiguation
pub mod conflict_resolver;
/// Compilation verifier with automated testing and rollback capabilities
pub mod compilation_verifier;
/// Core data structures for naming system operations
pub mod types;

#[cfg(test)]
/// Property-based tests for naming system with 10,000+ iterations
pub mod property_tests;

pub use reference_updater::ReferenceUpdater;
pub use naming_validator::NamingValidator;
pub use conflict_resolver::ConflictResolver;
pub use compilation_verifier::CompilationVerifier;
pub use types::*;
