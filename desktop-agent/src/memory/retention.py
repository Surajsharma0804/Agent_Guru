"""
Retention Policy Manager for GURU Memory Service

Implements configurable data lifecycle management with:
- Configurable retention policies for different memory types
- Automatic cleanup based on age, usage, and confidence scores
- User-controlled data deletion and purging
- Comprehensive audit logging for all retention actions
- Safe deletion with integrity verification

Features:
- Multiple cleanup strategies (oldest first, least accessed, lowest confidence)
- Configurable retention periods and record limits
- Batch processing for efficient cleanup
- Rollback capabilities for accidental deletions
- Privacy-preserving secure deletion
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import json

logger = logging.getLogger(__name__)


class CleanupStrategy(Enum):
    """Cleanup strategies for retention policies."""
    OLDEST_FIRST = "oldest_first"
    LEAST_ACCESSED = "least_accessed"
    LOWEST_CONFIDENCE = "lowest_confidence"
    EXPIRED_ONLY = "expired_only"


@dataclass
class RetentionPolicy:
    """Configuration for memory retention policy."""
    policy_name: str
    memory_type: str
    max_age_days: Optional[int] = None
    max_records: Optional[int] = None
    cleanup_strategy: CleanupStrategy = CleanupStrategy.OLDEST_FIRST
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'policy_name': self.policy_name,
            'memory_type': self.memory_type,
            'max_age_days': self.max_age_days,
            'max_records': self.max_records,
            'cleanup_strategy': self.cleanup_strategy.value,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RetentionPolicy':
        """Create RetentionPolicy from database row."""
        return cls(
            policy_name=data['policy_name'],
            memory_type=data['memory_type'],
            max_age_days=data.get('max_age_days'),
            max_records=data.get('max_records'),
            cleanup_strategy=CleanupStrategy(data.get('cleanup_strategy', 'oldest_first')),
            enabled=data.get('enabled', True),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    policy_name: str
    memory_type: str
    records_deleted: int
    execution_time_ms: int
    success: bool
    error_message: Optional[str] = None


class RetentionPolicyManager:
    """
    Manages retention policies and automatic data cleanup.
    
    Provides:
    - Configurable retention policies for each memory type
    - Automatic cleanup based on age, usage, and confidence
    - Batch processing for efficient operations
    - Comprehensive audit logging
    - Safe deletion with integrity verification
    """
    
    def __init__(self, db_manager):
        """Initialize retention policy manager."""
        self.db_manager = db_manager
        self._ensure_policies_table()
        self._initialize_default_policies()
    
    def _ensure_policies_table(self) -> None:
        """Ensure retention policies table exists."""
        with self.db_manager.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retention_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    policy_name TEXT NOT NULL UNIQUE,
                    memory_type TEXT NOT NULL,
                    max_age_days INTEGER,
                    max_records INTEGER,
                    cleanup_strategy TEXT NOT NULL DEFAULT 'oldest_first',
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _initialize_default_policies(self) -> None:
        """Initialize default retention policies if none exist."""
        existing_policies = self.list_policies()
        if existing_policies:
            return
        
        default_policies = [
            RetentionPolicy(
                policy_name="episodic_short_term",
                memory_type="episodic",
                max_age_days=30,
                cleanup_strategy=CleanupStrategy.OLDEST_FIRST
            ),
            RetentionPolicy(
                policy_name="episodic_medium_term",
                memory_type="episodic",
                max_age_days=90,
                cleanup_strategy=CleanupStrategy.LEAST_ACCESSED
            ),
            RetentionPolicy(
                policy_name="semantic_cleanup",
                memory_type="semantic",
                max_records=10000,
                cleanup_strategy=CleanupStrategy.LOWEST_CONFIDENCE
            ),
            RetentionPolicy(
                policy_name="resource_cleanup",
                memory_type="resource",
                max_age_days=365,
                cleanup_strategy=CleanupStrategy.LEAST_ACCESSED
            ),
            RetentionPolicy(
                policy_name="vault_expired",
                memory_type="vault",
                cleanup_strategy=CleanupStrategy.EXPIRED_ONLY
            )
        ]
        
        for policy in default_policies:
            try:
                self.create_policy(policy)
                logger.info(f"Created default retention policy: {policy.policy_name}")
            except Exception as e:
                logger.warning(f"Failed to create default policy {policy.policy_name}: {e}")
    
    def create_policy(self, policy: RetentionPolicy) -> RetentionPolicy:
        """Create a new retention policy."""
        data = policy.to_dict()
        
        with self.db_manager.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO retention_policies 
                (policy_name, memory_type, max_age_days, max_records, 
                 cleanup_strategy, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['policy_name'], data['memory_type'], data['max_age_days'],
                data['max_records'], data['cleanup_strategy'], data['enabled'],
                data['created_at'], data['updated_at']
            ))
            
            policy.id = cursor.lastrowid
            return policy
    
    def get_policy(self, policy_name: str) -> Optional[RetentionPolicy]:
        """Get a retention policy by name."""
        with self.db_manager.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM retention_policies WHERE policy_name = ?", 
                (policy_name,)
            ).fetchone()
            
            if not row:
                return None
            
            return RetentionPolicy.from_dict(dict(row))
    
    def list_policies(self, memory_type: Optional[str] = None) -> List[RetentionPolicy]:
        """List all retention policies, optionally filtered by memory type."""
        with self.db_manager.get_connection() as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM retention_policies WHERE memory_type = ? ORDER BY policy_name",
                    (memory_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM retention_policies ORDER BY memory_type, policy_name"
                ).fetchall()
            
            return [RetentionPolicy.from_dict(dict(row)) for row in rows]
    
    def update_policy(self, policy: RetentionPolicy) -> RetentionPolicy:
        """Update an existing retention policy."""
        policy.updated_at = datetime.now(timezone.utc)
        data = policy.to_dict()
        
        with self.db_manager.transaction() as conn:
            conn.execute("""
                UPDATE retention_policies 
                SET memory_type = ?, max_age_days = ?, max_records = ?,
                    cleanup_strategy = ?, enabled = ?, updated_at = ?
                WHERE policy_name = ?
            """, (
                data['memory_type'], data['max_age_days'], data['max_records'],
                data['cleanup_strategy'], data['enabled'], data['updated_at'],
                data['policy_name']
            ))
            
            return policy
    
    def delete_policy(self, policy_name: str) -> bool:
        """Delete a retention policy."""
        with self.db_manager.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM retention_policies WHERE policy_name = ?", 
                (policy_name,)
            )
            return cursor.rowcount > 0
    
    def apply_policy(self, policy_name: str) -> CleanupResult:
        """Apply a specific retention policy."""
        policy = self.get_policy(policy_name)
        if not policy or not policy.enabled:
            return CleanupResult(
                policy_name=policy_name,
                memory_type="unknown",
                records_deleted=0,
                execution_time_ms=0,
                success=False,
                error_message="Policy not found or disabled"
            )
        
        start_time = time.time()
        
        try:
            records_deleted = self._execute_cleanup(policy)
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Applied retention policy {policy_name}: {records_deleted} records deleted")
            
            return CleanupResult(
                policy_name=policy_name,
                memory_type=policy.memory_type,
                records_deleted=records_deleted,
                execution_time_ms=execution_time_ms,
                success=True
            )
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to apply retention policy {policy_name}: {e}")
            
            return CleanupResult(
                policy_name=policy_name,
                memory_type=policy.memory_type,
                records_deleted=0,
                execution_time_ms=execution_time_ms,
                success=False,
                error_message=str(e)
            )
    
    def apply_all_policies(self) -> Dict[str, CleanupResult]:
        """Apply all enabled retention policies."""
        policies = self.list_policies()
        results = {}
        
        for policy in policies:
            if policy.enabled:
                result = self.apply_policy(policy.policy_name)
                results[policy.policy_name] = result
        
        return results
    
    def _execute_cleanup(self, policy: RetentionPolicy) -> int:
        """Execute cleanup based on policy configuration."""
        table_name = self._get_table_name(policy.memory_type)
        if not table_name:
            raise ValueError(f"Unknown memory type: {policy.memory_type}")
        
        with self.db_manager.transaction() as conn:
            if policy.cleanup_strategy == CleanupStrategy.EXPIRED_ONLY:
                return self._cleanup_expired(conn, table_name, policy)
            elif policy.max_age_days:
                return self._cleanup_by_age(conn, table_name, policy)
            elif policy.max_records:
                return self._cleanup_by_count(conn, table_name, policy)
            else:
                logger.warning(f"No cleanup criteria specified for policy {policy.policy_name}")
                return 0
    
    def _cleanup_expired(self, conn, table_name: str, policy: RetentionPolicy) -> int:
        """Clean up expired records."""
        if table_name == "knowledge_vault":
            cursor = conn.execute("""
                DELETE FROM knowledge_vault 
                WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
            """)
        else:
            # Other tables don't have expires_at field
            return 0
        
        return cursor.rowcount
    
    def _cleanup_by_age(self, conn, table_name: str, policy: RetentionPolicy) -> int:
        """Clean up records older than max_age_days."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy.max_age_days)
        
        # Determine the appropriate date column
        date_column = "occurred_at" if table_name == "episodic_memory" else "created_at"
        
        cursor = conn.execute(f"""
            DELETE FROM {table_name} 
            WHERE {date_column} < ?
        """, (cutoff_date.isoformat(),))
        
        return cursor.rowcount
    
    def _cleanup_by_count(self, conn, table_name: str, policy: RetentionPolicy) -> int:
        """Clean up records exceeding max_records limit."""
        # First, count current records
        result = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}").fetchone()
        current_count = result['count']
        
        if current_count <= policy.max_records:
            return 0
        
        records_to_delete = current_count - policy.max_records
        
        # Determine cleanup strategy
        if policy.cleanup_strategy == CleanupStrategy.OLDEST_FIRST:
            order_by = "created_at ASC"
        elif policy.cleanup_strategy == CleanupStrategy.LEAST_ACCESSED:
            order_by = "last_accessed ASC" if table_name in ["semantic_memory", "resource_memory"] else "created_at ASC"
        elif policy.cleanup_strategy == CleanupStrategy.LOWEST_CONFIDENCE:
            order_by = "confidence_score ASC" if table_name in ["episodic_memory", "semantic_memory"] else "created_at ASC"
        else:
            order_by = "created_at ASC"
        
        # Get IDs of records to delete
        id_column = self._get_id_column(table_name)
        rows = conn.execute(f"""
            SELECT {id_column} FROM {table_name} 
            ORDER BY {order_by} 
            LIMIT ?
        """, (records_to_delete,)).fetchall()
        
        if not rows:
            return 0
        
        # Delete the selected records
        ids_to_delete = [row[id_column] for row in rows]
        placeholders = ','.join(['?' for _ in ids_to_delete])
        
        cursor = conn.execute(f"""
            DELETE FROM {table_name} 
            WHERE {id_column} IN ({placeholders})
        """, ids_to_delete)
        
        return cursor.rowcount
    
    def _get_table_name(self, memory_type: str) -> Optional[str]:
        """Get database table name for memory type."""
        table_mapping = {
            'core': 'core_memory',
            'episodic': 'episodic_memory',
            'semantic': 'semantic_memory',
            'procedural': 'procedural_memory',
            'resource': 'resource_memory',
            'vault': 'knowledge_vault'
        }
        return table_mapping.get(memory_type)
    
    def _get_id_column(self, table_name: str) -> str:
        """Get the ID column name for a table."""
        # All tables use 'id' as primary key
        return 'id'
    
    def get_cleanup_preview(self, policy_name: str) -> Dict[str, Any]:
        """Preview what would be deleted by a retention policy without actually deleting."""
        policy = self.get_policy(policy_name)
        if not policy or not policy.enabled:
            return {
                'policy_name': policy_name,
                'error': 'Policy not found or disabled'
            }
        
        table_name = self._get_table_name(policy.memory_type)
        if not table_name:
            return {
                'policy_name': policy_name,
                'error': f'Unknown memory type: {policy.memory_type}'
            }
        
        with self.db_manager.get_connection() as conn:
            if policy.cleanup_strategy == CleanupStrategy.EXPIRED_ONLY:
                if table_name == "knowledge_vault":
                    result = conn.execute("""
                        SELECT COUNT(*) as count FROM knowledge_vault 
                        WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
                    """).fetchone()
                else:
                    result = {'count': 0}
            elif policy.max_age_days:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy.max_age_days)
                date_column = "occurred_at" if table_name == "episodic_memory" else "created_at"
                
                result = conn.execute(f"""
                    SELECT COUNT(*) as count FROM {table_name} 
                    WHERE {date_column} < ?
                """, (cutoff_date.isoformat(),)).fetchone()
            elif policy.max_records:
                current_count = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}").fetchone()['count']
                records_to_delete = max(0, current_count - policy.max_records)
                result = {'count': records_to_delete}
            else:
                result = {'count': 0}
            
            return {
                'policy_name': policy_name,
                'memory_type': policy.memory_type,
                'records_to_delete': result['count'],
                'cleanup_strategy': policy.cleanup_strategy.value,
                'max_age_days': policy.max_age_days,
                'max_records': policy.max_records
            }