//! Type definitions for the Runtime Self-Attestation System
//!
//! This module defines all data structures for runtime integrity monitoring,
//! module validation, threat detection, and forensic analysis. All types are
//! designed for production-grade continuous validation with cryptographic
//! verification and real-time threat response.

use crate::crypto::AuditSignature;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// Runtime attestation result with comprehensive integrity validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimeAttestationResult {
    /// Attestation identifier
    pub attestation_id: String,
    /// Attestation timestamp
    pub timestamp: SystemTime,
    /// Overall integrity status
    pub integrity_status: IntegrityStatus,
    /// Module validation results
    pub module_validations: Vec<ModuleValidationResult>,
    /// Configuration verification results
    pub configuration_verifications: Vec<ConfigurationVerificationResult>,
    /// Threat detection results
    pub threat_detections: Vec<ThreatDetectionResult>,
    /// Forensic analysis results
    pub forensic_analyses: Vec<ForensicAnalysisResult>,
    /// Cryptographic signature for attestation
    pub signature: Option<AuditSignature>,
    /// Performance metrics
    pub performance_metrics: RuntimePerformanceMetrics,
}

/// Overall integrity status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IntegrityStatus {
    /// System integrity verified - all checks passed
    Verified,
    /// System integrity compromised - violations detected
    Compromised,
    /// System integrity unknown - unable to verify
    Unknown,
    /// System in safe mode - reduced functionality
    SafeMode,
}

/// Module validation result with signature verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModuleValidationResult {
    /// Module identifier
    pub module_id: String,
    /// Module path
    pub module_path: PathBuf,
    /// Validation status
    pub validation_status: ValidationStatus,
    /// Expected checksum (SHA-256)
    pub expected_checksum: [u8; 32],
    /// Actual checksum (SHA-256)
    pub actual_checksum: [u8; 32],
    /// Signature verification result
    pub signature_verified: bool,
    /// Tamper detection result
    pub tamper_detected: bool,
    /// Validation timestamp
    pub validation_timestamp: SystemTime,
    /// Validation duration
    pub validation_duration: Duration,
}

/// Validation status for modules and configurations
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ValidationStatus {
    /// Validation passed - integrity confirmed
    Passed,
    /// Validation failed - integrity violation detected
    Failed,
    /// Validation skipped - not applicable
    Skipped,
    /// Validation error - unable to complete
    Error,
}

/// Configuration verification result with policy compliance
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigurationVerificationResult {
    /// Configuration identifier
    pub config_id: String,
    /// Configuration path
    pub config_path: PathBuf,
    /// Verification status
    pub verification_status: ValidationStatus,
    /// Policy compliance status
    pub policy_compliance: PolicyComplianceStatus,
    /// Configuration checksum
    pub config_checksum: [u8; 32],
    /// Policy violations detected
    pub policy_violations: Vec<PolicyViolation>,
    /// Verification timestamp
    pub verification_timestamp: SystemTime,
    /// Verification duration
    pub verification_duration: Duration,
}

/// Policy compliance status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PolicyComplianceStatus {
    /// Fully compliant with all policies
    Compliant,
    /// Non-compliant - violations detected
    NonCompliant,
    /// Partially compliant - minor violations
    PartiallyCompliant,
    /// Compliance unknown - unable to verify
    Unknown,
}

/// Policy violation details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyViolation {
    /// Violation identifier
    pub violation_id: String,
    /// Policy rule violated
    pub policy_rule: String,
    /// Violation severity
    pub severity: ViolationSeverity,
    /// Violation description
    pub description: String,
    /// Affected configuration parameters
    pub affected_parameters: Vec<String>,
    /// Remediation recommendations
    pub remediation_recommendations: Vec<String>,
}

/// Violation severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ViolationSeverity {
    /// Low severity - informational
    Low,
    /// Medium severity - attention required
    Medium,
    /// High severity - action required
    High,
    /// Critical severity - immediate action required
    Critical,
}

/// Threat detection result with anomaly analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThreatDetectionResult {
    /// Threat identifier
    pub threat_id: String,
    /// Threat type
    pub threat_type: ThreatType,
    /// Threat severity
    pub threat_severity: ThreatSeverity,
    /// Detection timestamp
    pub detection_timestamp: SystemTime,
    /// Threat description
    pub description: String,
    /// Anomaly indicators
    pub anomaly_indicators: Vec<AnomalyIndicator>,
    /// Behavioral analysis results
    pub behavioral_analysis: BehavioralAnalysisResult,
    /// Recommended response actions
    pub response_actions: Vec<ResponseAction>,
    /// Threat confidence score (0.0 to 1.0)
    pub confidence_score: f64,
}

