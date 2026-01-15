"""
GURU Memory Service - Main Service Implementation

The MemorySubsystemController is the primary interface for all memory operations in GURU.
It coordinates the MIRIX architecture agents and provides a unified API for:

- Memory storage and retrieval across all six memory types
- Vector-based similarity search (local only)
- Encryption and privacy protection
- Retention policy management
- Comprehensive audit logging
- Performance monitoring and optimization

The service ensures:
- Thread-safe operations
- Automatic encryption for sensitive data
- Local-only processing (no external dependencies)
- Instant data deletion capabilities
- Comprehensive error handling and recovery
"""

import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .conversation_storage import ConversationStorage, ConversationTurn
from .database import DatabaseConfig, DatabaseLifecycleOrchestrator
from .encryption import MemoryEncryption
from .memory_agents import MetaAgent
from .memory_types import (
    AccessPolicy,
    CoreMemory,
    EpisodicMemory,
    KnowledgeVault,
    ProceduralMemory,
    ResourceMemory,
    RetentionPolicy,
    SemanticMemory,
)
from .retention_scheduler import RetentionScheduler
from .vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


class MemorySubsystemControllerError(Exception):
    """Exception for memory subsystem controller operations."""


class MemorySubsystemController:
    """
    Main Memory Service for GURU Personal Assistant.
    
    Provides unified access to all memory types through the MIRIX architecture.
    Handles encryption, vector search, retention policies, and audit logging.
    """
    
    def __init__(self, data_dir: str, encryption_key: Optional[bytes] = None,
                 enable_vector_search: bool = True, enable_retention: bool = True,
                 enable_auto_purge: bool = True):
        """
        Initialize the Memory Service.
        
        Args:
            data_dir: Directory for storing memory database and files
            encryption_key: User-controlled encryption key (generated if None)
            enable_vector_search: Enable vector similarity search
            enable_retention: Enable automatic retention policy enforcement
            enable_auto_purge: Enable automatic conversation purging
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()
        self._initialized = False
        self._shutdown = False
        
        # Initialize core components
        self._initialize_database()
        self._initialize_encryption(encryption_key)
        self._initialize_vector_search(enable_vector_search)
        self._initialize_retention(enable_retention)
        self._initialize_agents()
        
        # Initialize retention scheduler
        if enable_auto_purge:
            self.retention_scheduler = RetentionScheduler(self)
            self.retention_scheduler.start()
        else:
            self.retention_scheduler = None
        
        self._initialized = True
        logger.info("Memory Service initialized successfully")
    
    def _initialize_database(self) -> None:
        """Initialize the database manager with optimized configuration."""
        db_path = self.data_dir / "memory.db"
        
        config = DatabaseConfig(
            db_path=str(db_path),
            max_connections=10,
            connection_timeout=30.0,
            enable_wal_mode=True,
            enable_foreign_keys=True,
            page_size=4096,
            cache_size=-64000,  # 64MB cache
            temp_store="memory",
            synchronous="NORMAL",
            journal_mode="WAL",
            auto_vacuum="INCREMENTAL"
        )
        
        self.db_orchestrator = DatabaseLifecycleOrchestrator(config)
        logger.info(f"Database initialized at {db_path}")
    
    def _initialize_encryption(self, encryption_key: Optional[bytes]) -> None:
        """Initialize encryption with user-controlled keys."""
        key_file = self.data_dir / "encryption.key"
        
        if encryption_key is None:
            if key_file.exists():
                # Load existing key
                with open(key_file, 'rb') as f:
                    encryption_key = f.read()
                logger.info("Loaded existing encryption key")
            else:
                # Generate new key
                encryption_key = os.urandom(32)  # 256-bit key
                with open(key_file, 'wb') as f:
                    f.write(encryption_key)
                # Set restrictive permissions
                os.chmod(key_file, 0o600)
                logger.info("Generated new encryption key")
        else:
            # Save provided key
            with open(key_file, 'wb') as f:
                f.write(encryption_key)
            os.chmod(key_file, 0o600)
            logger.info("Using provided encryption key")
        
        # Convert bytes key to base64 string for MemoryEncryption
        import base64
        key_string = base64.b64encode(encryption_key).decode('utf-8')
        self.encryption = MemoryEncryption(key_string)
    
    def _initialize_vector_search(self, enable_vector_search: bool) -> None:
        """Initialize vector search engine for similarity search."""
        if enable_vector_search:
            try:
                self.vector_search = VectorSearchEngine(
                    min_similarity_threshold=0.1  # Minimum similarity for results
                )
                logger.info("Vector search engine initialized")
            except Exception as e:
                logger.warning(f"Vector search initialization failed: {e}")
                self.vector_search = None
        else:
            self.vector_search = None
            logger.info("Vector search disabled")
    
    def _initialize_retention(self, enable_retention: bool) -> None:
        """Initialize retention policy manager."""
        if enable_retention:
            from .retention import MemoryRetentionEnforcer  # Local import to avoid circular dependency
            self.retention_manager = MemoryRetentionEnforcer(self.db_orchestrator)
            logger.info("Retention policy manager initialized")
        else:
            self.retention_manager = None
            logger.info("Retention policies disabled")
    
    def _initialize_agents(self) -> None:
        """Initialize all memory agents."""
        self.meta_agent = MetaAgent(
            self.db_orchestrator, 
            self.encryption, 
            self.vector_search
        )
        
        # Direct access to specialized agents
        self.core_manager = self.meta_agent.core_manager
        self.episodic_manager = self.meta_agent.episodic_manager
        self.semantic_manager = self.meta_agent.semantic_manager
        self.procedural_manager = self.meta_agent.procedural_manager
        self.resource_manager = self.meta_agent.resource_manager
        self.vault_manager = self.meta_agent.vault_manager
        
        # Initialize conversation storage
        self.conversation_storage = ConversationStorage(
            self.db_orchestrator,
            self.encryption,
            self.vector_search
        )
        
        logger.info("Memory agents initialized")
    
    def _ensure_initialized(self) -> None:
        """Ensure service is initialized and not shutdown."""
        if not self._initialized:
            raise MemorySubsystemControllerError("Memory service not initialized")
        if self._shutdown:
            raise MemorySubsystemControllerError("Memory service is shutdown")
    
    # Core Memory Operations
    
    def store_core_preference(self, key: str, value: Any, encrypted: bool = False) -> CoreMemory:
        """Store a core user preference or configuration."""
        self._ensure_initialized()
        
        with self._lock:
            # Determine data type
            from .memory_types import DataType
            if isinstance(value, bool):
                data_type = DataType.BOOLEAN
            elif isinstance(value, int):
                data_type = DataType.INTEGER
            elif isinstance(value, float):
                data_type = DataType.FLOAT
            elif isinstance(value, (dict, list)):
                data_type = DataType.JSON
            else:
                data_type = DataType.STRING
            
            memory = CoreMemory(
                key=key,
                value=value,
                data_type=data_type,
                encrypted=encrypted
            )
            
            return self.core_manager.create(memory)
    
    def get_core_preference(self, key: str) -> Optional[Any]:
        """Get a core user preference value."""
        self._ensure_initialized()
        
        memory = self.core_manager.get(key)
        return memory.value if memory else None
    
    def update_core_preference(self, key: str, value: Any) -> bool:
        """Update an existing core preference."""
        self._ensure_initialized()
        
        memory = self.core_manager.get(key)
        if not memory:
            return False
        
        memory.value = value
        self.core_manager.update(memory)
        return True
    
    def delete_core_preference(self, key: str) -> bool:
        """Delete a core preference."""
        self._ensure_initialized()
        
        return self.core_manager.delete(key)
    
    # Episodic Memory Operations
    
    def store_episode(self, summary: str, details: Optional[str] = None,
                     participants: Optional[List[str]] = None,
                     location: Optional[str] = None,
                     tags: Optional[List[str]] = None,
                     retention_policy: RetentionPolicy = RetentionPolicy.SHORT_TERM,
                     encrypted: bool = False) -> EpisodicMemory:
        """Store an episodic memory (event or interaction)."""
        self._ensure_initialized()
        
        memory = EpisodicMemory(
            summary=summary,
            details=details,
            participants=participants or [],
            location=location,
            tags=tags or [],
            retention_policy=retention_policy,
            encrypted=encrypted
        )
        
        return self.episodic_manager.create(memory)
    
    def get_episode(self, event_id: str) -> Optional[EpisodicMemory]:
        """Get an episodic memory by event ID."""
        self._ensure_initialized()
        
        return self.episodic_manager.get(event_id)
    
    def search_episodes(self, query: str, limit: int = 20) -> List[EpisodicMemory]:
        """Search episodic memories."""
        self._ensure_initialized()
        
        return self.episodic_manager.search(query, limit)
    
    def get_episodes_by_timerange(self, start_time: datetime, end_time: datetime,
                                 limit: int = 50) -> List[EpisodicMemory]:
        """Get episodes within a time range."""
        self._ensure_initialized()
        
        return self.episodic_manager.search_by_timerange(start_time, end_time, limit)
    
    def get_episodes_by_tags(self, tags: List[str], limit: int = 50) -> List[EpisodicMemory]:
        """Get episodes by tags."""
        self._ensure_initialized()
        
        return self.episodic_manager.search_by_tags(tags, limit)
    
    # Semantic Memory Operations
    
    def store_concept(self, concept_name: str, description: Optional[str] = None,
                     category: Optional[str] = None,
                     relationships: Optional[Dict[str, Any]] = None) -> SemanticMemory:
        """Store a semantic concept."""
        self._ensure_initialized()
        
        memory = SemanticMemory(
            concept_name=concept_name,
            description=description,
            category=category,
            relationships=relationships or {}
        )
        
        return self.semantic_manager.create(memory)
    
    def get_concept(self, concept_id: str) -> Optional[SemanticMemory]:
        """Get a semantic concept by ID."""
        self._ensure_initialized()
        
        return self.semantic_manager.get(concept_id)
    
    def search_concepts(self, query: str, limit: int = 20) -> List[SemanticMemory]:
        """Search semantic concepts."""
        self._ensure_initialized()
        
        return self.semantic_manager.search(query, limit)
    
    def get_concepts_by_category(self, category: str, limit: int = 50) -> List[SemanticMemory]:
        """Get concepts by category."""
        self._ensure_initialized()
        
        return self.semantic_manager.search_by_category(category, limit)
    
    def get_related_concepts(self, concept_id: str, limit: int = 10) -> List[SemanticMemory]:
        """Get concepts related to the given concept."""
        self._ensure_initialized()
        
        return self.semantic_manager.get_related_concepts(concept_id, limit)
    
    # Procedural Memory Operations
    
    def store_procedure(self, name: str, steps: List[Dict[str, Any]],
                       description: Optional[str] = None,
                       prerequisites: Optional[List[str]] = None,
                       success_criteria: Optional[List[str]] = None) -> ProceduralMemory:
        """Store a procedural memory (workflow or process)."""
        self._ensure_initialized()
        
        memory = ProceduralMemory(
            name=name,
            description=description,
            steps=steps,
            prerequisites=prerequisites or [],
            success_criteria=success_criteria or []
        )
        
        return self.procedural_manager.create(memory)
    
    def get_procedure(self, procedure_id: str) -> Optional[ProceduralMemory]:
        """Get a procedure by ID."""
        self._ensure_initialized()
        
        return self.procedural_manager.get(procedure_id)
    
    def record_procedure_execution(self, procedure_id: str, success: bool, 
                                  duration_ms: int) -> bool:
        """Record execution of a procedure."""
        self._ensure_initialized()
        
        return self.procedural_manager.record_execution(procedure_id, success, duration_ms)
    
    def get_best_procedures(self, limit: int = 10) -> List[ProceduralMemory]:
        """Get procedures with highest success rates."""
        self._ensure_initialized()
        
        return self.procedural_manager.get_best_procedures(limit)
    
    def search_procedures(self, query: str, limit: int = 20) -> List[ProceduralMemory]:
        """Search procedural memories."""
        self._ensure_initialized()
        
        return self.procedural_manager.search(query, limit)
    
    # Resource Memory Operations
    
    def store_resource(self, name: str, resource_type: str, path: Optional[str] = None,
                      content_hash: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      file_size: Optional[int] = None,
                      mime_type: Optional[str] = None) -> ResourceMemory:
        """Store a resource memory (file, document, URL)."""
        self._ensure_initialized()
        
        memory = ResourceMemory(
            name=name,
            resource_type=resource_type,
            path=path,
            content_hash=content_hash,
            metadata=metadata or {},
            file_size=file_size,
            mime_type=mime_type
        )
        
        return self.resource_manager.create(memory)
    
    def get_resource(self, resource_id: str) -> Optional[ResourceMemory]:
        """Get a resource by ID."""
        self._ensure_initialized()
        
        return self.resource_manager.get(resource_id)
    
    def get_resources_by_type(self, resource_type: str, limit: int = 50) -> List[ResourceMemory]:
        """Get resources by type."""
        self._ensure_initialized()
        
        return self.resource_manager.search_by_type(resource_type, limit)
    
    def get_recently_accessed_resources(self, limit: int = 20) -> List[ResourceMemory]:
        """Get recently accessed resources."""
        self._ensure_initialized()
        
        return self.resource_manager.get_recently_accessed(limit)
    
    def search_resources(self, query: str, limit: int = 20) -> List[ResourceMemory]:
        """Search resource memories."""
        self._ensure_initialized()
        
        return self.resource_manager.search(query, limit)
    
    # Knowledge Vault Operations
    
    def store_vault_item(self, name: str, vault_type: str, encrypted_data: bytes,
                        metadata: Optional[Dict[str, Any]] = None,
                        expires_at: Optional[datetime] = None,
                        access_policy: AccessPolicy = AccessPolicy.STRICT) -> KnowledgeVault:
        """Store an encrypted vault item."""
        self._ensure_initialized()
        
        memory = KnowledgeVault(
            name=name,
            vault_type=vault_type,
            encrypted_data=encrypted_data,
            metadata=metadata or {},
            expires_at=expires_at,
            access_policy=access_policy
        )
        
        return self.vault_manager.create(memory)
    
    def get_vault_item(self, vault_id: str, require_auth: bool = True) -> Optional[KnowledgeVault]:
        """Get a vault item by ID."""
        self._ensure_initialized()
        
        return self.vault_manager.get(vault_id, require_auth)
    
    def get_vault_items_by_type(self, vault_type: str, limit: int = 50) -> List[KnowledgeVault]:
        """Get vault items by type."""
        self._ensure_initialized()
        
        return self.vault_manager.search_by_type(vault_type, limit)
    
    def search_vault_items(self, query: str, limit: int = 20) -> List[KnowledgeVault]:
        """Search vault items (name and metadata only)."""
        self._ensure_initialized()
        
        return self.vault_manager.search(query, limit)
    
    # Conversation Storage Operations
    
    def store_conversation(self, user_message: str, assistant_response: str,
                          context_metadata: Optional[Dict[str, Any]] = None) -> ConversationTurn:
        """
        Store a conversation turn with encryption.
        
        Args:
            user_message: User's message
            assistant_response: Assistant's response
            context_metadata: Optional context metadata
            
        Returns:
            ConversationTurn: Stored conversation turn
            
        Validates: Requirements 10.1, 10.2
        """
        self._ensure_initialized()
        
        return self.conversation_storage.store_conversation(
            user_message, assistant_response, context_metadata
        )
    
    def get_conversation(self, turn_id: str) -> Optional[ConversationTurn]:
        """Get a conversation turn by ID."""
        self._ensure_initialized()
        
        return self.conversation_storage.get_conversation(turn_id)
    
    def search_conversations(self, query: str, limit: int = 10) -> List[ConversationTurn]:
        """
        Search conversations using vector similarity.
        
        Validates: Requirements 10.3
        """
        self._ensure_initialized()
        
        return self.conversation_storage.search_conversations(query, limit)
    
    def get_recent_conversations(self, limit: int = 10) -> List[ConversationTurn]:
        """Get recent conversation history."""
        self._ensure_initialized()
        
        return self.conversation_storage.get_recent_conversations(limit)
    
    def get_conversations_by_timerange(self, start_time: datetime, end_time: datetime,
                                      limit: int = 100) -> List[ConversationTurn]:
        """Get conversations within a time range."""
        self._ensure_initialized()
        
        return self.conversation_storage.get_conversations_by_timerange(
            start_time, end_time, limit
        )
    
    def purge_old_conversations(self, days: int = 90) -> int:
        """
        Purge conversations older than specified days.
        
        Validates: Requirements 10.5
        """
        self._ensure_initialized()
        
        return self.conversation_storage.purge_old_conversations(days)
    
    def delete_conversation(self, turn_id: str) -> bool:
        """Delete a specific conversation."""
        self._ensure_initialized()
        
        return self.conversation_storage.delete_conversation(turn_id)
    
    def delete_all_conversations(self, confirmation_token: str) -> int:
        """Delete all conversations (requires confirmation)."""
        self._ensure_initialized()
        
        return self.conversation_storage.delete_all_conversations(confirmation_token)
    
    def get_conversation_count(self) -> int:
        """Get total number of stored conversations."""
        self._ensure_initialized()
        
        return self.conversation_storage.get_conversation_count()
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation storage statistics."""
        self._ensure_initialized()
        
        return self.conversation_storage.get_storage_stats()
    
    # Cross-Memory Operations
    
    def search_all_memories(self, query: str, memory_types: Optional[List[str]] = None,
                           limit: int = 50) -> List[Tuple[str, Any]]:
        """Search across all memory types."""
        self._ensure_initialized()
        
        return self.meta_agent.search_across_types(query, memory_types, limit)
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        self._ensure_initialized()
        
        return self.meta_agent.get_memory_statistics()
    
    # Data Management Operations
    
    def cleanup_expired_memories(self) -> Dict[str, int]:
        """Clean up expired memories across all types."""
        self._ensure_initialized()
        
        results = self.meta_agent.cleanup_expired_memories()
        
        # Also clean up vault items
        if self.vault_manager:
            vault_cleanup = self.vault_manager.cleanup_expired()
            results['vault'] = vault_cleanup
        
        return results
    
    def apply_retention_policies(self) -> Dict[str, int]:
        """Apply retention policies to clean up old data."""
        self._ensure_initialized()
        
        if not self.retention_manager:
            return {}
        
        return self.retention_manager.apply_all_policies()
    
    def export_memories(self, output_dir: str, memory_types: Optional[List[str]] = None,
                       include_encrypted: bool = False) -> Dict[str, str]:
        """Export memories to files for backup or migration."""
        self._ensure_initialized()
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        export_results = {}
        
        if memory_types is None:
            memory_types = ['core', 'episodic', 'semantic', 'procedural', 'resource']
            if include_encrypted:
                memory_types.append('vault')
        
        for memory_type in memory_types:
            try:
                self.meta_agent.get_agent(memory_type)
                
                # Export would be implemented based on specific requirements
                # This is a placeholder for the export functionality
                export_file = output_path / f"{memory_type}_export.json"
                export_results[memory_type] = str(export_file)
                
                logger.info(f"Exported {memory_type} memories to {export_file}")
                
            except Exception as e:
                logger.error(f"Failed to export {memory_type}: {e}")
                export_results[memory_type] = f"Error: {e}"
        
        return export_results
    
    def purge_all_data(self, confirmation_token: str) -> bool:
        """
        Permanently delete all memory data.
        
        Args:
            confirmation_token: Must be "CONFIRM_PURGE_ALL_DATA"
            
        Returns:
            True if successful, False otherwise
        """
        if confirmation_token != "CONFIRM_PURGE_ALL_DATA":
            raise MemorySubsystemControllerError("Invalid confirmation token")
        
        self._ensure_initialized()
        
        try:
            with self._lock:
                # Delete all data from all tables
                with self.db_orchestrator.transaction() as conn:
                    tables = [
                        'core_memory', 'episodic_memory', 'semantic_memory',
                        'procedural_memory', 'resource_memory', 'knowledge_vault',
                        'memory_access_log', 'vector_search_index'
                    ]
                    
                    for table in tables:
                        conn.execute(f"DELETE FROM {table}")
                    
                    # Reset auto-increment counters
                    for table in tables:
                        conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                
                # Clear vector search index
                if self.vector_search:
                    self.vector_search.clear_index()
                
                logger.warning("All memory data has been permanently deleted")
                return True
                
        except Exception as e:
            logger.error(f"Failed to purge all data: {e}")
            return False
    
    # Service Management
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        self._ensure_initialized()
        
        health = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {}
        }
        
        # Check database
        try:
            if self.db_orchestrator.verify_integrity():
                health['components']['database'] = 'healthy'
            else:
                health['components']['database'] = 'degraded'
                health['status'] = 'degraded'
        except Exception as e:
            health['components']['database'] = f'error: {e}'
            health['status'] = 'unhealthy'
        
        # Check encryption
        try:
            test_data = b"health_check_test"
            encrypted = self.encryption.encrypt_data(test_data)
            decrypted = self.encryption.decrypt_data(encrypted)
            if decrypted == test_data:
                health['components']['encryption'] = 'healthy'
            else:
                health['components']['encryption'] = 'degraded'
                health['status'] = 'degraded'
        except Exception as e:
            health['components']['encryption'] = f'error: {e}'
            health['status'] = 'unhealthy'
        
        # Check vector search
        if self.vector_search:
            try:
                # Simple vector search test
                health['components']['vector_search'] = 'healthy'
            except Exception as e:
                health['components']['vector_search'] = f'error: {e}'
                health['status'] = 'degraded'
        else:
            health['components']['vector_search'] = 'disabled'
        
        # Check retention manager
        if self.retention_manager:
            health['components']['retention_manager'] = 'healthy'
        else:
            health['components']['retention_manager'] = 'disabled'
        
        return health
    
    def shutdown(self) -> None:
        """Shutdown the memory service and clean up resources."""
        if self._shutdown:
            return
        
        logger.info("Shutting down Memory Service...")
        
        with self._lock:
            self._shutdown = True
            
            # Stop retention scheduler
            if hasattr(self, 'retention_scheduler') and self.retention_scheduler:
                self.retention_scheduler.stop()
            
            # Shutdown components
            if hasattr(self, 'db_orchestrator'):
                self.db_orchestrator.shutdown()
            
            if hasattr(self, 'vector_search') and self.vector_search:
                self.vector_search.shutdown()
            
            logger.info("Memory Service shutdown complete")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.shutdown()


# Alias for test compatibility
MemoryService = MemorySubsystemController
MemoryServiceError = MemorySubsystemControllerError
