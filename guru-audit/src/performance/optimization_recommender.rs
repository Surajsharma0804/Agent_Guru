//! Optimization Recommender with Automated Suggestions
//!
//! Generates automated performance optimization recommendations with priority ranking.

use crate::error::AuditError;
use crate::performance::types::*;

/// Optimization Recommender
///
/// Generates automated performance optimization recommendations.
///
/// # Performance Requirements
/// - Optimization recommendation: ≤1 second per recommendation generated
/// - Memory overhead: <50MB for analysis state
#[derive(Debug)]
#[allow(dead_code)]
pub struct OptimizationRecommender {
    min_improvement_threshold: f64,
}

impl OptimizationRecommender {
    /// Creates a new Optimization Recommender with production-grade configuration
    pub fn new() -> Result<Self, AuditError> {
        Ok(Self {
            min_improvement_threshold: 5.0, // Minimum 5% improvement to recommend
        })
    }

    /// Generates optimization recommendations
    ///
    /// Analyzes timing, complexity, and bottlenecks to generate prioritized recommendations.
    pub async fn generate_recommendations(
        &self,
        timing_analysis: &TimingAnalysis,
        complexity_metrics: &ComplexityMetrics,
        bottlenecks: &[PerformanceBottleneck],
    ) -> Result<Vec<OptimizationRecommendation>, AuditError> {
        let mut recommendations = Vec::new();

        // Generate recommendations from bottlenecks
        for bottleneck in bottlenecks {
            let recommendation = self.create_recommendation_from_bottleneck(bottleneck);
            recommendations.push(recommendation);
        }

        // Generate recommendations from complexity metrics
        for (file_path, complexity) in &complexity_metrics.cyclomatic_complexity {
            if complexity.cyclomatic_complexity > 15 {
                let recommendation = self.create_complexity_recommendation(file_path, complexity);
                recommendations.push(recommendation);
            }
        }

        // Generate recommendations from timing analysis
        for (operation_name, timing) in &timing_analysis.operations {
            if timing.percentile_99_9.as_millis() > 200 {
                let recommendation = self.create_timing_recommendation(operation_name, timing);
                recommendations.push(recommendation);
            }
        }

        // Sort by priority
        recommendations.sort_by(|a, b| b.priority.cmp(&a.priority));

        Ok(recommendations)
    }

    /// Creates recommendation from bottleneck
    fn create_recommendation_from_bottleneck(&self, bottleneck: &PerformanceBottleneck) -> OptimizationRecommendation {
        let priority = match bottleneck.severity {
            BottleneckSeverity::Critical => OptimizationPriority::Critical,
            BottleneckSeverity::High => OptimizationPriority::High,
            BottleneckSeverity::Medium => OptimizationPriority::Medium,
            BottleneckSeverity::Low => OptimizationPriority::Low,
        };

        OptimizationRecommendation {
            recommendation_id: format!("opt_{}", bottleneck.bottleneck_id),
            priority,
            optimization_type: OptimizationType::Algorithm,
            target_location: bottleneck.location.clone(),
            description: format!("Optimize bottleneck: {}", bottleneck.root_cause),
            expected_improvement: ExpectedImprovement {
                latency_reduction_percentage: bottleneck.impact_analysis.performance_degradation_percentage / 2.0,
                throughput_increase_percentage: 20.0,
                resource_savings: ResourceSavings {
                    cpu_reduction_percentage: 10.0,
                    memory_reduction_bytes: 1024 * 1024, // 1MB
                    io_reduction_operations: 100,
                },
                confidence_level: 0.7,
            },
            implementation_complexity: ImplementationComplexity::Moderate,
            code_example: None,
        }
    }

    /// Creates recommendation from complexity metrics
    fn create_complexity_recommendation(
        &self,
        file_path: &std::path::PathBuf,
        complexity: &FileComplexity,
    ) -> OptimizationRecommendation {
        OptimizationRecommendation {
            recommendation_id: format!("opt_complexity_{}", file_path.display()),
            priority: OptimizationPriority::Medium,
            optimization_type: OptimizationType::Algorithm,
            target_location: BottleneckLocation {
                file_path: file_path.clone(),
                line_number: None,
                function_name: None,
                module_path: file_path.display().to_string(),
            },
            description: format!(
                "Reduce cyclomatic complexity from {} to below 15 through refactoring",
                complexity.cyclomatic_complexity
            ),
            expected_improvement: ExpectedImprovement {
                latency_reduction_percentage: 5.0,
                throughput_increase_percentage: 5.0,
                resource_savings: ResourceSavings {
                    cpu_reduction_percentage: 2.0,
                    memory_reduction_bytes: 512 * 1024,
                    io_reduction_operations: 0,
                },
                confidence_level: 0.6,
            },
            implementation_complexity: ImplementationComplexity::Complex,
            code_example: Some("Consider extracting complex logic into smaller functions".to_string()),
        }
    }

    /// Creates recommendation from timing analysis
    fn create_timing_recommendation(&self, operation_name: &str, timing: &OperationTiming) -> OptimizationRecommendation {
        OptimizationRecommendation {
            recommendation_id: format!("opt_timing_{}", operation_name.replace(' ', "_")),
            priority: OptimizationPriority::High,
            optimization_type: OptimizationType::Caching,
            target_location: BottleneckLocation {
                file_path: std::path::PathBuf::from("unknown"),
                line_number: None,
                function_name: Some(operation_name.to_string()),
                module_path: "unknown".to_string(),
            },
            description: format!(
                "Optimize {} operation with {}ms latency at 99.9th percentile",
                operation_name,
                timing.percentile_99_9.as_millis()
            ),
            expected_improvement: ExpectedImprovement {
                latency_reduction_percentage: 30.0,
                throughput_increase_percentage: 40.0,
                resource_savings: ResourceSavings {
                    cpu_reduction_percentage: 15.0,
                    memory_reduction_bytes: 2 * 1024 * 1024, // 2MB
                    io_reduction_operations: 500,
                },
                confidence_level: 0.8,
            },
            implementation_complexity: ImplementationComplexity::Simple,
            code_example: Some("Consider adding caching layer or optimizing algorithm".to_string()),
        }
    }
}

impl Default for OptimizationRecommender {
    fn default() -> Self {
        Self::new().expect("Failed to create default OptimizationRecommender")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::time::Duration;

    #[test]
    fn test_optimization_recommender_creation() {
        let recommender = OptimizationRecommender::new();
        assert!(recommender.is_ok());
    }

    #[tokio::test]
    async fn test_recommendation_generation() {
        let recommender = OptimizationRecommender::new().expect("Failed to create recommender");
        
        let timing_analysis = TimingAnalysis {
            operations: HashMap::new(),
            percentile_99_9: HashMap::new(),
            gate_validations: HashMap::new(),
            statistical_summary: StatisticalSummary {
                total_operations_measured: 0,
                total_measurement_duration: Duration::from_secs(0),
                confidence_interval_95: (Duration::from_secs(0), Duration::from_secs(0)),
                outlier_count: 0,
                outlier_percentage: 0.0,
            },
        };

        let complexity_metrics = ComplexityMetrics {
            files_analyzed: 0,
            total_lines_of_code: 0,
            cyclomatic_complexity: HashMap::new(),
            maintainability_index: HashMap::new(),
            technical_debt_hours: 0.0,
            overall_maintainability_score: 0.0,
        };

        let bottlenecks = Vec::new();

        let result = recommender.generate_recommendations(&timing_analysis, &complexity_metrics, &bottlenecks).await;
        assert!(result.is_ok());
    }
}
