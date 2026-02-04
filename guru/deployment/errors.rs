//! # Deployment Error Types
//! 
//! **MAXIMUM ENGINEERING MANDATE (ZERO COMPROMISE):**
//! Complete error handling with detailed error information - never simplified error reporting.
//! Full error context, recovery suggestions, diagnostic information - no deferred error handling.
//! Production standards: Must provide comprehensive error information for debugging and recovery.

use std::fmt;

/// Comprehensive deployment error types with detailed context
#[derive(Debug, Clone)]
pub enum DeploymentError {
    // Package validation errors
    InvalidPackageName,
    InvalidPackageVersion,
    InvalidPackageSize,
    InvalidChecksum,
    
    // Signature and cryptographic errors
    InvalidSignatureLength,
    InvalidPublicKeyLength,
    SignatureVerificationFailed(String, String), // component_name, error_details
    CertificateChainInvalid(String),
    SignatureExpired(String),
    
    // Dependency resolution errors
    DependencyResolutionFailed(String),
    CircularDependencyDetected(Vec<String>),
    MissingDependency(String, String), // component_name, dependency_name
    IncompatibleDependencyVersion(String, String, String), // component, dependency, version
    
    // Installation and extraction errors
    PackageExtractionFailed(String, String), // component_name, error_details
    InstallationDirectoryNotFound(String),
    InsufficientDiskSpace(u64, u64), // required_bytes, available_bytes
    InsufficientPermissions(String),
    FileSystemError(String),
    
    // Platform integration errors
    PlatformIntegrationFailed(String),
    UnsupportedPlatform(String),
    PlatformVersionNotSupported(String, String), // platform, version
    RegistryAccessFailed(String),
    ServiceRegistrationFailed(String),
    
    // Backup and rollback errors
    BackupCreationFailed(String),
    BackupCorrupted(String),
    RollbackFailed(String),
    RollbackTargetNotFound(String),
    RollbackIntegrityFailure,
    
    // Update and migration errors
    UpdateFailedRolledBack(String), // version
    UpdatePackageIncompatible(String, String), // from_version, to_version
    MigrationFailed(String, String), // from_platform, to_platform
    VersionDowngradeNotAllowed(String, String), // from_version, to_version
    
    // Integrity and verification errors
    IntegrityCheckFailed(f32), // success_rate
    IntegrityVerificationFailed(String),
    ChecksumMismatch(String, String, String), // file_path, expected, actual
    FileCorrupted(String),
    
    // Network and download errors
    DownloadFailed(String, String), // url, error_details
    NetworkTimeout(String),
    ServerUnavailable(String),
    InvalidDownloadUrl(String),
    
    // Configuration and settings errors
    ConfigurationError(String),
    InvalidInstallationTarget(String),
    SettingsValidationFailed(String),
    
    // Resource and performance errors
    MemoryAllocationFailed(usize), // requested_bytes
    ConcurrentOperationTimeout,
    ResourceExhausted(String),
    PerformanceThresholdExceeded(String, u64, u64), // metric_name, actual, threshold
    
    // System and environment errors
    SystemRequirementsNotMet(Vec<String>),
    EnvironmentVariableNotSet(String),
    ServiceNotRunning(String),
    ProcessExecutionFailed(String, i32), // command, exit_code
    
    // User and permission errors
    UserCancelled,
    NoOperationToCancel,
    OperationInProgress(String),
    AccessDenied(String),
    
    // Cleanup and maintenance errors
    CleanupFailed(String),
    TempFileCleanupFailed(String),
    LogFileRotationFailed(String),
    
    // Generic and unknown errors
    UnknownError(String),
    InternalError(String),
}

