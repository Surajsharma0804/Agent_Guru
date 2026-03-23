"""
Example: Create and verify self-improvement database.

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


def main():
    """Create and verify database schema."""
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "data/self_improvement.db"

    print(f"Creating database at: {db_path}")
    print("-" * 60)

    # Create schema
    initialize_database(db_path)
    print("✓ Database schema created")

    # Verify schema
    if DatabaseSchema.verify_schema(db_path):
        print("✓ Schema verification passed")
    else:
        print("✗ Schema verification failed")
        sys.exit(1)

    # Check version
    version = DatabaseSchema.get_schema_version(db_path)
    print(f"✓ Schema version: {version}")

    # Inspect database structure
    print("\nDatabase Structure:")
    print("-" * 60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # List tables
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    print(f"\nTables ({len(tables)}):")
    for table in tables:
        print(f"  - {table}")

    # List indexes
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    indexes = [row[0] for row in cursor.fetchall()]

    print(f"\nIndexes ({len(indexes)}):")
    for index in indexes:
        print(f"  - {index}")

    # Show table details
    print("\nTable Details:")
    print("-" * 60)

    for table in tables:
        if table == 'sqlite_sequence':
            continue

        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()

        print(f"\n{table}:")
        print(f"  Columns: {len(columns)}")
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            not_null = "NOT NULL" if col[3] else ""
            pk = "PRIMARY KEY" if col[5] else ""
            print(f"    - {col_name}: {col_type} {not_null} {pk}".strip())

    conn.close()

    print("\n" + "=" * 60)
    print("Database created and verified successfully!")
    print(f"Location: {Path(db_path).absolute()}")


if __name__ == "__main__":
    main()