/// Threat types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ThreatType {
    /// Unauthorized access attempt
    UnauthorizedAccess,
    /// Data tampering detected
    DataTampering,
    /// Malicious code injection
    CodeInjection,
    /// Privilege escalation attempt
    PrivilegeEscalation,
    /// Resource exhaustion attack
    ResourceExhaustion,
    /// Network intrusion
    NetworkIntrusion,
    /// Configuration manipulation
    ConfigurationManipulation,
    /// Cryptographic attack
    CryptographicAttack,
    /// Unknown threat pattern
    Unknown,
}

/// Threat severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ThreatSeverity {
    /// Low severity - monitoring required
    Low,
    /// Medium severity - investigation required
    Medium,
    /// High severity - immediate response required
    High,
    /// Critical severity - system lockdown required
    Critical,
}

/// Anomaly indicator for threat detection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnomalyIndicator {
    /// Indicator type
    pub indicator_type: AnomalyType,
    /// Indicator value
    pub indicator_value: String,
    /// Baseline value for comparison
    pub baseline_value: Option<String>,
    /// Deviation from baseline
    pub deviation: f64,
    /// Statistical significance
    pub statistical_significance: f64,
}

/// Anomaly types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AnomalyType {
    /// Unusual memory access pattern
    MemoryAccessPattern,
    /// Abnormal CPU utilization
    CpuUtilization,
    /// Unexpected network activity
    NetworkActivity,
    /// Unusual file system operations
    FileSystemOperations,
    /// Abnormal process behavior
    ProcessBehavior,
    /// Unexpected system calls
    SystemCalls,
    /// Unusual timing patterns
    TimingPatterns,
    /// Abnormal resource consumption
    ResourceConsumption,
}

/// Behavioral analysis result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BehavioralAnalysisResult {
    /// Analysis identifier
    pub analysis_id: String,
    /// Behavior patterns detected
    pub behavior_patterns: Vec<BehaviorPattern>,
    /// Baseline comparison results
    pub baseline_comparison: BaselineComparison,
    /// Machine learning model predictions
    pub ml_predictions: Option<MachineLearningPrediction>,
    /// Analysis confidence score
    pub confidence_score: f64,
    /// Analysis timestamp
    pub analysis_timestamp: SystemTime,
}

/// Behavior pattern detected
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BehaviorPattern {
    /// Pattern identifier
    pub pattern_id: String,
    /// Pattern type
    pub pattern_type: String,
    /// Pattern description
    pub description: String,
    /// Pattern frequency
    pub frequency: u64,
    /// Pattern risk score (0.0 to 1.0)
    pub risk_score: f64,
}

/// Baseline comparison for behavioral analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaselineComparison {
    /// Baseline identifier
    pub baseline_id: String,
    /// Deviation from baseline
    pub deviation_score: f64,
    /// Significant deviations detected
    pub significant_deviations: Vec<String>,
    /// Baseline update recommended
    pub baseline_update_recommended: bool,
}

/// Machine learning prediction for threat detection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MachineLearningPrediction {
    /// Model identifier
    pub model_id: String,
    /// Model version
    pub model_version: String,
    /// Prediction confidence
    pub confidence: f64,
    /// Predicted threat probability
    pub threat_probability: f64,
    /// Feature importance scores
    pub feature_importance: HashMap<String, f64>,
}

/// Response action for threat mitigation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResponseAction {
    /// Action identifier
    pub action_id: String,
    /// Action type
    pub action_type: ResponseActionType,
    /// Action priority
    pub priority: ActionPriority,
    /// Action description
    pub description: String,
    /// Estimated execution time
    pub estimated_execution_time: Duration,
    /// Action prerequisites
    pub prerequisites: Vec<String>,
    /// Expected outcome
    pub expected_outcome: String,
}

/// Response action types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ResponseActionType {
    /// Alert administrator
    AlertAdministrator,
    /// Isolate affected component
    IsolateComponent,
    /// Terminate suspicious process
    TerminateProcess,
    /// Block network access
    BlockNetworkAccess,
    /// Rollback to safe state
    RollbackToSafeState,
    /// Enable safe mode
    EnableSafeMode,
    /// Collect forensic evidence
    CollectForensicEvidence,
    /// Update security policies
    UpdateSecurityPolicies,
}

/// Action priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ActionPriority {
    /// Low priority - can be deferred
    Low,
    /// Medium priority - should be executed soon
    Medium,
    /// High priority - should be executed immediately
    High,
    /// Critical priority - must be executed immediately
    Critical,
}