impl fmt::Display for DeploymentError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            // Package validation errors
            DeploymentError::InvalidPackageName => {
                write!(f, "Package name is invalid or empty")
            }
            DeploymentError::InvalidPackageVersion => {
                write!(f, "Package version is invalid or empty")
            }
            DeploymentError::InvalidPackageSize => {
                write!(f, "Package size is invalid (must be greater than 0)")
            }
            DeploymentError::InvalidChecksum => {
                write!(f, "Package checksum is invalid (must be 64-character SHA-256 hex string)")
            }
            
            // Signature and cryptographic errors
            DeploymentError::InvalidSignatureLength => {
                write!(f, "Cryptographic signature has invalid length for the specified algorithm")
            }
            DeploymentError::InvalidPublicKeyLength => {
                write!(f, "Public key has invalid length for the specified algorithm")
            }
            DeploymentError::SignatureVerificationFailed(component, details) => {
                write!(f, "Signature verification failed for component '{}': {}", component, details)
            }
            DeploymentError::CertificateChainInvalid(details) => {
                write!(f, "Certificate chain validation failed: {}", details)
            }
            DeploymentError::SignatureExpired(component) => {
                write!(f, "Signature for component '{}' has expired", component)
            }
            
            // Dependency resolution errors
            DeploymentError::DependencyResolutionFailed(details) => {
                write!(f, "Dependency resolution failed: {}", details)
            }
            DeploymentError::CircularDependencyDetected(cycle) => {
                write!(f, "Circular dependency detected: {}", cycle.join(" -> "))
            }
            DeploymentError::MissingDependency(component, dependency) => {
                write!(f, "Component '{}' requires missing dependency '{}'", component, dependency)
            }
            DeploymentError::IncompatibleDependencyVersion(component, dependency, version) => {
                write!(f, "Component '{}' requires incompatible version of dependency '{}': {}", 
                       component, dependency, version)
            }
            
            // Installation and extraction errors
            DeploymentError::PackageExtractionFailed(component, details) => {
                write!(f, "Failed to extract package '{}': {}", component, details)
            }
            DeploymentError::InstallationDirectoryNotFound(path) => {
                write!(f, "Installation directory not found: {}", path)
            }
            DeploymentError::InsufficientDiskSpace(required, available) => {
                write!(f, "Insufficient disk space: {} bytes required, {} bytes available", 
                       required, available)
            }
            DeploymentError::InsufficientPermissions(operation) => {
                write!(f, "Insufficient permissions for operation: {}", operation)
            }
            DeploymentError::FileSystemError(details) => {
                write!(f, "File system error: {}", details)
            }
            
            // Platform integration errors
            DeploymentError::PlatformIntegrationFailed(details) => {
                write!(f, "Platform integration failed: {}", details)
            }
            DeploymentError::UnsupportedPlatform(platform) => {
                write!(f, "Unsupported platform: {}", platform)
            }
            DeploymentError::PlatformVersionNotSupported(platform, version) => {
                write!(f, "Platform version not supported: {} {}", platform, version)
            }
            DeploymentError::RegistryAccessFailed(details) => {
                write!(f, "Registry access failed: {}", details)
            }
            DeploymentError::ServiceRegistrationFailed(service) => {
                write!(f, "Service registration failed: {}", service)
            }
            
            // Backup and rollback errors
            DeploymentError::BackupCreationFailed(details) => {
                write!(f, "Backup creation failed: {}", details)
            }
            DeploymentError::BackupCorrupted(backup_id) => {
                write!(f, "Backup is corrupted: {}", backup_id)
            }
            DeploymentError::RollbackFailed(details) => {
                write!(f, "Rollback operation failed: {}", details)
            }
            DeploymentError::RollbackTargetNotFound(version) => {
                write!(f, "Rollback target not found for version: {}", version)
            }
            DeploymentError::RollbackIntegrityFailure => {
                write!(f, "Rollback completed but integrity verification failed")
            }
            
            // Update and migration errors
            DeploymentError::UpdateFailedRolledBack(version) => {
                write!(f, "Update failed and system was rolled back to version: {}", version)
            }
            DeploymentError::UpdatePackageIncompatible(from_version, to_version) => {
                write!(f, "Update package incompatible: cannot update from {} to {}", 
                       from_version, to_version)
            }
            DeploymentError::MigrationFailed(from_platform, to_platform) => {
                write!(f, "Migration failed from {} to {}", from_platform, to_platform)
            }
            DeploymentError::VersionDowngradeNotAllowed(from_version, to_version) => {
                write!(f, "Version downgrade not allowed: from {} to {}", from_version, to_version)
            }
            
            // Integrity and verification errors
            DeploymentError::IntegrityCheckFailed(success_rate) => {
                write!(f, "Integrity check failed: {:.1}% success rate (minimum 99% required)", 
                       success_rate * 100.0)
            }
            DeploymentError::IntegrityVerificationFailed(details) => {
                write!(f, "Integrity verification failed: {}", details)
            }
            DeploymentError::ChecksumMismatch(file_path, expected, actual) => {
                write!(f, "Checksum mismatch for file '{}': expected {}, got {}", 
                       file_path, expected, actual)
            }
            DeploymentError::FileCorrupted(file_path) => {
                write!(f, "File is corrupted: {}", file_path)
            }
            
            // Network and download errors
            DeploymentError::DownloadFailed(url, details) => {
                write!(f, "Download failed from '{}': {}", url, details)
            }
            DeploymentError::NetworkTimeout(operation) => {
                write!(f, "Network timeout during operation: {}", operation)
            }
            DeploymentError::ServerUnavailable(server) => {
                write!(f, "Server unavailable: {}", server)
            }
            DeploymentError::InvalidDownloadUrl(url) => {
                write!(f, "Invalid download URL: {}", url)
            }
            
            // Configuration and settings errors
            DeploymentError::ConfigurationError(details) => {
                write!(f, "Configuration error: {}", details)
            }
            DeploymentError::InvalidInstallationTarget(details) => {
                write!(f, "Invalid installation target: {}", details)
            }
            DeploymentError::SettingsValidationFailed(details) => {
                write!(f, "Settings validation failed: {}", details)
            }
            
            // Resource and performance errors
            DeploymentError::MemoryAllocationFailed(requested_bytes) => {
                write!(f, "Memory allocation failed: {} bytes requested", requested_bytes)
            }
            DeploymentError::ConcurrentOperationTimeout => {
                write!(f, "Concurrent operation timed out")
            }
            DeploymentError::ResourceExhausted(resource) => {
                write!(f, "Resource exhausted: {}", resource)
            }
            DeploymentError::PerformanceThresholdExceeded(metric, actual, threshold) => {
                write!(f, "Performance threshold exceeded for {}: {} > {} (threshold)", 
                       metric, actual, threshold)
            }
            
            // System and environment errors
            DeploymentError::SystemRequirementsNotMet(requirements) => {
                write!(f, "System requirements not met: {}", requirements.join(", "))
            }
            DeploymentError::EnvironmentVariableNotSet(var_name) => {
                write!(f, "Required environment variable not set: {}", var_name)
            }
            DeploymentError::ServiceNotRunning(service_name) => {
                write!(f, "Required service not running: {}", service_name)
            }
            DeploymentError::ProcessExecutionFailed(command, exit_code) => {
                write!(f, "Process execution failed: '{}' exited with code {}", command, exit_code)
            }
            
            // User and permission errors
            DeploymentError::UserCancelled => {
                write!(f, "Operation was cancelled by the user")
            }
            DeploymentError::NoOperationToCancel => {
                write!(f, "No operation is currently running to cancel")
            }
            DeploymentError::OperationInProgress(operation) => {
                write!(f, "Another operation is already in progress: {}", operation)
            }
            DeploymentError::AccessDenied(resource) => {
                write!(f, "Access denied to resource: {}", resource)
            }
            
            // Cleanup and maintenance errors
            DeploymentError::CleanupFailed(details) => {
                write!(f, "Cleanup operation failed: {}", details)
            }
            DeploymentError::TempFileCleanupFailed(details) => {
                write!(f, "Temporary file cleanup failed: {}", details)
            }
            DeploymentError::LogFileRotationFailed(details) => {
                write!(f, "Log file rotation failed: {}", details)
            }
            
            // Generic and unknown errors
            DeploymentError::UnknownError(details) => {
                write!(f, "Unknown error occurred: {}", details)
            }
            DeploymentError::InternalError(details) => {
                write!(f, "Internal error: {}", details)
            }
        }
    }
}

