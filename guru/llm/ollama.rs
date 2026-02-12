//! # Ollama LLM Integration
//!
//! Production-grade integration with local Ollama LLM server.

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Ollama client for local LLM inference
pub struct OllamaClient {
    base_url: String,
    model: String,
    client: reqwest::Client,
}

/// Chat message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

/// Chat request
#[derive(Debug, Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<ChatMessage>,
    stream: bool,
}

/// Chat response
#[derive(Debug, Deserialize)]
struct ChatResponse {
    message: ChatMessage,
    _done: bool,
}

impl OllamaClient {
    /// Create new Ollama client
    pub fn new(model: String) -> Self {
        Self {
            base_url: "http://localhost:11434".to_string(),
            model,
            client: reqwest::Client::builder()
                .timeout(Duration::from_secs(120))
                .build()
                .unwrap(),
        }
    }

    /// Send chat message and get response
    pub async fn chat(&self, messages: Vec<ChatMessage>) -> Result<String, OllamaError> {
        let request = ChatRequest {
            model: self.model.clone(),
            messages,
            stream: false,
        };

        let response = self
            .client
            .post(format!("{}/api/chat", self.base_url))
            .json(&request)
            .send()
            .await
            .map_err(|e| OllamaError::RequestFailed(e.to_string()))?;

        if !response.status().is_success() {
            return Err(OllamaError::ServerError(format!(
                "Status: {}",
                response.status()
            )));
        }

        let chat_response: ChatResponse = response
            .json()
            .await
            .map_err(|e| OllamaError::ParseError(e.to_string()))?;

        Ok(chat_response.message.content)
    }

    /// Check if Ollama is available
    pub async fn is_available(&self) -> bool {
        self.client
            .get(format!("{}/api/tags", self.base_url))
            .send()
            .await
            .is_ok()
    }

    /// List available models
    pub async fn list_models(&self) -> Result<Vec<String>, OllamaError> {
        #[derive(Deserialize)]
        struct TagsResponse {
            models: Vec<ModelInfo>,
        }

        #[derive(Deserialize)]
        struct ModelInfo {
            name: String,
        }

        let response = self
            .client
            .get(format!("{}/api/tags", self.base_url))
            .send()
            .await
            .map_err(|e| OllamaError::RequestFailed(e.to_string()))?;

        let tags: TagsResponse = response
            .json()
            .await
            .map_err(|e| OllamaError::ParseError(e.to_string()))?;

        Ok(tags.models.into_iter().map(|m| m.name).collect())
    }
}

/// Ollama errors
#[derive(Debug, thiserror::Error)]
pub enum OllamaError {
    #[error("Request failed: {0}")]
    RequestFailed(String),

    #[error("Server error: {0}")]
    ServerError(String),

    #[error("Parse error: {0}")]
    ParseError(String),

    #[error("Model not found: {0}")]
    ModelNotFound(String),
}
