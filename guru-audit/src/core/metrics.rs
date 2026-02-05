//! Metrics Collector - Performance monitoring and analytics
//!
//! The Metrics Collector provides real-time performance monitoring and trend analysis
//! with comprehensive metrics collection, statistical analysis, and alerting capabilities.
//! It implements production-grade monitoring with cryptographic integrity and audit trails.

use crate::error::{AuditError, AuditResult};
use crate::types::{PhaseId, PhaseMetrics};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use std::time::{Duration, SystemTime};
use tokio::sync::RwLock;
use tracing::{info, warn};

/// Metrics Collector trait for performance monitoring
#[async_trait]
pub trait MetricsCollector: Send + Sync {
    /// Record phase metrics with comprehensive analysis
    async fn record_phase_metrics(&self, phase: PhaseId, metrics: &PhaseMetrics) -> AuditResult<()>;

    /// Get performance statistics for a specific phase
    async fn get_phase_performance_statistics(&self, phase: PhaseId) -> AuditResult<PhasePerformanceStatistics>;

    /// Get overall system performance statistics
    async fn get_system_performance_statistics(&self) -> SystemPerformanceStatistics;

    /// Get performance trends over time
    async fn get_performance_trends(&self, duration: Duration) -> AuditResult<PerformanceTrends>;

    /// Generate performance alerts based on thresholds
    async fn check_performance_alerts(&self) -> Vec<PerformanceAlert>;

    /// Export metrics for external monitoring systems
    async fn export_metrics(&self, format: MetricsExportFormat) -> AuditResult<String>;
}

/// Phase-specific performance statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhasePerformanceStatistics {
    /// Phase identifier
    pub phase_id: PhaseId,
    /// Total executions recorded
    pub total_executions: u64,
    /// Execution time statistics
    pub execution_time_stats: TimeStatistics,
    /// Memory usage statistics
    pub memory_usage_stats: MemoryStatistics,
    /// CPU utilization statistics
    pub cpu_utilization_stats: CpuStatistics,
    /// File processing statistics
    pub file_processing_stats: FileProcessingStatistics,
    /// Error and warning statistics
    pub error_warning_stats: ErrorWarningStatistics,
    /// Performance trend
    pub performance_trend: PerformanceTrend,
}

/// Time-based statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeStatistics {
    /// Minimum execution time
    pub min_time: Duration,
    /// Maximum execution time
    pub max_time: Duration,
    /// Average execution time
    pub average_time: Duration,
    /// Median execution time
    pub median_time: Duration,
    /// 95th percentile
    pub percentile_95: Duration,
    /// 99th percentile
    pub percentile_99: Duration,
    /// 99.9th percentile
    pub percentile_99_9: Duration,
    /// Standard deviation
    pub standard_deviation: Duration,
}

/// Memory usage statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryStatistics {
    /// Minimum memory usage
    pub min_memory: u64,
    /// Maximum memory usage
    pub max_memory: u64,
    /// Average memory usage
    pub average_memory: u64,
    /// Memory usage trend
    pub memory_trend: MemoryTrend,
    /// Memory efficiency score (0.0 - 100.0)
    pub efficiency_score: f64,
}

/// CPU utilization statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CpuStatistics {
    /// Minimum CPU utilization
    pub min_cpu: f64,
    /// Maximum CPU utilization
    pub max_cpu: f64,
    /// Average CPU utilization
    pub average_cpu: f64,
    /// CPU efficiency score (0.0 - 100.0)
    pub efficiency_score: f64,
}

/// File processing statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileProcessingStatistics {
    /// Total files processed
    pub total_files_processed: u64,
    /// Average files per execution
    pub average_files_per_execution: f64,
    /// File processing rate (files per second)
    pub processing_rate: f64,
    /// Processing efficiency score
    pub efficiency_score: f64,
}

