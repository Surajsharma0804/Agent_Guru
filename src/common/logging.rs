//! Secure logging utilities for AGENT_GURU system
//!
//! This module provides structured logging with security-aware sanitization
//! to prevent sensitive information leakage while maintaining debugging utility.

use serde_json::Value;
use std::collections::HashMap;
use crate::common::config::LoggingConfig;
use crate::common::error::SystemResult;

/// Security-aware logger that sanitizes sensitive information
#[derive(Debug)]
pub struct SecureLogger {
    /// Configuration for logging behavior
    config: LoggingConfig,
    
    /// Patterns to sanitize from log messages
    sensitive_patterns: Vec<String>,
}

impl SecureLogger {
    /// Create a new secure logger with configuration
    /// 
    /// # Arguments
    /// * `config` - Logging configuration
    /// 
    /// # Returns
    /// * `SecureLogger` - Configured logger instance
    pub fn new(config: LoggingConfig) -> Self {
        let sensitive_patterns = vec![
            // Cryptographic keys and secrets
            "secret_key".to_string(),
            "private_key".to_string(),
            "password".to_string(),
            "token".to_string(),
            "signature".to_string(),
            
            // Personal information
            "ssn".to_string(),
            "social_security".to_string(),
            "credit_card".to_string(),
            "phone".to_string(),
            "email".to_string(),
            
            // Biometric data
            "fingerprint".to_string(),
            "face_template".to_string(),
            "voice_print".to_string(),
            "biometric".to_string(),
        ];
        
        Self {
            config,
            sensitive_patterns,
        }
    }
    
    /// Initialize the global logger with secure configuration
    /// 
    /// # Arguments
    /// * `config` - Logging configuration
    /// 
    /// # Returns
    /// * `SystemResult<()>` - Success or initialization error
    pub fn initialize_global(config: &LoggingConfig) -> SystemResult<()> {
        let log_level = match config.level.as_str() {
            "error" => log::LevelFilter::Error,
            "warn" => log::LevelFilter::Warn,
            "info" => log::LevelFilter::Info,
            "debug" => log::LevelFilter::Debug,
            "trace" => log::LevelFilter::Trace,
            _ => log::LevelFilter::Info,
        };
        
        env_logger::Builder::from_default_env()
            .filter_level(log_level)
            .format_timestamp_secs()
            .init();
        
        log::info!("Secure logging initialized with level: {}", config.level);
        Ok(())
    }
    
    /// Sanitize a log message to remove sensitive information
    /// 
    /// # Arguments
    /// * `message` - Original log message
    /// 
    /// # Returns
    /// * `String` - Sanitized log message
    /// 
    /// # Time Complexity
    /// O(n*m) where n = message length, m = number of sensitive patterns
    pub fn sanitize_message(&self, message: &str) -> String {
        let mut sanitized = message.to_string();
        
        // Replace sensitive patterns with redacted placeholders
        for pattern in &self.sensitive_patterns {
            // Case-insensitive pattern matching
            let pattern_lower = pattern.to_lowercase();
            let message_lower = sanitized.to_lowercase();
            
            if message_lower.contains(&pattern_lower) {
                // Find all occurrences and replace with appropriate redaction
                sanitized = self.redact_pattern(&sanitized, pattern);
            }
        }
        
        // Additional sanitization for common sensitive formats
        sanitized = self.sanitize_hex_patterns(&sanitized);
        sanitized = self.sanitize_base64_patterns(&sanitized);
        
        sanitized
    }
    
    /// Redact a specific pattern from the message
    /// 
    /// # Arguments
    /// * `message` - Message to sanitize
    /// * `pattern` - Pattern to redact
    /// 
    /// # Returns
    /// * `String` - Message with pattern redacted
    fn redact_pattern(&self, message: &str, pattern: &str) -> String {
        let redacted = format!("[REDACTED_{}]", pattern.to_uppercase());
        
        // Enhanced pattern matching to capture key-value pairs
        // Pattern: "keyword is value" or "keyword: value" or "keyword = value"
        let key_value_patterns = [
            format!(r"(?i)\b{}\s+(is|:|\=)\s+\S+", regex::escape(pattern)),
            format!(r"(?i)\b{}\b", regex::escape(pattern)),
        ];
        
        let mut result = message.to_string();
        
        for regex_pattern in &key_value_patterns {
            if let Ok(re) = regex::Regex::new(regex_pattern) {
                result = re.replace_all(&result, redacted.as_str()).to_string();
                break; // Use first matching pattern
            }
        }
        
        // Fallback to simple string replacement if regex fails
        if result == message {
            result = message.replace(pattern, &redacted);
        }
        
        result
    }
    
    /// Sanitize hexadecimal patterns that might be cryptographic material
    /// 
    /// # Arguments
    /// * `message` - Message to sanitize
    /// 
    /// # Returns
    /// * `String` - Message with hex patterns sanitized
    fn sanitize_hex_patterns(&self, message: &str) -> String {
        // Redact long hex strings that might be keys or hashes
        if let Ok(hex_regex) = regex::Regex::new(r"\b[0-9a-fA-F]{16,}\b") {
            hex_regex.replace_all(message, "[REDACTED_HEX]").to_string()
        } else {
            message.to_string()
        }
    }
    
