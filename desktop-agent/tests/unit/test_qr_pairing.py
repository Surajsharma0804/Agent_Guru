"""
Unit Tests for QR Code Pairing System

Tests QR code generation, token validation, and pairing workflow
with comprehensive security and error condition coverage.
"""

import json
import time
import secrets
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

import pytest
from PIL import Image

from src.pairing.qr_pairing import (
    QRPairingManager, PairingToken, DeviceFingerprint, 
    PairingResult, PairingStatus
)


class TestDeviceFingerprint:
    """Test device fingerprint generation and validation"""
    
    def test_device_fingerprint_creation(self):
        """Test device fingerprint creation with all required fields"""
        fingerprint = DeviceFingerprint(
            device_id="test-device-123",
            hardware_hash="abc123def456",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        assert fingerprint.device_id == "test-device-123"
        assert fingerprint.hardware_hash == "abc123def456"
        assert fingerprint.os_version == "Windows 11"
        assert fingerprint.app_version == "1.0.0"
        assert fingerprint.creation_timestamp > 0
    
    def test_device_fingerprint_to_bytes(self):
        """Test fingerprint serialization to bytes"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=1234567890.0
        )
        
        fingerprint_bytes = fingerprint.to_bytes()
        assert isinstance(fingerprint_bytes, bytes)
        
        # Should be valid JSON
        fingerprint_data = json.loads(fingerprint_bytes.decode('utf-8'))
        assert fingerprint_data["device_id"] == "test-device"
        assert fingerprint_data["hardware_hash"] == "hash123"
    
    def test_device_fingerprint_hash_computation(self):
        """Test fingerprint hash computation is deterministic"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=1234567890.0
        )
        
        hash1 = fingerprint.compute_hash()
        hash2 = fingerprint.compute_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest
        assert isinstance(hash1, str)
    
    def test_device_fingerprint_immutable(self):
        """Test that device fingerprint is immutable"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        # Should not be able to modify frozen dataclass
        with pytest.raises(AttributeError):
            fingerprint.device_id = "modified"


class TestPairingToken:
    """Test pairing token generation and validation"""
    
    def test_pairing_token_generation(self):
        """Test pairing token generation with valid parameters"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        secret_key = secrets.token_bytes(32)
        token = PairingToken.generate(fingerprint, 300, secret_key)
        
        assert len(token.token_id) > 0
        assert token.device_fingerprint == fingerprint
        assert token.expiration_timestamp > time.time()
        assert len(token.challenge_nonce) > 0
        assert len(token.hmac_signature) > 0
    
    def test_pairing_token_validation_success(self):
        """Test successful pairing token validation"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        secret_key = secrets.token_bytes(32)
        token = PairingToken.generate(fingerprint, 300, secret_key)
        
        # Token should be valid immediately after generation
        assert token.is_valid(secret_key)
    
    def test_pairing_token_validation_expired(self):
        """Test pairing token validation with expired token"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        secret_key = secrets.token_bytes(32)
        token = PairingToken.generate(fingerprint, -1, secret_key)  # Already expired
        
        # Token should be invalid due to expiration
        assert not token.is_valid(secret_key)
    
    def test_pairing_token_validation_wrong_key(self):
        """Test pairing token validation with wrong secret key"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        secret_key = secrets.token_bytes(32)
        wrong_key = secrets.token_bytes(32)
        token = PairingToken.generate(fingerprint, 300, secret_key)
        
        # Token should be invalid with wrong key
        assert not token.is_valid(wrong_key)
    
    def test_pairing_token_qr_data_format(self):
        """Test pairing token QR data format"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        token = PairingToken.generate(fingerprint)
        qr_data = token.to_qr_data()
        
        assert qr_data["version"] == "1.0"
        assert qr_data["type"] == "guru_pairing"
        assert qr_data["token_id"] == token.token_id
        assert "device_fingerprint" in qr_data
        assert qr_data["expiration_timestamp"] == token.expiration_timestamp
        assert qr_data["challenge_nonce"] == token.challenge_nonce
        assert qr_data["hmac_signature"] == token.hmac_signature


