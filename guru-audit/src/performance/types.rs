//! Performance Audit Type Definitions
//!
//! Comprehensive type system for performance analysis with mathematical guarantees.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// Performance Audit Result
///
/// Complete performance analysis results including timing, complexity, bottlenecks, and optimizations.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceAuditResult {
    pub timing_analysis: TimingAnalysis,
    pub complexity_metrics: ComplexityMetrics,
    pub bottlenecks: Vec<PerformanceBottleneck>,
    pub optimizations: Vec<OptimizationRecommendation>,
    pub audit_timestamp: SystemTime,
}

/// Timing Analysis Results
///
/// Statistical analysis of timing constraints with 99.9th percentile guarantees.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimingAnalysis {
    pub operations: HashMap<String, OperationTiming>,
    pub percentile_99_9: HashMap<String, Duration>,
    pub gate_validations: HashMap<PerformanceGate, GateValidationResult>,
    pub statistical_summary: StatisticalSummary,
}

/// Operation Timing Statistics
///
/// Comprehensive timing statistics for a single operation with mathematical guarantees.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperationTiming {
    pub operation_name: String,
    pub sample_count: u64,
    pub min_duration: Duration,
    pub max_duration: Duration,
    pub mean_duration: Duration,
    pub median_duration: Duration,
    pub std_deviation: Duration,
    pub percentile_50: Duration,
    pub percentile_90: Duration,
    pub percentile_95: Duration,
    pub percentile_99: Duration,
    pub percentile_99_9: Duration,
}

/// Performance Gate Definitions
///
/// Critical timing constraints that must be met with 99.9th percentile guarantees.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PerformanceGate {
    /// Wake Word Detection: ≤50ms
    WakeWordDetection,
    /// Speech-to-Text Processing: ≤120ms
    SpeechToText,
    /// LLM Processing: ≤200ms (initial token)
    LlmProcessing,
    /// Vision Processing: ≥24 FPS
    VisionProcessing,
    /// Memory Query: ≤100ms
    MemoryQuery,
    /// Custom gate with specified constraint
    Custom { name: String, max_duration_ms: u64 },
}

impl PerformanceGate {
    /// Returns the maximum allowed duration for this gate
    pub fn max_duration(&self) -> Duration {
        match self {
            Self::WakeWordDetection => Duration::from_millis(50),
            Self::SpeechToText => Duration::from_millis(120),
            Self::LlmProcessing => Duration::from_millis(200),
            Self::VisionProcessing => Duration::from_millis(42), // ~24 FPS
            Self::MemoryQuery => Duration::from_millis(100),
            Self::Custom { max_duration_ms, .. } => Duration::from_millis(*max_duration_ms),
        }
    }

    /// Returns the name of this performance gate
    pub fn name(&self) -> String {
        match self {
            Self::WakeWordDetection => "Wake Word Detection".to_string(),
            Self::SpeechToText => "Speech-to-Text".to_string(),
            Self::LlmProcessing => "LLM Processing".to_string(),
            Self::VisionProcessing => "Vision Processing".to_string(),
            Self::MemoryQuery => "Memory Query".to_string(),
            Self::Custom { name, .. } => name.clone(),
        }
    }
}

/// Gate Validation Result
///
/// Result of validating a performance gate with 99.9th percentile measurement.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GateValidationResult {
    pub gate: PerformanceGate,
    pub passed: bool,
    pub measured_duration: Duration,
    pub max_allowed_duration: Duration,
    pub percentile_99_9_duration: Duration,
    pub violation_details: Option<String>,
}

/// Performance Gate Status
///
/// Overall status of all performance gate validations.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceGateStatus {
    pub all_gates_passed: bool,
    pub gate_results: HashMap<PerformanceGate, GateValidationResult>,
    pub failed_gates: Vec<PerformanceGate>,
    pub validation_timestamp: SystemTime,
}

/// Statistical Summary
///
/// Comprehensive statistical analysis of performance measurements.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StatisticalSummary {
    pub total_operations_measured: u64,
    pub total_measurement_duration: Duration,
    pub confidence_interval_95: (Duration, Duration),
    pub outlier_count: u64,
    pub outlier_percentage: f64,
}

/// Complexity Metrics
///
/// Code complexity and maintainability analysis results.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplexityMetrics {
    pub files_analyzed: u64,
    pub total_lines_of_code: u64,
    pub cyclomatic_complexity: HashMap<PathBuf, FileComplexity>,
    pub maintainability_index: HashMap<PathBuf, f64>,
    pub technical_debt_hours: f64,
    pub overall_maintainability_score: f64,
}

/// File Complexity Analysis
///
/// Detailed complexity metrics for a single file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileComplexity {
    pub file_path: PathBuf,
    pub lines_of_code: u64,
    pub cyclomatic_complexity: u32,
    pub cognitive_complexity: u32,
    pub function_count: u32,
    pub average_function_complexity: f64,
    pub max_function_complexity: u32,
    pub maintainability_index: f64,
    pub technical_debt_minutes: f64,
}

