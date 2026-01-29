//! Agent Trait
//! Core interface for all agents in the system.

use std::collections::HashSet;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum AgentCapability {
    Read,           // Read files/data
    Write,          // Write files/data
    Execute,        // Execute commands
    Network,        // Network access
    Memory,         // Access semantic memory
    Crypto,         // Cryptographic operations
    VoiceControl,   // Voice command processing
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AgentRole {
    System,         // Full privileges
    Assistant,      // User-facing agent
    Worker,         // Background task executor
    Observer,       // Read-only monitoring
}

pub trait Agent: Send + Sync {
    fn id(&self) -> &str;
    fn role(&self) -> AgentRole;
    fn capabilities(&self) -> HashSet<AgentCapability>;
    
    fn execute(&self, task: &str) -> Result<String, String>;
}