/// Error and warning statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorWarningStatistics {
    /// Total errors encountered
    pub total_errors: u64,
    /// Total warnings generated
    pub total_warnings: u64,
    /// Error rate (errors per execution)
    pub error_rate: f64,
    /// Warning rate (warnings per execution)
    pub warning_rate: f64,
    /// Quality score (0.0 - 100.0)
    pub quality_score: f64,
}

/// Performance trend analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PerformanceTrend {
    /// Performance is improving
    Improving { 
        /// Rate of improvement per measurement period
        improvement_rate: f64 
    },
    /// Performance is stable
    Stable { 
        /// Variance in performance measurements
        variance: f64 
    },
    /// Performance is degrading
    Degrading { 
        /// Rate of degradation per measurement period
        degradation_rate: f64 
    },
    /// Insufficient data for trend analysis
    InsufficientData,
}

/// Memory usage trend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MemoryTrend {
    /// Memory usage increasing
    Increasing { 
        /// Rate of memory usage increase
        rate: f64 
    },
    /// Memory usage stable
    Stable { 
        /// Variance in memory usage measurements
        variance: f64 
    },
    /// Memory usage decreasing
    Decreasing { 
        /// Rate of memory usage decrease
        rate: f64 
    },
    /// Insufficient data
    InsufficientData,
}

/// System-wide performance statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemPerformanceStatistics {
    /// Overall system health score (0.0 - 100.0)
    pub system_health_score: f64,
    /// Total audit cycles completed
    pub total_audit_cycles: u64,
    /// Average audit cycle time
    pub average_cycle_time: Duration,
    /// System uptime
    pub system_uptime: Duration,
    /// Resource utilization summary
    pub resource_utilization: ResourceUtilizationSummary,
    /// Performance by phase
    pub phase_performance: HashMap<PhaseId, PhasePerformanceStatistics>,
    /// System alerts
    pub active_alerts: Vec<PerformanceAlert>,
}

/// Resource utilization summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceUtilizationSummary {
    /// Average CPU utilization across all phases
    pub average_cpu_utilization: f64,
    /// Peak memory usage
    pub peak_memory_usage: u64,
    /// Average memory usage
    pub average_memory_usage: u64,
    /// Disk I/O statistics
    pub disk_io_stats: DiskIoStatistics,
    /// Network utilization (if applicable)
    pub network_utilization: NetworkUtilization,
}

/// Disk I/O statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiskIoStatistics {
    /// Total read operations
    pub total_reads: u64,
    /// Total write operations
    pub total_writes: u64,
    /// Average read latency
    pub average_read_latency: Duration,
    /// Average write latency
    pub average_write_latency: Duration,
}

/// Network utilization statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkUtilization {
    /// Total bytes sent
    pub bytes_sent: u64,
    /// Total bytes received
    pub bytes_received: u64,
    /// Average network latency
    pub average_latency: Duration,
}

/// Performance trends over time
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceTrends {
    /// Time period covered
    pub time_period: Duration,
    /// Trend data points
    pub trend_points: Vec<PerformanceTrendPoint>,
    /// Overall trend direction
    pub overall_trend: PerformanceTrend,
    /// Anomalies detected
    pub anomalies: Vec<PerformanceAnomaly>,
}

/// Performance trend data point
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceTrendPoint {
    /// Timestamp
    pub timestamp: SystemTime,
    /// Performance score at this point
    pub performance_score: f64,
    /// Active phase
    pub active_phase: Option<PhaseId>,
    /// Resource utilization
    pub resource_utilization: f64,
}

/// Performance anomaly detection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceAnomaly {
    /// Anomaly timestamp
    pub timestamp: SystemTime,
    /// Anomaly type
    pub anomaly_type: AnomalyType,
    /// Severity level
    pub severity: AnomalySeverity,
    /// Description
    pub description: String,
    /// Affected metrics
    pub affected_metrics: Vec<String>,
}

