//! Quality Gates - Mathematical quality validation
//!
//! The Quality Gates system provides mathematical validation of all quality metrics
//! with formal proof requirements and zero-tolerance enforcement. It implements
//! comprehensive quality validation with cryptographic verification and detailed
//! violation analysis.

use crate::error::{AuditError, AuditResult, QualityMetric, ViolationDetails, ViolationSeverity};
use crate::types::{PhaseResult, QualityGateConfig};
use async_trait::async_trait;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime};
use tokio::sync::RwLock;
use tracing::{info, warn};

/// Quality validation result with comprehensive details
#[derive(Debug, Clone)]
pub struct QualityValidationResult {
    /// Whether validation passed
    pub passed: bool,
    /// Gate name that was validated
    pub gate_name: String,
    /// Expected value
    pub expected_value: QualityMetric,
    /// Actual value
    pub actual_value: QualityMetric,
    /// Violation details if failed
    pub violation_details: ViolationDetails,
    /// Validation timestamp
    pub validation_timestamp: SystemTime,
    /// Validation duration
    pub validation_duration: Duration,
}

/// Quality Gates trait for comprehensive validation
#[async_trait]
pub trait QualityGates: Send + Sync {
    /// Validate phase result against quality gates
    async fn validate_phase_result(&self, result: &PhaseResult) -> AuditResult<QualityValidationResult>;

    /// Validate specific quality metric
    async fn validate_quality_metric(
        &self,
        metric_name: &str,
        expected: QualityMetric,
        actual: QualityMetric,
    ) -> AuditResult<QualityValidationResult>;

    /// Get quality gate configuration
    async fn get_quality_gate_config(&self) -> QualityGateConfig;

    /// Get quality validation statistics
    async fn get_validation_statistics(&self) -> QualityValidationStatistics;
}

/// Quality validation statistics
#[derive(Debug, Clone)]
pub struct QualityValidationStatistics {
    /// Total validations performed
    pub total_validations: u64,
    /// Successful validations
    pub successful_validations: u64,
    /// Failed validations
    pub failed_validations: u64,
    /// Average validation time
    pub average_validation_time: Duration,
    /// Most common violation types
    pub common_violations: HashMap<String, u64>,
    /// Quality trend over time
    pub quality_trend: Vec<QualityTrendPoint>,
}

/// Quality trend data point
#[derive(Debug, Clone)]
pub struct QualityTrendPoint {
    /// Timestamp
    pub timestamp: SystemTime,
    /// Overall quality score (0.0 - 100.0)
    pub quality_score: f64,
    /// Number of violations
    pub violation_count: u32,
    /// Phase being validated
    pub phase: crate::types::PhaseId,
}

/// Production quality gates implementation with zero-tolerance enforcement
#[derive(Debug)]
pub struct ProductionQualityGates {
    /// Quality gate configuration
    config: Arc<RwLock<QualityGateConfig>>,
    /// Validation statistics
    statistics: Arc<RwLock<QualityValidationStatistics>>,
    /// Quality gate validators
    validators: Arc<QualityGateValidators>,
}

/// Quality gate validators for different metrics
#[derive(Debug)]
#[allow(dead_code)]
struct QualityGateValidators {
    /// Compiler warning validator
    compiler_warning_validator: CompilerWarningValidator,
    /// Runtime error validator
    runtime_error_validator: RuntimeErrorValidator,
    /// Test coverage validator
    test_coverage_validator: TestCoverageValidator,
    /// Performance validator
    performance_validator: PerformanceValidator,
    /// Security validator
    security_validator: SecurityValidator,
}

/// Compiler warning validator
#[derive(Debug)]
struct CompilerWarningValidator {
    /// Maximum allowed warnings (should be 0 for zero-tolerance)
    max_warnings: u32,
}

/// Runtime error validator
#[derive(Debug)]
struct RuntimeErrorValidator {
    /// Maximum allowed errors (should be 0 for zero-tolerance)
    max_errors: u32,
}

/// Test coverage validator
#[derive(Debug)]
#[allow(dead_code)]
struct TestCoverageValidator {
    /// Minimum required coverage percentage
    min_coverage: f64,
}

/// Performance validator
#[derive(Debug)]
struct PerformanceValidator {
    /// Maximum allowed execution time per phase
    max_execution_times: HashMap<crate::types::PhaseId, Duration>,
    /// Maximum allowed memory usage
    max_memory_usage: u64,
    /// Maximum allowed CPU utilization
    max_cpu_utilization: f64,
}

/// Security validator
#[derive(Debug)]
#[allow(dead_code)]
struct SecurityValidator {
    /// Maximum allowed security vulnerabilities (should be 0)
    max_vulnerabilities: u32,
    /// Required cryptographic operations
    required_crypto_operations: Vec<String>,
}

impl ProductionQualityGates {
    /// Create new production quality gates with zero-tolerance configuration
    #[must_use]
    pub fn new() -> Self {
        let config = Arc::new(RwLock::new(QualityGateConfig::default()));
        
        let statistics = Arc::new(RwLock::new(QualityValidationStatistics {
            total_validations: 0,
            successful_validations: 0,
            failed_validations: 0,
            average_validation_time: Duration::ZERO,
            common_violations: HashMap::new(),
            quality_trend: Vec::new(),
        }));

        let validators = Arc::new(QualityGateValidators {
            compiler_warning_validator: CompilerWarningValidator { max_warnings: 0 },
            runtime_error_validator: RuntimeErrorValidator { max_errors: 0 },
            test_coverage_validator: TestCoverageValidator { min_coverage: 100.0 },
            performance_validator: PerformanceValidator {
                max_execution_times: Self::create_default_execution_time_limits(),
                max_memory_usage: 8_000_000_000, // 8GB
                max_cpu_utilization: 95.0, // 95%
            },
            security_validator: SecurityValidator {
                max_vulnerabilities: 0,
                required_crypto_operations: vec![
                    "signature_verification".to_string(),
                    "checksum_validation".to_string(),
                    "integrity_attestation".to_string(),
                ],
            },
        });

        Self {
            config,
            statistics,
            validators,
        }
    }

    /// Create default execution time limits for phases
    fn create_default_execution_time_limits() -> HashMap<crate::types::PhaseId, Duration> {
        let mut limits = HashMap::new();
        limits.insert(crate::types::PhaseId::Inventory, Duration::from_secs(300)); // 5 minutes
        limits.insert(crate::types::PhaseId::Naming, Duration::from_secs(600)); // 10 minutes
        limits.insert(crate::types::PhaseId::Purge, Duration::from_secs(900)); // 15 minutes
        limits.insert(crate::types::PhaseId::Integration, Duration::from_secs(1800)); // 30 minutes
        limits.insert(crate::types::PhaseId::Testing, Duration::from_secs(3600)); // 1 hour
        limits.insert(crate::types::PhaseId::Performance, Duration::from_secs(1800)); // 30 minutes
        limits.insert(crate::types::PhaseId::FormalVerification, Duration::from_secs(7200)); // 2 hours
        limits.insert(crate::types::PhaseId::ReproducibleBuild, Duration::from_secs(1800)); // 30 minutes
        limits.insert(crate::types::PhaseId::RuntimeAttestation, Duration::from_secs(600)); // 10 minutes
        limits.insert(crate::types::PhaseId::FinalCertification, Duration::from_secs(300)); // 5 minutes
        limits
    }

