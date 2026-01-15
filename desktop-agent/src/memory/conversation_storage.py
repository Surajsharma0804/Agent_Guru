"""
Conversation Storage for GURU Memory System

Implements encrypted conversation history storage with:
- AES-256-GCM encryption for all conversation data
- Biometric-derived encryption keys
- SQLite-based persistent storage
- Automatic conversation purging (90 days)
- Vector search integration for semantic retrieval
- Complete isolation from command execution

Security Features:
- All conversations encrypted at rest
- Keys derived from biometric authentication
- No plaintext storage of sensitive data
- Tamper-evident audit logging
- Instant deletion capabilities

Validates Requirements: 10.1, 10.2, 10.4, 10.5, 10.6, 27.2, 27.3, 27.6
"""

import logging
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from .encryption import MemoryEncryption, EncryptedData
from .database import DatabaseLifecycleOrchestrator
from .vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """
    A single turn in a conversation (user message + assistant response).
    
    Represents one complete interaction cycle between user and GURU.
    All sensitive data is encrypted before storage.
    """
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_message: str = ""
    assistant_response: str = ""
    context_metadata: Dict[str, Any] = field(default_factory=dict)
    encrypted: bool = True  # Always encrypted
    vector_embedding: Optional[bytes] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'turn_id': self.turn_id,
            'timestamp': self.timestamp.isoformat(),
            'user_message': self.user_message,
            'assistant_response': self.assistant_response,
            'context_metadata': self.context_metadata,
            'encrypted': self.encrypted
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationTurn':
        """Create from dictionary."""
        return cls(
            turn_id=data['turn_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            user_message=data['user_message'],
            assistant_response=data['assistant_response'],
            context_metadata=data.get('context_metadata', {}),
            encrypted=data.get('encrypted', True)
        )


class ConversationStorageError(Exception):
    """Exception for conversation storage operations."""
    pass


class ConversationStorage:
    """
    Encrypted conversation history storage for GURU.
    
    Provides secure storage and retrieval of conversation history with:
    - AES-256-GCM encryption for all data
    - Biometric-derived encryption keys
    - Vector search for semantic retrieval
    - Automatic 90-day purging
    - Complete isolation from command execution
    
    CRITICAL: This storage is READ-ONLY for context retrieval.
    It NEVER influences command execution logic.
    """
    
    def __init__(self, db_orchestrator: DatabaseLifecycleOrchestrator,
                 encryption: MemoryEncryption,
                 vector_search: Optional[VectorSearchEngine] = None):
        """
        Initialize conversation storage.
        
        Args:
            db_orchestrator: Database manager
            encryption: Encryption service with biometric-derived keys
            vector_search: Optional vector search engine for semantic retrieval
        """
        self.db_orchestrator = db_orchestrator
        self.encryption = encryption
        self.vector_search = vector_search
        self._ensure_conversation_table()
    
    def _ensure_conversation_table(self) -> None:
        """Ensure conversation storage table exists."""
        with self.db_orchestrator.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    turn_id TEXT NOT NULL UNIQUE,
                    timestamp TIMESTAMP NOT NULL,
                    encrypted_data BLOB NOT NULL,
                    vector_embedding BLOB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes separately
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_turn_id 
                ON conversations(turn_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_timestamp 
                ON conversations(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_created_at 
                ON conversations(created_at)
            """)
            
            conn.commit()
    
    def store_conversation(self, user_message: str, assistant_response: str,
                          context_metadata: Optional[Dict[str, Any]] = None) -> ConversationTurn:
        """
        Store a conversation turn with encryption.
        
        Args:
            user_message: User's message
            assistant_response: Assistant's response
            context_metadata: Optional context metadata (non-sensitive only)
            
        Returns:
            ConversationTurn: Stored conversation turn
            
        Raises:
            ConversationStorageError: If storage fails
            
        Validates: Requirements 10.1, 10.2
        """
        try:
            # Create conversation turn
            turn = ConversationTurn(
                user_message=user_message,
                assistant_response=assistant_response,
                context_metadata=context_metadata or {}
            )
            
            # Serialize to JSON
            turn_json = json.dumps(turn.to_dict())
            
            # Encrypt conversation data using biometric-derived key
            encrypted_data = self.encryption.encrypt_string(
                turn_json,
                context="conversations"  # Context for key derivation
            )
            
            # Serialize encrypted data for storage
            encrypted_bytes = encrypted_data.to_bytes()
            
            # Generate vector embedding if vector search is enabled
            vector_embedding = None
            if self.vector_search:
                # Combine user message and assistant response for embedding
                combined_text = f"{user_message} {assistant_response}"
                self.vector_search.add_document(
                    memory_type="conversations",
                    record_id=turn.turn_id,
                    content=combined_text,
                    metadata={
                        'timestamp': turn.timestamp.isoformat(),
                        'user_message_preview': user_message[:100],
                        'assistant_response_preview': assistant_response[:100]
                    }
                )
            
            # Store encrypted conversation in database
            with self.db_orchestrator.transaction() as conn:
                conn.execute("""
                    INSERT INTO conversations 
                    (turn_id, timestamp, encrypted_data, vector_embedding, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    turn.turn_id,
                    turn.timestamp.isoformat(),
                    encrypted_bytes,
                    vector_embedding,
                    datetime.now(timezone.utc).isoformat()
                ))
            
            logger.info(f"Stored encrypted conversation turn {turn.turn_id}")
            return turn
            
        except Exception as e:
            logger.error(f"Failed to store conversation: {e}")
            raise ConversationStorageError(f"Failed to store conversation: {e}")
    
    def get_conversation(self, turn_id: str) -> Optional[ConversationTurn]:
        """
        Retrieve and decrypt a conversation turn.
        
        Args:
            turn_id: Conversation turn identifier
            
        Returns:
            ConversationTurn: Decrypted conversation turn or None if not found
            
        Raises:
            ConversationStorageError: If retrieval or decryption fails
            
        Validates: Requirements 10.4 (round-trip)
        """
        try:
            with self.db_orchestrator.get_connection() as conn:
                row = conn.execute("""
                    SELECT turn_id, timestamp, encrypted_data, vector_embedding
                    FROM conversations
                    WHERE turn_id = ?
                """, (turn_id,)).fetchone()
                
                if not row:
                    return None
                
                # Deserialize encrypted data
                encrypted_data = EncryptedData.from_bytes(row['encrypted_data'])
                
                # Decrypt conversation data
                decrypted_json = self.encryption.decrypt_string(encrypted_data)
                
                # Parse JSON
                turn_dict = json.loads(decrypted_json)
                
                # Create ConversationTurn object
                turn = ConversationTurn.from_dict(turn_dict)
                
                return turn
                
        except Exception as e:
            logger.error(f"Failed to retrieve conversation {turn_id}: {e}")
            raise ConversationStorageError(f"Failed to retrieve conversation: {e}")
    
    def search_conversations(self, query: str, limit: int = 10) -> List[ConversationTurn]:
        """
        Search conversations using vector similarity.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            
        Returns:
            List[ConversationTurn]: Matching conversations sorted by relevance
            
        Validates: Requirements 10.3 (semantic search)
        """
        try:
            if not self.vector_search:
                logger.warning("Vector search not enabled, falling back to recent conversations")
                return self.get_recent_conversations(limit)
            
            # Perform vector search
            search_results = self.vector_search.search(
                query=query,
                memory_types=["conversations"],
                max_results=limit
            )
            
            # Retrieve and decrypt matching conversations
            conversations = []
            for result in search_results:
                turn = self.get_conversation(result.record_id)
                if turn:
                    conversations.append(turn)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []
    
    def get_recent_conversations(self, limit: int = 10) -> List[ConversationTurn]:
        """
        Get recent conversation history.
        
        Args:
            limit: Maximum number of conversations to retrieve
            
        Returns:
            List[ConversationTurn]: Recent conversations sorted by timestamp (newest first)
        """
        try:
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute("""
                    SELECT turn_id, timestamp, encrypted_data
                    FROM conversations
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,)).fetchall()
                
                conversations = []
                for row in rows:
                    try:
                        # Deserialize and decrypt
                        encrypted_data = EncryptedData.from_bytes(row['encrypted_data'])
                        decrypted_json = self.encryption.decrypt_string(encrypted_data)
                        turn_dict = json.loads(decrypted_json)
                        turn = ConversationTurn.from_dict(turn_dict)
                        conversations.append(turn)
                    except Exception as e:
                        logger.warning(f"Failed to decrypt conversation {row['turn_id']}: {e}")
                        continue
                
                return conversations
                
        except Exception as e:
            logger.error(f"Failed to retrieve recent conversations: {e}")
            return []
    
    def get_conversations_by_timerange(self, start_time: datetime, end_time: datetime,
                                      limit: int = 100) -> List[ConversationTurn]:
        """
        Get conversations within a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of conversations
            
        Returns:
            List[ConversationTurn]: Conversations within time range
        """
        try:
            with self.db_orchestrator.get_connection() as conn:
                rows = conn.execute("""
                    SELECT turn_id, timestamp, encrypted_data
                    FROM conversations
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (start_time.isoformat(), end_time.isoformat(), limit)).fetchall()
                
                conversations = []
                for row in rows:
                    try:
                        encrypted_data = EncryptedData.from_bytes(row['encrypted_data'])
                        decrypted_json = self.encryption.decrypt_string(encrypted_data)
                        turn_dict = json.loads(decrypted_json)
                        turn = ConversationTurn.from_dict(turn_dict)
                        conversations.append(turn)
                    except Exception as e:
                        logger.warning(f"Failed to decrypt conversation {row['turn_id']}: {e}")
                        continue
                
                return conversations
                
        except Exception as e:
            logger.error(f"Failed to retrieve conversations by timerange: {e}")
            return []
    
    def purge_old_conversations(self, days: int = 90) -> int:
        """
        Purge conversations older than specified days.
        
        Args:
            days: Age threshold in days (default: 90)
            
        Returns:
            int: Number of conversations purged
            
        Validates: Requirements 10.5 (automatic purging)
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            with self.db_orchestrator.transaction() as conn:
                # Get turn_ids to remove from vector search
                if self.vector_search:
                    rows = conn.execute("""
                        SELECT turn_id FROM conversations
                        WHERE timestamp < ?
                    """, (cutoff_date.isoformat(),)).fetchall()
                    
                    for row in rows:
                        try:
                            self.vector_search.remove_document("conversations", row['turn_id'])
                        except Exception as e:
                            logger.warning(f"Failed to remove vector for {row['turn_id']}: {e}")
                
                # Delete old conversations
                cursor = conn.execute("""
                    DELETE FROM conversations
                    WHERE timestamp < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
            
            logger.info(f"Purged {deleted_count} conversations older than {days} days")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to purge old conversations: {e}")
            raise ConversationStorageError(f"Failed to purge conversations: {e}")
    
    def delete_conversation(self, turn_id: str) -> bool:
        """
        Delete a specific conversation.
        
        Args:
            turn_id: Conversation turn identifier
            
        Returns:
            bool: True if deleted, False if not found
        """
        try:
            with self.db_orchestrator.transaction() as conn:
                # Remove from vector search
                if self.vector_search:
                    try:
                        self.vector_search.remove_document("conversations", turn_id)
                    except Exception as e:
                        logger.warning(f"Failed to remove vector for {turn_id}: {e}")
                
                # Delete from database
                cursor = conn.execute("""
                    DELETE FROM conversations
                    WHERE turn_id = ?
                """, (turn_id,))
                
                deleted = cursor.rowcount > 0
            
            if deleted:
                logger.info(f"Deleted conversation {turn_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete conversation {turn_id}: {e}")
            return False
    
    def delete_all_conversations(self, confirmation_token: str) -> int:
        """
        Delete all conversations (requires confirmation).
        
        Args:
            confirmation_token: Must be "CONFIRM_DELETE_ALL_CONVERSATIONS"
            
        Returns:
            int: Number of conversations deleted
            
        Raises:
            ConversationStorageError: If confirmation token is invalid
        """
        if confirmation_token != "CONFIRM_DELETE_ALL_CONVERSATIONS":
            raise ConversationStorageError("Invalid confirmation token")
        
        try:
            with self.db_orchestrator.transaction() as conn:
                # Get count before deletion
                result = conn.execute("SELECT COUNT(*) as count FROM conversations").fetchone()
                count = result['count']
                
                # Clear vector search index
                if self.vector_search:
                    self.vector_search.clear_index("conversations")
                
                # Delete all conversations
                conn.execute("DELETE FROM conversations")
            
            logger.warning(f"Deleted all {count} conversations")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete all conversations: {e}")
            raise ConversationStorageError(f"Failed to delete all conversations: {e}")
    
    def get_conversation_count(self) -> int:
        """Get total number of stored conversations."""
        try:
            with self.db_orchestrator.get_connection() as conn:
                result = conn.execute("SELECT COUNT(*) as count FROM conversations").fetchone()
                return result['count']
        except Exception as e:
            logger.error(f"Failed to get conversation count: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get conversation storage statistics."""
        try:
            with self.db_orchestrator.get_connection() as conn:
                stats = {}
                
                # Total conversations
                result = conn.execute("SELECT COUNT(*) as count FROM conversations").fetchone()
                stats['total_conversations'] = result['count']
                
                # Oldest conversation
                result = conn.execute("""
                    SELECT MIN(timestamp) as oldest FROM conversations
                """).fetchone()
                stats['oldest_conversation'] = result['oldest']
                
                # Newest conversation
                result = conn.execute("""
                    SELECT MAX(timestamp) as newest FROM conversations
                """).fetchone()
                stats['newest_conversation'] = result['newest']
                
                # Storage size estimate
                result = conn.execute("""
                    SELECT SUM(LENGTH(encrypted_data)) as size FROM conversations
                """).fetchone()
                stats['encrypted_data_size_bytes'] = result['size'] or 0
                
                # Vector search stats
                if self.vector_search:
                    vector_stats = self.vector_search.get_index_stats()
                    stats['vector_search'] = vector_stats.get('conversations', {})
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}
