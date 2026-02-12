//! # Installation Metrics and Performance Tracking
//! 
//! **MAXIMUM ENGINEERING MANDATE (ZERO COMPROMISE):**
//! Complete performance metrics with comprehensive tracking - never simplified monitoring.
//! Full timing analysis, resource monitoring, statistical validation - no deferred metrics.
//! Production standards: Must provide detailed performance insights for optimization and debugging.

use std::time::{Duration, Instant, SystemTime};
use std::collections::HashMap;

/// Comprehensive installation metrics for performance monitoring
#[derive(Debug, Clone)]
pub struct InstallationMetrics {
    /// Total installation time from start to completion
    pub total_installation_time: Duration,
    /// Time spent on signature verification
    pub signature_verification_time: Duration,
    /// Time spent on dependency resolution
    pub dependency_resolution_time: Duration,
    /// Time spent on backup creation
    pub backup_time: Duration,
    /// Time spent on package extraction
    pub extraction_time: Duration,
    /// Time spent on platform integration
    pub platform_integration_time: Duration,
    /// Time spent on integrity verification
    pub integrity_verification_time: Duration,
    /// Time spent on rollback operations
    pub rollback_time: Duration,
    
    /// Number of signatures verified
    pub verified_signatures_count: usize,
    /// Number of dependencies resolved
    pub resolved_dependencies_count: usize,
    /// Number of components installed
    pub installed_components_count: usize,
    /// Total bytes processed during installation
    pub bytes_processed: u64,
    /// Size of backup created
    pub backup_size_bytes: u64,
    /// Current memory usage
    pub memory_usage_bytes: usize,
    /// Disk space used by installation
    pub disk_space_used_bytes: u64,
    /// Backup space used
    pub backup_space_used_bytes: u64,
    
    /// Integrity check success rate (0.0 to 1.0)
    pub integrity_success_rate: f32,
    /// Rollback success rate (0.0 to 1.0)
    pub rollback_success_rate: f32,
    
    /// Performance counters for detailed analysis
    pub performance_counters: HashMap<String, u64>,
    /// Error counters by category
    pub error_counters: HashMap<String, u64>,
    /// Timing measurements for individual operations
    pub operation_timings: HashMap<String, Vec<Duration>>,
    
    /// Metrics collection start time
    pub start_time: Instant,
    /// Last update timestamp
    pub last_updated: SystemTime,
}

impl InstallationMetrics {
    /// Create a new metrics instance
    pub fn new() -> Self {
        Self {
            total_installation_time: Duration::ZERO,
            signature_verification_time: Duration::ZERO,
            dependency_resolution_time: Duration::ZERO,
            backup_time: Duration::ZERO,
            extraction_time: Duration::ZERO,
            platform_integration_time: Duration::ZERO,
            integrity_verification_time: Duration::ZERO,
            rollback_time: Duration::ZERO,
            
            verified_signatures_count: 0,
            resolved_dependencies_count: 0,
            installed_components_count: 0,
            bytes_processed: 0,
            backup_size_bytes: 0,
            memory_usage_bytes: 0,
            disk_space_used_bytes: 0,
            backup_space_used_bytes: 0,
            
            integrity_success_rate: 1.0,
            rollback_success_rate: 1.0,
            
            performance_counters: HashMap::new(),
            error_counters: HashMap::new(),
            operation_timings: HashMap::new(),
            
            start_time: Instant::now(),
            last_updated: SystemTime::now(),
        }
    }
    
    /// Record total installation time
    pub fn record_total_installation_time(&mut self, duration: Duration) {
        self.total_installation_time = duration;
        self.last_updated = SystemTime::now();
    }
    
    /// Record operation timing for detailed analysis
    fn record_operation_timing(&mut self, operation: &str, duration: Duration) {
        self.operation_timings
            .entry(operation.to_string())
            .or_insert_with(Vec::new)
            .push(duration);
    }
    
    /// Record signature verification time
    pub fn record_signature_verification_time(&mut self, duration: Duration) {
        self.signature_verification_time = duration;
        self.record_operation_timing("signature_verification", duration);
        self.last_updated = SystemTime::now();
    }
    
    /// Record dependency resolution time
    pub fn record_dependency_resolution_time(&mut self, duration: Duration) {
        self.dependency_resolution_time = duration;
        self.record_operation_timing("dependency_resolution", duration);
        self.last_updated = SystemTime::now();
    }
    
    /// Record backup creation time
    pub fn record_backup_time(&mut self, duration: Duration) {
        self.backup_time = duration;
        self.record_operation_timing("backup_creation", duration);
        self.last_updated = SystemTime::now();
    }
    
