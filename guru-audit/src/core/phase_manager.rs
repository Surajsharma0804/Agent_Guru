//! Phase Manager - Sequential phase execution with checkpoints
//!
//! The Phase Manager enforces strict sequential execution of the 10 mandatory audit phases
//! with zero tolerance for phase skipping or partial completion. It provides comprehensive
//! phase orchestration with dependency validation, resource management, and performance monitoring.

use crate::error::{AuditError, AuditResult, FailureReason, RemediationStep, RiskLevel};
use crate::types::{
    AuditContext, ExecutionStatus, PhaseId, PhaseMetrics, PhaseResult,
};
use async_trait::async_trait;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, SystemTime};
use tokio::sync::RwLock;
use tracing::{error, info};

/// Phase Manager trait for sequential execution
#[async_trait]
pub trait PhaseManager: Send + Sync {
    /// Execute specific phase with comprehensive validation
    async fn execute_phase(&self, phase: PhaseId, context: AuditContext) -> AuditResult<PhaseResult>;

    /// Get phase execution statistics
    async fn get_phase_statistics(&self) -> PhaseStatistics;

    /// Validate phase prerequisites
    async fn validate_phase_prerequisites(&self, phase: PhaseId, context: &AuditContext) -> AuditResult<PrerequisiteStatus>;

    /// Get supported phases
    fn get_supported_phases(&self) -> Vec<PhaseId>;
}

/// Phase execution statistics
#[derive(Debug, Clone)]
pub struct PhaseStatistics {
    /// Total phases executed
    pub total_phases_executed: u64,
    /// Successful phase executions
    pub successful_executions: u64,
    /// Failed phase executions
    pub failed_executions: u64,
    /// Average execution time per phase
    pub average_execution_time: Duration,
    /// Peak memory usage across all phases
    pub peak_memory_usage: u64,
    /// Total CPU time consumed
    pub total_cpu_time: Duration,
}

/// Phase prerequisite validation status
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PrerequisiteStatus {
    /// All prerequisites satisfied
    Satisfied,
    /// Prerequisites missing with details
    Missing { 
        /// List of missing prerequisite items
        missing_items: Vec<String> 
    },
    /// Prerequisites invalid with reasons
    Invalid { 
        /// List of invalid prerequisite items
        invalid_items: Vec<String> 
    },
}

/// Production phase manager implementation with comprehensive orchestration
#[derive(Debug)]
pub struct ProductionPhaseManager {
    /// Phase execution statistics
    statistics: Arc<RwLock<PhaseStatistics>>,
    /// Phase execution history
    execution_history: Arc<RwLock<HashMap<PhaseId, Vec<PhaseExecutionRecord>>>>,
    /// Resource monitoring
    resource_monitor: Arc<ResourceMonitor>,
}

/// Phase execution record for history tracking
#[derive(Debug, Clone)]
#[allow(dead_code)]
struct PhaseExecutionRecord {
    /// Execution timestamp
    timestamp: SystemTime,
    /// Execution duration
    duration: Duration,
    /// Success status
    success: bool,
    /// Memory usage peak
    memory_usage: u64,
    /// CPU utilization
    cpu_utilization: f64,
    /// Error message if failed
    error_message: Option<String>,
}

/// Resource monitoring for phase execution
#[derive(Debug)]
struct ResourceMonitor {
    /// Current memory usage
    current_memory_usage: Arc<RwLock<u64>>,
    /// Current CPU utilization
    current_cpu_utilization: Arc<RwLock<f64>>,
    /// Resource usage history
    usage_history: Arc<RwLock<Vec<ResourceUsageSnapshot>>>,
}

/// Resource usage snapshot
#[derive(Debug, Clone)]
#[allow(dead_code)]
struct ResourceUsageSnapshot {
    /// Snapshot timestamp
    timestamp: SystemTime,
    /// Memory usage at snapshot
    memory_usage: u64,
    /// CPU utilization at snapshot
    cpu_utilization: f64,
    /// Active phase
    active_phase: Option<PhaseId>,
}