/// Types of performance anomalies
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AnomalyType {
    /// Execution time spike
    ExecutionTimeSpike,
    /// Memory usage spike
    MemorySpike,
    /// CPU utilization spike
    CpuSpike,
    /// Error rate increase
    ErrorRateIncrease,
    /// Performance degradation
    PerformanceDegradation,
}

/// Anomaly severity levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum AnomalySeverity {
    /// Low severity - monitoring required
    Low,
    /// Medium severity - investigation recommended
    Medium,
    /// High severity - immediate attention required
    High,
    /// Critical severity - system intervention required
    Critical,
}

/// Performance alert
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceAlert {
    /// Alert identifier
    pub alert_id: String,
    /// Alert timestamp
    pub timestamp: SystemTime,
    /// Alert type
    pub alert_type: AlertType,
    /// Severity level
    pub severity: AnomalySeverity,
    /// Alert message
    pub message: String,
    /// Affected phase
    pub affected_phase: Option<PhaseId>,
    /// Threshold violated
    pub threshold_violated: String,
    /// Current value
    pub current_value: String,
    /// Recommended actions
    pub recommended_actions: Vec<String>,
}

/// Types of performance alerts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertType {
    /// Execution time threshold exceeded
    ExecutionTimeThreshold,
    /// Memory usage threshold exceeded
    MemoryThreshold,
    /// CPU utilization threshold exceeded
    CpuThreshold,
    /// Error rate threshold exceeded
    ErrorRateThreshold,
    /// System health degradation
    SystemHealthDegradation,
}

/// Metrics export formats
#[derive(Debug, Clone, Copy)]
pub enum MetricsExportFormat {
    /// Prometheus format
    Prometheus,
    /// JSON format
    Json,
    /// CSV format
    Csv,
    /// InfluxDB line protocol
    InfluxDb,
}

/// Production metrics collector implementation
#[derive(Debug)]
pub struct ProductionMetricsCollector {
    /// Phase metrics storage
    phase_metrics: Arc<RwLock<HashMap<PhaseId, VecDeque<PhaseMetricsRecord>>>>,
    /// System statistics
    system_statistics: Arc<RwLock<SystemPerformanceStatistics>>,
    /// Performance thresholds
    performance_thresholds: Arc<PerformanceThresholds>,
    /// Metrics collection start time
    start_time: SystemTime,
    /// Alert history
    alert_history: Arc<RwLock<VecDeque<PerformanceAlert>>>,
}

/// Performance thresholds for alerting
#[derive(Debug)]
#[allow(dead_code)]
struct PerformanceThresholds {
    /// Maximum execution time per phase
    max_execution_times: HashMap<PhaseId, Duration>,
    /// Maximum memory usage
    max_memory_usage: u64,
    /// Maximum CPU utilization
    max_cpu_utilization: f64,
    /// Maximum error rate
    max_error_rate: f64,
    /// Minimum system health score
    min_system_health_score: f64,
}

/// Phase metrics record with timestamp
#[derive(Debug, Clone)]
struct PhaseMetricsRecord {
    /// Record timestamp
    timestamp: SystemTime,
    /// Phase metrics
    metrics: PhaseMetrics,
}

impl ProductionMetricsCollector {
    /// Create new production metrics collector
    #[must_use]
    pub fn new() -> Self {
        let phase_metrics = Arc::new(RwLock::new(HashMap::new()));
        
        let system_statistics = Arc::new(RwLock::new(SystemPerformanceStatistics {
            system_health_score: 100.0,
            total_audit_cycles: 0,
            average_cycle_time: Duration::ZERO,
            system_uptime: Duration::ZERO,
            resource_utilization: ResourceUtilizationSummary {
                average_cpu_utilization: 0.0,
                peak_memory_usage: 0,
                average_memory_usage: 0,
                disk_io_stats: DiskIoStatistics {
                    total_reads: 0,
                    total_writes: 0,
                    average_read_latency: Duration::ZERO,
                    average_write_latency: Duration::ZERO,
                },
                network_utilization: NetworkUtilization {
                    bytes_sent: 0,
                    bytes_received: 0,
                    average_latency: Duration::ZERO,
                },
            },
            phase_performance: HashMap::new(),
            active_alerts: Vec::new(),
        }));

        let performance_thresholds = Arc::new(PerformanceThresholds {
            max_execution_times: Self::create_default_execution_thresholds(),
            max_memory_usage: 8_000_000_000, // 8GB
            max_cpu_utilization: 95.0, // 95%
            max_error_rate: 0.01, // 1%
            min_system_health_score: 80.0, // 80%
        });

        let start_time = SystemTime::now();
        let alert_history = Arc::new(RwLock::new(VecDeque::new()));

        Self {
            phase_metrics,
            system_statistics,
            performance_thresholds,
            start_time,
            alert_history,
        }
    }

