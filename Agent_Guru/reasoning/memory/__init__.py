"""Embeddings for semantic memory search.

Components:
    - EmbeddingGenerator: Sentence-transformers based embedding generation,
      used by Agent_Guru.memory.memory_manager to rank past conversations.

This package also held VectorDatabase (a ChromaDB store) and
MemoryStoragePipeline. Nothing in the application ever constructed either:
the assistant's memory is memory_manager's SQLite store. Because this file
imported them eagerly, every process that loaded the embedder imported
chromadb anyway (2.0 s measured) and shipped a package with two unfixed
critical advisories. They were removed with the chromadb dependency.

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from Agent_Guru.reasoning.memory.embedding import EmbeddingGenerator

__all__ = [
    "EmbeddingGenerator",
]
