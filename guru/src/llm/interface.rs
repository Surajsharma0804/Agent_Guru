//! LLM Interface
//! Traits for Large Language Model interaction.

use crate::intelligence::tensor::Tensor;

#[derive(Debug, Clone)]
pub struct CompletionRequest {
    pub prompt: String,
    pub temperature: f32,
    pub max_tokens: usize,
    pub stop: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct CompletionResponse {
    pub text: String,
    pub usage: usize,
}

pub trait LLM: Send + Sync {
    // Basic completion
    fn complete(&self, request: CompletionRequest) -> CompletionResponse;
    
    // Embedding usually separate, but some LLMs offer it.
    // We strictly use EmbeddingModel trait for embeddings.
}
