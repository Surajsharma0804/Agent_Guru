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
    print(f"Creating database schema at: {db_path}")
    initialize_database(db_path)

    # Verify schema
    # BUG FIX: this branch used to be `pass` on success, so the script never
    # confirmed anything to whoever ran it -- restored per the module
    # docstring's own description of step 2, "Verify the schema is valid".
    if DatabaseSchema.verify_schema(db_path):
        print("Schema verified successfully.")
    else:
        print("Schema verification FAILED.")
        sys.exit(1)

    # Check version
    # BUG FIX: the return value used to be computed and immediately
    # discarded -- restored per step 3, "Check the schema version".
    schema_version = DatabaseSchema.get_schema_version(db_path)
    print(f"Schema version: {schema_version}")

    # Inspect database structure
    print("\nInspecting database structure...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # List tables
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    # BUG FIX: this loop used to be `pass` -- the comment says "List
    # tables" but nothing was ever listed. Restored to actually list them.
    print(f"\nTables ({len(tables)}):")
    for _table in tables:
        print(f"  - {_table}")

    # List indexes
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    indexes = [row[0] for row in cursor.fetchall()]

    # BUG FIX: identical pattern to the tables loop above -- restored.
    print(f"\nIndexes ({len(indexes)}):")
    for _index in indexes:
        print(f"  - {_index}")

    # Show table details
    print("\nTable details:")

    for table in tables:
        if table == "sqlite_sequence":
            continue

        cursor.execute(f"PRAGMA table_info({table})")  # nosec B608
        columns = cursor.fetchall()

        # BUG FIX: these four values used to be four bare expression
        # statements (`col[1]`, `col[2]`, and two conditional expressions)
        # that computed a value and threw it away on every line -- the
        # comment above says "Show table details", but nothing was shown.
        print(f"\n  {table}:")
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            not_null = "NOT NULL" if col[3] else ""
            primary_key = "PRIMARY KEY" if col[5] else ""
            flags = " ".join(flag for flag in (not_null, primary_key) if flag)
            print(f"    {col_name} ({col_type}) {flags}".rstrip())

    conn.close()


if __name__ == "__main__":
    main()
