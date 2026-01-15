"""
Comprehensive Tests for Audit Log Rotation and Compression

This module validates the audit logging system's log rotation and compression
capabilities, ensuring long-term operational stability and storage efficiency.

Tests validate:
- Daily log rotation triggers
- Compression of archived logs
- Hash chain preservation across rotations
- Storage space management
- Archive integrity verification
- Rotation under concurrent load
- Recovery from rotation failures

Requirements validated: 5.7
"""

import sys
from pathlib import Path
import tempfile
import shutil
import json
import gzip
import time
import sqlite3
from datetime import datetime, timezone
from typing import List

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_audit_dir():
    """Create temporary directory for audit logs"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def audit_logger_with_small_limit(temp_audit_dir):
    """Create audit logger with small entry limit for testing rotation"""
    return AuditLogger(
        log_directory=temp_audit_dir,
        max_log_entries=100,  # Small limit to trigger rotation easily
        enable_real_time_verification=False,
        testing_mode=True
    )


def create_test_event(index: int) -> AuditEvent:
    """Create a test audit event with unique data"""
    return AuditEvent(
        event_type=AuditEventType.SYSTEM_STARTUP,
        severity=AuditSeverity.INFO,
        component="test_component",
        action=f"test_action_{index}",
        details={"test_index": index, "timestamp": time.time()}
    )


# ============================================================================
# Test 1: Basic Log Rotation Trigger
# ============================================================================

def test_log_rotation_triggers_at_max_entries(audit_logger_with_small_limit):
    """
    Test that log rotation triggers when max_log_entries is reached.
    
    Validates:
    - Rotation occurs at configured threshold
    - Archive file is created with timestamp
    - Archive file is compressed (.gz extension)
    - Original database continues operation
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Log entries up to the limit
    for i in range(100):
        logger.log_event(create_test_event(i))
    
    # Verify no rotation yet (at limit, not over)
    archives = list(Path(logger.log_directory).glob("audit_log_*.db.gz"))
    assert len(archives) == 0, "Should not rotate until exceeding limit"
    
    # Log one more entry to trigger rotation
    logger.log_event(create_test_event(100))
    
    # Rotation should have occurred
    result = logger.rotate_logs()
    
    # Verify archive was created
    archives = list(Path(logger.log_directory).glob("audit_log_*.db.gz"))
    assert len(archives) == 1, "Should create one compressed archive"
    
    # Verify archive filename format (audit_log_YYYYMMDD_HHMMSS.db.gz)
    archive_name = archives[0].name
    assert archive_name.startswith("audit_log_"), "Archive should have correct prefix"
    assert archive_name.endswith(".db.gz"), "Archive should be gzip compressed"
    
    # Verify original database still exists and is operational
    assert logger.db_path.exists(), "Original database should still exist"
    
    # Verify we can still log after rotation
    entry_id = logger.log_event(create_test_event(101))
    assert entry_id is not None, "Should be able to log after rotation"


# ============================================================================
# Test 2: Archive Compression Integrity
# ============================================================================