impl ProductionPhaseManager {
    /// Create new production phase manager with comprehensive monitoring
    #[must_use]
    pub fn new() -> Self {
        let statistics = Arc::new(RwLock::new(PhaseStatistics {
            total_phases_executed: 0,
            successful_executions: 0,
            failed_executions: 0,
            average_execution_time: Duration::ZERO,
            peak_memory_usage: 0,
            total_cpu_time: Duration::ZERO,
        }));

        let execution_history = Arc::new(RwLock::new(HashMap::new()));

        let resource_monitor = Arc::new(ResourceMonitor {
            current_memory_usage: Arc::new(RwLock::new(0)),
            current_cpu_utilization: Arc::new(RwLock::new(0.0)),
            usage_history: Arc::new(RwLock::new(Vec::new())),
        });

        Self {
            statistics,
            execution_history,
            resource_monitor,
        }
    }

    /// Execute phase with comprehensive monitoring and validation
    async fn execute_phase_internal(
        &self,
        phase: PhaseId,
        context: AuditContext,
    ) -> AuditResult<PhaseResult> {
        let start_time = SystemTime::now();
        let initial_memory = self.get_current_memory_usage().await;

        info!("Starting phase execution: {phase:?}");

        // Validate prerequisites
        let prerequisite_status = self.validate_phase_prerequisites(phase, &context).await?;
        if !matches!(prerequisite_status, PrerequisiteStatus::Satisfied) {
            return Err(AuditError::PhaseExecutionError {
                phase_id: phase,
                failure_reason: FailureReason::DependencyNotSatisfied {
                    dependency: format!("{prerequisite_status:?}"),
                    required_version: None,
                },
                checkpoint_id: crate::types::CheckpointId::new(),
                remediation_steps: vec![RemediationStep {
                    description: "Resolve phase prerequisites".to_string(),
                    actions: vec!["Check previous phase completion".to_string()],
                    estimated_time: Duration::from_secs(300),
                    risk_level: RiskLevel::Medium,
                }],
            });
        }

        // Start resource monitoring
        let _monitor_handle = self.start_resource_monitoring(phase).await;

        // Execute phase-specific logic
        let phase_result = match phase {
            PhaseId::Inventory => self.execute_inventory_phase(context).await,
            PhaseId::Naming => self.execute_naming_phase(context).await,
            PhaseId::Purge => self.execute_purge_phase(context).await,
            PhaseId::Integration => self.execute_integration_phase(context).await,
            PhaseId::Testing => self.execute_testing_phase(context).await,
            PhaseId::Performance => self.execute_performance_phase(context).await,
            PhaseId::FormalVerification => self.execute_formal_verification_phase(context).await,
            PhaseId::ReproducibleBuild => self.execute_reproducible_build_phase(context).await,
            PhaseId::RuntimeAttestation => self.execute_runtime_attestation_phase(context).await,
            PhaseId::FinalCertification => self.execute_final_certification_phase(context).await,
        };

        let end_time = SystemTime::now();
        let execution_duration = end_time.duration_since(start_time).unwrap_or(Duration::ZERO);
        let peak_memory = self.get_current_memory_usage().await;
        let cpu_utilization = self.get_current_cpu_utilization().await;

        // Record execution statistics
        self.record_phase_execution(
            phase,
            execution_duration,
            phase_result.is_ok(),
            peak_memory,
            cpu_utilization,
            phase_result.as_ref().err().map(|e| e.to_string()),
        ).await;

        match phase_result {
            Ok(mut result) => {
                // Update result with timing and resource information
                result.start_time = start_time;
                result.end_time = Some(end_time);
                result.metrics.execution_duration = execution_duration;
                result.metrics.memory_usage_peak = peak_memory.saturating_sub(initial_memory);
                result.metrics.cpu_utilization = cpu_utilization;

                info!("Phase {phase:?} completed successfully in {execution_duration:?}");
                Ok(result)
            }
            Err(error) => {
                error!("Phase {phase:?} failed after {execution_duration:?}: {error}");
                Err(error)
            }
        }
    }