class TestPairingResult:
    """Test pairing result data structure"""
    
    def test_pairing_result_creation(self):
        """Test pairing result creation with required fields"""
        result = PairingResult(
            status=PairingStatus.INITIATED,
            token_id="test-token-123"
        )
        
        assert result.status == PairingStatus.INITIATED
        assert result.token_id == "test-token-123"
        assert result.requires_physical_confirmation is True
        assert result.confirmed_on_both_devices is False
        assert result.has_valid_key_exchange is False
    
    def test_pairing_result_success_property(self):
        """Test pairing result success property"""
        # Successful result
        success_result = PairingResult(
            status=PairingStatus.COMPLETED,
            token_id="test-token"
        )
        assert success_result.is_successful is True
        
        # Failed result
        failed_result = PairingResult(
            status=PairingStatus.FAILED,
            token_id="test-token"
        )
        assert failed_result.is_successful is False
    
    def test_pairing_result_pending_property(self):
        """Test pairing result pending property"""
        # Pending result
        pending_result = PairingResult(
            status=PairingStatus.PENDING_CONFIRMATION,
            token_id="test-token"
        )
        assert pending_result.is_pending is True
        
        # Completed result
        completed_result = PairingResult(
            status=PairingStatus.COMPLETED,
            token_id="test-token"
        )
        assert completed_result.is_pending is False