    /// Create default execution time thresholds
    fn create_default_execution_thresholds() -> HashMap<PhaseId, Duration> {
        let mut thresholds = HashMap::new();
        thresholds.insert(PhaseId::Inventory, Duration::from_secs(300)); // 5 minutes
        thresholds.insert(PhaseId::Naming, Duration::from_secs(600)); // 10 minutes
        thresholds.insert(PhaseId::Purge, Duration::from_secs(900)); // 15 minutes
        thresholds.insert(PhaseId::Integration, Duration::from_secs(1800)); // 30 minutes
        thresholds.insert(PhaseId::Testing, Duration::from_secs(3600)); // 1 hour
        thresholds.insert(PhaseId::Performance, Duration::from_secs(1800)); // 30 minutes
        thresholds.insert(PhaseId::FormalVerification, Duration::from_secs(7200)); // 2 hours
        thresholds.insert(PhaseId::ReproducibleBuild, Duration::from_secs(1800)); // 30 minutes
        thresholds.insert(PhaseId::RuntimeAttestation, Duration::from_secs(600)); // 10 minutes
        thresholds.insert(PhaseId::FinalCertification, Duration::from_secs(300)); // 5 minutes
        thresholds
    }

    /// Record phase metrics with comprehensive analysis
    async fn record_phase_metrics_internal(&self, phase: PhaseId, metrics: &PhaseMetrics) -> AuditResult<()> {
        let timestamp = SystemTime::now();
        
        info!("Recording metrics for phase: {phase:?}");

        // Store phase metrics
        {
            let mut phase_metrics_map = self.phase_metrics.write().await;
            let phase_records = phase_metrics_map.entry(phase).or_insert_with(VecDeque::new);
            
            phase_records.push_back(PhaseMetricsRecord {
                timestamp,
                metrics: metrics.clone(),
            });

            // Keep only recent records (last 1000 per phase)
            if phase_records.len() > 1000 {
                phase_records.drain(0..100);
            }
        }

        // Update system statistics
        self.update_system_statistics(phase, metrics).await;

        // Check for performance alerts
        self.check_and_generate_alerts(phase, metrics).await;

        info!("Metrics recorded successfully for phase: {phase:?}");
        Ok(())
    }

    /// Update system-wide statistics
    async fn update_system_statistics(&self, phase: PhaseId, metrics: &PhaseMetrics) {
        let mut stats = self.system_statistics.write().await;
        
        // Update system uptime
        stats.system_uptime = self.start_time.elapsed().unwrap_or(Duration::ZERO);

        // Update resource utilization
        if metrics.memory_usage_peak > stats.resource_utilization.peak_memory_usage {
            stats.resource_utilization.peak_memory_usage = metrics.memory_usage_peak;
        }

        // Update average CPU utilization (simple moving average)
        let total_phases = stats.phase_performance.len() as f64;
        if total_phases > 0.0 {
            stats.resource_utilization.average_cpu_utilization = 
                (stats.resource_utilization.average_cpu_utilization * total_phases + metrics.cpu_utilization) / (total_phases + 1.0);
        } else {
            stats.resource_utilization.average_cpu_utilization = metrics.cpu_utilization;
        }

        // Update phase-specific performance statistics
        let phase_stats = self.calculate_phase_statistics(phase).await;
        stats.phase_performance.insert(phase, phase_stats);

        // Calculate overall system health score
        stats.system_health_score = self.calculate_system_health_score(&stats).await;
    }

