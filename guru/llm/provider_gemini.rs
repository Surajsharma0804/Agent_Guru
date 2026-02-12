//! # Google Gemini API Provider
//!
//! Production-grade Gemini API integration with security boundaries.

use super::ChatMessage;
use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Gemini API client
pub struct GeminiClient {
    api_key: String,
    model: String,
    base_url: String,
    client: reqwest::Client,
}

#[derive(Debug, Serialize)]
struct GeminiRequest {
    contents: Vec<GeminiContent>,
}

#[derive(Debug, Serialize)]
struct GeminiContent {
    role: String,
    parts: Vec<GeminiPart>,
}

#[derive(Debug, Serialize)]
struct GeminiPart {
    text: String,
}

#[derive(Debug, Deserialize)]
struct GeminiResponse {
    candidates: Vec<GeminiCandidate>,
}

#[derive(Debug, Deserialize)]
struct GeminiCandidate {
    content: GeminiContentResponse,
}

#[derive(Debug, Deserialize)]
struct GeminiContentResponse {
    parts: Vec<GeminiPartResponse>,
}

#[derive(Debug, Deserialize)]
struct GeminiPartResponse {
    text: String,
}

impl GeminiClient {
    /// Create new Gemini client
    pub fn new(api_key: String, model: String) -> Self {
        Self {
            api_key,
            model,
            base_url: "https://generativelanguage.googleapis.com/v1beta".to_string(),
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(30))
                .build()
                .unwrap(),
        }
    }
    
    /// Send chat request
    pub async fn chat(&self, messages: Vec<ChatMessage>) -> Result<String, ProviderError> {
        let contents: Vec<GeminiContent> = messages
            .into_iter()
            .map(|msg| GeminiContent {
                role: if msg.role == "assistant" {
                    "model".to_string()
                } else {
                    msg.role
                },
                parts: vec![GeminiPart { text: msg.content }],
            })
            .collect();
        
        let request = GeminiRequest { contents };
        
        let url = format!(
            "{}/models/{}:generateContent?key={}",
            self.base_url, self.model, self.api_key
        );
        
        let response = self
            .client
            .post(&url)
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| ProviderError::RequestFailed(e.to_string()))?;
        
        if !response.status().is_success() {
            return Err(ProviderError::ApiError(format!(
                "Gemini API error: {}",
                response.status()
            )));
        }
        
        let api_response: GeminiResponse = response
            .json()
            .await
            .map_err(|e| ProviderError::ParseError(e.to_string()))?;
        
        api_response
            .candidates
            .first()
            .and_then(|c| c.content.parts.first())
            .map(|p| p.text.clone())
            .ok_or_else(|| ProviderError::EmptyResponse)
    }
    
    /// Check if API is available
    pub async fn is_available(&self) -> bool {
        let url = format!(
            "{}/models?key={}",
            self.base_url, self.api_key
        );
        
        self.client
            .get(&url)
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
