//! # Unified LLM Provider
//!
//! Production-grade multi-provider router with strict security boundaries.
//! Routes requests to appropriate providers based on configuration.

use super::audit_logger::{AuditLogEntry, AuditLogger};
use super::ollama::{OllamaClient, OllamaError};
use super::provider_gemini::GeminiClient;
use super::provider_openai::OpenAiClient;
use super::provider_types::{
    ApiCredentials, LlmRuntimeConfig, ProviderType, TaskType,
};
use super::ChatMessage;
use chrono::Utc;
use std::time::Instant;

/// Unified provider that routes to appropriate backend
pub struct UnifiedProvider {
    config: LlmRuntimeConfig,
    credentials: ApiCredentials,
    ollama_clients: std::collections::HashMap<String, OllamaClient>,
    openai_clients: std::collections::HashMap<String, OpenAiClient>,
    gemini_clients: std::collections::HashMap<String, GeminiClient>,
    audit_logger: AuditLogger,
    api_confirmed: bool,
}

/// Response from unified provider
#[derive(Debug)]
pub struct ProviderResponse {
    pub content: String,
    pub provider: ProviderType,
    pub model: String,
    pub latency_ms: u64,
    pub fallback_used: bool,
}

impl UnifiedProvider {
    /// Create new unified provider
    pub fn new(
        config: LlmRuntimeConfig,
        credentials: ApiCredentials,
        audit_log_path: std::path::PathBuf,
    ) -> Result<Self, UnifiedProviderError> {
        // Validate configuration
        Self::validate_config(&config, &credentials)?;
        
        Ok(Self {
            config,
            credentials,
            ollama_clients: std::collections::HashMap::new(),
            openai_clients: std::collections::HashMap::new(),
            gemini_clients: std::collections::HashMap::new(),
            audit_logger: AuditLogger::new(audit_log_path),
            api_confirmed: false,
        })
    }
    
    /// Validate configuration against available credentials
    fn validate_config(
        config: &LlmRuntimeConfig,
        credentials: &ApiCredentials,
    ) -> Result<(), UnifiedProviderError> {
        for (task_type, task_config) in &config.tasks {
            if task_config.provider == ProviderType::Disabled {
                continue;
            }
            
            if matches!(
                task_config.provider,
                ProviderType::OpenAI | ProviderType::Gemini
            ) && !credentials.has_credentials_for(task_config.provider)
            {
                return Err(UnifiedProviderError::MissingCredentials(format!(
                    "Task {:?} requires {:?} but credentials not found",
                    task_type, task_config.provider
                )));
            }
        }
        
        Ok(())
    }
    
    /// Confirm API usage (required before first API call)
    pub fn confirm_api_usage(&mut self) {
        self.api_confirmed = true;
    }
    
    /// Execute task with appropriate provider
    pub async fn execute_task(
        &mut self,
        task_type: TaskType,
        messages: Vec<ChatMessage>,
    ) -> Result<ProviderResponse, UnifiedProviderError> {
        let start = Instant::now();
        
        // Get task configuration and clone needed values
        let task_config = self
            .config
            .tasks
            .get(&task_type)
            .ok_or_else(|| UnifiedProviderError::TaskNotConfigured(format!("{:?}", task_type)))?;
        
        let provider = task_config.provider;
        let model = task_config.model.clone();
        let fallback_provider = task_config.fallback_provider;
        let fallback_model = task_config.fallback_model.clone();
        
        // Check if provider is disabled
        if provider == ProviderType::Disabled {
            return Err(UnifiedProviderError::ProviderDisabled(format!(
                "{:?}",
                task_type
            )));
        }
        
        // Check API confirmation requirement
        if matches!(
            provider,
            ProviderType::OpenAI | ProviderType::Gemini
        ) && self.config.require_user_confirmation_for_api
            && !self.api_confirmed
        {
            return Err(UnifiedProviderError::ApiNotConfirmed);
        }
        
        // Try primary provider
        let result = self
            .execute_with_provider(
                provider,
                &model,
                messages.clone(),
            )
            .await;
        
        let (content, final_provider, final_model, fallback_used) = match result {
            Ok(content) => (content, provider, model, false),
            Err(e) => {
                // Try fallback if configured
                if let (Some(fb_provider), Some(fb_model)) = (fallback_provider, fallback_model.as_ref()) {
                    let fallback_result = self
                        .execute_with_provider(fb_provider, fb_model, messages)
                        .await;
                    
                    match fallback_result {
                        Ok(content) => (content, fb_provider, fb_model.clone(), true),
                        Err(fallback_err) => {
                            self.log_failure(task_type, provider, &model, start, false, &fallback_err);
                            return Err(fallback_err);
                        }
                    }
                } else {
                    self.log_failure(task_type, provider, &model, start, false, &e);
                    return Err(e);
                }
            }
        };
        
        let latency_ms = start.elapsed().as_millis() as u64;
        
        // Log success
        self.log_success(task_type, final_provider, &final_model, latency_ms, fallback_used);
        
        Ok(ProviderResponse {
            content,
            provider: final_provider,
            model: final_model,
            latency_ms,
            fallback_used,
        })
    }
    
