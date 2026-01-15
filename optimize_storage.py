#!/usr/bin/env python3
"""
Production Storage Optimization Script
Optimizes databases, archives old logs, and cleans up storage.
"""
import sqlite3
import os
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json

class StorageOptimizer:
    """Optimize production storage."""
    
    def __init__(self):
        self.databases = [
            "audit_logs/audit_log.db",
            "desktop-agent/audit_logs/audit_log.db"
        ]
        self.log_files = [
            "logs/multilingual_audit.jsonl"
        ]
        self.archive_dir = Path("archives")
        self.archive_dir.mkdir(exist_ok=True)
    
    def optimize_database(self, db_path: str) -> dict:
        """Optimize a single database."""
        if not os.path.exists(db_path):
            return {"status": "not_found", "path": db_path}
        
        print(f"\n{'='*60}")
        print(f"Optimizing: {db_path}")
        print(f"{'='*60}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get initial stats
        cursor.execute("PRAGMA page_count")
        before_pages = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        before_mb = (before_pages * page_size) / (1024 * 1024)
        
        cursor.execute("PRAGMA freelist_count")
        freelist_before = cursor.fetchone()[0]
        
        print(f"Before optimization:")
        print(f"  Size: {before_mb:.2f} MB")
        print(f"  Free pages: {freelist_before}")
        
        # Run VACUUM to reclaim space
        print("\nRunning VACUUM...")
        conn.execute("VACUUM")
        
        # Run ANALYZE to update statistics
        print("Running ANALYZE...")
        conn.execute("ANALYZE")
        
        # Run PRAGMA optimize
        print("Running PRAGMA optimize...")
        conn.execute("PRAGMA optimize")
        
        # Get final stats
        cursor.execute("PRAGMA page_count")
        after_pages = cursor.fetchone()[0]
        after_mb = (after_pages * page_size) / (1024 * 1024)
        
        cursor.execute("PRAGMA freelist_count")
        freelist_after = cursor.fetchone()[0]
        
        saved_mb = before_mb - after_mb
        
        print(f"\nAfter optimization:")
        print(f"  Size: {after_mb:.2f} MB")
        print(f"  Free pages: {freelist_after}")
        print(f"  Space saved: {saved_mb:.2f} MB ({(saved_mb/before_mb*100):.1f}%)")
        
        # Verify integrity
        print("\nVerifying integrity...")
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        print(f"  Integrity: {integrity}")
        
        conn.close()
        
        return {
            "status": "optimized",
            "path": db_path,
            "before_mb": before_mb,
            "after_mb": after_mb,
            "saved_mb": saved_mb,
            "integrity": integrity
        }
    
    def archive_old_logs(self, log_path: str, days_old: int = 30) -> dict:
        """Archive old log files."""
        if not os.path.exists(log_path):
            return {"status": "not_found", "path": log_path}
        
        print(f"\n{'='*60}")
        print(f"Archiving: {log_path}")
        print(f"{'='*60}")
        
        log_file = Path(log_path)
        file_size_mb = log_file.stat().st_size / (1024 * 1024)
        
        print(f"Current size: {file_size_mb:.2f} MB")
        
        # Check if file is old enough to archive
        file_age = datetime.now() - datetime.fromtimestamp(log_file.stat().st_mtime)
        
        if file_age.days < days_old:
            print(f"File is only {file_age.days} days old (threshold: {days_old} days)")
            print("Skipping archive (file too recent)")
            return {
                "status": "skipped",
                "path": log_path,
                "reason": "too_recent",
                "age_days": file_age.days
            }
        
        # Create archive filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{log_file.stem}_{timestamp}.jsonl.gz"
        archive_path = self.archive_dir / archive_name
        
        print(f"Compressing to: {archive_path}")
        
        # Compress the file
        with open(log_path, 'rb') as f_in:
            with gzip.open(archive_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        archive_size_mb = archive_path.stat().st_size / (1024 * 1024)
        compression_ratio = (1 - archive_size_mb / file_size_mb) * 100
        
        print(f"Archive size: {archive_size_mb:.2f} MB")
        print(f"Compression: {compression_ratio:.1f}%")
        
        # Clear the original file (keep it but empty)
        print("Clearing original file...")
        with open(log_path, 'w') as f:
            pass
        
        return {
            "status": "archived",
            "path": log_path,
            "archive_path": str(archive_path),
            "original_mb": file_size_mb,
            "archive_mb": archive_size_mb,
            "compression_ratio": compression_ratio
        }
    
    def clean_test_databases(self):
        """Remove test databases."""
        print(f"\n{'='*60}")
        print("Cleaning test databases...")
        print(f"{'='*60}")
        
        test_patterns = [
            "**/test_*.db",
            "**/*_test.db",
            "**/temp_*.db",
            "**/*.db.bak"
        ]
        
        removed = []
        for pattern in test_patterns:
            for db_file in Path(".").rglob(pattern):
                if "node_modules" not in str(db_file):
                    print(f"Removing: {db_file}")
                    db_file.unlink()
                    removed.append(str(db_file))
        
        if not removed:
            print("No test databases found")
        
        return removed
    
    def generate_report(self, results: dict):
        """Generate optimization report."""
        print(f"\n{'='*60}")
        print("OPTIMIZATION REPORT")
        print(f"{'='*60}")
        
        print("\nDatabase Optimization:")
        total_saved = 0
        for result in results.get("databases", []):
            if result["status"] == "optimized":
                print(f"  ✓ {result['path']}")
                print(f"    Saved: {result['saved_mb']:.2f} MB")
                total_saved += result['saved_mb']
        
        print(f"\n  Total space saved: {total_saved:.2f} MB")
        
        print("\nLog Archiving:")
        for result in results.get("logs", []):
            if result["status"] == "archived":
                print(f"  ✓ {result['path']}")
                print(f"    Compressed: {result['compression_ratio']:.1f}%")
            elif result["status"] == "skipped":
                print(f"  ⊘ {result['path']} (skipped: {result['reason']})")
        
        if results.get("test_dbs"):
            print(f"\nTest Databases Removed: {len(results['test_dbs'])}")
        
        # Save report
        report_path = self.archive_dir / f"optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nReport saved to: {report_path}")
    
    def run(self):
        """Run full optimization."""
        print("="*60)
        print("PRODUCTION STORAGE OPTIMIZATION")
        print("="*60)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "databases": [],
            "logs": [],
            "test_dbs": []
        }
        
        # Optimize databases
        for db_path in self.databases:
            result = self.optimize_database(db_path)
            results["databases"].append(result)
        
        # Archive old logs (only if > 30 days old)
        for log_path in self.log_files:
            result = self.archive_old_logs(log_path, days_old=30)
            results["logs"].append(result)
        
        # Clean test databases
        removed = self.clean_test_databases()
        results["test_dbs"] = removed
        
        # Generate report
        self.generate_report(results)
        
        print("\n" + "="*60)
        print("OPTIMIZATION COMPLETE")
        print("="*60)

if __name__ == "__main__":
    optimizer = StorageOptimizer()
    optimizer.run()
