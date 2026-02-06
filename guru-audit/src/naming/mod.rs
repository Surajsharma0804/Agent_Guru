// Naming System Module for GURU Production Audit System
//
// This module provides comprehensive file naming capabilities with semantic analysis,
// reference updating, and compilation verification.
//
// MAXIMUM ENGINEERING MANDATE:
// - Full semantic analysis engine with natural language processing
// - Complete reference updating with dependency tracking
// - Production-grade implementation for millions of files over 20+ years
// - Zero tolerance for simplified or demo implementations

pub mod reference_updater;
pub mod naming_validator;
pub mod conflict_resolver;
pub mod compilation_verifier;
pub mod types;

#[cfg(test)]
pub mod property_tests;

pub use reference_updater::ReferenceUpdater;
pub use naming_validator::NamingValidator;
pub use conflict_resolver::ConflictResolver;
pub use compilation_verifier::CompilationVerifier;
pub use types::*;
