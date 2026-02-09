//! Runtime Self-Attestation System
//!
//! This module provides comprehensive runtime integrity monitoring with continuous
//! validation, threat detection, and forensic analysis capabilities. All operations
//! are designed for minimal performance overhead (<1% CPU) while maintaining
//! comprehensive security validation.
//!
//! ## Core Components
//!
//! - [`IntegrityMonitor`] - Real-time integrity monitoring with cryptographic verification
//! - [`ModuleValidator`] - Module validation with signature verification and tamper detection
//! - [`ConfigurationVerifier`] - Configuration integrity verification with policy compliance
//! - [`ThreatDetector`] - Threat detection with anomaly analysis and behavioral monitoring
//! - [`ForensicAnalyzer`] - Forensic analysis with evidence preservation and investigation
//!
//! ## Performance Requirements
//!
//! - Integrity monitoring: ≤1% CPU overhead during normal operation
//! - Module validation: ≤10ms per module verification
//! - Configuration verification: ≤50ms per configuration check
//! - Threat detection: ≤100ms per threat analysis
//! - Forensic analysis: ≤5 seconds per forensic investigation

pub mod types;
pub mod integrity_monitor;
pub mod module_validator;
pub mod configuration_verifier;
pub mod threat_detector;
pub mod forensic_analyzer;

#[cfg(test)]
mod property_tests;

pub use integrity_monitor::IntegrityMonitor;
pub use module_validator::ModuleValidator;
pub use configuration_verifier::ConfigurationVerifier;
pub use threat_detector::ThreatDetector;
pub use forensic_analyzer::ForensicAnalyzer;

pub use types::{
    IntegrityMonitoringConfig, IntegrityStatus, RuntimeAttestationResult,
    RuntimePerformanceMetrics, ModuleValidationResult, ValidationStatus,
    ConfigurationVerificationResult, PolicyComplianceStatus, PolicyViolation,
    ThreatDetectionResult, ThreatType, ThreatSeverity, ForensicAnalysisResult,
    ForensicEvidence, EvidenceType, SafeModeConfig,
};
