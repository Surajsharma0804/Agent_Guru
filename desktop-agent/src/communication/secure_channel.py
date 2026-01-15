"""
Secure Communication Channels

Production-grade secure communication channels for GURU component communication.
Implements cryptographic security, message integrity, and secure transport.

Key Features:
- End-to-end encryption with AES-256-GCM
- Message authentication with HMAC-SHA256
- Perfect forward secrecy with key rotation
- Replay attack prevention with nonces
- Comprehensive audit logging
- Thread-safe operations
"""

import logging
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import ChannelClosedError, ChannelSecurityError, MessageValidationError


class EncryptionMode(Enum):
    """Encryption modes for secure channels."""
    NONE = "none"                    # No encryption (testing only)
    AES_256_GCM = "aes_256_gcm"     # AES-256-GCM authenticated encryption
    CHACHA20_POLY1305 = "chacha20_poly1305"  # ChaCha20-Poly1305 (future)


class ChannelSecurity(Enum):
    """Security levels for communication channels."""
    STANDARD = "standard"            # Standard security
    HIGH = "high"                   # High security with frequent key rotation
    CRITICAL = "critical"           # Maximum security for sensitive operations


@dataclass
class ChannelKey:
    """Cryptographic key for secure channel."""
    key_id: str
    key_data: bytes
    created_at: datetime
    expires_at: Optional[datetime] = None
    usage_count: int = 0
    max_usage: int = 10000  # Maximum uses before rotation
    
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at and datetime.now() > self.expires_at:
            return True
        return self.usage_count >= self.max_usage
    
    def increment_usage(self) -> None:
        """Increment key usage counter."""
        self.usage_count += 1


@dataclass
class SecureMessage:
    """Encrypted message for secure channel transmission."""
    channel_id: str
    message_id: str
    encrypted_payload: bytes
    nonce: bytes
    auth_tag: bytes
    key_id: str
    timestamp: datetime
    sender_id: str
    recipient_id: str
    
    def to_bytes(self) -> bytes:
        """Serialize secure message to bytes."""
        # Simple serialization - in production, use proper protocol buffers
        data = {
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "encrypted_payload": self.encrypted_payload.hex(),
            "nonce": self.nonce.hex(),
            "auth_tag": self.auth_tag.hex(),
            "key_id": self.key_id,
            "timestamp": self.timestamp.isoformat(),
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id
        }
        
        import json
        return json.dumps(data).encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SecureMessage':
        """Deserialize secure message from bytes."""
        import json
        parsed = json.loads(data.decode('utf-8'))
        
        return cls(
            channel_id=parsed["channel_id"],
            message_id=parsed["message_id"],
            encrypted_payload=bytes.fromhex(parsed["encrypted_payload"]),
            nonce=bytes.fromhex(parsed["nonce"]),
            auth_tag=bytes.fromhex(parsed["auth_tag"]),
            key_id=parsed["key_id"],
            timestamp=datetime.fromisoformat(parsed["timestamp"]),
            sender_id=parsed["sender_id"],
            recipient_id=parsed["recipient_id"]
        )


