"""
Property-Based Tests for Memory Privacy Protection

Tests Property 6: Privacy Protection
Validates Requirements 5.2, 5.3, 5.5

This test suite uses property-based testing to verify that:
1. All sensitive data is encrypted at rest and in transit
2. All processing occurs locally without external data sharing
3. Data deletion is complete and irreversible
4. No data exfiltration occurs through any channel
5. Encryption cannot be bypassed or weakened
6. Recovery attacks are prevented through secure deletion
"""

import pytest
import tempfile
import shutil
import os
import sqlite3
import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from src.memory.memory_service import MemoryService, MemoryServiceError
from src.memory.memory_types import (
    CoreMemory, EpisodicMemory, SemanticMemory, ProceduralMemory,
    ResourceMemory, KnowledgeVault, DataType, RetentionPolicy, AccessPolicy
)
from src.memory.encryption import MemoryEncryption, EncryptedData, MemoryEncryptionError
from src.memory.database import DatabaseManager, DatabaseConfig


"""
Property-Based Tests for Memory Privacy Protection

Tests Property 6: Privacy Protection
Validates Requirements 5.2, 5.3, 5.5

This test suite uses property-based testing to verify that:
1. All sensitive data is encrypted at rest and in transit
2. All processing occurs locally without external data sharing
3. Data deletion is complete and irreversible
4. No data exfiltration occurs through any channel
5. Encryption cannot be bypassed or weakened
6. Recovery attacks are prevented through secure deletion
"""

import pytest
import tempfile
import shutil
import sqlite3
import secrets
from pathlib import Path
from unittest.mock import patch
from hypothesis import given, strategies as st, settings, HealthCheck

