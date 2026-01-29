#![allow(clippy::needless_range_loop)]
//! Embedding Model Interface

use crate::intelligence::tensor::Tensor;

pub trait EmbeddingModel: Send + Sync {
    fn embed(&self, text: &str) -> Tensor;
}

// Stub implementation for compilation
pub struct MockEmbedder;

impl EmbeddingModel for MockEmbedder {
    fn embed(&self, text: &str) -> Tensor {
        // Hash text to deterministic random vector for testing
        let mut h = 0u64;
        for b in text.bytes() {
            h = h.wrapping_add(b as u64).wrapping_mul(31);
        }
        
        let mut data = vec![0.0; 256];
        for i in 0..256 {
            data[i] = ((h.wrapping_add(i as u64) % 100) as f32) / 100.0;
        }
        Tensor::new(data, vec![256])
    }
}
