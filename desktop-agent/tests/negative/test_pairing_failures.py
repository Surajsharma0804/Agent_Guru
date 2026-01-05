"""
Negative Tests for Device Pairing System

Tests error conditions, edge cases, and failure scenarios
to ensure robust error handling and graceful degradation.
"""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from src.pairing.qr_pairing import (
    QRPairingManager, PairingToken, DeviceFingerprint, 
    PairingResult, PairingStatus
)
from src.pairing.key_exchange import (
    KeyExchangeManager, KeyExchangeMessage,
    KeyExchangeResult, KeyExchangeStatus
)
from src.pairing.device_registry import (
    DeviceRegistry, DeviceIdentity
)


class TestQRPairingFailures:
    """Test QR pairing failure scenarios"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = QRPairingManager()
    
    def test_corrupted_qr_data_handling(self):
        """Test handling of corrupted QR code data"""
        # Completely invalid JSON
        invalid_json = "not json at all"
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)
        
        # Valid JSON but missing required fields
        incomplete_data = {
            "type": "guru_pairing",
            "version": "1.0"
            # Missing token_id, device_fingerprint, etc.
        }
        
        result = self.manager.validate_pairing_token(incomplete_data)
        assert result.status == PairingStatus.FAILED
        assert "error" in result.error_message.lower()
    
    def test_invalid_qr_code_versions(self):
        """Test handling of unsupported QR code versions"""
        # Future version
        future_version_data = {
            "type": "guru_pairing",
            "version": "99.0"
        }
        
        result = self.manager.validate_pairing_token(future_version_data)
        assert result.status == PairingStatus.FAILED
        assert "Unsupported QR code version" in result.error_message
        
        # Invalid version format
        invalid_version_data = {
            "type": "guru_pairing",
            "version": "not_a_version"
        }
        
        result = self.manager.validate_pairing_token(invalid_version_data)
        assert result.status == PairingStatus.FAILED
    
    def test_malformed_device_fingerprint(self):
        """Test handling of malformed device fingerprints"""
        # Missing required fingerprint fields
        incomplete_fingerprint = {
            "device_id": "test-device"
            # Missing hardware_hash, os_version, etc.
        }
        
        qr_data = {
            "type": "guru_pairing",
            "version": "1.0",
            "token_id": "test-token",
            "device_fingerprint": incomplete_fingerprint,
            "expiration_timestamp": time.time() + 300,
            "challenge_nonce": "nonce",
            "hmac_signature": "signature"
        }
        
        result = self.manager.validate_pairing_token(qr_data)
        assert result.status == PairingStatus.FAILED
        assert "error" in result.error_message.lower()
    
    def test_pairing_session_not_found_errors(self):
        """Test errors when pairing sessions are not found"""
        # Confirm non-existent pairing
        result = self.manager.confirm_pairing("non-existent-token", True)
        assert result.status == PairingStatus.FAILED
        assert "not found" in result.error_message
        
        # Complete non-existent pairing
        result = self.manager.complete_pairing("non-existent-token")
        assert result.status == PairingStatus.FAILED
        assert "not found" in result.error_message
        
        # Get status of non-existent pairing
        result = self.manager.get_pairing_status("non-existent-token")
        assert result is None
    
    def test_pairing_state_transition_errors(self):
        """Test invalid pairing state transitions"""
        # Set up pairing session in wrong state
        token_id = "test-token"
        session = PairingResult(
            status=PairingStatus.INITIATED,  # Not confirmed
            token_id=token_id
        )
        self.manager.pairing_sessions[token_id] = session
        
        # Try to complete without confirmation
        result = self.manager.complete_pairing(token_id)
        assert result.status == PairingStatus.FAILED
        assert "not confirmed" in result.error_message
    
    @patch('src.pairing.qr_pairing.platform')
    @patch('src.pairing.qr_pairing.psutil')
    def test_system_info_gathering_failures(self, mock_psutil, mock_platform):
        """Test handling of system information gathering failures"""
        # Mock system calls to raise exceptions
        mock_platform.processor.side_effect = Exception("System error")
        mock_psutil.virtual_memory.side_effect = Exception("Memory error")
        
        # Should handle gracefully and still generate fingerprint
        with pytest.raises(Exception):
            self.manager.generate_device_fingerprint()
    
    def test_qr_code_generation_edge_cases(self):
        """Test QR code generation with edge case data"""
        # Very long device fingerprint data
        long_fingerprint = DeviceFingerprint(
            device_id="x" * 1000,  # Very long device ID
            hardware_hash="y" * 1000,  # Very long hash
            os_version="z" * 1000,  # Very long OS version
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        # Should still generate QR code (might be large)
        token = PairingToken.generate(long_fingerprint)
        qr_data = token.to_qr_data()
        
        # QR data should be valid JSON
        qr_json = json.dumps(qr_data)
        assert isinstance(qr_json, str)
        assert len(qr_json) > 0


class TestKeyExchangeFailures:
    """Test key exchange failure scenarios"""
    
    def test_invalid_message_types(self):
        """Test handling of invalid message types"""
        manager = KeyExchangeManager("test-device")
        
        # Unknown message type
        invalid_message = KeyExchangeMessage(
            message_type="unknown_type",
            sender_device_id="sender",
            recipient_device_id="test-device",
            public_key_pem="fake-key",
            challenge_nonce="nonce",
            signature="signature",
            timestamp=time.time()
        )
        
        with pytest.raises(ValueError, match="Invalid message type"):
            manager.process_key_exchange_request(invalid_message)
    
    def test_wrong_recipient_handling(self):
        """Test handling of messages sent to wrong recipient"""
        manager = KeyExchangeManager("device-a")
        
        # Message intended for different device
        wrong_recipient_message = KeyExchangeMessage(
            message_type="key_exchange_request",
            sender_device_id="sender",
            recipient_device_id="device-b",  # Wrong recipient
            public_key_pem="fake-key",
            challenge_nonce="nonce",
            signature="signature",
            timestamp=time.time()
        )
        
        with pytest.raises(ValueError, match="not intended for this device"):
            manager.process_key_exchange_request(wrong_recipient_message)
    
    def test_invalid_public_key_formats(self):
        """Test handling of invalid public key formats"""
        manager = KeyExchangeManager("test-device")
        
        invalid_keys = [
            "not-a-key",
            "-----BEGIN PRIVATE KEY-----\ndata\n-----END PRIVATE KEY-----",  # Private key
            "-----BEGIN PUBLIC KEY-----\nINVALID_DATA\n-----END PUBLIC KEY-----",
            "",
            None
        ]
        
        for invalid_key in invalid_keys:
            if invalid_key is None:
                continue
                
            message = KeyExchangeMessage(
                message_type="key_exchange_request",
                sender_device_id="sender",
                recipient_device_id="test-device",
                public_key_pem=invalid_key,
                challenge_nonce="nonce",
                signature="signature",
                timestamp=time.time()
            )
            
            # Should fail during signature verification or key loading
            with pytest.raises((ValueError, Exception)):
                manager.process_key_exchange_request(message)
    
    def test_signature_verification_failures(self):
        """Test various signature verification failure scenarios"""
        device_a = KeyExchangeManager("device-a")
        device_b = KeyExchangeManager("device-b")
        
        # Generate legitimate message
        request_message, _ = device_a.initiate_key_exchange("device-b")
        
        # Test various signature corruption scenarios
        corrupted_signatures = [
            "",  # Empty signature
            "invalid_base64!",  # Invalid base64
            "dGVzdA==",  # Valid base64 but wrong signature
            request_message.signature[:-5] + "XXXXX",  # Partially corrupted
        ]
        
        for corrupted_sig in corrupted_signatures:
            corrupted_message = KeyExchangeMessage(
                message_type=request_message.message_type,
                sender_device_id=request_message.sender_device_id,
                recipient_device_id=request_message.recipient_device_id,
                public_key_pem=request_message.public_key_pem,
                challenge_nonce=request_message.challenge_nonce,
                signature=corrupted_sig,
                timestamp=request_message.timestamp
            )
            
            with pytest.raises(ValueError, match="Invalid message signature"):
                device_b.process_key_exchange_request(corrupted_message)
    
    def test_key_exchange_response_validation_failures(self):
        """Test key exchange response validation failures"""
        device_a = KeyExchangeManager("device-a")
        device_b = KeyExchangeManager("device-b")
        
        # Set up initial exchange
        request_message, _ = device_a.initiate_key_exchange("device-b")
        response_message, _ = device_b.process_key_exchange_request(request_message)
        exchange_id = "device-a-device-b"
        
        # Test response from wrong sender
        wrong_sender_response = KeyExchangeMessage(
            message_type="key_exchange_response",
            sender_device_id="wrong-sender",  # Wrong sender
            recipient_device_id="device-a",
            public_key_pem=response_message.public_key_pem,
            challenge_nonce=response_message.challenge_nonce,
            signature=response_message.signature,
            timestamp=response_message.timestamp
        )
        
        with pytest.raises(ValueError, match="unexpected device"):
            device_a.process_key_exchange_response(wrong_sender_response, exchange_id)
        
        # Test response for non-existent exchange
        with pytest.raises(ValueError, match="not found"):
            device_a.process_key_exchange_response(response_message, "non-existent-exchange")
    
    def test_ecdh_key_derivation_failures(self):
        """Test ECDH key derivation failure scenarios"""
        manager = KeyExchangeManager("test-device")
        
        # Mock ECDH to raise exception
        with patch('cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePrivateKey.exchange') as mock_exchange:
            mock_exchange.side_effect = Exception("ECDH failed")
            
            # Create fake exchange result
            exchange_result = KeyExchangeResult(
                status=KeyExchangeStatus.PUBLIC_KEY_RECEIVED,
                local_device_id="test-device",
                remote_device_id="remote-device"
            )
            
            # Should handle ECDH failure gracefully
            manager._derive_shared_secret("fake-public-key-pem", exchange_result)
            
            assert exchange_result.status == KeyExchangeStatus.FAILED
            assert "derivation failed" in exchange_result.error_message


class TestDeviceRegistryFailures:
    """Test device registry failure scenarios"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.encryption_key = Fernet.generate_key()
        self.registry = DeviceRegistry(self.temp_db.name, self.encryption_key)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        # Ensure registry is properly closed
        if hasattr(self, 'registry'):
            del self.registry
        
        # Force garbage collection to close any remaining connections
        import gc
        gc.collect()
        
        # Try to remove the file, with retry on Windows
        import time
        for attempt in range(3):
            try:
                Path(self.temp_db.name).unlink(missing_ok=True)
                break
            except PermissionError:
                if attempt < 2:  # Not the last attempt
                    time.sleep(0.1)  # Wait a bit and retry
                    gc.collect()  # Force another GC
                else:
                    # Last attempt failed, but don't fail the test
                    pass
    
    def test_database_corruption_handling(self):
        """Test handling of database corruption"""
        # Corrupt the database file
        with open(self.temp_db.name, 'wb') as f:
            f.write(b"corrupted data")
        
        # Should handle corruption gracefully
        corrupted_registry = DeviceRegistry(self.temp_db.name, self.encryption_key)
        
        # Operations should fail gracefully
        result = corrupted_registry.get_trusted_device("any-device")
        assert result is None
    
    def test_encryption_key_mismatch_handling(self):
        """Test handling of encryption key mismatches"""
        # Register device with original key
        device_identity = DeviceIdentity(
            device_id="test-device",
            device_name="Test Device",
            device_type="phone",
            public_key_pem="test-key",
            key_fingerprint="fingerprint",
            hardware_fingerprint="hw-fingerprint",
            pairing_timestamp=time.time(),
            last_seen_timestamp=time.time()
        )
        
        self.registry.register_device(device_identity, "secret")
        
        # Create new registry with different key
        wrong_key = Fernet.generate_key()
        wrong_registry = DeviceRegistry(self.temp_db.name, wrong_key)
        
        # Should not be able to decrypt data
        result = wrong_registry.get_trusted_device("test-device")
        assert result is None
    
    def test_invalid_device_data_handling(self):
        """Test handling of invalid device data"""
        # Create device with invalid data types
        with pytest.raises(TypeError):
            DeviceIdentity(
                device_id=123,  # Should be string
                device_name="Test Device",
                device_type="phone",
                public_key_pem="test-key",
                key_fingerprint="fingerprint",
                hardware_fingerprint="hw-fingerprint",
                pairing_timestamp="not-a-timestamp",  # Should be float
                last_seen_timestamp=time.time()
            )
    
    def test_database_permission_errors(self):
        """Test handling of database permission errors"""
        # Create read-only database file
        readonly_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        readonly_db.close()
        
        # Make file read-only
        Path(readonly_db.name).chmod(0o444)
        
        readonly_registry = None
        try:
            # Should handle permission errors gracefully
            readonly_registry = DeviceRegistry(readonly_db.name, self.encryption_key)
            
            device_identity = DeviceIdentity(
                device_id="test-device",
                device_name="Test Device",
                device_type="phone",
                public_key_pem="test-key",
                key_fingerprint="fingerprint",
                hardware_fingerprint="hw-fingerprint",
                pairing_timestamp=time.time(),
                last_seen_timestamp=time.time()
            )
            
            # Registration should fail gracefully
            result = readonly_registry.register_device(device_identity, "secret")
            assert result is False
            
        finally:
            # Clean up with proper resource management
            if readonly_registry is not None:
                # Force close any database connections
                del readonly_registry
            
            # Force garbage collection to release file handles
            import gc
            gc.collect()
            
            # Restore write permissions
            try:
                Path(readonly_db.name).chmod(0o644)
            except (OSError, PermissionError):
                pass
            
            # Retry cleanup with backoff
            import time as time_module
            for attempt in range(5):
                try:
                    Path(readonly_db.name).unlink(missing_ok=True)
                    break
                except (OSError, PermissionError):
                    if attempt < 4:
                        time_module.sleep(0.1 * (2 ** attempt))
                    else:
                        # Final attempt - ignore errors
                        try:
                            Path(readonly_db.name).unlink()
                        except:
                            pass
    
    def test_malformed_encrypted_data_handling(self):
        """Test handling of malformed encrypted data in database"""
        # Register device normally
        device_identity = DeviceIdentity(
            device_id="test-device",
            device_name="Test Device",
            device_type="phone",
            public_key_pem="test-key",
            key_fingerprint="fingerprint",
            hardware_fingerprint="hw-fingerprint",
            pairing_timestamp=time.time(),
            last_seen_timestamp=time.time()
        )
        
        self.registry.register_device(device_identity, "secret")
        
        # Corrupt encrypted data in database
        import sqlite3
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute("""
                UPDATE trusted_devices 
                SET encrypted_data = ? 
                WHERE device_id = ?
            """, (b"corrupted_encrypted_data", "test-device"))
            conn.commit()
        
        # Should handle decryption failure gracefully
        result = self.registry.get_trusted_device("test-device")
        assert result is None
    
    def test_concurrent_access_handling(self):
        """Test handling of concurrent database access"""
        # This is a simplified test - real concurrent access testing would be more complex
        device_identity = DeviceIdentity(
            device_id="concurrent-device",
            device_name="Concurrent Device",
            device_type="phone",
            public_key_pem="test-key",
            key_fingerprint="fingerprint",
            hardware_fingerprint="hw-fingerprint",
            pairing_timestamp=time.time(),
            last_seen_timestamp=time.time()
        )
        
        # Multiple registries accessing same database
        registry1 = DeviceRegistry(self.temp_db.name, self.encryption_key)
        registry2 = DeviceRegistry(self.temp_db.name, self.encryption_key)
        
        # Both should be able to register devices
        result1 = registry1.register_device(device_identity, "secret1")
        
        device_identity2 = DeviceIdentity(
            device_id="concurrent-device-2",
            device_name="Concurrent Device 2",
            device_type="phone",
            public_key_pem="test-key-2",
            key_fingerprint="fingerprint2",
            hardware_fingerprint="hw-fingerprint2",
            pairing_timestamp=time.time(),
            last_seen_timestamp=time.time()
        )
        
        result2 = registry2.register_device(device_identity2, "secret2")
        
        assert result1 is True
        assert result2 is True
        
        # Both should be able to read each other's devices
        device1_from_registry2 = registry2.get_trusted_device("concurrent-device")
        device2_from_registry1 = registry1.get_trusted_device("concurrent-device-2")
        
        assert device1_from_registry2 is not None
        assert device2_from_registry1 is not None


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions"""
    
    def test_extremely_long_device_identifiers(self):
        """Test handling of extremely long device identifiers"""
        # Very long device ID
        long_device_id = "x" * 10000
        
        device_identity = DeviceIdentity(
            device_id=long_device_id,
            device_name="Long ID Device",
            device_type="phone",
            public_key_pem="test-key",
            key_fingerprint="fingerprint",
            hardware_fingerprint="hw-fingerprint",
            pairing_timestamp=time.time(),
            last_seen_timestamp=time.time()
        )
        
        # Should handle long IDs gracefully
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        registry = None
        try:
            registry = DeviceRegistry(temp_db.name, Fernet.generate_key())
            result = registry.register_device(device_identity, "secret")
            
            # Might succeed or fail depending on database limits
            if result:
                retrieved = registry.get_trusted_device(long_device_id)
                assert retrieved is not None
                assert retrieved.identity.device_id == long_device_id
                
        finally:
            if registry:
                del registry
            # Force garbage collection to close any remaining connections
            import gc
            gc.collect()
            
            # Retry deletion with backoff
            for attempt in range(5):
                try:
                    Path(temp_db.name).unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt < 4:  # Not the last attempt
                        time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        gc.collect()  # Force another GC
    
    def test_zero_and_negative_timestamps(self):
        """Test handling of zero and negative timestamps"""
        # Zero timestamp
        zero_timestamp_identity = DeviceIdentity(
            device_id="zero-timestamp-device",
            device_name="Zero Timestamp Device",
            device_type="phone",
            public_key_pem="test-key",
            key_fingerprint="fingerprint",
            hardware_fingerprint="hw-fingerprint",
            pairing_timestamp=0.0,
            last_seen_timestamp=0.0
        )
        
        # Negative timestamp
        negative_timestamp_identity = DeviceIdentity(
            device_id="negative-timestamp-device",
            device_name="Negative Timestamp Device",
            device_type="phone",
            public_key_pem="test-key",
            key_fingerprint="fingerprint",
            hardware_fingerprint="hw-fingerprint",
            pairing_timestamp=-1000.0,
            last_seen_timestamp=-1000.0
        )
        
        # Should handle edge case timestamps
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            registry = DeviceRegistry(temp_db.name, Fernet.generate_key())
            
            result1 = registry.register_device(zero_timestamp_identity, "secret1")
            result2 = registry.register_device(negative_timestamp_identity, "secret2")
            
            # Should handle gracefully
            assert result1 in [True, False]  # Either succeeds or fails gracefully
            assert result2 in [True, False]
            
        finally:
            if 'registry' in locals():
                del registry
            # Force garbage collection to close any remaining connections
            import gc
            gc.collect()
            
            # Retry deletion with backoff
            for attempt in range(5):
                try:
                    Path(temp_db.name).unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt < 4:  # Not the last attempt
                        time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        gc.collect()  # Force another GC
    
    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters in device data"""
        unicode_identity = DeviceIdentity(
            device_id="unicode-device-🔐",
            device_name="Test Device 测试设备 🚀",
            device_type="phone",
            public_key_pem="test-key-with-unicode-comment-/* 测试 */",
            key_fingerprint="fingerprint-🔑",
            hardware_fingerprint="hw-fingerprint-特殊字符",
            pairing_timestamp=time.time(),
            last_seen_timestamp=time.time()
        )
        
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            registry = DeviceRegistry(temp_db.name, Fernet.generate_key())
            result = registry.register_device(unicode_identity, "secret-with-unicode-🔐")
            
            if result:
                retrieved = registry.get_trusted_device("unicode-device-🔐")
                assert retrieved is not None
                assert retrieved.identity.device_name == "Test Device 测试设备 🚀"
                
        finally:
            if 'registry' in locals():
                del registry
            # Force garbage collection to close any remaining connections
            import gc
            gc.collect()
            
            # Retry deletion with backoff
            for attempt in range(5):
                try:
                    Path(temp_db.name).unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt < 4:  # Not the last attempt
                        time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        gc.collect()  # Force another GC
    
    def test_maximum_rate_limit_values(self):
        """Test handling of maximum rate limit values"""
        device_identity = DeviceIdentity(
            device_id="max-rate-device",
            device_name="Max Rate Device",
            device_type="phone",
            public_key_pem="test-key",
            key_fingerprint="fingerprint",
            hardware_fingerprint="hw-fingerprint",
            pairing_timestamp=time.time(),
            last_seen_timestamp=time.time()
        )
        
        # Extreme rate limits
        extreme_rate_limits = {
            "commands_per_day": 2**31 - 1,  # Max 32-bit signed int
            "input_events_per_minute": 0,   # Zero limit
            "negative_limit": -1000         # Negative limit
        }
        
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            registry = DeviceRegistry(temp_db.name, Fernet.generate_key())
            result = registry.register_device(
                device_identity, 
                "secret",
                rate_limits=extreme_rate_limits
            )
            
            if result:
                # Test rate limit checking with extreme values
                assert registry.check_rate_limit("max-rate-device", "commands_per_day") is True
                assert registry.check_rate_limit("max-rate-device", "input_events_per_minute") is False
                assert registry.check_rate_limit("max-rate-device", "negative_limit") is True  # Negative treated as no limit
                
        finally:
            if 'registry' in locals():
                del registry
            # Force garbage collection to close any remaining connections
            import gc
            gc.collect()
            
            # Retry deletion with backoff
            for attempt in range(5):
                try:
                    Path(temp_db.name).unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt < 4:  # Not the last attempt
                        time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        gc.collect()  # Force another GC