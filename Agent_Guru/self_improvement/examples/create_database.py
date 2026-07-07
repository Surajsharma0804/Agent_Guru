"""Example: Create and verify self-improvement database.

This script demonstrates how to:
1. Create the database schema
2. Verify the schema is valid
3. Check the schema version
4. Inspect the database structure

Usage:
    python -m Agent_Guru.self_improvement.examples.create_database [db_path]
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import sqlite3

from Agent_Guru.self_improvement.database_schema import DatabaseSchema, initialize_database


def main() -> None:
    """Create and verify database schema."""
    # Get database path from command line or use default
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/self_improvement.db"

    # Create schema
    initialize_database(db_path)

    # Verify schema
    if DatabaseSchema.verify_schema(db_path):
        pass
    else:
        sys.exit(1)

    # Check version
    DatabaseSchema.get_schema_version(db_path)

    # Inspect database structure

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # List tables
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    for _table in tables:
        pass

    # List indexes
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    indexes = [row[0] for row in cursor.fetchall()]

    for _index in indexes:
        pass

    # Show table details

    for table in tables:
        if table == "sqlite_sequence":
            continue

        cursor.execute(f"PRAGMA table_info({table})")  # nosec B608
        columns = cursor.fetchall()

        for col in columns:
            col[1]
            col[2]
            "NOT NULL" if col[3] else ""
            "PRIMARY KEY" if col[5] else ""

    conn.close()


if __name__ == "__main__":
    main()
