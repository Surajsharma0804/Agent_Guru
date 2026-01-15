"""
Property-Based Tests for Audit Logging System

This module contains property-based tests that validate the audit logging system's
cryptographic integrity, tamper detection, and data protection capabilities.

Tests validate:
- Property 26: Command Execution Logging Completeness
- Property 27: Cryptographic Signature Integrity
- Property 28: Signature Chain Integrity
- Property 29: Tamper Detection
- Property 30: Sensitive Data Redaction

Requirements validated: 5.1, 5.4, 5.5, 5.6, 5.8
"""

import hashlib
import hmac
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit.audit_logger import AuditEvent, AuditEventType, AuditLogger, AuditSeverity, IntegrityVerificationResult

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
def audit_logger(temp_audit_dir):
    """Create audit logger instance for testing"""
    return AuditLogger(
        log_directory=temp_audit_dir,
        enable_real_time_verification=False,
        testing_mode=True
    )


# ============================================================================
# Test Strategies
# ============================================================================

@st.composite
def command_text_strategy(draw):
    """Generate command text for testing"""
    commands = [
        "open notepad",
        "write hello world",
        "send message to john",
        "search for python tutorial",
        "close chrome",
        "type this is a test",
        "open calculator and add 5 plus 3"
    ]
    return draw(st.sampled_from(commands))


@st.composite
def execution_result_strategy(draw):
    """Generate execution results"""
    return draw(st.sampled_from(["success", "failure", "timeout", "error"]))


@st.composite
def user_id_strategy(draw):
    """Generate user IDs"""
    return draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='_-'
    )))


@st.composite
def session_id_strategy(draw):
    """Generate session IDs"""
    # Use draw to generate a UUID-like string
    return draw(st.uuids()).hex


@st.composite
def audit_event_strategy(draw):
    """Generate random audit events"""
    event_type = draw(st.sampled_from(list(AuditEventType)))
    severity = draw(st.sampled_from(list(AuditSeverity)))
    component = draw(st.sampled_from([
        "authority", "command_executor", "voice_interface",
        "tts_service", "llm_adapter", "memory_system"
    ]))
    action = draw(st.sampled_from([
        "execute_command", "grant_authority", "revoke_authority",
        "speak_text", "transcribe_audio", "store_conversation"
    ]))
    
    # Generate details without sensitive data
    details = {
        "action_type": draw(st.sampled_from(["system", "user", "automated"])),
        "duration_ms": draw(st.integers(min_value=0, max_value=10000)),
        "status": draw(st.sampled_from(["started", "completed", "failed"]))
    }
    
    return AuditEvent(
        event_type=event_type,
        severity=severity,
        component=component,
        action=action,
        details=details,
        session_id=draw(st.one_of(st.none(), session_id_strategy())),
        user_id=draw(st.one_of(st.none(), user_id_strategy()))
    )


@st.composite
def sensitive_data_strategy(draw):
    """Generate data containing sensitive information"""
    sensitive_keys = [
        "password", "secret", "token", "credential", "auth",
        "biometric", "fingerprint", "face_data", "voice_data",
        "private_key", "signing_key", "encryption_key", "api_key"
    ]
    
    key = draw(st.sampled_from(sensitive_keys))
    value = draw(st.text(min_size=10, max_size=100))
    
    return {key: value}


# ============================================================================
# Property 26: Command Execution Logging Completeness
# ============================================================================

@pytest.mark.property
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    command=command_text_strategy(),
    result=execution_result_strategy(),
    user=user_id_strategy(),
    execution_time=st.floats(min_value=0.0, max_value=10.0)
)
def test_property_26_command_execution_logging_completeness(
    audit_logger, command, result, user, execution_time
):
    """
    Property 26: Command Execution Logging Completeness
    
    For any command execution, the Audit_Logger should create a log entry
    containing timestamp, user, command text, and result.
    
    Feature: guru-complete-system, Property 26: Command Execution Logging Completeness
    Validates: Requirements 5.1
    """
    # Log command execution
    entry_id = audit_logger.log_command_execution(
        command=command,
        result=result,
        user=user,
        execution_time=execution_time
    )
    
    # Verify entry was created
    assert entry_id is not None
    
    # Verify entry exists in database
    import sqlite3
    with sqlite3.connect(audit_logger.db_path) as conn:
        cursor = conn.execute("""
            SELECT id, timestamp, event_type, component, action, details, user_id
            FROM audit_entries
            WHERE id = ?
        """, (entry_id,))
        
        row = cursor.fetchone()
        assert row is not None, "Audit entry should exist in database"
        
        # Verify completeness
        assert row[0] == entry_id, "Entry ID should match"
        assert row[1] is not None, "Timestamp should be present"
        assert row[2] == AuditEventType.COMMAND_EXECUTED.value, "Event type should be COMMAND_EXECUTED"
        assert row[3] == "command_executor", "Component should be command_executor"
        assert row[4] == "execute_command", "Action should be execute_command"
        assert row[6] == user, "User ID should match"
        
        # Verify details contain command and result
        details = json.loads(row[5])
        assert "command" in details, "Details should contain command"
        assert "result" in details, "Details should contain result"
        assert details["command"] == command, "Command should match"
        assert details["result"] == result, "Result should match"


