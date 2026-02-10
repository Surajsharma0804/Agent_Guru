//! Automated Remediation and Recovery System
//!
//! This module provides comprehensive automated remediation capabilities for common
//! issues detected during the audit process. The system includes issue detection,
//! automatic fixing with verification, rollback capabilities, and escalation handling
//! for manual intervention when automatic remediation is not possible or safe.
//!
//! ## Core Components
//!
//! - [`issue_detector`] - Comprehensive problem identification and classification
//! - [`auto_fixer`] - Automated fixing with proven remediation patterns
//! - [`verification_engine`] - Fix verification and testing before applying changes
//! - [`rollback_manager`] - Complete state restoration and recovery capabilities
//! - [`escalation_handler`] - Manual intervention coordination and context provision
//!
//! ## Maximum Engineering Principles
//!
//! - **NO MINIMALISM:** Full automated remediation with comprehensive recovery
//! - **NO SHORTCUTS:** Complete issue detection, automatic fixing, verification, rollback
//! - **PRODUCTION STANDARDS:** Handle automated remediation for millions of issues over 20+ years
//!
//! ## Safety Guarantees
//!
//! - All remediation operations create checkpoints before execution
//! - Comprehensive verification before applying any changes
//! - Automatic rollback on verification failure
//! - Risk-based escalation for high-risk operations
//! - Complete audit trail of all remediation actions

pub mod types;
pub mod issue_detector;
pub mod verification_engine;
pub mod rollback_manager;
pub mod escalation_handler;

#[cfg(test)]
pub mod property_tests;

pub use types::{
    DetectedIssue, EscalationRequest, IssueType, IssueSeverity, RemediationConfig,
    RemediationId, RemediationResult, RemediationStatistics, RemediationStatus, RollbackResult,
    RollbackStatus, StateSnapshot,
};

pub use issue_detector::IssueDetector;
pub use verification_engine::VerificationEngine;
pub use rollback_manager::RollbackManager;
pub use escalation_handler::EscalationHandler;