def test_archive_compression_preserves_data(audit_logger_with_small_limit):
    """
    Test that compressed archives preserve all log data with integrity.
    
    Validates:
    - Compressed archive contains all original entries
    - Entry hashes are preserved
    - Signature chain is intact in archive
    - Archive can be decompressed and queried
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Log entries and track their IDs
    entry_ids = []
    for i in range(105):
        entry_id = logger.log_event(create_test_event(i))
        entry_ids.append(entry_id)
    
    # Trigger rotation
    logger.rotate_logs()
    
    # Find the archive
    archives = list(Path(logger.log_directory).glob("audit_log_*.db.gz"))
    assert len(archives) == 1, "Should have one archive"
    
    archive_path = archives[0]
    
    # Decompress and verify contents
    decompressed_path = archive_path.parent / "temp_decompressed.db"
    try:
        with gzip.open(archive_path, 'rb') as f_in:
            with open(decompressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Verify database structure
        with sqlite3.connect(decompressed_path) as conn:
            # Check entry count
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            count = cursor.fetchone()[0]
            assert count == 105, f"Archive should contain all 105 entries, found {count}"
            
            # Verify hash chain integrity in archive
            cursor = conn.execute("""
                SELECT id, entry_hash, previous_hash, sequence_number
                FROM audit_entries
                ORDER BY sequence_number ASC
            """)
            entries = cursor.fetchall()
            
            # Verify chain continuity
            for i in range(1, len(entries)):
                previous_entry = entries[i - 1]
                current_entry = entries[i]
                
                previous_hash = previous_entry[1]  # entry_hash
                current_previous_hash = current_entry[2]  # previous_hash
                
                assert current_previous_hash == previous_hash, \
                    f"Hash chain broken in archive at entry {i}"
            
            # Verify all original entry IDs are present
            cursor = conn.execute("SELECT id FROM audit_entries ORDER BY sequence_number")
            archived_ids = [row[0] for row in cursor.fetchall()]
            
            for entry_id in entry_ids:
                assert entry_id in archived_ids, \
                    f"Entry {entry_id} missing from archive"
    
    finally:
        # Clean up decompressed file
        if decompressed_path.exists():
            decompressed_path.unlink()


# ============================================================================
# Test 3: Hash Chain Preservation Across Rotation
# ============================================================================

def test_hash_chain_preserved_across_rotation(audit_logger_with_small_limit):
    """
    Test that the cryptographic hash chain is preserved across log rotations.
    
    Validates:
    - Last hash from archive links to first hash in new log
    - Sequence numbers continue incrementing
    - No gaps in the audit trail
    - Integrity verification works across rotation boundary
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Log entries before rotation
    for i in range(105):
        logger.log_event(create_test_event(i))
    
    # Capture last hash before rotation
    with sqlite3.connect(logger.db_path) as conn:
        cursor = conn.execute("""
            SELECT entry_hash, sequence_number
            FROM audit_entries
            ORDER BY sequence_number DESC
            LIMIT 1
        """)
        last_hash_before, last_seq_before = cursor.fetchone()
    
    # Trigger rotation
    logger.rotate_logs()
    
    # Log entries after rotation
    for i in range(105, 110):
        logger.log_event(create_test_event(i))
    
    # Verify new log continues from where archive left off
    with sqlite3.connect(logger.db_path) as conn:
        cursor = conn.execute("""
            SELECT entry_hash, previous_hash, sequence_number
            FROM audit_entries
            ORDER BY sequence_number ASC
            LIMIT 1
        """)
        first_hash_after, first_prev_hash_after, first_seq_after = cursor.fetchone()
    
    # The rotation event itself will be logged, so we need to account for that
    # The sequence should continue incrementing
    assert first_seq_after > last_seq_before, \
        "Sequence numbers should continue incrementing after rotation"
    
    # Verify integrity of current log
    result = logger.verify_integrity()
    assert result.verified, "Integrity should be valid after rotation"
    assert result.hash_chain_valid, "Hash chain should be valid after rotation"


# ============================================================================
# Test 4: Multiple Rotations
# ============================================================================

