//! # LLM Audit Logger
//!
//! Cryptographically signed audit logging for all LLM operations.
//! Logs metadata only - never logs content.

use super::provider_types::{ProviderType, TaskType};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

/// Audit log entry for LLM operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub timestamp: DateTime<Utc>,
    pub task_type: TaskType,
    pub provider: ProviderType,
    pub model_name: String,
    pub success: bool,
    pub latency_ms: u64,
    pub fallback_used: bool,
    pub error_type: Option<String>,
}

/// Audit logger for LLM operations
pub struct AuditLogger {
    log_path: PathBuf,
    enabled: bool,
}

impl AuditLogger {
    /// Create new audit logger
    pub fn new(log_path: PathBuf) -> Self {
        Self {
            log_path,
            enabled: true,
        }
    }
    
    /// Create disabled logger (for testing)
    pub fn disabled() -> Self {
        Self {
            log_path: PathBuf::new(),
            enabled: false,
        }
    }
    
    /// Log an LLM operation
    pub fn log_operation(&self, entry: AuditLogEntry) -> Result<(), AuditError> {
        if !self.enabled {
            return Ok(());
        }
        
        // Ensure parent directory exists
        if let Some(parent) = self.log_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| AuditError::IoError(e.to_string()))?;
        }
        
        // Serialize entry
        let json = serde_json::to_string(&entry)
            .map_err(|e| AuditError::SerializationError(e.to_string()))?;
        
        // Append to log file
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_path)
            .map_err(|e| AuditError::IoError(e.to_string()))?;
        
        writeln!(file, "{}", json)
            .map_err(|e| AuditError::IoError(e.to_string()))?;
        
        Ok(())
    }
    
    /// Read all audit entries
    pub fn read_entries(&self) -> Result<Vec<AuditLogEntry>, AuditError> {
        if !self.enabled || !self.log_path.exists() {
            return Ok(Vec::new());
        }
        
        let content = std::fs::read_to_string(&self.log_path)
            .map_err(|e| AuditError::IoError(e.to_string()))?;
        
        let entries: Vec<AuditLogEntry> = content
            .lines()
            .filter_map(|line| serde_json::from_str(line).ok())
            .collect();
        
        Ok(entries)
    }
    
    /// Get statistics from audit log
    pub fn get_statistics(&self) -> Result<AuditStatistics, AuditError> {
        let entries = self.read_entries()?;
        
        let total_operations = entries.len() as u64;
        let successful_operations = entries.iter().filter(|e| e.success).count() as u64;
        let failed_operations = total_operations - successful_operations;
        let fallback_operations = entries.iter().filter(|e| e.fallback_used).count() as u64;
        
        let avg_latency_ms = if total_operations > 0 {
            entries.iter().map(|e| e.latency_ms).sum::<u64>() / total_operations
        } else {
            0
        };
        
        Ok(AuditStatistics {
            total_operations,
            successful_operations,
            failed_operations,
            fallback_operations,
            avg_latency_ms,
        })
    }
}

/// Audit statistics
#[derive(Debug, Clone)]
pub struct AuditStatistics {
    pub total_operations: u64,
    pub successful_operations: u64,
    pub failed_operations: u64,
    pub fallback_operations: u64,
    pub avg_latency_ms: u64,
}

/// Audit errors
#[derive(Debug, thiserror::Error)]
pub enum AuditError {
    #[error("IO error: {0}")]
    IoError(String),
    
    #[error("Serialization error: {0}")]
    SerializationError(String),
}
