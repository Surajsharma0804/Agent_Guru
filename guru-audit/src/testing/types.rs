//! # Testing Types
//!
//! Core data structures for the comprehensive testing framework.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// Test execution status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum TestStatus {
    /// Test has not been executed
    NotStarted,
    /// Test is currently running
    InProgress { progress_percentage: u8 },
    /// Test completed successfully
    Passed,
    /// Test failed with error
    Failed { error: String, details: String },
    /// Test was skipped
    Skipped { reason: String },
}

/// Test result with comprehensive metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestResult {
    /// Test identifier
    pub test_id: String,
    /// Test name
    pub test_name: String,
    /// Test status
    pub status: TestStatus,
    /// Execution start time
    pub start_time: SystemTime,
    /// Execution end time
    pub end_time: SystemTime,
    /// Execution duration
    pub duration: Duration,
    /// Test output
    pub output: String,
    /// Test metrics
    pub metrics: TestMetrics,
}

/// Test metrics for analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestMetrics {
    /// Number of assertions executed
    pub assertions_count: u64,
    /// Code coverage percentage
    pub coverage_percentage: f64,
    /// Memory usage in bytes
    pub memory_usage_bytes: u64,
    /// CPU time in milliseconds
    pub cpu_time_ms: u64,
}

/// Unit test configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnitTestConfig {
    /// Test suite name
    pub suite_name: String,
    /// Test files to execute
    pub test_files: Vec<PathBuf>,
    /// Coverage threshold (0.0 to 100.0)
    pub coverage_threshold: f64,
    /// Parallel execution enabled
    pub parallel_execution: bool,
    /// Maximum execution time per test
    pub max_execution_time: Duration,
}

/// Property test configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PropertyTestConfig {
    /// Property name
    pub property_name: String,
    /// Minimum number of test iterations
    pub min_iterations: u32,
    /// Maximum shrinking attempts
    pub max_shrink_attempts: u32,
    /// Random seed for reproducibility
    pub random_seed: Option<u64>,
    /// Timeout per iteration
    pub iteration_timeout: Duration,
}

/// Property test result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PropertyTestResult {
    /// Property name
    pub property_name: String,
    /// Test status
    pub status: TestStatus,
    /// Number of iterations executed
    pub iterations_executed: u32,
    /// Counterexample if test failed
    pub counterexample: Option<String>,
    /// Shrinking steps performed
    pub shrinking_steps: u32,
    /// Execution duration
    pub duration: Duration,
}

/// Security test configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityTestConfig {
    /// Test name
    pub test_name: String,
    /// Target system or component
    pub target: String,
    /// Security test type
    pub test_type: SecurityTestType,
    /// Severity threshold
    pub severity_threshold: SecuritySeverity,
}

/// Security test type
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum SecurityTestType {
    /// Penetration testing
    PenetrationTest,
    /// Vulnerability scanning
    VulnerabilityScan,
    /// Cryptographic validation
    CryptographicValidation,
    /// Access control testing
    AccessControlTest,
    /// Input validation testing
    InputValidationTest,
}

/// Security severity level
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum SecuritySeverity {
    /// Informational finding
    Info,
    /// Low severity
    Low,
    /// Medium severity
    Medium,
    /// High severity
    High,
    /// Critical severity
    Critical,
}

/// Security test result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityTestResult {
    /// Test name
    pub test_name: String,
    /// Test status
    pub status: TestStatus,
    /// Vulnerabilities found
    pub vulnerabilities: Vec<SecurityVulnerability>,
    /// Execution duration
    pub duration: Duration,
}

/// Security vulnerability
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityVulnerability {
    /// Vulnerability identifier
    pub id: String,
    /// Vulnerability description
    pub description: String,
    /// Severity level
    pub severity: SecuritySeverity,
    /// Location in code
    pub location: String,
    /// Remediation recommendation
    pub remediation: String,
}

/// Formal verification configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FormalVerificationConfig {
    /// Specification file path
    pub spec_file: PathBuf,
    /// Model checking depth
    pub model_checking_depth: u32,
    /// Proof certificate generation enabled
    pub generate_proof_certificate: bool,
    /// Timeout for verification
    pub verification_timeout: Duration,
}

/// Formal verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FormalVerificationResult {
    /// Specification name
    pub spec_name: String,
    /// Verification status
    pub status: VerificationStatus,
    /// Properties verified
    pub properties_verified: Vec<PropertyVerification>,
    /// Proof certificate
    pub proof_certificate: Option<ProofCertificate>,
    /// Execution duration
    pub duration: Duration,
}

/// Verification status
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum VerificationStatus {
    /// Verification succeeded
    Verified,
    /// Verification failed with counterexample
    Failed { counterexample: String },
    /// Verification timed out
    Timeout,
    /// Verification error
    Error { message: String },
}

/// Property verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PropertyVerification {
    /// Property name
    pub property_name: String,
    /// Property type
    pub property_type: PropertyType,
    /// Verification result
    pub verified: bool,
    /// Counterexample if failed
    pub counterexample: Option<String>,
}

/// Property type
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum PropertyType {
    /// Safety property (nothing bad happens)
    Safety,
    /// Liveness property (something good eventually happens)
    Liveness,
    /// Invariant property (always true)
    Invariant,
    /// Temporal property (time-dependent behavior)
    Temporal,
}

/// Proof certificate
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofCertificate {
    /// Certificate identifier
    pub certificate_id: String,
    /// Specification name
    pub spec_name: String,
    /// Proof steps
    pub proof_steps: Vec<ProofStep>,
    /// Cryptographic signature
    pub signature: Vec<u8>,
    /// Generation timestamp
    pub timestamp: SystemTime,
}

/// Proof step
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofStep {
    /// Step number
    pub step_number: u32,
    /// Step description
    pub description: String,
    /// Logical justification
    pub justification: String,
}

/// Test battery execution summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestBatterySummary {
    /// Total tests executed
    pub total_tests: u64,
    /// Tests passed
    pub tests_passed: u64,
    /// Tests failed
    pub tests_failed: u64,
    /// Tests skipped
    pub tests_skipped: u64,
    /// Overall pass rate
    pub pass_rate: f64,
    /// Total execution duration
    pub total_duration: Duration,
    /// Coverage metrics
    pub coverage_metrics: CoverageMetrics,
}

/// Coverage metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoverageMetrics {
    /// Line coverage percentage
    pub line_coverage: f64,
    /// Branch coverage percentage
    pub branch_coverage: f64,
    /// Function coverage percentage
    pub function_coverage: f64,
    /// Total lines covered
    pub lines_covered: u64,
    /// Total lines
    pub total_lines: u64,
}

impl Default for TestMetrics {
    fn default() -> Self {
        Self {
            assertions_count: 0,
            coverage_percentage: 0.0,
            memory_usage_bytes: 0,
            cpu_time_ms: 0,
        }
    }
}

impl Default for CoverageMetrics {
    fn default() -> Self {
        Self {
            line_coverage: 0.0,
            branch_coverage: 0.0,
            function_coverage: 0.0,
            lines_covered: 0,
            total_lines: 0,
        }
    }
}
