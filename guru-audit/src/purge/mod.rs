//! Dead Code Purge System
//!
//! This module provides comprehensive dead code elimination with static analysis,
//! dependency tracing, safety verification, and secure deletion. Designed for
//! production-grade code quality improvement with zero data loss risk.
//!
//! # Architecture
//!
//! The purge system consists of five main components:
//!
//! 1. **Static Analyzer**: LLVM-based static analysis with control flow graphs
//! 2. **Dependency Tracer**: Comprehensive dependency analysis and reachability computation
//! 3. **Safety Verifier**: Impact assessment and rollback capability testing
//! 4. **Deletion Executor**: Secure deletion with cryptographic audit trails
//! 5. **Duplicate Detector**: Advanced duplicate code detection with refactoring recommendations
//!
//! # Performance Requirements
//!
//! - Static analysis: ≤1 second per 1000 lines of code
//! - Dependency tracing: ≤500ms per dependency graph
//! - Safety verification: ≤2 seconds per deletion operation
//! - Secure deletion: ≤100ms per file with cryptographic verification
//!
//! # Usage Example
//!
//! ```rust,no_run
//! use guru_audit::purge::*;
//! use guru_audit::crypto::CryptoProvider;
//! use std::path::Path;
//!
//! # fn main() -> Result<(), Box<dyn std::error::Error>> {
//! let config = PurgeConfig::default();
//! let crypto = CryptoProvider::new()?;
//!
//! // Analyze workspace
//! let mut analyzer = StaticAnalyzer::new(config.clone());
//! let analysis_result = analyzer.analyze_workspace(Path::new("./src"))?;
//!
//! // Trace dependencies
//! let tracer = DependencyTracer::new(config.clone());
//! let trace_result = tracer.trace_dependencies(&analysis_result)?;
//!
//! // Verify safety
//! let verifier = SafetyVerifier::new(config.clone());
//! let safety_result = verifier.verify_deletion_safety(
//!     &trace_result.unreachable_elements,
//!     &analysis_result,
//!     &trace_result,
//! )?;
//!
//! // Execute deletions
//! let mut executor = DeletionExecutor::new(config.clone(), crypto);
//! let deletion_result = executor.execute_deletions(
//!     &safety_result.safe_to_delete,
//!     &analysis_result,
//!     &safety_result,
//! )?;
//!
//! println!("Deleted {} elements", deletion_result.deleted_elements.len());
//! # Ok(())
//! # }
//! ```

pub mod types;
pub mod static_analyzer;
pub mod dependency_tracer;
pub mod safety_verifier;
pub mod deletion_executor;
pub mod duplicate_detector;

#[cfg(test)]
pub mod property_tests;

// Re-export main types and components
pub use types::*;
pub use static_analyzer::StaticAnalyzer;
pub use dependency_tracer::DependencyTracer;
pub use safety_verifier::SafetyVerifier;
pub use deletion_executor::DeletionExecutor;
pub use duplicate_detector::DuplicateDetector;

use crate::error::AuditError;
use crate::crypto::AuditSigningKey;
use std::path::Path;

/// Comprehensive purge system orchestrator
///
/// Coordinates all purge system components to provide end-to-end
/// dead code elimination with safety guarantees.
pub struct PurgeSystem {
    config: PurgeConfig,
    analyzer: StaticAnalyzer,
    tracer: DependencyTracer,
    verifier: SafetyVerifier,
    executor: DeletionExecutor,
    detector: DuplicateDetector,
}

impl PurgeSystem {
    /// Create a new purge system
    pub fn new(config: PurgeConfig, signing_key: AuditSigningKey) -> Self {
        Self {
            analyzer: StaticAnalyzer::new(config.clone()),
            tracer: DependencyTracer::new(config.clone()),
            verifier: SafetyVerifier::new(config.clone()),
            executor: DeletionExecutor::new(config.clone(), signing_key),
            detector: DuplicateDetector::new(config.clone()),
            config,
        }
    }

    /// Execute complete purge cycle
    ///
    /// Performs all purge operations in sequence:
    /// 1. Static analysis
    /// 2. Dependency tracing
    /// 3. Duplicate detection
    /// 4. Safety verification
    /// 5. Secure deletion
    pub fn execute_purge_cycle(&mut self, workspace_path: &Path) -> Result<PurgeCycleResult, AuditError> {
        // Step 1: Static analysis
        let analysis_result = self.analyzer.analyze_workspace(workspace_path)?;
        
        // Step 2: Dependency tracing
        let trace_result = self.tracer.trace_dependencies(&analysis_result)?;
        
        // Step 3: Duplicate detection
        let duplicate_result = self.detector.detect_duplicates(&analysis_result)?;
        
        // Step 4: Safety verification
        let safety_result = self.verifier.verify_deletion_safety(
            &trace_result.unreachable_elements,
            &analysis_result,
            &trace_result,
        )?;
        
        // Step 5: Secure deletion (if safe)
        let deletion_result = if safety_result.is_safe || !self.config.require_manual_approval {
            Some(self.executor.execute_deletions(
                &safety_result.safe_to_delete,
                &analysis_result,
                &safety_result,
            )?)
        } else {
            None
        };
        
        Ok(PurgeCycleResult {
            analysis_result,
            trace_result,
            duplicate_result,
            safety_result,
            deletion_result,
        })
    }

