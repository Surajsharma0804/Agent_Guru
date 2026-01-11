"""
Database Foundation for GURU Memory Service

Implements SQLite database foundation with:
- Optimized schema for six memory types
- Connection pooling and transaction management
- Database migration system with version control
- Thread-safe operations
- Comprehensive error handling and logging
"""

import sqlite3
import threading
import logging
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
import queue
import time

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration with security and performance settings."""
    db_path: str
    max_connections: int = 10
    connection_timeout: float = 30.0
    enable_wal_mode: bool = True
    enable_foreign_keys: bool = True
    page_size: int = 4096
    cache_size: int = -64000  # 64MB cache
    temp_store: str = "memory"
    synchronous: str = "NORMAL"
    journal_mode: str = "WAL"
    auto_vacuum: str = "INCREMENTAL"


@dataclass
class MigrationRecord:
    """Database migration record for version control."""
    version: int
    name: str
    description: str
    applied_at: datetime
    checksum: str
    execution_time_ms: int


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class MigrationError(DatabaseError):
    """Exception for database migration failures."""
    pass


class ConnectionPoolError(DatabaseError):
    """Exception for connection pool issues."""
    pass


class DatabaseConnectionPool:
    """
    Thread-safe SQLite connection pool with automatic connection management.
    
    Provides:
    - Connection pooling with configurable limits
    - Automatic connection lifecycle management
    - Thread-safe operations
    - Connection health monitoring
    - Graceful degradation on connection failures
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool = queue.Queue(maxsize=config.max_connections)
        self._active_connections = 0
        self._lock = threading.RLock()
        self._shutdown = False
        
        # Initialize connection pool
        self._initialize_pool()
        
    def _initialize_pool(self) -> None:
        """Initialize the connection pool with configured connections."""
        try:
            # Ensure database directory exists
            db_dir = Path(self.config.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Create initial connections
            for _ in range(min(2, self.config.max_connections)):
                conn = self._create_connection()
                self._pool.put(conn, block=False)
                
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise ConnectionPoolError(f"Pool initialization failed: {e}")
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with optimized settings."""
        try:
            conn = sqlite3.connect(
                self.config.db_path,
                timeout=self.config.connection_timeout,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode for explicit transaction control
            )
            
            # Configure connection for performance and security
            conn.execute("PRAGMA foreign_keys = ON" if self.config.enable_foreign_keys else "PRAGMA foreign_keys = OFF")
            conn.execute(f"PRAGMA page_size = {self.config.page_size}")
            conn.execute(f"PRAGMA cache_size = {self.config.cache_size}")
            conn.execute(f"PRAGMA temp_store = {self.config.temp_store}")
            conn.execute(f"PRAGMA synchronous = {self.config.synchronous}")
            conn.execute(f"PRAGMA journal_mode = {self.config.journal_mode}")
            conn.execute(f"PRAGMA auto_vacuum = {self.config.auto_vacuum}")
            
            # Enable row factory for dict-like access
            conn.row_factory = sqlite3.Row
            
            with self._lock:
                self._active_connections += 1
                
            logger.debug(f"Created new database connection (active: {self._active_connections})")
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise ConnectionPoolError(f"Connection creation failed: {e}")
    
    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool with automatic cleanup.
        
        Yields:
            sqlite3.Connection: Database connection
            
        Raises:
            ConnectionPoolError: If connection cannot be obtained
        """
        if self._shutdown:
            raise ConnectionPoolError("Connection pool is shutdown")
            
        conn = None
        try:
            # Try to get existing connection from pool
            try:
                conn = self._pool.get(block=False)
            except queue.Empty:
                # Create new connection if pool is empty and under limit
                with self._lock:
                    if self._active_connections < self.config.max_connections:
                        conn = self._create_connection()
                    else:
                        # Wait for available connection
                        conn = self._pool.get(timeout=self.config.connection_timeout)
            
            # Verify connection health
            if not self._is_connection_healthy(conn):
                self._close_connection(conn)
                conn = self._create_connection()
                
            yield conn
            
        except Exception as e:
            logger.error(f"Connection pool error: {e}")
            if conn:
                self._close_connection(conn)
            raise ConnectionPoolError(f"Failed to get connection: {e}")
        finally:
            # Return connection to pool if healthy
            if conn and not self._shutdown:
                if self._is_connection_healthy(conn):
                    try:
                        self._pool.put(conn, block=False)
                    except queue.Full:
                        # Pool is full, close connection
                        self._close_connection(conn)
                else:
                    self._close_connection(conn)
    
    def _is_connection_healthy(self, conn: sqlite3.Connection) -> bool:
        """Check if connection is healthy and responsive."""
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False
    
    def _close_connection(self, conn: sqlite3.Connection) -> None:
        """Close a database connection and update counters."""
        try:
            conn.close()
            with self._lock:
                self._active_connections = max(0, self._active_connections - 1)
            logger.debug(f"Closed database connection (active: {self._active_connections})")
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
    
    def shutdown(self) -> None:
        """Shutdown the connection pool and close all connections."""
        self._shutdown = True
        
        # Close all pooled connections
        while True:
            try:
                conn = self._pool.get(block=False)
                self._close_connection(conn)
            except queue.Empty:
                break
                
        logger.info("Database connection pool shutdown complete")


class DatabaseMigrator:
    """
    Database migration system with version control and integrity verification.
    
    Features:
    - Sequential migration execution
    - Migration integrity verification with checksums
    - Rollback capabilities for failed migrations
    - Comprehensive migration logging
    - Atomic migration transactions
    """
    
    def __init__(self, pool: DatabaseConnectionPool):
        self.pool = pool
        self._ensure_migration_table()
    
    def _ensure_migration_table(self) -> None:
        """Ensure migration tracking table exists."""
        with self.pool.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT NOT NULL,
                    execution_time_ms INTEGER NOT NULL
                )
            """)
            conn.commit()
    
    def get_current_version(self) -> int:
        """Get the current database schema version."""
        with self.pool.get_connection() as conn:
            result = conn.execute(
                "SELECT MAX(version) as version FROM schema_migrations"
            ).fetchone()
            return result['version'] if result['version'] is not None else 0
    
    def get_migration_history(self) -> List[MigrationRecord]:
        """Get complete migration history."""
        with self.pool.get_connection() as conn:
            rows = conn.execute("""
                SELECT version, name, description, applied_at, checksum, execution_time_ms
                FROM schema_migrations 
                ORDER BY version
            """).fetchall()
            
            return [
                MigrationRecord(
                    version=row['version'],
                    name=row['name'],
                    description=row['description'],
                    applied_at=datetime.fromisoformat(row['applied_at']),
                    checksum=row['checksum'],
                    execution_time_ms=row['execution_time_ms']
                )
                for row in rows
            ]
    
    def apply_migration(self, version: int, name: str, description: str, sql: str) -> None:
        """
        Apply a database migration with integrity verification.
        
        Args:
            version: Migration version number
            name: Migration name
            description: Migration description
            sql: SQL statements to execute
            
        Raises:
            MigrationError: If migration fails or version conflict
        """
        current_version = self.get_current_version()
        
        if version <= current_version:
            raise MigrationError(f"Migration version {version} already applied (current: {current_version})")
        
        if version != current_version + 1:
            raise MigrationError(f"Migration version {version} is not sequential (expected: {current_version + 1})")
        
        # Calculate migration checksum
        checksum = hashlib.sha256(sql.encode('utf-8')).hexdigest()
        
        start_time = time.time()
        
        with self.pool.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Execute migration SQL
                conn.executescript(sql)
                
                # Record migration
                execution_time_ms = int((time.time() - start_time) * 1000)
                conn.execute("""
                    INSERT INTO schema_migrations 
                    (version, name, description, applied_at, checksum, execution_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    version, name, description, 
                    datetime.now(timezone.utc).isoformat(),
                    checksum, execution_time_ms
                ))
                
                conn.commit()
                logger.info(f"Applied migration {version}: {name} ({execution_time_ms}ms)")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Migration {version} failed: {e}")
                raise MigrationError(f"Migration {version} failed: {e}")
    
    def verify_migration_integrity(self) -> bool:
        """Verify integrity of all applied migrations."""
        try:
            migrations = self.get_migration_history()
            
            # Verify sequential versions
            for i, migration in enumerate(migrations):
                expected_version = i + 1
                if migration.version != expected_version:
                    logger.error(f"Migration version gap: expected {expected_version}, got {migration.version}")
                    return False
            
            logger.info(f"Migration integrity verified: {len(migrations)} migrations")
            return True
            
        except Exception as e:
            logger.error(f"Migration integrity check failed: {e}")
            return False


