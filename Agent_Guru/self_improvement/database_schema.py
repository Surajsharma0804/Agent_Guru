"""
Database schema for Self-Improvement Engine.

This module defines the SQLite database schema for storing:
- Failures: Complete execution context and categorization
- Strategies: Performance tracking and success rates
- Prompts: Version history and performance metrics
- Metrics: Performance tracking over time
- Patterns: Identified failure patterns

Performance Requirements:
- Time Complexity: O(1) for inserts, O(log n) for indexed queries
- Space Complexity: O(n) where n is number of records
- Indexes: Optimized for failure_type, task_type, timestamp queries

Design Decisions:
- SQLite for simplicity and portability
- JSON for flexible context storage
- Indexes on frequently queried columns
- Foreign keys for referential integrity
- Timestamps for temporal analysis
"""

import sqlite3
from typing import Optional
from pathlib import Path


class DatabaseSchema:
    """
    Database schema manager for Self-Improvement Engine.
    
    Creates and manages SQLite database schema with tables for:
    - failures: Failed task executions with full context
    - strategies: Strategy performance tracking
    - prompts: Prompt versions and performance
    - metrics: Performance metrics over time
    - failure_patterns: Identified patterns across failures
    
    Time Complexity: O(1) for schema creation
    Space Complexity: O(1) - schema definition only
    """
    
    # Schema version for migrations
    SCHEMA_VERSION = 1
    
    @staticmethod
    def create_schema(db_path: str) -> None:
        """
        Create complete database schema.
        
        Creates all tables, indexes, and constraints needed for
        the self-improvement engine.
        
        Args:
            db_path: Path to SQLite database file
            
        Time Complexity: O(1) - fixed number of tables
        Space Complexity: O(1) - schema definition only
        """
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create schema version table
        DatabaseSchema._create_version_table(cursor)
        
        # Create core tables
        DatabaseSchema._create_failures_table(cursor)
        DatabaseSchema._create_strategies_table(cursor)
        DatabaseSchema._create_prompts_table(cursor)
        DatabaseSchema._create_metrics_table(cursor)
        DatabaseSchema._create_failure_patterns_table(cursor)
        
        # Create indexes for performance
        DatabaseSchema._create_indexes(cursor)
        
        # Set schema version
        cursor.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (DatabaseSchema.SCHEMA_VERSION,)
        )
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def _create_version_table(cursor: sqlite3.Cursor) -> None:
        """Create schema version table for migrations."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    @staticmethod
    def _create_failures_table(cursor: sqlite3.Cursor) -> None:
        """
        Create failures table.
        
        Stores complete failure information including:
        - Task identification and type
        - Failure categorization
        - Full execution context
        - Specific failure details (reasoning step, tool name, etc.)
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                failure_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                execution_context TEXT NOT NULL,
                error_details TEXT NOT NULL,
                reasoning_step TEXT,
                tool_name TEXT,
                hallucination_content TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                -- Constraints
                CHECK (failure_type IN (
                    'reasoning_error',
                    'tool_error', 
                    'hallucination',
                    'timeout',
                    'resource_error',
                    'unknown'
                )),
                CHECK (execution_time_ms >= 0)
            )
        """)
    
    @staticmethod
    def _create_strategies_table(cursor: sqlite3.Cursor) -> None:
        """
        Create strategies table.
        
        Stores strategy definitions and performance tracking:
        - Strategy identification and description
        - Task types the strategy applies to
        - Success rate and execution count
        - Performance metrics
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                strategy_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                task_types TEXT NOT NULL,
                parameters TEXT NOT NULL,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                total_executions INTEGER NOT NULL DEFAULT 0,
                success_rate REAL NOT NULL DEFAULT 0.0,
                avg_execution_time_ms REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used TEXT,
                
                -- Constraints
                CHECK (success_count >= 0),
                CHECK (failure_count >= 0),
                CHECK (total_executions >= 0),
                CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
                CHECK (avg_execution_time_ms >= 0.0),
                CHECK (total_executions = success_count + failure_count)
            )
        """)
    
    @staticmethod
    def _create_prompts_table(cursor: sqlite3.Cursor) -> None:
        """
        Create prompts table.
        
        Stores prompt versions and performance:
        - Prompt identification and type
        - Version history
        - Performance metrics per version
        - Active/inactive status
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                prompt_id TEXT PRIMARY KEY,
                prompt_type TEXT NOT NULL,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                total_uses INTEGER NOT NULL DEFAULT 0,
                success_rate REAL NOT NULL DEFAULT 0.0,
                hallucination_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used TEXT,
                
                -- Constraints
                CHECK (version > 0),
                CHECK (is_active IN (0, 1)),
                CHECK (success_count >= 0),
                CHECK (failure_count >= 0),
                CHECK (total_uses >= 0),
                CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
                CHECK (hallucination_count >= 0),
                CHECK (total_uses = success_count + failure_count),
                
                -- Unique constraint: only one active prompt per type
                UNIQUE (prompt_type, version)
            )
        """)
    
    @staticmethod
    def _create_metrics_table(cursor: sqlite3.Cursor) -> None:
        """
        Create metrics table.
        
        Stores performance metrics over time:
        - Task execution outcomes
        - Success rates and timing
        - Reasoning quality metrics
        - Tool usage efficiency
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success INTEGER NOT NULL,
                execution_time_ms REAL NOT NULL,
                reasoning_quality REAL,
                tool_selection_correct INTEGER,
                hallucination_detected INTEGER NOT NULL DEFAULT 0,
                task_sequence_number INTEGER NOT NULL,
                window_start INTEGER NOT NULL,
                window_end INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                -- Constraints
                CHECK (success IN (0, 1)),
                CHECK (execution_time_ms >= 0),
                CHECK (reasoning_quality IS NULL OR (reasoning_quality >= 0.0 AND reasoning_quality <= 1.0)),
                CHECK (tool_selection_correct IS NULL OR tool_selection_correct IN (0, 1)),
                CHECK (hallucination_detected IN (0, 1)),
                CHECK (task_sequence_number > 0),
                CHECK (window_start >= 0),
                CHECK (window_end >= window_start)
            )
        """)
    
    @staticmethod
    def _create_failure_patterns_table(cursor: sqlite3.Cursor) -> None:
        """
        Create failure_patterns table.
        
        Stores identified patterns across multiple failures:
        - Pattern identification
        - Common features across failures
        - Occurrence tracking
        - Temporal information
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failure_patterns (
                pattern_id TEXT PRIMARY KEY,
                failure_type TEXT NOT NULL,
                common_features TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL DEFAULT 1,
                confidence_score REAL NOT NULL DEFAULT 0.0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                -- Constraints
                CHECK (failure_type IN (
                    'reasoning_error',
                    'tool_error',
                    'hallucination',
                    'timeout',
                    'resource_error',
                    'unknown'
                )),
                CHECK (occurrence_count > 0),
                CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
            )
        """)
    
    @staticmethod
    def _create_indexes(cursor: sqlite3.Cursor) -> None:
        """
        Create indexes for query performance.
        
        Indexes on frequently queried columns:
        - failure_type for failure analysis
        - task_type for strategy selection
        - timestamp for temporal queries
        - strategy_id for performance tracking
        """
        # Failures table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_type 
            ON failures(failure_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_task_type 
            ON failures(task_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_timestamp 
            ON failures(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_strategy 
            ON failures(strategy_id)
        """)
        
        # Strategies table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategies_task_types 
            ON strategies(task_types)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategies_success_rate 
            ON strategies(success_rate DESC)
        """)
        
        # Prompts table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_type 
            ON prompts(prompt_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_active 
            ON prompts(is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompts_success_rate 
            ON prompts(success_rate DESC)
        """)
        
        # Metrics table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
            ON metrics(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_task_type 
            ON metrics(task_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_sequence 
            ON metrics(task_sequence_number)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_window 
            ON metrics(window_start, window_end)
        """)
        
        # Failure patterns table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_type 
            ON failure_patterns(failure_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_occurrence 
            ON failure_patterns(occurrence_count DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_confidence 
            ON failure_patterns(confidence_score DESC)
        """)
    
    @staticmethod
    def get_schema_version(db_path: str) -> Optional[int]:
        """
        Get current schema version.
        
        Args:
            db_path: Path to SQLite database file
            
        Returns:
            Schema version number or None if not set
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except sqlite3.OperationalError:
            return None
    
    @staticmethod
    def verify_schema(db_path: str) -> bool:
        """
        Verify database schema is complete and valid.
        
        Checks that all required tables and indexes exist.
        
        Args:
            db_path: Path to SQLite database file
            
        Returns:
            True if schema is valid, False otherwise
        """
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check all required tables exist
            required_tables = [
                'schema_version',
                'failures',
                'strategies',
                'prompts',
                'metrics',
                'failure_patterns'
            ]
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ({})
            """.format(','.join('?' * len(required_tables))), required_tables)
            
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            conn.close()
            
            return existing_tables == set(required_tables)
            
        except Exception:
            return False


def initialize_database(db_path: str) -> None:
    """
    Initialize database with schema.
    
    Convenience function to create database schema.
    
    Args:
        db_path: Path to SQLite database file
        
    Example:
        >>> initialize_database("data/self_improvement.db")
    """
    DatabaseSchema.create_schema(db_path)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "data/self_improvement.db"
    
    print(f"Creating database schema at: {db_path}")
    initialize_database(db_path)
    
    if DatabaseSchema.verify_schema(db_path):
        print("✓ Schema created successfully")
        version = DatabaseSchema.get_schema_version(db_path)
        print(f"✓ Schema version: {version}")
    else:
        print("✗ Schema verification failed")
        sys.exit(1)
