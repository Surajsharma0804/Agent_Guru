//! Core type definitions for the GURU Production Audit System
//!
//! This module defines all fundamental data structures used throughout the audit system,
//! including configuration, results, metrics, and state management types. All types are
//! designed for production-grade operation with cryptographic verification and formal
//! specification compliance.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};
use uuid::Uuid;

/// Unique identifier for audit cycles
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct AuditId(pub Uuid);

impl AuditId {
    /// Generate a new unique audit identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for AuditId {
    fn default() -> Self {
        Self::new()
    }
}

/// Phase identifier for the 10 mandatory audit phases
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PhaseId {
    /// Phase 1: Full Inventory Generation System
    Inventory = 1,
    /// Phase 2: Humanized Naming Enforcement System
    Naming = 2,
    /// Phase 3: Dead Code and File Purge System
    Purge = 3,
    /// Phase 4: Integration Verification System
    Integration = 4,
    /// Phase 5: Hardcore Test Battery Execution
    Testing = 5,
    /// Phase 6: Performance and Complexity Audit
    Performance = 6,
    /// Phase 7: Formal Model Verification System
    FormalVerification = 7,
    /// Phase 8: Reproducible Build Proof System
    ReproducibleBuild = 8,
    /// Phase 9: Runtime Self-Attestation System
    RuntimeAttestation = 9,
    /// Phase 10: Final Certification System
    FinalCertification = 10,
}

impl PhaseId {
    /// Get all phases in execution order
    #[must_use]
    pub const fn all_phases() -> [PhaseId; 10] {
        [
            PhaseId::Inventory,
            PhaseId::Naming,
            PhaseId::Purge,
            PhaseId::Integration,
            PhaseId::Testing,
            PhaseId::Performance,
            PhaseId::FormalVerification,
            PhaseId::ReproducibleBuild,
            PhaseId::RuntimeAttestation,
            PhaseId::FinalCertification,
        ]
    }

    /// Get the next phase in sequence, if any
    #[must_use]
    pub const fn next_phase(self) -> Option<PhaseId> {
        match self {
            PhaseId::Inventory => Some(PhaseId::Naming),
            PhaseId::Naming => Some(PhaseId::Purge),
            PhaseId::Purge => Some(PhaseId::Integration),
            PhaseId::Integration => Some(PhaseId::Testing),
            PhaseId::Testing => Some(PhaseId::Performance),
            PhaseId::Performance => Some(PhaseId::FormalVerification),
            PhaseId::FormalVerification => Some(PhaseId::ReproducibleBuild),
            PhaseId::ReproducibleBuild => Some(PhaseId::RuntimeAttestation),
            PhaseId::RuntimeAttestation => Some(PhaseId::FinalCertification),
            PhaseId::FinalCertification => None,
        }
    }

    /// Get the previous phase in sequence, if any
    #[must_use]
    pub const fn previous_phase(self) -> Option<PhaseId> {
        match self {
            PhaseId::Inventory => None,
            PhaseId::Naming => Some(PhaseId::Inventory),
            PhaseId::Purge => Some(PhaseId::Naming),
            PhaseId::Integration => Some(PhaseId::Purge),
            PhaseId::Testing => Some(PhaseId::Integration),
            PhaseId::Performance => Some(PhaseId::Testing),
            PhaseId::FormalVerification => Some(PhaseId::Performance),
            PhaseId::ReproducibleBuild => Some(PhaseId::FormalVerification),
            PhaseId::RuntimeAttestation => Some(PhaseId::ReproducibleBuild),
            PhaseId::FinalCertification => Some(PhaseId::RuntimeAttestation),
        }
    }

    /// Get human-readable phase name
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            PhaseId::Inventory => "Full Inventory Generation System",
            PhaseId::Naming => "Humanized Naming Enforcement System",
            PhaseId::Purge => "Dead Code and File Purge System",
            PhaseId::Integration => "Integration Verification System",
            PhaseId::Testing => "Hardcore Test Battery Execution",
            PhaseId::Performance => "Performance and Complexity Audit",
            PhaseId::FormalVerification => "Formal Model Verification System",
            PhaseId::ReproducibleBuild => "Reproducible Build Proof System",
            PhaseId::RuntimeAttestation => "Runtime Self-Attestation System",
            PhaseId::FinalCertification => "Final Certification System",
        }
    }
}

