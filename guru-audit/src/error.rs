//! Error handling for the GURU Production Audit System
//!
//! This module provides comprehensive error types and handling mechanisms for all
//! audit system operations. All errors include detailed context, recovery options,
//! and forensic information for investigation and remediation.

use crate::types::{CheckpointId, PhaseId};
use std::fmt;
use thiserror::Error;

/// Result type alias for audit operations
pub type AuditResult<T> = std::result::Result<T, AuditError>;

/// Comprehensive error types for the audit system
#[derive(Error, Debug, Clone)]
pub enum AuditError {
    /// Critical system errors that threaten integrity or security
    #[error("Critical system error: {error_code} (threat level: {threat_level:?})")]
    CriticalSystemError {
        /// System error code for classification
        error_code: SystemErrorCode,
        /// Threat level assessment
        threat_level: ThreatLevel,
        /// Forensic data for investigation
        forensic_data: ForensicData,
        /// Available recovery options
        recovery_options: Vec<RecoveryOption>,
    },

    /// Phase execution errors with rollback capabilities
    #[error("Phase execution failed: {phase_id:?} - {failure_reason}")]
    PhaseExecutionError {
        /// Phase that failed
        phase_id: PhaseId,
        /// Detailed failure reason
        failure_reason: FailureReason,
        /// Checkpoint for rollback
        checkpoint_id: CheckpointId,
        /// Remediation steps
        remediation_steps: Vec<RemediationStep>,
    },

    /// Quality gate failures with zero-tolerance enforcement
    #[error("Quality gate failure: {gate_name} (expected: {expected_value}, actual: {actual_value})")]
    QualityGateFailure {
        /// Name of the failed quality gate
        gate_name: String,
        /// Expected value for the gate
        expected_value: QualityMetric,
        /// Actual measured value
        actual_value: QualityMetric,
        /// Detailed violation information
        violation_details: ViolationDetails,
    },

    /// Integration errors with external systems
    #[error("Integration error with {service_name}: {error_type:?} (retry {retry_count})")]
    IntegrationError {
        /// Name of the external service
        service_name: String,
        /// Type of integration error
        error_type: IntegrationErrorType,
        /// Number of retry attempts
        retry_count: u32,
        /// Last successful operation timestamp
        last_successful_operation: Option<std::time::SystemTime>,
    },

    /// Performance constraint violations
    #[error("Performance violation: {constraint_name} (required: {required_value:?}, measured: {measured_value:?})")]
    PerformanceViolation {
        /// Name of the performance constraint
        constraint_name: String,
        /// Required performance value
        required_value: PerformanceMetric,
        /// Measured performance value
        measured_value: PerformanceMetric,
        /// Statistical analysis of the violation
        statistical_analysis: StatisticalAnalysis,
    },

    /// Cryptographic operation failures
    #[error("Cryptographic operation failed: {operation} - {reason}")]
    CryptographicError {
        /// Type of cryptographic operation
        operation: CryptographicOperation,
        /// Failure reason
        reason: String,
        /// Key information (if applicable)
        key_info: Option<String>,
    },

    /// Configuration errors
    #[error("Configuration error: {parameter} - {reason}")]
    ConfigurationError {
        /// Configuration parameter that failed
        parameter: String,
        /// Reason for the failure
        reason: String,
        /// Suggested fix
        suggested_fix: Option<String>,
    },

    /// File system operation errors
    #[error("File system error: {operation} on {path} - {reason}")]
    FileSystemError {
        /// File system operation
        operation: String,
        /// File path involved
        path: String,
        /// Error reason
        reason: String,
    },

    /// Network operation errors
    #[error("Network error: {operation} - {reason}")]
    NetworkError {
        /// Network operation
        operation: String,
        /// Error reason
        reason: String,
        /// Retry information
        retry_info: Option<RetryInfo>,
    },

    /// Serialization/deserialization errors
    #[error("Serialization error: {format} - {reason}")]
    SerializationError {
        /// Data format (JSON, TOML, etc.)
        format: String,
        /// Error reason
        reason: String,
    },

    /// Timeout errors
    #[error("Operation timeout: {operation} (timeout: {timeout_ms}ms)")]
    TimeoutError {
        /// Operation that timed out
        operation: String,
        /// Timeout duration in milliseconds
        timeout_ms: u64,
    },

    /// Resource exhaustion errors
    #[error("Resource exhaustion: {resource} (limit: {limit}, requested: {requested})")]
    ResourceExhaustionError {
        /// Resource type
        resource: String,
        /// Resource limit
        limit: u64,
        /// Requested amount
        requested: u64,
    },
}

