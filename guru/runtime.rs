//! # AGENT_GURU Runtime System
//!
//! Orchestrates all subsystems and provides the main execution loop.

use std::sync::Arc;
use tokio::sync::RwLock;

/// Main runtime for AGENT_GURU
pub struct GuruRuntime {
    /// System configuration
    config: RuntimeConfig,
    /// Current state
    state: Arc<RwLock<RuntimeState>>,
}

/// Runtime configuration
#[derive(Debug, Clone)]
#[derive(Default)]
pub struct RuntimeConfig {
    /// Enable voice interface
    pub voice_enabled: bool,
    /// Enable biometric authentication
    pub biometric_enabled: bool,
    /// Enable LLM processing
    pub llm_enabled: bool,
    /// Enable memory system
    pub memory_enabled: bool,
    /// Enable OS control
    pub os_control_enabled: bool,
}


/// Runtime state
#[derive(Debug, Clone)]
pub struct RuntimeState {
    /// Is system running
    pub running: bool,
    /// Current mode
    pub mode: OperationMode,
    /// Active user session
    pub user_session: Option<String>,
}

/// Operation modes
#[derive(Debug, Clone, PartialEq)]
pub enum OperationMode {
    /// Interactive CLI mode
    Interactive,
    /// Voice-driven mode
    Voice,
    /// Autonomous mode
    Autonomous,
}

impl GuruRuntime {
    /// Create a new runtime with default configuration
    pub fn new() -> Self {
        Self {
            config: RuntimeConfig::default(),
            state: Arc::new(RwLock::new(RuntimeState {
                running: false,
                mode: OperationMode::Interactive,
                user_session: None,
            })),
        }
    }

    /// Create runtime with custom configuration
    pub fn with_config(config: RuntimeConfig) -> Self {
        Self {
            config,
            state: Arc::new(RwLock::new(RuntimeState {
                running: false,
                mode: OperationMode::Interactive,
                user_session: None,
            })),
        }
    }

    /// Start the runtime
    pub async fn start(&mut self) -> Result<(), RuntimeError> {
        let mut state = self.state.write().await;
        state.running = true;
        Ok(())
    }

    /// Stop the runtime
    pub async fn stop(&mut self) -> Result<(), RuntimeError> {
        let mut state = self.state.write().await;
        state.running = false;
        Ok(())
    }

    /// Process a natural language command
    pub fn process_command(&self, input: &str) -> Result<String, RuntimeError> {
        // Placeholder for LLM integration
        Ok(format!("Processed: {input}"))
    }

    /// Get current configuration
    pub fn config(&self) -> &RuntimeConfig {
        &self.config
    }

    /// Get current state
    pub async fn state(&self) -> RuntimeState {
        self.state.read().await.clone()
    }
}

impl Default for GuruRuntime {
    fn default() -> Self {
        Self::new()
    }
}

/// Runtime errors
#[derive(Debug, thiserror::Error)]
pub enum RuntimeError {
    #[error("Runtime initialization failed: {0}")]
    InitializationFailed(String),

    #[error("Command processing failed: {0}")]
    CommandFailed(String),

    #[error("System not running")]
    NotRunning,
}
