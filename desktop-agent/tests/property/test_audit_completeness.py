"""
Property-Based Tests for Audit Completeness

Tests comprehensive audit coverage, data integrity, and completeness
verification across all system operations using property-based testing.

**Property 9: Audit Completeness**
**Validates: Requirements 1.6, 3.4, 17.8, 23.7, 25.9**
"""

import pytest
import tempfile
import shutil
import json
import hashlib
import hmac
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List
from hypothesis import given, strategies as st, settings, assume, note
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, initialize, invariant

from src.audit.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditLogEntry,
    IntegrityVerificationResult
)
from src.audit.integrity_verifier import IntegrityVerifier


# Strategy for generating valid audit events
@st.composite
def audit_event_strategy(draw):
    """Generate valid audit events for property testing"""
    event_type = draw(st.sampled_from(list(AuditEventType)))
    severity = draw(st.sampled_from(list(AuditSeverity)))
    component = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    action = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    
    # Generate safe details (no sensitive data)
    details = draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        values=st.one_of(
            st.text(max_size=100),
            st.integers(min_value=0, max_value=1000000),
            st.booleans(),
            st.none()
        ),
        min_size=0,
        max_size=10
    ))
    
    session_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    user_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    device_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    correlation_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    
    return AuditEvent(
        event_type=event_type,
        severity=severity,
        component=component,
        action=action,
        details=details,
        session_id=session_id,
        user_id=user_id,
        device_id=device_id,
        correlation_id=correlation_id
    )