/// System error codes for classification
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SystemErrorCode {
    /// Memory corruption detected
    MemoryCorruption,
    /// Unauthorized access attempt
    UnauthorizedAccess,
    /// Cryptographic verification failure
    CryptographicFailure,
    /// System integrity violation
    IntegrityViolation,
    /// Resource exhaustion
    ResourceExhaustion,
    /// Configuration tampering
    ConfigurationTampering,
    /// Network security breach
    NetworkSecurityBreach,
    /// File system corruption
    FileSystemCorruption,
}

impl fmt::Display for SystemErrorCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SystemErrorCode::MemoryCorruption => write!(f, "MEMORY_CORRUPTION"),
            SystemErrorCode::UnauthorizedAccess => write!(f, "UNAUTHORIZED_ACCESS"),
            SystemErrorCode::CryptographicFailure => write!(f, "CRYPTOGRAPHIC_FAILURE"),
            SystemErrorCode::IntegrityViolation => write!(f, "INTEGRITY_VIOLATION"),
            SystemErrorCode::ResourceExhaustion => write!(f, "RESOURCE_EXHAUSTION"),
            SystemErrorCode::ConfigurationTampering => write!(f, "CONFIGURATION_TAMPERING"),
            SystemErrorCode::NetworkSecurityBreach => write!(f, "NETWORK_SECURITY_BREACH"),
            SystemErrorCode::FileSystemCorruption => write!(f, "FILE_SYSTEM_CORRUPTION"),
        }
    }
}

/// Threat level assessment
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ThreatLevel {
    /// Low threat - monitoring required
    Low,
    /// Medium threat - investigation required
    Medium,
    /// High threat - immediate action required
    High,
    /// Critical threat - system lockdown required
    Critical,
}

/// Forensic data for error investigation
#[derive(Debug, Clone)]
pub struct ForensicData {
    /// Error timestamp
    pub timestamp: std::time::SystemTime,
    /// System state snapshot
    pub system_state_hash: String,
    /// Execution trace
    pub execution_trace: Vec<String>,
    /// Memory usage at error time
    pub memory_usage: u64,
    /// CPU utilization at error time
    pub cpu_utilization: f64,
    /// Network activity log
    pub network_activity: Vec<String>,
    /// File system operations log
    pub file_system_operations: Vec<String>,
}

/// Recovery options for error handling
#[derive(Debug, Clone)]
pub enum RecoveryOption {
    /// Automatic retry with exponential backoff
    AutomaticRetry {
        /// Maximum retry attempts
        max_attempts: u32,
        /// Base delay in milliseconds
        base_delay_ms: u64,
    },
    /// Rollback to previous checkpoint
    RollbackToCheckpoint {
        /// Checkpoint identifier
        checkpoint_id: CheckpointId,
        /// Rollback description
        description: String,
    },
    /// Manual intervention required
    ManualIntervention {
        /// Required actions
        required_actions: Vec<String>,
        /// Contact information
        contact_info: String,
    },
    /// Safe mode activation
    SafeModeActivation {
        /// Safe mode configuration
        safe_mode_config: String,
        /// Reduced functionality description
        reduced_functionality: Vec<String>,
    },
}

/// Detailed failure reasons
#[derive(Debug, Clone)]
pub enum FailureReason {
    /// Dependency not satisfied
    DependencyNotSatisfied {
        /// Missing dependency
        dependency: String,
        /// Required version
        required_version: Option<String>,
    },
    /// Quality gate violation
    QualityGateViolation {
        /// Gate name
        gate_name: String,
        /// Violation count
        violation_count: u32,
    },
    /// Performance constraint violation
    PerformanceConstraintViolation {
        /// Constraint name
        constraint_name: String,
        /// Measured value
        measured_value: f64,
        /// Required value
        required_value: f64,
    },
    /// Resource unavailable
    ResourceUnavailable {
        /// Resource name
        resource_name: String,
        /// Availability status
        availability_status: String,
    },
    /// External service failure
    ExternalServiceFailure {
        /// Service name
        service_name: String,
        /// Service status
        service_status: String,
    },
    /// Configuration invalid
    ConfigurationInvalid {
        /// Configuration parameter
        parameter: String,
        /// Invalid value
        invalid_value: String,
    },
}