    /// Get mutable reference to analyzer
    pub fn analyzer_mut(&mut self) -> &mut StaticAnalyzer {
        &mut self.analyzer
    }

    /// Get mutable reference to tracer
    pub fn tracer_mut(&mut self) -> &mut DependencyTracer {
        &mut self.tracer
    }

    /// Get mutable reference to verifier
    pub fn verifier_mut(&mut self) -> &mut SafetyVerifier {
        &mut self.verifier
    }

    /// Get mutable reference to executor
    pub fn executor_mut(&mut self) -> &mut DeletionExecutor {
        &mut self.executor
    }

    /// Get mutable reference to detector
    pub fn detector_mut(&mut self) -> &mut DuplicateDetector {
        &mut self.detector
    }
}

/// Result of complete purge cycle
#[derive(Debug)]
pub struct PurgeCycleResult {
    pub analysis_result: StaticAnalysisResult,
    pub trace_result: DependencyTraceResult,
    pub duplicate_result: DuplicateDetectionResult,
    pub safety_result: SafetyVerificationResult,
    pub deletion_result: Option<DeletionResult>,
}

impl PurgeCycleResult {
    /// Generate summary report
    pub fn generate_summary(&self) -> String {
        let mut summary = String::new();
        
        summary.push_str("=== Purge Cycle Summary ===\n\n");
        
        // Analysis summary
        summary.push_str(&format!(
            "Code Elements Analyzed: {}\n",
            self.analysis_result.code_elements.len()
        ));
        summary.push_str(&format!(
            "Analysis Duration: {}ms\n\n",
            self.analysis_result.analysis_duration_ms
        ));
        
        // Dependency tracing summary
        summary.push_str(&format!(
            "Reachable Elements: {}\n",
            self.trace_result.reachable_elements.len()
        ));
        summary.push_str(&format!(
            "Unreachable Elements (Dead Code): {}\n",
            self.trace_result.unreachable_elements.len()
        ));
        summary.push_str(&format!(
            "Unused Files: {}\n",
            self.trace_result.unused_files.len()
        ));
        summary.push_str(&format!(
            "Unused Imports: {}\n",
            self.trace_result.unused_imports.len()
        ));
        summary.push_str(&format!(
            "Tracing Duration: {}ms\n\n",
            self.trace_result.tracing_duration_ms
        ));
        
        // Duplicate detection summary
        summary.push_str(&format!(
            "Duplicate Code Blocks: {}\n",
            self.duplicate_result.duplicates.len()
        ));
        summary.push_str(&format!(
            "Total Duplicate Lines: {}\n",
            self.duplicate_result.total_duplicate_lines
        ));
        summary.push_str(&format!(
            "Duplicate Percentage: {:.2}%\n",
            self.duplicate_result.duplicate_percentage
        ));
        summary.push_str(&format!(
            "Refactoring Recommendations: {}\n",
            self.duplicate_result.refactoring_recommendations.len()
        ));
        summary.push_str(&format!(
            "Detection Duration: {}ms\n\n",
            self.duplicate_result.detection_duration_ms
        ));
        
        // Safety verification summary
        summary.push_str(&format!(
            "Safe to Delete: {}\n",
            self.safety_result.safe_to_delete.len()
        ));
        summary.push_str(&format!(
            "Unsafe to Delete: {}\n",
            self.safety_result.unsafe_to_delete.len()
        ));
        summary.push_str(&format!(
            "Rollback Verified: {}\n",
            self.safety_result.rollback_verified
        ));
        summary.push_str(&format!(
            "Verification Duration: {}ms\n\n",
            self.safety_result.verification_duration_ms
        ));
        
        // Deletion summary
        if let Some(deletion_result) = &self.deletion_result {
            summary.push_str(&format!(
                "Elements Deleted: {}\n",
                deletion_result.deleted_elements.len()
            ));
            summary.push_str(&format!(
                "Files Deleted: {}\n",
                deletion_result.deleted_files.len()
            ));
            summary.push_str(&format!(
                "Files Modified: {}\n",
                deletion_result.modified_files.len()
            ));
            summary.push_str(&format!(
                "Audit Trail Entries: {}\n",
                deletion_result.audit_trail.len()
            ));
            summary.push_str(&format!(
                "Deletion Duration: {}ms\n",
                deletion_result.deletion_duration_ms
            ));
        } else {
            summary.push_str("Deletion: Skipped (manual approval required)\n");
        }
        
        summary
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_purge_config_default() {
        let config = PurgeConfig::default();
        assert!(config.enable_static_analysis);
        assert!(config.enable_dependency_tracing);
        assert!(config.enable_safety_verification);
        assert!(config.enable_duplicate_detection);
        assert_eq!(config.auto_delete_risk_threshold, RiskLevel::Low);
        assert!(config.require_manual_approval);
        assert!(config.create_backups);
        assert_eq!(config.max_batch_size, 100);
    }
}
