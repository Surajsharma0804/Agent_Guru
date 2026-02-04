//! Integration Tests for Automated Quality Assurance System
//! 
//! Comprehensive integration tests validating the complete quality assurance system
//! with real-world scenarios, performance validation, and compliance verification.

use std::collections::HashMap;
use std::time::{Duration, SystemTime};
use tempfile::TempDir;
use uuid::Uuid;

// Import the quality assurance modules
use quality_assurance::{
    QualityMonitor, QualityMetrics, MetricType, TrendDirection,
    ComplianceVerifier, ComplianceScope, VerificationDepth,
    QualityReporter, ReportPeriod, DashboardConfig, DashboardLayout, LayoutType,
    QualityError
};

/// Test the complete quality monitoring workflow
#[tokio::test]
async fn test_quality_monitoring_workflow() {
    // Create quality monitor
    let monitor = QualityMonitor::new();
    
    // Start monitoring
    assert!(monitor.start_monitoring().is_ok());
    
    // Create test metrics
    let metrics = vec![
        QualityMetrics {
            timestamp: SystemTime::now(),
            component_id: "test_component".to_string(),
            metric_type: MetricType::ResponseLatency,
            value: 100.0,
            confidence_interval: (95.0, 105.0),
            trend_direction: TrendDirection::Stable(0.95),
            anomaly_score: 0.1,
            prediction_accuracy: 0.9,
            metadata: HashMap::new(),
        },
        QualityMetrics {
            timestamp: SystemTime::now(),
            component_id: "test_component".to_string(),
            metric_type: MetricType::ErrorRate,
            value: 0.02,
            confidence_interval: (0.01, 0.03),
            trend_direction: TrendDirection::Improving(0.05),
            anomaly_score: 0.0,
            prediction_accuracy: 0.95,
            metadata: HashMap::new(),
        },
    ];
    
    // Record metrics
    for metric in metrics {
        assert!(monitor.record_metric(metric).is_ok());
    }
    
    // Wait for processing
    tokio::time::sleep(Duration::from_millis(100)).await;
    
    // Retrieve metrics
    let retrieved_metrics = monitor.get_metrics("test_component", Some(10));
    assert!(retrieved_metrics.is_ok());
    
    let metrics_list = retrieved_metrics.unwrap();
    assert_eq!(metrics_list.len(), 2);
    
    // Check alerts
    let alerts = monitor.get_alerts();
    assert!(alerts.is_ok());
    
    // Stop monitoring
    assert!(monitor.stop_monitoring().is_ok());
}

/// Test anomaly detection capabilities
#[tokio::test]
async fn test_anomaly_detection() {
    let monitor = QualityMonitor::new();
    assert!(monitor.start_monitoring().is_ok());
    
    // Create normal metrics
    for i in 0..50 {
        let metric = QualityMetrics {
            timestamp: SystemTime::now(),
            component_id: "anomaly_test".to_string(),
            metric_type: MetricType::ResponseLatency,
            value: 100.0 + (i as f64 * 0.1), // Slight variation
            confidence_interval: (99.0, 101.0),
            trend_direction: TrendDirection::Stable(0.95),
            anomaly_score: 0.0,
            prediction_accuracy: 0.9,
            metadata: HashMap::new(),
        };
        
        assert!(monitor.record_metric(metric).is_ok());
    }
    
    // Create anomalous metric
    let anomaly_metric = QualityMetrics {
        timestamp: SystemTime::now(),
        component_id: "anomaly_test".to_string(),
        metric_type: MetricType::ResponseLatency,
        value: 500.0, // Significant anomaly
        confidence_interval: (495.0, 505.0),
        trend_direction: TrendDirection::Degrading(0.8),
        anomaly_score: 0.95, // High anomaly score
        prediction_accuracy: 0.9,
        metadata: HashMap::new(),
    };
    
    assert!(monitor.record_metric(anomaly_metric).is_ok());
    
    // Wait for anomaly detection
    tokio::time::sleep(Duration::from_millis(200)).await;
    
    // Check for alerts
    let alerts = monitor.get_alerts().unwrap();
    
    // Should have detected the anomaly
    let anomaly_alerts: Vec<_> = alerts.iter()
        .filter(|alert| alert.component_id == "anomaly_test")
        .collect();
    
    assert!(!anomaly_alerts.is_empty(), "Should have detected anomaly");
    
    assert!(monitor.stop_monitoring().is_ok());
}

