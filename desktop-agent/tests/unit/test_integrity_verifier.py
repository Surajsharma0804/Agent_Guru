"""
Unit Tests for Audit Log Integrity Verifier

Tests the integrity verification system for audit logs including
cryptographic signature verification, hash chain validation, and
tamper detection capabilities.
"""

import pytest
import tempfile
import shutil
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from src.audit.audit_logger import AuditLogger, AuditEvent, AuditEventType, AuditSeverity
from src.audit.integrity_verifier import IntegrityVerifier


class TestIntegrityVerifier:
    """Test suite for audit log integrity verifier"""
    
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
            enable_real_time_verification=False,
            testing_mode=True
        )
    
    @pytest.fixture
    def integrity_verifier(self, audit_logger):
        """Create integrity verifier instance"""
        return IntegrityVerifier(
            db_path=str(audit_logger.db_path),
            signing_key=audit_logger.signing_key
        )
    
    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing"""
        return [
            AuditEvent(
                event_type=AuditEventType.SYSTEM_STARTUP,
                severity=AuditSeverity.INFO,
                component="test",
                action="startup",
                details={"order": 1}
            ),
            AuditEvent(
                event_type=AuditEventType.AUTHORITY_STATE_CHANGE,
                severity=AuditSeverity.INFO,
                component="authority",
                action="state_change",
                details={"from": "LOCKED", "to": "ARMED"}
            ),
            AuditEvent(
                event_type=AuditEventType.INPUT_SIMULATION,
                severity=AuditSeverity.INFO,
                component="input",
                action="keyboard_input",
                details={"text_length": 10}
            )
        ]
    
    def test_verifier_initialization(self, integrity_verifier, audit_logger):
        """Test integrity verifier initialization"""
        assert integrity_verifier.db_path == audit_logger.db_path
        assert integrity_verifier.signing_key == audit_logger.signing_key
    
    def test_verifier_initialization_missing_database(self, temp_dir):
        """Test verifier initialization with missing database"""
        missing_db_path = Path(temp_dir) / "missing.db"
        
        with pytest.raises(FileNotFoundError):
            IntegrityVerifier(
                db_path=str(missing_db_path),
                signing_key=b"test_key" * 8
            )
    
    def test_verify_single_entry_valid(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of a single valid entry"""
        # Log an event
        audit_logger.log_event(sample_events[0])
        
        # Get entry from database
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number LIMIT 1
            """)
            entry_data = cursor.fetchone()
        
        # Verify entry
        result = integrity_verifier.verify_single_entry(entry_data)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["entry_id"] == entry_data[0]
        assert result["sequence_number"] == 1
    
    def test_verify_single_entry_invalid_hash(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of entry with corrupted hash"""
        # Log an event
        audit_logger.log_event(sample_events[0])
        
        # Corrupt the entry hash in database
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("""
                UPDATE audit_entries 
                SET entry_hash = 'corrupted_hash' 
                WHERE sequence_number = 1
            """)
            conn.commit()
        
        # Get corrupted entry
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number LIMIT 1
            """)
            entry_data = cursor.fetchone()
        
        # Verify entry
        result = integrity_verifier.verify_single_entry(entry_data)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Hash mismatch" in error for error in result["errors"])
    
    def test_verify_single_entry_invalid_signature(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of entry with corrupted signature"""
        # Log an event
        audit_logger.log_event(sample_events[0])
        
        # Corrupt the signature in database
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("""
                UPDATE audit_entries 
                SET signature = 'corrupted_signature' 
                WHERE sequence_number = 1
            """)
            conn.commit()
        
        # Get corrupted entry
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number LIMIT 1
            """)
            entry_data = cursor.fetchone()
        
        # Verify entry
        result = integrity_verifier.verify_single_entry(entry_data)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Invalid HMAC signature" in error for error in result["errors"])
    
    def test_verify_hash_chain_valid(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of valid hash chain"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Get all entries
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number
            """)
            entries = cursor.fetchall()
        
        # Verify hash chain
        result = integrity_verifier.verify_hash_chain(entries)
        
        assert result["valid"] is True
        assert result["total_entries"] == 3
        assert len(result["chain_breaks"]) == 0
    
    def test_verify_hash_chain_broken(self, audit_logger, integrity_verifier, sample_events):
        """Test detection of broken hash chain"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Break the hash chain by corrupting previous_hash
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("""
                UPDATE audit_entries 
                SET previous_hash = 'corrupted_previous_hash' 
                WHERE sequence_number = 2
            """)
            conn.commit()
        
        # Get all entries
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number
            """)
            entries = cursor.fetchall()
        
        # Verify hash chain
        result = integrity_verifier.verify_hash_chain(entries)
        
        assert result["valid"] is False
        assert result["total_entries"] == 3
        assert len(result["chain_breaks"]) == 1
        assert result["chain_breaks"][0]["sequence_number"] == 2
    
    def test_verify_sequence_continuity_valid(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of valid sequence continuity"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Get all entries
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number
            """)
            entries = cursor.fetchall()
        
        # Verify sequence continuity
        result = integrity_verifier.verify_sequence_continuity(entries)
        
        assert result["valid"] is True
        assert result["total_entries"] == 3
        assert len(result["sequence_gaps"]) == 0
        assert len(result["duplicate_sequences"]) == 0
        assert result["highest_sequence"] == 3
    
    def test_verify_sequence_continuity_gap(self, audit_logger, integrity_verifier, sample_events):
        """Test detection of sequence gaps"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Create sequence gap by deleting middle entry
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("DELETE FROM audit_entries WHERE sequence_number = 2")
            conn.commit()
        
        # Get remaining entries
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number
            """)
            entries = cursor.fetchall()
        
        # Verify sequence continuity
        result = integrity_verifier.verify_sequence_continuity(entries)
        
        assert result["valid"] is False
        assert result["total_entries"] == 2
        assert len(result["sequence_gaps"]) == 1
        assert result["sequence_gaps"][0]["expected"] == 2
        assert result["sequence_gaps"][0]["actual"] == 3
        assert result["sequence_gaps"][0]["gap_size"] == 1
    
    def test_verify_sequence_continuity_duplicate(self, audit_logger, integrity_verifier, sample_events):
        """
        Test that duplicate sequence numbers are prevented by database constraints.
        
        CRITICAL SECURITY FIX: The database UNIQUE constraint on sequence_number
        is a security feature that prevents audit log tampering. This test verifies
        that the constraint is properly enforced.
        """
        # Log an event
        audit_logger.log_event(sample_events[0])
        
        # Attempt to manually insert duplicate sequence number should fail
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            with sqlite3.connect(audit_logger.db_path) as conn:
                conn.execute("""
                    INSERT INTO audit_entries (
                        id, timestamp, sequence_number, event_type, severity,
                        component, action, details, session_id, user_id,
                        device_id, correlation_id, previous_hash, entry_hash, signature
                    ) VALUES (
                        'duplicate_id', ?, 1, 'SYSTEM_STARTUP', 'INFO',
                        'test', 'duplicate', '{}', NULL, NULL,
                        NULL, NULL, NULL, 'fake_hash', 'fake_signature'
                    )
                """, (datetime.now(timezone.utc).isoformat(),))
                conn.commit()
    
    def test_verify_complete_integrity_valid(self, audit_logger, integrity_verifier, sample_events):
        """Test complete integrity verification of valid log"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Verify complete integrity
        result = integrity_verifier.verify_complete_integrity()
        
        assert result.verified is True
        assert result.total_entries == 3
        assert result.hash_chain_valid is True
        assert result.signatures_valid is True
        assert result.sequence_valid is True
        assert len(result.invalid_entries) == 0
        assert result.error_message is None
    
    def test_verify_complete_integrity_corrupted(self, audit_logger, integrity_verifier, sample_events):
        """Test complete integrity verification of corrupted log"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Corrupt multiple aspects
        with sqlite3.connect(audit_logger.db_path) as conn:
            # Corrupt hash
            conn.execute("""
                UPDATE audit_entries 
                SET entry_hash = 'corrupted_hash' 
                WHERE sequence_number = 1
            """)
            
            # Break hash chain
            conn.execute("""
                UPDATE audit_entries 
                SET previous_hash = 'corrupted_previous_hash' 
                WHERE sequence_number = 2
            """)
            
            conn.commit()
        
        # Verify complete integrity
        result = integrity_verifier.verify_complete_integrity()
        
        assert result.verified is False
        assert result.total_entries == 3
        assert result.hash_chain_valid is False
        assert result.signatures_valid is False
        assert len(result.invalid_entries) > 0
    
    def test_verify_complete_integrity_empty_log(self, integrity_verifier):
        """Test complete integrity verification of empty log"""
        result = integrity_verifier.verify_complete_integrity()
        
        assert result.verified is True
        assert result.total_entries == 0
        assert result.hash_chain_valid is True
        assert result.signatures_valid is True
        assert result.sequence_valid is True
        assert len(result.invalid_entries) == 0
    
    def test_verify_complete_integrity_with_constraints(self, audit_logger, integrity_verifier, sample_events):
        """Test complete integrity verification with sequence constraints"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Verify with sequence range constraint
        result = integrity_verifier.verify_complete_integrity(
            start_sequence=2,
            end_sequence=3
        )
        
        assert result.verified is True
        assert result.total_entries == 2  # Only entries 2 and 3
        assert result.hash_chain_valid is True
        assert result.signatures_valid is True
        assert result.sequence_valid is True
    
    def test_verify_complete_integrity_with_max_entries(self, audit_logger, integrity_verifier, sample_events):
        """Test complete integrity verification with entry limit"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Verify with max entries constraint
        result = integrity_verifier.verify_complete_integrity(max_entries=2)
        
        assert result.verified is True
        assert result.total_entries == 2  # Limited to 2 entries
        assert result.hash_chain_valid is True
        assert result.signatures_valid is True
        assert result.sequence_valid is True
    
    def test_verify_recent_entries(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of recent entries"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        # Verify recent entries
        result = integrity_verifier.verify_recent_entries(count=2)
        
        assert result.verified is True
        assert result.total_entries == 2  # Last 2 entries
        assert result.hash_chain_valid is True
        assert result.signatures_valid is True
        assert result.sequence_valid is True
    
    def test_verify_recent_entries_empty_log(self, integrity_verifier):
        """Test verification of recent entries on empty log"""
        result = integrity_verifier.verify_recent_entries(count=10)
        
        assert result.verified is True
        assert result.total_entries == 0
        assert result.hash_chain_valid is True
        assert result.signatures_valid is True
        assert result.sequence_valid is True
    
    def test_get_verification_statistics(self, audit_logger, integrity_verifier, sample_events):
        """Test verification statistics generation"""
        # Log multiple events
        for event in sample_events:
            audit_logger.log_event(event)
        
        stats = integrity_verifier.get_verification_statistics()
        
        assert stats["total_entries"] == 3
        assert stats["sequence_range"]["min"] == 1
        assert stats["sequence_range"]["max"] == 3
        assert stats["sequence_range"]["expected_count"] == 3
        assert stats["database_size_bytes"] > 0
        assert stats["has_signing_key"] is True
        assert stats["date_range"]["earliest"] is not None
        assert stats["date_range"]["latest"] is not None
    
    def test_get_verification_statistics_empty_log(self, integrity_verifier):
        """Test verification statistics for empty log"""
        stats = integrity_verifier.get_verification_statistics()
        
        assert stats["total_entries"] == 0
        assert stats["sequence_range"]["min"] is None
        assert stats["sequence_range"]["max"] is None
        assert stats["sequence_range"]["expected_count"] == 0
        assert stats["date_range"]["earliest"] is None
        assert stats["date_range"]["latest"] is None
    
    def test_verify_single_entry_invalid_json(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of entry with invalid JSON in details"""
        # Log an event
        audit_logger.log_event(sample_events[0])
        
        # Corrupt the JSON in details field
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("""
                UPDATE audit_entries 
                SET details = 'invalid json {' 
                WHERE sequence_number = 1
            """)
            conn.commit()
        
        # Get corrupted entry
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number LIMIT 1
            """)
            entry_data = cursor.fetchone()
        
        # Verify entry
        result = integrity_verifier.verify_single_entry(entry_data)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Invalid JSON" in error for error in result["errors"])
    
    def test_verify_single_entry_invalid_timestamp(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of entry with invalid timestamp"""
        # Log an event
        audit_logger.log_event(sample_events[0])
        
        # Corrupt the timestamp
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("""
                UPDATE audit_entries 
                SET timestamp = 'invalid_timestamp' 
                WHERE sequence_number = 1
            """)
            conn.commit()
        
        # Get corrupted entry
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number LIMIT 1
            """)
            entry_data = cursor.fetchone()
        
        # Verify entry
        result = integrity_verifier.verify_single_entry(entry_data)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Invalid timestamp format" in error for error in result["errors"])
    
    def test_verify_single_entry_invalid_sequence(self, audit_logger, integrity_verifier, sample_events):
        """Test verification of entry with invalid sequence number"""
        # Log an event
        audit_logger.log_event(sample_events[0])
        
        # Corrupt the sequence number
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("""
                UPDATE audit_entries 
                SET sequence_number = -1 
                WHERE sequence_number = 1
            """)
            conn.commit()
        
        # Get corrupted entry
        with integrity_verifier._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY id LIMIT 1
            """)
            entry_data = cursor.fetchone()
        
        # Verify entry
        result = integrity_verifier.verify_single_entry(entry_data)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Invalid sequence number" in error for error in result["errors"])