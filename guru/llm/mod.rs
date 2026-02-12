//! # LLM Runtime Module
//! 
//! Production-grade multi-provider language model runtime with strict security boundaries.
//! Supports local models (Ollama) and cloud APIs (OpenAI, Gemini) with runtime switching.

pub mod ollama;
pub mod model_router;
pub mod provider_types;
pub mod provider_openai;
pub mod provider_gemini;
pub mod audit_logger;
pub mod unified_provider;
pub mod config_loader;

pub use ollama::{OllamaClient, OllamaError, ChatMessage};
pub use model_router::{ModelRouter, RouterResponse, ModelTier, QueryComplexity, PerformanceStats, ModelAvailability};
pub use provider_types::{ProviderType, TaskType, RuntimeMode, LlmRuntimeConfig, ApiCredentials, TaskProviderConfig};
pub use provider_openai::OpenAiClient;
pub use provider_gemini::GeminiClient;
pub use audit_logger::{AuditLogger, AuditLogEntry, AuditStatistics};
pub use unified_provider::{UnifiedProvider, ProviderResponse, UnifiedProviderError};
pub use config_loader::{load_config, load_config_or_default, ConfigError};