    /// Record package extraction time
    pub fn record_extraction_time(&mut self, duration: Duration) {
        self.extraction_time = duration;
        self.record_operation_timing("package_extraction", duration);
        self.last_updated = SystemTime::now();
    }
    
    /// Record platform integration time
    pub fn record_platform_integration_time(&mut self, duration: Duration) {
        self.platform_integration_time = duration;
        self.record_operation_timing("platform_integration", duration);
        self.last_updated = SystemTime::now();
    }
    
    /// Record integrity verification time
    pub fn record_integrity_verification_time(&mut self, duration: Duration) {
        self.integrity_verification_time = duration;
        self.record_operation_timing("integrity_verification", duration);
        self.last_updated = SystemTime::now();
    }
    
    /// Record rollback time
    pub fn record_rollback_time(&mut self, duration: Duration) {
        self.rollback_time = duration;
        self.record_operation_timing("rollback", duration);
        self.last_updated = SystemTime::now();
    }
    
    /// Record number of verified signatures
    pub fn record_verified_signatures(&mut self, count: usize) {
        self.verified_signatures_count = count;
        self.increment_performance_counter("signatures_verified", count as u64);
        self.last_updated = SystemTime::now();
    }
    
    /// Record number of resolved dependencies
    pub fn record_resolved_dependencies(&mut self, count: usize) {
        self.resolved_dependencies_count = count;
        self.increment_performance_counter("dependencies_resolved", count as u64);
        self.last_updated = SystemTime::now();
    }
    
    /// Record number of installed components
    pub fn record_installed_components(&mut self, count: usize) {
        self.installed_components_count = count;
        self.increment_performance_counter("components_installed", count as u64);
        self.last_updated = SystemTime::now();
    }
    
    /// Record bytes processed
    pub fn record_bytes_processed(&mut self, bytes: u64) {
        self.bytes_processed = bytes;
        self.increment_performance_counter("bytes_processed", bytes);
        self.last_updated = SystemTime::now();
    }
    
    /// Record backup size
    pub fn record_backup_size(&mut self, bytes: u64) {
        self.backup_size_bytes = bytes;
        self.increment_performance_counter("backup_size", bytes);
        self.last_updated = SystemTime::now();
    }
    
    /// Record current memory usage
    pub fn record_memory_usage(&mut self, bytes: usize) {
        self.memory_usage_bytes = bytes;
        self.last_updated = SystemTime::now();
    }
    
    /// Record integrity check success rate
    pub fn record_integrity_success_rate(&mut self, rate: f32) {
        self.integrity_success_rate = rate;
        self.last_updated = SystemTime::now();
    }
    
    /// Record rollback success rate
    pub fn record_rollback_success_rate(&mut self, rate: f32) {
        self.rollback_success_rate = rate;
        self.last_updated = SystemTime::now();
    }
    
    /// Increment a performance counter
    pub fn increment_performance_counter(&mut self, name: &str, value: u64) {
        *self.performance_counters.entry(name.to_string()).or_insert(0) += value;
        self.last_updated = SystemTime::now();
    }
    
    /// Increment an error counter
    pub fn increment_error_counter(&mut self, category: &str) {
        *self.error_counters.entry(category.to_string()).or_insert(0) += 1;
        self.last_updated = SystemTime::now();
    }
    
    /// Record operation timing for statistical analysis
    #[allow(dead_code)]
    fn recordoperation_timing(&mut self, operation: &str, duration: Duration) {
        self.operation_timings
            .entry(operation.to_string())
            .or_insert_with(Vec::new)
            .push(duration);
    }
    
    /// Get average time for an operation
    pub fn get_averageoperation_time(&self, operation: &str) -> Option<Duration> {
        if let Some(timings) = self.operation_timings.get(operation) {
            if !timings.is_empty() {
                let total: Duration = timings.iter().sum();
                Some(total / timings.len() as u32)
            } else {
                None
            }
        } else {
            None
        }
    }
    
    /// Get percentile time for an operation
    pub fn getoperation_time_percentile(&self, operation: &str, percentile: f32) -> Option<Duration> {
        if let Some(timings) = self.operation_timings.get(operation) {
            if timings.is_empty() {
                return None;
            }
            
            let mut sorted_timings = timings.clone();
            sorted_timings.sort();
            
            let index = ((percentile / 100.0) * (sorted_timings.len() - 1) as f32) as usize;
            Some(sorted_timings[index])
        } else {
            None
        }
    }
    
    /// Calculate installation throughput (bytes per second)
    pub fn calculate_throughput(&self) -> f64 {
        if self.total_installation_time.as_secs_f64() > 0.0 {
            self.bytes_processed as f64 / self.total_installation_time.as_secs_f64()
        } else {
            0.0
        }
    }
    