impl std::error::Error for DeploymentError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        // Most deployment errors are leaf errors without underlying causes
        None
    }
}

impl DeploymentError {
    /// Get error category for logging and metrics
    pub fn category(&self) -> ErrorCategory {
        match self {
            DeploymentError::InvalidPackageName |
            DeploymentError::InvalidPackageVersion |
            DeploymentError::InvalidPackageSize |
            DeploymentError::InvalidChecksum => ErrorCategory::Validation,
            
            DeploymentError::InvalidSignatureLength |
            DeploymentError::InvalidPublicKeyLength |
            DeploymentError::SignatureVerificationFailed(_, _) |
            DeploymentError::CertificateChainInvalid(_) |
            DeploymentError::SignatureExpired(_) => ErrorCategory::Security,
            
            DeploymentError::DependencyResolutionFailed(_) |
            DeploymentError::CircularDependencyDetected(_) |
            DeploymentError::MissingDependency(_, _) |
            DeploymentError::IncompatibleDependencyVersion(_, _, _) => ErrorCategory::Dependency,
            
            DeploymentError::PackageExtractionFailed(_, _) |
            DeploymentError::InstallationDirectoryNotFound(_) |
            DeploymentError::InsufficientDiskSpace(_, _) |
            DeploymentError::InsufficientPermissions(_) |
            DeploymentError::FileSystemError(_) => ErrorCategory::Installation,
            
            DeploymentError::PlatformIntegrationFailed(_) |
            DeploymentError::UnsupportedPlatform(_) |
            DeploymentError::PlatformVersionNotSupported(_, _) |
            DeploymentError::RegistryAccessFailed(_) |
            DeploymentError::ServiceRegistrationFailed(_) => ErrorCategory::Platform,
            
            DeploymentError::BackupCreationFailed(_) |
            DeploymentError::BackupCorrupted(_) |
            DeploymentError::RollbackFailed(_) |
            DeploymentError::RollbackTargetNotFound(_) |
            DeploymentError::RollbackIntegrityFailure => ErrorCategory::Backup,
            
            DeploymentError::UpdateFailedRolledBack(_) |
            DeploymentError::UpdatePackageIncompatible(_, _) |
            DeploymentError::MigrationFailed(_, _) |
            DeploymentError::VersionDowngradeNotAllowed(_, _) => ErrorCategory::Update,
            
            DeploymentError::IntegrityCheckFailed(_) |
            DeploymentError::IntegrityVerificationFailed(_) |
            DeploymentError::ChecksumMismatch(_, _, _) |
            DeploymentError::FileCorrupted(_) => ErrorCategory::Integrity,
            
            DeploymentError::DownloadFailed(_, _) |
            DeploymentError::NetworkTimeout(_) |
            DeploymentError::ServerUnavailable(_) |
            DeploymentError::InvalidDownloadUrl(_) => ErrorCategory::Network,
            
            DeploymentError::ConfigurationError(_) |
            DeploymentError::InvalidInstallationTarget(_) |
            DeploymentError::SettingsValidationFailed(_) => ErrorCategory::Configuration,
            
            DeploymentError::MemoryAllocationFailed(_) |
            DeploymentError::ConcurrentOperationTimeout |
            DeploymentError::ResourceExhausted(_) |
            DeploymentError::PerformanceThresholdExceeded(_, _, _) => ErrorCategory::Resource,
            
            DeploymentError::SystemRequirementsNotMet(_) |
            DeploymentError::EnvironmentVariableNotSet(_) |
            DeploymentError::ServiceNotRunning(_) |
            DeploymentError::ProcessExecutionFailed(_, _) => ErrorCategory::System,
            
            DeploymentError::UserCancelled |
            DeploymentError::NoOperationToCancel |
            DeploymentError::OperationInProgress(_) |
            DeploymentError::AccessDenied(_) => ErrorCategory::User,
            
            DeploymentError::CleanupFailed(_) |
            DeploymentError::TempFileCleanupFailed(_) |
            DeploymentError::LogFileRotationFailed(_) => ErrorCategory::Maintenance,
            
            DeploymentError::UnknownError(_) |
            DeploymentError::InternalError(_) => ErrorCategory::Internal,
        }
    }
    
