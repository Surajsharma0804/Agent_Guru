//! Message Bus
//! Secure inter-agent communication system.

use crate::security::crypto::symmetric_encryption::{encrypt, decrypt, EnvelopeKey};
use crate::security::crypto::secure_memory::Secret;
use std::sync::{Arc, Mutex};
use std::collections::VecDeque;

#[derive(Debug, Clone)]
pub struct Message {
    pub from: String,
    pub to: String,
    pub payload: String,
    pub timestamp: u64,
}

pub struct MessageBus {
    key: EnvelopeKey,
    queue: Arc<Mutex<VecDeque<Vec<u8>>>>, // Encrypted messages
}

impl MessageBus {
    pub fn new(key_bytes: [u8; 32]) -> Self {
        Self {
            key: EnvelopeKey(Secret::new(key_bytes)),
            queue: Arc::new(Mutex::new(VecDeque::new())),
        }
    }

    pub fn send(&self, msg: Message) -> Result<(), String> {
        // Serialize message (simple format)
        let data = format!("{}|{}|{}|{}", msg.from, msg.to, msg.payload, msg.timestamp);
        
        // Encrypt
        let nonce = [0u8; 24]; // TODO: Random nonce per message
        let encrypted = encrypt(&self.key, &nonce, data.as_bytes());
        
        // Enqueue
        let mut queue = self.queue.lock().unwrap();
        queue.push_back(encrypted);
        
        Ok(())
    }

    pub fn receive(&self, agent_id: &str) -> Option<Message> {
        let mut queue = self.queue.lock().unwrap();
        
        // Find first message for this agent
        for i in 0..queue.len() {
            if let Some(encrypted) = queue.get(i) {
                let nonce = [0u8; 24];
                if let Some(decrypted) = decrypt(&self.key, &nonce, encrypted) {
                    if let Ok(data_str) = String::from_utf8(decrypted) {
                        let parts: Vec<&str> = data_str.split('|').collect();
                        if parts.len() == 4 && parts[1] == agent_id {
                            // This message is for us
                            queue.remove(i);
                            return Some(Message {
                                from: parts[0].to_string(),
                                to: parts[1].to_string(),
                                payload: parts[2].to_string(),
                                timestamp: parts[3].parse().unwrap_or(0),
                            });
                        }
                    }
                }
            }
        }
        
        None
    }
}