impl fmt::Display for FailureReason {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FailureReason::DependencyNotSatisfied { dependency, required_version } => {
                write!(f, "Dependency not satisfied: {} (required: {:?})", dependency, required_version)
            }
            FailureReason::QualityGateViolation { gate_name, violation_count } => {
                write!(f, "Quality gate violation: {} ({} violations)", gate_name, violation_count)
            }
            FailureReason::PerformanceConstraintViolation { constraint_name, measured_value, required_value } => {
                write!(f, "Performance constraint violation: {} (measured: {}, required: {})", constraint_name, measured_value, required_value)
            }
            FailureReason::ResourceUnavailable { resource_name, availability_status } => {
                write!(f, "Resource unavailable: {} (status: {})", resource_name, availability_status)
            }
            FailureReason::ExternalServiceFailure { service_name, service_status } => {
                write!(f, "External service failure: {} (status: {})", service_name, service_status)
            }
            FailureReason::ConfigurationInvalid { parameter, invalid_value } => {
                write!(f, "Configuration invalid: {} (value: {})", parameter, invalid_value)
            }
        }
    }
}

/// Remediation steps for error recovery
#[derive(Debug, Clone)]
pub struct RemediationStep {
    /// Step description
    pub description: String,
    /// Required actions
    pub actions: Vec<String>,
    /// Estimated time to complete
    pub estimated_time: std::time::Duration,
    /// Risk level of the remediation
    pub risk_level: RiskLevel,
}

/// Risk level for remediation steps
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RiskLevel {
    /// Low risk - safe to execute automatically
    Low,
    /// Medium risk - requires confirmation
    Medium,
    /// High risk - requires manual review
    High,
    /// Critical risk - requires expert intervention
    Critical,
}

/// Quality metrics for error reporting
#[derive(Debug, Clone, PartialEq)]
pub enum QualityMetric {
    /// Integer count (e.g., warnings, errors)
    Count(u32),
    /// Percentage value (e.g., test coverage)
    Percentage(f64),
    /// Duration value (e.g., execution time)
    Duration(std::time::Duration),
    /// Boolean value (e.g., compliance status)
    Boolean(bool),
    /// String value (e.g., version, status)
    String(String),
}

impl fmt::Display for QualityMetric {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            QualityMetric::Count(value) => write!(f, "{value}"),
            QualityMetric::Percentage(value) => write!(f, "{value:.2}%"),
            QualityMetric::Duration(value) => write!(f, "{value:?}"),
            QualityMetric::Boolean(value) => write!(f, "{value}"),
            QualityMetric::String(value) => write!(f, "{value}"),
        }
    }
}

/// Violation details for quality gate failures
#[derive(Debug, Clone)]
pub struct ViolationDetails {
    /// Violation severity
    pub severity: ViolationSeverity,
    /// Affected components
    pub affected_components: Vec<String>,
    /// Violation evidence
    pub evidence: Vec<String>,
    /// Impact assessment
    pub impact_assessment: String,
    /// Recommended actions
    pub recommended_actions: Vec<String>,
}

/// Violation severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ViolationSeverity {
    /// Minor violation - warning level
    Minor,
    /// Major violation - error level
    Major,
    /// Critical violation - system failure level
    Critical,
    /// Catastrophic violation - security breach level
    Catastrophic,
}

/// Integration error types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IntegrationErrorType {
    /// Authentication failure
    AuthenticationFailure,
    /// Authorization failure
    AuthorizationFailure,
    /// Network connectivity issue
    NetworkConnectivity,
    /// API rate limiting
    RateLimiting,
    /// Service unavailable
    ServiceUnavailable,
    /// Protocol error
    ProtocolError,
    /// Data format error
    DataFormatError,
    /// Timeout error
    Timeout,
}

/// Performance metrics for error reporting
#[derive(Debug, Clone, PartialEq)]
pub enum PerformanceMetric {
    /// Latency measurement
    Latency(std::time::Duration),
    /// Throughput measurement
    Throughput(f64),
    /// Memory usage
    MemoryUsage(u64),
    /// CPU utilization
    CpuUtilization(f64),
    /// Disk I/O rate
    DiskIoRate(f64),
    /// Network bandwidth
    NetworkBandwidth(f64),
}

impl fmt::Display for PerformanceMetric {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PerformanceMetric::Latency(value) => write!(f, "{value:?}"),
            PerformanceMetric::Throughput(value) => write!(f, "{value:.2} ops/sec"),
            PerformanceMetric::MemoryUsage(value) => write!(f, "{value} bytes"),
            PerformanceMetric::CpuUtilization(value) => write!(f, "{value:.2}%"),
            PerformanceMetric::DiskIoRate(value) => write!(f, "{value:.2} MB/s"),
            PerformanceMetric::NetworkBandwidth(value) => write!(f, "{value:.2} Mbps"),
        }
    }
}

