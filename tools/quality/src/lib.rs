//! Automated Quality Assurance System
//! 
//! Enterprise-grade automated quality assurance system with machine learning validation,
//! real-time monitoring, and comprehensive compliance verification.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![allow(clippy::module_name_repetitions)]
#![allow(clippy::too_many_lines)]

pub mod monitor;
pub mod reporting;
pub mod compliance;

// Re-export main types for convenience
pub use monitor::{
    QualityMonitor, QualityMetrics, MetricType, TrendDirection, 
    QualityAlert, AlertLevel, QualityError
};

pub use reporting::{
    QualityReporter, QualityReport, DashboardConfig, DashboardLayout, 
    LayoutType, ReportPeriod, ReportingError
};

pub use compliance::{
    ComplianceVerifier, ComplianceReport, ComplianceScope, VerificationDepth,
    ComplianceError
};

/// Version information
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Quality assurance system configuration
#[derive(Debug, Clone)]
pub struct QualityConfig {
    pub monitoring_enabled: bool,
    pub compliance_enabled: bool,
    pub reporting_enabled: bool,
    pub real_time_alerts: bool,
    pub audit_logging: bool,
}

impl Default for QualityConfig {
    fn default() -> Self {
        Self {
            monitoring_enabled: true,
            compliance_enabled: true,
            reporting_enabled: true,
            real_time_alerts: true,
            audit_logging: true,
        }
    }
}

/// Initialize the quality assurance system
pub fn initialize(config: QualityConfig) -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt::init();
    
    tracing::info!("Initializing Quality Assurance System v{}", VERSION);
    tracing::info!("Configuration: {:?}", config);
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_version() {
        assert!(!VERSION.is_empty());
    }
    
    #[test]
    fn test_default_config() {
        let config = QualityConfig::default();
        assert!(config.monitoring_enabled);
        assert!(config.compliance_enabled);
        assert!(config.reporting_enabled);
        assert!(config.real_time_alerts);
        assert!(config.audit_logging);
    }
    
    #[test]
    fn test_initialization() {
        let config = QualityConfig::default();
        let result = initialize(config);
        assert!(result.is_ok());
    }
}