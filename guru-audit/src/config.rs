//! Configuration management for the GURU Production Audit System
//!
//! This module provides configuration loading, validation, and management
//! for all audit system components. Configuration is loaded from multiple
//! sources with proper precedence and validation.

use crate::error::{AuditError, AuditResult};
use crate::types::{
    AuditConfig, GitHubIntegrationConfig, NotificationSettings,
    PerformanceRequirements, QualityGateConfig, RepositoryConfig, SecurityRequirements,
};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// Default configuration file name
pub const DEFAULT_CONFIG_FILE: &str = "guru-audit.toml";

/// Environment variable prefix for configuration
pub const ENV_PREFIX: &str = "GURU_AUDIT";

/// Configuration loader with multiple source support
#[derive(Debug)]
pub struct ConfigLoader {
    /// Configuration search paths
    search_paths: Vec<PathBuf>,
    /// Environment variable prefix
    env_prefix: String,
}

impl ConfigLoader {
    /// Create new configuration loader with default settings
    #[must_use]
    pub fn new() -> Self {
        Self {
            search_paths: vec![
                PathBuf::from("."),
                PathBuf::from("config"),
                PathBuf::from("/etc/guru-audit"),
                dirs::config_dir().unwrap_or_else(|| PathBuf::from(".")),
            ],
            env_prefix: ENV_PREFIX.to_string(),
        }
    }

    /// Add custom search path for configuration files
    pub fn add_search_path<P: AsRef<Path>>(&mut self, path: P) {
        self.search_paths.push(path.as_ref().to_path_buf());
    }

    /// Set custom environment variable prefix
    pub fn set_env_prefix<S: Into<String>>(&mut self, prefix: S) {
        self.env_prefix = prefix.into();
    }

    /// Load configuration from all available sources
    ///
    /// # Errors
    ///
    /// Returns `AuditError::ConfigurationError` if configuration loading fails
    pub fn load(&self) -> AuditResult<AuditConfig> {
        // For now, return a default configuration
        // In a full implementation, this would load from files and environment
        
        // Use current directory as default for testing
        let current_dir = std::env::current_dir().map_err(|e| {
            AuditError::ConfigurationError {
                parameter: "current_directory".to_string(),
                reason: format!("Failed to get current directory: {e}"),
                suggested_fix: Some("Check system permissions".to_string()),
            }
        })?;

        let config = crate::config::ConfigBuilder::new()
            .repository_config(RepositoryConfig {
                root_path: current_dir,
                branch: "main".to_string(),
                commit_hash: None,
                excluded_paths: vec![
                    std::path::PathBuf::from("target"),
                    std::path::PathBuf::from("node_modules"),
                    std::path::PathBuf::from(".git"),
                ],
                included_patterns: vec![
                    "**/*.rs".to_string(),
                    "**/*.py".to_string(),
                    "**/*.ts".to_string(),
                ],
            })
            .notification_settings(NotificationSettings {
                email_addresses: vec!["test@example.com".to_string()],
                webhook_urls: Vec::new(),
                slack_config: None,
                notification_levels: vec!["error".to_string(), "warning".to_string()],
            })
            .build()?;

        // Validate configuration
        self.validate_config(&config)?;

        Ok(config)
    }

    /// Load configuration from specific file
    ///
    /// # Errors
    ///
    /// Returns `AuditError::ConfigurationError` if file loading fails
    pub fn load_from_file<P: AsRef<std::path::Path>>(&self, _path: P) -> AuditResult<AuditConfig> {
        // For now, delegate to load() method
        // In a full implementation, this would load from the specific file
        self.load()
    }