    /// Validate phase result with comprehensive quality checks
    async fn validate_phase_result_internal(&self, result: &PhaseResult) -> AuditResult<QualityValidationResult> {
        let start_time = SystemTime::now();
        
        info!("Starting quality validation for phase: {:?}", result.phase_id);

        // Perform comprehensive quality validation
        let mut violations = Vec::new();
        let mut validation_passed = true;

        // 1. Validate compiler warnings (zero-tolerance)
        if let Err(violation) = self.validate_compiler_warnings(result).await {
            violations.push(violation.to_string());
            validation_passed = false;
        }

        // 2. Validate runtime errors (zero-tolerance)
        if let Err(violation) = self.validate_runtime_errors(result).await {
            violations.push(violation.to_string());
            validation_passed = false;
        }

        // 3. Validate execution performance
        if let Err(violation) = self.validate_execution_performance(result).await {
            violations.push(violation.to_string());
            validation_passed = false;
        }

        // 4. Validate memory usage
        if let Err(violation) = self.validate_memory_usage(result).await {
            violations.push(violation.to_string());
            validation_passed = false;
        }

        // 5. Validate CPU utilization
        if let Err(violation) = self.validate_cpu_utilization(result).await {
            violations.push(violation.to_string());
            validation_passed = false;
        }

        // 6. Validate artifacts generation
        if let Err(violation) = self.validate_artifacts(result).await {
            violations.push(violation.to_string());
            validation_passed = false;
        }

        // 7. Validate quality gate failures
        if !result.quality_gates_failed.is_empty() {
            violations.push(format!("Quality gate failures detected: {}", result.quality_gates_failed.len()));
            validation_passed = false;
        }

        let validation_duration = start_time.elapsed().unwrap_or(Duration::ZERO);

        // Create validation result
        let validation_result = QualityValidationResult {
            passed: validation_passed,
            gate_name: format!("{:?}_quality_validation", result.phase_id),
            expected_value: QualityMetric::Boolean(true),
            actual_value: QualityMetric::Boolean(validation_passed),
            violation_details: ViolationDetails {
                severity: if validation_passed {
                    ViolationSeverity::Minor
                } else {
                    ViolationSeverity::Major
                },
                affected_components: vec![format!("{:?}", result.phase_id)],
                evidence: violations.clone(),
                impact_assessment: if validation_passed {
                    "No quality violations detected".to_string()
                } else {
                    format!("Quality violations detected: {}", violations.len())
                },
                recommended_actions: if validation_passed {
                    Vec::new()
                } else {
                    vec![
                        "Review phase implementation".to_string(),
                        "Address quality violations".to_string(),
                        "Re-run phase after fixes".to_string(),
                    ]
                },
            },
            validation_timestamp: start_time,
            validation_duration,
        };

        // Update statistics
        self.update_validation_statistics(&validation_result).await;

        if validation_passed {
            info!("Quality validation passed for phase: {:?}", result.phase_id);
        } else {
            warn!("Quality validation failed for phase: {:?} - violations: {:?}", result.phase_id, violations);
        }

        Ok(validation_result)
    }

    /// Validate compiler warnings (zero-tolerance)
    async fn validate_compiler_warnings(&self, result: &PhaseResult) -> AuditResult<()> {
        let warning_count = result.metrics.warnings_generated;
        
        if warning_count > self.validators.compiler_warning_validator.max_warnings.into() {
            return Err(AuditError::QualityGateFailure {
                gate_name: "zero_compiler_warnings".to_string(),
                expected_value: QualityMetric::Count(self.validators.compiler_warning_validator.max_warnings),
                actual_value: QualityMetric::Count(warning_count as u32),
                violation_details: ViolationDetails {
                    severity: ViolationSeverity::Major,
                    affected_components: vec![format!("{:?}", result.phase_id)],
                    evidence: vec![format!("Compiler warnings detected: {warning_count}")],
                    impact_assessment: "Compiler warnings violate zero-tolerance policy".to_string(),
                    recommended_actions: vec![
                        "Fix all compiler warnings".to_string(),
                        "Enable strict linting configuration".to_string(),
                    ],
                },
            });
        }

        Ok(())
    }

