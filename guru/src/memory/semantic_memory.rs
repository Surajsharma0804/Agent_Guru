//! Semantic Memory
//! High-level interface for remembering and recalling facts.

use super::vector_store::VectorStore;
use crate::intelligence::embedding_model::EmbeddingModel;
use std::sync::{Arc, Mutex};

pub struct SemanticMemory {
    store: Arc<Mutex<VectorStore>>,
    embedder: Box<dyn EmbeddingModel>,
}

impl SemanticMemory {
    pub fn new(key: [u8; 32], embedder: Box<dyn EmbeddingModel>) -> Self {
        Self {
            store: Arc::new(Mutex::new(VectorStore::new(key))),
            embedder,
        }
    }

    pub fn remember(&self, text: &str) {
        let embedding = self.embedder.embed(text);
        let mut store = self.store.lock().unwrap();
        store.add(text.to_string(), embedding, "{}".to_string());
    }

    pub fn recall(&self, query: &str) -> Vec<String> {
        let embedding = self.embedder.embed(query);
        let store = self.store.lock().unwrap();
        // Top 3
        let results = store.search(&embedding, 3);
        results.into_iter().map(|(t, _)| t).collect()
    }
}
