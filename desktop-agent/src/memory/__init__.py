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

from .database import DatabaseLifecycleOrchestrator, DatabaseMigrator
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
    UserIdentityPersistence,
    TemporalEventArchive,
    ConceptualKnowledgeBase,
    WorkflowExecutionLibrary,
    DocumentResourceCatalog,
    EncryptedCredentialVault
)
from .encryption import MemoryEncryption
from .vector_search import VectorSearchEngine
from .conversation_storage import ConversationStorage, ConversationTurn
from .retention_scheduler import RetentionScheduler, RetentionScheduleConfig
# from .retention import MemoryRetentionEnforcer  # Temporarily disabled
from .memory_service import MemorySubsystemController

__all__ = [
    'DatabaseLifecycleOrchestrator',
    'DatabaseMigrator', 
    'CoreMemory',
    'EpisodicMemory',
    'SemanticMemory', 
    'ProceduralMemory',
    'ResourceMemory',
    'KnowledgeVault',
    'MetaAgent',
    'UserIdentityPersistence',
    'TemporalEventArchive',
    'ConceptualKnowledgeBase',
    'WorkflowExecutionLibrary',
    'DocumentResourceCatalog',
    'EncryptedCredentialVault',
    'MemoryEncryption',
    'VectorSearchEngine',
    'ConversationStorage',
    'ConversationTurn',
    'RetentionScheduler',
    'RetentionScheduleConfig',
    # 'MemoryRetentionEnforcer',  # Temporarily disabled
    'MemorySubsystemController'
]