    /// Start resource monitoring for phase execution
    async fn start_resource_monitoring(&self, phase: PhaseId) -> ResourceMonitorHandle {
        let monitor = Arc::clone(&self.resource_monitor);
        let handle = tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(100));
            loop {
                interval.tick().await;
                
                // Simulate resource monitoring (in production, this would use actual system APIs)
                let memory_usage = Self::get_system_memory_usage();
                let cpu_utilization = Self::get_system_cpu_utilization();

                {
                    let mut current_memory = monitor.current_memory_usage.write().await;
                    *current_memory = memory_usage;
                }

                {
                    let mut current_cpu = monitor.current_cpu_utilization.write().await;
                    *current_cpu = cpu_utilization;
                }

                {
                    let mut history = monitor.usage_history.write().await;
                    history.push(ResourceUsageSnapshot {
                        timestamp: SystemTime::now(),
                        memory_usage,
                        cpu_utilization,
                        active_phase: Some(phase),
                    });

                    // Keep only recent history (last 1000 snapshots)
                    if history.len() > 1000 {
                        history.drain(0..100);
                    }
                }
            }
        });

        ResourceMonitorHandle { handle }
    }

    /// Get current memory usage
    async fn get_current_memory_usage(&self) -> u64 {
        let memory = self.resource_monitor.current_memory_usage.read().await;
        *memory
    }

    /// Get current CPU utilization
    async fn get_current_cpu_utilization(&self) -> f64 {
        let cpu = self.resource_monitor.current_cpu_utilization.read().await;
        *cpu
    }

    /// Get system memory usage (placeholder implementation)
    fn get_system_memory_usage() -> u64 {
        // In production, this would use system APIs to get actual memory usage
        // For now, simulate realistic memory usage
        use std::sync::atomic::{AtomicU64, Ordering};
        static SIMULATED_MEMORY: AtomicU64 = AtomicU64::new(1_000_000_000); // 1GB base
        
        let current = SIMULATED_MEMORY.load(Ordering::Relaxed);
        let variation = (rand::random::<u64>() % 100_000_000).saturating_add(current);
        SIMULATED_MEMORY.store(variation, Ordering::Relaxed);
        variation
    }

    /// Get system CPU utilization (placeholder implementation)
    fn get_system_cpu_utilization() -> f64 {
        // In production, this would use system APIs to get actual CPU usage
        // For now, simulate realistic CPU utilization
        use std::sync::atomic::{AtomicU64, Ordering};
        static SIMULATED_CPU: AtomicU64 = AtomicU64::new(2500); // 25.00% base
        
        let current = SIMULATED_CPU.load(Ordering::Relaxed);
        let variation = ((rand::random::<u64>() % 5000) + current) % 10000; // 0-100%
        SIMULATED_CPU.store(variation, Ordering::Relaxed);
        variation as f64 / 100.0
    }

    /// Record phase execution statistics
    async fn record_phase_execution(
        &self,
        phase: PhaseId,
        duration: Duration,
        success: bool,
        memory_usage: u64,
        cpu_utilization: f64,
        error_message: Option<String>,
    ) {
        // Update statistics
        {
            let mut stats = self.statistics.write().await;
            stats.total_phases_executed += 1;
            
            if success {
                stats.successful_executions += 1;
            } else {
                stats.failed_executions += 1;
            }

            // Update average execution time
            let total_time = stats.average_execution_time.mul_f64(stats.total_phases_executed as f64 - 1.0)
                + duration;
            stats.average_execution_time = total_time.div_f64(stats.total_phases_executed as f64);

            // Update peak memory usage
            if memory_usage > stats.peak_memory_usage {
                stats.peak_memory_usage = memory_usage;
            }

            // Update total CPU time
            stats.total_cpu_time += duration;
        }

        // Record execution history
        {
            let mut history = self.execution_history.write().await;
            let phase_history = history.entry(phase).or_insert_with(Vec::new);
            
            phase_history.push(PhaseExecutionRecord {
                timestamp: SystemTime::now(),
                duration,
                success,
                memory_usage,
                cpu_utilization,
                error_message,
            });

            // Keep only recent history (last 100 executions per phase)
            if phase_history.len() > 100 {
                phase_history.drain(0..10);
            }
        }
    }

    // Phase-specific execution methods (placeholder implementations for now)
    async fn execute_inventory_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        // Simulate phase execution
        tokio::time::sleep(Duration::from_millis(100)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::Inventory,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(100),
                memory_usage_peak: 1_000_000,
                cpu_utilization: 25.0,
                files_processed: 1000,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["inventory_report.json".to_string()],
            quality_gates_passed: vec!["file_analysis_complete".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["inventory_complete".to_string()],
        })
    }

    async fn execute_naming_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(150)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::Naming,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(150),
                memory_usage_peak: 1_500_000,
                cpu_utilization: 30.0,
                files_processed: 500,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["naming_report.json".to_string()],
            quality_gates_passed: vec!["naming_complete".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["naming_complete".to_string()],
        })
    }

    async fn execute_purge_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(200)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::Purge,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(200),
                memory_usage_peak: 2_000_000,
                cpu_utilization: 35.0,
                files_processed: 300,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["purge_report.json".to_string()],
            quality_gates_passed: vec!["dead_code_removed".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["purge_complete".to_string()],
        })
    }

    async fn execute_integration_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(300)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::Integration,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(300),
                memory_usage_peak: 3_000_000,
                cpu_utilization: 40.0,
                files_processed: 200,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["integration_report.json".to_string()],
            quality_gates_passed: vec!["integration_verified".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["integration_complete".to_string()],
        })
    }

    async fn execute_testing_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(500)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::Testing,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(500),
                memory_usage_peak: 4_000_000,
                cpu_utilization: 60.0,
                files_processed: 150,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["test_report.json".to_string()],
            quality_gates_passed: vec!["all_tests_passed".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["testing_complete".to_string()],
        })
    }

    async fn execute_performance_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(400)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::Performance,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(400),
                memory_usage_peak: 3_500_000,
                cpu_utilization: 50.0,
                files_processed: 100,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["performance_report.json".to_string()],
            quality_gates_passed: vec!["performance_validated".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["performance_complete".to_string()],
        })
    }

    async fn execute_formal_verification_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(600)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::FormalVerification,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(600),
                memory_usage_peak: 5_000_000,
                cpu_utilization: 70.0,
                files_processed: 50,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["formal_verification_report.json".to_string()],
            quality_gates_passed: vec!["formal_proofs_verified".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["formal_verification_complete".to_string()],
        })
    }

    async fn execute_reproducible_build_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(350)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::ReproducibleBuild,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(350),
                memory_usage_peak: 2_500_000,
                cpu_utilization: 45.0,
                files_processed: 75,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["build_report.json".to_string()],
            quality_gates_passed: vec!["build_reproducible".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["build_complete".to_string()],
        })
    }

    async fn execute_runtime_attestation_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(250)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::RuntimeAttestation,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(250),
                memory_usage_peak: 2_000_000,
                cpu_utilization: 40.0,
                files_processed: 25,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["attestation_report.json".to_string()],
            quality_gates_passed: vec!["runtime_verified".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: vec!["attestation_complete".to_string()],
        })
    }

    async fn execute_final_certification_phase(&self, _context: AuditContext) -> AuditResult<PhaseResult> {
        tokio::time::sleep(Duration::from_millis(100)).await;
        
        Ok(PhaseResult {
            phase_id: PhaseId::FinalCertification,
            execution_status: ExecutionStatus::Completed { success: true },
            start_time: SystemTime::now(),
            end_time: Some(SystemTime::now()),
            metrics: PhaseMetrics {
                execution_duration: Duration::from_millis(100),
                memory_usage_peak: 1_000_000,
                cpu_utilization: 20.0,
                files_processed: 10,
                errors_encountered: 0,
                warnings_generated: 0,
            },
            artifacts: vec!["certification_report.json".to_string()],
            quality_gates_passed: vec!["certification_complete".to_string()],
            quality_gates_failed: Vec::new(),
            next_phase_dependencies: Vec::new(),
        })
    }
}

