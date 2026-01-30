//! Configuration management for AGENT_GURU system
//!
//! This module provides secure configuration loading and validation with
//! support for environment variables, configuration files, and runtime
//! parameter validation.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use crate::common::error::{SystemError, SystemResult};

/// Main system configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemConfig {
    /// Cryptographic configuration
    pub crypto: CryptoConfig,
    
    /// Performance configuration
    pub performance: PerformanceConfig,
    
    /// Security configuration
    pub security: SecurityConfig,
    
    /// Logging configuration
    pub logging: LoggingConfig,
}

/// Cryptographic system configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CryptoConfig {
    /// Enable Ed25519 signatures
    pub enable_ed25519: bool,
    
    /// Key rotation interval in seconds
    pub key_rotation_interval: u64,
    
    /// Maximum audit log entries before rotation
    pub max_audit_entries: usize,
}

/// Performance configuration parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceConfig {
    /// Maximum memory usage in bytes
    pub max_memory_bytes: u64,
    
    /// Wake word detection timeout in milliseconds
    pub wake_word_timeout_ms: u32,
    
    /// Speech recognition timeout in milliseconds
    pub speech_recognition_timeout_ms: u32,
    
    /// LLM response timeout in milliseconds
    pub llm_response_timeout_ms: u32,
    
    /// Avatar rendering target FPS
    pub avatar_target_fps: u32,
}

/// Security configuration parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    /// Enable biometric authentication
    pub enable_biometric_auth: bool,
    
    /// Maximum authentication attempts
    pub max_auth_attempts: u32,
    
    /// Authentication lockout duration in seconds
    pub auth_lockout_duration: u64,
    
    /// Enable audit logging
    pub enable_audit_logging: bool,
}

/// Logging configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggingConfig {
    /// Log level (error, warn, info, debug, trace)
    pub level: String,
    
    /// Enable structured logging
    pub structured: bool,
    
    /// Log file path (optional)
    pub file_path: Option<PathBuf>,
    
    /// Maximum log file size in bytes
    pub max_file_size: u64,
    
    /// Number of log files to retain
    pub max_files: u32,
}

impl Default for SystemConfig {
    fn default() -> Self {
        Self {
            crypto: CryptoConfig::default(),
            performance: PerformanceConfig::default(),
            security: SecurityConfig::default(),
            logging: LoggingConfig::default(),
        }
    }
}

impl Default for CryptoConfig {
    fn default() -> Self {
        Self {
            enable_ed25519: true,
            key_rotation_interval: 86400, // 24 hours
            max_audit_entries: 10000,
        }
    }
}

impl Default for PerformanceConfig {
    fn default() -> Self {
        Self {
            max_memory_bytes: 4 * 1024 * 1024 * 1024, // 4GB
            wake_word_timeout_ms: 50,
            speech_recognition_timeout_ms: 120,
            llm_response_timeout_ms: 200,
            avatar_target_fps: 24,
        }
    }
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            enable_biometric_auth: false, // Will be enabled in Task 4
            max_auth_attempts: 3,
            auth_lockout_duration: 300, // 5 minutes
            enable_audit_logging: true,
        }
    }
}

impl Default for LoggingConfig {
    fn default() -> Self {
        Self {
            level: "info".to_string(),
            structured: true,
            file_path: None,
            max_file_size: 100 * 1024 * 1024, // 100MB
            max_files: 5,
        }
    }
}

impl SystemConfig {
    /// Load configuration from file
    /// 
    /// # Arguments
    /// * `path` - Path to configuration file
    /// 
    /// # Returns
    /// * `SystemResult<SystemConfig>` - Loaded configuration or error
    pub fn from_file<P: AsRef<std::path::Path>>(path: P) -> SystemResult<Self> {
        let content = std::fs::read_to_string(path)
            .map_err(|e| SystemError::config(format!("Failed to read config file: {}", e)))?;
        
        let config: SystemConfig = serde_json::from_str(&content)
            .map_err(|e| SystemError::config(format!("Failed to parse config: {}", e)))?;
        
        config.validate()?;
        Ok(config)
    }
    
    /// Load configuration from environment variables
    /// 
    /// # Returns
    /// * `SystemResult<SystemConfig>` - Configuration from environment or error
    pub fn from_env() -> SystemResult<Self> {
        let mut config = SystemConfig::default();
        
        // Override with environment variables if present
        if let Ok(level) = std::env::var("AGENT_GURU_LOG_LEVEL") {
            config.logging.level = level;
        }
        
        if let Ok(max_memory) = std::env::var("AGENT_GURU_MAX_MEMORY") {
            config.performance.max_memory_bytes = max_memory.parse()
                .map_err(|e| SystemError::config(format!("Invalid max memory: {}", e)))?;
        }
        
        if let Ok(wake_timeout) = std::env::var("AGENT_GURU_WAKE_TIMEOUT") {
            config.performance.wake_word_timeout_ms = wake_timeout.parse()
                .map_err(|e| SystemError::config(format!("Invalid wake timeout: {}", e)))?;
        }
        
        config.validate()?;
        Ok(config)
    }
    
