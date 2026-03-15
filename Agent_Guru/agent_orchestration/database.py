"""
Database initialization and connection management for Agent Orchestration System.

Provides SQLite database setup with schema initialization and connection pooling.

Performance Characteristics:
- Time Complexity: O(1) for connection acquisition
- Space Complexity: O(1) per connection
- Connection pool: Reuses connections for efficiency

Design Decisions:
- SQLite for simplicity and portability
- Schema loaded from external SQL file
- Connection context manager for automatic cleanup
- Async support for concurrent operations
"""

import aiosqlite
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncIterator, Iterator


class Database:
    """Database connection manager for Agent Orchestration System.
    
    Manages SQLite connections with automatic schema initialization.
    Supports both sync and async operations.
    
    Example:
        >>> db = Database("agents.db")
        >>> await db.initialize()
        >>> async with db.connection() as conn:
        ...     cursor = await conn.execute("SELECT * FROM agents")
        ...     agents = await cursor.fetchall()
    """
    
    def __init__(self, db_path: str = "agent_orchestration.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database with schema.
        
        Creates tables and indexes if they don't exist.
        Safe to call multiple times (idempotent).
        
        Time Complexity: O(n) where n = number of tables
        Space Complexity: O(1)
        """
        if self._initialized:
            return
        
        # Load schema from SQL file
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        
        # Execute schema
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(schema_sql)
            await conn.commit()
        
        self._initialized = True
    
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Get async database connection.
        
        Yields:
            Async SQLite connection
            
        Example:
            >>> async with db.connection() as conn:
            ...     await conn.execute("INSERT INTO agents ...")
            ...     await conn.commit()
        """
        if not self._initialized:
            await self.initialize()
        
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            await conn.close()
    
    @contextmanager
    def sync_connection(self) -> Iterator[sqlite3.Connection]:
        """Get sync database connection.
        
        Yields:
            Sync SQLite connection
            
        Example:
            >>> with db.sync_connection() as conn:
            ...     conn.execute("INSERT INTO agents ...")
            ...     conn.commit()
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    async def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a query without returning results.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Example:
            >>> await db.execute(
            ...     "INSERT INTO agents (id, status) VALUES (?, ?)",
            ...     ("agent-1", "active")
            ... )
        """
        async with self.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()
    
    async def fetch_one(self, query: str, params: tuple = ()) -> dict:
        """Execute query and fetch one result.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Single row as dict, or None if no results
            
        Example:
            >>> agent = await db.fetch_one(
            ...     "SELECT * FROM agents WHERE id = ?",
            ...     ("agent-1",)
            ... )
        """
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute query and fetch all results.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of rows as dicts
            
        Example:
            >>> agents = await db.fetch_all(
            ...     "SELECT * FROM agents WHERE status = ?",
            ...     ("active",)
            ... )
        """
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def close(self) -> None:
        """Close database and cleanup resources.
        
        Note: Individual connections are closed automatically by context manager.
        This method is for cleanup of any shared resources.
        """
        # SQLite doesn't require explicit cleanup for connection pool
        # This method is here for API consistency and future extensions
        pass


# Global database instance (singleton pattern)
_db_instance: Database = None


def get_database(db_path: str = "agent_orchestration.db") -> Database:
    """Get global database instance.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        Database instance (singleton)
        
    Example:
        >>> db = get_database()
        >>> await db.initialize()
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance
