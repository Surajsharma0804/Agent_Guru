"""
Memory Retrieval Layer for retrieval-augmented reasoning.

This module provides vector database storage and semantic search capabilities
for different types of memories (episodic, semantic, preference, task).

Components:
    - VectorDatabase: ChromaDB-based vector storage with semantic search
    - MemoryRetriever: High-level interface for memory storage and retrieval
    - EmbeddingGenerator: Sentence-transformers based embedding generation
    - MemoryStoragePipeline: Automatic memory storage with deduplication

Performance Targets:
    - Retrieval latency: <100ms (P95)
    - Embedding generation: <50ms per text (GPU accelerated)
    - Storage: <10ms per memory
    - Search: <100ms for top-k retrieval

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from Agent_Guru.reasoning.memory.embedding import EmbeddingGenerator
from Agent_Guru.reasoning.memory.storage_pipeline import MemoryStoragePipeline
from Agent_Guru.reasoning.memory.vector_db import VectorDatabase

__all__ = [
    "VectorDatabase",
    "EmbeddingGenerator",
    "MemoryStoragePipeline",
]