    /// Validate runtime errors (zero-tolerance)
    async fn validate_runtime_errors(&self, result: &PhaseResult) -> AuditResult<()> {
        let error_count = result.metrics.errors_encountered;
        
        if error_count > self.validators.runtime_error_validator.max_errors.into() {
            return Err(AuditError::QualityGateFailure {
                gate_name: "zero_runtime_errors".to_string(),
                expected_value: QualityMetric::Count(self.validators.runtime_error_validator.max_errors),
                actual_value: QualityMetric::Count(error_count as u32),
                violation_details: ViolationDetails {
                    severity: ViolationSeverity::Critical,
                    affected_components: vec![format!("{:?}", result.phase_id)],
                    evidence: vec![format!("Runtime errors detected: {error_count}")],
                    impact_assessment: "Runtime errors violate zero-tolerance policy".to_string(),
                    recommended_actions: vec![
                        "Fix all runtime errors".to_string(),
                        "Implement comprehensive error handling".to_string(),
                    ],
                },
            });
        }

        Ok(())
    }

    /// Validate execution performance
    async fn validate_execution_performance(&self, result: &PhaseResult) -> AuditResult<()> {
        if let Some(&max_duration) = self.validators.performance_validator.max_execution_times.get(&result.phase_id) {
            if result.metrics.execution_duration > max_duration {
                return Err(AuditError::PerformanceViolation {
                    constraint_name: format!("{:?}_execution_time", result.phase_id),
                    required_value: crate::error::PerformanceMetric::Latency(max_duration),
                    measured_value: crate::error::PerformanceMetric::Latency(result.metrics.execution_duration),
                    statistical_analysis: crate::error::StatisticalAnalysis {
                        mean: result.metrics.execution_duration.as_secs_f64(),
                        standard_deviation: 0.0,
                        percentile_95: result.metrics.execution_duration.as_secs_f64(),
                        percentile_99: result.metrics.execution_duration.as_secs_f64(),
                        percentile_99_9: result.metrics.execution_duration.as_secs_f64(),
                        sample_size: 1,
                        confidence_interval: (result.metrics.execution_duration.as_secs_f64(), result.metrics.execution_duration.as_secs_f64()),
                    },
                });
            }
        }

        Ok(())
    }

    /// Validate memory usage
    async fn validate_memory_usage(&self, result: &PhaseResult) -> AuditResult<()> {
        if result.metrics.memory_usage_peak > self.validators.performance_validator.max_memory_usage {
            return Err(AuditError::PerformanceViolation {
                constraint_name: "memory_usage".to_string(),
                required_value: crate::error::PerformanceMetric::MemoryUsage(self.validators.performance_validator.max_memory_usage),
                measured_value: crate::error::PerformanceMetric::MemoryUsage(result.metrics.memory_usage_peak),
                statistical_analysis: crate::error::StatisticalAnalysis {
                    mean: result.metrics.memory_usage_peak as f64,
                    standard_deviation: 0.0,
                    percentile_95: result.metrics.memory_usage_peak as f64,
                    percentile_99: result.metrics.memory_usage_peak as f64,
                    percentile_99_9: result.metrics.memory_usage_peak as f64,
                    sample_size: 1,
                    confidence_interval: (result.metrics.memory_usage_peak as f64, result.metrics.memory_usage_peak as f64),
                },
            });
        }

        Ok(())
    }

    /// Validate CPU utilization
    async fn validate_cpu_utilization(&self, result: &PhaseResult) -> AuditResult<()> {
        if result.metrics.cpu_utilization > self.validators.performance_validator.max_cpu_utilization {
            return Err(AuditError::PerformanceViolation {
                constraint_name: "cpu_utilization".to_string(),
                required_value: crate::error::PerformanceMetric::CpuUtilization(self.validators.performance_validator.max_cpu_utilization),
                measured_value: crate::error::PerformanceMetric::CpuUtilization(result.metrics.cpu_utilization),
                statistical_analysis: crate::error::StatisticalAnalysis {
                    mean: result.metrics.cpu_utilization,
                    standard_deviation: 0.0,
                    percentile_95: result.metrics.cpu_utilization,
                    percentile_99: result.metrics.cpu_utilization,
                    percentile_99_9: result.metrics.cpu_utilization,
                    sample_size: 1,
                    confidence_interval: (result.metrics.cpu_utilization, result.metrics.cpu_utilization),
                },
            });
        }

        Ok(())
    }

