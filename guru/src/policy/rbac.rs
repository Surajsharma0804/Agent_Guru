//! Role-Based Access Control (RBAC)
//! Policy engine for agent permissions.

use crate::agents::agent_trait::{AgentCapability, AgentRole};
use std::collections::HashSet;

#[derive(Debug, Clone)]
pub struct Role {
    pub name: AgentRole,
    pub capabilities: HashSet<AgentCapability>,
}

impl Role {
    pub fn system() -> Self {
        let mut caps = HashSet::new();
        caps.insert(AgentCapability::Read);
        caps.insert(AgentCapability::Write);
        caps.insert(AgentCapability::Execute);
        caps.insert(AgentCapability::Network);
        caps.insert(AgentCapability::Memory);
        caps.insert(AgentCapability::Crypto);
        caps.insert(AgentCapability::VoiceControl);
        
        Self {
            name: AgentRole::System,
            capabilities: caps,
        }
    }

    pub fn assistant() -> Self {
        let mut caps = HashSet::new();
        caps.insert(AgentCapability::Read);
        caps.insert(AgentCapability::Memory);
        caps.insert(AgentCapability::VoiceControl);
        
        Self {
            name: AgentRole::Assistant,
            capabilities: caps,
        }
    }

    pub fn worker() -> Self {
        let mut caps = HashSet::new();
        caps.insert(AgentCapability::Read);
        caps.insert(AgentCapability::Write);
        caps.insert(AgentCapability::Execute);
        
        Self {
            name: AgentRole::Worker,
            capabilities: caps,
        }
    }

    pub fn observer() -> Self {
        let mut caps = HashSet::new();
        caps.insert(AgentCapability::Read);
        
        Self {
            name: AgentRole::Observer,
            capabilities: caps,
        }
    }
}

pub struct PolicyEngine;

impl PolicyEngine {
    pub fn can_execute(role: &Role, capability: &AgentCapability) -> bool {
        role.capabilities.contains(capability)
    }

    pub fn enforce(role: &Role, capability: &AgentCapability) -> Result<(), String> {
        if Self::can_execute(role, capability) {
            Ok(())
        } else {
            Err(format!("Permission denied: {:?} lacks {:?}", role.name, capability))
        }
    }
}