from src.memory.memory_service import MemoryService


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing"""
    temp_dir = tempfile.mkdtemp(prefix="guru_memory_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def memory_service(temp_dir):
    """Create memory service with temporary storage"""
    service = MemoryService(
        data_dir=temp_dir,
        encryption_key=None,
        enable_vector_search=False,
        enable_retention=False
    )
    yield service
    service.shutdown()


@given(data=st.text(min_size=5, max_size=100))
@settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_data_encryption_at_rest(memory_service, data):
    """
    Property: All sensitive data must be encrypted when stored at rest
    
    **Validates: Requirements 5.2** - Screen capture data encrypted at rest and stored locally
    
    For any sensitive data, when stored with encryption enabled, it should be
    encrypted using strong encryption and never stored in plaintext.
    """
    # Store encrypted data
    key = f"test_encryption_{secrets.token_hex(8)}"
    memory = memory_service.store_core_preference(
        key=key,
        value=data,
        encrypted=True
    )
    
    # Verify data is encrypted in database
    db_path = Path(memory_service.data_dir) / "memory.db"
    conn = sqlite3.connect(str(db_path))
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM core_memory WHERE key = ?", (key,))
        result = cursor.fetchone()
        
        assert result is not None
        stored_value = result[0]
        
        # Original data should not appear in plaintext
        assert data not in stored_value, f"Plaintext data found: {stored_value[:50]}"
        
        # Verify we can still retrieve the original data
        retrieved = memory_service.get_core_preference(key)
        assert retrieved == data
        
    finally:
        conn.close()


@given(data=st.text(min_size=1, max_size=100))
@settings(max_examples=15, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_local_processing_only(memory_service, data):
    """
    Property: All data processing must occur locally without external services
    
    **Validates: Requirements 5.3** - OCR and NER processing locally without external services
    
    For any data processing operation, no network connections should be made
    and all processing should occur within the local memory service.
    """
    # Mock network operations to detect any external calls
    with patch('urllib.request.urlopen') as mock_urlopen, \
         patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post, \
         patch('socket.socket') as mock_socket:
        
        # Store and process data
        key = f"test_local_{secrets.token_hex(8)}"
        memory = memory_service.store_core_preference(
            key=key,
            value=data,
            encrypted=True
        )
        
        # Retrieve data
        retrieved = memory_service.get_core_preference(key)
        assert retrieved == data
        
        # Verify no external network calls were made
        mock_urlopen.assert_not_called()
        mock_get.assert_not_called()
        mock_post.assert_not_called()
        mock_socket.assert_not_called()


@given(data=st.text(min_size=1, max_size=100))
@settings(max_examples=15, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_complete_data_deletion(memory_service, data):
    """
    Property: Data deletion must be complete and irreversible
    
    **Validates: Requirements 5.5** - Full deletion capability for stored screen memories
    
    For any stored data, when deletion is requested, the data should be
    completely removed from all storage locations and be unrecoverable.
    """
    # Store data
    key = f"test_deletion_{secrets.token_hex(8)}"
    memory = memory_service.store_core_preference(
        key=key,
        value=data,
        encrypted=True
    )
    
    # Verify data exists
    retrieved_before = memory_service.get_core_preference(key)
    assert retrieved_before == data
    
    # Delete data
    result = memory_service.delete_core_preference(key)
    assert result is True
    
    # Verify data is gone
    retrieved_after = memory_service.get_core_preference(key)
    assert retrieved_after is None
    
    # Verify data is removed from database
    db_path = Path(memory_service.data_dir) / "memory.db"
    conn = sqlite3.connect(str(db_path))
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM core_memory WHERE key = ?", (key,))
        result = cursor.fetchone()
        assert result is None, "Deleted data still found in database"
    finally:
        conn.close()


def test_simple_privacy_verification(memory_service):
    """Simple test to verify basic privacy functionality works"""
    # Store encrypted data
    memory = memory_service.store_core_preference(
        key="test_privacy_simple",
        value="sensitive_data_12345",
        encrypted=True
    )
    
    # Verify it was stored and can be retrieved
    assert memory is not None
    retrieved = memory_service.get_core_preference("test_privacy_simple")
    assert retrieved == "sensitive_data_12345"
    
    # Property-Based Test Strategies
    
    # Strategy for generating sensitive data
    sensitive_data_strategy = st.one_of(
        st.text(min_size=1, max_size=1000),  # Text data
        st.binary(min_size=1, max_size=1000),  # Binary data
        st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(st.text(), st.integers(), st.floats(allow_nan=False)),
            min_size=1, max_size=10
        ),  # JSON-like data
        st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=20)  # List data
    )
    
    # Strategy for memory contexts
    memory_context_strategy = st.sampled_from([
        "episodic_memory", "semantic_memory", "procedural_memory",
        "resource_memory", "knowledge_vault", "screen_observation",
        "ocr_data", "ner_data", "user_preferences"
    ])
    
    # Strategy for file paths and names
    file_path_strategy = st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='._-/\\'),
        min_size=1, max_size=200
    ).filter(lambda x: len(x.strip()) > 0)
    
    # Property 1: Data Encryption at Rest
    @given(
        data=sensitive_data_strategy,
        context=memory_context_strategy
    )
    @settings(max_examples=100, deadline=5000)
    def test_data_encryption_at_rest(self, memory_service, data, context):
        """
        Property: All sensitive data must be encrypted when stored at rest
        
        **Validates: Requirements 5.2** - Screen capture data encrypted at rest and stored locally
        
        For any sensitive data and storage context, when data is stored in the memory service,
        it should be encrypted using strong encryption and never stored in plaintext.
        """
        # Convert data to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, (dict, list)):
            import json
            data_bytes = json.dumps(data).encode('utf-8')
        else:
            data_bytes = data
        
        # Store data with encryption enabled
        if context == "episodic_memory":
            memory = memory_service.store_episode(
                summary="Test episode",
                details=data.decode('utf-8') if isinstance(data, bytes) else str(data),
                encrypted=True
            )
            stored_id = memory.event_id
        elif context == "semantic_memory":
            memory = memory_service.store_concept(
                concept_name="Test concept",
                description=data.decode('utf-8') if isinstance(data, bytes) else str(data)
            )
            stored_id = memory.concept_id
        elif context == "knowledge_vault":
            memory = memory_service.store_vault_item(
                name="Test vault item",
                vault_type="sensitive_data",
                encrypted_data=data_bytes
            )
            stored_id = memory.vault_id
        else:
            # Use core memory for other contexts
            memory = memory_service.store_core_preference(
                key=f"test_{context}",
                value=data.decode('utf-8') if isinstance(data, bytes) else data,
                encrypted=True
            )
            stored_id = memory.key
        
        # Verify data is encrypted in database
        db_path = Path(memory_service.data_dir) / "memory.db"
        conn = sqlite3.connect(str(db_path))
        
        try:
            # Check that raw data is not present in database
            cursor = conn.cursor()
            
            # Search all text columns for the original data
            tables = ['core_memory', 'episodic_memory', 'semantic_memory', 
                     'procedural_memory', 'resource_memory', 'knowledge_vault']
            
            original_text = data.decode('utf-8') if isinstance(data, bytes) else str(data)
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        for field in row:
                            if field and isinstance(field, str):
                                # Original data should not appear in plaintext
                                assert original_text not in field, f"Plaintext data found in {table}: {field[:100]}"
                                
                                # Should not contain obvious unencrypted patterns
                                if len(original_text) > 10:
                                    assert original_text[:10] not in field, f"Data prefix found unencrypted in {table}"
                except sqlite3.OperationalError:
                    # Table might not exist yet, skip
                    continue
                            
        finally:
            conn.close()
    
    # Property 2: Local Processing Only
    @given(
        data=sensitive_data_strategy,
        context=memory_context_strategy
    )
    @settings(max_examples=50, deadline=5000)
    def test_local_processing_only(self, memory_service, data, context):
        """
        Property: All data processing must occur locally without external services
        
        **Validates: Requirements 5.3** - OCR and NER processing locally without external services
        
        For any data processing operation, no network connections should be made
        and all processing should occur within the local memory service.
        """
        # Mock network operations to detect any external calls
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('requests.get') as mock_requests_get, \
             patch('requests.post') as mock_requests_post, \
             patch('socket.socket') as mock_socket:
            
            # Store and process data
            if context == "screen_observation":
                # Simulate screen observation data processing
                memory = memory_service.store_resource(
                    name="screen_capture.png",
                    resource_type="screenshot",
                    content_hash=hashlib.sha256(str(data).encode()).hexdigest(),
                    metadata={"ocr_processed": True, "ner_processed": True}
                )
            elif context == "ocr_data":
                # Simulate OCR data processing
                memory = memory_service.store_concept(
                    concept_name="OCR Result",
                    description=str(data),
                    category="ocr_extraction"
                )
            elif context == "ner_data":
                # Simulate NER data processing
                memory = memory_service.store_concept(
                    concept_name="NER Result", 
                    description=str(data),
                    category="entity_extraction"
                )
            else:
                # Regular memory storage
                memory = memory_service.store_core_preference(
                    key=f"local_test_{context}",
                    value=data
                )
            
            # Verify no external network calls were made
            mock_urlopen.assert_not_called()
            mock_requests_get.assert_not_called()
            mock_requests_post.assert_not_called()
            mock_socket.assert_not_called()
            
            # Verify data was processed and stored locally
            assert memory is not None
            
            # Verify we can retrieve the data (proving local storage works)
            if hasattr(memory, 'event_id'):
                retrieved = memory_service.get_episode(memory.event_id)
            elif hasattr(memory, 'concept_id'):
                retrieved = memory_service.get_concept(memory.concept_id)
            elif hasattr(memory, 'resource_id'):
                retrieved = memory_service.get_resource(memory.resource_id)
            elif hasattr(memory, 'vault_id'):
                retrieved = memory_service.get_vault_item(memory.vault_id)
            else:
                retrieved = memory_service.get_core_preference(memory.key)
            
            assert retrieved is not None
    
    # Property 3: Complete Data Deletion
    @given(
        data=sensitive_data_strategy,
        context=memory_context_strategy
    )
    @settings(max_examples=50, deadline=5000)
    def test_complete_data_deletion(self, memory_service, data, context):
        """
        Property: Data deletion must be complete and irreversible
        
        **Validates: Requirements 5.5** - Full deletion capability for stored screen memories
        
        For any stored data, when deletion is requested, the data should be
        completely removed from all storage locations and be unrecoverable.
        """
        # Store data first
        if context == "episodic_memory":
            memory = memory_service.store_episode(
                summary="Test episode for deletion",
                details=str(data),
                encrypted=True
            )
            memory_id = memory.event_id
            delete_func = lambda: memory_service.episodic_manager.delete(memory_id)
            retrieve_func = lambda: memory_service.get_episode(memory_id)
        elif context == "semantic_memory":
            memory = memory_service.store_concept(
                concept_name="Test concept for deletion",
                description=str(data)
            )
            memory_id = memory.concept_id
            delete_func = lambda: memory_service.semantic_manager.delete(memory_id)
            retrieve_func = lambda: memory_service.get_concept(memory_id)
        elif context == "knowledge_vault":
            data_bytes = str(data).encode('utf-8')
            memory = memory_service.store_vault_item(
                name="Test vault for deletion",
                vault_type="test_data",
                encrypted_data=data_bytes
            )
            memory_id = memory.vault_id
            delete_func = lambda: memory_service.vault_manager.delete(memory_id)
            retrieve_func = lambda: memory_service.get_vault_item(memory_id)
        else:
            memory = memory_service.store_core_preference(
                key=f"deletion_test_{context}",
                value=data,
                encrypted=True
            )
            memory_id = memory.key
            delete_func = lambda: memory_service.delete_core_preference(memory_id)
            retrieve_func = lambda: memory_service.get_core_preference(memory_id)
        
        # Verify data exists before deletion
        retrieved_before = retrieve_func()
        assert retrieved_before is not None
        
        # Get database state before deletion
        db_path = Path(memory_service.data_dir) / "memory.db"
        conn = sqlite3.connect(str(db_path))
        
        # Count total rows before deletion
        cursor = conn.cursor()
        tables = ['core_memory', 'episodic_memory', 'semantic_memory', 
                 'procedural_memory', 'resource_memory', 'knowledge_vault']
        
        row_counts_before = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_counts_before[table] = cursor.fetchone()[0]
        
        conn.close()
        
        # Perform deletion
        deletion_result = delete_func()
        assert deletion_result is True or deletion_result is None  # Some delete methods return None
        
        # Verify data is no longer retrievable
        retrieved_after = retrieve_func()
        assert retrieved_after is None
        
        # Verify data is removed from database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check that at least one row was deleted
        total_deleted = 0
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count_after = cursor.fetchone()[0]
            deleted_from_table = row_counts_before[table] - row_count_after
            total_deleted += deleted_from_table
        
        assert total_deleted > 0, "No rows were deleted from database"
        
        # Verify no traces of the original data remain in database
        original_text = str(data)
        if len(original_text) > 5:  # Only check for non-trivial data
            for table in tables:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                
                for row in rows:
                    for field in row:
                        if field and isinstance(field, str):
                            # Original data should not appear anywhere
                            assert original_text not in field, f"Deleted data still found in {table}: {field[:100]}"
        
        conn.close()
    
    # Property 4: Encryption Bypass Prevention
    @given(
        data=sensitive_data_strategy,
        context=memory_context_strategy
    )
    @settings(max_examples=30, deadline=5000)
    def test_encryption_bypass_prevention(self, memory_service, data, context):
        """
        Property: Encryption cannot be bypassed or weakened
        
        **Validates: Requirements 5.2** - Encryption integrity and bypass prevention
        
        For any attempt to store sensitive data, encryption should be enforced
        and there should be no way to bypass or weaken the encryption.
        """
        # Attempt to store sensitive data
        if context == "knowledge_vault":
            data_bytes = str(data).encode('utf-8')
            memory = memory_service.store_vault_item(
                name="Bypass test",
                vault_type="sensitive",
                encrypted_data=data_bytes
            )
        else:
            memory = memory_service.store_core_preference(
                key=f"bypass_test_{context}",
                value=data,
                encrypted=True  # Explicitly request encryption
            )
        
        # Try to access raw database and verify encryption is applied
        db_path = Path(memory_service.data_dir) / "memory.db"
        conn = sqlite3.connect(str(db_path))
        
        try:
            cursor = conn.cursor()
            
            # Get the stored data from database
            if context == "knowledge_vault":
                cursor.execute("SELECT encrypted_data FROM knowledge_vault WHERE vault_id = ?", (memory.vault_id,))
            else:
                cursor.execute("SELECT value FROM core_memory WHERE key = ?", (memory.key,))
            
            result = cursor.fetchone()
            assert result is not None
            
            stored_value = result[0]
            
            # Verify the stored value is not the original plaintext
            original_text = str(data)
            if isinstance(stored_value, str):
                assert original_text != stored_value, "Data stored in plaintext despite encryption request"
                
                # Should not contain recognizable patterns from original data
                if len(original_text) > 10:
                    assert original_text[:5] not in stored_value, "Plaintext patterns found in stored data"
            
            # Verify stored data looks encrypted (contains non-printable characters or base64-like patterns)
            if isinstance(stored_value, bytes):
                # Binary data should not match original
                original_bytes = original_text.encode('utf-8')
                assert stored_value != original_bytes, "Binary data not encrypted"
            elif isinstance(stored_value, str) and len(stored_value) > 20:
                # Encrypted text should have high entropy
                import string
                printable_chars = set(string.printable)
                non_printable_count = sum(1 for c in stored_value if c not in printable_chars)
                
                # Either high entropy or base64-like encoding
                is_base64_like = all(c in string.ascii_letters + string.digits + '+/=' for c in stored_value)
                has_high_entropy = non_printable_count > len(stored_value) * 0.1
                
                assert is_base64_like or has_high_entropy, "Stored data does not appear encrypted"
        
        finally:
            conn.close()
    
    # Property 5: Recovery Attack Prevention
    @given(
        data=sensitive_data_strategy,
        context=memory_context_strategy
    )
    @settings(max_examples=30, deadline=5000)
    def test_recovery_attack_prevention(self, memory_service, data, context):
        """
        Property: Recovery attacks should be prevented through secure deletion
        
        **Validates: Requirements 5.5** - Secure deletion prevents recovery attacks
        
        For any deleted sensitive data, it should not be recoverable through
        database analysis, file system recovery, or memory inspection.
        """
        # Store sensitive data
        if context == "episodic_memory":
            memory = memory_service.store_episode(
                summary="Recovery test episode",
                details=str(data),
                encrypted=True
            )
            memory_id = memory.event_id
            delete_func = lambda: memory_service.episodic_manager.delete(memory_id)
        else:
            memory = memory_service.store_core_preference(
                key=f"recovery_test_{context}",
                value=data,
                encrypted=True
            )
            memory_id = memory.key
            delete_func = lambda: memory_service.delete_core_preference(memory_id)
        
        # Get database file path
        db_path = Path(memory_service.data_dir) / "memory.db"
        
        # Read entire database file before deletion
        with open(db_path, 'rb') as f:
            db_content_before = f.read()
        
        # Delete the data
        delete_func()
        
        # Force database to flush changes
        memory_service.db_manager.execute_update("VACUUM", ())
        
        # Read database file after deletion
        with open(db_path, 'rb') as f:
            db_content_after = f.read()
        
        # Verify original data is not recoverable from database file
        original_text = str(data)
        original_bytes = original_text.encode('utf-8')
        
        # Check that plaintext data is not present in database file
        assert original_bytes not in db_content_after, "Original data recoverable from database file"
        
        # For longer data, check that significant portions are not recoverable
        if len(original_text) > 20:
            # Check chunks of the original data
            chunk_size = min(10, len(original_text) // 3)
            for i in range(0, len(original_text) - chunk_size, chunk_size):
                chunk = original_text[i:i + chunk_size].encode('utf-8')
                assert chunk not in db_content_after, f"Data chunk recoverable: {chunk}"
        
        # Verify database integrity after secure deletion
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            assert integrity_result == "ok", f"Database integrity compromised: {integrity_result}"
        finally:
            conn.close()
    
    # Property 6: Data Exfiltration Prevention
    @given(
        data=sensitive_data_strategy,
        context=memory_context_strategy
    )
    @settings(max_examples=30, deadline=5000)
    def test_data_exfiltration_prevention(self, memory_service, data, context):
        """
        Property: No data exfiltration should occur through any channel
        
        **Validates: Requirements 5.2, 5.3** - Local storage only, no external data sharing
        
        For any memory operation, no data should be transmitted externally
        through network, files, logs, or any other channel.
        """
        # Mock all potential exfiltration channels
        with patch('urllib.request.urlopen') as mock_urlopen, \
             patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post, \
             patch('smtplib.SMTP') as mock_smtp, \
             patch('socket.socket') as mock_socket, \
             patch('subprocess.run') as mock_subprocess, \
             patch('os.system') as mock_system, \
             patch('builtins.open', wraps=open) as mock_open:
            
            # Store data
            memory = memory_service.store_core_preference(
                key=f"exfiltration_test_{context}",
                value=data,
                encrypted=True
            )
            
            # Retrieve data
            retrieved = memory_service.get_core_preference(memory.key)
            
            # Search data
            if isinstance(data, str) and len(data) > 5:
                search_results = memory_service.search_all_memories(data[:5])
            
            # Delete data
            memory_service.delete_core_preference(memory.key)
            
            # Verify no external communications occurred
            mock_urlopen.assert_not_called()
            mock_get.assert_not_called()
            mock_post.assert_not_called()
            mock_smtp.assert_not_called()
            mock_socket.assert_not_called()
            mock_subprocess.assert_not_called()
            mock_system.assert_not_called()
            
            # Check that no suspicious file operations occurred
            # (Allow normal database operations but not external file writes)
            external_writes = []
            for call in mock_open.call_args_list:
                if len(call[0]) > 0:
                    file_path = str(call[0][0])
                    # Allow database and temp files, but not external paths
                    if not any(allowed in file_path for allowed in [
                        'memory.db', 'temp', 'tmp', str(memory_service.data_dir)
                    ]):
                        if len(call) > 1 and 'w' in str(call[1]):  # Write mode
                            external_writes.append(file_path)
            
            assert len(external_writes) == 0, f"Suspicious external file writes: {external_writes}"


class MemoryPrivacyStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for memory privacy protection.
    
    This tests complex scenarios involving multiple operations and state transitions
    to ensure privacy properties hold under all conditions.
    """
    
    def __init__(self):
        super().__init__()
        self.temp_dir = tempfile.mkdtemp(prefix="guru_privacy_state_test_")
        self.memory_service = MemoryService(
            data_dir=self.temp_dir,
            encryption_key=None,
            enable_vector_search=False,
            enable_retention=False
        )
        self.stored_items = {}  # Track stored items for verification
        self.deleted_items = set()  # Track deleted items
    
    def teardown(self):
        """Clean up resources"""
        if hasattr(self, 'memory_service'):
            self.memory_service.shutdown()
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @rule(
        key=st.text(min_size=1, max_size=50),
        value=st.text(min_size=1, max_size=200),
        encrypted=st.booleans()
    )
    def store_preference(self, key, value, encrypted):
        """Store a preference and track it"""
        assume(key not in self.deleted_items)
        
        memory = self.memory_service.store_core_preference(
            key=key,
            value=value,
            encrypted=encrypted
        )
        
        self.stored_items[key] = {
            'value': value,
            'encrypted': encrypted,
            'memory': memory
        }
    
    @rule(key=st.sampled_from(lambda self: list(self.stored_items.keys()) if self.stored_items else ['dummy']))
    def retrieve_preference(self, key):
        """Retrieve a preference and verify privacy properties"""
        if key == 'dummy' or key in self.deleted_items:
            return
        
        retrieved = self.memory_service.get_core_preference(key)
        
        if key in self.stored_items:
            # Should be able to retrieve stored items
            assert retrieved is not None
            assert retrieved == self.stored_items[key]['value']
        else:
            # Should not retrieve non-existent items
            assert retrieved is None
    
    @rule(key=st.sampled_from(lambda self: list(self.stored_items.keys()) if self.stored_items else ['dummy']))
    def delete_preference(self, key):
        """Delete a preference and verify secure deletion"""
        if key == 'dummy' or key in self.deleted_items:
            return
        
        if key in self.stored_items:
            original_value = self.stored_items[key]['value']
            
            # Delete the item
            result = self.memory_service.delete_core_preference(key)
            assert result is True
            
            # Mark as deleted
            del self.stored_items[key]
            self.deleted_items.add(key)
            
            # Verify it's no longer retrievable
            retrieved = self.memory_service.get_core_preference(key)
            assert retrieved is None
    
    @invariant()
    def verify_no_plaintext_in_database(self):
        """Invariant: No plaintext sensitive data should be in database"""
        db_path = Path(self.memory_service.data_dir) / "memory.db"
        
        if not db_path.exists():
            return
        
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM core_memory WHERE encrypted = 1")
            encrypted_values = cursor.fetchall()
            
            # Check that encrypted values don't contain original plaintext
            for item_key, item_data in self.stored_items.items():
                if item_data['encrypted']:
                    original_value = item_data['value']
                    
                    for (stored_value,) in encrypted_values:
                        if stored_value and isinstance(stored_value, str):
                            assert original_value not in stored_value, \
                                f"Plaintext value found in encrypted storage: {original_value[:20]}"
        
        finally:
            conn.close()
    
    @invariant()
    def verify_deleted_items_not_recoverable(self):
        """Invariant: Deleted items should not be recoverable"""
        for deleted_key in self.deleted_items:
            retrieved = self.memory_service.get_core_preference(deleted_key)
            assert retrieved is None, f"Deleted item {deleted_key} is still recoverable"


# Test runner for stateful testing
TestMemoryPrivacyStateMachine = MemoryPrivacyStateMachine.TestCase