/// Execution status for audit phases and overall audit cycles
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ExecutionStatus {
    /// Phase has not been started
    NotStarted,
    /// Phase is currently executing with progress percentage
    InProgress { 
        /// Current progress as percentage (0.0 to 100.0)
        progress_percentage: f64 
    },
    /// Phase completed successfully or with failure
    Completed { 
        /// Whether the phase completed successfully
        success: bool 
    },
    /// Phase failed with error and recovery options
    Failed {
        /// Error message describing the failure
        error: String,
        /// Available recovery options
        recovery_options: Vec<String>,
    },
    /// Phase was rolled back to a previous checkpoint
    RolledBack {
        /// Checkpoint identifier that was rolled back to
        checkpoint_id: String,
        /// Reason for the rollback
        reason: String,
    },
}

/// Comprehensive audit configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditConfig {
    /// Unique identifier for this audit configuration
    pub audit_id: AuditId,
    /// Target repository configuration
    pub target_repository: RepositoryConfig,
    /// Quality gate configuration with zero-tolerance enforcement
    pub quality_gates: QualityGateConfig,
    /// Performance requirements with mathematical guarantees
    pub performance_requirements: PerformanceRequirements,
    /// Security requirements with cryptographic verification
    pub security_requirements: SecurityRequirements,
    /// Formal verification specifications
    pub formal_verification_specs: Vec<String>,
    /// GitHub integration configuration
    pub github_integration: Option<GitHubIntegrationConfig>,
    /// Notification settings for alerts and reports
    pub notification_settings: NotificationSettings,
}

/// Repository configuration for audit target
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepositoryConfig {
    /// Root path of the repository
    pub root_path: PathBuf,
    /// Branch to audit (default: main)
    pub branch: String,
    /// Commit hash for specific version auditing
    pub commit_hash: Option<String>,
    /// Excluded paths from audit
    pub excluded_paths: Vec<PathBuf>,
    /// Included file patterns
    pub included_patterns: Vec<String>,
}

/// Quality gate configuration with zero-tolerance enforcement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityGateConfig {
    /// Enforce zero compiler warnings across all platforms
    pub zero_compiler_warnings: bool,
    /// Enforce zero runtime errors in all execution paths
    pub zero_runtime_errors: bool,
    /// Enforce zero unused files after dead code elimination
    pub zero_unused_files: bool,
    /// Enforce zero ambiguous names after humanized naming
    pub zero_ambiguous_names: bool,
    /// Require 100% test pass rate
    pub hundred_percent_test_pass: bool,
    /// Minimum property test iterations (default: 10,000)
    pub property_test_iterations: u32,
    /// Enforce performance gate requirements
    pub performance_gate_enforcement: bool,
    /// Require formal verification for critical components
    pub formal_verification_required: bool,
}

impl Default for QualityGateConfig {
    fn default() -> Self {
        Self {
            zero_compiler_warnings: true,
            zero_runtime_errors: true,
            zero_unused_files: true,
            zero_ambiguous_names: true,
            hundred_percent_test_pass: true,
            property_test_iterations: 10_000,
            performance_gate_enforcement: true,
            formal_verification_required: true,
        }
    }
}

/// Performance requirements with mathematical guarantees
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceRequirements {
    /// Phase transition latency requirement (≤100ms)
    pub phase_transition_latency_ms: u64,
    /// Dependency validation requirement (≤50ms)
    pub dependency_validation_ms: u64,
    /// Audit trail generation requirement (≤10ms per entry)
    pub audit_trail_generation_ms: u64,
    /// Rollback operation requirement (≤5 seconds)
    pub rollback_operation_seconds: u64,
    /// Percentile guarantee level (99.9th percentile)
    pub percentile_guarantee: f64,
}

impl Default for PerformanceRequirements {
    fn default() -> Self {
        Self {
            phase_transition_latency_ms: 100,
            dependency_validation_ms: 50,
            audit_trail_generation_ms: 10,
            rollback_operation_seconds: 5,
            percentile_guarantee: 99.9,
        }
    }
}

/// Security requirements with cryptographic verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityRequirements {
    /// Enforce capability-based security model
    pub capability_based_security: bool,
    /// Require encryption for all sensitive data
    pub encryption_everywhere: bool,
    /// Enforce zero telemetry and tracking
    pub zero_telemetry: bool,
    /// Require formal verification for security properties
    pub formal_verification_required: bool,
    /// Enforce clean-room development compliance
    pub clean_room_compliance: bool,
    /// Require cryptographic signatures for all operations
    pub cryptographic_signatures: bool,
    /// Require supply chain attestation
    pub supply_chain_attestation: bool,
    /// Enable runtime integrity monitoring
    pub runtime_integrity_monitoring: bool,
}

