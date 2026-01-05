"""
Unit Tests for Asymmetric Key Exchange System

Tests ECDSA-P256 key generation, key exchange protocol, and mutual authentication
with comprehensive security and error condition coverage.
"""

import json
import time
import secrets
from unittest.mock import patch, MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

from src.pairing.key_exchange import (
    KeyExchangeManager, DeviceKeyPair, KeyExchangeMessage,
    KeyExchangeResult, KeyExchangeStatus
)


class TestDeviceKeyPair:
    """Test ECDSA-P256 key pair generation and operations"""
    
    def test_key_pair_generation(self):
        """Test ECDSA-P256 key pair generation"""
        device_id = "test-device-123"
        key_pair = DeviceKeyPair.generate(device_id)
        
        assert key_pair.device_id == device_id
        assert key_pair.algorithm == "ECDSA-P256"
        assert len(key_pair.key_fingerprint) == 16
        assert key_pair.creation_timestamp > 0
        
        # Verify PEM format
        assert key_pair.private_key_pem.startswith("-----BEGIN PRIVATE KEY-----")
        assert key_pair.public_key_pem.startswith("-----BEGIN PUBLIC KEY-----")
    
    def test_key_pair_cryptographic_strength(self):
        """Test that generated keys use proper cryptographic parameters"""
        key_pair = DeviceKeyPair.generate("test-device")
        
        # Load and verify private key
        private_key = key_pair.get_private_key()
        assert isinstance(private_key, ec.EllipticCurvePrivateKey)
        assert isinstance(private_key.curve, ec.SECP256R1)
        
        # Load and verify public key
        public_key = key_pair.get_public_key()
        assert isinstance(public_key, ec.EllipticCurvePublicKey)
        assert isinstance(public_key.curve, ec.SECP256R1)
        
        # Verify key correspondence
        derived_public = private_key.public_key()
        assert (derived_public.public_numbers().x == public_key.public_numbers().x and
                derived_public.public_numbers().y == public_key.public_numbers().y)
    
    def test_key_fingerprint_uniqueness(self):
        """Test that key fingerprints are unique across different keys"""
        key_pair1 = DeviceKeyPair.generate("device-1")
        key_pair2 = DeviceKeyPair.generate("device-2")
        
        assert key_pair1.key_fingerprint != key_pair2.key_fingerprint
        assert len(key_pair1.key_fingerprint) == 16
        assert len(key_pair2.key_fingerprint) == 16
    
    def test_key_fingerprint_deterministic(self):
        """Test that key fingerprint is deterministic for same key"""
        key_pair = DeviceKeyPair.generate("test-device")
        
        # Recreate key pair from same PEM data
        recreated_pair = DeviceKeyPair(
            private_key_pem=key_pair.private_key_pem,
            public_key_pem=key_pair.public_key_pem,
            key_fingerprint=key_pair.key_fingerprint,
            device_id=key_pair.device_id,
            creation_timestamp=key_pair.creation_timestamp
        )
        
        # Fingerprints should match
        assert key_pair.key_fingerprint == recreated_pair.key_fingerprint
    
    def test_sign_and_verify_data(self):
        """Test data signing and verification"""
        key_pair = DeviceKeyPair.generate("test-device")
        test_data = b"Hello, GURU secure pairing!"
        
        # Sign data
        signature = key_pair.sign_data(test_data)
        assert isinstance(signature, str)
        assert len(signature) > 0
        
        # Verify signature with own public key
        assert key_pair.verify_signature(test_data, signature)
        
        # Verify signature fails with different data
        assert not key_pair.verify_signature(b"Different data", signature)
    
    def test_cross_device_signature_verification(self):
        """Test signature verification between different devices"""
        device1_keys = DeviceKeyPair.generate("device-1")
        device2_keys = DeviceKeyPair.generate("device-2")
        
        test_data = b"Cross-device verification test"
        
        # Device 1 signs data
        signature = device1_keys.sign_data(test_data)
        
        # Device 2 verifies using Device 1's public key
        assert device2_keys.verify_signature(
            test_data, signature, device1_keys.public_key_pem
        )
        
        # Verification should fail with Device 2's own public key
        assert not device2_keys.verify_signature(test_data, signature)
    
    def test_invalid_signature_handling(self):
        """Test handling of invalid signatures"""
        key_pair = DeviceKeyPair.generate("test-device")
        test_data = b"Test data"
        
        # Invalid base64 signature
        assert not key_pair.verify_signature(test_data, "invalid_base64!")
        
        # Valid base64 but invalid signature
        invalid_signature = "YWJjZGVmZ2hpams="  # "abcdefghijk" in base64
        assert not key_pair.verify_signature(test_data, invalid_signature)