    /// Check if error is recoverable through retry
    pub fn is_recoverable(&self) -> bool {
        match self {
            // Network errors are often recoverable
            DeploymentError::DownloadFailed(_, _) |
            DeploymentError::NetworkTimeout(_) |
            DeploymentError::ServerUnavailable(_) => true,
            
            // Resource errors might be recoverable after cleanup
            DeploymentError::MemoryAllocationFailed(_) |
            DeploymentError::ResourceExhausted(_) => true,
            
            // Some system errors might be recoverable
            DeploymentError::ServiceNotRunning(_) => true,
            
            // Most other errors are not recoverable through simple retry
            _ => false,
        }
    }
    
    /// Get suggested recovery action
    pub fn recovery_suggestion(&self) -> Option<String> {
        match self {
            DeploymentError::InsufficientDiskSpace(required, available) => {
                Some(format!("Free up {} bytes of disk space (currently {} bytes available, {} bytes required)", 
                           required - available, available, required))
            }
            DeploymentError::InsufficientPermissions(operation) => {
                Some(format!("Run the installer as administrator or ensure proper permissions for: {}", operation))
            }
            DeploymentError::MissingDependency(component, dependency) => {
                Some(format!("Install the required dependency '{}' before installing '{}'", dependency, component))
            }
            DeploymentError::ServiceNotRunning(service) => {
                Some(format!("Start the required service: {}", service))
            }
            DeploymentError::NetworkTimeout(_) => {
                Some("Check your internet connection and try again".to_string())
            }
            DeploymentError::BackupCreationFailed(_) => {
                Some("Ensure sufficient disk space and permissions for backup creation".to_string())
            }
            DeploymentError::UnsupportedPlatform(platform) => {
                Some(format!("This software is not supported on platform: {}", platform))
            }
            _ => None,
        }
    }
}

