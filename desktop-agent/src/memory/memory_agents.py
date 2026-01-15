"""
MIRIX Memory Agents Implementation

Implements the six specialized memory agents that manage different types of memory:
1. MetaAgent: Coordinates all memory operations and routing
2. CoreManager: Manages persistent user preferences and identity
3. EpisodicManager: Manages time-based activities and events
4. SemanticManager: Manages general knowledge and concepts
5. ProceduralManager: Manages workflows and step-by-step processes
6. ResourceManager: Manages documents and active files
7. VaultManager: Manages encrypted sensitive data

Each agent provides:
- Specialized CRUD operations for their memory type
- Type-specific validation and business logic
- Integration with encryption and vector search
- Performance optimization for their use cases
- Audit logging for all operations
"""

import logging
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .database import DatabaseLifecycleOrchestrator
from .encryption import EncryptedData, MemoryEncryption
from .memory_types import (
    BaseMemoryRecord,
    CoreMemory,
    DataType,
    EpisodicMemory,
    KnowledgeVault,
    ProceduralMemory,
    ResourceMemory,
    SemanticMemory,
)
from .vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


class MemoryOperationError(Exception):
    """Exception for memory operation failures."""


class BaseMemoryAgent(ABC):
    """
    Base class for all memory agents.

    Provides common functionality for memory operations including:
    - Database access through connection pooling
    - Audit logging for all operations
    - Error handling and recovery
    - Performance monitoring
    """

    def __init__(
        self,
        db_orchestrator: DatabaseLifecycleOrchestrator,
        encryption: MemoryEncryption,
        vector_search: VectorSearchEngine,
    ):
        self.db_orchestrator = db_orchestrator
        self.encryption = encryption
        self.vector_search = vector_search
        self.agent_name = self.__class__.__name__

    @abstractmethod
    def get_table_name(self) -> str:
        """Get the database table name for this memory type."""

    @abstractmethod
    def get_memory_type(self) -> str:
        """Get the memory type identifier."""

    def _log_operation(
        self,
        operation_type: str,
        record_id: str,
        success: bool,
        execution_time_ms: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Log memory operation for audit trail."""
        try:
            operation_id = str(uuid.uuid4())

            with self.db_orchestrator.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO memory_access_log
                    (operation_id, memory_type, operation_type, record_id,
                     success, error_message, execution_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        operation_id,
                        self.get_memory_type(),
                        operation_type,
                        record_id,
                        success,
                        error_message,
                        execution_time_ms,
                    ),
                )
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to log memory operation: {e}")

    @contextmanager
    def _operation_context(self, operation_type: str, record_id: str):
        """Context manager for memory operations with automatic logging."""
        start_time = datetime.now()
        success = False
        error_message = None

        try:
            yield
            success = True
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._log_operation(operation_type, record_id, success, execution_time_ms, error_message)


class MetaAgent:
    """
    Meta Agent: Coordinates all memory operations and routing.

    The MetaAgent serves as the central coordinator for all memory operations,
    routing requests to appropriate specialized agents and managing cross-agent
    operations like search and cleanup.
    """

    def __init__(
        self,
        db_orchestrator: DatabaseLifecycleOrchestrator,
        encryption: MemoryEncryption,
        vector_search: VectorSearchEngine,
    ):
        self.db_orchestrator = db_orchestrator
        self.encryption = encryption
        self.vector_search = vector_search

        # Initialize specialized agents
        self.core_manager = UserIdentityPersistence(db_orchestrator, encryption, vector_search)
        self.episodic_manager = TemporalEventArchive(db_orchestrator, encryption, vector_search)
        self.semantic_manager = ConceptualKnowledgeBase(db_orchestrator, encryption, vector_search)
        self.procedural_manager = WorkflowExecutionLibrary(db_orchestrator, encryption, vector_search)
        self.resource_manager = DocumentResourceCatalog(db_orchestrator, encryption, vector_search)
        self.vault_manager = EncryptedCredentialVault(db_orchestrator, encryption, vector_search)

        self.agents = {
            "core": self.core_manager,
            "episodic": self.episodic_manager,
            "semantic": self.semantic_manager,
            "procedural": self.procedural_manager,
            "resource": self.resource_manager,
            "vault": self.vault_manager,
        }

    def get_agent(self, memory_type: str) -> BaseMemoryAgent:
        """Get the appropriate agent for a memory type."""
        if memory_type not in self.agents:
            raise MemoryOperationError(f"Unknown memory type: {memory_type}")
        return self.agents[memory_type]

    def search_across_types(
        self, query: str, memory_types: Optional[List[str]] = None, limit: int = 50
    ) -> List[Tuple[str, BaseMemoryRecord]]:
        """
        Search across multiple memory types using vector similarity.

        Args:
            query: Search query text
            memory_types: List of memory types to search (None for all)
            limit: Maximum number of results

        Returns:
            List of (memory_type, record) tuples sorted by relevance
        """
        if memory_types is None:
            memory_types = list(self.agents.keys())

        all_results = []

        for memory_type in memory_types:
            try:
                agent = self.get_agent(memory_type)
                results = agent.search(query, limit=limit // len(memory_types))
                all_results.extend([(memory_type, record) for record in results])
            except Exception as e:
                logger.warning(f"Search failed for memory type {memory_type}: {e}")

        # Sort by relevance (would need similarity scores from vector search)
        return all_results[:limit]

    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics across all types."""
        stats = {}

        for memory_type, agent in self.agents.items():
            try:
                stats[memory_type] = agent.get_statistics()
            except Exception as e:
                logger.error(f"Failed to get statistics for {memory_type}: {e}")
                stats[memory_type] = {"error": str(e)}

        # Add database-level statistics
        stats["database"] = self.db_orchestrator.get_database_stats()

        return stats

    def cleanup_expired_memories(self) -> Dict[str, int]:
        """Clean up expired memories across all types."""
        cleanup_results = {}

        for memory_type, agent in self.agents.items():
            try:
                if hasattr(agent, "cleanup_expired"):
                    count = agent.cleanup_expired()
                    cleanup_results[memory_type] = count
            except Exception as e:
                logger.error(f"Cleanup failed for {memory_type}: {e}")
                cleanup_results[memory_type] = -1

        return cleanup_results


class UserIdentityPersistence(BaseMemoryAgent):
    """
    User Identity Persistence: Manages persistent user preferences and identity.

    Handles fundamental user configuration and preferences that persist
    across sessions and form the foundation of user personalization.
    """

    def get_table_name(self) -> str:
        return "core_memory"

    def get_memory_type(self) -> str:
        return "core"

    def create(self, memory: CoreMemory) -> CoreMemory:
        """Create a new core memory record."""
        with self._operation_context("create", memory.key):
            # Encrypt value if needed
            if memory.encrypted:
                serialized_value = str(memory.value)
                if memory.data_type == DataType.JSON:
                    import json

                    serialized_value = json.dumps(memory.value)

                encrypted_value = self.encryption.encrypt_data(serialized_value.encode(), "core_memory")
                import base64

                memory.value = base64.b64encode(encrypted_value.to_bytes()).decode("utf-8")

            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO core_memory
                    (key, value, data_type, encrypted, created_at, updated_at, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        memory.key,
                        memory.value,
                        memory.data_type.value,
                        memory.encrypted,
                        memory.created_at.isoformat(),
                        memory.updated_at.isoformat(),
                        memory.version,
                    ),
                )

                memory.id = cursor.lastrowid
                return memory

    def get(self, key: str) -> Optional[CoreMemory]:
        """Get a core memory record by key."""
        with self._operation_context("read", key):
            with self.db_orchestrator.get_connection() as conn:
                row = conn.execute("SELECT * FROM core_memory WHERE key = ?", (key,)).fetchone()

                if not row:
                    return None

                memory = CoreMemory.from_dict(dict(row))

                # Decrypt value if needed
                if memory.encrypted:
                    try:
                        import base64

                        encrypted_bytes = base64.b64decode(memory.value.encode("utf-8"))
                        encrypted_data = EncryptedData.from_bytes(encrypted_bytes)
                        decrypted_value = self.encryption.decrypt_data(encrypted_data)
                        if memory.data_type == DataType.JSON:
                            import json

                            memory.value = json.loads(decrypted_value.decode())
                        else:
                            memory.value = decrypted_value.decode()
                    except Exception as e:
                        logger.error(f"Failed to decrypt core memory {key}: {e}")
                        raise MemoryOperationError(f"Decryption failed: {e}")

                return memory

    def update(self, memory: CoreMemory) -> CoreMemory:
        """Update an existing core memory record."""
        with self._operation_context("update", memory.key):
            memory.update_timestamp()
            memory.version += 1

            # Encrypt value if needed
            if memory.encrypted:
                serialized_value = str(memory.value)
                if memory.data_type == DataType.JSON:
                    import json

                    serialized_value = json.dumps(memory.value)

                encrypted_value = self.encryption.encrypt_data(serialized_value.encode(), "core_memory")
                import base64

                memory.value = base64.b64encode(encrypted_value.to_bytes()).decode("utf-8")

            with self.db_orchestrator.transaction() as conn:
                conn.execute(
                    """
                    UPDATE core_memory
                    SET value = ?, data_type = ?, encrypted = ?, updated_at = ?, version = ?
                    WHERE key = ?
                """,
                    (
                        memory.value,
                        memory.data_type.value,
                        memory.encrypted,
                        memory.updated_at.isoformat(),
                        memory.version,
                        memory.key,
                    ),
                )

                return memory

    def delete(self, key: str) -> bool:
        """Delete a core memory record."""
        with self._operation_context("delete", key):
            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute("DELETE FROM core_memory WHERE key = ?", (key,))
                return cursor.rowcount > 0

    def list_all(self) -> List[CoreMemory]:
        """List all core memory records."""
        with self._operation_context("read", "all"):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute("SELECT * FROM core_memory ORDER BY key").fetchall()

                memories = []
                for row in rows:
                    memory = CoreMemory.from_dict(dict(row))

                    # Decrypt if needed
                    if memory.encrypted:
                        try:
                            decrypted_value = self.encryption.decrypt_data(memory.value.encode())
                            if memory.data_type == DataType.JSON:
                                import json

                                memory.value = json.loads(decrypted_value.decode())
                            else:
                                memory.value = decrypted_value.decode()
                        except Exception as e:
                            logger.warning(f"Failed to decrypt core memory {memory.key}: {e}")
                            continue

                    memories.append(memory)

                return memories

    def search(self, query: str, limit: int = 10) -> List[CoreMemory]:
        """Search core memory records."""
        with self._operation_context("search", query):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM core_memory
                    WHERE key LIKE ? OR value LIKE ?
                    ORDER BY key
                    LIMIT ?
                """,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()

                return [CoreMemory.from_dict(dict(row)) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get core memory statistics."""
        with self.db_orchestrator.get_connection() as conn:
            stats = {}

            # Total count
            result = conn.execute("SELECT COUNT(*) as count FROM core_memory").fetchone()
            stats["total_records"] = result["count"]

            # Encrypted count
            result = conn.execute("SELECT COUNT(*) as count FROM core_memory WHERE encrypted = 1").fetchone()
            stats["encrypted_records"] = result["count"]

            # Data type distribution
            rows = conn.execute(
                """
                SELECT data_type, COUNT(*) as count
                FROM core_memory
                GROUP BY data_type
            """
            ).fetchall()
            stats["data_type_distribution"] = {row["data_type"]: row["count"] for row in rows}

            return stats


