"""
GURU Memory Service - MIRIX Architecture Implementation

This module implements the MIRIX (Multi-agent Intelligent Resource Information eXchange) 
memory architecture with six specialized memory types for the GURU Personal Assistant.

The memory service provides:
- Six specialized memory types (Core, Episodic, Semantic, Procedural, Resource, Knowledge Vault)
- SQLite-based persistent storage with encryption
- Vector embeddings for similarity search (local only)
- Configurable retention policies
- Comprehensive audit logging
- Thread-safe operations with connection pooling

Security Features:
- AES-256 encryption for sensitive data
- User-controlled encryption keys
- Local-only processing (no external dependencies)
- Instant full deletion capabilities
- Tamper-evident audit logging
"""

from .database import DatabaseManager, DatabaseMigrator
from .memory_types import (
    CoreMemory,
    EpisodicMemory, 
    SemanticMemory,
    ProceduralMemory,
    ResourceMemory,
    KnowledgeVault
)
from .memory_agents import (
    MetaAgent,
    CoreManager,
    EpisodicManager,
    SemanticManager,
    ProceduralManager,
    ResourceManager,
    VaultManager
)
from .encryption import MemoryEncryption
from .vector_search import VectorSearchEngine
# from .retention import RetentionPolicyManager  # Temporarily disabled
from .memory_service import MemoryService

__all__ = [
    'DatabaseManager',
    'DatabaseMigrator', 
    'CoreMemory',
    'EpisodicMemory',
    'SemanticMemory', 
    'ProceduralMemory',
    'ResourceMemory',
    'KnowledgeVault',
    'MetaAgent',
    'CoreManager',
    'EpisodicManager',
    'SemanticManager',
    'ProceduralManager',
    'ResourceManager',
    'VaultManager',
    'MemoryEncryption',
    'VectorSearchEngine',
    # 'RetentionPolicyManager',  # Temporarily disabled
    'MemoryService'
]