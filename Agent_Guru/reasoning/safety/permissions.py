"""Permission management with database persistence."""

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Permission:
    """Permission model.
    
    Attributes:
        user_id: User identifier
        permission_scope: Permission scope (e.g., 'messaging', 'file_deletion')
        granted_at: Timestamp when permission was granted
        granted_by: Who granted the permission (user or system)
        expires_at: Optional expiration timestamp (None = never expires)
        metadata: Additional metadata about the permission
    """
    
    user_id: str
    permission_scope: str
    granted_at: float
    granted_by: str
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self) -> None:
        """Initialize metadata if None."""
        if self.metadata is None:
            self.metadata = {}
    
    def is_expired(self) -> bool:
        """
        Check if permission has expired.
        
        Returns:
            True if expired, False otherwise
        """
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert permission to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "user_id": self.user_id,
            "permission_scope": self.permission_scope,
            "granted_at": self.granted_at,
            "granted_by": self.granted_by,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Permission":
        """
        Create permission from dictionary.
        
        Args:
            data: Dictionary with permission data
            
        Returns:
            Permission instance
        """
        return cls(
            user_id=data["user_id"],
            permission_scope=data["permission_scope"],
            granted_at=data["granted_at"],
            granted_by=data["granted_by"],
            expires_at=data.get("expires_at"),
            metadata=data.get("metadata", {}),
        )


