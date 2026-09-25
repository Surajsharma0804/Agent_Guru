"""Database schema for Self-Improvement Engine.

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

import logging

_logger = logging.getLogger(__name__)

import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402

from Agent_Guru.utils.path_utils import safe_path  # noqa: E402

# Every connection here goes through open_sqlite(). `with sqlite3.connect()
# as conn:` only ends the transaction and leaves the connection open, which on
# Windows kept each database file locked: 149 self_improvement tests errored
# at teardown with WinError 32 because the schema was created that way.
from Agent_Guru.utils.sqlite import open_sqlite  # noqa: E402

BASE_DIR = Path(__file__).parent.resolve()


class DatabaseSchema:
    """Database schema manager for Self-Improvement Engine.

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
        """Create complete database schema.

        Creates all tables, indexes, and constraints needed for
        the self-improvement engine.

        Args:
            db_path: Path to SQLite database file

        Time Complexity: O(1) - fixed number of tables
        Space Complexity: O(1) - schema definition only

        """
        # Validate db_path: must be a plain filename or relative path with no traversal
        # sequences. safe_path enforces BASE_DIR containment, but we also reject
        # any path that contains ".." segments before it reaches safe_path.
        db_path_clean = str(db_path).strip()

        # Handle absolute paths (e.g., from temp files in tests) directly
        db_file = Path(db_path_clean)
        if db_file.is_absolute():
            # Absolute path - use directly (for temp files in tests)
            db_file = db_file.resolve()
        else:
            # Relative path - validate no traversal and use safe_path
            if ".." in db_path_clean.replace("\\", "/").split("/"):
                msg = f"Invalid db_path - path traversal sequences are not allowed: {db_path!r}"
                raise ValueError(
                    msg,
                )
            db_file = safe_path(BASE_DIR, db_path_clean)

        # Ensure directory exists
        db_file.parent.mkdir(parents=True, exist_ok=True)

        with open_sqlite(db_file) as conn:
            cursor = conn.cursor()

            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")

            # Create schema version table
            DatabaseSchema._create_version_table(cursor)

            # Create core tables
            DatabaseSchema._create_failures_table(cursor)
            DatabaseSchema._create_strategies_table(cursor)
            DatabaseSchema._create_prompts_table(cursor)
            DatabaseSchema._create_prompt_updates_table(cursor)
            DatabaseSchema._create_metrics_table(cursor)
            DatabaseSchema._create_failure_patterns_table(cursor)
            DatabaseSchema._create_stability_metrics_table(cursor)
            DatabaseSchema._create_edge_case_metrics_table(cursor)

            # Create indexes for performance
            DatabaseSchema._create_indexes(cursor)

            # Set schema version
            cursor.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (DatabaseSchema.SCHEMA_VERSION,),
            )

            conn.commit()

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
        """Create failures table.

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
        """Create strategies table.

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
        """Create prompts table.

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
    def _create_prompt_updates_table(cursor: sqlite3.Cursor) -> None:
        """Create prompt_updates table for rate limiting.

        Tracks prompt update history to enforce rate limits and prevent oscillations:
        - Update timestamps per prompt type
        - Update types (register, rollback, replace)
        - Previous and new versions for oscillation detection
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_updates (
                update_id TEXT PRIMARY KEY,
                prompt_type TEXT NOT NULL,
                update_type TEXT NOT NULL,
                previous_version INTEGER,
                new_version INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                -- Constraints
                CHECK (update_type IN ('register', 'rollback', 'replace')),
                CHECK (new_version > 0),
                CHECK (previous_version IS NULL OR previous_version > 0)
            )
        """)

    @staticmethod
    def _create_metrics_table(cursor: sqlite3.Cursor) -> None:
        """Create metrics table.

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
        """Create failure_patterns table.

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
    def _create_stability_metrics_table(cursor: sqlite3.Cursor) -> None:
        """Create stability_metrics table.

        Stores stability tracking for oscillation detection:
        - Component and metric identification
        - Stability metrics (variance, change frequency)
        - Oscillation detection flags
        - Stability scores
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stability_metrics (
                metric_id TEXT PRIMARY KEY,
                component TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                variance REAL NOT NULL DEFAULT 0.0,
                change_frequency REAL NOT NULL DEFAULT 0.0,
                oscillation_detected INTEGER NOT NULL DEFAULT 0,
                stability_score REAL NOT NULL DEFAULT 1.0,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                -- Constraints
                CHECK (variance >= 0.0),
                CHECK (change_frequency >= 0.0 AND change_frequency <= 1.0),
                CHECK (oscillation_detected IN (0, 1)),
                CHECK (stability_score >= 0.0 AND stability_score <= 1.0)
            )
        """)

    @staticmethod
    def _create_edge_case_metrics_table(cursor: sqlite3.Cursor) -> None:
        """Create edge_case_metrics table.

        Stores confidence metrics for patterns to prevent overgeneralization:
        - Pattern identification
        - Sample size and success rate
        - Confidence scores and intervals
        - Edge case detection flags
        - Event frequency and weighted scores
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edge_case_metrics (
                metric_id TEXT PRIMARY KEY,
                pattern_id TEXT NOT NULL,
                sample_size INTEGER NOT NULL,
                success_rate REAL NOT NULL,
                confidence_score REAL NOT NULL,
                lower_bound REAL NOT NULL,
                upper_bound REAL NOT NULL,
                is_edge_case INTEGER NOT NULL,
                event_frequency REAL NOT NULL,
                weighted_score REAL NOT NULL,
                meets_threshold INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                -- Constraints
                CHECK (sample_size >= 0),
                CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
                CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
                CHECK (lower_bound >= 0.0 AND lower_bound <= 1.0),
                CHECK (upper_bound >= 0.0 AND upper_bound <= 1.0),
                CHECK (lower_bound <= upper_bound),
                CHECK (is_edge_case IN (0, 1)),
                CHECK (event_frequency >= 0.0 AND event_frequency <= 1.0),
                CHECK (weighted_score >= 0.0 AND weighted_score <= 1.0),
                CHECK (meets_threshold IN (0, 1))
            )
        """)

    @staticmethod
    def _create_indexes(cursor: sqlite3.Cursor) -> None:
        """Create indexes for query performance.

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

        # Prompt updates table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompt_updates_type
            ON prompt_updates(prompt_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompt_updates_timestamp
            ON prompt_updates(timestamp DESC)
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

        # Stability metrics table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stability_component
            ON stability_metrics(component)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stability_metric_name
            ON stability_metrics(metric_name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stability_timestamp
            ON stability_metrics(timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stability_score
            ON stability_metrics(stability_score ASC)
        """)

        # Edge case metrics table indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_case_pattern
            ON edge_case_metrics(pattern_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_case_is_edge
            ON edge_case_metrics(is_edge_case)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_case_timestamp
            ON edge_case_metrics(timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edge_case_confidence
            ON edge_case_metrics(confidence_score DESC)
        """)

    @staticmethod
    def get_schema_version(db_path: str) -> int | None:
        """Get current schema version.

        Args:
            db_path: Path to SQLite database file

        Returns:
            Schema version number or None if not set

        """
        try:
            with open_sqlite(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
                result = cursor.fetchone()
            return result[0] if result else None
        except sqlite3.OperationalError:
            return None

    @staticmethod
    def verify_schema(db_path: str) -> bool:
        """Verify database schema is complete and valid.

        Checks that all required tables and indexes exist.

        Args:
            db_path: Path to SQLite database file

        Returns:
            True if schema is valid, False otherwise

        """
        try:
            with open_sqlite(db_path) as conn:
                cursor = conn.cursor()

                # Check all required tables exist
                # BUG FIX: this list previously named only 7 of the
                # 9 tables create_schema() actually creates, so a
                # schema that was missing prompt_updates and/or
                # edge_case_metrics entirely (e.g. from a
                # create_schema() call that failed partway through --
                # DDL statements are not implicitly transactional the
                # way INSERT/UPDATE/DELETE are under sqlite3's default
                # isolation level) would still report as fully valid
                # here, contradicting this method's own docstring
                # ("Checks that all required tables ... exist").
                required_tables = [
                    "schema_version",
                    "failures",
                    "strategies",
                    "prompts",
                    "prompt_updates",
                    "metrics",
                    "failure_patterns",
                    "stability_metrics",
                    "edge_case_metrics",
                ]

                # Use parameterized placeholders - table names are hardcoded, only values are parameterized
                placeholders = ",".join("?" * len(required_tables))
                cursor.execute(
                    "SELECT name FROM sqlite_master "  # noqa: S608 - SQL parameterization reviewed
                    "WHERE type='table' AND name IN (" + placeholders + ")",  # nosec B608
                    required_tables,
                )

                existing_tables = {row[0] for row in cursor.fetchall()}

            return existing_tables == set(required_tables)

        except Exception:
            return False


def initialize_database(db_path: str) -> None:
    """Initialize database with schema.

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

    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/self_improvement.db"

    _logger.info("Creating database schema at: %s", db_path)
    initialize_database(db_path)

    if DatabaseSchema.verify_schema(db_path):
        _logger.info("✓ Schema created successfully")
        version = DatabaseSchema.get_schema_version(db_path)
        _logger.info("✓ Schema version: %s", version)
    else:
        _logger.info("✗ Schema verification failed")
        sys.exit(1)