# ============================================================================
# Property 27: Cryptographic Signature Integrity
# ============================================================================

@pytest.mark.property
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(event=audit_event_strategy())
def test_property_27_cryptographic_signature_integrity(audit_logger, event):
    """
    Property 27: Cryptographic Signature Integrity
    
    For any audit log entry, it should have a valid HMAC-SHA256 signature
    computed from its contents.
    
    Feature: guru-complete-system, Property 27: Cryptographic Signature Integrity
    Validates: Requirements 5.4
    """
    # Log event
    entry_id = audit_logger.log_event(event)
    
    # Retrieve entry from database
    import sqlite3
    with sqlite3.connect(audit_logger.db_path) as conn:
        cursor = conn.execute("""
            SELECT id, timestamp, sequence_number, event_type, component, action,
                   details, previous_hash, entry_hash, signature
            FROM audit_entries
            WHERE id = ?
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
        
        # Recalculate hash
        expected_hash = audit_logger._calculate_entry_hash(entry_data)
        actual_hash = row[8]
        
        assert expected_hash == actual_hash, "Entry hash should match calculated hash"
        
        # Recalculate signature
        expected_signature = audit_logger._sign_entry(actual_hash)
        actual_signature = row[9]
        
        assert expected_signature == actual_signature, "Signature should be valid HMAC-SHA256"


# ============================================================================
# Property 28: Signature Chain Integrity
# ============================================================================

@pytest.mark.property
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    events=st.lists(audit_event_strategy(), min_size=2, max_size=10)
)
def test_property_28_signature_chain_integrity(audit_logger, events):
    """
    Property 28: Signature Chain Integrity
    
    For any pair of consecutive audit log entries, the second entry's
    previous_signature should match the first entry's signature.
    
    Feature: guru-complete-system, Property 28: Signature Chain Integrity
    Validates: Requirements 5.5
    """
    # Log multiple events
    entry_ids = []
    for event in events:
        entry_id = audit_logger.log_event(event)
        entry_ids.append(entry_id)
    
    # Retrieve all entries in sequence order
    import sqlite3
    with sqlite3.connect(audit_logger.db_path) as conn:
        cursor = conn.execute("""
            SELECT id, entry_hash, previous_hash, sequence_number
            FROM audit_entries
            WHERE id IN ({})
            ORDER BY sequence_number ASC
        """.format(','.join('?' * len(entry_ids))), entry_ids)
        
        entries = cursor.fetchall()
        
        # Verify chain integrity
        for i in range(1, len(entries)):
            previous_entry = entries[i - 1]
            current_entry = entries[i]
            
            previous_hash = previous_entry[1]  # entry_hash of previous
            current_previous_hash = current_entry[2]  # previous_hash of current
            
            assert current_previous_hash == previous_hash, \
                f"Chain break detected: entry {i} previous_hash doesn't match entry {i-1} hash"


# ============================================================================
# Property 29: Tamper Detection
# ============================================================================

@pytest.mark.property
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    events=st.lists(audit_event_strategy(), min_size=5, max_size=10),
    tamper_index=st.integers(min_value=0, max_value=4)
)
def test_property_29_tamper_detection(events, tamper_index):
    """
    Property 29: Tamper Detection
    
    For any audit log that has been tampered with, the verify_integrity()
    function should detect the tampering and report the violated entries.
    
    Feature: guru-complete-system, Property 29: Tamper Detection
    Validates: Requirements 5.6
    """
    assume(tamper_index < len(events))
    
    # Create completely fresh temp directory for this test
    temp_dir = tempfile.mkdtemp()
    try:
        # Create fresh audit logger for this test
        audit_logger = AuditLogger(
            log_directory=temp_dir,
            enable_real_time_verification=False,
            testing_mode=True
        )
        
        # Log events
        entry_ids = []
        for event in events:
            entry_id = audit_logger.log_event(event)
            entry_ids.append(entry_id)
        
        # Verify integrity before tampering
        result_before = audit_logger.verify_integrity()
        assert result_before.verified, "Integrity should be valid before tampering"
        assert result_before.hash_chain_valid, "Hash chain should be valid before tampering"
        assert result_before.signatures_valid, "Signatures should be valid before tampering"
        assert len(result_before.invalid_entries) == 0, "No invalid entries before tampering"
        
        # Tamper with an entry by modifying its details
        import sqlite3
        tampered_entry_id = entry_ids[tamper_index]
        with sqlite3.connect(audit_logger.db_path) as conn:
            # Modify the details field (this breaks the hash)
            conn.execute("""
                UPDATE audit_entries
                SET details = ?
                WHERE id = ?
            """, (json.dumps({"tampered": "data"}), tampered_entry_id))
            conn.commit()
        
        # Verify integrity after tampering
        result_after = audit_logger.verify_integrity()
        
        # Tampering should be detected
        assert not result_after.verified, "Integrity should be invalid after tampering"
        assert not result_after.hash_chain_valid, "Hash chain should be invalid after tampering"
        assert len(result_after.invalid_entries) > 0, "Invalid entries should be detected"
        
        # Verify the tampered entry is in the invalid list
        tampered_sequences = [entry["sequence_number"] for entry in result_after.invalid_entries]
        
        # Get sequence number of tampered entry
        with sqlite3.connect(audit_logger.db_path) as conn:
            cursor = conn.execute("""
                SELECT sequence_number FROM audit_entries WHERE id = ?
            """, (tampered_entry_id,))
            tampered_sequence = cursor.fetchone()[0]
        
        assert tampered_sequence in tampered_sequences, \
            "Tampered entry should be detected in invalid entries list"
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Property 30: Sensitive Data Redaction
# ============================================================================

@pytest.mark.property
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(sensitive_data=sensitive_data_strategy())
def test_property_30_sensitive_data_redaction(audit_logger, sensitive_data):
    """
    Property 30: Sensitive Data Redaction
    
    For any audit log entry, it should never contain passwords, biometric
    templates, or other sensitive personal information.
    
    Feature: guru-complete-system, Property 30: Sensitive Data Redaction
    Validates: Requirements 5.8
    """
    # Create event with sensitive data
    event = AuditEvent(
        event_type=AuditEventType.COMMAND_EXECUTED,
        severity=AuditSeverity.INFO,
        component="test_component",
        action="test_action",
        details=sensitive_data
    )
    
    # Log event
    entry_id = audit_logger.log_event(event)
    
    # Retrieve entry from database
    import sqlite3
    with sqlite3.connect(audit_logger.db_path) as conn:
        cursor = conn.execute("""
            SELECT details FROM audit_entries WHERE id = ?
        """, (entry_id,))
        
        row = cursor.fetchone()
        assert row is not None
        
        details = json.loads(row[0])
        
        # Verify sensitive data is redacted
        for key, value in details.items():
            if isinstance(value, str):
                assert value == "[REDACTED]", \
                    f"Sensitive key '{key}' should be redacted, but got: {value}"
            else:
                # If not redacted, it should not contain the original sensitive value
                assert value != sensitive_data.get(key), \
                    f"Sensitive data should not be stored in plaintext"


# ============================================================================
# Additional Integration Tests
# ============================================================================

@pytest.mark.property
def test_verify_integrity_empty_log(audit_logger):
    """Test integrity verification on empty log"""
    result = audit_logger.verify_integrity()
    
    assert result.verified
    assert result.total_entries == 0
    assert result.hash_chain_valid
    assert result.signatures_valid
    assert result.sequence_valid
    assert len(result.invalid_entries) == 0


@pytest.mark.property
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    events=st.lists(audit_event_strategy(), min_size=10, max_size=50)
)
def test_verify_integrity_large_log(events):
    """Test integrity verification on larger logs"""
    # Create completely fresh temp directory for this test
    temp_dir = tempfile.mkdtemp()
    try:
        # Create fresh audit logger for this test
        audit_logger = AuditLogger(
            log_directory=temp_dir,
            enable_real_time_verification=False,
            testing_mode=True
        )
        
        # Log many events
        for event in events:
            audit_logger.log_event(event)
        
        # Verify integrity
        result = audit_logger.verify_integrity()
        
        assert result.verified
        assert result.total_entries == len(events)
        assert result.hash_chain_valid
        assert result.signatures_valid
        assert result.sequence_valid
        assert len(result.invalid_entries) == 0
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.property
def test_audit_statistics(audit_logger):
    """Test audit statistics retrieval"""
    # Log some events
    for i in range(10):
        event = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            component="system",
            action=f"test_action_{i}",
            details={"test": i}
        )
        audit_logger.log_event(event)
    
    # Get statistics
    stats = audit_logger.get_audit_statistics()
    
    assert stats["total_entries"] == 10
    assert stats["current_sequence"] == 10
    assert "database_path" in stats
    assert "database_size_bytes" in stats