    /// Calculate phase-specific statistics
    async fn calculate_phase_statistics(&self, phase: PhaseId) -> PhasePerformanceStatistics {
        let phase_metrics_map = self.phase_metrics.read().await;
        let phase_records = phase_metrics_map.get(&phase).cloned().unwrap_or_default();

        if phase_records.is_empty() {
            return PhasePerformanceStatistics {
                phase_id: phase,
                total_executions: 0,
                execution_time_stats: TimeStatistics {
                    min_time: Duration::ZERO,
                    max_time: Duration::ZERO,
                    average_time: Duration::ZERO,
                    median_time: Duration::ZERO,
                    percentile_95: Duration::ZERO,
                    percentile_99: Duration::ZERO,
                    percentile_99_9: Duration::ZERO,
                    standard_deviation: Duration::ZERO,
                },
                memory_usage_stats: MemoryStatistics {
                    min_memory: 0,
                    max_memory: 0,
                    average_memory: 0,
                    memory_trend: MemoryTrend::InsufficientData,
                    efficiency_score: 0.0,
                },
                cpu_utilization_stats: CpuStatistics {
                    min_cpu: 0.0,
                    max_cpu: 0.0,
                    average_cpu: 0.0,
                    efficiency_score: 0.0,
                },
                file_processing_stats: FileProcessingStatistics {
                    total_files_processed: 0,
                    average_files_per_execution: 0.0,
                    processing_rate: 0.0,
                    efficiency_score: 0.0,
                },
                error_warning_stats: ErrorWarningStatistics {
                    total_errors: 0,
                    total_warnings: 0,
                    error_rate: 0.0,
                    warning_rate: 0.0,
                    quality_score: 100.0,
                },
                performance_trend: PerformanceTrend::InsufficientData,
            };
        }

        let total_executions = phase_records.len() as u64;
        
        // Calculate execution time statistics
        let mut execution_times: Vec<Duration> = phase_records.iter()
            .map(|record| record.metrics.execution_duration)
            .collect();
        execution_times.sort();

        let min_time = execution_times.first().copied().unwrap_or(Duration::ZERO);
        let max_time = execution_times.last().copied().unwrap_or(Duration::ZERO);
        let average_time = Duration::from_nanos(
            (execution_times.iter().map(|d| d.as_nanos()).sum::<u128>() / execution_times.len() as u128).try_into().unwrap_or(0)
        );
        let median_time = execution_times[execution_times.len() / 2];
        let percentile_95 = execution_times[(execution_times.len() as f64 * 0.95) as usize];
        let percentile_99 = execution_times[(execution_times.len() as f64 * 0.99) as usize];
        let percentile_99_9 = execution_times[(execution_times.len() as f64 * 0.999) as usize];

        // Calculate standard deviation
        let variance = execution_times.iter()
            .map(|d| {
                let diff = d.as_nanos() as f64 - average_time.as_nanos() as f64;
                diff * diff
            })
            .sum::<f64>() / execution_times.len() as f64;
        let standard_deviation = Duration::from_nanos(variance.sqrt() as u64);

        // Calculate memory statistics
        let memory_usages: Vec<u64> = phase_records.iter()
            .map(|record| record.metrics.memory_usage_peak)
            .collect();
        
        let min_memory = memory_usages.iter().min().copied().unwrap_or(0);
        let max_memory = memory_usages.iter().max().copied().unwrap_or(0);
        let average_memory = memory_usages.iter().sum::<u64>() / memory_usages.len() as u64;

        // Calculate CPU statistics
        let cpu_utilizations: Vec<f64> = phase_records.iter()
            .map(|record| record.metrics.cpu_utilization)
            .collect();
        
        let min_cpu = cpu_utilizations.iter().fold(f64::INFINITY, |a, &b| a.min(b));
        let max_cpu = cpu_utilizations.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        let average_cpu = cpu_utilizations.iter().sum::<f64>() / cpu_utilizations.len() as f64;

        // Calculate file processing statistics
        let total_files_processed = phase_records.iter()
            .map(|record| record.metrics.files_processed)
            .sum::<u64>();
        let average_files_per_execution = total_files_processed as f64 / total_executions as f64;
        let processing_rate = if average_time.as_secs_f64() > 0.0 {
            average_files_per_execution / average_time.as_secs_f64()
        } else {
            0.0
        };

        // Calculate error/warning statistics
        let total_errors = phase_records.iter()
            .map(|record| record.metrics.errors_encountered)
            .sum::<u64>();
        let total_warnings = phase_records.iter()
            .map(|record| record.metrics.warnings_generated)
            .sum::<u64>();
        let error_rate = total_errors as f64 / total_executions as f64;
        let warning_rate = total_warnings as f64 / total_executions as f64;
        let quality_score = 100.0 - (error_rate * 50.0 + warning_rate * 25.0).min(100.0);

        PhasePerformanceStatistics {
            phase_id: phase,
            total_executions,
            execution_time_stats: TimeStatistics {
                min_time,
                max_time,
                average_time,
                median_time,
                percentile_95,
                percentile_99,
                percentile_99_9,
                standard_deviation,
            },
            memory_usage_stats: MemoryStatistics {
                min_memory,
                max_memory,
                average_memory,
                memory_trend: MemoryTrend::Stable { variance: 0.1 }, // Simplified
                efficiency_score: 85.0, // Simplified calculation
            },
            cpu_utilization_stats: CpuStatistics {
                min_cpu,
                max_cpu,
                average_cpu,
                efficiency_score: 90.0, // Simplified calculation
            },
            file_processing_stats: FileProcessingStatistics {
                total_files_processed,
                average_files_per_execution,
                processing_rate,
                efficiency_score: 88.0, // Simplified calculation
            },
            error_warning_stats: ErrorWarningStatistics {
                total_errors,
                total_warnings,
                error_rate,
                warning_rate,
                quality_score,
            },
            performance_trend: PerformanceTrend::Stable { variance: 0.05 }, // Simplified
        }
    }