    /// Sanitize base64 patterns that might be encoded sensitive data
    /// 
    /// # Arguments
    /// * `message` - Message to sanitize
    /// 
    /// # Returns
    /// * `String` - Message with base64 patterns sanitized
    fn sanitize_base64_patterns(&self, message: &str) -> String {
        // Redact long base64 strings that might be encoded sensitive data
        if let Ok(b64_regex) = regex::Regex::new(r"\b[A-Za-z0-9+/]{16,}={0,2}\b") {
            b64_regex.replace_all(message, "[REDACTED_BASE64]").to_string()
        } else {
            message.to_string()
        }
    }
    
    /// Create a structured log entry with sanitization
    /// 
    /// # Arguments
    /// * `level` - Log level
    /// * `message` - Log message
    /// * `context` - Additional context data
    /// 
    /// # Returns
    /// * `Value` - Structured log entry as JSON
    pub fn create_structured_entry(
        &self,
        level: &str,
        message: &str,
        context: &HashMap<String, String>,
    ) -> Value {
        let sanitized_message = self.sanitize_message(message);
        let mut sanitized_context = HashMap::new();
        
        // Sanitize context values
        for (key, value) in context {
            let sanitized_value = if self.is_sensitive_key(key) {
                "[REDACTED]".to_string()
            } else {
                self.sanitize_message(value)
            };
            sanitized_context.insert(key.clone(), sanitized_value);
        }
        
        serde_json::json!({
            "timestamp": chrono::Utc::now().to_rfc3339(),
            "level": level,
            "message": sanitized_message,
            "context": sanitized_context,
            "component": "agent_guru",
            "version": env!("CARGO_PKG_VERSION")
        })
    }
    
    /// Check if a key name indicates sensitive information
    /// 
    /// # Arguments
    /// * `key` - Key name to check
    /// 
    /// # Returns
    /// * `bool` - True if the key is considered sensitive
    fn is_sensitive_key(&self, key: &str) -> bool {
        let key_lower = key.to_lowercase();
        self.sensitive_patterns.iter().any(|pattern| {
            key_lower.contains(&pattern.to_lowercase())
        })
    }
    
    /// Log a security event with enhanced context
    /// 
    /// # Arguments
    /// * `event_type` - Type of security event
    /// * `message` - Event description
    /// * `context` - Additional event context
    pub fn log_security_event(
        &self,
        event_type: &str,
        message: &str,
        context: &HashMap<String, String>,
    ) {
        let mut security_context = context.clone();
        security_context.insert("event_type".to_string(), event_type.to_string());
        security_context.insert("security_event".to_string(), "true".to_string());
        
        if self.config.structured {
            let entry = self.create_structured_entry("warn", message, &security_context);
            log::warn!("{}", entry);
        } else {
            let sanitized_message = self.sanitize_message(message);
            log::warn!("SECURITY_EVENT [{}]: {}", event_type, sanitized_message);
        }
    }
    
    /// Log a performance metric
    /// 
    /// # Arguments
    /// * `metric_name` - Name of the performance metric
    /// * `value` - Metric value
    /// * `unit` - Unit of measurement
    /// * `context` - Additional metric context
    pub fn log_performance_metric(
        &self,
        metric_name: &str,
        value: f64,
        unit: &str,
        context: &HashMap<String, String>,
    ) {
        let mut perf_context = context.clone();
        perf_context.insert("metric_name".to_string(), metric_name.to_string());
        perf_context.insert("metric_value".to_string(), value.to_string());
        perf_context.insert("metric_unit".to_string(), unit.to_string());
        perf_context.insert("performance_metric".to_string(), "true".to_string());
        
        if self.config.structured {
            let entry = self.create_structured_entry("info", 
                &format!("Performance metric: {} = {} {}", metric_name, value, unit), 
                &perf_context);
            log::info!("{}", entry);
        } else {
            log::info!("PERFORMANCE: {} = {} {} {:?}", metric_name, value, unit, context);
        }
    }
}

/// Convenience macros for secure logging

/// Securely log an info message with automatic sanitization
/// 
/// # Arguments
/// * `$logger` - SecureLogger instance
/// * `$msg` - Message to log (with optional format arguments)
/// 
/// # Examples
/// ```no_run
/// use agent_guru::common::logging::SecureLogger;
/// use agent_guru::common::config::LoggingConfig;
/// use agent_guru::secure_log_info;
/// 
/// let config = LoggingConfig::default();
/// let logger = SecureLogger::new(config);
/// secure_log_info!(logger, "User logged in");
/// secure_log_info!(logger, "Processing {} items", 42);
/// ```
#[macro_export]
macro_rules! secure_log_info {
    ($logger:expr, $msg:expr) => {
        log::info!("{}", $logger.sanitize_message($msg));
    };
    ($logger:expr, $msg:expr, $($arg:tt)*) => {
        log::info!("{}", $logger.sanitize_message(&format!($msg, $($arg)*)));
    };
}

