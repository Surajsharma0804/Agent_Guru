//! Legacy System Bridge
//!
//! This module provides backward compatibility and migration support for legacy
//! GURU systems and components.

use crate::error::AuditError;
use crate::integration::types::GuruIntegrationConfig;
use std::time::Instant;
use tracing::{debug, info};

/// Legacy System Bridge - Provides backward compatibility
#[derive(Debug, Clone)]
pub struct LegacySystemBridge {
    /// Legacy systems being supported
    legacy_systems: Vec<String>,
}

impl LegacySystemBridge {
    /// Create a new legacy system bridge
    #[must_use]
    pub fn new() -> Self {
        Self {
            legacy_systems: Vec::new(),
        }
    }

    /// Bridge legacy systems
    pub fn bridge_legacy_systems(&mut self, config: &GuruIntegrationConfig) -> Result<bool, AuditError> {
        let start_time = Instant::now();
        
        debug!("Bridging legacy systems");
        
        // Register legacy systems
        for system in &config.legacy_systems {
            self.legacy_systems.push(system.clone());
        }
        
        // Legacy systems are optional, so always return true
        let bridged = true;
        
        let duration = start_time.elapsed();
        info!("Legacy system bridging completed in {:?}, systems: {}", duration, self.legacy_systems.len());
        
        Ok(bridged)
    }

    /// Get legacy systems
    #[must_use]
    pub fn legacy_systems(&self) -> &[String] {
        &self.legacy_systems
    }
}

impl Default for LegacySystemBridge {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::integration::types::{GuruDirectoryConfig, GuruIntegrationConfig};

    #[test]
    fn test_legacy_system_bridge_creation() {
        let bridge = LegacySystemBridge::new();
        assert_eq!(bridge.legacy_systems().len(), 0);
    }

    #[test]
    fn test_legacy_system_bridging() {
        let mut bridge = LegacySystemBridge::new();
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
            workflow_requirements: vec![],
            legacy_systems: vec!["legacy-v1".to_string()],
            optimization_targets: vec![],
        };
        
        let result = bridge.bridge_legacy_systems(&config).unwrap();
        assert!(result);
        assert_eq!(bridge.legacy_systems().len(), 1);
    }
}