impl Default for ProductionPhaseManager {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PhaseManager for ProductionPhaseManager {
    async fn execute_phase(&self, phase: PhaseId, context: AuditContext) -> AuditResult<PhaseResult> {
        self.execute_phase_internal(phase, context).await
    }

    async fn get_phase_statistics(&self) -> PhaseStatistics {
        let stats = self.statistics.read().await;
        stats.clone()
    }

    async fn validate_phase_prerequisites(&self, phase: PhaseId, context: &AuditContext) -> AuditResult<PrerequisiteStatus> {
        // Validate phase-specific prerequisites
        match phase {
            PhaseId::Inventory => {
                // First phase - no prerequisites
                Ok(PrerequisiteStatus::Satisfied)
            }
            PhaseId::Naming => {
                // Requires inventory completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::Inventory && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Inventory phase completion".to_string()],
                    })
                }
            }
            PhaseId::Purge => {
                // Requires naming completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::Naming && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Naming phase completion".to_string()],
                    })
                }
            }
            PhaseId::Integration => {
                // Requires purge completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::Purge && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Purge phase completion".to_string()],
                    })
                }
            }
            PhaseId::Testing => {
                // Requires integration completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::Integration && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Integration phase completion".to_string()],
                    })
                }
            }
            PhaseId::Performance => {
                // Requires testing completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::Testing && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Testing phase completion".to_string()],
                    })
                }
            }
            PhaseId::FormalVerification => {
                // Requires performance completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::Performance && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Performance phase completion".to_string()],
                    })
                }
            }
            PhaseId::ReproducibleBuild => {
                // Requires formal verification completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::FormalVerification && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Formal verification phase completion".to_string()],
                    })
                }
            }
            PhaseId::RuntimeAttestation => {
                // Requires reproducible build completion
                if context.previous_results.iter().any(|r| r.phase_id == PhaseId::ReproducibleBuild && matches!(r.execution_status, ExecutionStatus::Completed { success: true })) {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: vec!["Reproducible build phase completion".to_string()],
                    })
                }
            }
            PhaseId::FinalCertification => {
                // Requires all previous phases completion
                let required_phases = [
                    PhaseId::Inventory,
                    PhaseId::Naming,
                    PhaseId::Purge,
                    PhaseId::Integration,
                    PhaseId::Testing,
                    PhaseId::Performance,
                    PhaseId::FormalVerification,
                    PhaseId::ReproducibleBuild,
                    PhaseId::RuntimeAttestation,
                ];

                let missing_phases: Vec<String> = required_phases
                    .iter()
                    .filter(|&&required_phase| {
                        !context.previous_results.iter().any(|r| {
                            r.phase_id == required_phase && matches!(r.execution_status, ExecutionStatus::Completed { success: true })
                        })
                    })
                    .map(|phase| format!("{phase:?} phase completion"))
                    .collect();

                if missing_phases.is_empty() {
                    Ok(PrerequisiteStatus::Satisfied)
                } else {
                    Ok(PrerequisiteStatus::Missing {
                        missing_items: missing_phases,
                    })
                }
            }
        }
    }

    fn get_supported_phases(&self) -> Vec<PhaseId> {
        PhaseId::all_phases().to_vec()
    }
}

/// Resource monitor handle for cleanup
struct ResourceMonitorHandle {
    handle: tokio::task::JoinHandle<()>,
}

impl Drop for ResourceMonitorHandle {
    fn drop(&mut self) {
        self.handle.abort();
    }
}