class TestQRPairingManager:
    """Test QR pairing manager functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.secret_key = secrets.token_bytes(32)
        self.manager = QRPairingManager(self.secret_key)
    
    @patch('platform.processor')
    @patch('platform.machine') 
    @patch('platform.platform')
    @patch('uuid.getnode')
    @patch('psutil.virtual_memory')
    def test_generate_device_fingerprint(self, mock_memory, mock_getnode, mock_platform_platform, mock_machine, mock_processor):
        """Test device fingerprint generation"""
        # Mock system information
        mock_getnode.return_value = 0x123456789abc
        mock_processor.return_value = "Intel64 Family 6 Model 142"
        mock_machine.return_value = "AMD64"
        mock_platform_platform.return_value = "Windows-11-10.0.22000-SP0"
        
        mock_memory_obj = MagicMock()
        mock_memory_obj.total = 17179869184  # 16GB
        mock_memory.return_value = mock_memory_obj
        
        fingerprint = self.manager.generate_device_fingerprint()
        
        assert fingerprint.device_id.startswith("guru-desktop-")
        assert len(fingerprint.hardware_hash) == 16
        assert fingerprint.os_version == "Windows-11-10.0.22000-SP0"
        assert fingerprint.app_version == "1.0.0"
        assert fingerprint.creation_timestamp > 0
    
    def test_initiate_pairing(self):
        """Test pairing initiation with QR code generation"""
        with patch.object(self.manager, 'generate_device_fingerprint') as mock_fingerprint:
            mock_fingerprint.return_value = DeviceFingerprint(
                device_id="test-device",
                hardware_hash="hash123",
                os_version="Windows 11",
                app_version="1.0.0",
                creation_timestamp=time.time()
            )
            
            token, qr_image = self.manager.initiate_pairing(300)
            
            # Verify token
            assert isinstance(token, PairingToken)
            assert token.token_id in self.manager.active_tokens
            assert token.token_id in self.manager.pairing_sessions
            
            # Verify QR image
            assert hasattr(qr_image, 'save')  # PIL Image-like object
            
            # Verify pairing session
            session = self.manager.pairing_sessions[token.token_id]
            assert session.status == PairingStatus.INITIATED
            assert session.requires_physical_confirmation is True
    
    def test_validate_pairing_token_success(self):
        """Test successful pairing token validation"""
        # First initiate pairing
        with patch.object(self.manager, 'generate_device_fingerprint') as mock_fingerprint:
            mock_fingerprint.return_value = DeviceFingerprint(
                device_id="test-device",
                hardware_hash="hash123",
                os_version="Windows 11",
                app_version="1.0.0",
                creation_timestamp=time.time()
            )
            
            token, _ = self.manager.initiate_pairing(300)
            
            # Validate the token
            qr_data = token.to_qr_data()
            result = self.manager.validate_pairing_token(qr_data)
            
            assert result.status == PairingStatus.PENDING_CONFIRMATION
            assert result.token_id == token.token_id
            assert result.error_message is None
    
    def test_validate_pairing_token_invalid_type(self):
        """Test pairing token validation with invalid QR type"""
        invalid_qr_data = {
            "type": "invalid_type",
            "version": "1.0"
        }
        
        result = self.manager.validate_pairing_token(invalid_qr_data)
        
        assert result.status == PairingStatus.FAILED
        assert "Invalid QR code type" in result.error_message
    
    def test_validate_pairing_token_unsupported_version(self):
        """Test pairing token validation with unsupported version"""
        invalid_qr_data = {
            "type": "guru_pairing",
            "version": "2.0"  # Unsupported version
        }
        
        result = self.manager.validate_pairing_token(invalid_qr_data)
        
        assert result.status == PairingStatus.FAILED
        assert "Unsupported QR code version" in result.error_message
    
    def test_validate_pairing_token_not_found(self):
        """Test pairing token validation with token not in active tokens"""
        # Create a valid token structure but don't add to active tokens
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        token = PairingToken.generate(fingerprint, 300, self.secret_key)
        qr_data = token.to_qr_data()
        
        result = self.manager.validate_pairing_token(qr_data)
        
        assert result.status == PairingStatus.FAILED
        assert "not found or already used" in result.error_message
    
    def test_confirm_pairing_success(self):
        """Test successful pairing confirmation"""
        # Set up pairing session
        token_id = "test-token-123"
        session = PairingResult(
            status=PairingStatus.PENDING_CONFIRMATION,
            token_id=token_id
        )
        self.manager.pairing_sessions[token_id] = session
        self.manager.active_tokens[token_id] = MagicMock()
        
        result = self.manager.confirm_pairing(token_id, True)
        
        assert result.status == PairingStatus.CONFIRMED
        assert result.confirmed_on_both_devices is True
        assert result.completion_timestamp is not None
    
    def test_confirm_pairing_rejected(self):
        """Test pairing confirmation rejection"""
        # Set up pairing session
        token_id = "test-token-123"
        session = PairingResult(
            status=PairingStatus.PENDING_CONFIRMATION,
            token_id=token_id
        )
        self.manager.pairing_sessions[token_id] = session
        self.manager.active_tokens[token_id] = MagicMock()
        
        result = self.manager.confirm_pairing(token_id, False)
        
        assert result.status == PairingStatus.REJECTED
        assert "User rejected" in result.error_message
        assert token_id not in self.manager.active_tokens
    
    def test_confirm_pairing_not_found(self):
        """Test pairing confirmation with non-existent session"""
        result = self.manager.confirm_pairing("non-existent-token", True)
        
        assert result.status == PairingStatus.FAILED
        assert "not found" in result.error_message
    
    def test_complete_pairing_success(self):
        """Test successful pairing completion"""
        # Set up confirmed pairing session
        token_id = "test-token-123"
        session = PairingResult(
            status=PairingStatus.CONFIRMED,
            token_id=token_id
        )
        self.manager.pairing_sessions[token_id] = session
        self.manager.active_tokens[token_id] = MagicMock()
        
        result = self.manager.complete_pairing(token_id)
        
        assert result.status == PairingStatus.COMPLETED
        assert result.has_valid_key_exchange is True
        assert result.completion_timestamp is not None
        assert token_id not in self.manager.active_tokens
    
    def test_complete_pairing_not_confirmed(self):
        """Test pairing completion without confirmation"""
        # Set up unconfirmed pairing session
        token_id = "test-token-123"
        session = PairingResult(
            status=PairingStatus.PENDING_CONFIRMATION,
            token_id=token_id
        )
        self.manager.pairing_sessions[token_id] = session
        
        result = self.manager.complete_pairing(token_id)
        
        assert result.status == PairingStatus.FAILED
        assert "not confirmed" in result.error_message
    
    def test_cleanup_expired_tokens(self):
        """Test cleanup of expired pairing tokens"""
        # Add expired token
        expired_fingerprint = DeviceFingerprint(
            device_id="expired-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        expired_token = PairingToken.generate(expired_fingerprint, -1, self.secret_key)
        self.manager.active_tokens[expired_token.token_id] = expired_token
        self.manager.pairing_sessions[expired_token.token_id] = PairingResult(
            status=PairingStatus.INITIATED,
            token_id=expired_token.token_id
        )
        
        # Add valid token
        valid_fingerprint = DeviceFingerprint(
            device_id="valid-device",
            hardware_hash="hash456",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        valid_token = PairingToken.generate(valid_fingerprint, 300, self.secret_key)
        self.manager.active_tokens[valid_token.token_id] = valid_token
        
        # Cleanup expired tokens
        expired_count = self.manager.cleanup_expired_tokens()
        
        assert expired_count == 1
        assert expired_token.token_id not in self.manager.active_tokens
        assert valid_token.token_id in self.manager.active_tokens
        
        # Check session status updated
        expired_session = self.manager.pairing_sessions[expired_token.token_id]
        assert expired_session.status == PairingStatus.EXPIRED
    
    def test_get_pairing_status(self):
        """Test getting pairing status"""
        token_id = "test-token-123"
        session = PairingResult(
            status=PairingStatus.INITIATED,
            token_id=token_id
        )
        self.manager.pairing_sessions[token_id] = session
        
        # Should return the session
        result = self.manager.get_pairing_status(token_id)
        assert result == session
        
        # Should return None for non-existent token
        result = self.manager.get_pairing_status("non-existent")
        assert result is None
    
    def test_revoke_pairing(self):
        """Test pairing revocation"""
        token_id = "test-token-123"
        
        # Add active token and session
        self.manager.active_tokens[token_id] = MagicMock()
        self.manager.pairing_sessions[token_id] = PairingResult(
            status=PairingStatus.INITIATED,
            token_id=token_id
        )
        
        result = self.manager.revoke_pairing(token_id)
        
        assert result is True
        assert token_id not in self.manager.active_tokens
        
        session = self.manager.pairing_sessions[token_id]
        assert session.status == PairingStatus.REJECTED
        assert "revoked" in session.error_message
    
    def test_revoke_pairing_not_found(self):
        """Test revoking non-existent pairing"""
        result = self.manager.revoke_pairing("non-existent-token")
        assert result is False


# Security-focused tests
class TestQRPairingSecurity:
    """Security-focused tests for QR pairing system"""
    
    def test_token_cryptographic_randomness(self):
        """Test that tokens use cryptographically secure randomness"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        # Generate multiple tokens
        tokens = []
        for _ in range(10):
            token = PairingToken.generate(fingerprint)
            tokens.append(token)
        
        # All token IDs should be unique
        token_ids = [token.token_id for token in tokens]
        assert len(set(token_ids)) == len(token_ids)
        
        # All nonces should be unique
        nonces = [token.challenge_nonce for token in tokens]
        assert len(set(nonces)) == len(nonces)
    
    def test_hmac_signature_prevents_tampering(self):
        """Test that HMAC signature prevents token tampering"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        secret_key = secrets.token_bytes(32)
        token = PairingToken.generate(fingerprint, 300, secret_key)
        
        # Original token should be valid
        assert token.is_valid(secret_key)
        
        # Tampered token should be invalid
        tampered_token = PairingToken(
            token_id=token.token_id + "tampered",  # Modified token ID
            device_fingerprint=token.device_fingerprint,
            expiration_timestamp=token.expiration_timestamp,
            challenge_nonce=token.challenge_nonce,
            hmac_signature=token.hmac_signature  # Original signature
        )
        
        assert not tampered_token.is_valid(secret_key)
    
    def test_token_expiration_enforcement(self):
        """Test that token expiration is properly enforced"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        secret_key = secrets.token_bytes(32)
        
        # Create token that expires in 1 second
        token = PairingToken.generate(fingerprint, 1, secret_key)
        
        # Should be valid immediately
        assert token.is_valid(secret_key)
        
        # Should be invalid after expiration
        time.sleep(1.1)
        assert not token.is_valid(secret_key)
    
    def test_constant_time_signature_verification(self):
        """Test that signature verification uses constant-time comparison"""
        fingerprint = DeviceFingerprint(
            device_id="test-device",
            hardware_hash="hash123",
            os_version="Windows 11",
            app_version="1.0.0",
            creation_timestamp=time.time()
        )
        
        secret_key = secrets.token_bytes(32)
        token = PairingToken.generate(fingerprint, 300, secret_key)
        
        # Valid signature should pass
        assert token.is_valid(secret_key)
        
        # Invalid signature should fail (tests hmac.compare_digest usage)
        invalid_token = PairingToken(
            token_id=token.token_id,
            device_fingerprint=token.device_fingerprint,
            expiration_timestamp=token.expiration_timestamp,
            challenge_nonce=token.challenge_nonce,
            hmac_signature="invalid_signature"
        )
        
        assert not invalid_token.is_valid(secret_key)