//! # Memory Management Module
//! 
//! Production-grade semantic memory with encryption, indexing, pruning, and temporal relationships.

#![deny(clippy::all, clippy::pedantic, clippy::nursery)]
#![allow(
    clippy::module_name_repetitions,
    clippy::missing_errors_doc,
    clippy::unnecessary_wraps,
    clippy::cast_possible_truncation,
    clippy::unused_self,
    clippy::too_many_arguments,
    clippy::ptr_arg,
    clippy::manual_clamp,
    clippy::inherent_to_string,
    clippy::await_holding_lock,
    clippy::needless_range_loop,
    clippy::manual_memcpy,
    clippy::suboptimal_flops,
    clippy::struct_excessive_bools,
    clippy::cast_precision_loss,
    clippy::cast_sign_loss,
    clippy::cast_lossless,
    clippy::or_fun_call,
    missing_docs
)]
pub mod semantic_index;
pub mod encryption;
pub mod pruning;
pub mod temporal_graph;

pub use semantic_index::{SemanticIndex, SemanticIndexConfig, SemanticEntry, SimilarityResult, SemanticIndexError};
pub use encryption::{MemoryEncryption, EncryptionConfig, EncryptionAlgorithm, EncryptedData, UserEncryptionKey, EncryptionError};
pub use pruning::{MemoryPruning, PruningConfig, PruningStrategy, PrunableEntry, ImportanceScore, PruningError};
pub use temporal_graph::{TemporalGraph, TemporalGraphConfig, TemporalNode, TemporalEdge, RelationshipType, TemporalPath, TemporalGraphError};