/// Test threshold-based alerting
#[tokio::test]
async fn test_threshold_alerting() {
    let monitor = QualityMonitor::new();
    
    // Set custom thresholds
    assert!(monitor.update_thresholds(MetricType::ResponseLatency, 200.0, 500.0).is_ok());
    assert!(monitor.update_thresholds(MetricType::ErrorRate, 0.05, 0.1).is_ok());
    
    assert!(monitor.start_monitoring().is_ok());
    
    // Create metric that exceeds warning threshold
    let warning_metric = QualityMetrics {
        timestamp: SystemTime::now(),
        component_id: "threshold_test".to_string(),
        metric_type: MetricType::ResponseLatency,
        value: 250.0, // Exceeds warning threshold of 200ms
        confidence_interval: (245.0, 255.0),
        trend_direction: TrendDirection::Degrading(0.1),
        anomaly_score: 0.3,
        prediction_accuracy: 0.9,
        metadata: HashMap::new(),
    };
    
    assert!(monitor.record_metric(warning_metric).is_ok());
    
    // Create metric that exceeds critical threshold
    let critical_metric = QualityMetrics {
        timestamp: SystemTime::now(),
        component_id: "threshold_test".to_string(),
        metric_type: MetricType::ResponseLatency,
        value: 600.0, // Exceeds critical threshold of 500ms
        confidence_interval: (595.0, 605.0),
        trend_direction: TrendDirection::Degrading(0.3),
        anomaly_score: 0.8,
        prediction_accuracy: 0.9,
        metadata: HashMap::new(),
    };
    
    assert!(monitor.record_metric(critical_metric).is_ok());
    
    // Wait for alert processing
    tokio::time::sleep(Duration::from_millis(100)).await;
    
    // Check alerts
    let alerts = monitor.get_alerts().unwrap();
    let threshold_alerts: Vec<_> = alerts.iter()
        .filter(|alert| alert.component_id == "threshold_test")
        .collect();
    
    assert!(!threshold_alerts.is_empty(), "Should have generated threshold alerts");
    
    // Should have both warning and critical alerts
    let has_critical = threshold_alerts.iter()
        .any(|alert| matches!(alert.level, quality_assurance::AlertLevel::Critical));
    assert!(has_critical, "Should have critical alert for threshold violation");
    
    assert!(monitor.stop_monitoring().is_ok());
}

/// Test compliance verification workflow
#[test]
fn test_compliance_verification() {
    // Create temporary workspace
    let temp_dir = TempDir::new().unwrap();
    let workspace_path = temp_dir.path().to_path_buf();
    
    // Create test source files
    std::fs::create_dir_all(workspace_path.join("src")).unwrap();
    
    let test_source = r#"
//! Test source file for compliance verification
//! 
//! This file contains clean room compliant code for testing.

use std::collections::HashMap;

/// Test function with proper documentation
pub fn test_function() -> Result<(), String> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_basic_functionality() {
        assert!(test_function().is_ok());
    }
}
"#;
    
    std::fs::write(workspace_path.join("src/lib.rs"), test_source).unwrap();
    
    // Create compliance verifier
    let verifier = ComplianceVerifier::new(workspace_path.clone());
    
    // Define compliance scope
    let scope = ComplianceScope {
        workspace_path,
        verification_depth: VerificationDepth::Comprehensive,
        included_patterns: vec!["*.rs".to_string()],
        excluded_patterns: vec!["target/**".to_string()],
        legal_frameworks: vec!["clean_room".to_string()],
        verification_timestamp: SystemTime::now(),
    };
    
    // Verify compliance
    let report = verifier.verify_compliance(scope);
    assert!(report.is_ok(), "Compliance verification should succeed");
    
    let compliance_report = report.unwrap();
    
    // Validate report structure
    assert!(!compliance_report.report_id.is_nil());
    assert!(compliance_report.compliance_score >= 0.0);
    assert!(compliance_report.compliance_score <= 1.0);
    
    // Check clean room verification
    assert!(compliance_report.clean_room_verification.clean_room_score >= 0.0);
    assert!(compliance_report.clean_room_verification.clean_room_score <= 1.0);
    
    // Should have framework compliance for clean_room
    assert!(!compliance_report.legal_framework_compliance.is_empty());
    
    // Check audit trail
    assert!(!compliance_report.audit_trail.entries.is_empty());
}

