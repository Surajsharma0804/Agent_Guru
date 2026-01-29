//! Orchestrator
//! Coordinates multi-agent workflows.


use super::registry::AgentRegistry;
use super::message_bus::{MessageBus, Message};
use std::sync::Arc;

pub struct Orchestrator {
    registry: Arc<AgentRegistry>,
    message_bus: Arc<MessageBus>,
}

impl Orchestrator {
    pub fn new(registry: Arc<AgentRegistry>, message_bus: Arc<MessageBus>) -> Self {
        Self {
            registry,
            message_bus,
        }
    }

    pub fn delegate_task(&self, task: &str, agent_id: &str) -> Result<String, String> {
        // Get agent
        let agent = self.registry.get(agent_id)
            .ok_or_else(|| format!("Agent {} not found", agent_id))?;
        
        // Execute task
        agent.execute(task)
    }

    pub fn broadcast(&self, from: &str, payload: &str) -> Result<(), String> {
        let agents = self.registry.list_agents();
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        for agent_id in agents {
            if agent_id != from {
                let msg = Message {
                    from: from.to_string(),
                    to: agent_id,
                    payload: payload.to_string(),
                    timestamp,
                };
                self.message_bus.send(msg)?;
            }
        }
        
        Ok(())
    }
}
