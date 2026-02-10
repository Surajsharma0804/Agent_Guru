//! Type definitions for the Automated Remediation and Recovery System
//!
//! This module defines all data structures for automated issue detection, fixing,
//! verification, and rollback operations. All types are designed for production-grade
//! operation with comprehensive safety validation and state restoration capabilities.

use crate::types::{CheckpointId, PhaseId};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};
use uuid::Uuid;

/// Unique identifier for remediation operations
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct RemediationId(pub Uuid);

impl RemediationId {
    /// Generate a new unique remediation identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for RemediationId {
    fn default() -> Self {
        Self::new()
    }
}

/// Issue classification for automated detection
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum IssueType {
    /// Code quality issues (formatting, style violations)
    CodeQuality,
    /// Dependency conflicts and version mismatches
    DependencyConflict,
    /// Import statement and reference errors
    ImportReference,
    /// Build failures and compilation errors
    BuildFailure,
    /// Performance bottlenecks and optimization opportunities
    PerformanceBottleneck,
    /// Security vulnerabilities and patches
    SecurityVulnerability,
    /// Configuration errors and invalid settings
    ConfigurationError,
    /// File system issues (permissions, paths)
    FileSystemIssue,
    /// Test failures and coverage gaps
    TestFailure,
    /// Documentation gaps and inconsistencies
    DocumentationGap,
}

impl IssueType {
    /// Get human-readable issue type name
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            IssueType::CodeQuality => "Code Quality Issue",
            IssueType::DependencyConflict => "Dependency Conflict",
            IssueType::ImportReference => "Import/Reference Error",
            IssueType::BuildFailure => "Build Failure",
            IssueType::PerformanceBottleneck => "Performance Bottleneck",
            IssueType::SecurityVulnerability => "Security Vulnerability",
            IssueType::ConfigurationError => "Configuration Error",
            IssueType::FileSystemIssue => "File System Issue",
            IssueType::TestFailure => "Test Failure",
            IssueType::DocumentationGap => "Documentation Gap",
        }
    }

    /// Check if issue type is automatically fixable
    #[must_use]
    pub const fn is_auto_fixable(self) -> bool {
        matches!(
            self,
            IssueType::CodeQuality
                | IssueType::ImportReference
                | IssueType::ConfigurationError
                | IssueType::DocumentationGap
        )
    }
}

/// Issue severity for prioritization
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum IssueSeverity {
    /// Low severity - cosmetic issues
    Low,
    /// Medium severity - quality issues
    Medium,
    /// High severity - functional issues
    High,
    /// Critical severity - security or data integrity issues
    Critical,
}

/// Detected issue with comprehensive context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectedIssue {
    /// Unique issue identifier
    pub issue_id: RemediationId,
    /// Issue type classification
    pub issue_type: IssueType,
    /// Issue severity level
    pub severity: IssueSeverity,
    /// Affected file paths
    pub affected_files: Vec<PathBuf>,
    /// Detailed issue description
    pub description: String,
    /// Root cause analysis
    pub root_cause: String,
    /// Impact assessment
    pub impact_assessment: ImpactAssessment,
    /// Detection timestamp
    pub detected_at: SystemTime,
    /// Detection method
    pub detection_method: DetectionMethod,
    /// Suggested remediation patterns
    pub suggested_patterns: Vec<RemediationPattern>,
    /// Related issues
    pub related_issues: Vec<RemediationId>,
}

/// Impact assessment for detected issues
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImpactAssessment {
    /// Affected components count
    pub affected_components: u32,
    /// Estimated fix time
    pub estimated_fix_time: Duration,
    /// Risk level of the issue
    pub risk_level: RiskLevel,
    /// Business impact description
    pub business_impact: String,
    /// Technical impact description
    pub technical_impact: String,
    /// User impact description
    pub user_impact: String,
}

/// Risk level for remediation operations
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum RiskLevel {
    /// Low risk - safe to execute automatically
    Low,
    /// Medium risk - requires verification
    Medium,
    /// High risk - requires manual review
    High,
    /// Critical risk - requires expert intervention
    Critical,
}

/// Detection method for issue identification
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum DetectionMethod {
    /// Static code analysis
    StaticAnalysis,
    /// Dynamic runtime analysis
    DynamicAnalysis,
    /// Compiler diagnostics
    CompilerDiagnostics,
    /// Linter warnings
    LinterWarnings,
    /// Test execution failures
    TestExecution,
    /// Performance profiling
    PerformanceProfiling,
    /// Security scanning
    SecurityScanning,
    /// Dependency analysis
    DependencyAnalysis,
    /// Manual reporting
    ManualReporting,
}