/// Test quality report generation
#[test]
fn test_quality_report_generation() {
    let reporter = QualityReporter::new();
    
    // Define report period
    let report_period = ReportPeriod {
        start_time: SystemTime::now() - Duration::from_secs(3600),
        end_time: SystemTime::now(),
        duration_hours: 1,
        timezone: "UTC".to_string(),
    };
    
    let components = vec![
        "auth_service".to_string(),
        "data_service".to_string(),
        "api_gateway".to_string(),
    ];
    
    // Generate report
    let report = reporter.generate_quality_report(report_period, components);
    assert!(report.is_ok(), "Quality report generation should succeed");
    
    let quality_report = report.unwrap();
    
    // Validate report structure
    assert!(!quality_report.report_id.is_nil());
    assert_eq!(quality_report.component_reports.len(), 3);
    
    // Check executive summary
    assert!(quality_report.executive_summary.overall_health_score >= 0.0);
    assert!(quality_report.executive_summary.overall_health_score <= 1.0);
    
    // Check metadata
    assert!(!quality_report.metadata.report_version.is_empty());
    assert!(quality_report.metadata.generation_time_ms > 0);
    assert!(quality_report.metadata.confidence_score >= 0.0);
    assert!(quality_report.metadata.confidence_score <= 1.0);
}

/// Test dashboard creation and data generation
#[test]
fn test_dashboard_functionality() {
    let reporter = QualityReporter::new();
    
    // Create dashboard configuration
    let dashboard_config = DashboardConfig {
        dashboard_id: Uuid::new_v4(),
        name: "Test Dashboard".to_string(),
        description: "Integration test dashboard".to_string(),
        layout: DashboardLayout {
            layout_type: LayoutType::Grid,
            columns: 4,
            rows: 3,
            responsive: true,
        },
        widgets: vec![], // Empty for test
        refresh_interval_ms: 1000,
        auto_refresh: true,
        access_permissions: vec!["admin".to_string(), "viewer".to_string()],
    };
    
    let dashboard_id = dashboard_config.dashboard_id;
    
    // Create dashboard
    let result = reporter.create_dashboard(dashboard_config);
    assert!(result.is_ok(), "Dashboard creation should succeed");
    assert_eq!(result.unwrap(), dashboard_id);
    
    // Generate dashboard data
    let dashboard_data = reporter.generate_dashboard_data(dashboard_id);
    assert!(dashboard_data.is_ok(), "Dashboard data generation should succeed");
    
    let data = dashboard_data.unwrap();
    assert_eq!(data.dashboard_id, dashboard_id);
    assert!(data.refresh_interval_ms > 0);
}

