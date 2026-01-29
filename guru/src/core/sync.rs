//! Sync Engine
//! Protocol for synchronizing state between agents.

use crate::platform::networking::{NetworkTransport, TransportPacket};
use crate::security::crypto::symmetric_encryption::{encrypt, decrypt, EnvelopeKey};
use crate::security::crypto::secure_memory::Secret;
use std::sync::{Arc, Mutex};
use std::collections::HashSet;

#[derive(Debug, Clone)]
pub struct SyncItem {
    pub id: String,
    pub payload: Vec<u8>,
    pub timestamp: u64,
}

pub struct SyncEngine {
    transport: Arc<dyn NetworkTransport>,
    key: EnvelopeKey,
    seen_ids: Arc<Mutex<HashSet<String>>>,
    // In real app, this would modify Memory/Policy stores directly.
    // Here we act as a queue.
    pub inbox: Arc<Mutex<Vec<SyncItem>>>, 
}

impl SyncEngine {
    pub fn new(transport: Arc<dyn NetworkTransport>, key_bytes: [u8; 32]) -> Self {
        Self {
            transport,
            key: EnvelopeKey(Secret::new(key_bytes)),
            seen_ids: Arc::new(Mutex::new(HashSet::new())),
            inbox: Arc::new(Mutex::new(Vec::new())),
        }
    }

    pub fn broadcast_item(&self, item: SyncItem) -> Result<(), String> {
        // Encrypt payload only? Or whole packet? 
        // We wrap the item in: id|timestamp|payload_hex
        // Then encrypt.
        
        // Simplified: Payload is ALREADY user data.
        // We construct a packet.
        // Data: Encrypt( [ID: 32 bytes][Timestamp: 8][Payload...] )
        
        let mut raw = Vec::new();
        raw.extend_from_slice(item.id.as_bytes()); // Assume ID is fixed or we prefix len
        // Let's use prefix-len for ID
        let id_bytes = item.id.as_bytes();
        raw.extend_from_slice(&(id_bytes.len() as u32).to_le_bytes());
        raw.extend_from_slice(id_bytes);
        
        raw.extend_from_slice(&item.timestamp.to_le_bytes());
        raw.extend_from_slice(&item.payload);
        
        // Encrypt
        // Nonce: Time + ID hash? 
        // Using SystemTime
        let nonce_time = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
        let mut nonce = [0u8; 24];
        nonce[0..16].copy_from_slice(&nonce_time.to_le_bytes());
        
        let encrypted = encrypt(&self.key, &nonce, &raw);
        
        // Prefix Packet with Nonce
        let mut final_data = Vec::with_capacity(24 + encrypted.len());
        final_data.extend_from_slice(&nonce);
        final_data.extend_from_slice(&encrypted);
        
        let packet = TransportPacket {
            data: final_data,
            metadata: "SYNC_V1".to_string(),
        };
        
        self.transport.send(&packet).map_err(|e| e.to_string())
    }

    pub fn process_incoming(&self) -> Result<usize, String> {
        let packets = self.transport.receive_all().map_err(|e| e.to_string())?;
        let mut count = 0;
        
        let mut seen = self.seen_ids.lock().unwrap();
        let mut inbox = self.inbox.lock().unwrap();
        
        for packet in packets {
            if packet.data.len() < 24 { continue; }
            
            let mut nonce = [0u8; 24];
            nonce.copy_from_slice(&packet.data[0..24]);
            let ciphertext = &packet.data[24..];
            
            if let Some(decrypted) = decrypt(&self.key, &nonce, ciphertext) {
                 // Parse
                 let mut offset = 0;
                 if offset + 4 > decrypted.len() { continue; }
                 
                 let id_len = u32::from_le_bytes(decrypted[offset..offset+4].try_into().unwrap()) as usize;
                 offset += 4;
                 
                 if offset + id_len > decrypted.len() { continue; }
                 let id = String::from_utf8_lossy(&decrypted[offset..offset+id_len]).to_string();
                 offset += id_len;
                 
                 if seen.contains(&id) { continue; }
                 seen.insert(id.clone());
                 
                 if offset + 8 > decrypted.len() { continue; }
                 let timestamp = u64::from_le_bytes(decrypted[offset..offset+8].try_into().unwrap());
                 offset += 8;
                 
                 let payload = decrypted[offset..].to_vec();
                 
                 inbox.push(SyncItem { id, timestamp, payload });
                 count += 1;
            }
        }
        
        Ok(count)
    }
}
