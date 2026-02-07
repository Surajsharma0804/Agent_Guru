//! Type definitions for Integration Verification System
//!
//! This module defines all data structures used in the integration verification
//! system, including API endpoints, data flow traces, platform configurations,
//! and test results.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, SystemTime};

/// HTTP method types for API requests
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum HttpMethod {
    /// GET request
    Get,
    /// POST request
    Post,
    /// PUT request
    Put,
    /// DELETE request
    Delete,
    /// PATCH request
    Patch,
    /// HEAD request
    Head,
    /// OPTIONS request
    Options,
}

/// API endpoint definition
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ApiEndpoint {
    /// Service name
    pub service_name: String,
    /// API path
    pub path: String,
    /// API version
    pub version: String,
    /// HTTP method
    pub method: HttpMethod,
}

/// API request structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiRequest {
    /// Target endpoint
    pub endpoint: ApiEndpoint,
    /// Request headers
    pub headers: HashMap<String, String>,
    /// Request body (optional)
    pub body: Option<Vec<u8>>,
    /// Request timeout
    pub timeout: Duration,
}


/// Data flow trace for end-to-end validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataFlowTrace {
    /// Unique trace identifier
    pub trace_id: String,
    /// Path through components
    pub component_path: Vec<String>,
    /// Data snapshots at each component
    pub data_snapshots: HashMap<String, Vec<u8>>,
    /// Trace start time
    pub start_time: SystemTime,
    /// Trace end time (if completed)
    pub end_time: Option<SystemTime>,
}

/// Platform configuration for cross-platform testing
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PlatformConfig {
    /// Windows platform
    Windows {
        /// Architecture (x64, ARM64)
        architecture: String,
    },
    /// macOS platform
    MacOS {
        /// Architecture (x64, ARM64)
        architecture: String,
    },
    /// Linux platform
    Linux {
        /// Architecture (x64, ARM64)
        architecture: String,
    },
}

impl PlatformConfig {
    /// Get platform name as string
    #[must_use]
    pub fn platform_name(&self) -> &'static str {
        match self {
            PlatformConfig::Windows { .. } => "Windows",
            PlatformConfig::MacOS { .. } => "MacOS",
            PlatformConfig::Linux { .. } => "Linux",
        }
    }

    /// Get architecture string
    #[must_use]
    pub fn architecture(&self) -> &str {
        match self {
            PlatformConfig::Windows { architecture }
            | PlatformConfig::MacOS { architecture }
            | PlatformConfig::Linux { architecture } => architecture,
        }
    }
}

/// Integration test configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntegrationTestConfig {
    /// API endpoints to test
    pub api_endpoints: Vec<ApiEndpoint>,
    /// Data flows to validate
    pub data_flows: Vec<DataFlowTrace>,
    /// Platforms to test
    pub platforms: Vec<PlatformConfig>,
    /// Test timeout
    pub timeout: Duration,
    /// Enable parallel execution
    pub parallel_execution: bool,
}


/// API boundary test result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiBoundaryTestResult {
    /// Contract compliance validated
    pub contract_compliance: bool,
    /// Protocol correctness verified
    pub protocol_correctness: bool,
    /// Interface consistency enforced
    pub interface_consistency: bool,
    /// Input validation comprehensive
    pub input_validation: bool,
    /// Execution time
    pub execution_time: Duration,
    /// Test timestamp
    pub timestamp: SystemTime,
}

impl ApiBoundaryTestResult {
    /// Check if contract compliance was validated
    #[must_use]
    pub const fn contract_compliance_validated(&self) -> bool {
        self.contract_compliance
    }

    /// Check if protocol correctness was verified
    #[must_use]
    pub const fn protocol_correctness_verified(&self) -> bool {
        self.protocol_correctness
    }

    /// Check if interface consistency was enforced
    #[must_use]
    pub const fn interface_consistency_enforced(&self) -> bool {
        self.interface_consistency
    }

    /// Check if input validation was comprehensive
    #[must_use]
    pub const fn input_validation_comprehensive(&self) -> bool {
        self.input_validation
    }

    /// Get execution time
    #[must_use]
    pub const fn execution_time(&self) -> Duration {
        self.execution_time
    }
}