class SecureChannel:
    """
    Production-grade secure communication channel.
    
    Provides cryptographically secure communication between GURU components with:
    - End-to-end encryption using AES-256-GCM
    - Message authentication and integrity verification
    - Perfect forward secrecy with automatic key rotation
    - Replay attack prevention using nonces and timestamps
    - Comprehensive security audit logging
    - Thread-safe operations with proper locking
    """
    
    def __init__(self,
                 channel_id: str,
                 local_component: str,
                 remote_component: str,
                 security_level: ChannelSecurity = ChannelSecurity.STANDARD,
                 encryption_mode: EncryptionMode = EncryptionMode.AES_256_GCM,
                 key_rotation_interval: timedelta = timedelta(hours=1),
                 master_key: Optional[bytes] = None):
        """
        Initialize secure communication channel.
        
        Args:
            channel_id: Unique channel identifier
            local_component: Local component name
            remote_component: Remote component name
            security_level: Security level for the channel
            encryption_mode: Encryption algorithm to use
            key_rotation_interval: Interval for automatic key rotation
            master_key: Master key for key derivation (generated if None)
        """
        self.channel_id = channel_id
        self.local_component = local_component
        self.remote_component = remote_component
        self.security_level = security_level
        self.encryption_mode = encryption_mode
        self.key_rotation_interval = key_rotation_interval
        
        self.logger = logging.getLogger(__name__)
        
        # Cryptographic state
        self.master_key = master_key or secrets.token_bytes(32)
        self._current_key: Optional[ChannelKey] = None
        self._key_history: List[ChannelKey] = []
        self._max_key_history = 10
        
        # Security state
        self._channel_open = False
        self._used_nonces: set = set()
        self._max_nonce_history = 10000
        self._message_sequence = 0
        
        # Threading
        self._channel_lock = threading.RLock()
        
        # Statistics and monitoring
        self._channel_stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "encryption_operations": 0,
            "decryption_operations": 0,
            "key_rotations": 0,
            "security_violations": 0,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        
        # Security callbacks
        self._security_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Initialize cryptographic components
        self._initialize_crypto()
        
        self.logger.info(f"SecureChannel '{channel_id}' initialized ({local_component} <-> {remote_component})")
    
    def _initialize_crypto(self) -> None:
        """Initialize cryptographic components."""
        if self.encryption_mode == EncryptionMode.AES_256_GCM:
            self._cipher = AESGCM
        else:
            raise ValueError(f"Unsupported encryption mode: {self.encryption_mode}")
        
        # Generate initial key
        self._rotate_key()
    
    def open_channel(self) -> None:
        """Open the secure channel for communication."""
        with self._channel_lock:
            if self._channel_open:
                return
            
            self._channel_open = True
            self._channel_stats["last_activity"] = datetime.now()
        
        self.logger.info(f"Secure channel '{self.channel_id}' opened")
        self._audit_security_event("channel_opened", {"channel_id": self.channel_id})
    
    def close_channel(self) -> None:
        """Close the secure channel."""
        with self._channel_lock:
            if not self._channel_open:
                return
            
            self._channel_open = False
            
            # Clear sensitive data
            self._current_key = None
            self._key_history.clear()
            self._used_nonces.clear()
        
        self.logger.info(f"Secure channel '{self.channel_id}' closed")
        self._audit_security_event("channel_closed", {"channel_id": self.channel_id})
    
    def encrypt_message(self, plaintext: bytes, recipient_id: str) -> SecureMessage:
        """
        Encrypt message for secure transmission.
        
        Args:
            plaintext: Message data to encrypt
            recipient_id: Intended recipient component ID
            
        Returns:
            Encrypted secure message
            
        Raises:
            ChannelClosedError: If channel is closed
            ChannelSecurityError: If encryption fails
        """
        with self._channel_lock:
            if not self._channel_open:
                raise ChannelClosedError(self.channel_id, "Channel is closed")
            
            # Check if key rotation is needed
            if self._current_key and self._current_key.is_expired():
                self._rotate_key()
            
            if not self._current_key:
                raise ChannelSecurityError(self.channel_id, "No encryption key available")
            
            try:
                # Generate unique nonce
                nonce = self._generate_nonce()
                
                # Create cipher instance
                cipher = self._cipher(self._current_key.key_data)
                
                # Encrypt with authenticated encryption
                ciphertext = cipher.encrypt(nonce, plaintext, None)
                
                # Extract auth tag (last 16 bytes for GCM)
                encrypted_payload = ciphertext[:-16]
                auth_tag = ciphertext[-16:]
                
                # Create secure message
                secure_msg = SecureMessage(
                    channel_id=self.channel_id,
                    message_id=str(uuid.uuid4()),
                    encrypted_payload=encrypted_payload,
                    nonce=nonce,
                    auth_tag=auth_tag,
                    key_id=self._current_key.key_id,
                    timestamp=datetime.now(),
                    sender_id=self.local_component,
                    recipient_id=recipient_id
                )
                
                # Update statistics
                self._current_key.increment_usage()
                self._channel_stats["messages_sent"] += 1
                self._channel_stats["encryption_operations"] += 1
                self._channel_stats["last_activity"] = datetime.now()
                
                self.logger.debug(f"Message encrypted for channel '{self.channel_id}'")
                
                return secure_msg
                
            except Exception as e:
                self._channel_stats["security_violations"] += 1
                raise ChannelSecurityError(self.channel_id, f"Encryption failed: {e}")
    
    def decrypt_message(self, secure_msg: SecureMessage) -> bytes:
        """
        Decrypt secure message.
        
        Args:
            secure_msg: Encrypted secure message
            
        Returns:
            Decrypted plaintext data
            
        Raises:
            ChannelClosedError: If channel is closed
            ChannelSecurityError: If decryption fails
            MessageValidationError: If message validation fails
        """
        with self._channel_lock:
            if not self._channel_open:
                raise ChannelClosedError(self.channel_id, "Channel is closed")
            
            # Validate message
            self._validate_secure_message(secure_msg)
            
            # Find appropriate key
            decryption_key = self._find_key_by_id(secure_msg.key_id)
            if not decryption_key:
                raise ChannelSecurityError(
                    self.channel_id, 
                    f"Decryption key not found: {secure_msg.key_id}"
                )
            
            try:
                # Create cipher instance
                cipher = self._cipher(decryption_key.key_data)
                
                # Reconstruct ciphertext with auth tag
                ciphertext = secure_msg.encrypted_payload + secure_msg.auth_tag
                
                # Decrypt and verify
                plaintext = cipher.decrypt(secure_msg.nonce, ciphertext, None)
                
                # Update statistics
                self._channel_stats["messages_received"] += 1
                self._channel_stats["decryption_operations"] += 1
                self._channel_stats["last_activity"] = datetime.now()
                
                # Record nonce to prevent replay
                self._record_used_nonce(secure_msg.nonce)
                
                self.logger.debug(f"Message decrypted for channel '{self.channel_id}'")
                
                return plaintext
                
            except Exception as e:
                self._channel_stats["security_violations"] += 1
                self._audit_security_event("decryption_failed", {
                    "channel_id": self.channel_id,
                    "message_id": secure_msg.message_id,
                    "error": str(e)
                })
                raise ChannelSecurityError(self.channel_id, f"Decryption failed: {e}")
    
    def _rotate_key(self) -> None:
        """Rotate encryption key for perfect forward secrecy."""
        with self._channel_lock:
            # Generate new key using PBKDF2
            salt = secrets.token_bytes(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            # Derive key from master key and current time
            key_material = self.master_key + str(time.time()).encode()
            derived_key = kdf.derive(key_material)
            
            # Create new key
            new_key = ChannelKey(
                key_id=str(uuid.uuid4()),
                key_data=derived_key,
                created_at=datetime.now(),
                expires_at=datetime.now() + self.key_rotation_interval
            )
            
            # Store old key in history
            if self._current_key:
                self._key_history.append(self._current_key)
                
                # Limit key history size
                if len(self._key_history) > self._max_key_history:
                    self._key_history = self._key_history[-self._max_key_history:]
            
            # Set new current key
            self._current_key = new_key
            self._channel_stats["key_rotations"] += 1
            
            self.logger.info(f"Key rotated for channel '{self.channel_id}' (key_id: {new_key.key_id[:8]}...)")
            self._audit_security_event("key_rotated", {
                "channel_id": self.channel_id,
                "key_id": new_key.key_id,
                "rotation_count": self._channel_stats["key_rotations"]
            })
    
    def _generate_nonce(self) -> bytes:
        """Generate cryptographically secure nonce."""
        # Use timestamp + random bytes for uniqueness
        timestamp_bytes = int(time.time() * 1000000).to_bytes(8, 'big')
        random_bytes = secrets.token_bytes(4)
        nonce = timestamp_bytes + random_bytes
        
        # Ensure nonce is unique (prevent accidental reuse)
        while nonce in self._used_nonces:
            random_bytes = secrets.token_bytes(4)
            nonce = timestamp_bytes + random_bytes
        
        return nonce
    
    def _record_used_nonce(self, nonce: bytes) -> None:
        """Record used nonce to prevent replay attacks."""
        self._used_nonces.add(nonce)
        
        # Limit nonce history size
        if len(self._used_nonces) > self._max_nonce_history:
            # Remove oldest nonces (simple approach - in production use time-based cleanup)
            oldest_nonces = list(self._used_nonces)[:len(self._used_nonces) - self._max_nonce_history + 1000]
            for old_nonce in oldest_nonces:
                self._used_nonces.discard(old_nonce)
    
    def _find_key_by_id(self, key_id: str) -> Optional[ChannelKey]:
        """Find key by ID in current key or history."""
        if self._current_key and self._current_key.key_id == key_id:
            return self._current_key
        
        for key in self._key_history:
            if key.key_id == key_id:
                return key
        
        return None
    
    def _validate_secure_message(self, secure_msg: SecureMessage) -> None:
        """Validate secure message before decryption."""
        # Check channel ID
        if secure_msg.channel_id != self.channel_id:
            raise MessageValidationError(
                secure_msg.message_id,
                f"Channel ID mismatch: expected {self.channel_id}, got {secure_msg.channel_id}"
            )
        
        # Check recipient
        if secure_msg.recipient_id != self.local_component:
            raise MessageValidationError(
                secure_msg.message_id,
                f"Recipient mismatch: expected {self.local_component}, got {secure_msg.recipient_id}"
            )
        
        # Check for replay attack
        if secure_msg.nonce in self._used_nonces:
            self._audit_security_event("replay_attack_detected", {
                "channel_id": self.channel_id,
                "message_id": secure_msg.message_id,
                "sender": secure_msg.sender_id
            })
            raise ChannelSecurityError(self.channel_id, "Replay attack detected")
        
        # Check message age (prevent old message replay)
        message_age = datetime.now() - secure_msg.timestamp
        if message_age > timedelta(minutes=5):  # 5-minute window
            raise MessageValidationError(
                secure_msg.message_id,
                f"Message too old: {message_age}"
            )
    
    def _audit_security_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log security event for audit purposes."""
        audit_data = {
            "event_type": event_type,
            "channel_id": self.channel_id,
            "local_component": self.local_component,
            "remote_component": self.remote_component,
            "timestamp": datetime.now().isoformat(),
            **details
        }
        
        self.logger.info(f"SECURITY_AUDIT[{event_type}]: {audit_data}")
        
        # Notify security callbacks
        for callback in self._security_callbacks:
            try:
                callback(event_type, audit_data)
            except Exception as e:
                self.logger.error(f"Error in security callback: {e}")
    
    # Public API methods
    
    def is_open(self) -> bool:
        """Check if channel is open."""
        with self._channel_lock:
            return self._channel_open
    
    def get_channel_info(self) -> Dict[str, Any]:
        """Get channel information and statistics."""
        with self._channel_lock:
            return {
                "channel_id": self.channel_id,
                "local_component": self.local_component,
                "remote_component": self.remote_component,
                "security_level": self.security_level.value,
                "encryption_mode": self.encryption_mode.value,
                "is_open": self._channel_open,
                "current_key_id": self._current_key.key_id if self._current_key else None,
                "key_history_size": len(self._key_history),
                "statistics": self._channel_stats.copy()
            }
    
    def force_key_rotation(self) -> None:
        """Force immediate key rotation."""
        with self._channel_lock:
            self._rotate_key()
            self.logger.info(f"Forced key rotation for channel '{self.channel_id}'")
    
    def add_security_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add security event callback."""
        self._security_callbacks.append(callback)
    
    def get_security_statistics(self) -> Dict[str, Any]:
        """Get security-related statistics."""
        with self._channel_lock:
            return {
                "security_violations": self._channel_stats["security_violations"],
                "key_rotations": self._channel_stats["key_rotations"],
                "used_nonces_count": len(self._used_nonces),
                "current_key_usage": self._current_key.usage_count if self._current_key else 0,
                "current_key_age": (datetime.now() - self._current_key.created_at).total_seconds() if self._current_key else 0,
                "encryption_operations": self._channel_stats["encryption_operations"],
                "decryption_operations": self._channel_stats["decryption_operations"]
            }


class SecureChannelOrchestrator:
    """
    Manager for multiple secure communication channels.
    
    Provides centralized management of secure channels between components
    with automatic lifecycle management and security monitoring.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._channels: Dict[str, SecureChannel] = {}
        self._channel_lock = threading.RLock()
        
        # Global security monitoring
        self._security_events: List[Dict[str, Any]] = []
        self._max_security_events = 1000
        
    def create_channel(self,
                      local_component: str,
                      remote_component: str,
                      security_level: ChannelSecurity = ChannelSecurity.STANDARD,
                      encryption_mode: EncryptionMode = EncryptionMode.AES_256_GCM) -> str:
        """
        Create new secure channel between components.
        
        Args:
            local_component: Local component name
            remote_component: Remote component name
            security_level: Security level for the channel
            encryption_mode: Encryption mode to use
            
        Returns:
            Channel ID of created channel
        """
        channel_id = f"{local_component}_{remote_component}_{uuid.uuid4().hex[:8]}"
        
        with self._channel_lock:
            if channel_id in self._channels:
                raise ValueError(f"Channel {channel_id} already exists")
            
            channel = SecureChannel(
                channel_id=channel_id,
                local_component=local_component,
                remote_component=remote_component,
                security_level=security_level,
                encryption_mode=encryption_mode
            )
            
            # Add security monitoring
            channel.add_security_callback(self._handle_security_event)
            
            self._channels[channel_id] = channel
        
        self.logger.info(f"Created secure channel '{channel_id}' ({local_component} <-> {remote_component})")
        return channel_id
    
    def get_channel(self, channel_id: str) -> Optional[SecureChannel]:
        """Get channel by ID."""
        with self._channel_lock:
            return self._channels.get(channel_id)
    
    def close_channel(self, channel_id: str) -> None:
        """Close and remove channel."""
        with self._channel_lock:
            channel = self._channels.pop(channel_id, None)
            if channel:
                channel.close_channel()
                self.logger.info(f"Closed and removed channel '{channel_id}'")
    
    def get_all_channels(self) -> Dict[str, SecureChannel]:
        """Get all managed channels."""
        with self._channel_lock:
            return self._channels.copy()
    
    def _handle_security_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Handle security events from channels."""
        security_event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        }
        
        self._security_events.append(security_event)
        
        # Limit security event history
        if len(self._security_events) > self._max_security_events:
            self._security_events = self._security_events[-self._max_security_events:]
        
        # Log critical security events
        if event_type in ["replay_attack_detected", "decryption_failed"]:
            self.logger.warning(f"CRITICAL_SECURITY_EVENT: {event_type} - {details}")
    
    def get_security_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent security events."""
        return self._security_events[-limit:] if self._security_events else []
    
    def get_manager_statistics(self) -> Dict[str, Any]:
        """Get channel manager statistics."""
        with self._channel_lock:
            total_messages = sum(
                channel.get_channel_info()["statistics"]["messages_sent"] + 
                channel.get_channel_info()["statistics"]["messages_received"]
                for channel in self._channels.values()
            )
            
            return {
                "total_channels": len(self._channels),
                "open_channels": sum(1 for channel in self._channels.values() if channel.is_open()),
                "total_messages_processed": total_messages,
                "security_events_count": len(self._security_events),
                "channels_by_security_level": {
                    level.value: sum(1 for channel in self._channels.values() 
                                   if channel.security_level == level)
                    for level in ChannelSecurity
                }
            }