/// Securely log a warning message with automatic sanitization
/// 
/// # Arguments
/// * `$logger` - SecureLogger instance
/// * `$msg` - Message to log (with optional format arguments)
/// 
/// # Examples
/// ```no_run
/// use agent_guru::common::logging::SecureLogger;
/// use agent_guru::common::config::LoggingConfig;
/// use agent_guru::secure_log_warn;
/// 
/// let config = LoggingConfig::default();
/// let logger = SecureLogger::new(config);
/// secure_log_warn!(logger, "Invalid input detected");
/// secure_log_warn!(logger, "Retry attempt {} failed", 3);
/// ```
#[macro_export]
macro_rules! secure_log_warn {
    ($logger:expr, $msg:expr) => {
        log::warn!("{}", $logger.sanitize_message($msg));
    };
    ($logger:expr, $msg:expr, $($arg:tt)*) => {
        log::warn!("{}", $logger.sanitize_message(&format!($msg, $($arg)*)));
    };
}

/// Securely log an error message with automatic sanitization
/// 
/// # Arguments
/// * `$logger` - SecureLogger instance
/// * `$msg` - Message to log (with optional format arguments)
/// 
/// # Examples
/// ```no_run
/// use agent_guru::common::logging::SecureLogger;
/// use agent_guru::common::config::LoggingConfig;
/// use agent_guru::secure_log_error;
/// 
/// let config = LoggingConfig::default();
/// let logger = SecureLogger::new(config);
/// secure_log_error!(logger, "Authentication failed");
/// secure_log_error!(logger, "Database error: {}", "connection timeout");
/// ```
#[macro_export]
macro_rules! secure_log_error {
    ($logger:expr, $msg:expr) => {
        log::error!("{}", $logger.sanitize_message($msg));
    };
    ($logger:expr, $msg:expr, $($arg:tt)*) => {
        log::error!("{}", $logger.sanitize_message(&format!($msg, $($arg)*)));
    };
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_message_sanitization() {
        let config = LoggingConfig::default();
        let logger = SecureLogger::new(config);
        
        let sensitive_message = "User secret_key is abc123 and password is xyz789";
        let sanitized = logger.sanitize_message(sensitive_message);
        
        assert!(sanitized.contains("[REDACTED_SECRET_KEY]"));
        assert!(sanitized.contains("[REDACTED_PASSWORD]"));
        assert!(!sanitized.contains("abc123"));
        assert!(!sanitized.contains("xyz789"));
    }
    
    #[test]
    fn test_hex_pattern_sanitization() {
        let config = LoggingConfig::default();
        let logger = SecureLogger::new(config);
        
        let hex_message = "Generated key: 1234567890abcdef1234567890abcdef12345678";
        let sanitized = logger.sanitize_message(hex_message);
        
        assert!(sanitized.contains("[REDACTED_HEX]"));
        assert!(!sanitized.contains("1234567890abcdef"));
    }
    
    #[test]
    fn test_structured_log_entry() {
        let config = LoggingConfig::default();
        let logger = SecureLogger::new(config);
        
        let mut context = HashMap::new();
        context.insert("user_id".to_string(), "12345".to_string());
        context.insert("secret_key".to_string(), "sensitive_data".to_string());
        
        let entry = logger.create_structured_entry("info", "Test message", &context);
        
        assert_eq!(entry["level"], "info");
        assert_eq!(entry["message"], "Test message");
        assert_eq!(entry["context"]["user_id"], "12345");
        assert_eq!(entry["context"]["secret_key"], "[REDACTED]");
    }
    
    #[test]
    fn test_sensitive_key_detection() {
        let config = LoggingConfig::default();
        let logger = SecureLogger::new(config);
        
        assert!(logger.is_sensitive_key("secret_key"));
        assert!(logger.is_sensitive_key("user_password"));
        assert!(logger.is_sensitive_key("biometric_template"));
        assert!(!logger.is_sensitive_key("user_id"));
        assert!(!logger.is_sensitive_key("timestamp"));
    }
    
    #[test]
    fn test_security_event_logging() {
        let config = LoggingConfig::default();
        let logger = SecureLogger::new(config);
        
        let mut context = HashMap::new();
        context.insert("user_id".to_string(), "12345".to_string());
        context.insert("attempt_count".to_string(), "3".to_string());
        
        // This should not panic and should sanitize properly
        logger.log_security_event("AUTH_FAILURE", "Authentication failed", &context);
    }
    
    #[test]
    fn test_performance_metric_logging() {
        let config = LoggingConfig::default();
        let logger = SecureLogger::new(config);
        
        let context = HashMap::new();
        
        // This should not panic
        logger.log_performance_metric("response_time", 45.5, "ms", &context);
    }
}