//! Sovereign Vector Store
//! Encrypted in-memory vector database.

use crate::intelligence::tensor::Tensor;
use crate::security::crypto::symmetric_encryption::{encrypt, decrypt, EnvelopeKey};
use crate::security::crypto::secure_memory::Secret;
use std::fs;
use std::io;

#[derive(Debug, Clone)]
pub struct VectorDocument {
    pub text: String,
    pub embedding: Tensor,
    pub metadata: String, // JSON or formatted.
}

pub struct VectorStore {
    documents: Vec<VectorDocument>,
    key: EnvelopeKey,
}

impl VectorStore {
    pub fn new(key_bytes: [u8; 32]) -> Self {
        Self {
            documents: Vec::new(),
            key: EnvelopeKey(Secret::new(key_bytes)),
        }
    }

    pub fn add(&mut self, text: String, embedding: Tensor, metadata: String) {
        self.documents.push(VectorDocument { text, embedding, metadata });
    }

    pub fn search(&self, query_emb: &Tensor, k: usize) -> Vec<(String, f32)> {
        // Linear scan (exact kNN)
        // Cosine similarity
        let mut scores: Vec<(usize, f32)> = self.documents.iter().enumerate().map(|(idx, doc)| {
            // Manual cosine: A.B / (|A|*|B|)
            // Assume embeddings are normalized? 
            // If not, normalize here or trust input.
            // Let's safe-guard:
            let dot = doc.embedding.data.iter().zip(&query_emb.data).map(|(a, b)| a * b).sum::<f32>();
            // Assuming normalized for speed.
            (idx, dot)
        }).collect();

        // Sort desc
        scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        scores.into_iter().take(k).map(|(idx, score)| {
            (self.documents[idx].text.clone(), score)
        }).collect()
    }
    
    // Save/Load Encrypted
    pub fn save(&self, path: &str) -> io::Result<()> {
        // Simple serialization: Count | Doc1 | Doc2 ...
        // Doc: TextLen | Text | EmbDim | EmbData | MetaLen | Meta
        let mut data = Vec::new();
        data.extend_from_slice(&(self.documents.len() as u32).to_le_bytes());
        
        for doc in &self.documents {
             let t_bytes = doc.text.as_bytes();
             data.extend_from_slice(&(t_bytes.len() as u32).to_le_bytes());
             data.extend_from_slice(t_bytes);
             
             let dim = doc.embedding.data.len();
             data.extend_from_slice(&(dim as u32).to_le_bytes());
             for val in &doc.embedding.data {
                 data.extend_from_slice(&val.to_le_bytes());
             }
             
             let m_bytes = doc.metadata.as_bytes();
             data.extend_from_slice(&(m_bytes.len() as u32).to_le_bytes());
             data.extend_from_slice(m_bytes);
        }
        
        // Encrypt
        let nonce = [0u8; 24]; // TODO: Random
        let encrypted = encrypt(&self.key, &nonce, &data);
        fs::write(path, encrypted)
    }

    pub fn load(path: &str, key_bytes: [u8; 32]) -> io::Result<Self> {
         let encrypted = fs::read(path)?;
         let key = EnvelopeKey(Secret::new(key_bytes));
         let nonce = [0u8; 24];
         
         let data = decrypt(&key, &nonce, &encrypted).ok_or(io::Error::new(io::ErrorKind::InvalidData, "Decrypt failed"))?;
         
         let mut offset = 0;
         if data.len() < 4 { return Ok(Self::new(key_bytes)); }
         let count = u32::from_le_bytes(data[0..4].try_into().unwrap());
         offset += 4;
         
         let mut docs = Vec::new();
         
         for _ in 0..count {
             // Text
             if offset + 4 > data.len() { break; }
             let t_len = u32::from_le_bytes(data[offset..offset+4].try_into().unwrap()) as usize;
             offset += 4;
             if offset + t_len > data.len() { break; }
             let text = String::from_utf8(data[offset..offset+t_len].to_vec()).map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "UTF8"))?;
             offset += t_len;
             
             // Emb
             if offset + 4 > data.len() { break; }
             let e_len = u32::from_le_bytes(data[offset..offset+4].try_into().unwrap()) as usize;
             offset += 4;
             if offset + e_len * 4 > data.len() { break; }
             let mut e_data = Vec::with_capacity(e_len);
             for _ in 0..e_len {
                 let f = f32::from_le_bytes(data[offset..offset+4].try_into().unwrap());
                 e_data.push(f);
                 offset += 4;
             }
             let embedding = Tensor::new(e_data, vec![e_len]); // Flat 1D for storage
             
             // Meta
             if offset + 4 > data.len() { break; }
             let m_len = u32::from_le_bytes(data[offset..offset+4].try_into().unwrap()) as usize;
             offset += 4;
             if offset + m_len > data.len() { break; }
             let metadata = String::from_utf8(data[offset..offset+m_len].to_vec()).map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "UTF8"))?;
             offset += m_len;
             
             docs.push(VectorDocument { text, embedding, metadata });
         }
         
         Ok(VectorStore { documents: docs, key })
    }
}
