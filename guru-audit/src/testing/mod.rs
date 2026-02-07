//! # Testing Module
//!
//! Comprehensive testing framework with property-based validation and formal verification.
//! This module implements a zero-tolerance quality enforcement system with exhaustive testing
//! capabilities designed for civilization-scale software quality assurance.
//!
//! ## Core Components
//!
//! - **Unit Test Runner**: Comprehensive coverage analysis and branch testing
//! - **Property Test Engine**: Minimum 10,000 iterations with comprehensive shrinking
//! - **Security Test Framework**: Penetration testing and vulnerability assessment
//! - **Formal Verification Engine**: TLA+ model checking and proof certificate generation
//!
//! ## Maximum Engineering Standards
//!
//! All components follow zero-tolerance quality standards with:
//! - 100% test coverage with property-based testing
//! - Performance validation with timing constraint verification
//! - Security validation with penetration testing
//! - Formal verification with mathematical correctness guarantees

pub mod unit_test_runner;
pub mod property_test_engine;
pub mod security_test_framework;
pub mod formal_verification_engine;
pub mod types;

#[cfg(test)]
pub mod property_tests;

pub use unit_test_runner::UnitTestRunner;
pub use property_test_engine::PropertyTestEngine;
pub use security_test_framework::SecurityTestFramework;
pub use formal_verification_engine::FormalVerificationEngine;
pub use types::*;