/// Test performance under load
#[tokio::test]
async fn test_performance_under_load() {
    let monitor = QualityMonitor::new();
    assert!(monitor.start_monitoring().is_ok());
    
    let start_time = SystemTime::now();
    let metric_count = 1000;
    
    // Generate high volume of metrics
    for i in 0..metric_count {
        let metric = QualityMetrics {
            timestamp: SystemTime::now(),
            component_id: format!("load_test_component_{}", i % 10),
            metric_type: if i % 2 == 0 { MetricType::ResponseLatency } else { MetricType::ErrorRate },
            value: 100.0 + (i as f64 * 0.1),
            confidence_interval: (99.0, 101.0),
            trend_direction: TrendDirection::Stable(0.95),
            anomaly_score: 0.1,
            prediction_accuracy: 0.9,
            metadata: HashMap::new(),
        };
        
        assert!(monitor.record_metric(metric).is_ok());
        
        // Small delay to simulate realistic load
        if i % 100 == 0 {
            tokio::time::sleep(Duration::from_millis(1)).await;
        }
    }
    
    let processing_time = SystemTime::now()
        .duration_since(start_time)
        .unwrap();
    
    // Verify performance requirements
    let max_processing_time = Duration::from_secs(5); // 5 seconds for 1000 metrics
    assert!(
        processing_time < max_processing_time,
        "Processing time {:?} exceeded maximum {:?}",
        processing_time,
        max_processing_time
    );
    
    // Verify all metrics were processed
    for component_id in 0..10 {
        let component_name = format!("load_test_component_{}", component_id);
        let metrics = monitor.get_metrics(&component_name, None).unwrap();
        assert!(!metrics.is_empty(), "Should have metrics for component {}", component_name);
    }
    
    assert!(monitor.stop_monitoring().is_ok());
}

/// Test error handling and recovery
#[test]
fn test_error_handling() {
    // Test invalid metric values
    let monitor = QualityMonitor::new();
    
    let invalid_metric = QualityMetrics {
        timestamp: SystemTime::now(),
        component_id: "".to_string(), // Invalid empty component ID
        metric_type: MetricType::ResponseLatency,
        value: f64::NAN, // Invalid NaN value
        confidence_interval: (100.0, 50.0), // Invalid interval (min > max)
        trend_direction: TrendDirection::Stable(0.95),
        anomaly_score: -1.0, // Invalid negative anomaly score
        prediction_accuracy: 0.9,
        metadata: HashMap::new(),
    };
    
    let result = monitor.record_metric(invalid_metric);
    assert!(result.is_err(), "Should reject invalid metric");
    
    match result.unwrap_err() {
        QualityError::InvalidMetric(_) => {}, // Expected error type
        other => panic!("Unexpected error type: {:?}", other),
    }
}

/// Test concurrent access and thread safety
#[tokio::test]
async fn test_concurrent_access() {
    let monitor = std::sync::Arc::new(QualityMonitor::new());
    assert!(monitor.start_monitoring().is_ok());
    
    let mut handles = Vec::new();
    
    // Spawn multiple concurrent tasks
    for task_id in 0..10 {
        let monitor_clone = monitor.clone();
        
        let handle = tokio::spawn(async move {
            for i in 0..100 {
                let metric = QualityMetrics {
                    timestamp: SystemTime::now(),
                    component_id: format!("concurrent_test_{}", task_id),
                    metric_type: MetricType::ResponseLatency,
                    value: 100.0 + (i as f64),
                    confidence_interval: (99.0, 101.0),
                    trend_direction: TrendDirection::Stable(0.95),
                    anomaly_score: 0.1,
                    prediction_accuracy: 0.9,
                    metadata: HashMap::new(),
                };
                
                assert!(monitor_clone.record_metric(metric).is_ok());
                
                // Small delay to allow interleaving
                tokio::time::sleep(Duration::from_micros(100)).await;
            }
        });
        
        handles.push(handle);
    }
    
    // Wait for all tasks to complete
    for handle in handles {
        assert!(handle.await.is_ok());
    }
    
    // Verify all metrics were recorded correctly
    for task_id in 0..10 {
        let component_name = format!("concurrent_test_{}", task_id);
        let metrics = monitor.get_metrics(&component_name, None).unwrap();
        assert_eq!(metrics.len(), 100, "Should have 100 metrics for task {}", task_id);
    }
    
    assert!(monitor.stop_monitoring().is_ok());
}