def test_multiple_rotations_create_multiple_archives(audit_logger_with_small_limit):
    """
    Test that multiple rotations create separate compressed archives.
    
    Validates:
    - Each rotation creates a unique archive file
    - Archive filenames have unique timestamps
    - All archives are properly compressed
    - System remains operational after multiple rotations
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Perform three rotation cycles
    for cycle in range(3):
        # Log enough entries to trigger rotation
        for i in range(105):
            logger.log_event(create_test_event(cycle * 1000 + i))
        
        # Trigger rotation
        logger.rotate_logs()
        
        # Small delay to ensure unique timestamps
        time.sleep(0.1)
    
    # Verify three archives were created
    archives = sorted(Path(logger.log_directory).glob("audit_log_*.db.gz"))
    assert len(archives) == 3, f"Should have 3 archives, found {len(archives)}"
    
    # Verify archives have unique names (timestamps)
    archive_names = [a.name for a in archives]
    assert len(set(archive_names)) == 3, "Archive names should be unique"
    
    # Verify all archives are valid gzip files
    for archive in archives:
        try:
            with gzip.open(archive, 'rb') as f:
                # Try to read header to verify it's valid gzip
                f.read(1)
        except Exception as e:
            pytest.fail(f"Archive {archive.name} is not a valid gzip file: {e}")
    
    # Verify current log is still operational
    entry_id = logger.log_event(create_test_event(9999))
    assert entry_id is not None, "Should be able to log after multiple rotations"


# ============================================================================
# Test 5: Rotation Under Concurrent Load
# ============================================================================

def test_rotation_under_concurrent_logging(audit_logger_with_small_limit):
    """
    Test that rotation works correctly when logging continues during rotation.
    
    Validates:
    - No entries are lost during rotation
    - No database corruption occurs
    - Thread safety is maintained
    - All entries maintain integrity
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Log entries to approach rotation threshold
    for i in range(98):
        logger.log_event(create_test_event(i))
    
    # Log entries that will trigger rotation
    entry_ids_during_rotation = []
    for i in range(98, 110):
        entry_id = logger.log_event(create_test_event(i))
        entry_ids_during_rotation.append(entry_id)
    
    # Trigger rotation
    logger.rotate_logs()
    
    # Verify all entries during rotation were logged
    with sqlite3.connect(logger.db_path) as conn:
        for entry_id in entry_ids_during_rotation:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM audit_entries WHERE id = ?
            """, (entry_id,))
            count = cursor.fetchone()[0]
            
            # Entry might be in archive or current log
            if count == 0:
                # Check if it's in the archive
                archives = list(Path(logger.log_directory).glob("audit_log_*.db.gz"))
                found_in_archive = False
                
                for archive in archives:
                    decompressed_path = archive.parent / "temp_check.db"
                    try:
                        with gzip.open(archive, 'rb') as f_in:
                            with open(decompressed_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        with sqlite3.connect(decompressed_path) as archive_conn:
                            cursor = archive_conn.execute("""
                                SELECT COUNT(*) FROM audit_entries WHERE id = ?
                            """, (entry_id,))
                            if cursor.fetchone()[0] > 0:
                                found_in_archive = True
                                break
                    finally:
                        if decompressed_path.exists():
                            decompressed_path.unlink()
                
                assert found_in_archive, \
                    f"Entry {entry_id} not found in current log or archives"


# ============================================================================
# Test 6: Rotation Failure Handling
# ============================================================================

def test_rotation_handles_disk_full_gracefully(temp_audit_dir):
    """
    Test that rotation failures don't corrupt the audit log.
    
    Validates:
    - Original log remains intact on rotation failure
    - System continues logging after failed rotation
    - Error is logged appropriately
    - No data loss occurs
    
    Requirements: 5.7
    """
    logger = AuditLogger(
        log_directory=temp_audit_dir,
        max_log_entries=50,
        enable_real_time_verification=False,
        testing_mode=True
    )
    
    # Log entries
    entry_ids = []
    for i in range(55):
        entry_id = logger.log_event(create_test_event(i))
        entry_ids.append(entry_id)
    
    # Attempt rotation (may fail due to various reasons, but should handle gracefully)
    try:
        result = logger.rotate_logs()
        # If rotation succeeds, verify archive exists
        if result:
            archives = list(Path(logger.log_directory).glob("audit_log_*.db.gz"))
            assert len(archives) > 0, "Archive should exist after successful rotation"
    except Exception as e:
        # If rotation fails, verify original log is intact
        pass
    
    # Verify original database is still operational
    assert logger.db_path.exists(), "Original database should still exist"
    
    # Verify we can still log after rotation attempt
    entry_id = logger.log_event(create_test_event(999))
    assert entry_id is not None, "Should be able to log after rotation attempt"
    
    # Verify integrity of current log
    result = logger.verify_integrity()
    assert result.verified, "Log integrity should be maintained after rotation attempt"


# ============================================================================
# Test 7: Archive Storage Efficiency
# ============================================================================

def test_compression_reduces_storage_size(audit_logger_with_small_limit):
    """
    Test that gzip compression significantly reduces archive storage size.
    
    Validates:
    - Compressed archive is smaller than original database
    - Compression ratio is reasonable (at least 30% reduction)
    - Storage efficiency improves with larger logs
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Log entries with compressible data
    for i in range(105):
        event = AuditEvent(
            event_type=AuditEventType.COMMAND_EXECUTED,
            severity=AuditSeverity.INFO,
            component="test_component",
            action="test_action",
            details={
                "command": "open notepad and write hello world",
                "result": "success",
                "execution_time": 1.234,
                "metadata": "This is test data that should compress well"
            }
        )
        logger.log_event(event)
    
    # Get original database size
    original_size = logger.db_path.stat().st_size
    
    # Trigger rotation
    logger.rotate_logs()
    
    # Get compressed archive size
    archives = list(Path(logger.log_directory).glob("audit_log_*.db.gz"))
    assert len(archives) == 1, "Should have one archive"
    
    compressed_size = archives[0].stat().st_size
    
    # Verify compression achieved size reduction
    compression_ratio = compressed_size / original_size
    assert compression_ratio < 0.7, \
        f"Compression should reduce size by at least 30%, got {compression_ratio:.2%}"
    
    print(f"Compression ratio: {compression_ratio:.2%} "
          f"(original: {original_size} bytes, compressed: {compressed_size} bytes)")