impl Default for SecurityRequirements {
    fn default() -> Self {
        Self {
            capability_based_security: true,
            encryption_everywhere: true,
            zero_telemetry: true,
            formal_verification_required: true,
            clean_room_compliance: true,
            cryptographic_signatures: true,
            supply_chain_attestation: true,
            runtime_integrity_monitoring: true,
        }
    }
}

/// GitHub integration configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitHubIntegrationConfig {
    /// Repository URL
    pub repository_url: String,
    /// Access token for API calls
    pub access_token: String,
    /// Branch protection rules
    pub branch_protection_rules: BranchProtectionRules,
    /// Required status checks
    pub required_status_checks: Vec<String>,
    /// Enable automatic PR validation
    pub automatic_pr_validation: bool,
    /// Require commit signature verification
    pub commit_signature_verification: bool,
    /// Enable CI/CD pipeline integration
    pub ci_cd_pipeline_integration: bool,
}

/// Branch protection rules for GitHub integration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BranchProtectionRules {
    /// Require audit completion before merge
    pub require_audit_completion: bool,
    /// Require signed commits
    pub require_signed_commits: bool,
    /// Required number of PR reviews
    pub require_pr_reviews: u32,
    /// Dismiss stale reviews on new commits
    pub dismiss_stale_reviews: bool,
    /// Require status checks to pass
    pub require_status_checks: bool,
    /// Restrict pushes to specific users/teams
    pub restrict_pushes: bool,
}

/// Notification settings for alerts and reports
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationSettings {
    /// Email addresses for notifications
    pub email_addresses: Vec<String>,
    /// Webhook URLs for real-time notifications
    pub webhook_urls: Vec<String>,
    /// Slack integration configuration
    pub slack_config: Option<SlackConfig>,
    /// Notification levels (error, warning, info)
    pub notification_levels: Vec<String>,
}

/// Slack integration configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackConfig {
    /// Slack webhook URL
    pub webhook_url: String,
    /// Channel for notifications
    pub channel: String,
    /// Bot username
    pub username: String,
}

/// Phase execution result with comprehensive metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseResult {
    /// Phase identifier
    pub phase_id: PhaseId,
    /// Execution status
    pub execution_status: ExecutionStatus,
    /// Phase start time
    pub start_time: SystemTime,
    /// Phase end time (if completed)
    pub end_time: Option<SystemTime>,
    /// Phase execution metrics
    pub metrics: PhaseMetrics,
    /// Generated artifacts
    pub artifacts: Vec<String>,
    /// Quality gates that passed
    pub quality_gates_passed: Vec<String>,
    /// Quality gates that failed
    pub quality_gates_failed: Vec<QualityGateFailure>,
    /// Dependencies for next phase
    pub next_phase_dependencies: Vec<String>,
}

/// Phase-specific metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseMetrics {
    /// Execution duration
    pub execution_duration: Duration,
    /// Memory usage peak (bytes)
    pub memory_usage_peak: u64,
    /// CPU utilization percentage
    pub cpu_utilization: f64,
    /// Files processed count
    pub files_processed: u64,
    /// Errors encountered count
    pub errors_encountered: u64,
    /// Warnings generated count
    pub warnings_generated: u64,
}

/// Quality gate failure details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityGateFailure {
    /// Gate name that failed
    pub gate_name: String,
    /// Expected value
    pub expected_value: String,
    /// Actual value
    pub actual_value: String,
    /// Detailed failure reason
    pub failure_reason: String,
    /// Remediation steps
    pub remediation_steps: Vec<String>,
}

/// Comprehensive audit result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditResult {
    /// Audit identifier
    pub audit_id: AuditId,
    /// Overall audit status
    pub overall_status: ExecutionStatus,
    /// Results for each phase
    pub phase_results: Vec<PhaseResult>,
    /// Overall quality metrics
    pub quality_metrics: QualityMetrics,
    /// Performance metrics
    pub performance_metrics: PerformanceMetrics,
    /// Security metrics
    pub security_metrics: SecurityMetrics,
    /// Compliance status
    pub compliance_status: ComplianceStatus,
    /// Final certification (if successful)
    pub certification: Option<FinalCertification>,
    /// Total audit duration
    pub audit_duration: Duration,
    /// Resource utilization summary
    pub resource_utilization: ResourceUtilization,
}

/// Quality metrics with zero-tolerance enforcement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityMetrics {
    /// Compiler warnings count (must be 0)
    pub compiler_warnings: u32,
    /// Runtime errors count (must be 0)
    pub runtime_errors: u32,
    /// Unused files count (must be 0)
    pub unused_files: u32,
    /// Ambiguous names count (must be 0)
    pub ambiguous_names: u32,
    /// Test pass rate (must be 100.0)
    pub test_pass_rate: f64,
    /// Code coverage percentage (must be 100.0)
    pub code_coverage: f64,
    /// Property test iterations completed
    pub property_test_iterations: u32,
    /// Formal verification proofs generated
    pub formal_verification_proofs: u32,
    /// Security vulnerabilities found (must be 0)
    pub security_vulnerabilities: u32,
}

