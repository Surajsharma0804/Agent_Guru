//! # LLM Configuration Loader
//!
//! Loads and validates LLM runtime configuration from YAML files.

use super::provider_types::LlmRuntimeConfig;
use std::path::Path;

/// Load configuration from YAML file
pub fn load_config<P: AsRef<Path>>(path: P) -> Result<LlmRuntimeConfig, ConfigError> {
    let content = std::fs::read_to_string(path.as_ref())
        .map_err(|e| ConfigError::IoError(e.to_string()))?;
    
    let config: ConfigFile = serde_yaml::from_str(&content)
        .map_err(|e| ConfigError::ParseError(e.to_string()))?;
    
    Ok(config.llm)
}

/// Load configuration with fallback to default
pub fn load_config_or_default<P: AsRef<Path>>(path: P) -> LlmRuntimeConfig {
    load_config(path).unwrap_or_default()
}

#[derive(Debug, serde::Deserialize)]
struct ConfigFile {
    llm: LlmRuntimeConfig,
}

/// Configuration errors
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("IO error: {0}")]
    IoError(String),
    
    #[error("Parse error: {0}")]
    ParseError(String),
}