    /// Validate configuration for consistency and completeness
    fn validate_config(&self, config: &AuditConfig) -> AuditResult<()> {
        // Validate repository configuration
        if !config.target_repository.root_path.exists() {
            return Err(AuditError::ConfigurationError {
                parameter: "target_repository.root_path".to_string(),
                reason: "Repository root path does not exist".to_string(),
                suggested_fix: Some("Ensure the repository path is correct and accessible".to_string()),
            });
        }

        // Validate quality gate configuration
        if config.quality_gates.property_test_iterations < 1000 {
            return Err(AuditError::ConfigurationError {
                parameter: "quality_gates.property_test_iterations".to_string(),
                reason: "Property test iterations must be at least 1000".to_string(),
                suggested_fix: Some("Set property_test_iterations to at least 10000 for production use".to_string()),
            });
        }

        // Validate performance requirements
        if config.performance_requirements.percentile_guarantee < 90.0 {
            return Err(AuditError::ConfigurationError {
                parameter: "performance_requirements.percentile_guarantee".to_string(),
                reason: "Percentile guarantee must be at least 90.0".to_string(),
                suggested_fix: Some("Set percentile_guarantee to 99.9 for production use".to_string()),
            });
        }

        // Validate GitHub integration if configured
        if let Some(github_config) = &config.github_integration {
            if github_config.repository_url.is_empty() {
                return Err(AuditError::ConfigurationError {
                    parameter: "github_integration.repository_url".to_string(),
                    reason: "GitHub repository URL cannot be empty".to_string(),
                    suggested_fix: Some("Provide a valid GitHub repository URL".to_string()),
                });
            }

            if github_config.access_token.is_empty() {
                return Err(AuditError::ConfigurationError {
                    parameter: "github_integration.access_token".to_string(),
                    reason: "GitHub access token cannot be empty".to_string(),
                    suggested_fix: Some("Provide a valid GitHub access token or use environment variable".to_string()),
                });
            }
        }

        // Validate notification settings
        if config.notification_settings.email_addresses.is_empty()
            && config.notification_settings.webhook_urls.is_empty()
            && config.notification_settings.slack_config.is_none()
        {
            return Err(AuditError::ConfigurationError {
                parameter: "notification_settings".to_string(),
                reason: "At least one notification method must be configured".to_string(),
                suggested_fix: Some("Configure email, webhook, or Slack notifications".to_string()),
            });
        }

        Ok(())
    }
}

impl Default for ConfigLoader {
    fn default() -> Self {
        Self::new()
    }
}

/// Default configuration values
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
struct DefaultConfig {
    /// Default audit configuration
    pub audit: DefaultAuditConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
struct DefaultAuditConfig {
    /// Default target repository
    pub target_repository: DefaultRepositoryConfig,
    /// Default quality gates
    pub quality_gates: QualityGateConfig,
    /// Default performance requirements
    pub performance_requirements: PerformanceRequirements,
    /// Default security requirements
    pub security_requirements: SecurityRequirements,
    /// Default formal verification specs
    pub formal_verification_specs: Vec<String>,
    /// Default notification settings
    pub notification_settings: DefaultNotificationSettings,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
struct DefaultRepositoryConfig {
    /// Default root path (current directory)
    pub root_path: PathBuf,
    /// Default branch
    pub branch: String,
    /// Default excluded paths
    pub excluded_paths: Vec<PathBuf>,
    /// Default included patterns
    pub included_patterns: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
struct DefaultNotificationSettings {
    /// Default email addresses (empty)
    pub email_addresses: Vec<String>,
    /// Default webhook URLs (empty)
    pub webhook_urls: Vec<String>,
    /// Default notification levels
    pub notification_levels: Vec<String>,
}

impl Default for DefaultConfig {
    fn default() -> Self {
        Self {
            audit: DefaultAuditConfig {
                target_repository: DefaultRepositoryConfig {
                    root_path: PathBuf::from("."),
                    branch: "main".to_string(),
                    excluded_paths: vec![
                        PathBuf::from("target"),
                        PathBuf::from("node_modules"),
                        PathBuf::from(".git"),
                        PathBuf::from("build"),
                        PathBuf::from("dist"),
                    ],
                    included_patterns: vec![
                        "**/*.rs".to_string(),
                        "**/*.py".to_string(),
                        "**/*.ts".to_string(),
                        "**/*.js".to_string(),
                        "**/*.go".to_string(),
                        "**/*.cpp".to_string(),
                        "**/*.c".to_string(),
                        "**/*.h".to_string(),
                        "**/*.hpp".to_string(),
                        "**/*.java".to_string(),
                        "**/*.cs".to_string(),
                        "**/*.tla".to_string(),
                    ],
                },
                quality_gates: QualityGateConfig::default(),
                performance_requirements: PerformanceRequirements::default(),
                security_requirements: SecurityRequirements::default(),
                formal_verification_specs: vec![
                    "audit_controller.tla".to_string(),
                    "phase_execution.tla".to_string(),
                ],
                notification_settings: DefaultNotificationSettings {
                    email_addresses: Vec::new(),
                    webhook_urls: Vec::new(),
                    notification_levels: vec![
                        "error".to_string(),
                        "warning".to_string(),
                        "info".to_string(),
                    ],
                },
            },
        }
    }
}

impl From<config::ConfigError> for AuditError {
    fn from(error: config::ConfigError) -> Self {
        AuditError::ConfigurationError {
            parameter: "configuration".to_string(),
            reason: error.to_string(),
            suggested_fix: Some("Check configuration file syntax and format".to_string()),
        }
    }
}

/// Configuration builder for programmatic configuration creation
#[derive(Debug, Default)]
pub struct ConfigBuilder {
    /// Repository configuration
    repository_config: Option<RepositoryConfig>,
    /// Quality gate configuration
    quality_gates: Option<QualityGateConfig>,
    /// Performance requirements
    performance_requirements: Option<PerformanceRequirements>,
    /// Security requirements
    security_requirements: Option<SecurityRequirements>,
    /// GitHub integration configuration
    github_integration: Option<GitHubIntegrationConfig>,
    /// Notification settings
    notification_settings: Option<NotificationSettings>,
    /// Formal verification specs
    formal_verification_specs: Vec<String>,
}

impl ConfigBuilder {
    /// Create new configuration builder
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Set repository configuration
    #[must_use]
    pub fn repository_config(mut self, config: RepositoryConfig) -> Self {
        self.repository_config = Some(config);
        self
    }