/// Performance metrics with mathematical guarantees
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    /// Phase transition latencies (99.9th percentile)
    pub phase_transition_latencies: HashMap<PhaseId, Duration>,
    /// Dependency validation times
    pub dependency_validation_times: Vec<Duration>,
    /// Audit trail generation times
    pub audit_trail_generation_times: Vec<Duration>,
    /// Rollback operation times
    pub rollback_operation_times: Vec<Duration>,
    /// Memory usage statistics
    pub memory_usage_stats: MemoryUsageStats,
    /// CPU utilization statistics
    pub cpu_utilization_stats: CpuUtilizationStats,
}

/// Memory usage statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryUsageStats {
    /// Peak memory usage (bytes)
    pub peak_usage: u64,
    /// Average memory usage (bytes)
    pub average_usage: u64,
    /// Memory usage 99.9th percentile (bytes)
    pub percentile_99_9: u64,
}

/// CPU utilization statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CpuUtilizationStats {
    /// Peak CPU utilization (percentage)
    pub peak_utilization: f64,
    /// Average CPU utilization (percentage)
    pub average_utilization: f64,
    /// CPU utilization 99.9th percentile (percentage)
    pub percentile_99_9: f64,
}

/// Security metrics with cryptographic verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityMetrics {
    /// Cryptographic operations performed
    pub cryptographic_operations: u64,
    /// Signature verifications completed
    pub signature_verifications: u64,
    /// Checksum validations performed
    pub checksum_validations: u64,
    /// Security violations detected (must be 0)
    pub security_violations: u32,
    /// Capability-based access control checks
    pub capability_checks: u64,
    /// Integrity attestations generated
    pub integrity_attestations: u64,
}

/// Compliance status with regulatory requirements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceStatus {
    /// Clean-room methodology compliance
    pub clean_room_compliance: bool,
    /// Intellectual property compliance
    pub intellectual_property_compliance: bool,
    /// License compliance verification
    pub license_compliance: bool,
    /// Supply chain attestation compliance
    pub supply_chain_compliance: bool,
    /// Security compliance verification
    pub security_compliance: bool,
    /// Performance compliance verification
    pub performance_compliance: bool,
}

/// Final certification with cryptographic signatures
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FinalCertification {
    /// Certification identifier
    pub certification_id: String,
    /// Certification timestamp
    pub certification_timestamp: DateTime<Utc>,
    /// Cryptographic signature (Ed25519)
    pub cryptographic_signature: Vec<u8>,
    /// Certificate authority information
    pub certificate_authority: String,
    /// Certification validity period
    pub validity_period: Duration,
    /// Certification scope and coverage
    pub certification_scope: Vec<String>,
}

/// Resource utilization summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceUtilization {
    /// Total CPU time used
    pub total_cpu_time: Duration,
    /// Peak memory usage
    pub peak_memory_usage: u64,
    /// Disk I/O operations
    pub disk_io_operations: u64,
    /// Network operations (if any)
    pub network_operations: u64,
    /// Parallel processing efficiency
    pub parallel_processing_efficiency: f64,
}

/// Checkpoint identifier for state management
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CheckpointId(pub Uuid);

impl CheckpointId {
    /// Generate a new unique checkpoint identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for CheckpointId {
    fn default() -> Self {
        Self::new()
    }
}

/// Audit context for phase execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditContext {
    /// Current audit configuration
    pub config: AuditConfig,
    /// Previous phase results
    pub previous_results: Vec<PhaseResult>,
    /// Current system state
    pub system_state: SystemState,
    /// Execution environment information
    pub execution_environment: ExecutionEnvironment,
}

/// System state snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemState {
    /// Repository state hash
    pub repository_hash: String,
    /// File system state
    pub file_system_state: HashMap<PathBuf, String>,
    /// Environment variables
    pub environment_variables: HashMap<String, String>,
    /// System timestamp
    pub timestamp: SystemTime,
}

/// Execution environment information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionEnvironment {
    /// Operating system information
    pub operating_system: String,
    /// Architecture information
    pub architecture: String,
    /// Rust version
    pub rust_version: String,
    /// Available CPU cores
    pub cpu_cores: u32,
    /// Available memory (bytes)
    pub available_memory: u64,
}