/// Data flow validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataFlowValidationResult {
    /// End-to-end integrity preserved
    pub end_to_end_integrity: bool,
    /// Corruption detection active
    pub corruption_detection: bool,
    /// Trace completeness verified
    pub trace_completeness: bool,
    /// Cryptographic integrity verified
    pub cryptographic_integrity: bool,
    /// Execution time
    pub execution_time: Duration,
    /// Test timestamp
    pub timestamp: SystemTime,
}

impl DataFlowValidationResult {
    /// Check if end-to-end integrity was preserved
    #[must_use]
    pub const fn end_to_end_integrity_preserved(&self) -> bool {
        self.end_to_end_integrity
    }

    /// Check if corruption detection is active
    #[must_use]
    pub const fn corruption_detection_active(&self) -> bool {
        self.corruption_detection
    }

    /// Check if trace completeness was verified
    #[must_use]
    pub const fn trace_completeness_verified(&self) -> bool {
        self.trace_completeness
    }

    /// Check if cryptographic integrity was verified
    #[must_use]
    pub const fn cryptographic_integrity_verified(&self) -> bool {
        self.cryptographic_integrity
    }

    /// Get execution time
    #[must_use]
    pub const fn execution_time(&self) -> Duration {
        self.execution_time
    }

    /// Check if error propagation is correct
    #[must_use]
    pub const fn error_propagation_correct(&self) -> bool {
        true // Placeholder for actual implementation
    }

    /// Check if error context is preserved
    #[must_use]
    pub const fn error_context_preserved(&self) -> bool {
        true // Placeholder for actual implementation
    }

    /// Check if recovery mechanism is available
    #[must_use]
    pub const fn recovery_mechanism_available(&self) -> bool {
        true // Placeholder for actual implementation
    }

    /// Check if error isolation is maintained
    #[must_use]
    pub const fn error_isolation_maintained(&self) -> bool {
        true // Placeholder for actual implementation
    }
}


/// Cross-platform test result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CrossPlatformTestResult {
    /// Feature parity verified
    pub feature_parity: bool,
    /// Compatibility validated
    pub compatibility: bool,
    /// Performance consistency verified
    pub performance_consistency: bool,
    /// Platform API integration verified
    pub platform_api_integration: bool,
    /// Execution time
    pub execution_time: Duration,
    /// Test timestamp
    pub timestamp: SystemTime,
}

impl CrossPlatformTestResult {
    /// Check if feature parity was verified
    #[must_use]
    pub const fn feature_parity_verified(&self) -> bool {
        self.feature_parity
    }

    /// Check if compatibility was validated
    #[must_use]
    pub const fn compatibility_validated(&self) -> bool {
        self.compatibility
    }

    /// Check if performance consistency was verified
    #[must_use]
    pub const fn performance_consistency_verified(&self) -> bool {
        self.performance_consistency
    }

    /// Check if platform API integration was verified
    #[must_use]
    pub const fn platform_api_integration_verified(&self) -> bool {
        self.platform_api_integration
    }

    /// Get execution time
    #[must_use]
    pub const fn execution_time(&self) -> Duration {
        self.execution_time
    }
}

/// Performance validation result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceValidationResult {
    /// Latency measurement accurate
    pub latency_measurement: bool,
    /// Throughput validated
    pub throughput_validation: bool,
    /// Percentile guarantees met
    pub percentile_guarantees: bool,
    /// Regression detection active
    pub regression_detection: bool,
    /// Execution time
    pub execution_time: Duration,
    /// Test timestamp
    pub timestamp: SystemTime,
}

impl PerformanceValidationResult {
    /// Check if latency measurement is accurate
    #[must_use]
    pub const fn latency_measurement_accurate(&self) -> bool {
        self.latency_measurement
    }

    /// Check if throughput was validated
    #[must_use]
    pub const fn throughput_validated(&self) -> bool {
        self.throughput_validation
    }

    /// Check if percentile guarantees are met
    #[must_use]
    pub const fn percentile_guarantees_met(&self) -> bool {
        self.percentile_guarantees
    }

    /// Check if regression detection is active
    #[must_use]
    pub const fn regression_detection_active(&self) -> bool {
        self.regression_detection
    }

