"""
Unit Tests for Comprehensive Audit Logger

Tests the core audit logging functionality including cryptographic
signatures, hash chain integrity, and comprehensive event coverage.
"""

import pytest
import tempfile
import shutil
import json
import hashlib
import hmac
import os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.audit.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditLogEntry,
    IntegrityVerificationResult
)


class TestAuditLogger:
    """Test suite for comprehensive audit logger"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test logs"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Handle Windows file locking issues
        try:
            shutil.rmtree(temp_dir)
        except PermissionError:
            # On Windows, SQLite files may still be locked
            import time
            time.sleep(0.1)
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                # If still locked, ignore - temp files will be cleaned up by OS
                pass
    
    @pytest.fixture
    def audit_logger(self, temp_dir):
        """Create audit logger instance for testing"""
        return AuditLogger(
            log_directory=temp_dir,
            enable_real_time_verification=False,  # Disable for testing
            testing_mode=True  # Enable testing mode
        )
    
    @pytest.fixture
    def sample_event(self):
        """Create sample audit event for testing"""
        return AuditEvent(
            event_type=AuditEventType.AUTHORITY_STATE_CHANGE,
            severity=AuditSeverity.INFO,
            component="test_component",
            action="test_action",
            details={"test_key": "test_value"},
            session_id="test_session",
            user_id="test_user"
        )
    
    def test_audit_logger_initialization(self, temp_dir):
        """Test audit logger initialization"""
        logger = AuditLogger(log_directory=temp_dir, testing_mode=True)
        
        assert logger.log_directory == Path(temp_dir)
        assert logger.signing_key is not None
        assert len(logger.signing_key) == 32  # 256-bit key
        assert logger.db_path.exists()
        assert logger.sequence_counter == 1
        assert logger.last_entry_hash is None
    
    def test_signing_key_generation_and_persistence(self, temp_dir):
        """Test signing key generation and persistence"""
        # First logger instance
        logger1 = AuditLogger(log_directory=temp_dir, testing_mode=True)
        key1 = logger1.signing_key
        
        # Second logger instance should load same key
        logger2 = AuditLogger(log_directory=temp_dir, testing_mode=True)
        key2 = logger2.signing_key
        
        assert key1 == key2
        
        # Key file should exist with correct permissions
        key_file = Path(temp_dir) / "audit_signing_key.bin"
        assert key_file.exists()
        
        # Check file permissions (owner read/write only)
        if os.name != 'nt':  # Skip on Windows
            assert oct(key_file.stat().st_mode)[-3:] == '600'
    
    def test_database_initialization(self, audit_logger):
        """Test database schema initialization"""
        # Check that database exists
        assert audit_logger.db_path.exists()
        
        # Check table structure
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='audit_entries'
            """)
            assert cursor.fetchone() is not None
            
            # Check indexes
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='audit_entries'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            expected_indexes = [
                'idx_timestamp', 'idx_event_type', 'idx_component',
                'idx_severity', 'idx_session_id', 'idx_sequence'
            ]
            for expected_index in expected_indexes:
                assert expected_index in indexes
    
    def test_log_event_basic(self, audit_logger, sample_event):
        """Test basic event logging"""
        entry_id = audit_logger.log_event(sample_event)
        
        assert entry_id is not None
        assert audit_logger.sequence_counter == 2
        assert audit_logger.last_entry_hash is not None
        
        # Verify entry in database
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, event_type, component, action, details
                FROM audit_entries WHERE id = ?
            """, (entry_id,))
            
            row = cursor.fetchone()
            assert row is not None
            assert row[1] == sample_event.event_type.value
            assert row[2] == sample_event.component
            assert row[3] == sample_event.action
            
            details = json.loads(row[4])
            assert details["test_key"] == "test_value"
    
    def test_hash_chain_integrity(self, audit_logger):
        """Test hash chain linking between entries"""
        # Log first event
        event1 = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            component="test",
            action="first_event",
            details={"order": 1}
        )
        audit_logger.log_event(event1)
        first_hash = audit_logger.last_entry_hash
        
        # Log second event
        event2 = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            component="test",
            action="second_event",
            details={"order": 2}
        )
        audit_logger.log_event(event2)
        
        # Verify hash chain
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT previous_hash, entry_hash, sequence_number
                FROM audit_entries ORDER BY sequence_number
            """)
            
            entries = cursor.fetchall()
            assert len(entries) == 2
            
            # First entry should have no previous hash
            assert entries[0][0] is None
            
            # Second entry should reference first entry's hash
            assert entries[1][0] == entries[0][1]
            assert entries[1][0] == first_hash
    
    def test_cryptographic_signatures(self, audit_logger, sample_event):
        """Test cryptographic signature generation and verification"""
        entry_id = audit_logger.log_event(sample_event)
        
        # Get entry from database
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, component,
                       action, details, previous_hash, entry_hash, signature
                FROM audit_entries WHERE id = ?
            """, (entry_id,))
            
            row = cursor.fetchone()
            assert row is not None
            
            # Reconstruct entry data for verification
            entry_data = {
                "id": row[0],
                "timestamp": row[1],
                "sequence_number": row[2],
                "event_type": row[3],
                "component": row[4],
                "action": row[5],
                "details": json.loads(row[6]),
                "previous_hash": row[7]
            }
            
            # Verify hash
            expected_hash = audit_logger._calculate_entry_hash(entry_data)
            assert expected_hash == row[8]
            
            # Verify signature
            expected_signature = audit_logger._sign_entry(expected_hash)
            assert expected_signature == row[9]
    
    def test_sensitive_data_sanitization(self, audit_logger):
        """Test that sensitive data is properly sanitized"""
        sensitive_event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.ERROR,
            component="test",
            action="sensitive_test",
            details={
                "password": "secret123",
                "private_key": "key_data",
                "biometric": "fingerprint_data",
                "text_content": "user typed this",
                "safe_data": "this is ok",
                "long_data": "x" * 3000  # Test length limiting
            }
        )
        
        entry_id = audit_logger.log_event(sensitive_event)
        
        # Verify sanitization
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT details FROM audit_entries WHERE id = ?
            """, (entry_id,))
            
            details = json.loads(cursor.fetchone()[0])
            
            # Sensitive data should be redacted
            assert details["password"] == "[REDACTED]"
            assert details["private_key"] == "[REDACTED]"
            assert details["biometric"] == "[REDACTED]"
            assert details["text_content"] == "[REDACTED]"
            
            # Safe data should be preserved
            assert details["safe_data"] == "this is ok"
            
            # Long data should be truncated
            assert details["long_data"].endswith("...[truncated]")
            assert len(details["long_data"]) <= audit_logger.max_detail_length + 15
    
    def test_sequence_number_continuity(self, audit_logger):
        """Test sequence number continuity"""
        events = []
        for i in range(5):
            event = AuditEvent(
                event_type=AuditEventType.SYSTEM_STARTUP,
                severity=AuditSeverity.INFO,
                component="test",
                action=f"event_{i}",
                details={"index": i}
            )
            events.append(event)
            audit_logger.log_event(event)
        
        # Verify sequence numbers
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT sequence_number FROM audit_entries 
                ORDER BY sequence_number
            """)
            
            sequences = [row[0] for row in cursor.fetchall()]
            expected_sequences = list(range(1, 6))
            assert sequences == expected_sequences
    
    def test_convenience_logging_methods(self, audit_logger):
        """Test convenience methods for common event types"""
        # Test authority event logging
        authority_id = audit_logger.log_authority_event(
            "state_change",
            {"from": "LOCKED", "to": "ARMED"},
            session_id="test_session"
        )
        
        # Test security event logging
        security_id = audit_logger.log_security_event(
            "violation_detected",
            {"violation_type": "unauthorized_access"}
        )
        
        # Test system event logging
        system_id = audit_logger.log_system_event(
            "startup",
            {"component": "test_system"}
        )
        
        # Test emergency event logging
        emergency_id = audit_logger.log_emergency_event(
            "critical_failure",
            {"failure_type": "system_halt"}
        )
        
        # Verify all events were logged
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            assert cursor.fetchone()[0] == 4
            
            # Verify event types
            cursor = conn.execute("""
                SELECT event_type, severity FROM audit_entries 
                ORDER BY sequence_number
            """)
            
            events = cursor.fetchall()
            assert events[0][0] == AuditEventType.AUTHORITY_STATE_CHANGE.value
            assert events[1][0] == AuditEventType.SECURITY_VIOLATION.value
            assert events[2][0] == AuditEventType.CONFIGURATION_CHANGE.value  # System events map to config change
            assert events[3][0] == AuditEventType.EMERGENCY_SHUTDOWN.value
            assert events[3][1] == AuditSeverity.EMERGENCY.value
    
    def test_audit_statistics(self, audit_logger):
        """Test audit statistics generation"""
        # Log some events
        for i in range(3):
            event = AuditEvent(
                event_type=AuditEventType.INPUT_SIMULATION,
                severity=AuditSeverity.INFO,
                component="test",
                action=f"test_{i}",
                details={"index": i}
            )
            audit_logger.log_event(event)
        
        stats = audit_logger.get_audit_statistics()
        
        assert stats["total_entries"] == 3
        assert stats["current_sequence"] == 3
        assert stats["last_entry_hash"] is not None
        assert stats["database_size_bytes"] > 0
        assert stats["real_time_verification"] is False
        assert "severity_counts" in stats
    
    def test_error_handling_database_failure(self, temp_dir):
        """Test error handling when database operations fail"""
        logger = AuditLogger(log_directory=temp_dir, testing_mode=True)
        
        # Close any open connections first
        logger._db_lock.acquire()
        try:
            # Remove the database file
            if logger.db_path.exists():
                logger.db_path.unlink()
        finally:
            logger._db_lock.release()
        
        event = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            component="test",
            action="test_action",
            details={}
        )
        
        # Should raise RuntimeError for audit failure
        with pytest.raises(RuntimeError, match="Audit system failure"):
            logger.log_event(event)
    
    def test_thread_safety_basic(self, audit_logger):
        """Test basic thread safety of audit logging"""
        import threading
        import time
        
        results = []
        errors = []
        
        def log_events(thread_id):
            try:
                for i in range(10):
                    event = AuditEvent(
                        event_type=AuditEventType.SYSTEM_STARTUP,
                        severity=AuditSeverity.INFO,
                        component="test",
                        action=f"thread_{thread_id}_event_{i}",
                        details={"thread_id": thread_id, "event_index": i}
                    )
                    entry_id = audit_logger.log_event(event)
                    results.append((thread_id, i, entry_id))
                    time.sleep(0.001)  # Small delay to encourage race conditions
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start multiple threads
        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=log_events, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 30  # 3 threads * 10 events each
        
        # Verify all entries in database
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            assert cursor.fetchone()[0] == 30
            
            # Verify sequence number continuity
            cursor = conn.execute("""
                SELECT sequence_number FROM audit_entries 
                ORDER BY sequence_number
            """)
            sequences = [row[0] for row in cursor.fetchall()]
            expected_sequences = list(range(1, 31))
            assert sequences == expected_sequences
    
    def test_large_details_handling(self, audit_logger):
        """Test handling of large detail objects"""
        large_details = {
            "large_string": "x" * 5000,
            "large_list": list(range(100)),
            "nested_dict": {
                "level1": {
                    "level2": {
                        "large_data": "y" * 3000
                    }
                }
            },
            "normal_data": "this should be preserved"
        }
        
        event = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            component="test",
            action="large_details_test",
            details=large_details
        )
        
        entry_id = audit_logger.log_event(event)
        
        # Verify sanitization and truncation
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT details FROM audit_entries WHERE id = ?
            """, (entry_id,))
            
            stored_details = json.loads(cursor.fetchone()[0])
            
            # Large string should be truncated
            assert stored_details["large_string"].endswith("...[truncated]")
            assert len(stored_details["large_string"]) <= audit_logger.max_detail_length + 15
            
            # Large list should be limited
            assert len(stored_details["large_list"]) <= 10
            
            # Normal data should be preserved
            assert stored_details["normal_data"] == "this should be preserved"
    
    def test_invalid_event_data_handling(self, audit_logger):
        """Test handling of invalid event data"""
        # Test with non-dict details
        event = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            component="test",
            action="invalid_details_test",
            details="this should be a dict"  # Invalid: string instead of dict
        )
        
        entry_id = audit_logger.log_event(event)
        
        # Should handle gracefully
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT details FROM audit_entries WHERE id = ?
            """, (entry_id,))
            
            stored_details = json.loads(cursor.fetchone()[0])
            assert "error" in stored_details
            assert stored_details["error"] == "details_not_dict"