/// Remediation pattern for automated fixing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RemediationPattern {
    /// Pattern identifier
    pub pattern_id: String,
    /// Pattern name
    pub pattern_name: String,
    /// Pattern description
    pub description: String,
    /// Applicable issue types
    pub applicable_types: Vec<IssueType>,
    /// Success rate (0.0 to 1.0)
    pub success_rate: f64,
    /// Average fix time
    pub average_fix_time: Duration,
    /// Required tools
    pub required_tools: Vec<String>,
    /// Verification steps
    pub verification_steps: Vec<VerificationStep>,
}

/// Verification step for fix validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationStep {
    /// Step description
    pub description: String,
    /// Verification command
    pub command: Option<String>,
    /// Expected outcome
    pub expected_outcome: String,
    /// Timeout duration
    pub timeout: Duration,
    /// Retry count on failure
    pub retry_count: u32,
}

/// Remediation operation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RemediationResult {
    /// Remediation identifier
    pub remediation_id: RemediationId,
    /// Issue that was remediated
    pub issue_id: RemediationId,
    /// Remediation status
    pub status: RemediationStatus,
    /// Applied pattern
    pub applied_pattern: Option<RemediationPattern>,
    /// Start time
    pub start_time: SystemTime,
    /// End time
    pub end_time: Option<SystemTime>,
    /// Execution duration
    pub execution_duration: Option<Duration>,
    /// Modified files
    pub modified_files: Vec<PathBuf>,
    /// Before state snapshot
    pub before_state: StateSnapshot,
    /// After state snapshot
    pub after_state: Option<StateSnapshot>,
    /// Verification results
    pub verification_results: Vec<VerificationResult>,
    /// Rollback checkpoint
    pub rollback_checkpoint: Option<CheckpointId>,
    /// Error details (if failed)
    pub error_details: Option<String>,
}

/// Remediation operation status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum RemediationStatus {
    /// Remediation pending
    Pending,
    /// Remediation in progress
    InProgress,
    /// Remediation completed successfully
    Completed,
    /// Remediation failed
    Failed,
    /// Remediation rolled back
    RolledBack,
    /// Escalated to manual intervention
    Escalated,
}

/// State snapshot for rollback capability
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateSnapshot {
    /// Snapshot identifier
    pub snapshot_id: Uuid,
    /// Snapshot timestamp
    pub timestamp: SystemTime,
    /// File checksums (SHA-256)
    pub file_checksums: HashMap<PathBuf, Vec<u8>>,
    /// File contents (for small files)
    pub file_contents: HashMap<PathBuf, Vec<u8>>,
    /// Environment variables
    pub environment_variables: HashMap<String, String>,
    /// Configuration state
    pub configuration_state: HashMap<String, String>,
    /// System metadata
    pub system_metadata: SystemMetadata,
}

/// System metadata for state snapshots
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemMetadata {
    /// Operating system
    pub operating_system: String,
    /// Architecture
    pub architecture: String,
    /// Rust version
    pub rust_version: String,
    /// Git commit hash
    pub git_commit_hash: Option<String>,
    /// Git branch
    pub git_branch: Option<String>,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
}

/// Verification result for fix validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResult {
    /// Verification step description
    pub step_description: String,
    /// Verification status
    pub status: VerificationStatus,
    /// Execution time
    pub execution_time: Duration,
    /// Output/result
    pub output: String,
    /// Error message (if failed)
    pub error_message: Option<String>,
}

/// Verification status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum VerificationStatus {
    /// Verification passed
    Passed,
    /// Verification failed
    Failed,
    /// Verification skipped
    Skipped,
    /// Verification timed out
    TimedOut,
}

/// Escalation request for manual intervention
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscalationRequest {
    /// Escalation identifier
    pub escalation_id: RemediationId,
    /// Issue that requires escalation
    pub issue_id: RemediationId,
    /// Escalation reason
    pub reason: EscalationReason,
    /// Detailed context
    pub context: EscalationContext,
    /// Required actions
    pub required_actions: Vec<String>,
    /// Escalation timestamp
    pub escalated_at: SystemTime,
    /// Priority level
    pub priority: EscalationPriority,
    /// Contact information
    pub contact_info: Vec<String>,
}

/// Escalation reason
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum EscalationReason {
    /// Automatic remediation failed
    AutomaticRemediationFailed,
    /// High risk operation requires approval
    HighRiskOperation,
    /// Ambiguous issue requires human judgment
    AmbiguousIssue,
    /// Multiple remediation patterns applicable
    MultiplePatterns,
    /// Verification failed after fix
    VerificationFailed,
    /// Resource constraints prevent automatic fix
    ResourceConstraints,
    /// Security implications require review
    SecurityImplications,
}