    /// Get execution time
    #[must_use]
    pub const fn execution_time(&self) -> Duration {
        self.execution_time
    }
}


/// Security boundary test result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityBoundaryTestResult {
    /// Capability access control enforced
    pub capability_access_control: bool,
    /// Privilege escalation detected
    pub privilege_escalation_detection: bool,
    /// Security policy enforced
    pub security_policy: bool,
    /// Cryptographic verification performed
    pub cryptographic_verification: bool,
    /// Audit trail generated
    pub audit_trail: bool,
    /// Execution time
    pub execution_time: Duration,
    /// Test timestamp
    pub timestamp: SystemTime,
}

impl SecurityBoundaryTestResult {
    /// Check if capability access control is enforced
    #[must_use]
    pub const fn capability_access_control_enforced(&self) -> bool {
        self.capability_access_control
    }

    /// Check if privilege escalation was detected
    #[must_use]
    pub const fn privilege_escalation_detected(&self) -> bool {
        self.privilege_escalation_detection
    }

    /// Check if security policy is enforced
    #[must_use]
    pub const fn security_policy_enforced(&self) -> bool {
        self.security_policy
    }

    /// Check if cryptographic verification was performed
    #[must_use]
    pub const fn cryptographic_verification_performed(&self) -> bool {
        self.cryptographic_verification
    }

    /// Check if audit trail was generated
    #[must_use]
    pub const fn audit_trail_generated(&self) -> bool {
        self.audit_trail
    }

    /// Get execution time
    #[must_use]
    pub const fn execution_time(&self) -> Duration {
        self.execution_time
    }
}

/// Integration verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntegrationVerificationResult {
    /// Race conditions prevented
    pub race_conditions_prevented: bool,
    /// Thread safety enforced
    pub thread_safety: bool,
    /// Data consistency maintained
    pub data_consistency: bool,
    /// Deadlock prevention active
    pub deadlock_prevention: bool,
    /// Parallel execution correct
    pub parallel_execution: bool,
    /// All API boundaries tested
    pub all_api_boundaries_tested: bool,
    /// All data flows validated
    pub all_data_flows_validated: bool,
    /// Integration matrix complete
    pub integration_matrix_complete: bool,
    /// Formal contracts validated
    pub formal_contracts_validated: bool,
    /// Comprehensive report generated
    pub comprehensive_report: bool,
    /// Execution time
    pub execution_time: Duration,
    /// Test timestamp
    pub timestamp: SystemTime,
}

impl IntegrationVerificationResult {
    /// Check if race conditions are prevented
    #[must_use]
    pub const fn race_conditions_prevented(&self) -> bool {
        self.race_conditions_prevented
    }

    /// Check if thread safety is enforced
    #[must_use]
    pub const fn thread_safety_enforced(&self) -> bool {
        self.thread_safety
    }

    /// Check if data consistency is maintained
    #[must_use]
    pub const fn data_consistency_maintained(&self) -> bool {
        self.data_consistency
    }

    /// Check if deadlock prevention is active
    #[must_use]
    pub const fn deadlock_prevention_active(&self) -> bool {
        self.deadlock_prevention
    }

    /// Check if parallel execution is correct
    #[must_use]
    pub const fn parallel_execution_correct(&self) -> bool {
        self.parallel_execution
    }

    /// Check if all API boundaries were tested
    #[must_use]
    pub const fn all_api_boundaries_tested(&self) -> bool {
        self.all_api_boundaries_tested
    }

    /// Check if all data flows were validated
    #[must_use]
    pub const fn all_data_flows_validated(&self) -> bool {
        self.all_data_flows_validated
    }

    /// Check if integration matrix is complete
    #[must_use]
    pub const fn integration_matrix_complete(&self) -> bool {
        self.integration_matrix_complete
    }

    /// Check if formal contracts were validated
    #[must_use]
    pub const fn formal_contracts_validated(&self) -> bool {
        self.formal_contracts_validated
    }

    /// Check if comprehensive report was generated
    #[must_use]
    pub const fn comprehensive_report_generated(&self) -> bool {
        self.comprehensive_report
    }

    /// Get execution time
    #[must_use]
    pub const fn execution_time(&self) -> Duration {
        self.execution_time
    }
}
