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

use std::sync::atomic::{AtomicU64, Ordering};

pub struct MessageBus {
    key: EnvelopeKey,
    queue: Arc<Mutex<VecDeque<Vec<u8>>>>, // Encrypted messages
    nonce_counter: AtomicU64,
}

impl MessageBus {
    pub fn new(key_bytes: [u8; 32]) -> Self {
        Self {
            key: EnvelopeKey(Secret::new(key_bytes)),
            queue: Arc::new(Mutex::new(VecDeque::new())),
            nonce_counter: AtomicU64::new(0),
        }
    }

    pub fn send(&self, msg: Message) -> Result<(), String> {
        // Serialize message (simple format)
        let data = format!("{}|{}|{}|{}", msg.from, msg.to, msg.payload, msg.timestamp);
        
        // Generate Dynamic Nonce: [8 bytes timestamp][8 bytes counter][8 bytes padding/random]
        // Since we don't have rand, we use this structure to ensure uniqueness.
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(); // u64
            
        let count = self.nonce_counter.fetch_add(1, Ordering::SeqCst);
        
        // Construct 24-byte nonce (XChaCha / NaCl usually takes 24 bytes)
        let mut nonce = [0u8; 24];
        nonce[0..8].copy_from_slice(&timestamp.to_le_bytes());
        nonce[8..16].copy_from_slice(&count.to_le_bytes());
        // Remaining 8 bytes 0 for now (or could hash something)
        
        // We need to prepend the nonce to the message so the receiver can decrypt!
        // Encrypted = [Nonce (24)] + [Ciphertext]
        let ciphertext = encrypt(&self.key, &nonce, data.as_bytes());
        
        let mut package = Vec::with_capacity(24 + ciphertext.len());
        package.extend_from_slice(&nonce);
        package.extend_from_slice(&ciphertext);
        
        // Enqueue
        let mut queue = self.queue.lock().unwrap();
        queue.push_back(package);
        
        Ok(())
    }

    pub fn receive(&self, agent_id: &str) -> Option<Message> {
        let mut queue = self.queue.lock().unwrap();
        
        // Find first message for this agent
        for i in 0..queue.len() {
            if let Some(package) = queue.get(i) {
                if package.len() < 24 { continue; }
                
                let nonce_slice = &package[0..24];
                let ciphertext = &package[24..];
                
                let mut nonce = [0u8; 24];
                nonce.copy_from_slice(nonce_slice);
                
                // Attempt decrypt
                if let Some(decrypted) = decrypt(&self.key, &nonce, ciphertext) {
                    if let Ok(data_str) = String::from_utf8(decrypted) {
                        let parts: Vec<&str> = data_str.split('|').collect();
                        if parts.len() >= 4 && parts[1] == agent_id {
                            // This message is for us (and successfully decrypted with validity)
                            // Reconstruct message
                            // Handle potential | in payload by re-joining
                            let from = parts[0].to_string();
                            let to = parts[1].to_string();
                            let timestamp = parts[parts.len()-1].parse().unwrap_or(0);
                            // Payload is everything in between
                            let payload = parts[2..parts.len()-1].join("|");
                            
                            queue.remove(i);
                            return Some(Message {
                                from,
                                to,
                                payload,
                                timestamp,
                            });
                        }
                    }
                }
            }
        }
        
        None
    }
}
