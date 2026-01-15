#!/usr/bin/env python3
"""Check database status and optimize."""
import sqlite3
import os
from pathlib import Path

def check_database(db_path: str):
    """Check database status."""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    print(f"\n=== Checking {db_path} ===")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table count
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
    table_count = cursor.fetchone()[0]
    print(f"Tables: {table_count}")
    
    # Get page count and size
    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]
    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    
    size_mb = (page_count * page_size) / (1024 * 1024)
    print(f"Size: {size_mb:.2f} MB ({page_count} pages × {page_size} bytes)")
    
    # Get table names and row counts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("\nTable row counts:")
    for table in tables:
        table_name = table[0]
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            print(f"  {table_name}: {row_count} rows")
        except Exception as e:
            print(f"  {table_name}: Error - {e}")
    
    # Check for fragmentation
    cursor.execute("PRAGMA freelist_count")
    freelist = cursor.fetchone()[0]
    print(f"\nFragmentation: {freelist} free pages")
    
    conn.close()

def vacuum_database(db_path: str):
    """Vacuum database to reclaim space."""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    print(f"\n=== Vacuuming {db_path} ===")
    conn = sqlite3.connect(db_path)
    
    # Get size before
    cursor = conn.cursor()
    cursor.execute("PRAGMA page_count")
    before_pages = cursor.fetchone()[0]
    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    before_mb = (before_pages * page_size) / (1024 * 1024)
    
    # Vacuum
    print("Running VACUUM...")
    conn.execute("VACUUM")
    
    # Get size after
    cursor.execute("PRAGMA page_count")
    after_pages = cursor.fetchone()[0]
    after_mb = (after_pages * page_size) / (1024 * 1024)
    
    saved_mb = before_mb - after_mb
    print(f"Before: {before_mb:.2f} MB")
    print(f"After: {after_mb:.2f} MB")
    print(f"Saved: {saved_mb:.2f} MB ({(saved_mb/before_mb*100):.1f}%)")
    
    conn.close()

def optimize_database(db_path: str):
    """Optimize database indexes."""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    print(f"\n=== Optimizing {db_path} ===")
    conn = sqlite3.connect(db_path)
    
    # Analyze tables
    print("Running ANALYZE...")
    conn.execute("ANALYZE")
    
    # Optimize
    print("Running PRAGMA optimize...")
    conn.execute("PRAGMA optimize")
    
    conn.close()
    print("Optimization complete")

if __name__ == "__main__":
    # Check all databases
    databases = [
        "audit_logs/audit_log.db",
        "desktop-agent/audit_logs/audit_log.db"
    ]
    
    # Check for memory databases
    memory_db = Path("desktop-agent/src/memory/data/memory.db")
    if memory_db.exists():
        databases.append(str(memory_db))
    
    # Check status
    for db in databases:
        check_database(db)
    
    # Ask user before vacuuming
    print("\n" + "="*60)
    response = input("\nVacuum databases? (y/n): ")
    
    if response.lower() == 'y':
        for db in databases:
            if os.path.exists(db):
                vacuum_database(db)
                optimize_database(db)
        
        print("\n" + "="*60)
        print("Database optimization complete!")
    else:
        print("Skipping vacuum.")