/// Error category for classification and metrics
#[derive(Debug, Clone, PartialEq)]
pub enum ErrorCategory {
    Validation,
    Security,
    Dependency,
    Installation,
    Platform,
    Backup,
    Update,
    Integrity,
    Network,
    Configuration,
    Resource,
    System,
    User,
    Maintenance,
    Internal,
}

impl fmt::Display for ErrorCategory {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ErrorCategory::Validation => write!(f, "Validation"),
            ErrorCategory::Security => write!(f, "Security"),
            ErrorCategory::Dependency => write!(f, "Dependency"),
            ErrorCategory::Installation => write!(f, "Installation"),
            ErrorCategory::Platform => write!(f, "Platform"),
            ErrorCategory::Backup => write!(f, "Backup"),
            ErrorCategory::Update => write!(f, "Update"),
            ErrorCategory::Integrity => write!(f, "Integrity"),
            ErrorCategory::Network => write!(f, "Network"),
            ErrorCategory::Configuration => write!(f, "Configuration"),
            ErrorCategory::Resource => write!(f, "Resource"),
            ErrorCategory::System => write!(f, "System"),
            ErrorCategory::User => write!(f, "User"),
            ErrorCategory::Maintenance => write!(f, "Maintenance"),
            ErrorCategory::Internal => write!(f, "Internal"),
        }
    }
}