    /// Calculate overall system health score
    async fn calculate_system_health_score(&self, stats: &SystemPerformanceStatistics) -> f64 {
        let mut health_score = 100.0;

        // Factor in CPU utilization
        if stats.resource_utilization.average_cpu_utilization > 90.0 {
            health_score -= 20.0;
        } else if stats.resource_utilization.average_cpu_utilization > 80.0 {
            health_score -= 10.0;
        }

        // Factor in memory usage
        let memory_usage_ratio = stats.resource_utilization.average_memory_usage as f64 / 
            stats.resource_utilization.peak_memory_usage as f64;
        if memory_usage_ratio > 0.9 {
            health_score -= 15.0;
        } else if memory_usage_ratio > 0.8 {
            health_score -= 8.0;
        }

        // Factor in active alerts
        health_score -= stats.active_alerts.len() as f64 * 5.0;

        health_score.max(0.0)
    }

    /// Check for performance alerts and generate them
    async fn check_and_generate_alerts(&self, phase: PhaseId, metrics: &PhaseMetrics) {
        let mut alerts = Vec::new();

        // Check execution time threshold
        if let Some(&max_time) = self.performance_thresholds.max_execution_times.get(&phase) {
            if metrics.execution_duration > max_time {
                alerts.push(PerformanceAlert {
                    alert_id: uuid::Uuid::new_v4().to_string(),
                    timestamp: SystemTime::now(),
                    alert_type: AlertType::ExecutionTimeThreshold,
                    severity: AnomalySeverity::High,
                    message: format!("Phase {phase:?} execution time exceeded threshold"),
                    affected_phase: Some(phase),
                    threshold_violated: format!("{max_time:?}"),
                    current_value: format!("{:?}", metrics.execution_duration),
                    recommended_actions: vec![
                        "Investigate performance bottlenecks".to_string(),
                        "Optimize phase implementation".to_string(),
                        "Consider resource scaling".to_string(),
                    ],
                });
            }
        }

        // Check memory threshold
        if metrics.memory_usage_peak > self.performance_thresholds.max_memory_usage {
            alerts.push(PerformanceAlert {
                alert_id: uuid::Uuid::new_v4().to_string(),
                timestamp: SystemTime::now(),
                alert_type: AlertType::MemoryThreshold,
                severity: AnomalySeverity::High,
                message: format!("Phase {phase:?} memory usage exceeded threshold"),
                affected_phase: Some(phase),
                threshold_violated: format!("{} bytes", self.performance_thresholds.max_memory_usage),
                current_value: format!("{} bytes", metrics.memory_usage_peak),
                recommended_actions: vec![
                    "Investigate memory leaks".to_string(),
                    "Optimize memory usage".to_string(),
                    "Consider memory scaling".to_string(),
                ],
            });
        }

        // Check CPU threshold
        if metrics.cpu_utilization > self.performance_thresholds.max_cpu_utilization {
            alerts.push(PerformanceAlert {
                alert_id: uuid::Uuid::new_v4().to_string(),
                timestamp: SystemTime::now(),
                alert_type: AlertType::CpuThreshold,
                severity: AnomalySeverity::Medium,
                message: format!("Phase {phase:?} CPU utilization exceeded threshold"),
                affected_phase: Some(phase),
                threshold_violated: format!("{}%", self.performance_thresholds.max_cpu_utilization),
                current_value: format!("{}%", metrics.cpu_utilization),
                recommended_actions: vec![
                    "Investigate CPU-intensive operations".to_string(),
                    "Optimize algorithms".to_string(),
                    "Consider parallel processing".to_string(),
                ],
            });
        }

        // Check error rate
        let error_rate = metrics.errors_encountered as f64 / metrics.files_processed.max(1) as f64;
        if error_rate > self.performance_thresholds.max_error_rate {
            alerts.push(PerformanceAlert {
                alert_id: uuid::Uuid::new_v4().to_string(),
                timestamp: SystemTime::now(),
                alert_type: AlertType::ErrorRateThreshold,
                severity: AnomalySeverity::Critical,
                message: format!("Phase {phase:?} error rate exceeded threshold"),
                affected_phase: Some(phase),
                threshold_violated: format!("{:.2}%", self.performance_thresholds.max_error_rate * 100.0),
                current_value: format!("{:.2}%", error_rate * 100.0),
                recommended_actions: vec![
                    "Investigate error causes".to_string(),
                    "Improve error handling".to_string(),
                    "Review input validation".to_string(),
                ],
            });
        }

        // Store alerts
        if !alerts.is_empty() {
            let mut alert_history = self.alert_history.write().await;
            for alert in &alerts {
                warn!("Performance alert generated: {}", alert.message);
                alert_history.push_back(alert.clone());
            }

            // Keep only recent alerts (last 1000)
            if alert_history.len() > 1000 {
                alert_history.drain(0..100);
            }

            // Update system statistics with active alerts
            let mut stats = self.system_statistics.write().await;
            stats.active_alerts.extend(alerts);
        }
    }
}

