"""
Unit tests for GURU Memory Service SQLite Database Foundation

Tests the comprehensive SQLite database foundation including:
- Database initialization and schema creation
- Connection pooling and transaction management
- Database migration system with version control
- Thread-safe operations
- Comprehensive error handling and logging
- Security features (SQL injection prevention, connection security)
- Performance optimization (indexing, connection pooling)
"""

import pytest
import tempfile
import os
import threading
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from src.memory.database import (
    DatabaseManager, DatabaseConfig, DatabaseMigrator, 
    DatabaseConnectionPool, DatabaseError, MigrationError, ConnectionPoolError
)
from src.memory.memory_types import CoreMemory, DataType


class TestDatabaseConfig:
    """Test database configuration."""
    
    def test_database_config_creation(self):
        """Test database configuration creation with default values."""
        config = DatabaseConfig(db_path="test.db")
        
        assert config.db_path == "test.db"
        assert config.max_connections == 10
        assert config.connection_timeout == 30.0
        assert config.enable_wal_mode is True
        assert config.enable_foreign_keys is True
        assert config.page_size == 4096
        assert config.cache_size == -64000
        assert config.temp_store == "memory"
        assert config.synchronous == "NORMAL"
        assert config.journal_mode == "WAL"
        assert config.auto_vacuum == "INCREMENTAL"
    
    def test_database_config_custom_values(self):
        """Test database configuration with custom values."""
        config = DatabaseConfig(
            db_path="custom.db",
            max_connections=5,
            connection_timeout=15.0,
            enable_wal_mode=False,
            page_size=8192
        )
        
        assert config.db_path == "custom.db"
        assert config.max_connections == 5
        assert config.connection_timeout == 15.0
        assert config.enable_wal_mode is False
        assert config.page_size == 8192


