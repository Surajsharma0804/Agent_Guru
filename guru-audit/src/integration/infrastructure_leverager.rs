//! Infrastructure Leverager
//!
//! This module implements optimal utilization of existing GURU infrastructure components
//! including observability, security, and other shared services.

use crate::error::AuditError;
use crate::integration::types::GuruIntegrationConfig;
use std::time::Instant;
use tracing::{debug, info};

/// Infrastructure Leverager - Optimizes utilization of existing GURU infrastructure
#[derive(Debug, Clone)]
pub struct InfrastructureLeverager {
    /// Infrastructure components being utilized
    components: Vec<String>,
}

impl InfrastructureLeverager {
    /// Create a new infrastructure leverager
    #[must_use]
    pub fn new() -> Self {
        Self {
            components: Vec::new(),
        }
    }

    /// Leverage existing infrastructure components
    pub fn leverage_infrastructure(&mut self, config: &GuruIntegrationConfig) -> Result<bool, AuditError> {
        let start_time = Instant::now();
        
        debug!("Leveraging existing GURU infrastructure components");
        
        // Register infrastructure components
        for component in &config.infrastructure_components {
            self.components.push(component.clone());
        }
        
        // Verify no duplication
        let unique_count = self.components.iter().collect::<std::collections::HashSet<_>>().len();
        let no_duplication = unique_count == self.components.len();
        
        let duration = start_time.elapsed();
        info!("Infrastructure leveraging completed in {:?}, components: {}", duration, self.components.len());
        
        Ok(no_duplication)
    }

    /// Get leveraged components
    #[must_use]
    pub fn components(&self) -> &[String] {
        &self.components
    }
}

impl Default for InfrastructureLeverager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::integration::types::{GuruDirectoryConfig, GuruIntegrationConfig};

    #[test]
    fn test_infrastructure_leverager_creation() {
        let leverager = InfrastructureLeverager::new();
        assert_eq!(leverager.components().len(), 0);
    }

    #[test]
    fn test_infrastructure_leveraging() {
        let mut leverager = InfrastructureLeverager::new();
        let config = GuruIntegrationConfig {
            directory_config: GuruDirectoryConfig {
                guru_root: "guru".to_string(),
                formal_dir: "guru/formal".to_string(),
                observability_dir: "guru/observability".to_string(),
                security_dir: "guru/security".to_string(),
                tests_dir: "tests".to_string(),
                build_dir: "guru/build".to_string(),
                policy_dir: "guru/policy".to_string(),
                supply_chain_dir: "guru/supply_chain".to_string(),
                platform_dir: "guru/platform".to_string(),
            },
            infrastructure_components: vec!["observability".to_string(), "security".to_string()],
            workflow_requirements: vec![],
            legacy_systems: vec![],
            optimization_targets: vec![],
        };
        
        let result = leverager.leverage_infrastructure(&config).unwrap();
        assert!(result);
        assert_eq!(leverager.components().len(), 2);
    }
}
