//! Observability Type Definitions
//!
//! Comprehensive type system for monitoring, tracing, logging, and alerting with privacy preservation.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, SystemTime};
use uuid::Uuid;

/// Unique identifier for metrics
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct MetricId(pub Uuid);

impl MetricId {
    /// Generate a new unique metric identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for MetricId {
    fn default() -> Self {
        Self::new()
    }
}

/// Unique identifier for traces
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TraceId(pub Uuid);

impl TraceId {
    /// Generate a new unique trace identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for TraceId {
    fn default() -> Self {
        Self::new()
    }
}

/// Unique identifier for spans within traces
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct SpanId(pub Uuid);

impl SpanId {
    /// Generate a new unique span identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for SpanId {
    fn default() -> Self {
        Self::new()
    }
}

/// Unique identifier for log entries
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct LogId(pub Uuid);

impl LogId {
    /// Generate a new unique log identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for LogId {
    fn default() -> Self {
        Self::new()
    }
}

/// Unique identifier for alerts
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct AlertId(pub Uuid);

impl AlertId {
    /// Generate a new unique alert identifier
    #[must_use]
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}

impl Default for AlertId {
    fn default() -> Self {
        Self::new()
    }
}

/// Metric Data Point
///
/// Single metric measurement with timestamp and metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricDataPoint {
    pub metric_id: MetricId,
    pub metric_name: String,
    pub metric_type: MetricType,
    pub value: MetricValue,
    pub timestamp: SystemTime,
    pub tags: HashMap<String, String>,
    pub privacy_level: PrivacyLevel,
}

/// Metric Type Classification
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MetricType {
    /// Counter: monotonically increasing value
    Counter,
    /// Gauge: point-in-time value that can increase or decrease
    Gauge,
    /// Histogram: distribution of values
    Histogram,
    /// Summary: statistical summary of observations
    Summary,
    /// Timer: duration measurements
    Timer,
}

/// Metric Value
///
/// Typed metric value supporting various numeric types.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MetricValue {
    /// Integer counter value
    Counter(u64),
    /// Floating-point gauge value
    Gauge(f64),
    /// Histogram bucket distribution
    Histogram {
        buckets: Vec<HistogramBucket>,
        count: u64,
        sum: f64,
    },
    /// Summary with quantiles
    Summary {
        quantiles: Vec<Quantile>,
        count: u64,
        sum: f64,
    },
    /// Duration measurement
    Timer(Duration),
}

/// Histogram Bucket
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistogramBucket {
    pub upper_bound: f64,
    pub count: u64,
}

/// Quantile for summary metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Quantile {
    pub quantile: f64,
    pub value: f64,
}

/// Privacy Level for Data Anonymization
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum PrivacyLevel {
    /// Public: No sensitive information
    Public,
    /// Internal: Internal use only, no PII
    Internal,
    /// Confidential: Contains aggregated sensitive data
    Confidential,
    /// Secret: Contains individual sensitive data, must be anonymized
    Secret,
}

/// Distributed Trace
///
/// Complete distributed trace with all spans and metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DistributedTrace {
    pub trace_id: TraceId,
    pub root_span: Span,
    pub child_spans: Vec<Span>,
    pub start_time: SystemTime,
    pub end_time: Option<SystemTime>,
    pub total_duration: Option<Duration>,
    pub service_name: String,
    pub trace_metadata: HashMap<String, String>,
}

/// Span within a Distributed Trace
///
/// Individual operation span with timing and metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Span {
    pub span_id: SpanId,
    pub trace_id: TraceId,
    pub parent_span_id: Option<SpanId>,
    pub operation_name: String,
    pub start_time: SystemTime,
    pub end_time: Option<SystemTime>,
    pub duration: Option<Duration>,
    pub tags: HashMap<String, String>,
    pub logs: Vec<SpanLog>,
    pub status: SpanStatus,
}

/// Span Status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SpanStatus {
    /// Operation in progress
    InProgress,
    /// Operation completed successfully
    Success,
    /// Operation failed with error
    Error,
    /// Operation was cancelled
    Cancelled,
}

/// Span Log Entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpanLog {
    pub timestamp: SystemTime,
    pub message: String,
    pub fields: HashMap<String, String>,
}