class PermissionManager:
    """Permission manager with database persistence and caching.
    
    This manager handles permission storage, retrieval, and validation
    with SQLite persistence and in-memory caching for performance.
    
    Time Complexity: O(1) for cached checks, O(log n) for database queries
    Space Complexity: O(m) where m is number of cached permissions
    """
    
    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialize permission manager.
        
        Args:
            db_path: Path to SQLite database (None for in-memory)
        """
        self._db_path = db_path or ":memory:"
        self._conn: Optional[sqlite3.Connection] = None
        self._cache: Dict[str, Dict[str, Permission]] = {}  # user_id -> {scope -> Permission}
        self._cache_ttl = 300.0  # 5 minutes
        self._cache_timestamps: Dict[str, float] = {}
        
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database schema."""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        
        cursor = self._conn.cursor()
        
        # Create permissions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                permission_scope TEXT NOT NULL,
                granted_at REAL NOT NULL,
                granted_by TEXT NOT NULL,
                expires_at REAL,
                metadata TEXT,
                UNIQUE(user_id, permission_scope)
            )
        """)
        
        # Create audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                user_id TEXT NOT NULL,
                permission_scope TEXT NOT NULL,
                action TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                reason TEXT,
                metadata TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_permissions_user 
            ON permissions(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user 
            ON permission_audit_log(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
            ON permission_audit_log(timestamp)
        """)
        
        self._conn.commit()
        
        logger.info("permission_database_initialized", db_path=self._db_path)
    
    def grant_permission(
        self,
        user_id: str,
        permission_scope: str,
        granted_by: str = "system",
        expires_at: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Permission:
        """
        Grant permission to user.
        
        Time Complexity: O(1) average case
        Space Complexity: O(1)
        
        Args:
            user_id: User identifier
            permission_scope: Permission scope to grant
            granted_by: Who is granting the permission
            expires_at: Optional expiration timestamp
            metadata: Additional metadata
            
        Returns:
            Created Permission object
        """
        permission = Permission(
            user_id=user_id,
            permission_scope=permission_scope,
            granted_at=time.time(),
            granted_by=granted_by,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        # Store in database
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO permissions 
            (user_id, permission_scope, granted_at, granted_by, expires_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            permission.user_id,
            permission.permission_scope,
            permission.granted_at,
            permission.granted_by,
            permission.expires_at,
            json.dumps(permission.metadata),
        ))
        self._conn.commit()
        
        # Update cache
        if user_id not in self._cache:
            self._cache[user_id] = {}
        self._cache[user_id][permission_scope] = permission
        self._cache_timestamps[user_id] = time.time()
        
        # Log to audit trail
        self._log_audit(
            user_id=user_id,
            permission_scope=permission_scope,
            action="grant",
            performed_by=granted_by,
            reason="Permission granted",
        )
        
        logger.info(
            "permission_granted",
            user_id=user_id,
            permission_scope=permission_scope,
            granted_by=granted_by,
            expires_at=expires_at,
        )
        
        return permission
    
    def revoke_permission(
        self,
        user_id: str,
        permission_scope: str,
        revoked_by: str = "system",
        reason: Optional[str] = None,
    ) -> bool:
        """
        Revoke permission from user.
        
        Time Complexity: O(1) average case
        Space Complexity: O(1)
        
        Args:
            user_id: User identifier
            permission_scope: Permission scope to revoke
            revoked_by: Who is revoking the permission
            reason: Reason for revocation
            
        Returns:
            True if permission was revoked, False if not found
        """
        # Check if permission exists
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM permissions 
            WHERE user_id = ? AND permission_scope = ?
        """, (user_id, permission_scope))
        
        count = cursor.fetchone()[0]
        if count == 0:
            return False
        
        # Delete from database
        cursor.execute("""
            DELETE FROM permissions 
            WHERE user_id = ? AND permission_scope = ?
        """, (user_id, permission_scope))
        self._conn.commit()
        
        # Update cache
        if user_id in self._cache and permission_scope in self._cache[user_id]:
            del self._cache[user_id][permission_scope]
        
        # Log to audit trail
        self._log_audit(
            user_id=user_id,
            permission_scope=permission_scope,
            action="revoke",
            performed_by=revoked_by,
            reason=reason or "Permission revoked",
        )
        
        logger.info(
            "permission_revoked",
            user_id=user_id,
            permission_scope=permission_scope,
            revoked_by=revoked_by,
            reason=reason,
        )
        
        return True
    
    def check_permission(
        self,
        user_id: str,
        permission_scope: str,
    ) -> bool:
        """
        Check if user has permission.
        
        Time Complexity: O(1) for cached, O(log n) for database query
        Space Complexity: O(1)
        
        Args:
            user_id: User identifier
            permission_scope: Permission scope to check
            
        Returns:
            True if user has valid permission, False otherwise
        """
        # Check cache first
        if self._is_cache_valid(user_id):
            if user_id in self._cache and permission_scope in self._cache[user_id]:
                permission = self._cache[user_id][permission_scope]
                if not permission.is_expired():
                    return True
                else:
                    # Permission expired, remove it
                    self.revoke_permission(user_id, permission_scope, "system", "Expired")
                    return False
        
        # Query database
        permission = self._get_permission_from_db(user_id, permission_scope)
        if permission is None:
            return False
        
        # Check expiration
        if permission.is_expired():
            self.revoke_permission(user_id, permission_scope, "system", "Expired")
            return False
        
        # Update cache
        if user_id not in self._cache:
            self._cache[user_id] = {}
        self._cache[user_id][permission_scope] = permission
        self._cache_timestamps[user_id] = time.time()
        
        return True
    
    def get_user_permissions(self, user_id: str) -> List[Permission]:
        """
        Get all permissions for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of Permission objects
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT user_id, permission_scope, granted_at, granted_by, expires_at, metadata
            FROM permissions 
            WHERE user_id = ?
        """, (user_id,))
        
        permissions = []
        for row in cursor.fetchall():
            permission = Permission(
                user_id=row["user_id"],
                permission_scope=row["permission_scope"],
                granted_at=row["granted_at"],
                granted_by=row["granted_by"],
                expires_at=row["expires_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            
            # Filter out expired permissions
            if not permission.is_expired():
                permissions.append(permission)
            else:
                # Clean up expired permission
                self.revoke_permission(user_id, permission.permission_scope, "system", "Expired")
        
        return permissions
    
    def request_permission(
        self,
        user_id: str,
        permission_scope: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Request permission from user (returns request data for confirmation flow).
        
        Args:
            user_id: User identifier
            permission_scope: Permission scope requested
            reason: Reason for requesting permission
            
        Returns:
            Dictionary with request details
        """
        request_id = f"perm_req_{user_id}_{permission_scope}_{int(time.time())}"
        
        request_data = {
            "request_id": request_id,
            "user_id": user_id,
            "permission_scope": permission_scope,
            "reason": reason,
            "requested_at": time.time(),
            "status": "pending",
        }
        
        # Log request
        self._log_audit(
            user_id=user_id,
            permission_scope=permission_scope,
            action="request",
            performed_by="system",
            reason=reason,
            metadata={"request_id": request_id},
        )
        
        logger.info(
            "permission_requested",
            user_id=user_id,
            permission_scope=permission_scope,
            request_id=request_id,
            reason=reason,
        )
        
        return request_data
    
    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get permission audit log.
        
        Args:
            user_id: Filter by user ID (None for all users)
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        cursor = self._conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT timestamp, user_id, permission_scope, action, performed_by, reason, metadata
                FROM permission_audit_log 
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            cursor.execute("""
                SELECT timestamp, user_id, permission_scope, action, performed_by, reason, metadata
                FROM permission_audit_log 
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
        
        entries = []
        for row in cursor.fetchall():
            entry = {
                "timestamp": row["timestamp"],
                "user_id": row["user_id"],
                "permission_scope": row["permission_scope"],
                "action": row["action"],
                "performed_by": row["performed_by"],
                "reason": row["reason"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            }
            entries.append(entry)
        
        return entries
    
    def clear_cache(self, user_id: Optional[str] = None) -> None:
        """
        Clear permission cache.
        
        Args:
            user_id: Clear cache for specific user (None for all users)
        """
        if user_id:
            if user_id in self._cache:
                del self._cache[user_id]
            if user_id in self._cache_timestamps:
                del self._cache_timestamps[user_id]
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
        
        logger.info("permission_cache_cleared", user_id=user_id)
    
    def _is_cache_valid(self, user_id: str) -> bool:
        """
        Check if cache is valid for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if cache is valid, False otherwise
        """
        if user_id not in self._cache_timestamps:
            return False
        
        age = time.time() - self._cache_timestamps[user_id]
        return age < self._cache_ttl
    
    def _get_permission_from_db(
        self,
        user_id: str,
        permission_scope: str,
    ) -> Optional[Permission]:
        """
        Get permission from database.
        
        Args:
            user_id: User identifier
            permission_scope: Permission scope
            
        Returns:
            Permission object or None if not found
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT user_id, permission_scope, granted_at, granted_by, expires_at, metadata
            FROM permissions 
            WHERE user_id = ? AND permission_scope = ?
        """, (user_id, permission_scope))
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        return Permission(
            user_id=row["user_id"],
            permission_scope=row["permission_scope"],
            granted_at=row["granted_at"],
            granted_by=row["granted_by"],
            expires_at=row["expires_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
    
    def _log_audit(
        self,
        user_id: str,
        permission_scope: str,
        action: str,
        performed_by: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log permission action to audit trail.
        
        Args:
            user_id: User identifier
            permission_scope: Permission scope
            action: Action performed (grant, revoke, request, check)
            performed_by: Who performed the action
            reason: Reason for action
            metadata: Additional metadata
        """
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO permission_audit_log 
            (timestamp, user_id, permission_scope, action, performed_by, reason, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            user_id,
            permission_scope,
            action,
            performed_by,
            reason,
            json.dumps(metadata) if metadata else None,
        ))
        self._conn.commit()
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("permission_database_closed")
    
    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()
