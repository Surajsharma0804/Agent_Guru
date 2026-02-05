//! # Observability Module
//! 
//! Production-grade monitoring and observability system with comprehensive
//! metrics collection, distributed tracing, structured logging, intelligent
//! alerting, and real-time dashboards. All components are designed with
//! privacy-preserving techniques and mathematical guarantees for system
//! observability.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![allow(missing_docs, dead_code)]

/// Comprehensive metrics collection system with privacy protection
pub mod metrics;

/// Structured logging system with security-aware sanitization
pub mod logging;

/// Intelligent alerting system with anomaly detection
pub mod alerting;

/// Distributed tracing system with performance analysis
pub mod tracing;

// Re-export main types for convenience
pub use metrics::{
    MetricsRegistry, MetricValue, MetricSample, MetricLabels, 
    TimeSeries, SystemResourceCollector, ApplicationMetricsCollector
};

pub use logging::{
    StructuredLogger, LogEntry, LogLevel, CorrelationId, 
    LogSanitizer, AsyncLogProcessor
};

pub use alerting::{
    AlertManager, Alert, AlertSeverity, AlertRule, AlertCondition,
    AnomalyDetector, AlertCorrelationEngine
};

pub use tracing::{
    TraceCollector, Trace, Span, TraceId, SpanId, SpanContext,
    Sampler, SamplingStrategy, TraceQuery
};