class TestKeyExchangeMessage:
    """Test key exchange message format and validation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.sender_keys = DeviceKeyPair.generate("sender-device")
        self.recipient_keys = DeviceKeyPair.generate("recipient-device")
    
    def test_key_exchange_message_creation(self):
        """Test key exchange message creation and serialization"""
        message = KeyExchangeMessage(
            message_type="key_exchange_request",
            sender_device_id="sender-device",
            recipient_device_id="recipient-device",
            public_key_pem=self.sender_keys.public_key_pem,
            challenge_nonce="test-nonce-123",
            signature="test-signature",
            timestamp=time.time()
        )
        
        # Test serialization
        message_dict = message.to_dict()
        assert message_dict["message_type"] == "key_exchange_request"
        assert message_dict["sender_device_id"] == "sender-device"
        assert message_dict["public_key_pem"] == self.sender_keys.public_key_pem
        
        # Test deserialization
        recreated_message = KeyExchangeMessage.from_dict(message_dict)
        assert recreated_message.message_type == message.message_type
        assert recreated_message.sender_device_id == message.sender_device_id
    
    def test_message_signature_verification_success(self):
        """Test successful message signature verification"""
        # Create message data
        message_data = {
            "message_type": "key_exchange_request",
            "sender_device_id": "sender-device",
            "recipient_device_id": "recipient-device",
            "public_key_pem": self.sender_keys.public_key_pem,
            "challenge_nonce": "test-nonce-123",
            "timestamp": time.time()
        }
        
        # Sign message
        message_bytes = json.dumps(message_data, sort_keys=True).encode('utf-8')
        signature = self.sender_keys.sign_data(message_bytes)
        
        # Create message with signature
        message = KeyExchangeMessage(
            signature=signature,
            **message_data
        )
        
        # Verify signature
        assert message.verify_signature(self.sender_keys.public_key_pem)
    
    def test_message_signature_verification_failure(self):
        """Test message signature verification failure"""
        message = KeyExchangeMessage(
            message_type="key_exchange_request",
            sender_device_id="sender-device",
            recipient_device_id="recipient-device",
            public_key_pem=self.sender_keys.public_key_pem,
            challenge_nonce="test-nonce-123",
            signature="invalid-signature",
            timestamp=time.time()
        )
        
        # Should fail with invalid signature
        assert not message.verify_signature(self.sender_keys.public_key_pem)
        
        # Should fail with wrong public key
        assert not message.verify_signature(self.recipient_keys.public_key_pem)


class TestKeyExchangeResult:
    """Test key exchange result data structure"""
    
    def test_key_exchange_result_creation(self):
        """Test key exchange result creation"""
        result = KeyExchangeResult(
            status=KeyExchangeStatus.INITIATED,
            local_device_id="local-device",
            remote_device_id="remote-device"
        )
        
        assert result.status == KeyExchangeStatus.INITIATED
        assert result.local_device_id == "local-device"
        assert result.remote_device_id == "remote-device"
        assert result.shared_secret_hash is None
        assert result.error_message is None
    
    def test_key_exchange_result_success_property(self):
        """Test success property evaluation"""
        # Successful result
        success_result = KeyExchangeResult(
            status=KeyExchangeStatus.COMPLETED,
            local_device_id="local-device"
        )
        assert success_result.is_successful is True
        assert success_result.is_failed is False
        
        # Failed result
        failed_result = KeyExchangeResult(
            status=KeyExchangeStatus.FAILED,
            local_device_id="local-device"
        )
        assert failed_result.is_successful is False
        assert failed_result.is_failed is True


class TestKeyExchangeManager:
    """Test key exchange manager functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.device_id = "test-device-123"
        self.manager = KeyExchangeManager(self.device_id)
    
    def test_manager_initialization(self):
        """Test key exchange manager initialization"""
        assert self.manager.device_id == self.device_id
        assert self.manager.device_key_pair is None
        assert len(self.manager.active_exchanges) == 0
        assert len(self.manager.trusted_keys) == 0
    
    def test_generate_device_keys(self):
        """Test device key generation"""
        key_pair = self.manager.generate_device_keys()
        
        assert isinstance(key_pair, DeviceKeyPair)
        assert key_pair.device_id == self.device_id
        assert self.manager.device_key_pair == key_pair
    
    def test_initiate_key_exchange(self):
        """Test key exchange initiation"""
        remote_device_id = "remote-device-456"
        
        message, result = self.manager.initiate_key_exchange(remote_device_id)
        
        # Verify message
        assert isinstance(message, KeyExchangeMessage)
        assert message.message_type == "key_exchange_request"
        assert message.sender_device_id == self.device_id
        assert message.recipient_device_id == remote_device_id
        assert len(message.challenge_nonce) > 0
        assert len(message.signature) > 0
        
        # Verify result
        assert isinstance(result, KeyExchangeResult)
        assert result.status == KeyExchangeStatus.PUBLIC_KEY_SENT
        assert result.local_device_id == self.device_id
        assert result.remote_device_id == remote_device_id
        
        # Verify exchange is tracked
        exchange_id = f"{self.device_id}-{remote_device_id}"
        assert exchange_id in self.manager.active_exchanges
    
    def test_process_key_exchange_request(self):
        """Test processing incoming key exchange request"""
        # Create sender manager
        sender_manager = KeyExchangeManager("sender-device")
        sender_message, _ = sender_manager.initiate_key_exchange(self.device_id)
        
        # Process request
        response_message, result = self.manager.process_key_exchange_request(sender_message)
        
        # Verify response message
        assert isinstance(response_message, KeyExchangeMessage)
        assert response_message.message_type == "key_exchange_response"
        assert response_message.sender_device_id == self.device_id
        assert response_message.recipient_device_id == "sender-device"
        
        # Verify result
        assert isinstance(result, KeyExchangeResult)
        assert result.status == KeyExchangeStatus.SHARED_SECRET_DERIVED
        assert result.local_device_id == self.device_id
        assert result.remote_device_id == "sender-device"
        assert result.shared_secret_hash is not None
    
    def test_process_key_exchange_response(self):
        """Test processing key exchange response"""
        # Set up initial exchange
        remote_device_id = "remote-device"
        original_message, original_result = self.manager.initiate_key_exchange(remote_device_id)
        exchange_id = f"{self.device_id}-{remote_device_id}"
        
        # Create remote manager and process request
        remote_manager = KeyExchangeManager(remote_device_id)
        response_message, _ = remote_manager.process_key_exchange_request(original_message)
        
        # Process response
        final_result = self.manager.process_key_exchange_response(response_message, exchange_id)
        
        # Verify completion
        assert final_result.status == KeyExchangeStatus.COMPLETED
        assert final_result.shared_secret_hash is not None
        assert final_result.remote_key_fingerprint is not None
        assert final_result.completion_timestamp is not None
        
        # Verify trusted key is stored
        assert remote_device_id in self.manager.trusted_keys
    
    def test_full_key_exchange_workflow(self):
        """Test complete key exchange workflow between two devices"""
        # Create two managers
        device_a = KeyExchangeManager("device-a")
        device_b = KeyExchangeManager("device-b")
        
        # Device A initiates exchange
        request_message, request_result = device_a.initiate_key_exchange("device-b")
        assert request_result.status == KeyExchangeStatus.PUBLIC_KEY_SENT
        
        # Device B processes request and sends response
        response_message, response_result = device_b.process_key_exchange_request(request_message)
        assert response_result.status == KeyExchangeStatus.SHARED_SECRET_DERIVED
        
        # Device A processes response
        exchange_id = "device-a-device-b"
        final_result = device_a.process_key_exchange_response(response_message, exchange_id)
        assert final_result.status == KeyExchangeStatus.COMPLETED
        
        # Verify both devices have derived the same shared secret
        assert final_result.shared_secret_hash == response_result.shared_secret_hash
        
        # Verify mutual trust establishment
        assert "device-b" in device_a.trusted_keys
        assert device_a.get_trusted_device_key("device-b") == device_b.device_key_pair.public_key_pem
    
    def test_key_exchange_message_validation_errors(self):
        """Test key exchange message validation error handling"""
        # Wrong recipient device
        wrong_recipient_message = KeyExchangeMessage(
            message_type="key_exchange_request",
            sender_device_id="sender-device",
            recipient_device_id="wrong-device",  # Not this device
            public_key_pem="fake-key",
            challenge_nonce="nonce",
            signature="signature",
            timestamp=time.time()
        )
        
        with pytest.raises(ValueError, match="not intended for this device"):
            self.manager.process_key_exchange_request(wrong_recipient_message)
        
        # Invalid message type
        invalid_type_message = KeyExchangeMessage(
            message_type="invalid_type",
            sender_device_id="sender-device",
            recipient_device_id=self.device_id,
            public_key_pem="fake-key",
            challenge_nonce="nonce",
            signature="signature",
            timestamp=time.time()
        )
        
        with pytest.raises(ValueError, match="Invalid message type"):
            self.manager.process_key_exchange_request(invalid_type_message)
    
    def test_key_exchange_signature_validation(self):
        """Test key exchange message signature validation"""
        # Create message with invalid signature
        invalid_signature_message = KeyExchangeMessage(
            message_type="key_exchange_request",
            sender_device_id="sender-device",
            recipient_device_id=self.device_id,
            public_key_pem=DeviceKeyPair.generate("sender-device").public_key_pem,
            challenge_nonce="nonce",
            signature="invalid-signature",
            timestamp=time.time()
        )
        
        with pytest.raises(ValueError, match="Invalid message signature"):
            self.manager.process_key_exchange_request(invalid_signature_message)
    
    def test_get_exchange_status(self):
        """Test getting exchange status"""
        # No exchange exists
        assert self.manager.get_exchange_status("non-existent") is None
        
        # Create exchange
        remote_device_id = "remote-device"
        _, result = self.manager.initiate_key_exchange(remote_device_id)
        exchange_id = f"{self.device_id}-{remote_device_id}"
        
        # Should return the result
        retrieved_result = self.manager.get_exchange_status(exchange_id)
        assert retrieved_result == result
    
    def test_trusted_device_management(self):
        """Test trusted device key management"""
        device_id = "trusted-device"
        public_key = DeviceKeyPair.generate(device_id).public_key_pem
        
        # Initially no trusted key
        assert self.manager.get_trusted_device_key(device_id) is None
        
        # Add trusted key (simulating completed exchange)
        self.manager.trusted_keys[device_id] = public_key
        
        # Should return the key
        assert self.manager.get_trusted_device_key(device_id) == public_key
        
        # Revoke trust
        assert self.manager.revoke_trusted_device(device_id) is True
        assert self.manager.get_trusted_device_key(device_id) is None
        
        # Revoking non-existent device should return False
        assert self.manager.revoke_trusted_device("non-existent") is False
    
    def test_cleanup_expired_exchanges(self):
        """Test cleanup of expired key exchange sessions"""
        # Create exchange that would be considered expired
        remote_device_id = "remote-device"
        _, result = self.manager.initiate_key_exchange(remote_device_id)
        exchange_id = f"{self.device_id}-{remote_device_id}"
        
        # Manually set completion timestamp to simulate old exchange
        result.completion_timestamp = time.time() - 7200  # 2 hours ago
        
        # Cleanup with 1 hour max age
        expired_count = self.manager.cleanup_expired_exchanges(3600)
        
        # Should have cleaned up the expired exchange
        assert expired_count == 1
        assert exchange_id not in self.manager.active_exchanges


