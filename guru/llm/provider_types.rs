//! # LLM Provider Type Definitions
//!
//! Core types for multi-provider LLM system with strict security boundaries.

use serde::{Deserialize, Serialize};

/// LLM provider type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ProviderType {
    /// Local Ollama models
    Ollama,
    /// OpenAI API
    OpenAI,
    /// Google Gemini API
    Gemini,
    /// Provider disabled
    Disabled,
}

/// Task type for model routing
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskType {
    /// Extract user intent from natural language
    IntentExtraction,
    /// Structure intent into JSON format
    IntentStructuring,
    /// Deep reasoning for complex queries
    DeepReasoning,
    /// Language assistance (non-executing)
    LanguageHelp,
}

/// Runtime mode for LLM system
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RuntimeMode {
    /// Local models only
    Local,
    /// API providers only
    Api,
    /// Hybrid local + API
    Hybrid,
}

/// Provider configuration for a specific task
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskProviderConfig {
    pub provider: ProviderType,
    pub model: String,
    #[serde(default)]
    pub fallback_provider: Option<ProviderType>,
    #[serde(default)]
    pub fallback_model: Option<String>,
}

/// Complete LLM runtime configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmRuntimeConfig {
    pub mode: RuntimeMode,
    pub default_provider: ProviderType,
    pub tasks: std::collections::HashMap<TaskType, TaskProviderConfig>,
    #[serde(default)]
    pub require_user_confirmation_for_api: bool,
    #[serde(default)]
    pub log_metadata_only: bool,
}

impl Default for LlmRuntimeConfig {
    fn default() -> Self {
        let mut tasks = std::collections::HashMap::new();
        
        tasks.insert(
            TaskType::IntentExtraction,
            TaskProviderConfig {
                provider: ProviderType::Ollama,
                model: "qwen2.5:7b-instruct".to_string(),
                fallback_provider: None,
                fallback_model: None,
            },
        );
        
        tasks.insert(
            TaskType::IntentStructuring,
            TaskProviderConfig {
                provider: ProviderType::Ollama,
                model: "mistral:7b-instruct".to_string(),
                fallback_provider: None,
                fallback_model: None,
            },
        );
        
        tasks.insert(
            TaskType::DeepReasoning,
            TaskProviderConfig {
                provider: ProviderType::Disabled,
                model: String::new(),
                fallback_provider: None,
                fallback_model: None,
            },
        );
        
        tasks.insert(
            TaskType::LanguageHelp,
            TaskProviderConfig {
                provider: ProviderType::Ollama,
                model: "qwen2.5:14b-instruct".to_string(),
                fallback_provider: None,
                fallback_model: None,
            },
        );
        
        Self {
            mode: RuntimeMode::Local,
            default_provider: ProviderType::Ollama,
            tasks,
            require_user_confirmation_for_api: true,
            log_metadata_only: true,
        }
    }
}

/// API credentials (never logged, never stored in code)
#[derive(Clone)]
pub struct ApiCredentials {
    pub openai_key: Option<String>,
    pub gemini_key: Option<String>,
}

impl ApiCredentials {
    /// Load from environment variables
    pub fn from_env() -> Self {
        Self {
            openai_key: std::env::var("OPENAI_API_KEY").ok(),
            gemini_key: std::env::var("GEMINI_API_KEY").ok(),
        }
    }
    
    /// Check if credentials exist for provider
    pub fn has_credentials_for(&self, provider: ProviderType) -> bool {
        match provider {
            ProviderType::OpenAI => self.openai_key.is_some(),
            ProviderType::Gemini => self.gemini_key.is_some(),
            ProviderType::Ollama => true,
            ProviderType::Disabled => false,
        }
    }
}

impl std::fmt::Debug for ApiCredentials {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ApiCredentials")
            .field("openai_key", &self.openai_key.as_ref().map(|_| "[REDACTED]"))
            .field("gemini_key", &self.gemini_key.as_ref().map(|_| "[REDACTED]"))
            .finish()
    }
}
