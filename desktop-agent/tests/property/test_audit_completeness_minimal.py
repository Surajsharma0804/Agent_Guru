"""
Minimal Property-Based Test for Audit Completeness

**Property 9: Audit Completeness**
**Validates: Requirements 1.6, 3.4, 17.8, 23.7, 25.9**
"""

import pytest
import tempfile
import shutil
from hypothesis import given, strategies as st, settings

from src.audit.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity
)
from src.audit.integrity_verifier import IntegrityVerifier


@given(st.integers(min_value=1, max_value=10))
@settings(max_examples=5, deadline=5000)
def test_property_audit_completeness_basic(num_events):
    """
    Property: All audit events are logged with cryptographic integrity
    
    For any number of audit events, all events should be logged with
    cryptographic integrity and complete coverage.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Create audit logger
        audit_logger = AuditLogger(
            log_directory=temp_dir,
            enable_real_time_verification=False,
            testing_mode=True
        )
        
        # Create integrity verifier
        integrity_verifier = IntegrityVerifier(
            db_path=str(audit_logger.db_path),
            signing_key=audit_logger.signing_key
        )
        
        # Log multiple events
        entry_ids = []
        for i in range(num_events):
            event = AuditEvent(
                event_type=AuditEventType.SYSTEM_STARTUP,
                severity=AuditSeverity.INFO,
                component=f"test_component_{i}",
                action=f"test_action_{i}",
                details={"index": i, "test_data": f"value_{i}"}
            )
            entry_id = audit_logger.log_event(event)
            entry_ids.append(entry_id)
        
        # Verify all events were logged
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            logged_count = cursor.fetchone()[0]
            assert logged_count == num_events, f"Expected {num_events} entries, found {logged_count}"
        
        # Verify integrity
        verification_result = integrity_verifier.verify_complete_integrity()
        assert verification_result.verified, f"Integrity verification failed: {verification_result.error_message}"
        assert verification_result.total_entries == num_events
        assert verification_result.hash_chain_valid
        assert verification_result.signatures_valid
        assert verification_result.sequence_valid
        assert len(verification_result.invalid_entries) == 0
        
        # Verify unique entry IDs
        assert len(set(entry_ids)) == len(entry_ids), "Entry IDs are not unique"
        
        # Verify completeness - all required fields present
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, component, 
                       action, details, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number
            """)
            
            entries = cursor.fetchall()
            assert len(entries) == num_events
            
            for i, entry in enumerate(entries):
                # Verify all required fields are present and valid
                assert entry[0] is not None  # id
                assert entry[1] is not None  # timestamp
                assert entry[2] == i + 1     # sequence_number
                assert entry[3] is not None  # event_type
                assert entry[4] is not None  # component
                assert entry[5] is not None  # action
                assert entry[6] is not None  # details
                assert entry[7] is not None and len(entry[7]) == 64  # entry_hash (SHA-256)
                assert entry[8] is not None and len(entry[8]) == 64  # signature (HMAC-SHA256)
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_audit_completeness_tamper_detection():
    """
    Test that audit completeness includes tamper detection
    
    Validates that any tampering with audit logs is detected
    by the integrity verification system.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Create audit logger
        audit_logger = AuditLogger(
            log_directory=temp_dir,
            enable_real_time_verification=False,
            testing_mode=True
        )
        
        # Create integrity verifier
        integrity_verifier = IntegrityVerifier(
            db_path=str(audit_logger.db_path),
            signing_key=audit_logger.signing_key
        )
        
        # Log some events
        for i in range(3):
            event = AuditEvent(
                event_type=AuditEventType.AUTHORITY_STATE_CHANGE,
                severity=AuditSeverity.INFO,
                component="authority",
                action=f"state_change_{i}",
                details={"from": "LOCKED", "to": "ARMED", "index": i}
            )
            audit_logger.log_event(event)
        
        # Verify initial integrity
        initial_verification = integrity_verifier.verify_complete_integrity()
        assert initial_verification.verified, "Initial integrity check failed"
        assert initial_verification.total_entries == 3
        
        # Tamper with an entry
        import sqlite3
        with sqlite3.connect(audit_logger.db_path) as conn:
            conn.execute("""
                UPDATE audit_entries 
                SET entry_hash = 'tampered_hash_12345678901234567890123456789012' 
                WHERE sequence_number = 2
            """)
            conn.commit()
        
        # Verify tampering is detected
        tampered_verification = integrity_verifier.verify_complete_integrity()
        assert not tampered_verification.verified, "Tampering was not detected"
        assert not tampered_verification.signatures_valid, "Signature tampering not detected"
        assert len(tampered_verification.invalid_entries) > 0, "No invalid entries reported"
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_audit_completeness_sensitive_data_protection():
    """
    Test that audit completeness includes sensitive data protection
    
    Validates that sensitive data is never stored in audit logs
    while maintaining complete audit coverage.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Create audit logger
        audit_logger = AuditLogger(
            log_directory=temp_dir,
            enable_real_time_verification=False,
            testing_mode=True
        )
        
        # Log event with sensitive data
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.ERROR,
            component="security",
            action="authentication_failure",
            details={
                "user_id": "test_user",
                "password": "secret123",  # Should be redacted
                "private_key": "key_data",  # Should be redacted
                "safe_data": "this_is_ok",  # Should be preserved
                "api_key": "secret_api_key"  # Should be redacted
            }
        )
        
        entry_id = audit_logger.log_event(event)
        
        # Verify event was logged (completeness)
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            assert cursor.fetchone()[0] == 1
        
        # Verify sensitive data protection
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT details FROM audit_entries WHERE id = ?", (entry_id,))
            details_json = cursor.fetchone()[0]
            
            import json
            details = json.loads(details_json)
            
            # Sensitive data should be redacted
            assert details["password"] == "[REDACTED]"
            assert details["private_key"] == "[REDACTED]"
            assert details["api_key"] == "[REDACTED]"
            
            # Safe data should be preserved
            assert details["safe_data"] == "this_is_ok"
            assert details["user_id"] == "test_user"
        
        # Verify integrity is maintained despite redaction
        integrity_verifier = IntegrityVerifier(
            db_path=str(audit_logger.db_path),
            signing_key=audit_logger.signing_key
        )
        
        verification_result = integrity_verifier.verify_complete_integrity()
        assert verification_result.verified, "Integrity verification failed after redaction"
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)