    /// Validate configuration parameters
    /// 
    /// # Returns
    /// * `SystemResult<()>` - Success or validation error
    pub fn validate(&self) -> SystemResult<()> {
        // Validate performance parameters
        if self.performance.max_memory_bytes < 1024 * 1024 * 1024 {
            return Err(SystemError::config("Maximum memory must be at least 1GB"));
        }
        
        if self.performance.wake_word_timeout_ms == 0 || self.performance.wake_word_timeout_ms > 1000 {
            return Err(SystemError::config("Wake word timeout must be between 1-1000ms"));
        }
        
        if self.performance.speech_recognition_timeout_ms == 0 || self.performance.speech_recognition_timeout_ms > 5000 {
            return Err(SystemError::config("Speech recognition timeout must be between 1-5000ms"));
        }
        
        if self.performance.llm_response_timeout_ms == 0 || self.performance.llm_response_timeout_ms > 10000 {
            return Err(SystemError::config("LLM response timeout must be between 1-10000ms"));
        }
        
        if self.performance.avatar_target_fps == 0 || self.performance.avatar_target_fps > 120 {
            return Err(SystemError::config("Avatar target FPS must be between 1-120"));
        }
        
        // Validate security parameters
        if self.security.max_auth_attempts == 0 || self.security.max_auth_attempts > 10 {
            return Err(SystemError::config("Max auth attempts must be between 1-10"));
        }
        
        if self.security.auth_lockout_duration == 0 || self.security.auth_lockout_duration > 3600 {
            return Err(SystemError::config("Auth lockout duration must be between 1-3600 seconds"));
        }
        
        // Validate crypto parameters
        if self.crypto.key_rotation_interval < 3600 {
            return Err(SystemError::config("Key rotation interval must be at least 1 hour"));
        }
        
        if self.crypto.max_audit_entries == 0 || self.crypto.max_audit_entries > 1_000_000 {
            return Err(SystemError::config("Max audit entries must be between 1-1,000,000"));
        }
        
        // Validate logging parameters
        let valid_levels = ["error", "warn", "info", "debug", "trace"];
        if !valid_levels.contains(&self.logging.level.as_str()) {
            return Err(SystemError::config(format!(
                "Invalid log level '{}', must be one of: {:?}",
                self.logging.level, valid_levels
            )));
        }
        
        if self.logging.max_file_size == 0 || self.logging.max_file_size > 1024 * 1024 * 1024 {
            return Err(SystemError::config("Max log file size must be between 1 byte and 1GB"));
        }
        
        if self.logging.max_files == 0 || self.logging.max_files > 100 {
            return Err(SystemError::config("Max log files must be between 1-100"));
        }
        
        Ok(())
    }
    
    /// Save configuration to file
    /// 
    /// # Arguments
    /// * `path` - Path to save configuration file
    /// 
    /// # Returns
    /// * `SystemResult<()>` - Success or error
    pub fn save_to_file<P: AsRef<std::path::Path>>(&self, path: P) -> SystemResult<()> {
        let content = serde_json::to_string_pretty(self)
            .map_err(|e| SystemError::config(format!("Failed to serialize config: {}", e)))?;
        
        std::fs::write(path, content)
            .map_err(|e| SystemError::config(format!("Failed to write config file: {}", e)))?;
        
        Ok(())
    }
    
    /// Get performance requirements as a summary
    pub fn performance_summary(&self) -> String {
        format!(
            "Performance Requirements: Wake Word ≤{}ms, STT ≤{}ms, LLM ≤{}ms, Avatar ≥{}fps, Memory ≤{}GB",
            self.performance.wake_word_timeout_ms,
            self.performance.speech_recognition_timeout_ms,
            self.performance.llm_response_timeout_ms,
            self.performance.avatar_target_fps,
            self.performance.max_memory_bytes / (1024 * 1024 * 1024)
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;
    
    #[test]
    fn test_default_config() {
        let config = SystemConfig::default();
        assert!(config.validate().is_ok());
    }
    
    #[test]
    fn test_config_validation() {
        let mut config = SystemConfig::default();
        
        // Test invalid memory size
        config.performance.max_memory_bytes = 100;
        assert!(config.validate().is_err());
        
        // Reset and test invalid timeout
        config = SystemConfig::default();
        config.performance.wake_word_timeout_ms = 0;
        assert!(config.validate().is_err());
        
        // Reset and test invalid log level
        config = SystemConfig::default();
        config.logging.level = "invalid".to_string();
        assert!(config.validate().is_err());
    }
    
    #[test]
    fn test_config_file_operations() {
        let dir = tempdir().unwrap();
        let config_path = dir.path().join("test_config.json");
        
        let config = SystemConfig::default();
        
        // Save config
        assert!(config.save_to_file(&config_path).is_ok());
        
        // Load config
        let loaded_config = SystemConfig::from_file(&config_path).unwrap();
        
        // Verify they match
        assert_eq!(config.performance.max_memory_bytes, loaded_config.performance.max_memory_bytes);
        assert_eq!(config.logging.level, loaded_config.logging.level);
    }
    
    #[test]
    fn test_performance_summary() {
        let config = SystemConfig::default();
        let summary = config.performance_summary();
        assert!(summary.contains("Wake Word ≤50ms"));
        assert!(summary.contains("STT ≤120ms"));
        assert!(summary.contains("LLM ≤200ms"));
    }
    
    #[test]
    fn test_env_config_loading() {
        // Set environment variable
        std::env::set_var("AGENT_GURU_LOG_LEVEL", "debug");
        
        let config = SystemConfig::from_env().unwrap();
        assert_eq!(config.logging.level, "debug");
        
        // Clean up
        std::env::remove_var("AGENT_GURU_LOG_LEVEL");
    }
}