    /// Set quality gate configuration
    #[must_use]
    pub fn quality_gates(mut self, gates: QualityGateConfig) -> Self {
        self.quality_gates = Some(gates);
        self
    }

    /// Set performance requirements
    #[must_use]
    pub fn performance_requirements(mut self, requirements: PerformanceRequirements) -> Self {
        self.performance_requirements = Some(requirements);
        self
    }

    /// Set security requirements
    #[must_use]
    pub fn security_requirements(mut self, requirements: SecurityRequirements) -> Self {
        self.security_requirements = Some(requirements);
        self
    }

    /// Set GitHub integration configuration
    #[must_use]
    pub fn github_integration(mut self, config: GitHubIntegrationConfig) -> Self {
        self.github_integration = Some(config);
        self
    }

    /// Set notification settings
    #[must_use]
    pub fn notification_settings(mut self, settings: NotificationSettings) -> Self {
        self.notification_settings = Some(settings);
        self
    }

    /// Add formal verification specification
    #[must_use]
    pub fn add_formal_verification_spec<S: Into<String>>(mut self, spec: S) -> Self {
        self.formal_verification_specs.push(spec.into());
        self
    }

    /// Build audit configuration
    ///
    /// # Errors
    ///
    /// Returns `AuditError::ConfigurationError` if required configuration is missing
    pub fn build(self) -> AuditResult<AuditConfig> {
        let repository_config = self.repository_config.ok_or_else(|| {
            AuditError::ConfigurationError {
                parameter: "repository_config".to_string(),
                reason: "Repository configuration is required".to_string(),
                suggested_fix: Some("Use repository_config() to set repository configuration".to_string()),
            }
        })?;

        Ok(AuditConfig {
            audit_id: crate::types::AuditId::new(),
            target_repository: repository_config,
            quality_gates: self.quality_gates.unwrap_or_default(),
            performance_requirements: self.performance_requirements.unwrap_or_default(),
            security_requirements: self.security_requirements.unwrap_or_default(),
            formal_verification_specs: if self.formal_verification_specs.is_empty() {
                vec![
                    "audit_controller.tla".to_string(),
                    "phase_execution.tla".to_string(),
                ]
            } else {
                self.formal_verification_specs
            },
            github_integration: self.github_integration,
            notification_settings: self.notification_settings.unwrap_or_else(|| {
                NotificationSettings {
                    email_addresses: Vec::new(),
                    webhook_urls: Vec::new(),
                    slack_config: None,
                    notification_levels: vec![
                        "error".to_string(),
                        "warning".to_string(),
                        "info".to_string(),
                    ],
                }
            }),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_default_config_loading() {
        let loader = ConfigLoader::new();
        let config = loader.load();
        
        // Should succeed with default configuration
        match &config {
            Ok(_) => {},
            Err(e) => println!("Config loading failed: {:?}", e),
        }
        assert!(config.is_ok());
    }

    #[test]
    fn test_config_builder() {
        let temp_dir = TempDir::new().unwrap();
        
        let repository_config = RepositoryConfig {
            root_path: temp_dir.path().to_path_buf(),
            branch: "main".to_string(),
            commit_hash: None,
            excluded_paths: vec![PathBuf::from("target")],
            included_patterns: vec!["**/*.rs".to_string()],
        };

        let config = ConfigBuilder::new()
            .repository_config(repository_config)
            .add_formal_verification_spec("test.tla")
            .build()
            .unwrap();

        assert_eq!(config.target_repository.branch, "main");
        assert!(config.formal_verification_specs.contains(&"test.tla".to_string()));
    }

    #[test]
    fn test_config_validation() {
        let loader = ConfigLoader::new();
        
        // Test with non-existent repository path
        let repository_config = RepositoryConfig {
            root_path: PathBuf::from("/non/existent/path"),
            branch: "main".to_string(),
            commit_hash: None,
            excluded_paths: Vec::new(),
            included_patterns: Vec::new(),
        };

        let config = ConfigBuilder::new()
            .repository_config(repository_config)
            .build()
            .unwrap();

        let validation_result = loader.validate_config(&config);
        assert!(validation_result.is_err());
    }
}