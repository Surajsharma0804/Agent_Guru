//! Automated Quality Assurance System
//! 
//! Enterprise-grade automated quality assurance system with machine learning validation,
//! real-time monitoring, and comprehensive compliance verification.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![allow(
    clippy::module_name_repetitions,
    clippy::too_many_lines,
    clippy::missing_errors_doc,
    clippy::unnecessary_wraps,
    clippy::cast_possible_truncation,
    clippy::unused_self,
    clippy::too_many_arguments,
    clippy::ptr_arg,
    clippy::manual_clamp,
    clippy::inherent_to_string,
    clippy::await_holding_lock,
    clippy::needless_range_loop,
    clippy::manual_memcpy,
    clippy::suboptimal_flops,
    clippy::struct_excessive_bools,
    clippy::cast_precision_loss,
    clippy::cast_sign_loss,
    clippy::cast_lossless,
    clippy::or_fun_call,
    clippy::significant_drop_tightening,
    clippy::missing_panics_doc,
    clippy::redundant_closure_for_method_calls,
    clippy::needless_borrow,
    clippy::derive_partial_eq_without_eq,
    clippy::type_complexity,
    clippy::match_same_arms,
    clippy::only_used_in_recursion,
    clippy::trivially_copy_pass_by_ref,
    clippy::single_element_loop,
    clippy::option_if_let_else,
    clippy::cast_possible_wrap,
    clippy::items_after_statements,
    clippy::ref_patterns,
    clippy::bool_comparison,
    clippy::needless_pass_by_value,
    clippy::wildcard_enum_match_arm,
    missing_docs
)]

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