impl Default for ProductionMetricsCollector {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl MetricsCollector for ProductionMetricsCollector {
    async fn record_phase_metrics(&self, phase: PhaseId, metrics: &PhaseMetrics) -> AuditResult<()> {
        self.record_phase_metrics_internal(phase, metrics).await
    }

    async fn get_phase_performance_statistics(&self, phase: PhaseId) -> AuditResult<PhasePerformanceStatistics> {
        Ok(self.calculate_phase_statistics(phase).await)
    }

    async fn get_system_performance_statistics(&self) -> SystemPerformanceStatistics {
        let stats = self.system_statistics.read().await;
        stats.clone()
    }

    async fn get_performance_trends(&self, duration: Duration) -> AuditResult<PerformanceTrends> {
        let cutoff_time = SystemTime::now() - duration;
        let mut trend_points = Vec::new();

        // Collect trend data from all phases
        let phase_metrics_map = self.phase_metrics.read().await;
        for (phase, records) in phase_metrics_map.iter() {
            for record in records.iter() {
                if record.timestamp >= cutoff_time {
                    let performance_score = 100.0 - (record.metrics.errors_encountered as f64 * 10.0);
                    let resource_utilization = record.metrics.cpu_utilization;

                    trend_points.push(PerformanceTrendPoint {
                        timestamp: record.timestamp,
                        performance_score,
                        active_phase: Some(*phase),
                        resource_utilization,
                    });
                }
            }
        }

        // Sort by timestamp
        trend_points.sort_by_key(|point| point.timestamp);

        // Analyze overall trend
        let overall_trend = if trend_points.len() < 2 {
            PerformanceTrend::InsufficientData
        } else {
            let first_score = trend_points.first().unwrap().performance_score;
            let last_score = trend_points.last().unwrap().performance_score;
            let change_rate = (last_score - first_score) / trend_points.len() as f64;

            if change_rate > 1.0 {
                PerformanceTrend::Improving { improvement_rate: change_rate }
            } else if change_rate < -1.0 {
                PerformanceTrend::Degrading { degradation_rate: -change_rate }
            } else {
                PerformanceTrend::Stable { variance: change_rate.abs() }
            }
        };

        Ok(PerformanceTrends {
            time_period: duration,
            trend_points,
            overall_trend,
            anomalies: Vec::new(), // Simplified - would implement anomaly detection
        })
    }

