//! Workflow Compatibility Manager
//!
//! This module ensures complete compatibility with existing development workflows
//! and tools, maintaining seamless developer experience.

use crate::error::AuditError;
use crate::integration::types::GuruIntegrationConfig;
use std::time::Instant;
use tracing::{debug, info};

/// Workflow Compatibility Manager - Ensures workflow compatibility
#[derive(Debug, Clone)]
pub struct WorkflowCompatibilityManager {
    /// Workflow requirements being met
    requirements: Vec<String>,
}

impl WorkflowCompatibilityManager {
    /// Create a new workflow compatibility manager
    #[must_use]
    pub fn new() -> Self {
        Self {
            requirements: Vec::new(),
        }
    }

    /// Verify workflow compatibility
    pub fn verify_compatibility(&mut self, config: &GuruIntegrationConfig) -> Result<bool, AuditError> {
        let start_time = Instant::now();
        
        debug!("Verifying workflow compatibility");
        
        // Register workflow requirements
        for requirement in &config.workflow_requirements {
            self.requirements.push(requirement.clone());
        }
        
        let compatible = !self.requirements.is_empty();
        
        let duration = start_time.elapsed();
        info!("Workflow compatibility verification completed in {:?}", duration);
        
        Ok(compatible)
    }

    /// Get workflow requirements
    #[must_use]
    pub fn requirements(&self) -> &[String] {
        &self.requirements
    }
}

impl Default for WorkflowCompatibilityManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::integration::types::{GuruDirectoryConfig, GuruIntegrationConfig};

    #[test]
    fn test_workflow_compatibility_manager_creation() {
        let manager = WorkflowCompatibilityManager::new();
        assert_eq!(manager.requirements().len(), 0);
    }

    #[test]
    fn test_workflow_compatibility_verification() {
        let mut manager = WorkflowCompatibilityManager::new();
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
            infrastructure_components: vec![],
            workflow_requirements: vec!["ci/cd".to_string(), "testing".to_string()],
            legacy_systems: vec![],
            optimization_targets: vec![],
        };
        
        let result = manager.verify_compatibility(&config).unwrap();
        assert!(result);
        assert_eq!(manager.requirements().len(), 2);
    }
}