    /// Calculate signature verification rate (signatures per second)
    pub fn calculate_signature_verification_rate(&self) -> f64 {
        if self.signature_verification_time.as_secs_f64() > 0.0 {
            self.verified_signatures_count as f64 / self.signature_verification_time.as_secs_f64()
        } else {
            0.0
        }
    }
    
    /// Get performance summary
    pub fn get_performance_summary(&self) -> PerformanceSummary {
        PerformanceSummary {
            total_time: self.total_installation_time,
            throughput_bytes_per_sec: self.calculate_throughput(),
            signature_rate_per_sec: self.calculate_signature_verification_rate(),
            components_processed: self.installed_components_count,
            dependencies_resolved: self.resolved_dependencies_count,
            signatures_verified: self.verified_signatures_count,
            integrity_success_rate: self.integrity_success_rate,
            rollback_success_rate: self.rollback_success_rate,
            memory_peak_bytes: self.memory_usage_bytes,
            backup_size_bytes: self.backup_size_bytes,
        }
    }
    
    /// Reset all metrics
    pub fn reset(&mut self) {
        *self = Self::new();
    }
    
    /// Merge metrics from another instance
    pub fn merge(&mut self, other: &InstallationMetrics) {
        self.total_installation_time = self.total_installation_time.max(other.total_installation_time);
        self.signature_verification_time += other.signature_verification_time;
        self.dependency_resolution_time += other.dependency_resolution_time;
        self.backup_time += other.backup_time;
        self.extraction_time += other.extraction_time;
        self.platform_integration_time += other.platform_integration_time;
        self.integrity_verification_time += other.integrity_verification_time;
        self.rollback_time += other.rollback_time;
        
        self.verified_signatures_count += other.verified_signatures_count;
        self.resolved_dependencies_count += other.resolved_dependencies_count;
        self.installed_components_count += other.installed_components_count;
        self.bytes_processed += other.bytes_processed;
        self.backup_size_bytes += other.backup_size_bytes;
        self.memory_usage_bytes = self.memory_usage_bytes.max(other.memory_usage_bytes);
        
        self.integrity_success_rate = self.integrity_success_rate.min(other.integrity_success_rate);
        self.rollback_success_rate = self.rollback_success_rate.min(other.rollback_success_rate);
        
        // Merge performance counters
        for (key, value) in &other.performance_counters {
            *self.performance_counters.entry(key.clone()).or_insert(0) += value;
        }
        
        // Merge error counters
        for (key, value) in &other.error_counters {
            *self.error_counters.entry(key.clone()).or_insert(0) += value;
        }
        
        // Merge operation timings
        for (operation, timings) in &other.operation_timings {
            self.operation_timings
                .entry(operation.clone())
                .or_insert_with(Vec::new)
                .extend(timings.iter().cloned());
        }
        
        self.last_updated = SystemTime::now();
    }
}

/// Performance summary for reporting
#[derive(Debug, Clone)]
pub struct PerformanceSummary {
    pub total_time: Duration,
    pub throughput_bytes_per_sec: f64,
    pub signature_rate_per_sec: f64,
    pub components_processed: usize,
    pub dependencies_resolved: usize,
    pub signatures_verified: usize,
    pub integrity_success_rate: f32,
    pub rollback_success_rate: f32,
    pub memory_peak_bytes: usize,
    pub backup_size_bytes: u64,
}

impl Default for InstallationMetrics {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Display for PerformanceSummary {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "Installation Performance Summary:")?;
        writeln!(f, "  Total Time: {:?}", self.total_time)?;
        writeln!(f, "  Throughput: {:.2} bytes/sec", self.throughput_bytes_per_sec)?;
        writeln!(f, "  Signature Rate: {:.2} signatures/sec", self.signature_rate_per_sec)?;
        writeln!(f, "  Components Processed: {}", self.components_processed)?;
        writeln!(f, "  Dependencies Resolved: {}", self.dependencies_resolved)?;
        writeln!(f, "  Signatures Verified: {}", self.signatures_verified)?;
        writeln!(f, "  Integrity Success Rate: {:.1}%", self.integrity_success_rate * 100.0)?;
        writeln!(f, "  Rollback Success Rate: {:.1}%", self.rollback_success_rate * 100.0)?;
        writeln!(f, "  Peak Memory Usage: {} bytes", self.memory_peak_bytes)?;
        writeln!(f, "  Backup Size: {} bytes", self.backup_size_bytes)?;
        Ok(())
    }
}
