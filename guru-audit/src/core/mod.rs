//! Core audit system components
//!
//! This module contains the fundamental components of the GURU Production Audit System,
//! including the audit controller, phase manager, quality gates, checkpoint manager,
//! and metrics collector. All components are designed for production-grade operation
//! with formal verification and zero-tolerance quality enforcement.

pub mod controller;
pub mod phase_manager;
pub mod quality_gates;
pub mod checkpoint;
pub mod metrics;

#[cfg(test)]
pub mod property_tests;

// Re-export core types for convenience
pub use controller::{AuditController, ProductionAuditController};
pub use phase_manager::{PhaseManager, ProductionPhaseManager, PhaseStatistics, PrerequisiteStatus};
pub use quality_gates::{QualityGates, ProductionQualityGates, QualityValidationResult, QualityValidationStatistics};
pub use checkpoint::{CheckpointManager, ProductionCheckpointManager, CheckpointInfo, CheckpointStatistics};
pub use metrics::{MetricsCollector, ProductionMetricsCollector, PhasePerformanceStatistics, SystemPerformanceStatistics};