/// Forensic analysis result with evidence preservation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForensicAnalysisResult {
    /// Analysis identifier
    pub analysis_id: String,
    /// Analysis timestamp
    pub analysis_timestamp: SystemTime,
    /// Incident identifier
    pub incident_id: String,
    /// Evidence collected
    pub evidence_collected: Vec<ForensicEvidence>,
    /// Timeline reconstruction
    pub timeline: Vec<TimelineEvent>,
    /// Root cause analysis
    pub root_cause_analysis: RootCauseAnalysis,
    /// Impact assessment
    pub impact_assessment: ImpactAssessment,
    /// Analysis duration
    pub analysis_duration: Duration,
}

/// Forensic evidence with chain of custody
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForensicEvidence {
    /// Evidence identifier
    pub evidence_id: String,
    /// Evidence type
    pub evidence_type: EvidenceType,
    /// Evidence description
    pub description: String,
    /// Evidence data hash
    pub data_hash: [u8; 32],
    /// Collection timestamp
    pub collection_timestamp: SystemTime,
    /// Collector identifier
    pub collector_id: String,
    /// Chain of custody
    pub chain_of_custody: Vec<CustodyTransfer>,
    /// Evidence integrity verified
    pub integrity_verified: bool,
}

/// Evidence types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EvidenceType {
    /// System logs
    SystemLogs,
    /// Memory dump
    MemoryDump,
    /// File system snapshot
    FileSystemSnapshot,
    /// Network traffic capture
    NetworkTrafficCapture,
    /// Process information
    ProcessInformation,
    /// Configuration snapshot
    ConfigurationSnapshot,
    /// Cryptographic artifacts
    CryptographicArtifacts,
    /// User activity logs
    UserActivityLogs,
}

/// Chain of custody transfer record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CustodyTransfer {
    /// Transfer identifier
    pub transfer_id: String,
    /// Transfer timestamp
    pub transfer_timestamp: SystemTime,
    /// From custodian
    pub from_custodian: String,
    /// To custodian
    pub to_custodian: String,
    /// Transfer reason
    pub transfer_reason: String,
    /// Transfer signature
    pub transfer_signature: Option<AuditSignature>,
}

/// Timeline event for incident reconstruction
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimelineEvent {
    /// Event identifier
    pub event_id: String,
    /// Event timestamp
    pub event_timestamp: SystemTime,
    /// Event type
    pub event_type: String,
    /// Event description
    pub description: String,
    /// Event source
    pub source: String,
    /// Related evidence
    pub related_evidence: Vec<String>,
    /// Event significance
    pub significance: EventSignificance,
}

/// Event significance levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum EventSignificance {
    /// Informational event
    Informational,
    /// Notable event
    Notable,
    /// Significant event
    Significant,
    /// Critical event
    Critical,
}

/// Root cause analysis result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RootCauseAnalysis {
    /// Analysis identifier
    pub analysis_id: String,
    /// Identified root causes
    pub root_causes: Vec<RootCause>,
    /// Contributing factors
    pub contributing_factors: Vec<String>,
    /// Analysis confidence
    pub confidence: f64,
    /// Recommendations
    pub recommendations: Vec<String>,
}

/// Root cause identification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RootCause {
    /// Cause identifier
    pub cause_id: String,
    /// Cause description
    pub description: String,
    /// Cause category
    pub category: RootCauseCategory,
    /// Evidence supporting this cause
    pub supporting_evidence: Vec<String>,
    /// Likelihood score (0.0 to 1.0)
    pub likelihood: f64,
}

/// Root cause categories
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RootCauseCategory {
    /// Configuration error
    ConfigurationError,
    /// Software bug
    SoftwareBug,
    /// Hardware failure
    HardwareFailure,
    /// Security vulnerability
    SecurityVulnerability,
    /// Human error
    HumanError,
    /// External attack
    ExternalAttack,
    /// Resource exhaustion
    ResourceExhaustion,
    /// Unknown cause
    Unknown,
}

/// Impact assessment for incidents
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImpactAssessment {
    /// Assessment identifier
    pub assessment_id: String,
    /// Overall impact severity
    pub overall_severity: ImpactSeverity,
    /// Affected systems
    pub affected_systems: Vec<String>,
    /// Affected data
    pub affected_data: Vec<String>,
    /// Estimated recovery time
    pub estimated_recovery_time: Duration,
    /// Business impact
    pub business_impact: BusinessImpact,
    /// Security impact
    pub security_impact: SecurityImpact,
}

/// Impact severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ImpactSeverity {
    /// Minimal impact
    Minimal,
    /// Minor impact
    Minor,
    /// Moderate impact
    Moderate,
    /// Major impact
    Major,
    /// Catastrophic impact
    Catastrophic,
}

/// Business impact assessment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BusinessImpact {
    /// Service availability impact
    pub service_availability: f64,
    /// Data integrity impact
    pub data_integrity: f64,
    /// Operational efficiency impact
    pub operational_efficiency: f64,
    /// Financial impact estimate
    pub financial_impact: Option<f64>,
    /// Reputation impact
    pub reputation_impact: ReputationImpact,
}