/// Escalation context with comprehensive information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscalationContext {
    /// Issue details
    pub issue_details: DetectedIssue,
    /// Attempted remediation patterns
    pub attempted_patterns: Vec<RemediationPattern>,
    /// Failure reasons
    pub failure_reasons: Vec<String>,
    /// System state at escalation
    pub system_state: StateSnapshot,
    /// Relevant logs
    pub relevant_logs: Vec<String>,
    /// Suggested next steps
    pub suggested_next_steps: Vec<String>,
}

/// Escalation priority
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum EscalationPriority {
    /// Low priority - can wait
    Low,
    /// Medium priority - address soon
    Medium,
    /// High priority - address quickly
    High,
    /// Critical priority - immediate attention required
    Critical,
}

/// Rollback operation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RollbackResult {
    /// Rollback identifier
    pub rollback_id: Uuid,
    /// Checkpoint that was restored
    pub checkpoint_id: CheckpointId,
    /// Rollback status
    pub status: RollbackStatus,
    /// Start time
    pub start_time: SystemTime,
    /// End time
    pub end_time: Option<SystemTime>,
    /// Execution duration
    pub execution_duration: Option<Duration>,
    /// Restored files
    pub restored_files: Vec<PathBuf>,
    /// Verification results
    pub verification_results: Vec<VerificationResult>,
    /// Error details (if failed)
    pub error_details: Option<String>,
}

/// Rollback operation status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum RollbackStatus {
    /// Rollback in progress
    InProgress,
    /// Rollback completed successfully
    Completed,
    /// Rollback failed
    Failed,
    /// Rollback partially completed
    PartiallyCompleted,
}

/// Remediation statistics for reporting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RemediationStatistics {
    /// Total issues detected
    pub total_issues_detected: u64,
    /// Issues automatically fixed
    pub issues_automatically_fixed: u64,
    /// Issues escalated
    pub issues_escalated: u64,
    /// Issues failed
    pub issues_failed: u64,
    /// Average fix time
    pub average_fix_time: Duration,
    /// Success rate (0.0 to 1.0)
    pub success_rate: f64,
    /// Rollback count
    pub rollback_count: u64,
    /// Issues by type
    pub issues_by_type: HashMap<IssueType, u64>,
    /// Issues by severity
    pub issues_by_severity: HashMap<IssueSeverity, u64>,
}

/// Remediation configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RemediationConfig {
    /// Enable automatic remediation
    pub enable_automatic_remediation: bool,
    /// Maximum concurrent remediation operations
    pub max_concurrent_operations: u32,
    /// Automatic retry attempts
    pub automatic_retry_attempts: u32,
    /// Verification timeout
    pub verification_timeout: Duration,
    /// Rollback timeout
    pub rollback_timeout: Duration,
    /// Risk level threshold for automatic execution
    pub auto_execution_risk_threshold: RiskLevel,
    /// Enable comprehensive logging
    pub enable_comprehensive_logging: bool,
    /// Notification settings
    pub notification_settings: NotificationSettings,
}

impl Default for RemediationConfig {
    fn default() -> Self {
        Self {
            enable_automatic_remediation: true,
            max_concurrent_operations: 4,
            automatic_retry_attempts: 3,
            verification_timeout: Duration::from_secs(120),
            rollback_timeout: Duration::from_secs(10),
            auto_execution_risk_threshold: RiskLevel::Medium,
            enable_comprehensive_logging: true,
            notification_settings: NotificationSettings::default(),
        }
    }
}

/// Notification settings for remediation events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationSettings {
    /// Notify on issue detection
    pub notify_on_detection: bool,
    /// Notify on successful remediation
    pub notify_on_success: bool,
    /// Notify on remediation failure
    pub notify_on_failure: bool,
    /// Notify on escalation
    pub notify_on_escalation: bool,
    /// Notify on rollback
    pub notify_on_rollback: bool,
    /// Email addresses
    pub email_addresses: Vec<String>,
    /// Webhook URLs
    pub webhook_urls: Vec<String>,
}

impl Default for NotificationSettings {
    fn default() -> Self {
        Self {
            notify_on_detection: false,
            notify_on_success: false,
            notify_on_failure: true,
            notify_on_escalation: true,
            notify_on_rollback: true,
            email_addresses: Vec::new(),
            webhook_urls: Vec::new(),
        }
    }
}