class TemporalEventArchive(BaseMemoryAgent):
    """
    Temporal Event Archive: Manages time-based activities and events.

    Handles specific events, interactions, and activities with temporal context.
    Used for remembering what happened when and building contextual understanding.
    """

    def get_table_name(self) -> str:
        return "episodic_memory"

    def get_memory_type(self) -> str:
        return "episodic"

    def create(self, memory: EpisodicMemory) -> EpisodicMemory:
        """Create a new episodic memory record."""
        with self._operation_context("create", memory.event_id):
            # Generate vector embedding if vector search is enabled
            if self.vector_search:
                embedding_text = f"{memory.summary} {memory.details or ''}"
                memory.vector_embedding = self.vector_search.generate_embedding(embedding_text)

            # Encrypt if needed
            if memory.encrypted:
                encrypted_summary = self.encryption.encrypt_data(memory.summary.encode(), "episodic_memory")
                import base64

                memory.summary = base64.b64encode(encrypted_summary.to_bytes()).decode("utf-8")

                if memory.details:
                    encrypted_details = self.encryption.encrypt_data(memory.details.encode(), "episodic_memory")
                    memory.details = base64.b64encode(encrypted_details.to_bytes()).decode("utf-8")

            data = memory.to_dict()

            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO episodic_memory
                    (event_id, summary, details, participants, location, tags,
                     confidence_score, encrypted, created_at, occurred_at,
                     retention_policy, vector_embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["event_id"],
                        data["summary"],
                        data["details"],
                        data["participants"],
                        data["location"],
                        data["tags"],
                        data["confidence_score"],
                        data["encrypted"],
                        data["created_at"],
                        data["occurred_at"],
                        data["retention_policy"],
                        data["vector_embedding"],
                    ),
                )

                memory.id = cursor.lastrowid
                return memory

    def get(self, event_id: str) -> Optional[EpisodicMemory]:
        """Get an episodic memory record by event ID."""
        with self._operation_context("read", event_id):
            with self.db_orchestrator.get_connection() as conn:
                row = conn.execute("SELECT * FROM episodic_memory WHERE event_id = ?", (event_id,)).fetchone()

                if not row:
                    return None

                memory = EpisodicMemory.from_dict(dict(row))

                # Decrypt if needed
                if memory.encrypted:
                    try:
                        decrypted_summary = self.encryption.decrypt_data(memory.summary.encode())
                        memory.summary = decrypted_summary.decode()

                        if memory.details:
                            decrypted_details = self.encryption.decrypt_data(memory.details.encode())
                            memory.details = decrypted_details.decode()
                    except Exception as e:
                        logger.error(f"Failed to decrypt episodic memory {event_id}: {e}")
                        raise MemoryOperationError(f"Decryption failed: {e}")

                return memory

    def search_by_timerange(self, start_time: datetime, end_time: datetime, limit: int = 50) -> List[EpisodicMemory]:
        """Search episodic memories within a time range."""
        with self._operation_context("search", f"timerange_{start_time}_{end_time}"):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM episodic_memory
                    WHERE occurred_at BETWEEN ? AND ?
                    ORDER BY occurred_at DESC
                    LIMIT ?
                """,
                    (start_time.isoformat(), end_time.isoformat(), limit),
                ).fetchall()

                return [EpisodicMemory.from_dict(dict(row)) for row in rows]

    def search_by_tags(self, tags: List[str], limit: int = 50) -> List[EpisodicMemory]:
        """Search episodic memories by tags."""
        with self._operation_context("search", f"tags_{','.join(tags)}"):
            # Simple tag search - in production would use proper JSON querying
            tag_conditions = []
            params = []

            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")

            params.append(limit)

            with self.db_orchestrator.get_connection() as conn:
                query = """
                    SELECT * FROM episodic_memory
                    WHERE {' OR '.join(tag_conditions)}
                    ORDER BY occurred_at DESC
                    LIMIT ?
                """
                rows = conn.execute(query, params).fetchall()

                return [EpisodicMemory.from_dict(dict(row)) for row in rows]

    def cleanup_expired(self) -> int:
        """Clean up expired episodic memories based on retention policy."""
        with self._operation_context("delete", "expired"):
            with self.db_orchestrator.transaction() as conn:
                # Clean up short-term memories older than 30 days
                cursor = conn.execute(
                    """
                    DELETE FROM episodic_memory
                    WHERE retention_policy = 'short_term'
                    AND occurred_at < datetime('now', '-30 days')
                """
                )

                return cursor.rowcount

    def search(self, query: str, limit: int = 10) -> List[EpisodicMemory]:
        """Search episodic memory records."""
        with self._operation_context("search", query):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM episodic_memory
                    WHERE summary LIKE ? OR details LIKE ?
                    ORDER BY occurred_at DESC
                    LIMIT ?
                """,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()

                return [EpisodicMemory.from_dict(dict(row)) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get episodic memory statistics."""
        with self.db_orchestrator.get_connection() as conn:
            stats = {}

            # Total count
            result = conn.execute("SELECT COUNT(*) as count FROM episodic_memory").fetchone()
            stats["total_records"] = result["count"]

            # Retention policy distribution
            rows = conn.execute(
                """
                SELECT retention_policy, COUNT(*) as count
                FROM episodic_memory
                GROUP BY retention_policy
            """
            ).fetchall()
            stats["retention_distribution"] = {row["retention_policy"]: row["count"] for row in rows}

            # Recent activity (last 7 days)
            result = conn.execute(
                """
                SELECT COUNT(*) as count FROM episodic_memory
                WHERE occurred_at > datetime('now', '-7 days')
            """
            ).fetchone()
            stats["recent_activity"] = result["count"]

            return stats


class ConceptualKnowledgeBase(BaseMemoryAgent):
    """
    Conceptual Knowledge Base: Manages general knowledge and concepts.

    Stores conceptual knowledge, relationships between concepts, and general
    understanding that builds over time through interactions and learning.
    """

    def get_table_name(self) -> str:
        return "semantic_memory"

    def get_memory_type(self) -> str:
        return "semantic"

    def create(self, memory: SemanticMemory) -> SemanticMemory:
        """Create a new semantic memory record."""
        with self._operation_context("create", memory.concept_id):
            # Generate vector embedding
            if self.vector_search:
                embedding_text = f"{memory.concept_name} {memory.description or ''}"
                memory.vector_embedding = self.vector_search.generate_embedding(embedding_text)

            data = memory.to_dict()

            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO semantic_memory
                    (concept_id, concept_name, description, category, relationships,
                     confidence_score, usage_count, last_accessed, encrypted,
                     created_at, updated_at, vector_embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["concept_id"],
                        data["concept_name"],
                        data["description"],
                        data["category"],
                        data["relationships"],
                        data["confidence_score"],
                        data["usage_count"],
                        data["last_accessed"],
                        data["encrypted"],
                        data["created_at"],
                        data["updated_at"],
                        data["vector_embedding"],
                    ),
                )

                memory.id = cursor.lastrowid
                return memory

    def get(self, concept_id: str) -> Optional[SemanticMemory]:
        """Get a semantic memory record by concept ID."""
        with self._operation_context("read", concept_id):
            with self.db_orchestrator.get_connection() as conn:
                row = conn.execute("SELECT * FROM semantic_memory WHERE concept_id = ?", (concept_id,)).fetchone()

                if not row:
                    return None

                memory = SemanticMemory.from_dict(dict(row))
                memory.increment_usage()

                # Update usage statistics
                self.update_usage_stats(memory)

                return memory

    def update_usage_stats(self, memory: SemanticMemory) -> None:
        """Update usage statistics for a semantic memory."""
        with self.db_orchestrator.transaction() as conn:
            conn.execute(
                """
                UPDATE semantic_memory
                SET usage_count = ?, last_accessed = ?, updated_at = ?
                WHERE concept_id = ?
            """,
                (
                    memory.usage_count,
                    memory.last_accessed.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.concept_id,
                ),
            )

    def search_by_category(self, category: str, limit: int = 50) -> List[SemanticMemory]:
        """Search semantic memories by category."""
        with self._operation_context("search", f"category_{category}"):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM semantic_memory
                    WHERE category = ?
                    ORDER BY usage_count DESC, last_accessed DESC
                    LIMIT ?
                """,
                    (category, limit),
                ).fetchall()

                return [SemanticMemory.from_dict(dict(row)) for row in rows]

    def get_related_concepts(self, concept_id: str, limit: int = 10) -> List[SemanticMemory]:
        """Get concepts related to the given concept."""
        # This would use vector similarity in a full implementation
        with self._operation_context("search", f"related_{concept_id}"):
            memory = self.get(concept_id)
            if not memory or not memory.relationships:
                return []

            # Extract related concept IDs from relationships
            related_ids = []
            if isinstance(memory.relationships, dict):
                for key, value in memory.relationships.items():
                    if isinstance(value, list):
                        related_ids.extend(value)
                    elif isinstance(value, str):
                        related_ids.append(value)

            # Fetch related concepts
            related_concepts = []
            for related_id in related_ids[:limit]:
                related = self.get(related_id)
                if related:
                    related_concepts.append(related)

            return related_concepts

    def search(self, query: str, limit: int = 10) -> List[SemanticMemory]:
        """Search semantic memory records."""
        with self._operation_context("search", query):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM semantic_memory
                    WHERE concept_name LIKE ? OR description LIKE ?
                    ORDER BY usage_count DESC, confidence_score DESC
                    LIMIT ?
                """,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()

                return [SemanticMemory.from_dict(dict(row)) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get semantic memory statistics."""
        with self.db_orchestrator.get_connection() as conn:
            stats = {}

            # Total count
            result = conn.execute("SELECT COUNT(*) as count FROM semantic_memory").fetchone()
            stats["total_records"] = result["count"]

            # Category distribution
            rows = conn.execute(
                """
                SELECT category, COUNT(*) as count
                FROM semantic_memory
                WHERE category IS NOT NULL
                GROUP BY category
            """
            ).fetchall()
            stats["category_distribution"] = {row["category"]: row["count"] for row in rows}

            # Most used concepts
            rows = conn.execute(
                """
                SELECT concept_name, usage_count
                FROM semantic_memory
                ORDER BY usage_count DESC
                LIMIT 10
            """
            ).fetchall()
            stats["most_used_concepts"] = [
                {"name": row["concept_name"], "usage_count": row["usage_count"]} for row in rows
            ]

            return stats