    /// Execute with specific provider
    async fn execute_with_provider(
        &mut self,
        provider: ProviderType,
        model: &str,
        messages: Vec<ChatMessage>,
    ) -> Result<String, UnifiedProviderError> {
        match provider {
            ProviderType::Ollama => {
                let client = self
                    .ollama_clients
                    .entry(model.to_string())
                    .or_insert_with(|| OllamaClient::new(model.to_string()));
                
                client
                    .chat(messages)
                    .await
                    .map_err(UnifiedProviderError::OllamaError)
            }
            ProviderType::OpenAI => {
                let api_key = self
                    .credentials
                    .openai_key
                    .as_ref()
                    .ok_or(UnifiedProviderError::MissingCredentials(
                        "OpenAI API key not found".to_string(),
                    ))?
                    .clone();
                
                let client = self
                    .openai_clients
                    .entry(model.to_string())
                    .or_insert_with(|| OpenAiClient::new(api_key, model.to_string()));
                
                client
                    .chat(messages)
                    .await
                    .map_err(|e| UnifiedProviderError::ProviderError(e.to_string()))
            }
            ProviderType::Gemini => {
                let api_key = self
                    .credentials
                    .gemini_key
                    .as_ref()
                    .ok_or(UnifiedProviderError::MissingCredentials(
                        "Gemini API key not found".to_string(),
                    ))?
                    .clone();
                
                let client = self
                    .gemini_clients
                    .entry(model.to_string())
                    .or_insert_with(|| GeminiClient::new(api_key, model.to_string()));
                
                client
                    .chat(messages)
                    .await
                    .map_err(|e| UnifiedProviderError::ProviderError(e.to_string()))
            }
            ProviderType::Disabled => Err(UnifiedProviderError::ProviderDisabled(
                "Provider is disabled".to_string(),
            )),
        }
    }
    
    /// Log successful operation
    fn log_success(
        &self,
        task_type: TaskType,
        provider: ProviderType,
        model: &str,
        latency_ms: u64,
        fallback_used: bool,
    ) {
        let entry = AuditLogEntry {
            timestamp: Utc::now(),
            task_type,
            provider,
            model_name: model.to_string(),
            success: true,
            latency_ms,
            fallback_used,
            error_type: None,
        };
        
        let _ = self.audit_logger.log_operation(entry);
    }
    
    /// Log failed operation
    fn log_failure(
        &self,
        task_type: TaskType,
        provider: ProviderType,
        model: &str,
        start: Instant,
        fallback_used: bool,
        error: &UnifiedProviderError,
    ) {
        let entry = AuditLogEntry {
            timestamp: Utc::now(),
            task_type,
            provider,
            model_name: model.to_string(),
            success: false,
            latency_ms: start.elapsed().as_millis() as u64,
            fallback_used,
            error_type: Some(format!("{:?}", error)),
        };
        
        let _ = self.audit_logger.log_operation(entry);
    }
    
    /// Get audit statistics
    pub fn get_audit_statistics(&self) -> Result<super::audit_logger::AuditStatistics, super::audit_logger::AuditError> {
        self.audit_logger.get_statistics()
    }
    
    /// Check provider availability
    pub async fn check_provider_availability(
        &self,
        provider: ProviderType,
    ) -> bool {
        match provider {
            ProviderType::Ollama => {
                let client = OllamaClient::new("test".to_string());
                client.is_available().await
            }
            ProviderType::OpenAI => {
                if let Some(api_key) = &self.credentials.openai_key {
                    let client = OpenAiClient::new(api_key.clone(), "gpt-3.5-turbo".to_string());
                    client.is_available().await
                } else {
                    false
                }
            }
            ProviderType::Gemini => {
                if let Some(api_key) = &self.credentials.gemini_key {
                    let client = GeminiClient::new(api_key.clone(), "gemini-pro".to_string());
                    client.is_available().await
                } else {
                    false
                }
            }
            ProviderType::Disabled => false,
        }
    }
    
    /// Get current configuration
    pub fn config(&self) -> &LlmRuntimeConfig {
        &self.config
    }
    
    /// Update configuration (requires validation)
    pub fn update_config(&mut self, new_config: LlmRuntimeConfig) -> Result<(), UnifiedProviderError> {
        Self::validate_config(&new_config, &self.credentials)?;
        self.config = new_config;
        self.api_confirmed = false; // Reset confirmation on config change
        Ok(())
    }
}

/// Unified provider errors
#[derive(Debug, thiserror::Error)]
pub enum UnifiedProviderError {
    #[error("Ollama error: {0}")]
    OllamaError(#[from] OllamaError),
    
    #[error("Provider error: {0}")]
    ProviderError(String),
    
    #[error("Task not configured: {0}")]
    TaskNotConfigured(String),
    
    #[error("Provider disabled: {0}")]
    ProviderDisabled(String),
    
    #[error("Missing credentials: {0}")]
    MissingCredentials(String),
    
    #[error("API usage not confirmed by user")]
    ApiNotConfirmed,
    
    #[error("Configuration error: {0}")]
    ConfigurationError(String),
}