/// Performance Bottleneck
///
/// Identified performance bottleneck with root cause analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceBottleneck {
    pub bottleneck_id: String,
    pub location: BottleneckLocation,
    pub severity: BottleneckSeverity,
    pub impact_analysis: ImpactAnalysis,
    pub root_cause: String,
    pub affected_operations: Vec<String>,
}

/// Bottleneck Location
///
/// Precise location of a performance bottleneck in the codebase.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BottleneckLocation {
    pub file_path: PathBuf,
    pub line_number: Option<u32>,
    pub function_name: Option<String>,
    pub module_path: String,
}

/// Bottleneck Severity
///
/// Severity classification for performance bottlenecks.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum BottleneckSeverity {
    /// Critical: Blocks production deployment
    Critical,
    /// High: Significant performance impact
    High,
    /// Medium: Noticeable performance degradation
    Medium,
    /// Low: Minor performance impact
    Low,
}

/// Impact Analysis
///
/// Detailed analysis of bottleneck impact on system performance.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImpactAnalysis {
    pub performance_degradation_percentage: f64,
    pub affected_user_operations: Vec<String>,
    pub estimated_latency_increase: Duration,
    pub resource_utilization_impact: ResourceImpact,
}

/// Resource Impact
///
/// Impact on system resources (CPU, memory, I/O).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceImpact {
    pub cpu_overhead_percentage: f64,
    pub memory_overhead_bytes: u64,
    pub io_overhead_operations: u64,
}

/// Optimization Recommendation
///
/// Automated performance optimization recommendation with priority ranking.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizationRecommendation {
    pub recommendation_id: String,
    pub priority: OptimizationPriority,
    pub optimization_type: OptimizationType,
    pub target_location: BottleneckLocation,
    pub description: String,
    pub expected_improvement: ExpectedImprovement,
    pub implementation_complexity: ImplementationComplexity,
    pub code_example: Option<String>,
}

/// Optimization Priority
///
/// Priority ranking for optimization recommendations.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum OptimizationPriority {
    /// Critical: Must be implemented immediately
    Critical,
    /// High: Should be implemented soon
    High,
    /// Medium: Should be implemented when possible
    Medium,
    /// Low: Nice to have
    Low,
}

/// Optimization Type
///
/// Category of performance optimization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum OptimizationType {
    /// Algorithm optimization (better complexity)
    Algorithm,
    /// Data structure optimization
    DataStructure,
    /// Caching strategy
    Caching,
    /// Parallelization opportunity
    Parallelization,
    /// Memory allocation optimization
    MemoryAllocation,
    /// I/O optimization
    IoOptimization,
    /// Database query optimization
    DatabaseQuery,
    /// Network optimization
    Network,
    /// Custom optimization
    Custom(String),
}

/// Expected Improvement
///
/// Quantified expected improvement from optimization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExpectedImprovement {
    pub latency_reduction_percentage: f64,
    pub throughput_increase_percentage: f64,
    pub resource_savings: ResourceSavings,
    pub confidence_level: f64,
}

/// Resource Savings
///
/// Expected resource savings from optimization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceSavings {
    pub cpu_reduction_percentage: f64,
    pub memory_reduction_bytes: u64,
    pub io_reduction_operations: u64,
}

/// Implementation Complexity
///
/// Estimated complexity of implementing an optimization.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ImplementationComplexity {
    /// Trivial: < 1 hour
    Trivial,
    /// Simple: 1-4 hours
    Simple,
    /// Moderate: 4-16 hours
    Moderate,
    /// Complex: 16-40 hours
    Complex,
    /// VeryComplex: > 40 hours
    VeryComplex,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_performance_gate_max_duration() {
        assert_eq!(PerformanceGate::WakeWordDetection.max_duration(), Duration::from_millis(50));
        assert_eq!(PerformanceGate::SpeechToText.max_duration(), Duration::from_millis(120));
        assert_eq!(PerformanceGate::LlmProcessing.max_duration(), Duration::from_millis(200));
        assert_eq!(PerformanceGate::VisionProcessing.max_duration(), Duration::from_millis(42));
        assert_eq!(PerformanceGate::MemoryQuery.max_duration(), Duration::from_millis(100));
    }

    #[test]
    fn test_bottleneck_severity_ordering() {
        assert!(BottleneckSeverity::Critical > BottleneckSeverity::High);
        assert!(BottleneckSeverity::High > BottleneckSeverity::Medium);
        assert!(BottleneckSeverity::Medium > BottleneckSeverity::Low);
    }

    #[test]
    fn test_optimization_priority_ordering() {
        assert!(OptimizationPriority::Critical > OptimizationPriority::High);
        assert!(OptimizationPriority::High > OptimizationPriority::Medium);
        assert!(OptimizationPriority::Medium > OptimizationPriority::Low);
    }
}