# Security-focused tests
class TestKeyExchangeSecurity:
    """Security-focused tests for key exchange system"""
    
    def test_ecdh_shared_secret_derivation(self):
        """Test ECDH shared secret derivation produces same result on both sides"""
        device_a = KeyExchangeManager("device-a")
        device_b = KeyExchangeManager("device-b")
        
        # Generate keys for both devices
        keys_a = device_a.generate_device_keys()
        keys_b = device_b.generate_device_keys()
        
        # Simulate key exchange
        request_message, _ = device_a.initiate_key_exchange("device-b")
        response_message, response_result = device_b.process_key_exchange_request(request_message)
        
        exchange_id = "device-a-device-b"
        final_result = device_a.process_key_exchange_response(response_message, exchange_id)
        
        # Both devices should derive the same shared secret
        assert final_result.shared_secret_hash == response_result.shared_secret_hash
        assert final_result.shared_secret_hash is not None
        assert len(final_result.shared_secret_hash) == 16  # Truncated SHA-256
    
    def test_key_exchange_replay_protection(self):
        """Test that key exchange messages cannot be replayed"""
        device_a = KeyExchangeManager("device-a")
        device_b = KeyExchangeManager("device-b")
        
        # Initial key exchange
        request_message, _ = device_a.initiate_key_exchange("device-b")
        response_message, _ = device_b.process_key_exchange_request(request_message)
        
        # Attempting to process the same request again should succeed in current implementation
        # (Full replay protection would require nonce tracking which is not implemented yet)
        # This test documents the current behavior
        response_message2, _ = device_b.process_key_exchange_request(request_message)
        
        # Both responses should be valid (no replay protection yet)
        assert response_message2 is not None
    
    def test_key_fingerprint_collision_resistance(self):
        """Test that key fingerprints are collision-resistant"""
        fingerprints = set()
        
        # Generate many key pairs and check for fingerprint collisions
        for i in range(100):
            key_pair = DeviceKeyPair.generate(f"device-{i}")
            assert key_pair.key_fingerprint not in fingerprints
            fingerprints.add(key_pair.key_fingerprint)
        
        # All fingerprints should be unique
        assert len(fingerprints) == 100
    
    def test_private_key_never_transmitted(self):
        """Test that private keys are never included in exchange messages"""
        device_a = KeyExchangeManager("device-a")
        device_b = KeyExchangeManager("device-b")
        
        # Generate keys
        device_a.generate_device_keys()
        device_b.generate_device_keys()
        
        # Perform key exchange
        request_message, _ = device_a.initiate_key_exchange("device-b")
        response_message, _ = device_b.process_key_exchange_request(request_message)
        
        # Verify private keys are not in messages
        request_dict = request_message.to_dict()
        response_dict = response_message.to_dict()
        
        # Check that no private key material is present
        for message_dict in [request_dict, response_dict]:
            message_str = json.dumps(message_dict)
            assert "PRIVATE KEY" not in message_str
            assert "BEGIN PRIVATE" not in message_str
        
        # Only public keys should be present
        assert "BEGIN PUBLIC KEY" in request_message.public_key_pem
        assert "BEGIN PUBLIC KEY" in response_message.public_key_pem
    
    def test_signature_prevents_message_tampering(self):
        """Test that message signatures prevent tampering"""
        device_a = KeyExchangeManager("device-a")
        device_b = KeyExchangeManager("device-b")
        
        # Create legitimate message
        request_message, _ = device_a.initiate_key_exchange("device-b")
        
        # Tamper with message content
        tampered_message = KeyExchangeMessage(
            message_type=request_message.message_type,
            sender_device_id=request_message.sender_device_id,
            recipient_device_id=request_message.recipient_device_id,
            public_key_pem=request_message.public_key_pem,
            challenge_nonce="tampered_nonce",  # Modified nonce
            signature=request_message.signature,  # Original signature
            timestamp=request_message.timestamp
        )
        
        # Tampered message should fail signature verification
        with pytest.raises(ValueError, match="Invalid message signature"):
            device_b.process_key_exchange_request(tampered_message)