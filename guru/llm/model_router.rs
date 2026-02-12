//! # Multi-Model Routing System
//!
//! Production-grade intelligent model selection for optimal performance and quality.
//! Routes queries to appropriate models based on complexity, latency requirements, and context.

use super::{ChatMessage, OllamaClient, OllamaError};
use std::time::{Duration, Instant};

/// Model tier for routing decisions
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ModelTier {
    /// Fast model for simple queries (≤ 200ms target)
    Fast,
    /// Balanced model for general use
    Balanced,
    /// Large model for complex reasoning
    Complex,
}

/// Query complexity classification
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QueryComplexity {
    Simple,
    Moderate,
    Complex,
}

/// Model configuration
#[derive(Debug, Clone)]
pub struct ModelConfig {
    pub name: String,
    pub tier: ModelTier,
    pub max_latency_ms: u64,
    pub context_window: usize,
}

/// Multi-model router with intelligent selection
pub struct ModelRouter {
    fast_model: OllamaClient,
    balanced_model: OllamaClient,
    complex_model: OllamaClient,
    fast_config: ModelConfig,
    balanced_config: ModelConfig,
    complex_config: ModelConfig,
    performance_metrics: PerformanceMetrics,
}

/// Performance tracking
#[derive(Debug, Clone)]
struct PerformanceMetrics {
    fast_avg_latency_ms: f64,
    balanced_avg_latency_ms: f64,
    complex_avg_latency_ms: f64,
    fast_query_count: u64,
    balanced_query_count: u64,
    complex_query_count: u64,
}

impl ModelRouter {
    /// Create new model router with available models
    pub fn new(
        fast_model: String,
        balanced_model: String,
        complex_model: String,
    ) -> Self {
        Self {
            fast_model: OllamaClient::new(fast_model.clone()),
            balanced_model: OllamaClient::new(balanced_model.clone()),
            complex_model: OllamaClient::new(complex_model.clone()),
            fast_config: ModelConfig {
                name: fast_model,
                tier: ModelTier::Fast,
                max_latency_ms: 200,
                context_window: 8192,
            },
            balanced_config: ModelConfig {
                name: balanced_model,
                tier: ModelTier::Balanced,
                max_latency_ms: 500,
                context_window: 32768,
            },
            complex_config: ModelConfig {
                name: complex_model,
                tier: ModelTier::Complex,
                max_latency_ms: 2000,
                context_window: 131072,
            },
            performance_metrics: PerformanceMetrics {
                fast_avg_latency_ms: 0.0,
                balanced_avg_latency_ms: 0.0,
                complex_avg_latency_ms: 0.0,
                fast_query_count: 0,
                balanced_query_count: 0,
                complex_query_count: 0,
            },
        }
    }

    /// Route query to appropriate model and get response
    pub async fn chat(&mut self, messages: Vec<ChatMessage>) -> Result<RouterResponse, OllamaError> {
        let complexity = self.classify_complexity(&messages);
        let tier = self.select_tier(complexity, &messages);
        
        let start = Instant::now();
        let (client, config) = self.get_client_for_tier(tier);
        
        // Clone model name before async call to avoid borrow issues
        let model_name = config.name.clone();
        
        let response = client.chat(messages.clone()).await?;
        let latency = start.elapsed();
        
        self.update_metrics(tier, latency);
        
        Ok(RouterResponse {
            content: response,
            model_used: model_name,
            tier_used: tier,
            latency,
            complexity,
        })
    }

    /// Classify query complexity
    fn classify_complexity(&self, messages: &[ChatMessage]) -> QueryComplexity {
        if messages.is_empty() {
            return QueryComplexity::Simple;
        }

        let last_message = &messages[messages.len() - 1];
        let content = &last_message.content;
        let word_count = content.split_whitespace().count();
        
        // Complexity indicators
        let has_code = content.contains("```") || content.contains("fn ") || content.contains("class ");
        let has_math = content.contains("calculate") || content.contains("equation") || content.contains("formula");
        let has_reasoning = content.contains("explain") || content.contains("why") || content.contains("how does");
        let has_multi_step = content.contains("first") && content.contains("then") || content.contains("step");
        let long_context = messages.len() > 10;
        
        // Classification logic
        if word_count < 10 && !has_code && !has_math && !has_reasoning {
            QueryComplexity::Simple
        } else if has_code || has_math || has_multi_step || long_context {
            QueryComplexity::Complex
        } else if has_reasoning || word_count > 50 {
            QueryComplexity::Moderate
        } else {
            QueryComplexity::Simple
        }
    }

