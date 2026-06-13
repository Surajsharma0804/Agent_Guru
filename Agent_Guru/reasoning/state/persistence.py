"""Conversation state persistence with SQLite.

This module implements async SQLite persistence for conversation state
with WAL mode for concurrent access.
"""

import asyncio
from pathlib import Path

import aiosqlite

from Agent_Guru.reasoning.models.conversation import ConversationState


class ConversationPersistence:
    """SQLite persistence for conversation state.

    Features:
    - WAL mode for concurrent access
    - Async operations with connection pooling
    - JSON serialization for complex types
    - Automatic schema creation
    """

    def __init__(self, db_path: str = "conversations.db", pool_size: int = 5) -> None:
        """Initialize persistence layer.

        Args:
            db_path: Path to SQLite database file
            pool_size: Maximum number of connections in pool

        """
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool: list[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database and connection pool."""
        if self._initialized:
            return

        # Create database directory if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create schema
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for concurrent access
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")

            # Create tables
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """,
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_id
                ON conversations(user_id)
            """,
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_updated_at
                ON conversations(updated_at)
            """,
            )

            await db.commit()

        self._initialized = True

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get connection from pool."""
        async with self._pool_lock:
            if self._pool:
                return self._pool.pop()

            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            return conn

    async def _return_connection(self, conn: aiosqlite.Connection) -> None:
        """Return connection to pool."""
        async with self._pool_lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
            else:
                await conn.close()

    async def save(self, state: ConversationState) -> None:
        """Save conversation state.

        Args:
            state: Conversation state to save

        """
        if not self._initialized:
            await self.initialize()

        conn = await self._get_connection()
        try:
            # Serialize state to JSON
            state_json = state.model_dump_json()

            await conn.execute(
                """
                INSERT OR REPLACE INTO conversations
                (conversation_id, user_id, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    state.conversation_id,
                    state.user_id,
                    state_json,
                    state.created_at.isoformat(),
                    state.updated_at.isoformat(),
                ),
            )
            await conn.commit()
        finally:
            await self._return_connection(conn)

    async def load(self, conversation_id: str) -> ConversationState | None:
        """Load conversation state.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            ConversationState if found, None otherwise

        """
        if not self._initialized:
            await self.initialize()

        conn = await self._get_connection()
        try:
            async with conn.execute(
                "SELECT state_json FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ) as cursor:
                row = await cursor.fetchone()

                if row is None:
                    return None

                # Deserialize from JSON
                return ConversationState.model_validate_json(row["state_json"])
        finally:
            await self._return_connection(conn)

    async def delete(self, conversation_id: str) -> bool:
        """Delete conversation state.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if deleted, False if not found

        """
        if not self._initialized:
            await self.initialize()

        conn = await self._get_connection()
        try:
            cursor = await conn.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await self._return_connection(conn)

    async def list_by_user(self, user_id: str, limit: int = 100) -> list[str]:
        """List conversation IDs for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of conversations to return

        Returns:
            List of conversation IDs

        """
        if not self._initialized:
            await self.initialize()

        conn = await self._get_connection()
        try:
            async with conn.execute(
                """
                SELECT conversation_id FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [row["conversation_id"] for row in rows]
        finally:
            await self._return_connection(conn)

    async def close(self) -> None:
        """Close all connections in pool."""
        async with self._pool_lock:
            for conn in self._pool:
                await conn.close()
            self._pool.clear()