/// Structured Log Entry
///
/// Security-aware structured log with correlation and sanitization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StructuredLogEntry {
    pub log_id: LogId,
    pub timestamp: SystemTime,
    pub level: LogLevel,
    pub message: String,
    pub fields: HashMap<String, String>,
    pub trace_id: Option<TraceId>,
    pub span_id: Option<SpanId>,
    pub source_location: SourceLocation,
    pub privacy_level: PrivacyLevel,
    pub sanitized: bool,
}

/// Log Level
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum LogLevel {
    /// Trace: Very detailed debugging information
    Trace,
    /// Debug: Debugging information
    Debug,
    /// Info: Informational messages
    Info,
    /// Warn: Warning messages
    Warn,
    /// Error: Error messages
    Error,
    /// Fatal: Fatal error messages
    Fatal,
}

/// Source Location for Log Entries
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceLocation {
    pub file: String,
    pub line: u32,
    pub module: String,
    pub function: Option<String>,
}

/// Alert Definition
///
/// Intelligent alert with anomaly detection and noise reduction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    pub alert_id: AlertId,
    pub alert_name: String,
    pub alert_type: AlertType,
    pub severity: AlertSeverity,
    pub condition: AlertCondition,
    pub triggered_at: SystemTime,
    pub resolved_at: Option<SystemTime>,
    pub status: AlertStatus,
    pub metadata: HashMap<String, String>,
    pub notification_channels: Vec<NotificationChannel>,
}

/// Alert Type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertType {
    /// Threshold-based alert
    Threshold,
    /// Anomaly detection alert
    Anomaly,
    /// Rate of change alert
    RateOfChange,
    /// Pattern matching alert
    Pattern,
    /// Composite alert (multiple conditions)
    Composite,
}

/// Alert Severity
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum AlertSeverity {
    /// Info: Informational alert
    Info,
    /// Warning: Warning level alert
    Warning,
    /// Error: Error level alert
    Error,
    /// Critical: Critical alert requiring immediate attention
    Critical,
    /// Fatal: Fatal alert indicating system failure
    Fatal,
}

/// Alert Condition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertCondition {
    pub metric_name: String,
    pub operator: ComparisonOperator,
    pub threshold: f64,
    pub duration: Duration,
    pub evaluation_window: Duration,
}

/// Comparison Operator for Alert Conditions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ComparisonOperator {
    /// Greater than
    GreaterThan,
    /// Greater than or equal
    GreaterThanOrEqual,
    /// Less than
    LessThan,
    /// Less than or equal
    LessThanOrEqual,
    /// Equal
    Equal,
    /// Not equal
    NotEqual,
}

/// Alert Status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AlertStatus {
    /// Alert is active and firing
    Firing,
    /// Alert condition is met but in grace period
    Pending,
    /// Alert has been resolved
    Resolved,
    /// Alert has been acknowledged
    Acknowledged,
    /// Alert has been silenced
    Silenced,
}

/// Notification Channel
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NotificationChannel {
    /// Email notification
    Email { addresses: Vec<String> },
    /// Webhook notification
    Webhook { url: String },
    /// Slack notification
    Slack { channel: String, webhook_url: String },
    /// PagerDuty notification
    PagerDuty { integration_key: String },
    /// Custom notification
    Custom { name: String, config: HashMap<String, String> },
}

/// Dashboard Configuration
///
/// Real-time dashboard with customizable visualization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardConfig {
    pub dashboard_id: String,
    pub dashboard_name: String,
    pub refresh_rate_ms: u64,
    pub panels: Vec<DashboardPanel>,
    pub time_range: TimeRange,
    pub variables: HashMap<String, String>,
}

/// Dashboard Panel
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardPanel {
    pub panel_id: String,
    pub panel_title: String,
    pub panel_type: PanelType,
    pub metrics: Vec<String>,
    pub visualization_config: VisualizationConfig,
}

/// Panel Type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PanelType {
    /// Time series graph
    TimeSeries,
    /// Bar chart
    BarChart,
    /// Pie chart
    PieChart,
    /// Gauge
    Gauge,
    /// Table
    Table,
    /// Heatmap
    Heatmap,
    /// Single stat
    SingleStat,
}

/// Visualization Configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VisualizationConfig {
    pub colors: Vec<String>,
    pub thresholds: Vec<Threshold>,
    pub legend_position: LegendPosition,
    pub axis_config: AxisConfig,
}

/// Threshold for Visualization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Threshold {
    pub value: f64,
    pub color: String,
    pub label: Option<String>,
}

/// Legend Position
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum LegendPosition {
    Top,
    Bottom,
    Left,
    Right,
    None,
}

/// Axis Configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AxisConfig {
    pub x_axis_label: Option<String>,
    pub y_axis_label: Option<String>,
    pub x_axis_scale: AxisScale,
    pub y_axis_scale: AxisScale,
}

/// Axis Scale
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum AxisScale {
    Linear,
    Logarithmic,
    Time,
}

/// Time Range for Dashboard
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeRange {
    pub start: SystemTime,
    pub end: SystemTime,
    pub relative: Option<RelativeTimeRange>,
}

/// Relative Time Range
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum RelativeTimeRange {
    Last5Minutes,
    Last15Minutes,
    Last30Minutes,
    Last1Hour,
    Last3Hours,
    Last6Hours,
    Last12Hours,
    Last24Hours,
    Last7Days,
    Last30Days,
}

/// Monitoring Configuration
///
/// Complete monitoring system configuration with privacy preservation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitoringConfig {
    pub metrics_collection_interval_ms: u64,
    pub tracing_sample_rate: f64,
    pub log_level: LogLevel,
    pub privacy_preservation_enabled: bool,
    pub data_anonymization_enabled: bool,
    pub secure_aggregation_enabled: bool,
    pub retention_policy: RetentionPolicy,
}

impl Default for MonitoringConfig {
    fn default() -> Self {
        Self {
            metrics_collection_interval_ms: 1000,
            tracing_sample_rate: 0.1,
            log_level: LogLevel::Info,
            privacy_preservation_enabled: true,
            data_anonymization_enabled: true,
            secure_aggregation_enabled: true,
            retention_policy: RetentionPolicy::default(),
        }
    }
}

/// Retention Policy for Monitoring Data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetentionPolicy {
    pub metrics_retention_days: u32,
    pub traces_retention_days: u32,
    pub logs_retention_days: u32,
    pub alerts_retention_days: u32,
}

impl Default for RetentionPolicy {
    fn default() -> Self {
        Self {
            metrics_retention_days: 30,
            traces_retention_days: 7,
            logs_retention_days: 90,
            alerts_retention_days: 365,
        }
    }
}

/// Performance Overhead Metrics
///
/// Metrics for monitoring system overhead with <1% CPU and memory impact.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceOverhead {
    pub cpu_overhead_percentage: f64,
    pub memory_overhead_bytes: u64,
    pub latency_overhead_ms: f64,
    pub collection_rate_per_second: u64,
    pub processing_rate_per_second: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_metric_id_generation() {
        let id1 = MetricId::new();
        let id2 = MetricId::new();
        assert_ne!(id1, id2);
    }

    #[test]
    fn test_trace_id_generation() {
        let id1 = TraceId::new();
        let id2 = TraceId::new();
        assert_ne!(id1, id2);
    }

    #[test]
    fn test_privacy_level_ordering() {
        assert!(PrivacyLevel::Secret > PrivacyLevel::Confidential);
        assert!(PrivacyLevel::Confidential > PrivacyLevel::Internal);
        assert!(PrivacyLevel::Internal > PrivacyLevel::Public);
    }

    #[test]
    fn test_log_level_ordering() {
        assert!(LogLevel::Fatal > LogLevel::Error);
        assert!(LogLevel::Error > LogLevel::Warn);
        assert!(LogLevel::Warn > LogLevel::Info);
        assert!(LogLevel::Info > LogLevel::Debug);
        assert!(LogLevel::Debug > LogLevel::Trace);
    }

    #[test]
    fn test_alert_severity_ordering() {
        assert!(AlertSeverity::Fatal > AlertSeverity::Critical);
        assert!(AlertSeverity::Critical > AlertSeverity::Error);
        assert!(AlertSeverity::Error > AlertSeverity::Warning);
        assert!(AlertSeverity::Warning > AlertSeverity::Info);
    }
}