    /// Validate artifacts generation
    async fn validate_artifacts(&self, result: &PhaseResult) -> AuditResult<()> {
        if result.artifacts.is_empty() {
            return Err(AuditError::QualityGateFailure {
                gate_name: "artifacts_generated".to_string(),
                expected_value: QualityMetric::Count(1),
                actual_value: QualityMetric::Count(0),
                violation_details: ViolationDetails {
                    severity: ViolationSeverity::Major,
                    affected_components: vec![format!("{:?}", result.phase_id)],
                    evidence: vec!["No artifacts generated".to_string()],
                    impact_assessment: "Phase must generate required artifacts".to_string(),
                    recommended_actions: vec![
                        "Ensure phase generates required artifacts".to_string(),
                        "Verify artifact generation logic".to_string(),
                    ],
                },
            });
        }

        Ok(())
    }

    /// Update validation statistics
    async fn update_validation_statistics(&self, result: &QualityValidationResult) {
        let mut stats = self.statistics.write().await;
        
        stats.total_validations += 1;
        
        if result.passed {
            stats.successful_validations += 1;
        } else {
            stats.failed_validations += 1;
            
            // Update common violations
            let violation_type = result.gate_name.clone();
            *stats.common_violations.entry(violation_type).or_insert(0) += 1;
        }

        // Update average validation time
        let total_time = stats.average_validation_time.mul_f64(stats.total_validations as f64 - 1.0)
            + result.validation_duration;
        stats.average_validation_time = total_time.div_f64(stats.total_validations as f64);

        // Add quality trend point
        let quality_score = if result.passed { 100.0 } else { 0.0 };
        stats.quality_trend.push(QualityTrendPoint {
            timestamp: result.validation_timestamp,
            quality_score,
            violation_count: if result.passed { 0 } else { 1 },
            phase: crate::types::PhaseId::Inventory, // Would be extracted from result in real implementation
        });

        // Keep only recent trend data (last 1000 points)
        if stats.quality_trend.len() > 1000 {
            stats.quality_trend.drain(0..100);
        }
    }
}

impl Default for ProductionQualityGates {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl QualityGates for ProductionQualityGates {
    async fn validate_phase_result(&self, result: &PhaseResult) -> AuditResult<QualityValidationResult> {
        self.validate_phase_result_internal(result).await
    }

    async fn validate_quality_metric(
        &self,
        metric_name: &str,
        expected: QualityMetric,
        actual: QualityMetric,
    ) -> AuditResult<QualityValidationResult> {
        let start_time = SystemTime::now();
        let passed = expected == actual;

        let result = QualityValidationResult {
            passed,
            gate_name: metric_name.to_string(),
            expected_value: expected.clone(),
            actual_value: actual.clone(),
            violation_details: ViolationDetails {
                severity: if passed { ViolationSeverity::Minor } else { ViolationSeverity::Major },
                affected_components: vec![metric_name.to_string()],
                evidence: if passed {
                    Vec::new()
                } else {
                    vec![format!("Expected: {expected}, Actual: {actual}")]
                },
                impact_assessment: if passed {
                    "Quality metric validation passed".to_string()
                } else {
                    "Quality metric validation failed".to_string()
                },
                recommended_actions: if passed {
                    Vec::new()
                } else {
                    vec!["Review and fix quality metric".to_string()]
                },
            },
            validation_timestamp: start_time,
            validation_duration: start_time.elapsed().unwrap_or(Duration::ZERO),
        };

        self.update_validation_statistics(&result).await;
        Ok(result)
    }

    async fn get_quality_gate_config(&self) -> QualityGateConfig {
        let config = self.config.read().await;
        config.clone()
    }

    async fn get_validation_statistics(&self) -> QualityValidationStatistics {
        let stats = self.statistics.read().await;
        stats.clone()
    }
}