/// Reputation impact levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ReputationImpact {
    /// No reputation impact
    None,
    /// Minor reputation impact
    Minor,
    /// Moderate reputation impact
    Moderate,
    /// Significant reputation impact
    Significant,
    /// Severe reputation impact
    Severe,
}

/// Security impact assessment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityImpact {
    /// Confidentiality impact
    pub confidentiality: SecurityImpactLevel,
    /// Integrity impact
    pub integrity: SecurityImpactLevel,
    /// Availability impact
    pub availability: SecurityImpactLevel,
    /// Compliance impact
    pub compliance: ComplianceImpact,
}

/// Security impact levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum SecurityImpactLevel {
    /// No impact
    None,
    /// Low impact
    Low,
    /// Medium impact
    Medium,
    /// High impact
    High,
    /// Critical impact
    Critical,
}

/// Compliance impact assessment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceImpact {
    /// Regulatory violations
    pub regulatory_violations: Vec<String>,
    /// Policy violations
    pub policy_violations: Vec<String>,
    /// Legal implications
    pub legal_implications: Vec<String>,
    /// Reporting requirements
    pub reporting_requirements: Vec<String>,
}

/// Runtime performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimePerformanceMetrics {
    /// Integrity monitoring overhead (CPU percentage)
    pub monitoring_overhead_cpu: f64,
    /// Integrity monitoring overhead (memory bytes)
    pub monitoring_overhead_memory: u64,
    /// Module validation latency
    pub module_validation_latency: Duration,
    /// Configuration verification latency
    pub configuration_verification_latency: Duration,
    /// Threat detection latency
    pub threat_detection_latency: Duration,
    /// Forensic analysis latency
    pub forensic_analysis_latency: Duration,
    /// Total operations performed
    pub total_operations: u64,
    /// Operations per second
    pub operations_per_second: f64,
}

/// Integrity monitoring configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntegrityMonitoringConfig {
    /// Enable continuous monitoring
    pub continuous_monitoring: bool,
    /// Monitoring interval (seconds)
    pub monitoring_interval_seconds: u64,
    /// Enable module validation
    pub enable_module_validation: bool,
    /// Enable configuration verification
    pub enable_configuration_verification: bool,
    /// Enable threat detection
    pub enable_threat_detection: bool,
    /// Enable forensic analysis
    pub enable_forensic_analysis: bool,
    /// Maximum CPU overhead percentage
    pub max_cpu_overhead_percent: f64,
    /// Maximum memory overhead (bytes)
    pub max_memory_overhead_bytes: u64,
    /// Alert thresholds
    pub alert_thresholds: AlertThresholds,
}

impl Default for IntegrityMonitoringConfig {
    fn default() -> Self {
        Self {
            continuous_monitoring: true,
            monitoring_interval_seconds: 60,
            enable_module_validation: true,
            enable_configuration_verification: true,
            enable_threat_detection: true,
            enable_forensic_analysis: true,
            max_cpu_overhead_percent: 1.0,
            max_memory_overhead_bytes: 100 * 1024 * 1024, // 100 MB
            alert_thresholds: AlertThresholds::default(),
        }
    }
}

/// Alert thresholds for runtime monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertThresholds {
    /// Threat severity threshold for alerts
    pub threat_severity_threshold: ThreatSeverity,
    /// Violation severity threshold for alerts
    pub violation_severity_threshold: ViolationSeverity,
    /// Anomaly confidence threshold
    pub anomaly_confidence_threshold: f64,
    /// Performance degradation threshold
    pub performance_degradation_threshold: f64,
}

impl Default for AlertThresholds {
    fn default() -> Self {
        Self {
            threat_severity_threshold: ThreatSeverity::Medium,
            violation_severity_threshold: ViolationSeverity::Medium,
            anomaly_confidence_threshold: 0.7,
            performance_degradation_threshold: 0.2,
        }
    }
}

/// Safe mode configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafeModeConfig {
    /// Enable safe mode
    pub enabled: bool,
    /// Reduced functionality list
    pub reduced_functionality: Vec<String>,
    /// Safe mode timeout (seconds)
    pub timeout_seconds: u64,
    /// Automatic recovery enabled
    pub automatic_recovery: bool,
    /// Administrator notification required
    pub admin_notification_required: bool,
}

impl Default for SafeModeConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            reduced_functionality: vec![
                "Network access disabled".to_string(),
                "External integrations disabled".to_string(),
                "Automatic updates disabled".to_string(),
            ],
            timeout_seconds: 3600, // 1 hour
            automatic_recovery: false,
            admin_notification_required: true,
        }
    }
}
