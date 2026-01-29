//! Agent Registry
//! Central registry for all agents in the system.

use super::agent_trait::{Agent, AgentCapability};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

pub struct AgentRegistry {
    agents: Arc<RwLock<HashMap<String, Arc<dyn Agent>>>>,
}

impl AgentRegistry {
    pub fn new() -> Self {
        Self {
            agents: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn register(&self, agent: Arc<dyn Agent>) {
        let mut agents = self.agents.write().unwrap();
        agents.insert(agent.id().to_string(), agent);
    }

    pub fn get(&self, id: &str) -> Option<Arc<dyn Agent>> {
        let agents = self.agents.read().unwrap();
        agents.get(id).cloned()
    }

    pub fn verify_capability(&self, agent_id: &str, capability: &AgentCapability) -> bool {
        if let Some(agent) = self.get(agent_id) {
            agent.capabilities().contains(capability)
        } else {
            false
        }
    }

    pub fn list_agents(&self) -> Vec<String> {
        let agents = self.agents.read().unwrap();
        agents.keys().cloned().collect()
    }
}