class WorkflowExecutionLibrary(BaseMemoryAgent):
    """
    Workflow Execution Library: Manages workflows and step-by-step processes.

    Stores learned procedures, workflows, and step-by-step processes that can
    be executed to accomplish tasks. Includes success tracking and optimization.
    """

    def get_table_name(self) -> str:
        return "procedural_memory"

    def get_memory_type(self) -> str:
        return "procedural"

    def create(self, memory: ProceduralMemory) -> ProceduralMemory:
        """Create a new procedural memory record."""
        with self._operation_context("create", memory.procedure_id):
            # Generate vector embedding
            if self.vector_search:
                embedding_text = f"{memory.name} {memory.description or ''}"
                memory.vector_embedding = self.vector_search.generate_embedding(embedding_text)

            data = memory.to_dict()

            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO procedural_memory
                    (procedure_id, name, description, steps, prerequisites,
                     success_criteria, failure_handling, execution_count,
                     success_rate, average_duration_ms, last_executed,
                     encrypted, created_at, updated_at, vector_embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["procedure_id"],
                        data["name"],
                        data["description"],
                        data["steps"],
                        data["prerequisites"],
                        data["success_criteria"],
                        data["failure_handling"],
                        data["execution_count"],
                        data["success_rate"],
                        data["average_duration_ms"],
                        data["last_executed"],
                        data["encrypted"],
                        data["created_at"],
                        data["updated_at"],
                        data["vector_embedding"],
                    ),
                )

                memory.id = cursor.lastrowid
                return memory

    def get(self, procedure_id: str) -> Optional[ProceduralMemory]:
        """Get a procedural memory record by procedure ID."""
        with self._operation_context("read", procedure_id):
            with self.db_orchestrator.get_connection() as conn:
                row = conn.execute("SELECT * FROM procedural_memory WHERE procedure_id = ?", (procedure_id,)).fetchone()

                if not row:
                    return None

                return ProceduralMemory.from_dict(dict(row))

    def record_execution(self, procedure_id: str, success: bool, duration_ms: int) -> bool:
        """Record an execution of a procedure and update statistics."""
        with self._operation_context("update", f"execution_{procedure_id}"):
            memory = self.get(procedure_id)
            if not memory:
                return False

            memory.record_execution(success, duration_ms)

            with self.db_orchestrator.transaction() as conn:
                conn.execute(
                    """
                    UPDATE procedural_memory
                    SET execution_count = ?, success_rate = ?, average_duration_ms = ?,
                        last_executed = ?, updated_at = ?
                    WHERE procedure_id = ?
                """,
                    (
                        memory.execution_count,
                        memory.success_rate,
                        memory.average_duration_ms,
                        memory.last_executed.isoformat(),
                        memory.updated_at.isoformat(),
                        procedure_id,
                    ),
                )

            return True

    def get_best_procedures(self, limit: int = 10) -> List[ProceduralMemory]:
        """Get procedures with highest success rates."""
        with self._operation_context("search", "best_procedures"):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM procedural_memory
                    WHERE execution_count > 0
                    ORDER BY success_rate DESC, execution_count DESC
                    LIMIT ?
                """,
                    (limit,),
                ).fetchall()

                return [ProceduralMemory.from_dict(dict(row)) for row in rows]

    def search(self, query: str, limit: int = 10) -> List[ProceduralMemory]:
        """Search procedural memory records."""
        with self._operation_context("search", query):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM procedural_memory
                    WHERE name LIKE ? OR description LIKE ?
                    ORDER BY success_rate DESC, execution_count DESC
                    LIMIT ?
                """,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()

                return [ProceduralMemory.from_dict(dict(row)) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get procedural memory statistics."""
        with self.db_orchestrator.get_connection() as conn:
            stats = {}

            # Total count
            result = conn.execute("SELECT COUNT(*) as count FROM procedural_memory").fetchone()
            stats["total_records"] = result["count"]

            # Execution statistics
            result = conn.execute(
                """
                SELECT
                    AVG(success_rate) as avg_success_rate,
                    AVG(execution_count) as avg_execution_count,
                    AVG(average_duration_ms) as avg_duration_ms
                FROM procedural_memory
                WHERE execution_count > 0
            """
            ).fetchone()

            stats["avg_success_rate"] = result["avg_success_rate"] or 0
            stats["avg_execution_count"] = result["avg_execution_count"] or 0
            stats["avg_duration_ms"] = result["avg_duration_ms"] or 0

            return stats


class DocumentResourceCatalog(BaseMemoryAgent):
    """
    Document Resource Catalog: Manages documents and active files.

    Stores references to and metadata about files, documents, URLs, and other
    resources that the user interacts with. Includes access tracking and content hashing.
    """

    def get_table_name(self) -> str:
        return "resource_memory"

    def get_memory_type(self) -> str:
        return "resource"

    def create(self, memory: ResourceMemory) -> ResourceMemory:
        """Create a new resource memory record."""
        with self._operation_context("create", memory.resource_id):
            # Generate vector embedding
            if self.vector_search:
                embedding_text = f"{memory.name} {memory.metadata}"
                memory.vector_embedding = self.vector_search.generate_embedding(embedding_text)

            data = memory.to_dict()

            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO resource_memory
                    (resource_id, name, resource_type, path, content_hash,
                     metadata, access_count, last_accessed, file_size,
                     mime_type, encrypted, created_at, updated_at,
                     retention_policy, vector_embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["resource_id"],
                        data["name"],
                        data["resource_type"],
                        data["path"],
                        data["content_hash"],
                        data["metadata"],
                        data["access_count"],
                        data["last_accessed"],
                        data["file_size"],
                        data["mime_type"],
                        data["encrypted"],
                        data["created_at"],
                        data["updated_at"],
                        data["retention_policy"],
                        data["vector_embedding"],
                    ),
                )

                memory.id = cursor.lastrowid
                return memory

    def get(self, resource_id: str) -> Optional[ResourceMemory]:
        """Get a resource memory record by resource ID."""
        with self._operation_context("read", resource_id):
            with self.db_orchestrator.get_connection() as conn:
                row = conn.execute("SELECT * FROM resource_memory WHERE resource_id = ?", (resource_id,)).fetchone()

                if not row:
                    return None

                memory = ResourceMemory.from_dict(dict(row))
                memory.record_access()

                # Update access statistics
                self.update_access_stats(memory)

                return memory

    def update_access_stats(self, memory: ResourceMemory) -> None:
        """Update access statistics for a resource memory."""
        with self.db_orchestrator.transaction() as conn:
            conn.execute(
                """
                UPDATE resource_memory
                SET access_count = ?, last_accessed = ?, updated_at = ?
                WHERE resource_id = ?
            """,
                (
                    memory.access_count,
                    memory.last_accessed.isoformat(),
                    memory.updated_at.isoformat(),
                    memory.resource_id,
                ),
            )

    def search_by_type(self, resource_type: str, limit: int = 50) -> List[ResourceMemory]:
        """Search resource memories by type."""
        with self._operation_context("search", f"type_{resource_type}"):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM resource_memory
                    WHERE resource_type = ?
                    ORDER BY last_accessed DESC
                    LIMIT ?
                """,
                    (resource_type, limit),
                ).fetchall()

                return [ResourceMemory.from_dict(dict(row)) for row in rows]

    def get_recently_accessed(self, limit: int = 20) -> List[ResourceMemory]:
        """Get recently accessed resources."""
        with self._operation_context("search", "recent"):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM resource_memory
                    ORDER BY last_accessed DESC
                    LIMIT ?
                """,
                    (limit,),
                ).fetchall()

                return [ResourceMemory.from_dict(dict(row)) for row in rows]

    def search(self, query: str, limit: int = 10) -> List[ResourceMemory]:
        """Search resource memory records."""
        with self._operation_context("search", query):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM resource_memory
                    WHERE name LIKE ? OR path LIKE ?
                    ORDER BY access_count DESC, last_accessed DESC
                    LIMIT ?
                """,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()

                return [ResourceMemory.from_dict(dict(row)) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get resource memory statistics."""
        with self.db_orchestrator.get_connection() as conn:
            stats = {}

            # Total count
            result = conn.execute("SELECT COUNT(*) as count FROM resource_memory").fetchone()
            stats["total_records"] = result["count"]

            # Type distribution
            rows = conn.execute(
                """
                SELECT resource_type, COUNT(*) as count
                FROM resource_memory
                GROUP BY resource_type
            """
            ).fetchall()
            stats["type_distribution"] = {row["resource_type"]: row["count"] for row in rows}

            # Total file size
            result = conn.execute(
                """
                SELECT SUM(file_size) as total_size
                FROM resource_memory
                WHERE file_size IS NOT NULL
            """
            ).fetchone()
            stats["total_file_size"] = result["total_size"] or 0

            return stats


class EncryptedCredentialVault(BaseMemoryAgent):
    """
    Encrypted Credential Vault: Manages encrypted sensitive data (credentials, contacts).

    Stores highly sensitive information with strong encryption and access controls.
    All data is encrypted at rest and requires explicit authorization to access.
    """

    def get_table_name(self) -> str:
        return "knowledge_vault"

    def get_memory_type(self) -> str:
        return "vault"

    def create(self, memory: KnowledgeVault) -> KnowledgeVault:
        """Create a new knowledge vault record."""
        with self._operation_context("create", memory.vault_id):
            # Vault data is always encrypted
            if not isinstance(memory.encrypted_data, bytes):
                raise MemoryOperationError("Vault data must be pre-encrypted bytes")

            data = memory.to_dict()

            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO knowledge_vault
                    (vault_id, name, vault_type, encrypted_data, metadata,
                     access_count, last_accessed, created_at, updated_at,
                     expires_at, access_policy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["vault_id"],
                        data["name"],
                        data["vault_type"],
                        data["encrypted_data"],
                        data["metadata"],
                        data["access_count"],
                        data["last_accessed"],
                        data["created_at"],
                        data["updated_at"],
                        data["expires_at"],
                        data["access_policy"],
                    ),
                )

                memory.id = cursor.lastrowid
                return memory

    def get(self, vault_id: str, require_auth: bool = True) -> Optional[KnowledgeVault]:
        """Get a knowledge vault record by vault ID."""
        with self._operation_context("read", vault_id):
            with self.db_orchestrator.get_connection() as conn:
                row = conn.execute("SELECT * FROM knowledge_vault WHERE vault_id = ?", (vault_id,)).fetchone()

                if not row:
                    return None

                memory = KnowledgeVault.from_dict(dict(row))

                # Check if expired
                if memory.is_expired():
                    logger.warning(f"Vault item {vault_id} has expired")
                    return None

                # Record access
                memory.record_access()
                self.update_access_stats(memory)

                return memory

    def update_access_stats(self, memory: KnowledgeVault) -> None:
        """Update access statistics for a vault memory."""
        with self.db_orchestrator.transaction() as conn:
            conn.execute(
                """
                UPDATE knowledge_vault
                SET access_count = ?, last_accessed = ?, updated_at = ?
                WHERE vault_id = ?
            """,
                (memory.access_count, memory.last_accessed.isoformat(), memory.updated_at.isoformat(), memory.vault_id),
            )

    def cleanup_expired(self) -> int:
        """Clean up expired vault items."""
        with self._operation_context("delete", "expired"):
            with self.db_orchestrator.transaction() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM knowledge_vault
                    WHERE expires_at IS NOT NULL
                    AND expires_at < datetime('now')
                """
                )

                return cursor.rowcount

    def search_by_type(self, vault_type: str, limit: int = 50) -> List[KnowledgeVault]:
        """Search vault items by type."""
        with self._operation_context("search", f"type_{vault_type}"):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM knowledge_vault
                    WHERE vault_type = ?
                    AND (expires_at IS NULL OR expires_at > datetime('now'))
                    ORDER BY last_accessed DESC
                    LIMIT ?
                """,
                    (vault_type, limit),
                ).fetchall()

                return [KnowledgeVault.from_dict(dict(row)) for row in rows]

    def search(self, query: str, limit: int = 10) -> List[KnowledgeVault]:
        """Search vault records by name and metadata only (never encrypted data)."""
        with self._operation_context("search", query):
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM knowledge_vault
                    WHERE name LIKE ?
                    AND (expires_at IS NULL OR expires_at > datetime('now'))
                    ORDER BY access_count DESC, last_accessed DESC
                    LIMIT ?
                """,
                    (f"%{query}%", limit),
                ).fetchall()

                return [KnowledgeVault.from_dict(dict(row)) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """Get vault memory statistics."""
        with self.db_orchestrator.get_connection() as conn:
            stats = {}

            # Total count
            result = conn.execute("SELECT COUNT(*) as count FROM knowledge_vault").fetchone()
            stats["total_records"] = result["count"]

            # Type distribution
            rows = conn.execute(
                """
                SELECT vault_type, COUNT(*) as count
                FROM knowledge_vault
                GROUP BY vault_type
            """
            ).fetchall()
            stats["type_distribution"] = {row["vault_type"]: row["count"] for row in rows}

            # Expired items
            result = conn.execute(
                """
                SELECT COUNT(*) as count FROM knowledge_vault
                WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
            """
            ).fetchone()
            stats["expired_items"] = result["count"]

            # Access policy distribution
            rows = conn.execute(
                """
                SELECT access_policy, COUNT(*) as count
                FROM knowledge_vault
                GROUP BY access_policy
            """
            ).fetchall()
            stats["access_policy_distribution"] = {row["access_policy"]: row["count"] for row in rows}

            return stats