def test_simple_audit_completeness():
    """Simple test to verify audit completeness functionality"""
    temp_dir = tempfile.mkdtemp()
    try:
        audit_logger = AuditLogger(
            log_directory=temp_dir,
            enable_real_time_verification=False,
            testing_mode=True
        )
        
        # Create a simple event
        event = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            component="test",
            action="simple_test",
            details={"test": "value"}
        )
        
        # Log the event
        entry_id = audit_logger.log_event(event)
        assert entry_id is not None
        
        # Verify integrity
        integrity_verifier = IntegrityVerifier(
            db_path=str(audit_logger.db_path),
            signing_key=audit_logger.signing_key
        )
        
        result = integrity_verifier.verify_complete_integrity()
        assert result.verified
        assert result.total_entries == 1
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class TestAuditCompleteness:
    """Property-based tests for comprehensive audit completeness"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test logs"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
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
    
    @given(st.lists(audit_event_strategy(), min_size=1, max_size=10))
    @settings(max_examples=5, deadline=10000)
    def test_property_all_events_logged_with_integrity(self, audit_logger, integrity_verifier, events):
        """
        Property: All audit events are logged with cryptographic integrity
        
        For any sequence of audit events, all events should be logged with:
        - Unique entry IDs
        - Cryptographic signatures
        - Hash chain integrity
        - Sequential numbering
        """
        note(f"Testing {len(events)} audit events")
        
        # Log all events
        entry_ids = []
        for event in events:
            entry_id = audit_logger.log_event(event)
            entry_ids.append(entry_id)
            note(f"Logged event: {event.event_type.value} -> {entry_id}")
        
        # Verify all events were logged
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            logged_count = cursor.fetchone()[0]
            assert logged_count == len(events), f"Expected {len(events)} entries, found {logged_count}"
        
        # Verify integrity
        verification_result = integrity_verifier.verify_complete_integrity()
        assert verification_result.verified, f"Integrity verification failed: {verification_result.error_message}"
        assert verification_result.total_entries == len(events)
        assert verification_result.hash_chain_valid
        assert verification_result.signatures_valid
        assert verification_result.sequence_valid
        assert len(verification_result.invalid_entries) == 0
        
        # Verify unique entry IDs
        assert len(set(entry_ids)) == len(entry_ids), "Entry IDs are not unique"
        """
        Property: All audit events are logged with cryptographic integrity
        
        For any sequence of audit events, all events should be logged with:
        - Unique entry IDs
        - Cryptographic signatures
        - Hash chain integrity
        - Sequential numbering
        """
        note(f"Testing {len(events)} audit events")
        
        # Log all events
        entry_ids = []
        for event in events:
            entry_id = audit_logger.log_event(event)
            entry_ids.append(entry_id)
            note(f"Logged event: {event.event_type.value} -> {entry_id}")
        
        # Verify all events were logged
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            logged_count = cursor.fetchone()[0]
            assert logged_count == len(events), f"Expected {len(events)} entries, found {logged_count}"
        
        # Verify integrity
        verification_result = integrity_verifier.verify_complete_integrity()
        assert verification_result.verified, f"Integrity verification failed: {verification_result.error_message}"
        assert verification_result.total_entries == len(events)
        assert verification_result.hash_chain_valid
        assert verification_result.signatures_valid
        assert verification_result.sequence_valid
        assert len(verification_result.invalid_entries) == 0
        
        # Verify unique entry IDs
        assert len(set(entry_ids)) == len(entry_ids), "Entry IDs are not unique"
    
    @given(st.lists(audit_event_strategy(), min_size=5, max_size=20))
    @settings(max_examples=10, deadline=10000)
    def test_property_hash_chain_tamper_detection(self, audit_logger, integrity_verifier, events):
        """
        Property: Hash chain detects any tampering attempts
        
        For any sequence of logged events, tampering with any entry should be detected
        by integrity verification.
        """
        note(f"Testing tamper detection with {len(events)} events")
        
        # Log all events
        for event in events:
            audit_logger.log_event(event)
        
        # Verify initial integrity
        initial_verification = integrity_verifier.verify_complete_integrity()
        assert initial_verification.verified, "Initial integrity check failed"
        
        # Tamper with a random entry
        with sqlite3.connect(audit_logger.db_path) as conn:
            # Get a random entry to tamper with
            cursor = conn.execute("SELECT sequence_number FROM audit_entries ORDER BY RANDOM() LIMIT 1")
            row = cursor.fetchone()
            if row:
                tampered_sequence = row[0]
                note(f"Tampering with entry sequence {tampered_sequence}")
                
                # Corrupt the entry hash
                conn.execute("""
                    UPDATE audit_entries 
                    SET entry_hash = 'tampered_hash_' || entry_hash 
                    WHERE sequence_number = ?
                """, (tampered_sequence,))
                conn.commit()
                
                # Verify tampering is detected
                tampered_verification = integrity_verifier.verify_complete_integrity()
                assert not tampered_verification.verified, "Tampering was not detected"
                assert not tampered_verification.signatures_valid, "Signature tampering not detected"
                assert len(tampered_verification.invalid_entries) > 0, "No invalid entries reported"
    
    @given(st.lists(audit_event_strategy(), min_size=3, max_size=15))
    @settings(max_examples=10, deadline=10000)
    def test_property_sequence_gap_detection(self, audit_logger, integrity_verifier, events):
        """
        Property: Sequence gaps are detected in audit logs
        
        For any sequence of logged events, removing entries should be detected
        as sequence gaps during integrity verification.
        """
        note(f"Testing sequence gap detection with {len(events)} events")
        
        # Log all events
        for event in events:
            audit_logger.log_event(event)
        
        # Verify initial integrity
        initial_verification = integrity_verifier.verify_complete_integrity()
        assert initial_verification.verified, "Initial integrity check failed"
        
        # Remove a random entry to create a gap
        with sqlite3.connect(audit_logger.db_path) as conn:
            cursor = conn.execute("SELECT sequence_number FROM audit_entries WHERE sequence_number > 1 ORDER BY RANDOM() LIMIT 1")
            row = cursor.fetchone()
            if row:
                deleted_sequence = row[0]
                note(f"Deleting entry sequence {deleted_sequence}")
                
                conn.execute("DELETE FROM audit_entries WHERE sequence_number = ?", (deleted_sequence,))
                conn.commit()
                
                # Verify gap is detected
                gap_verification = integrity_verifier.verify_complete_integrity()
                assert not gap_verification.verified, "Sequence gap was not detected"
                assert not gap_verification.sequence_valid, "Sequence validation should fail"
    
    @given(st.lists(audit_event_strategy(), min_size=1, max_size=30))
    @settings(max_examples=15, deadline=10000)
    def test_property_sensitive_data_never_logged(self, audit_logger, events):
        """
        Property: Sensitive data is never stored in audit logs
        
        For any audit events containing sensitive data patterns, the sensitive
        content should be redacted in the stored logs.
        """
        note(f"Testing sensitive data redaction with {len(events)} events")
        
        # Add sensitive data to some events
        sensitive_keys = ['password', 'secret', 'private_key', 'biometric', 'text_content']
        for i, event in enumerate(events):
            if i % 3 == 0:  # Add sensitive data to every third event
                sensitive_key = sensitive_keys[i % len(sensitive_keys)]
                event.details[sensitive_key] = f"sensitive_value_{i}"
                note(f"Added sensitive key '{sensitive_key}' to event {i}")
        
        # Log all events
        for event in events:
            audit_logger.log_event(event)
        
        # Verify sensitive data is redacted
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT details FROM audit_entries")
            for row in cursor.fetchall():
                details = json.loads(row[0])
                for key, value in details.items():
                    if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'biometric', 'text_content']):
                        assert value == "[REDACTED]", f"Sensitive data not redacted: {key}={value}"
    
    @given(st.lists(audit_event_strategy(), min_size=2, max_size=10))
    @settings(max_examples=10, deadline=10000)
    def test_property_concurrent_logging_integrity(self, audit_logger, integrity_verifier, events):
        """
        Property: Concurrent logging maintains integrity
        
        For any set of events logged concurrently, all events should be logged
        with maintained hash chain integrity and no corruption.
        """
        import threading
        import time
        
        note(f"Testing concurrent logging with {len(events)} events")
        
        results = []
        errors = []
        
        def log_event_thread(event, thread_id):
            try:
                entry_id = audit_logger.log_event(event)
                results.append((thread_id, entry_id))
                time.sleep(0.001)  # Small delay to encourage race conditions
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start concurrent threads
        threads = []
        for i, event in enumerate(events):
            thread = threading.Thread(target=log_event_thread, args=(event, i))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent logging errors: {errors}"
        assert len(results) == len(events), f"Expected {len(events)} results, got {len(results)}"
        
        # Verify integrity after concurrent logging
        verification_result = integrity_verifier.verify_complete_integrity()
        assert verification_result.verified, f"Concurrent logging broke integrity: {verification_result.error_message}"
        assert verification_result.total_entries == len(events)
        assert verification_result.hash_chain_valid
        assert verification_result.signatures_valid
        assert verification_result.sequence_valid
    
    @given(st.lists(audit_event_strategy(), min_size=1, max_size=20))
    @settings(max_examples=10, deadline=10000)
    def test_property_audit_completeness_coverage(self, audit_logger, events):
        """
        Property: Audit completeness covers all required event types
        
        For any sequence of events covering different event types, all events
        should be logged with complete context information.
        """
        note(f"Testing audit completeness coverage with {len(events)} events")
        
        # Ensure we have diverse event types
        event_types_used = set()
        for event in events:
            event_types_used.add(event.event_type)
        
        note(f"Event types covered: {[et.value for et in event_types_used]}")
        
        # Log all events
        for event in events:
            audit_logger.log_event(event)
        
        # Verify complete context is logged
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT event_type, component, action, details, timestamp, 
                       entry_hash, signature, sequence_number
                FROM audit_entries ORDER BY sequence_number
            """)
            
            logged_entries = cursor.fetchall()
            assert len(logged_entries) == len(events)
            
            for i, (event_type, component, action, details_json, timestamp, 
                   entry_hash, signature, sequence_number) in enumerate(logged_entries):
                
                # Verify required fields are present
                assert event_type is not None and event_type != ""
                assert component is not None and component != ""
                assert action is not None and action != ""
                assert details_json is not None
                assert timestamp is not None
                assert entry_hash is not None and len(entry_hash) == 64  # SHA-256 hex
                assert signature is not None and len(signature) == 64  # HMAC-SHA256 hex
                assert sequence_number == i + 1
                
                # Verify details can be parsed
                details = json.loads(details_json)
                assert isinstance(details, dict)
                
                # Verify timestamp format
                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    @given(st.lists(audit_event_strategy(), min_size=5, max_size=15))
    @settings(max_examples=10, deadline=10000)
    def test_property_audit_export_integrity(self, audit_logger, integrity_verifier, events):
        """
        Property: Audit log export maintains integrity
        
        For any sequence of logged events, exporting and re-importing the audit
        log should maintain complete integrity.
        """
        note(f"Testing audit export integrity with {len(events)} events")
        
        # Log all events
        for event in events:
            audit_logger.log_event(event)
        
        # Get original integrity verification
        original_verification = integrity_verifier.verify_complete_integrity()
        assert original_verification.verified, "Original integrity check failed"
        
        # Export audit data
        exported_entries = []
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, sequence_number, event_type, severity,
                       component, action, details, session_id, user_id,
                       device_id, correlation_id, previous_hash, entry_hash, signature
                FROM audit_entries ORDER BY sequence_number
            """)
            
            for row in cursor.fetchall():
                exported_entries.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'sequence_number': row[2],
                    'event_type': row[3],
                    'severity': row[4],
                    'component': row[5],
                    'action': row[6],
                    'details': row[7],
                    'session_id': row[8],
                    'user_id': row[9],
                    'device_id': row[10],
                    'correlation_id': row[11],
                    'previous_hash': row[12],
                    'entry_hash': row[13],
                    'signature': row[14]
                })
        
        # Verify export completeness
        assert len(exported_entries) == len(events)
        
        # Verify each exported entry has all required fields
        for entry in exported_entries:
            assert all(key in entry for key in [
                'id', 'timestamp', 'sequence_number', 'event_type', 'component',
                'action', 'details', 'entry_hash', 'signature'
            ])
            
            # Verify cryptographic fields
            assert len(entry['entry_hash']) == 64  # SHA-256 hex
            assert len(entry['signature']) == 64   # HMAC-SHA256 hex
        
        # Verify sequence continuity in export
        sequences = [entry['sequence_number'] for entry in exported_entries]
        expected_sequences = list(range(1, len(events) + 1))
        assert sequences == expected_sequences, "Export sequence continuity broken"
    
    @given(st.lists(audit_event_strategy(), min_size=1, max_size=25))
    @settings(max_examples=10, deadline=10000)
    def test_property_audit_search_completeness(self, audit_logger, events):
        """
        Property: Audit search returns complete and accurate results
        
        For any sequence of logged events, searching by various criteria should
        return complete and accurate results without missing entries.
        """
        note(f"Testing audit search completeness with {len(events)} events")
        
        # Log all events and track components/actions
        components_used = set()
        actions_used = set()
        event_types_used = set()
        
        for event in events:
            audit_logger.log_event(event)
            components_used.add(event.component)
            actions_used.add(event.action)
            event_types_used.add(event.event_type.value)
        
        # Test search by component
        for component in list(components_used)[:3]:  # Test first 3 components
            with audit_logger._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM audit_entries WHERE component = ?
                """, (component,))
                
                found_count = cursor.fetchone()[0]
                expected_count = sum(1 for e in events if e.component == component)
                assert found_count == expected_count, f"Component search incomplete: {component}"
        
        # Test search by event type
        for event_type in list(event_types_used)[:3]:  # Test first 3 event types
            with audit_logger._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM audit_entries WHERE event_type = ?
                """, (event_type,))
                
                found_count = cursor.fetchone()[0]
                expected_count = sum(1 for e in events if e.event_type.value == event_type)
                assert found_count == expected_count, f"Event type search incomplete: {event_type}"
        
        # Test total count consistency
        with audit_logger._get_db_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM audit_entries")
            total_count = cursor.fetchone()[0]
            assert total_count == len(events), "Total count inconsistent"


class AuditCompletenessStateMachine(RuleBasedStateMachine):
    """Stateful property-based testing for audit completeness"""
    
    def __init__(self):
        super().__init__()
        self.temp_dir = tempfile.mkdtemp()
        self.audit_logger = AuditLogger(
            log_directory=self.temp_dir,
            enable_real_time_verification=False,
            testing_mode=True
        )
        self.integrity_verifier = IntegrityVerifier(
            db_path=str(self.audit_logger.db_path),
            signing_key=self.audit_logger.signing_key
        )
        self.logged_events = []
        self.expected_sequence = 1
    
    def teardown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    events = Bundle('events')
    
    @rule(target=events, event=audit_event_strategy())
    def log_event(self, event):
        """Log an audit event and track it"""
        entry_id = self.audit_logger.log_event(event)
        self.logged_events.append((entry_id, event, self.expected_sequence))
        self.expected_sequence += 1
        return (entry_id, event)
    
    @rule(logged_event=events)
    def verify_event_logged(self, logged_event):
        """Verify that a logged event exists in the database"""
        entry_id, event = logged_event
        
        with self.audit_logger._get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT id, event_type, component, action 
                FROM audit_entries WHERE id = ?
            """, (entry_id,))
            
            row = cursor.fetchone()
            assert row is not None, f"Event {entry_id} not found in database"
            assert row[1] == event.event_type.value
            assert row[2] == event.component
            assert row[3] == event.action
    
    @invariant()
    def integrity_maintained(self):
        """Invariant: Audit log integrity is always maintained"""
        if self.logged_events:
            verification_result = self.integrity_verifier.verify_complete_integrity()
            assert verification_result.verified, f"Integrity invariant violated: {verification_result.error_message}"
            assert verification_result.total_entries == len(self.logged_events)
    
    @invariant()
    def sequence_continuity_maintained(self):
        """Invariant: Sequence numbers are always continuous"""
        if self.logged_events:
            with self.audit_logger._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT sequence_number FROM audit_entries 
                    ORDER BY sequence_number
                """)
                
                sequences = [row[0] for row in cursor.fetchall()]
                expected_sequences = list(range(1, len(self.logged_events) + 1))
                assert sequences == expected_sequences, "Sequence continuity invariant violated"
    
    @invariant()
    def hash_chain_continuity_maintained(self):
        """Invariant: Hash chain is always continuous"""
        if len(self.logged_events) > 1:
            with self.audit_logger._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT previous_hash, entry_hash, sequence_number
                    FROM audit_entries ORDER BY sequence_number
                """)
                
                entries = cursor.fetchall()
                for i in range(1, len(entries)):
                    prev_entry_hash = entries[i-1][1]  # Previous entry's hash
                    current_previous_hash = entries[i][0]  # Current entry's previous_hash
                    assert prev_entry_hash == current_previous_hash, f"Hash chain break at sequence {entries[i][2]}"


# Run the stateful test
TestAuditCompletenessStateMachine = AuditCompletenessStateMachine.TestCase