class DatabaseManager:
    """
    Main database manager for GURU Memory Service.
    
    Provides:
    - High-level database operations
    - Schema management and migrations
    - Connection pool management
    - Transaction management
    - Performance monitoring
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool = DatabaseConnectionPool(config)
        self.migrator = DatabaseMigrator(self.pool)
        self._initialize_schema()
    
    def _initialize_schema(self) -> None:
        """Initialize database schema with all required tables."""
        try:
            self._apply_initial_migrations()
            logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            raise DatabaseError(f"Schema initialization failed: {e}")
    
    def _apply_initial_migrations(self) -> None:
        """Apply initial database migrations for MIRIX architecture."""
        
        # Migration 1: Core tables and indexes
        migration_1_sql = """
        -- Core Memory: Persistent user preferences and identity
        CREATE TABLE IF NOT EXISTS core_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            data_type TEXT NOT NULL CHECK (data_type IN ('string', 'integer', 'float', 'boolean', 'json')),
            encrypted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            version INTEGER NOT NULL DEFAULT 1
        );
        
        CREATE INDEX IF NOT EXISTS idx_core_memory_key ON core_memory(key);
        CREATE INDEX IF NOT EXISTS idx_core_memory_updated_at ON core_memory(updated_at);
        
        -- Episodic Memory: Time-based activities and events
        CREATE TABLE IF NOT EXISTS episodic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            summary TEXT NOT NULL,
            details TEXT,
            participants TEXT, -- JSON array
            location TEXT,
            tags TEXT, -- JSON array
            confidence_score REAL NOT NULL DEFAULT 1.0,
            encrypted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            occurred_at TIMESTAMP NOT NULL,
            retention_policy TEXT NOT NULL DEFAULT 'short_term',
            vector_embedding BLOB -- For similarity search
        );
        
        CREATE INDEX IF NOT EXISTS idx_episodic_event_id ON episodic_memory(event_id);
        CREATE INDEX IF NOT EXISTS idx_episodic_occurred_at ON episodic_memory(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_episodic_retention ON episodic_memory(retention_policy);
        CREATE INDEX IF NOT EXISTS idx_episodic_tags ON episodic_memory(tags);
        
        -- Semantic Memory: General knowledge and concepts
        CREATE TABLE IF NOT EXISTS semantic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_id TEXT NOT NULL UNIQUE,
            concept_name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            relationships TEXT, -- JSON object
            confidence_score REAL NOT NULL DEFAULT 1.0,
            usage_count INTEGER NOT NULL DEFAULT 0,
            last_accessed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            encrypted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            vector_embedding BLOB
        );
        
        CREATE INDEX IF NOT EXISTS idx_semantic_concept_id ON semantic_memory(concept_id);
        CREATE INDEX IF NOT EXISTS idx_semantic_concept_name ON semantic_memory(concept_name);
        CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic_memory(category);
        CREATE INDEX IF NOT EXISTS idx_semantic_last_accessed ON semantic_memory(last_accessed);
        
        -- Procedural Memory: Workflows and step-by-step processes
        CREATE TABLE IF NOT EXISTS procedural_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procedure_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            steps TEXT NOT NULL, -- JSON array of steps
            prerequisites TEXT, -- JSON array
            success_criteria TEXT, -- JSON array
            failure_handling TEXT, -- JSON object
            execution_count INTEGER NOT NULL DEFAULT 0,
            success_rate REAL NOT NULL DEFAULT 0.0,
            average_duration_ms INTEGER,
            last_executed TIMESTAMP,
            encrypted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            vector_embedding BLOB
        );
        
        CREATE INDEX IF NOT EXISTS idx_procedural_procedure_id ON procedural_memory(procedure_id);
        CREATE INDEX IF NOT EXISTS idx_procedural_name ON procedural_memory(name);
        CREATE INDEX IF NOT EXISTS idx_procedural_last_executed ON procedural_memory(last_executed);
        CREATE INDEX IF NOT EXISTS idx_procedural_success_rate ON procedural_memory(success_rate);
        """
        
        if self.migrator.get_current_version() < 1:
            self.migrator.apply_migration(
                version=1,
                name="initial_core_tables",
                description="Create core memory tables for MIRIX architecture",
                sql=migration_1_sql
            )
        
        # Migration 2: Resource and Knowledge Vault tables
        migration_2_sql = """
        -- Resource Memory: Documents and active files
        CREATE TABLE IF NOT EXISTS resource_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            resource_type TEXT NOT NULL CHECK (resource_type IN ('file', 'document', 'url', 'reference')),
            path TEXT,
            content_hash TEXT,
            metadata TEXT, -- JSON object
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER,
            mime_type TEXT,
            encrypted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            retention_policy TEXT NOT NULL DEFAULT 'long_term',
            vector_embedding BLOB
        );
        
        CREATE INDEX IF NOT EXISTS idx_resource_resource_id ON resource_memory(resource_id);
        CREATE INDEX IF NOT EXISTS idx_resource_name ON resource_memory(name);
        CREATE INDEX IF NOT EXISTS idx_resource_type ON resource_memory(resource_type);
        CREATE INDEX IF NOT EXISTS idx_resource_last_accessed ON resource_memory(last_accessed);
        CREATE INDEX IF NOT EXISTS idx_resource_content_hash ON resource_memory(content_hash);
        
        -- Knowledge Vault: Encrypted sensitive data (credentials, contacts)
        CREATE TABLE IF NOT EXISTS knowledge_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            vault_type TEXT NOT NULL CHECK (vault_type IN ('credential', 'contact', 'secret', 'token')),
            encrypted_data BLOB NOT NULL, -- Always encrypted
            metadata TEXT, -- JSON object (non-sensitive metadata only)
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            access_policy TEXT NOT NULL DEFAULT 'strict' -- strict, normal, relaxed
        );
        
        CREATE INDEX IF NOT EXISTS idx_vault_vault_id ON knowledge_vault(vault_id);
        CREATE INDEX IF NOT EXISTS idx_vault_name ON knowledge_vault(name);
        CREATE INDEX IF NOT EXISTS idx_vault_type ON knowledge_vault(vault_type);
        CREATE INDEX IF NOT EXISTS idx_vault_expires_at ON knowledge_vault(expires_at);
        CREATE INDEX IF NOT EXISTS idx_vault_access_policy ON knowledge_vault(access_policy);
        
        -- Memory Access Log: Audit trail for all memory operations
        CREATE TABLE IF NOT EXISTS memory_access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id TEXT NOT NULL UNIQUE,
            memory_type TEXT NOT NULL CHECK (memory_type IN ('core', 'episodic', 'semantic', 'procedural', 'resource', 'vault')),
            operation_type TEXT NOT NULL CHECK (operation_type IN ('create', 'read', 'update', 'delete', 'search')),
            record_id TEXT NOT NULL,
            user_context TEXT, -- JSON object
            success BOOLEAN NOT NULL,
            error_message TEXT,
            execution_time_ms INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_access_log_operation_id ON memory_access_log(operation_id);
        CREATE INDEX IF NOT EXISTS idx_access_log_memory_type ON memory_access_log(memory_type);
        CREATE INDEX IF NOT EXISTS idx_access_log_operation_type ON memory_access_log(operation_type);
        CREATE INDEX IF NOT EXISTS idx_access_log_created_at ON memory_access_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_access_log_success ON memory_access_log(success);
        """
        
        if self.migrator.get_current_version() < 2:
            self.migrator.apply_migration(
                version=2,
                name="resource_vault_tables",
                description="Create resource memory and knowledge vault tables",
                sql=migration_2_sql
            )
        
        # Migration 3: Retention policies and cleanup tables
        migration_3_sql = """
        -- Retention Policies: Configurable data lifecycle management
        CREATE TABLE IF NOT EXISTS retention_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_name TEXT NOT NULL UNIQUE,
            memory_type TEXT NOT NULL,
            max_age_days INTEGER,
            max_records INTEGER,
            cleanup_strategy TEXT NOT NULL CHECK (cleanup_strategy IN ('oldest_first', 'least_accessed', 'lowest_confidence')),
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_retention_policy_name ON retention_policies(policy_name);
        CREATE INDEX IF NOT EXISTS idx_retention_memory_type ON retention_policies(memory_type);
        CREATE INDEX IF NOT EXISTS idx_retention_enabled ON retention_policies(enabled);
        
        -- Vector Search Index: For similarity search operations
        CREATE TABLE IF NOT EXISTS vector_search_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            vector_hash TEXT NOT NULL,
            dimension_count INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_vector_memory_type ON vector_search_index(memory_type);
        CREATE INDEX IF NOT EXISTS idx_vector_record_id ON vector_search_index(record_id);
        CREATE INDEX IF NOT EXISTS idx_vector_hash ON vector_search_index(vector_hash);
        
        -- System Metadata: Database configuration and status
        CREATE TABLE IF NOT EXISTS system_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            data_type TEXT NOT NULL CHECK (data_type IN ('string', 'integer', 'float', 'boolean', 'json')),
            description TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Insert initial system metadata
        INSERT OR IGNORE INTO system_metadata (key, value, data_type, description) VALUES
        ('schema_version', '3', 'integer', 'Current database schema version'),
        ('created_at', datetime('now'), 'string', 'Database creation timestamp'),
        ('encryption_enabled', 'true', 'boolean', 'Whether encryption is enabled'),
        ('vector_search_enabled', 'true', 'boolean', 'Whether vector search is enabled'),
        ('retention_enabled', 'true', 'boolean', 'Whether retention policies are enabled');
        """
        
        if self.migrator.get_current_version() < 3:
            self.migrator.apply_migration(
                version=3,
                name="retention_vector_search",
                description="Add retention policies and vector search support",
                sql=migration_3_sql
            )
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool."""
        with self.pool.get_connection() as conn:
            yield conn
    
    @contextmanager
    def transaction(self):
        """Execute operations within a database transaction."""
        with self.pool.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results."""
        with self.get_connection() as conn:
            return conn.execute(query, params).fetchall()
    
    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        with self.get_connection() as conn:
            stats = {}
            
            # Table row counts
            tables = [
                'core_memory', 'episodic_memory', 'semantic_memory',
                'procedural_memory', 'resource_memory', 'knowledge_vault',
                'memory_access_log', 'retention_policies', 'vector_search_index'
            ]
            
            for table in tables:
                try:
                    result = conn.execute(f"SELECT COUNT(*) as count FROM {table}").fetchone()
                    stats[f"{table}_count"] = result['count']
                except Exception as e:
                    stats[f"{table}_count"] = f"Error: {e}"
            
            # Database size
            try:
                result = conn.execute("PRAGMA page_count").fetchone()
                page_count = result[0] if result else 0
                result = conn.execute("PRAGMA page_size").fetchone()
                page_size = result[0] if result else 0
                stats['database_size_bytes'] = page_count * page_size
            except Exception as e:
                stats['database_size_bytes'] = f"Error: {e}"
            
            # Connection pool stats
            stats['active_connections'] = self.pool._active_connections
            stats['max_connections'] = self.config.max_connections
            
            return stats
    
    def verify_integrity(self) -> bool:
        """Verify database integrity."""
        try:
            with self.get_connection() as conn:
                # Check database integrity
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result[0] != "ok":
                    logger.error(f"Database integrity check failed: {result[0]}")
                    return False
                
                # Verify migration integrity
                if not self.migrator.verify_migration_integrity():
                    return False
                
                logger.info("Database integrity verification passed")
                return True
                
        except Exception as e:
            logger.error(f"Database integrity verification failed: {e}")
            return False
    
    def shutdown(self) -> None:
        """Shutdown database manager and close all connections."""
        try:
            self.pool.shutdown()
            logger.info("Database manager shutdown complete")
        except Exception as e:
            logger.error(f"Database shutdown error: {e}")