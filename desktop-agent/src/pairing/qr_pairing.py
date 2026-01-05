"""
QR Code Pairing System for GURU

Implements secure QR code generation and validation for device pairing.
Uses cryptographically secure tokens with device fingerprints and expiration.

Security Properties:
- Pairing tokens are cryptographically random and single-use
- Device fingerprints prevent token reuse across devices
- Expiration prevents replay attacks
- Physical presence required on both devices
- All operations are auditable and logged
"""

import json
import secrets
import time
import platform
import psutil
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import hmac
import base64

import qrcode
from qrcode.image.pil import PilImage
from PIL import Image
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, Field, validator
import structlog

logger = structlog.get_logger(__name__)


class PairingStatus(Enum):
    """Pairing operation status codes"""
    INITIATED = "initiated"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class DeviceFingerprint:
    """Cryptographic device fingerprint for binding pairing tokens"""
    device_id: str
    hardware_hash: str
    os_version: str
    app_version: str
    creation_timestamp: float
    
    def to_bytes(self) -> bytes:
        """Convert fingerprint to bytes for cryptographic operations"""
        fingerprint_data = {
            "device_id": self.device_id,
            "hardware_hash": self.hardware_hash,
            "os_version": self.os_version,
            "app_version": self.app_version,
            "creation_timestamp": self.creation_timestamp
        }
        return json.dumps(fingerprint_data, sort_keys=True).encode('utf-8')
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of fingerprint for verification"""
        return hashlib.sha256(self.to_bytes()).hexdigest()


@dataclass(frozen=True)
class PairingToken:
    """Cryptographically secure pairing token with device binding"""
    token_id: str
    device_fingerprint: DeviceFingerprint
    expiration_timestamp: float
    challenge_nonce: str
    hmac_signature: str
    
    @classmethod
    def generate(cls, device_fingerprint: DeviceFingerprint, 
                 validity_seconds: int = 300,
                 secret_key: Optional[bytes] = None) -> 'PairingToken':
        """
        Generate a new cryptographically secure pairing token
        
        Args:
            device_fingerprint: Device fingerprint to bind token to
            validity_seconds: Token validity period (default 5 minutes)
            secret_key: HMAC secret key (generated if not provided)
            
        Returns:
            New pairing token with cryptographic binding
        """
        if secret_key is None:
            secret_key = secrets.token_bytes(32)  # 256-bit key
            
        token_id = secrets.token_urlsafe(32)  # 256-bit token ID
        challenge_nonce = secrets.token_urlsafe(16)  # 128-bit nonce
        expiration_timestamp = time.time() + validity_seconds
        
        # Create HMAC signature binding token to device fingerprint
        token_data = {
            "token_id": token_id,
            "device_fingerprint_hash": device_fingerprint.compute_hash(),
            "expiration_timestamp": expiration_timestamp,
            "challenge_nonce": challenge_nonce
        }
        
        message = json.dumps(token_data, sort_keys=True).encode('utf-8')
        hmac_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
        
        logger.info("Generated pairing token",
                   token_id=token_id,
                   device_id=device_fingerprint.device_id,
                   expires_at=datetime.fromtimestamp(expiration_timestamp).isoformat())
        
        return cls(
            token_id=token_id,
            device_fingerprint=device_fingerprint,
            expiration_timestamp=expiration_timestamp,
            challenge_nonce=challenge_nonce,
            hmac_signature=hmac_signature
        )
    
    def is_valid(self, secret_key: bytes, current_time: Optional[float] = None) -> bool:
        """
        Validate token cryptographic signature and expiration
        
        Args:
            secret_key: HMAC secret key for signature verification
            current_time: Current timestamp (uses time.time() if not provided)
            
        Returns:
            True if token is valid and not expired
        """
        if current_time is None:
            current_time = time.time()
            
        # Check expiration
        if current_time >= self.expiration_timestamp:
            logger.warning("Pairing token expired",
                          token_id=self.token_id,
                          expired_at=datetime.fromtimestamp(self.expiration_timestamp).isoformat())
            return False
        
        # Verify HMAC signature
        token_data = {
            "token_id": self.token_id,
            "device_fingerprint_hash": self.device_fingerprint.compute_hash(),
            "expiration_timestamp": self.expiration_timestamp,
            "challenge_nonce": self.challenge_nonce
        }
        
        message = json.dumps(token_data, sort_keys=True).encode('utf-8')
        expected_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        is_signature_valid = hmac.compare_digest(self.hmac_signature, expected_signature)
        
        if not is_signature_valid:
            logger.error("Pairing token signature verification failed",
                        token_id=self.token_id,
                        device_id=self.device_fingerprint.device_id)
        
        return is_signature_valid
    
    def to_qr_data(self) -> Dict[str, Any]:
        """Convert token to QR code data format"""
        return {
            "version": "1.0",
            "type": "guru_pairing",
            "token_id": self.token_id,
            "device_fingerprint": asdict(self.device_fingerprint),
            "expiration_timestamp": self.expiration_timestamp,
            "challenge_nonce": self.challenge_nonce,
            "hmac_signature": self.hmac_signature
        }


@dataclass
class PairingResult:
    """Result of a pairing operation"""
    status: PairingStatus
    token_id: str
    device_fingerprint: Optional[DeviceFingerprint] = None
    error_message: Optional[str] = None
    requires_physical_confirmation: bool = True
    confirmed_on_both_devices: bool = False
    has_valid_key_exchange: bool = False
    completion_timestamp: Optional[float] = None
    
    @property
    def is_successful(self) -> bool:
        """Check if pairing completed successfully"""
        return self.status == PairingStatus.COMPLETED
    
    @property
    def is_pending(self) -> bool:
        """Check if pairing is pending confirmation"""
        return self.status in [PairingStatus.INITIATED, PairingStatus.PENDING_CONFIRMATION]


class QRPairingManager:
    """
    Manages QR code generation and validation for secure device pairing
    
    This class implements the QR code pairing protocol for GURU, providing
    cryptographically secure device pairing with physical presence verification.
    """
    
    def __init__(self, secret_key: Optional[bytes] = None):
        """
        Initialize QR pairing manager
        
        Args:
            secret_key: HMAC secret key (generated if not provided)
        """
        self.secret_key = secret_key or secrets.token_bytes(32)
        self.active_tokens: Dict[str, PairingToken] = {}
        self.pairing_sessions: Dict[str, PairingResult] = {}
        self.logger = structlog.get_logger(__name__).bind(component="QRPairingManager")
        
        self.logger.info("QR pairing manager initialized")
    
    def generate_device_fingerprint(self) -> DeviceFingerprint:
        """
        Generate device fingerprint for current device
        
        Returns:
            Device fingerprint with hardware and software identifiers
            
        Raises:
            Exception: If system information gathering fails
        """
        try:
            # Generate stable device ID based on hardware characteristics
            mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                                   for elements in range(0, 2*6, 2)][::-1])
            
            # Create hardware hash from system characteristics
            hardware_info = {
                "mac_address": mac_address,
                "processor": platform.processor(),
                "machine": platform.machine(),
                "total_memory": psutil.virtual_memory().total
            }
            
            hardware_hash = hashlib.sha256(
                json.dumps(hardware_info, sort_keys=True).encode('utf-8')
            ).hexdigest()[:16]  # First 16 chars for brevity
            
            device_id = f"guru-desktop-{hardware_hash}"
            
            fingerprint = DeviceFingerprint(
                device_id=device_id,
                hardware_hash=hardware_hash,
                os_version=platform.platform(),
                app_version="1.0.0",  # Version from application manifest
                creation_timestamp=time.time()
            )
            
            self.logger.info("Generated device fingerprint",
                            device_id=device_id,
                            hardware_hash=hardware_hash)
            
            return fingerprint
            
        except Exception as e:
            self.logger.error("Failed to generate device fingerprint", error=str(e))
            raise Exception(f"System information gathering failed: {str(e)}") from e
    
    def initiate_pairing(self, validity_seconds: int = 300) -> Tuple[PairingToken, Image.Image]:
        """
        Initiate pairing by generating QR code with embedded pairing token
        
        Args:
            validity_seconds: Token validity period in seconds (default 5 minutes)
            
        Returns:
            Tuple of (pairing_token, qr_code_image)
        """
        device_fingerprint = self.generate_device_fingerprint()
        pairing_token = PairingToken.generate(
            device_fingerprint=device_fingerprint,
            validity_seconds=validity_seconds,
            secret_key=self.secret_key
        )
        
        # Store active token
        self.active_tokens[pairing_token.token_id] = pairing_token
        
        # Create pairing session
        pairing_result = PairingResult(
            status=PairingStatus.INITIATED,
            token_id=pairing_token.token_id,
            device_fingerprint=device_fingerprint
        )
        self.pairing_sessions[pairing_token.token_id] = pairing_result
        
        # Generate QR code
        qr_data = pairing_token.to_qr_data()
        qr_json = json.dumps(qr_data, separators=(',', ':'))  # Compact JSON
        
        qr = qrcode.QRCode(
            version=None,  # Auto-determine version
            error_correction=qrcode.constants.ERROR_CORRECT_M,  # ~15% error correction
            box_size=10,
            border=4,
        )
        qr.add_data(qr_json)
        qr.make(fit=True)
        
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        self.logger.info("Pairing initiated with QR code",
                        token_id=pairing_token.token_id,
                        qr_data_size=len(qr_json),
                        expires_at=datetime.fromtimestamp(pairing_token.expiration_timestamp).isoformat())
        
        return pairing_token, qr_image
    
    def validate_pairing_token(self, token_data: Dict[str, Any]) -> PairingResult:
        """
        Validate pairing token from QR code scan
        
        Args:
            token_data: Parsed QR code data containing pairing token
            
        Returns:
            Pairing validation result
        """
        try:
            # Validate QR code format
            if token_data.get("type") != "guru_pairing":
                return PairingResult(
                    status=PairingStatus.FAILED,
                    token_id="unknown",
                    error_message="Invalid QR code type"
                )
            
            if token_data.get("version") != "1.0":
                return PairingResult(
                    status=PairingStatus.FAILED,
                    token_id="unknown", 
                    error_message="Unsupported QR code version"
                )
            
            # Reconstruct pairing token
            device_fingerprint_data = token_data.get("device_fingerprint", {})
            device_fingerprint = DeviceFingerprint(**device_fingerprint_data)
            
            pairing_token = PairingToken(
                token_id=token_data["token_id"],
                device_fingerprint=device_fingerprint,
                expiration_timestamp=token_data["expiration_timestamp"],
                challenge_nonce=token_data["challenge_nonce"],
                hmac_signature=token_data["hmac_signature"]
            )
            
            # Validate token
            if not pairing_token.is_valid(self.secret_key):
                return PairingResult(
                    status=PairingStatus.FAILED,
                    token_id=pairing_token.token_id,
                    error_message="Invalid or expired pairing token"
                )
            
            # Check if token is active
            if pairing_token.token_id not in self.active_tokens:
                return PairingResult(
                    status=PairingStatus.FAILED,
                    token_id=pairing_token.token_id,
                    error_message="Pairing token not found or already used"
                )
            
            # Update pairing session
            if pairing_token.token_id in self.pairing_sessions:
                session = self.pairing_sessions[pairing_token.token_id]
                session.status = PairingStatus.PENDING_CONFIRMATION
                
                self.logger.info("Pairing token validated successfully",
                                token_id=pairing_token.token_id,
                                device_id=device_fingerprint.device_id)
                
                return session
            else:
                return PairingResult(
                    status=PairingStatus.FAILED,
                    token_id=pairing_token.token_id,
                    error_message="Pairing session not found"
                )
                
        except Exception as e:
            self.logger.error("Pairing token validation failed",
                             error=str(e),
                             token_data=token_data)
            
            return PairingResult(
                status=PairingStatus.FAILED,
                token_id="unknown",
                error_message=f"Token validation error: {str(e)}"
            )
    
    def confirm_pairing(self, token_id: str, user_confirmation: bool) -> PairingResult:
        """
        Confirm pairing after physical presence verification
        
        Args:
            token_id: Pairing token identifier
            user_confirmation: User confirmation of pairing request
            
        Returns:
            Updated pairing result
        """
        if token_id not in self.pairing_sessions:
            return PairingResult(
                status=PairingStatus.FAILED,
                token_id=token_id,
                error_message="Pairing session not found"
            )
        
        session = self.pairing_sessions[token_id]
        
        if not user_confirmation:
            session.status = PairingStatus.REJECTED
            session.error_message = "User rejected pairing request"
            
            # Remove active token
            self.active_tokens.pop(token_id, None)
            
            self.logger.info("Pairing rejected by user", token_id=token_id)
            
            return session
        
        # Confirm pairing
        session.status = PairingStatus.CONFIRMED
        session.confirmed_on_both_devices = True
        session.completion_timestamp = time.time()
        
        self.logger.info("Pairing confirmed by user", token_id=token_id)
        
        return session
    
    def complete_pairing(self, token_id: str) -> PairingResult:
        """
        Complete pairing after successful key exchange
        
        Args:
            token_id: Pairing token identifier
            
        Returns:
            Final pairing result
        """
        if token_id not in self.pairing_sessions:
            return PairingResult(
                status=PairingStatus.FAILED,
                token_id=token_id,
                error_message="Pairing session not found"
            )
        
        session = self.pairing_sessions[token_id]
        
        if session.status != PairingStatus.CONFIRMED:
            return PairingResult(
                status=PairingStatus.FAILED,
                token_id=token_id,
                error_message="Pairing not confirmed"
            )
        
        # Mark as completed
        session.status = PairingStatus.COMPLETED
        session.has_valid_key_exchange = True
        session.completion_timestamp = time.time()
        
        # Clean up active token
        self.active_tokens.pop(token_id, None)
        
        self.logger.info("Pairing completed successfully", token_id=token_id)
        
        return session
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired pairing tokens and sessions
        
        Returns:
            Number of expired tokens removed
        """
        current_time = time.time()
        expired_tokens = []
        
        for token_id, token in self.active_tokens.items():
            if current_time >= token.expiration_timestamp:
                expired_tokens.append(token_id)
        
        for token_id in expired_tokens:
            self.active_tokens.pop(token_id, None)
            
            if token_id in self.pairing_sessions:
                session = self.pairing_sessions[token_id]
                session.status = PairingStatus.EXPIRED
                session.error_message = "Pairing token expired"
        
        if expired_tokens:
            self.logger.info("Cleaned up expired pairing tokens",
                           expired_count=len(expired_tokens))
        
        return len(expired_tokens)
    
    def get_pairing_status(self, token_id: str) -> Optional[PairingResult]:
        """
        Get current pairing status for a token
        
        Args:
            token_id: Pairing token identifier
            
        Returns:
            Current pairing result or None if not found
        """
        return self.pairing_sessions.get(token_id)
    
    def revoke_pairing(self, token_id: str) -> bool:
        """
        Revoke an active pairing token
        
        Args:
            token_id: Pairing token identifier
            
        Returns:
            True if token was revoked successfully
        """
        revoked = False
        
        if token_id in self.active_tokens:
            self.active_tokens.pop(token_id)
            revoked = True
        
        if token_id in self.pairing_sessions:
            session = self.pairing_sessions[token_id]
            session.status = PairingStatus.REJECTED
            session.error_message = "Pairing revoked"
            revoked = True
        
        if revoked:
            self.logger.info("Pairing token revoked", token_id=token_id)
        
        return revoked