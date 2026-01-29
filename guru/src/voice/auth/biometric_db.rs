use super::voiceprint::Voiceprint;
use std::fs;
use std::io::{self};
use crate::security::crypto::symmetric_encryption::{encrypt, decrypt, EnvelopeKey}; 
use crate::security::crypto::secure_memory::Secret;

pub struct BiometricDB {
    users: Vec<Voiceprint>,
    key: EnvelopeKey, 
}

impl BiometricDB {
    pub fn new(key_bytes: [u8; 32]) -> Self {
        BiometricDB {
            users: Vec::new(),
            key: EnvelopeKey(Secret::new(key_bytes)),
        }
    }

    pub fn register(&mut self, vp: Voiceprint) {
        // Remove existing user with same label?
        self.users.retain(|u| u.label != vp.label);
        self.users.push(vp);
    }

    pub fn verify(&self, probe: &Voiceprint, threshold: f32) -> Option<String> {
        // Find best match
        let mut best_score = -1.0f32;
        let mut best_user = None;

        for user in &self.users {
            let score = user.cosine_similarity(probe);
            if score > best_score {
                best_score = score;
                best_user = Some(user.label.clone());
            }
        }

        if best_score >= threshold {
            best_user
        } else {
            None
        }
    }
    
    pub fn save(&self, path: &str) -> io::Result<()> {
        let mut data = Vec::new();
        // Schema: [Count: u32] [Records...]
        data.extend_from_slice(&(self.users.len() as u32).to_le_bytes());
        for u in &self.users {
            data.extend_from_slice(&u.to_bytes());
        }
        
        // Encrypt `data`
        // Dynamic Nonce: [8 bytes timestamp][16 bytes 0] (Low freq write, timestamp sufficient uniqueness if > 1s intervals)
        // Better: Use timestamp high res + some variance? 
        // We will use SystemTime.
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos(); 
            
        let mut nonce = [0u8; 24];
        // nano fits in u128, take lower 16 or mix?
        // 24 bytes = 192 bits.
        // We can put 16 bytes of nanos.
        nonce[0..16].copy_from_slice(&timestamp.to_le_bytes());
        
        // Encrypt
        let encrypted = encrypt(&self.key, &nonce, &data);
        
        // Write: [Nonce 24][Ciphertext]
        let mut file_content = Vec::with_capacity(24 + encrypted.len());
        file_content.extend_from_slice(&nonce);
        file_content.extend_from_slice(&encrypted);
        
        fs::write(path, file_content)
    }
    
    pub fn load(path: &str, key_bytes: [u8; 32]) -> io::Result<Self> {
        let file_content = fs::read(path)?;
        let key = EnvelopeKey(Secret::new(key_bytes));
        
        // Needs at least nonce (24)
        if file_content.len() < 24 { 
             // Empty DB
             return Ok(BiometricDB { users: Vec::new(), key });
        }
        
        let mut nonce = [0u8; 24];
        nonce.copy_from_slice(&file_content[0..24]);
        let ciphertext = &file_content[24..];
        
        let data = decrypt(&key, &nonce, ciphertext)
            .ok_or(io::Error::new(io::ErrorKind::InvalidData, "Decrypt failed"))?;
        
        let mut users = Vec::new();
        let mut offset = 0;
        if data.len() < 4 { return Ok(BiometricDB { users: Vec::new(), key }); }
        
        let count = u32::from_le_bytes(data[0..4].try_into().unwrap());
        offset += 4;
        
        for _ in 0..count {
            if offset + 4 > data.len() { break; }
            let lbl_len = u32::from_le_bytes(data[offset..offset+4].try_into().unwrap()) as usize;
            if offset + 4 + lbl_len + 4 > data.len() { break; }
             let vec_len = u32::from_le_bytes(data[offset+4+lbl_len..offset+4+lbl_len+4].try_into().unwrap()) as usize;
             
             let total_len = 4 + lbl_len + 4 + vec_len * 4;
             if offset + total_len > data.len() { break; }
             
             if let Some(vp) = Voiceprint::from_bytes(&data[offset..offset+total_len]) {
                 users.push(vp);
             }
             offset += total_len;
        }
        
        Ok(BiometricDB {
            users,
            key,
        })
    }
}

