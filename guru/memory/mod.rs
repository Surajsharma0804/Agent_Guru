//! # Memory Management Module
//! 
//! Production-grade semantic memory with encryption, indexing, pruning, and temporal relationships.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
pub mod semantic_index;
pub mod encryption;
pub mod pruning;
pub mod temporal_graph;

pub use semantic_index::{SemanticIndex, SemanticIndexConfig, SemanticEntry, SimilarityResult, SemanticIndexError};
pub use encryption::{MemoryEncryption, EncryptionConfig, EncryptionAlgorithm, EncryptedData, UserEncryptionKey, EncryptionError};
pub use pruning::{MemoryPruning, PruningConfig, PruningStrategy, PrunableEntry, ImportanceScore, PruningError};
pub use temporal_graph::{TemporalGraph, TemporalGraphConfig, TemporalNode, TemporalEdge, RelationshipType, TemporalPath, TemporalGraphError};