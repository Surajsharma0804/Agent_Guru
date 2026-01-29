//! Voiceprint
//! Secure container for speaker embeddings.

// use serde::{Serialize, Deserialize};

#[derive(Debug, Clone)]
pub struct Voiceprint {
    pub vector: Vec<f32>, // 256-d
    pub label: String,    // "Owner"
}

impl Voiceprint {
    pub fn to_bytes(&self) -> Vec<u8> {
        // Simple serialization: Label Len (4 bytes) | Label | Vector Len (4 bytes) | Vector F32s
        let mut bytes = Vec::new();
        let label_bytes = self.label.as_bytes();
        bytes.extend_from_slice(&(label_bytes.len() as u32).to_le_bytes());
        bytes.extend_from_slice(label_bytes);
        
        bytes.extend_from_slice(&(self.vector.len() as u32).to_le_bytes());
        for f in &self.vector {
            bytes.extend_from_slice(&f.to_le_bytes());
        }
        bytes
    }
    
    pub fn from_bytes(data: &[u8]) -> Option<Self> {
        if data.len() < 4 { return None; }
        let mut offset = 0;
        
        let label_len = u32::from_le_bytes(data[offset..offset+4].try_into().ok()?) as usize;
        offset += 4;
        if data.len() < offset + label_len { return None; }
        
        let label = String::from_utf8(data[offset..offset+label_len].to_vec()).ok()?;
        offset += label_len;
        
        if data.len() < offset + 4 { return None; }
        let vec_len = u32::from_le_bytes(data[offset..offset+4].try_into().ok()?) as usize;
        offset += 4;
        
        if data.len() < offset + vec_len * 4 { return None; }
        
        let mut vector = Vec::with_capacity(vec_len);
        for _ in 0..vec_len {
            let val = f32::from_le_bytes(data[offset..offset+4].try_into().ok()?);
            vector.push(val);
            offset += 4;
        }
        
        Some(Self { vector, label })
    }


    pub fn new(vector: Vec<f32>, label: String) -> Self {
        Self { vector, label }
    }

    pub fn cosine_similarity(&self, other: &Self) -> f32 {
        // A . B / (|A| |B|)
        // Vectors are assumed L2 normalized by encoder?
        // If so, A . B is enough.
        // But safe to re-normalize or check.
        // encoder `embed` logic L2 norms it. 
        // So just dot product.
        
        let dot: f32 = self.vector.iter().zip(&other.vector).map(|(a, b)| a * b).sum();
        dot // Range [-1, 1], usually [0, 1] for similar speakers
    }
    
    pub fn is_match(&self, other: &Self, threshold: f32) -> bool {
        self.cosine_similarity(other) >= threshold
    }
}