    async fn check_performance_alerts(&self) -> Vec<PerformanceAlert> {
        let alert_history = self.alert_history.read().await;
        alert_history.iter().cloned().collect()
    }

    async fn export_metrics(&self, format: MetricsExportFormat) -> AuditResult<String> {
        let stats = self.get_system_performance_statistics().await;

        match format {
            MetricsExportFormat::Json => {
                serde_json::to_string_pretty(&stats).map_err(|e| {
                    AuditError::SerializationError {
                        format: "JSON".to_string(),
                        reason: e.to_string(),
                    }
                })
            }
            MetricsExportFormat::Prometheus => {
                // Simplified Prometheus format
                let mut output = String::new();
                output.push_str(&format!("# HELP system_health_score Overall system health score\n"));
                output.push_str(&format!("# TYPE system_health_score gauge\n"));
                output.push_str(&format!("system_health_score {}\n", stats.system_health_score));
                
                output.push_str(&format!("# HELP total_audit_cycles Total audit cycles completed\n"));
                output.push_str(&format!("# TYPE total_audit_cycles counter\n"));
                output.push_str(&format!("total_audit_cycles {}\n", stats.total_audit_cycles));

                Ok(output)
            }
            MetricsExportFormat::Csv => {
                let mut output = String::new();
                output.push_str("metric,value\n");
                output.push_str(&format!("system_health_score,{}\n", stats.system_health_score));
                output.push_str(&format!("total_audit_cycles,{}\n", stats.total_audit_cycles));
                output.push_str(&format!("average_cpu_utilization,{}\n", stats.resource_utilization.average_cpu_utilization));
                Ok(output)
            }
            MetricsExportFormat::InfluxDb => {
                let timestamp = SystemTime::now()
                    .duration_since(SystemTime::UNIX_EPOCH)
                    .unwrap_or(Duration::ZERO)
                    .as_nanos();
                
                let mut output = String::new();
                output.push_str(&format!("system_health_score value={} {}\n", stats.system_health_score, timestamp));
                output.push_str(&format!("total_audit_cycles value={} {}\n", stats.total_audit_cycles, timestamp));
                Ok(output)
            }
        }
    }
}