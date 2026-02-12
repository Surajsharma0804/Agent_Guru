//! # OpenAI API Provider
//!
//! Production-grade OpenAI API integration with security boundaries.

use super::ChatMessage;
use serde::{Deserialize, Serialize};
use std::time::Duration;

/// OpenAI API client
pub struct OpenAiClient {
    api_key: String,
    model: String,
    base_url: String,
    client: reqwest::Client,
}

#[derive(Debug, Serialize)]
struct OpenAiRequest {
    model: String,
    messages: Vec<ChatMessage>,
    temperature: f32,
}

#[derive(Debug, Deserialize)]
struct OpenAiResponse {
    choices: Vec<OpenAiChoice>,
}

#[derive(Debug, Deserialize)]
struct OpenAiChoice {
    message: ChatMessage,
}

impl OpenAiClient {
    /// Create new OpenAI client
    pub fn new(api_key: String, model: String) -> Self {
        Self {
            api_key,
            model,
            base_url: "https://api.openai.com/v1".to_string(),
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(30))
                .build()
                .unwrap(),
        }
    }
    
    /// Send chat request
    pub async fn chat(&self, messages: Vec<ChatMessage>) -> Result<String, ProviderError> {
        let request = OpenAiRequest {
            model: self.model.clone(),
            messages,
            temperature: 0.7,
        };
        
        let response = self
            .client
            .post(format!("{}/chat/completions", self.base_url))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| ProviderError::RequestFailed(e.to_string()))?;
        
        if !response.status().is_success() {
            return Err(ProviderError::ApiError(format!(
                "OpenAI API error: {}",
                response.status()
            )));
        }
        
        let api_response: OpenAiResponse = response
            .json()
            .await
            .map_err(|e| ProviderError::ParseError(e.to_string()))?;
        
        api_response
            .choices
            .first()
            .map(|choice| choice.message.content.clone())
            .ok_or_else(|| ProviderError::EmptyResponse)
    }
    
    /// Check if API is available
    pub async fn is_available(&self) -> bool {
        self.client
            .get(format!("{}/models", self.base_url))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .send()
            .await
            .is_ok()
    }
}

/// Provider errors
#[derive(Debug, thiserror::Error)]
pub enum ProviderError {
    #[error("Request failed: {0}")]
    RequestFailed(String),
    
    #[error("API error: {0}")]
    ApiError(String),
    
    #[error("Parse error: {0}")]
    ParseError(String),
    
    #[error("Empty response from provider")]
    EmptyResponse,
    
    #[error("Provider unavailable")]
    Unavailable,
}