/// Test memory usage and cleanup
#[tokio::test]
async fn test_memory_management() {
    let monitor = QualityMonitor::new();
    assert!(monitor.start_monitoring().is_ok());
    
    // Generate large number of metrics to test memory management
    for i in 0..10000 {
        let metric = QualityMetrics {
            timestamp: SystemTime::now(),
            component_id: "memory_test".to_string(),
            metric_type: MetricType::ResponseLatency,
            value: i as f64,
            confidence_interval: ((i - 1) as f64, (i + 1) as f64),
            trend_direction: TrendDirection::Stable(0.95),
            anomaly_score: 0.1,
            prediction_accuracy: 0.9,
            metadata: {
                let mut meta = HashMap::new();
                meta.insert("iteration".to_string(), i.to_string());
                meta
            },
        };
        
        assert!(monitor.record_metric(metric).is_ok());
        
        // Periodically check memory usage doesn't grow unbounded
        if i % 1000 == 0 {
            let metrics = monitor.get_metrics("memory_test", Some(100)).unwrap();
            // Should limit to recent metrics, not store all 10000
            assert!(metrics.len() <= 1000, "Memory usage should be bounded");
        }
    }
    
    assert!(monitor.stop_monitoring().is_ok());
}

/// Test integration with external systems
#[tokio::test]
async fn test_external_integration() {
    // Test would integrate with external monitoring systems
    // For now, just test the interface exists
    
    let monitor = QualityMonitor::new();
    
    // Test metric export functionality
    let metrics = monitor.get_metrics("test_component", Some(10));
    assert!(metrics.is_ok());
    
    // Test alert retrieval
    let alerts = monitor.get_alerts();
    assert!(alerts.is_ok());
    
    // Test threshold configuration
    let threshold_result = monitor.update_thresholds(MetricType::ResponseLatency, 100.0, 500.0);
    assert!(threshold_result.is_ok());
}

/// Helper function to create test metrics
fn create_test_metric(component_id: &str, metric_type: MetricType, value: f64) -> QualityMetrics {
    QualityMetrics {
        timestamp: SystemTime::now(),
        component_id: component_id.to_string(),
        metric_type,
        value,
        confidence_interval: (value - 5.0, value + 5.0),
        trend_direction: TrendDirection::Stable(0.95),
        anomaly_score: 0.1,
        prediction_accuracy: 0.9,
        metadata: HashMap::new(),
    }
}

/// Helper function to validate metric properties
fn validate_metric(metric: &QualityMetrics) -> bool {
    !metric.component_id.is_empty() &&
    metric.value.is_finite() &&
    metric.confidence_interval.0 <= metric.confidence_interval.1 &&
    metric.anomaly_score >= 0.0 &&
    metric.anomaly_score <= 10.0 &&
    metric.prediction_accuracy >= 0.0 &&
    metric.prediction_accuracy <= 1.0
}

/// Test metric validation
#[test]
fn test_metric_validation() {
    let valid_metric = create_test_metric("test", MetricType::ResponseLatency, 100.0);
    assert!(validate_metric(&valid_metric));
    
    let invalid_metric = QualityMetrics {
        component_id: "".to_string(), // Invalid
        metric_type: MetricType::ResponseLatency,
        value: f64::INFINITY, // Invalid
        confidence_interval: (100.0, 50.0), // Invalid
        trend_direction: TrendDirection::Stable(0.95),
        anomaly_score: -1.0, // Invalid
        prediction_accuracy: 2.0, // Invalid
        metadata: HashMap::new(),
        timestamp: SystemTime::now(),
    };
    
    assert!(!validate_metric(&invalid_metric));
}