class TestDatabaseConnectionPool:
    """Test database connection pool functionality."""
    
    def test_connection_pool_initialization(self):
        """Test connection pool initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path, max_connections=3)
            
            pool = DatabaseConnectionPool(config)
            
            assert pool.config.max_connections == 3
            assert pool._active_connections >= 0
            assert not pool._shutdown
            
            pool.shutdown()
    
    def test_connection_acquisition_and_release(self):
        """Test connection acquisition and release."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path, max_connections=2)
            
            pool = DatabaseConnectionPool(config)
            
            # Test connection acquisition
            with pool.get_connection() as conn:
                assert conn is not None
                # Test basic query
                result = conn.execute("SELECT 1").fetchone()
                assert result[0] == 1
            
            pool.shutdown()
    
    def test_concurrent_connections(self):
        """Test concurrent connection handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path, max_connections=3)
            
            pool = DatabaseConnectionPool(config)
            results = []
            errors = []
            
            def worker():
                try:
                    with pool.get_connection() as conn:
                        result = conn.execute("SELECT 1").fetchone()
                        results.append(result[0])
                        time.sleep(0.1)  # Simulate work
                except Exception as e:
                    errors.append(e)
            
            # Start multiple threads
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=worker)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            assert len(errors) == 0
            assert len(results) == 5
            assert all(r == 1 for r in results)
            
            pool.shutdown()


class TestDatabaseMigrator:
    """Test database migration system."""
    
    def test_migration_table_creation(self):
        """Test migration tracking table creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            pool = DatabaseConnectionPool(config)
            migrator = DatabaseMigrator(pool)
            
            # Check migration table exists
            with pool.get_connection() as conn:
                result = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='schema_migrations'
                """).fetchone()
                assert result is not None
            
            pool.shutdown()
    
    def test_migration_application(self):
        """Test migration application."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            pool = DatabaseConnectionPool(config)
            migrator = DatabaseMigrator(pool)
            
            # Apply test migration
            test_sql = """
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                );
            """
            
            migrator.apply_migration(1, "test_migration", "Test migration", test_sql)
            
            # Verify migration was applied
            assert migrator.get_current_version() == 1
            
            history = migrator.get_migration_history()
            assert len(history) == 1
            assert history[0].version == 1
            assert history[0].name == "test_migration"
            
            # Verify table was created
            with pool.get_connection() as conn:
                result = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='test_table'
                """).fetchone()
                assert result is not None
            
            pool.shutdown()
    
    def test_migration_version_validation(self):
        """Test migration version validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            pool = DatabaseConnectionPool(config)
            migrator = DatabaseMigrator(pool)
            
            # Try to apply non-sequential migration
            with pytest.raises(MigrationError):
                migrator.apply_migration(3, "invalid", "Invalid migration", "SELECT 1;")
            
            pool.shutdown()
    
    def test_migration_integrity_verification(self):
        """Test migration integrity verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            pool = DatabaseConnectionPool(config)
            migrator = DatabaseMigrator(pool)
            
            # Apply sequential migrations
            migrator.apply_migration(1, "migration_1", "First migration", "CREATE TABLE t1 (id INTEGER);")
            migrator.apply_migration(2, "migration_2", "Second migration", "CREATE TABLE t2 (id INTEGER);")
            
            # Verify integrity
            assert migrator.verify_migration_integrity() is True
            
            pool.shutdown()


class TestDatabaseManager:
    """Test database manager functionality."""
    
    def test_database_manager_initialization(self):
        """Test database manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            assert db_manager.config == config
            assert db_manager.pool is not None
            assert db_manager.migrator is not None
            
            # Verify initial migrations were applied
            current_version = db_manager.migrator.get_current_version()
            assert current_version >= 3  # Should have applied initial migrations
            
            db_manager.shutdown()
    
    def test_database_schema_creation(self):
        """Test that all required tables are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            expected_tables = [
                'core_memory', 'episodic_memory', 'semantic_memory',
                'procedural_memory', 'resource_memory', 'knowledge_vault',
                'memory_access_log', 'retention_policies', 'vector_search_index',
                'system_metadata', 'schema_migrations'
            ]
            
            with db_manager.get_connection() as conn:
                for table in expected_tables:
                    result = conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name=?
                    """, (table,)).fetchone()
                    assert result is not None, f"Table {table} not found"
            
            db_manager.shutdown()
    
    def test_database_statistics(self):
        """Test database statistics collection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            stats = db_manager.get_database_stats()
            
            # Check required statistics
            assert 'core_memory_count' in stats
            assert 'episodic_memory_count' in stats
            assert 'semantic_memory_count' in stats
            assert 'procedural_memory_count' in stats
            assert 'resource_memory_count' in stats
            assert 'knowledge_vault_count' in stats
            assert 'database_size_bytes' in stats
            assert 'active_connections' in stats
            assert 'max_connections' in stats
            
            # Verify initial counts are zero
            assert stats['core_memory_count'] == 0
            assert stats['episodic_memory_count'] == 0
            
            db_manager.shutdown()
    
    def test_database_integrity_verification(self):
        """Test database integrity verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            # Verify integrity
            assert db_manager.verify_integrity() is True
            
            db_manager.shutdown()
    
    def test_transaction_management(self):
        """Test transaction management."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            # Test successful transaction
            with db_manager.transaction() as conn:
                conn.execute("""
                    INSERT INTO core_memory (key, value, data_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, ('test_key', 'test_value', 'string', 
                      datetime.now(timezone.utc).isoformat(),
                      datetime.now(timezone.utc).isoformat()))
            
            # Verify data was committed
            result = db_manager.execute_query(
                "SELECT COUNT(*) as count FROM core_memory WHERE key = ?", 
                ('test_key',)
            )
            assert result[0]['count'] == 1
            
            # Test transaction rollback
            try:
                with db_manager.transaction() as conn:
                    conn.execute("""
                        INSERT INTO core_memory (key, value, data_type, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, ('test_key2', 'test_value2', 'string',
                          datetime.now(timezone.utc).isoformat(),
                          datetime.now(timezone.utc).isoformat()))
                    # Force an error to trigger rollback
                    raise Exception("Test rollback")
            except Exception:
                pass
            
            # Verify rollback occurred
            result = db_manager.execute_query(
                "SELECT COUNT(*) as count FROM core_memory WHERE key = ?", 
                ('test_key2',)
            )
            assert result[0]['count'] == 0
            
            db_manager.shutdown()
    
    def test_query_execution(self):
        """Test query execution methods."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            # Test insert
            affected_rows = db_manager.execute_update("""
                INSERT INTO core_memory (key, value, data_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, ('test_key', 'test_value', 'string',
                  datetime.now(timezone.utc).isoformat(),
                  datetime.now(timezone.utc).isoformat()))
            
            assert affected_rows == 1
            
            # Test select
            results = db_manager.execute_query(
                "SELECT key, value FROM core_memory WHERE key = ?", 
                ('test_key',)
            )
            
            assert len(results) == 1
            assert results[0]['key'] == 'test_key'
            assert results[0]['value'] == 'test_value'
            
            # Test update
            affected_rows = db_manager.execute_update(
                "UPDATE core_memory SET value = ? WHERE key = ?",
                ('updated_value', 'test_key')
            )
            
            assert affected_rows == 1
            
            # Test delete
            affected_rows = db_manager.execute_update(
                "DELETE FROM core_memory WHERE key = ?",
                ('test_key',)
            )
            
            assert affected_rows == 1
            
            db_manager.shutdown()


class TestDatabaseSecurity:
    """Test database security features."""
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention through parameterized queries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            # Insert test data
            db_manager.execute_update("""
                INSERT INTO core_memory (key, value, data_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, ('safe_key', 'safe_value', 'string',
                  datetime.now(timezone.utc).isoformat(),
                  datetime.now(timezone.utc).isoformat()))
            
            # Attempt SQL injection (should be safely handled by parameterized query)
            malicious_input = "'; DROP TABLE core_memory; --"
            results = db_manager.execute_query(
                "SELECT * FROM core_memory WHERE key = ?",
                (malicious_input,)
            )
            
            # Should return no results (injection prevented)
            assert len(results) == 0
            
            # Verify table still exists
            results = db_manager.execute_query("SELECT COUNT(*) as count FROM core_memory")
            assert results[0]['count'] == 1
            
            db_manager.shutdown()
    
    def test_connection_security_settings(self):
        """Test that connections have proper security settings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path, enable_foreign_keys=True)
            
            pool = DatabaseConnectionPool(config)
            
            with pool.get_connection() as conn:
                # Check foreign keys are enabled
                result = conn.execute("PRAGMA foreign_keys").fetchone()
                assert result[0] == 1
                
                # Check WAL mode is enabled
                result = conn.execute("PRAGMA journal_mode").fetchone()
                assert result[0] == "wal"
                
                # Check synchronous mode
                result = conn.execute("PRAGMA synchronous").fetchone()
                assert result[0] == 1  # NORMAL
            
            pool.shutdown()


class TestDatabasePerformance:
    """Test database performance optimizations."""
    
    def test_database_indexes(self):
        """Test that required indexes are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            # Check for key indexes
            with db_manager.get_connection() as conn:
                # Check core_memory indexes
                result = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND tbl_name='core_memory'
                """).fetchall()
                
                index_names = [row['name'] for row in result]
                assert 'idx_core_memory_key' in index_names
                assert 'idx_core_memory_updated_at' in index_names
                
                # Check episodic_memory indexes
                result = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND tbl_name='episodic_memory'
                """).fetchall()
                
                index_names = [row['name'] for row in result]
                assert 'idx_episodic_event_id' in index_names
                assert 'idx_episodic_occurred_at' in index_names
            
            db_manager.shutdown()
    
    def test_connection_pool_performance(self):
        """Test connection pool performance under load."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path, max_connections=5)
            
            pool = DatabaseConnectionPool(config)
            
            start_time = time.time()
            
            def worker():
                with pool.get_connection() as conn:
                    conn.execute("SELECT 1").fetchone()
            
            # Simulate concurrent load
            threads = []
            for _ in range(20):
                thread = threading.Thread(target=worker)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete reasonably quickly (under 5 seconds)
            assert execution_time < 5.0
            
            pool.shutdown()


class TestDatabaseErrorHandling:
    """Test database error handling."""
    
    def test_connection_failure_handling(self):
        """
        Test handling of connection failures.
        
        CRITICAL SECURITY FIX: Test actual connection failures, not just invalid paths
        that get auto-created. Use a path that will definitely fail on Windows.
        """
        # Test with a path that cannot be created (invalid characters on Windows)
        invalid_path = "CON:/invalid<>path/test.db"  # CON is reserved on Windows
        config = DatabaseConfig(db_path=invalid_path)
        
        with pytest.raises((ConnectionPoolError, OSError, sqlite3.OperationalError)):
            DatabaseConnectionPool(config)
    
    def test_migration_failure_handling(self):
        """Test handling of migration failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            pool = DatabaseConnectionPool(config)
            migrator = DatabaseMigrator(pool)
            
            try:
                # Test invalid SQL migration
                with pytest.raises(MigrationError):
                    migrator.apply_migration(1, "invalid", "Invalid SQL", "INVALID SQL STATEMENT;")
            finally:
                # CRITICAL FIX: Ensure proper resource cleanup
                # Shutdown pool and force garbage collection to release file handles
                pool.shutdown()
                import gc
                gc.collect()  # Force garbage collection to release any remaining references
    
    def test_transaction_failure_handling(self):
        """Test transaction failure handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            config = DatabaseConfig(db_path=db_path)
            
            db_manager = DatabaseManager(config)
            
            # Test transaction rollback on error
            with pytest.raises(Exception):
                with db_manager.transaction() as conn:
                    conn.execute("""
                        INSERT INTO core_memory (key, value, data_type, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, ('test_key', 'test_value', 'string',
                          datetime.now(timezone.utc).isoformat(),
                          datetime.now(timezone.utc).isoformat()))
                    
                    # Force constraint violation
                    conn.execute("""
                        INSERT INTO core_memory (key, value, data_type, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, ('test_key', 'duplicate_value', 'string',  # Duplicate key
                          datetime.now(timezone.utc).isoformat(),
                          datetime.now(timezone.utc).isoformat()))
            
            # Verify rollback occurred
            result = db_manager.execute_query(
                "SELECT COUNT(*) as count FROM core_memory WHERE key = ?",
                ('test_key',)
            )
            assert result[0]['count'] == 0
            
            db_manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])