    /// Select appropriate model tier
    fn select_tier(&self, complexity: QueryComplexity, messages: &[ChatMessage]) -> ModelTier {
        let context_size: usize = messages.iter()
            .map(|m| m.content.len())
            .sum();
        
        match complexity {
            QueryComplexity::Simple => {
                if context_size < 2000 {
                    ModelTier::Fast
                } else {
                    ModelTier::Balanced
                }
            }
            QueryComplexity::Moderate => ModelTier::Balanced,
            QueryComplexity::Complex => ModelTier::Complex,
        }
    }

    /// Get client and config for tier
    fn get_client_for_tier(&self, tier: ModelTier) -> (&OllamaClient, &ModelConfig) {
        match tier {
            ModelTier::Fast => (&self.fast_model, &self.fast_config),
            ModelTier::Balanced => (&self.balanced_model, &self.balanced_config),
            ModelTier::Complex => (&self.complex_model, &self.complex_config),
        }
    }

    /// Update performance metrics
    fn update_metrics(&mut self, tier: ModelTier, latency: Duration) {
        let latency_ms = latency.as_millis() as f64;
        
        match tier {
            ModelTier::Fast => {
                self.performance_metrics.fast_query_count += 1;
                let count = self.performance_metrics.fast_query_count as f64;
                self.performance_metrics.fast_avg_latency_ms = 
                    (self.performance_metrics.fast_avg_latency_ms * (count - 1.0) + latency_ms) / count;
            }
            ModelTier::Balanced => {
                self.performance_metrics.balanced_query_count += 1;
                let count = self.performance_metrics.balanced_query_count as f64;
                self.performance_metrics.balanced_avg_latency_ms = 
                    (self.performance_metrics.balanced_avg_latency_ms * (count - 1.0) + latency_ms) / count;
            }
            ModelTier::Complex => {
                self.performance_metrics.complex_query_count += 1;
                let count = self.performance_metrics.complex_query_count as f64;
                self.performance_metrics.complex_avg_latency_ms = 
                    (self.performance_metrics.complex_avg_latency_ms * (count - 1.0) + latency_ms) / count;
            }
        }
    }

    /// Get performance statistics
    pub fn get_performance_stats(&self) -> PerformanceStats {
        PerformanceStats {
            fast_avg_latency_ms: self.performance_metrics.fast_avg_latency_ms,
            balanced_avg_latency_ms: self.performance_metrics.balanced_avg_latency_ms,
            complex_avg_latency_ms: self.performance_metrics.complex_avg_latency_ms,
            fast_query_count: self.performance_metrics.fast_query_count,
            balanced_query_count: self.performance_metrics.balanced_query_count,
            complex_query_count: self.performance_metrics.complex_query_count,
            total_queries: self.performance_metrics.fast_query_count 
                + self.performance_metrics.balanced_query_count 
                + self.performance_metrics.complex_query_count,
        }
    }

    /// Check if all models are available
    pub async fn check_availability(&self) -> ModelAvailability {
        ModelAvailability {
            fast_available: self.fast_model.is_available().await,
            balanced_available: self.balanced_model.is_available().await,
            complex_available: self.complex_model.is_available().await,
        }
    }
}

/// Response from router
#[derive(Debug)]
pub struct RouterResponse {
    pub content: String,
    pub model_used: String,
    pub tier_used: ModelTier,
    pub latency: Duration,
    pub complexity: QueryComplexity,
}

/// Performance statistics
#[derive(Debug, Clone)]
pub struct PerformanceStats {
    pub fast_avg_latency_ms: f64,
    pub balanced_avg_latency_ms: f64,
    pub complex_avg_latency_ms: f64,
    pub fast_query_count: u64,
    pub balanced_query_count: u64,
    pub complex_query_count: u64,
    pub total_queries: u64,
}

/// Model availability status
#[derive(Debug)]
pub struct ModelAvailability {
    pub fast_available: bool,
    pub balanced_available: bool,
    pub complex_available: bool,
}