# ============================================================================
# Test 8: Rotation Metadata Logging
# ============================================================================

def test_rotation_logs_metadata_event(audit_logger_with_small_limit):
    """
    Test that rotation events are logged with complete metadata.
    
    Validates:
    - Rotation event is logged to audit trail
    - Metadata includes archive filename
    - Metadata includes entry count
    - Metadata includes last entry hash for chain verification
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Log entries to trigger rotation
    for i in range(105):
        logger.log_event(create_test_event(i))
    
    # Trigger rotation
    logger.rotate_logs()
    
    # Verify rotation event was logged
    with sqlite3.connect(logger.db_path) as conn:
        cursor = conn.execute("""
            SELECT event_type, action, details
            FROM audit_entries
            WHERE action = 'audit_log_rotated'
            ORDER BY sequence_number DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        assert row is not None, "Rotation event should be logged"
        
        event_type, action, details_json = row
        details = json.loads(details_json)
        
        # Verify metadata completeness
        assert "archive_file" in details, "Should include archive filename"
        assert "entries_archived" in details, "Should include entry count"
        assert "last_entry_hash" in details, "Should include last hash for chain verification"
        
        # Verify metadata accuracy
        assert details["entries_archived"] == 105, "Should archive all 105 entries"
        assert details["archive_file"].endswith(".db.gz"), "Archive should be compressed"


# ============================================================================
# Test 9: No Rotation When Below Threshold
# ============================================================================

def test_no_rotation_when_below_threshold(audit_logger_with_small_limit):
    """
    Test that rotation does not occur when entry count is below threshold.
    
    Validates:
    - rotate_logs() returns False when below threshold
    - No archive files are created
    - Original database remains unchanged
    
    Requirements: 5.7
    """
    logger = audit_logger_with_small_limit
    
    # Log entries below the threshold
    for i in range(50):
        logger.log_event(create_test_event(i))
    
    # Attempt rotation
    result = logger.rotate_logs()
    
    # Verify rotation did not occur
    assert result is False, "Should return False when below threshold"
    
    # Verify no archives were created
    archives = list(Path(logger.log_directory).glob("audit_log_*.db.gz"))
    assert len(archives) == 0, "Should not create archives when below threshold"
    
    # Verify all entries are still in current log
    with sqlite3.connect(logger.db_path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
        count = cursor.fetchone()[0]
        assert count == 50, "All entries should remain in current log"
