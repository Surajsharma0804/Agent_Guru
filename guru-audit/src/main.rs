//! GURU Production Audit System - Main Entry Point
//!
//! This is the main entry point for the GURU Production Audit System.
//! The system implements a comprehensive, zero-tolerance quality enforcement
//! framework with formal verification and cryptographic security.

use guru_audit::{
    config::ConfigLoader,
    core::{
        controller::{AuditController, ProductionAuditController},
        checkpoint::ProductionCheckpointManager,
        metrics::ProductionMetricsCollector,
        phase_manager::ProductionPhaseManager,
        quality_gates::ProductionQualityGates,
    },
    error::AuditResult,
};
use std::sync::Arc;
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> AuditResult<()> {
    // Initialize logging
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "guru_audit=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Starting GURU Production Audit System v{}", guru_audit::VERSION);
    info!("Zero Tolerance Policy: {}", guru_audit::ZERO_TOLERANCE_POLICY);

    // Load configuration
    let config_loader = ConfigLoader::new();
    let config = match config_loader.load() {
        Ok(config) => {
            info!("Configuration loaded successfully");
            config
        }
        Err(error) => {
            error!("Failed to load configuration: {error}");
            return Err(error);
        }
    };

    info!("Audit ID: {:?}", config.audit_id);
    info!("Target repository: {:?}", config.target_repository.root_path);
    info!("Quality gates: {} property test iterations", config.quality_gates.property_test_iterations);

    // Initialize core components
    info!("Initializing audit system components...");

    let phase_manager = Arc::new(ProductionPhaseManager::new());
    let quality_gates = Arc::new(ProductionQualityGates::new());
    let checkpoint_manager = Arc::new(ProductionCheckpointManager::new());
    let metrics_collector = Arc::new(ProductionMetricsCollector::new());

    // Create audit controller
    let controller = match ProductionAuditController::new(
        phase_manager,
        quality_gates,
        checkpoint_manager,
        metrics_collector,
    ).await {
        Ok(controller) => {
            info!("Audit controller initialized successfully");
            controller
        }
        Err(error) => {
            error!("Failed to initialize audit controller: {error}");
            return Err(error);
        }
    };

    info!("Cryptographic verification key: {}", controller.verifying_key().key_id());

    // Execute audit cycle
    info!("Starting audit cycle execution...");
    
    match controller.execute_audit_cycle(config).await {
        Ok(result) => {
            info!("Audit cycle completed successfully");
            info!("Overall status: {:?}", result.overall_status);
            info!("Phases executed: {}", result.phase_results.len());
            info!("Audit duration: {:?}", result.audit_duration);
            
            // Display quality metrics
            info!("Quality Metrics:");
            info!("  Compiler warnings: {}", result.quality_metrics.compiler_warnings);
            info!("  Runtime errors: {}", result.quality_metrics.runtime_errors);
            info!("  Unused files: {}", result.quality_metrics.unused_files);
            info!("  Test pass rate: {:.2}%", result.quality_metrics.test_pass_rate);
            info!("  Code coverage: {:.2}%", result.quality_metrics.code_coverage);
            info!("  Property test iterations: {}", result.quality_metrics.property_test_iterations);
            
            // Display compliance status
            info!("Compliance Status:");
            info!("  Clean room compliance: {}", result.compliance_status.clean_room_compliance);
            info!("  Security compliance: {}", result.compliance_status.security_compliance);
            info!("  Performance compliance: {}", result.compliance_status.performance_compliance);

            if let Some(certification) = result.certification {
                info!("Final Certification: {}", certification.certification_id);
                info!("Certification timestamp: {:?}", certification.certification_timestamp);
            } else {
                warn!("No final certification generated - audit may have failed");
            }
        }
        Err(error) => {
            error!("Audit cycle failed: {error}");
            
            // Attempt to generate report for failed audit
            let active_cycles = controller.get_active_cycles().await;
            if let Some(active_cycle) = active_cycles.into_iter().next() {
                if let Ok(report) = controller.generate_audit_report(active_cycle).await {
                    warn!("Generated failure report: {}", report.report_id);
                    warn!("Executive summary: {}", report.executive_summary.overall_status);
                }
            }
            
            return Err(error);
        }
    }

    info!("GURU Production Audit System completed successfully");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use guru_audit::config::ConfigBuilder;
    use guru_audit::types::RepositoryConfig;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_main_initialization() {
        // Test that the main components can be initialized
        let temp_dir = TempDir::new().unwrap();
        
        let _config = ConfigBuilder::new()
            .repository_config(RepositoryConfig {
                root_path: temp_dir.path().to_path_buf(),
                branch: "main".to_string(),
                commit_hash: None,
                excluded_paths: Vec::new(),
                included_patterns: vec!["**/*.rs".to_string()],
            })
            .build()
            .unwrap();

        // Initialize components
        let phase_manager = Arc::new(ProductionPhaseManager::new());
        let quality_gates = Arc::new(ProductionQualityGates::new());
        let checkpoint_manager = Arc::new(ProductionCheckpointManager::new());
        let metrics_collector = Arc::new(ProductionMetricsCollector::new());

        // Create controller
        let controller = ProductionAuditController::new(
            phase_manager,
            quality_gates,
            checkpoint_manager,
            metrics_collector,
        ).await;

        assert!(controller.is_ok());
        
        let controller = controller.unwrap();
        assert!(!controller.verifying_key().key_id().is_empty());
    }
}