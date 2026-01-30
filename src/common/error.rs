//! Common error types for the AGENT_GURU system
//!
//! This module provides a unified error handling system with proper error chaining,
//! context preservation, and security-aware error messages that don't leak sensitive
//! information.

use thiserror::Error;

/// Top-level system error type that encompasses all possible errors
#[derive(Error, Debug, Clone)]
pub enum SystemError {
    /// Cryptographic operation failed
    #[error("Cryptographic error: {0}")]
    Crypto(#[from] crate::security::crypto::identity::CryptoError),
    
    /// Configuration error
    #[error("Configuration error: {0}")]
    Config(String),
    
    /// I/O operation failed
    #[error("I/O error: {0}")]
    Io(String),
    
    /// Network operation failed
    #[error("Network error: {0}")]
    Network(String),
    
    /// Authentication failed
    #[error("Authentication failed: {0}")]
    Authentication(String),
    
    /// Authorization failed
    #[error("Authorization failed: {0}")]
    Authorization(String),
    
    /// Resource not found
    #[error("Resource not found: {0}")]
    NotFound(String),
    
    /// Resource already exists
    #[error("Resource already exists: {0}")]
    AlreadyExists(String),
    
    /// Invalid input or parameters
    #[error("Invalid input: {0}")]
    InvalidInput(String),
    
    /// System resource exhausted
    #[error("Resource exhausted: {0}")]
    ResourceExhausted(String),
    
    /// Operation timeout
    #[error("Operation timeout: {0}")]
    Timeout(String),
    
    /// Internal system error
    #[error("Internal error: {0}")]
    Internal(String),
    
    /// Feature not implemented
    #[error("Feature not implemented: {0}")]
    NotImplemented(String),
    
    /// Service unavailable
    #[error("Service unavailable: {0}")]
    ServiceUnavailable(String),
}

impl SystemError {
    /// Create a new configuration error
    pub fn config<S: Into<String>>(message: S) -> Self {
        Self::Config(message.into())
    }
    
    /// Create a new I/O error
    pub fn io<S: Into<String>>(message: S) -> Self {
        Self::Io(message.into())
    }
    
    /// Create a new network error
    pub fn network<S: Into<String>>(message: S) -> Self {
        Self::Network(message.into())
    }
    
    /// Create a new authentication error
    pub fn authentication<S: Into<String>>(message: S) -> Self {
        Self::Authentication(message.into())
    }
    
    /// Create a new authorization error
    pub fn authorization<S: Into<String>>(message: S) -> Self {
        Self::Authorization(message.into())
    }
    
    /// Create a new not found error
    pub fn not_found<S: Into<String>>(message: S) -> Self {
        Self::NotFound(message.into())
    }
    
    /// Create a new already exists error
    pub fn already_exists<S: Into<String>>(message: S) -> Self {
        Self::AlreadyExists(message.into())
    }
    
    /// Create a new invalid input error
    pub fn invalid_input<S: Into<String>>(message: S) -> Self {
        Self::InvalidInput(message.into())
    }
    
    /// Create a new resource exhausted error
    pub fn resource_exhausted<S: Into<String>>(message: S) -> Self {
        Self::ResourceExhausted(message.into())
    }
    
    /// Create a new timeout error
    pub fn timeout<S: Into<String>>(message: S) -> Self {
        Self::Timeout(message.into())
    }
    
    /// Create a new internal error
    pub fn internal<S: Into<String>>(message: S) -> Self {
        Self::Internal(message.into())
    }
    
    /// Create a new not implemented error
    pub fn not_implemented<S: Into<String>>(message: S) -> Self {
        Self::NotImplemented(message.into())
    }
    
    /// Create a new service unavailable error
    pub fn service_unavailable<S: Into<String>>(message: S) -> Self {
        Self::ServiceUnavailable(message.into())
    }
    
    /// Check if this error is retryable
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            Self::Network(_) | Self::Timeout(_) | Self::ServiceUnavailable(_) | Self::ResourceExhausted(_)
        )
    }
    
    /// Check if this error is a client error (4xx equivalent)
    pub fn is_client_error(&self) -> bool {
        matches!(
            self,
            Self::Authentication(_) | Self::Authorization(_) | Self::NotFound(_) | 
            Self::AlreadyExists(_) | Self::InvalidInput(_)
        )
    }
    
    /// Check if this error is a server error (5xx equivalent)
    pub fn is_server_error(&self) -> bool {
        matches!(
            self,
            Self::Internal(_) | Self::ServiceUnavailable(_) | Self::ResourceExhausted(_)
        )
    }
    
    /// Get error category for logging and metrics
    pub fn category(&self) -> &'static str {
        match self {
            Self::Crypto(_) => "crypto",
            Self::Config(_) => "config",
            Self::Io(_) => "io",
            Self::Network(_) => "network",
            Self::Authentication(_) => "auth",
            Self::Authorization(_) => "authz",
            Self::NotFound(_) => "not_found",
            Self::AlreadyExists(_) => "already_exists",
            Self::InvalidInput(_) => "invalid_input",
            Self::ResourceExhausted(_) => "resource_exhausted",
            Self::Timeout(_) => "timeout",
            Self::Internal(_) => "internal",
            Self::NotImplemented(_) => "not_implemented",
            Self::ServiceUnavailable(_) => "service_unavailable",
        }
    }
}

/// Result type alias for system operations
pub type SystemResult<T> = Result<T, SystemError>;

/// Convert standard I/O errors to system errors
impl From<std::io::Error> for SystemError {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error.to_string())
    }
}

/// Convert JSON serialization errors to system errors
impl From<serde_json::Error> for SystemError {
    fn from(error: serde_json::Error) -> Self {
        Self::InvalidInput(format!("JSON error: {}", error))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_error_creation() {
        let error = SystemError::config("test config error");
        assert!(matches!(error, SystemError::Config(_)));
        assert_eq!(error.category(), "config");
    }
    
    #[test]
    fn test_error_classification() {
        let client_error = SystemError::invalid_input("bad input");
        assert!(client_error.is_client_error());
        assert!(!client_error.is_server_error());
        assert!(!client_error.is_retryable());
        
        let server_error = SystemError::internal("server issue");
        assert!(server_error.is_server_error());
        assert!(!server_error.is_client_error());
        assert!(!server_error.is_retryable());
        
        let retryable_error = SystemError::timeout("operation timeout");
        assert!(retryable_error.is_retryable());
        assert!(!retryable_error.is_client_error());
        assert!(!retryable_error.is_server_error());
    }
    
    #[test]
    fn test_error_categories() {
        assert_eq!(SystemError::config("test").category(), "config");
        assert_eq!(SystemError::network("test").category(), "network");
        assert_eq!(SystemError::authentication("test").category(), "auth");
    }
}