/// Statistical analysis for performance violations
#[derive(Debug, Clone)]
pub struct StatisticalAnalysis {
    /// Mean value
    pub mean: f64,
    /// Standard deviation
    pub standard_deviation: f64,
    /// 95th percentile
    pub percentile_95: f64,
    /// 99th percentile
    pub percentile_99: f64,
    /// 99.9th percentile
    pub percentile_99_9: f64,
    /// Sample size
    pub sample_size: u64,
    /// Confidence interval
    pub confidence_interval: (f64, f64),
}

/// Cryptographic operation types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CryptographicOperation {
    /// Digital signature generation
    SignatureGeneration,
    /// Digital signature verification
    SignatureVerification,
    /// Hash computation
    HashComputation,
    /// Hash verification
    HashVerification,
    /// Key generation
    KeyGeneration,
    /// Key derivation
    KeyDerivation,
    /// Encryption
    Encryption,
    /// Decryption
    Decryption,
}

impl fmt::Display for CryptographicOperation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CryptographicOperation::SignatureGeneration => write!(f, "SIGNATURE_GENERATION"),
            CryptographicOperation::SignatureVerification => write!(f, "SIGNATURE_VERIFICATION"),
            CryptographicOperation::HashComputation => write!(f, "HASH_COMPUTATION"),
            CryptographicOperation::HashVerification => write!(f, "HASH_VERIFICATION"),
            CryptographicOperation::KeyGeneration => write!(f, "KEY_GENERATION"),
            CryptographicOperation::KeyDerivation => write!(f, "KEY_DERIVATION"),
            CryptographicOperation::Encryption => write!(f, "ENCRYPTION"),
            CryptographicOperation::Decryption => write!(f, "DECRYPTION"),
        }
    }
}

/// Retry information for network errors
#[derive(Debug, Clone)]
pub struct RetryInfo {
    /// Current retry attempt
    pub current_attempt: u32,
    /// Maximum retry attempts
    pub max_attempts: u32,
    /// Next retry delay
    pub next_retry_delay: std::time::Duration,
    /// Exponential backoff factor
    pub backoff_factor: f64,
}

impl AuditError {
    /// Check if the error is recoverable
    #[must_use]
    pub fn is_recoverable(&self) -> bool {
        match self {
            AuditError::CriticalSystemError { threat_level, .. } => {
                *threat_level < ThreatLevel::Critical
            }
            AuditError::PhaseExecutionError { .. } => true,
            AuditError::QualityGateFailure { .. } => true,
            AuditError::IntegrationError { .. } => true,
            AuditError::PerformanceViolation { .. } => true,
            AuditError::CryptographicError { .. } => false,
            AuditError::ConfigurationError { .. } => true,
            AuditError::FileSystemError { .. } => true,
            AuditError::NetworkError { .. } => true,
            AuditError::SerializationError { .. } => true,
            AuditError::TimeoutError { .. } => true,
            AuditError::ResourceExhaustionError { .. } => true,
        }
    }

    /// Get the severity level of the error
    #[must_use]
    pub fn severity(&self) -> ErrorSeverity {
        match self {
            AuditError::CriticalSystemError { threat_level, .. } => match threat_level {
                ThreatLevel::Low => ErrorSeverity::Warning,
                ThreatLevel::Medium => ErrorSeverity::Error,
                ThreatLevel::High => ErrorSeverity::Critical,
                ThreatLevel::Critical => ErrorSeverity::Fatal,
            },
            AuditError::PhaseExecutionError { .. } => ErrorSeverity::Error,
            AuditError::QualityGateFailure { .. } => ErrorSeverity::Error,
            AuditError::IntegrationError { .. } => ErrorSeverity::Warning,
            AuditError::PerformanceViolation { .. } => ErrorSeverity::Error,
            AuditError::CryptographicError { .. } => ErrorSeverity::Critical,
            AuditError::ConfigurationError { .. } => ErrorSeverity::Warning,
            AuditError::FileSystemError { .. } => ErrorSeverity::Warning,
            AuditError::NetworkError { .. } => ErrorSeverity::Warning,
            AuditError::SerializationError { .. } => ErrorSeverity::Warning,
            AuditError::TimeoutError { .. } => ErrorSeverity::Warning,
            AuditError::ResourceExhaustionError { .. } => ErrorSeverity::Error,
        }
    }
}

/// Error severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ErrorSeverity {
    /// Informational message
    Info,
    /// Warning - attention required
    Warning,
    /// Error - action required
    Error,
    /// Critical - immediate action required
    Critical,
    /// Fatal - system failure
    Fatal,
}