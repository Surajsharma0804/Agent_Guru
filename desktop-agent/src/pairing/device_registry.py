"""
Device Registry for GURU Trusted Device Management

Manages trusted device identities, public keys, and pairing relationships.
Provides secure storage and retrieval of device credentials with audit logging.

Security Features:
- Encrypted storage of device credentials
- Device fingerprint verification
- Pairing relationship management
- Audit logging of all device operations
- Instant revocation capabilities

All device data is stored locally with user-controlled encryption keys.
"""

import json
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import hashlib

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import structlog

logger = structlog.get_logger(__name__)


class DeviceStatus(Enum):
    """Device trust status"""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class DeviceIdentity:
    """Trusted device identity with cryptographic binding"""
    device_id: str
    device_name: str
    device_type: str  # "desktop", "phone", "tablet"
    public_key_pem: str
    key_fingerprint: str
    hardware_fingerprint: str
    pairing_timestamp: float
    last_seen_timestamp: float
    status: DeviceStatus = DeviceStatus.ACTIVE
    
    def __post_init__(self):
        """Validate field types and values"""
        # Validate string fields
        string_fields = ['device_id', 'device_name', 'device_type', 
                        'public_key_pem', 'key_fingerprint', 'hardware_fingerprint']
        for field_name in string_fields:
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
        
        # Validate float fields
        float_fields = ['pairing_timestamp', 'last_seen_timestamp']
        for field_name in float_fields:
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be a number, got {type(value).__name__}")
        
        # Validate status field
        if not isinstance(self.status, DeviceStatus):
            raise TypeError(f"status must be a DeviceStatus enum, got {type(self.status).__name__}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceIdentity':
        """Create from dictionary"""
        data['status'] = DeviceStatus(data['status'])
        return cls(**data)
    
    @property
    def is_active(self) -> bool:
        """Check if device is currently active"""
        return self.status == DeviceStatus.ACTIVE
    
    @property
    def age_days(self) -> float:
        """Get device age in days since pairing"""
        return (time.time() - self.pairing_timestamp) / 86400


@dataclass
class TrustedDevice:
    """Trusted device with operational metadata"""
    identity: DeviceIdentity
    shared_secret_hash: str
    permissions: List[str]
    rate_limits: Dict[str, int]
    last_command_timestamp: Optional[float] = None
    command_count_today: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'identity': self.identity.to_dict(),
            'shared_secret_hash': self.shared_secret_hash,
            'permissions': self.permissions,
            'rate_limits': self.rate_limits,
            'last_command_timestamp': self.last_command_timestamp,
            'command_count_today': self.command_count_today
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrustedDevice':
        """Create from dictionary"""
        return cls(
            identity=DeviceIdentity.from_dict(data['identity']),
            shared_secret_hash=data['shared_secret_hash'],
            permissions=data['permissions'],
            rate_limits=data['rate_limits'],
            last_command_timestamp=data.get('last_command_timestamp'),
            command_count_today=data.get('command_count_today', 0)
        )
    
    def update_last_seen(self) -> None:
        """Update last seen timestamp"""
        current_time = time.time()
        
        # Reset daily counter if it's a new day
        if (self.last_command_timestamp and 
            datetime.fromtimestamp(current_time).date() != 
            datetime.fromtimestamp(self.last_command_timestamp).date()):
            self.command_count_today = 0
        
        self.last_command_timestamp = current_time
        self.command_count_today += 1
    
    def check_rate_limit(self, operation: str) -> bool:
        """
        Check if operation is within rate limits
        
        Args:
            operation: Operation type to check
            
        Returns:
            True if operation is allowed
        """
        if operation not in self.rate_limits:
            return True  # No limit set
        
        limit = self.rate_limits[operation]
        
        # Negative limits are treated as no limit
        if limit < 0:
            return True
        
        return self.command_count_today < limit


class DeviceRegistry:
    """
    Manages trusted device registry with encrypted storage
    
    Provides secure storage and management of trusted device identities,
    public keys, and pairing relationships with comprehensive audit logging.
    """
    
    def __init__(self, storage_path: str, encryption_key: Optional[bytes] = None):
        """
        Initialize device registry
        
        Args:
            storage_path: Path to SQLite database file
            encryption_key: Encryption key for sensitive data (generated if not provided)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        if encryption_key is None:
            encryption_key = Fernet.generate_key()
        self.cipher = Fernet(encryption_key)
        
        self.logger = structlog.get_logger(__name__).bind(component="DeviceRegistry")
        
        # Initialize database with error handling
        try:
            self._init_database()
            self.logger.info("Device registry initialized", storage_path=str(self.storage_path))
        except Exception as e:
            self.logger.error("Failed to initialize device registry", 
                            storage_path=str(self.storage_path), 
                            error=str(e))
            # Don't raise the exception - allow the registry to be created but mark it as failed
            self._initialization_failed = True
    
    def _init_database(self) -> None:
        """Initialize SQLite database schema"""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trusted_devices (
                    device_id TEXT PRIMARY KEY,
                    encrypted_data BLOB NOT NULL,
                    key_fingerprint TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pairing_timestamp REAL NOT NULL,
                    last_seen_timestamp REAL NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    details TEXT,
                    timestamp REAL NOT NULL,
                    success BOOLEAN NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_device_status 
                ON trusted_devices(status)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON device_audit_log(timestamp)
            """)
            
            conn.commit()
    
    def register_device(self, device_identity: DeviceIdentity, 
                       shared_secret_hash: str,
                       permissions: Optional[List[str]] = None,
                       rate_limits: Optional[Dict[str, int]] = None) -> bool:
        """
        Register new trusted device
        
        Args:
            device_identity: Device identity information
            shared_secret_hash: Hash of shared secret from key exchange
            permissions: List of granted permissions
            rate_limits: Rate limits for operations
            
        Returns:
            True if device was registered successfully
        """
        # Check if initialization failed
        if hasattr(self, '_initialization_failed') and self._initialization_failed:
            self.logger.error("Cannot register device - registry initialization failed")
            return False
        
        if permissions is None:
            permissions = ["basic_commands", "input_simulation"]
        
        if rate_limits is None:
            rate_limits = {
                "commands_per_day": 1000,
                "input_events_per_minute": 60
            }
        
        trusted_device = TrustedDevice(
            identity=device_identity,
            shared_secret_hash=shared_secret_hash,
            permissions=permissions,
            rate_limits=rate_limits
        )
        
        try:
            # Encrypt device data
            device_data = json.dumps(trusted_device.to_dict()).encode('utf-8')
            encrypted_data = self.cipher.encrypt(device_data)
            
            current_time = time.time()
            
            with sqlite3.connect(self.storage_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trusted_devices 
                    (device_id, encrypted_data, key_fingerprint, device_type, 
                     status, pairing_timestamp, last_seen_timestamp, 
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device_identity.device_id,
                    encrypted_data,
                    device_identity.key_fingerprint,
                    device_identity.device_type,
                    device_identity.status.value,
                    device_identity.pairing_timestamp,
                    device_identity.last_seen_timestamp,
                    current_time,
                    current_time
                ))
                
                # Log registration
                self._log_device_operation(
                    conn, device_identity.device_id, "register", 
                    f"Device registered with fingerprint {device_identity.key_fingerprint}",
                    True
                )
                
                conn.commit()
            
            self.logger.info("Device registered successfully",
                           device_id=device_identity.device_id,
                           device_type=device_identity.device_type,
                           key_fingerprint=device_identity.key_fingerprint)
            
            return True
            
        except Exception as e:
            self.logger.error("Device registration failed",
                            device_id=device_identity.device_id,
                            error=str(e))
            
            # Log failed registration
            with sqlite3.connect(self.storage_path) as conn:
                self._log_device_operation(
                    conn, device_identity.device_id, "register",
                    f"Registration failed: {str(e)}", False
                )
                conn.commit()
            
            return False
    
    def get_trusted_device(self, device_id: str) -> Optional[TrustedDevice]:
        """
        Get trusted device by ID
        
        Args:
            device_id: Device identifier
            
        Returns:
            Trusted device or None if not found
        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.execute("""
                    SELECT encrypted_data FROM trusted_devices 
                    WHERE device_id = ? AND status = ?
                """, (device_id, DeviceStatus.ACTIVE.value))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Decrypt device data
                encrypted_data = row[0]
                device_data = self.cipher.decrypt(encrypted_data)
                device_dict = json.loads(device_data.decode('utf-8'))
                
                return TrustedDevice.from_dict(device_dict)
                
        except Exception as e:
            self.logger.error("Failed to retrieve trusted device",
                            device_id=device_id,
                            error=str(e))
            return None
    
    def update_device_last_seen(self, device_id: str) -> bool:
        """
        Update device last seen timestamp
        
        Args:
            device_id: Device identifier
            
        Returns:
            True if update was successful
        """
        trusted_device = self.get_trusted_device(device_id)
        if not trusted_device:
            return False
        
        try:
            # Update last seen
            trusted_device.update_last_seen()
            
            # Re-encrypt and store
            device_data = json.dumps(trusted_device.to_dict()).encode('utf-8')
            encrypted_data = self.cipher.encrypt(device_data)
            
            with sqlite3.connect(self.storage_path) as conn:
                conn.execute("""
                    UPDATE trusted_devices 
                    SET encrypted_data = ?, last_seen_timestamp = ?, updated_at = ?
                    WHERE device_id = ?
                """, (
                    encrypted_data,
                    trusted_device.last_command_timestamp,
                    time.time(),
                    device_id
                ))
                
                conn.commit()
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to update device last seen",
                            device_id=device_id,
                            error=str(e))
            return False
    
    def revoke_device(self, device_id: str, reason: str = "User revoked") -> bool:
        """
        Revoke trust for a device
        
        Args:
            device_id: Device identifier
            reason: Revocation reason
            
        Returns:
            True if device was revoked successfully
        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                # Update device status
                cursor = conn.execute("""
                    UPDATE trusted_devices 
                    SET status = ?, updated_at = ?
                    WHERE device_id = ? AND status = ?
                """, (
                    DeviceStatus.REVOKED.value,
                    time.time(),
                    device_id,
                    DeviceStatus.ACTIVE.value
                ))
                
                if cursor.rowcount == 0:
                    return False  # Device not found or already revoked
                
                # Log revocation
                self._log_device_operation(
                    conn, device_id, "revoke", reason, True
                )
                
                conn.commit()
            
            self.logger.info("Device revoked successfully",
                           device_id=device_id,
                           reason=reason)
            
            return True
            
        except Exception as e:
            self.logger.error("Device revocation failed",
                            device_id=device_id,
                            error=str(e))
            return False
    
    def list_trusted_devices(self, include_revoked: bool = False) -> List[DeviceIdentity]:
        """
        List all trusted devices
        
        Args:
            include_revoked: Include revoked devices in results
            
        Returns:
            List of device identities
        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                if include_revoked:
                    cursor = conn.execute("""
                        SELECT encrypted_data FROM trusted_devices 
                        ORDER BY pairing_timestamp DESC
                    """)
                else:
                    cursor = conn.execute("""
                        SELECT encrypted_data FROM trusted_devices 
                        WHERE status = ?
                        ORDER BY pairing_timestamp DESC
                    """, (DeviceStatus.ACTIVE.value,))
                
                devices = []
                for row in cursor.fetchall():
                    try:
                        encrypted_data = row[0]
                        device_data = self.cipher.decrypt(encrypted_data)
                        device_dict = json.loads(device_data.decode('utf-8'))
                        trusted_device = TrustedDevice.from_dict(device_dict)
                        devices.append(trusted_device.identity)
                    except Exception as e:
                        self.logger.warning("Failed to decrypt device data", error=str(e))
                        continue
                
                return devices
                
        except Exception as e:
            self.logger.error("Failed to list trusted devices", error=str(e))
            return []
    
    def verify_device_fingerprint(self, device_id: str, 
                                 expected_fingerprint: str) -> bool:
        """
        Verify device key fingerprint
        
        Args:
            device_id: Device identifier
            expected_fingerprint: Expected key fingerprint
            
        Returns:
            True if fingerprint matches
        """
        trusted_device = self.get_trusted_device(device_id)
        if not trusted_device:
            return False
        
        return trusted_device.identity.key_fingerprint == expected_fingerprint
    
    def check_device_permissions(self, device_id: str, 
                               required_permission: str) -> bool:
        """
        Check if device has required permission
        
        Args:
            device_id: Device identifier
            required_permission: Permission to check
            
        Returns:
            True if device has permission
        """
        trusted_device = self.get_trusted_device(device_id)
        if not trusted_device:
            return False
        
        return required_permission in trusted_device.permissions
    
    def check_rate_limit(self, device_id: str, operation: str) -> bool:
        """
        Check if device operation is within rate limits
        
        Args:
            device_id: Device identifier
            operation: Operation type
            
        Returns:
            True if operation is allowed
        """
        trusted_device = self.get_trusted_device(device_id)
        if not trusted_device:
            return False
        
        return trusted_device.check_rate_limit(operation)
    
    def cleanup_expired_devices(self, max_age_days: int = 365) -> int:
        """
        Clean up old device entries
        
        Args:
            max_age_days: Maximum age for device entries (default 1 year)
            
        Returns:
            Number of devices cleaned up
        """
        cutoff_timestamp = time.time() - (max_age_days * 86400)
        
        try:
            with sqlite3.connect(self.storage_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM trusted_devices 
                    WHERE status = ? AND last_seen_timestamp < ?
                """, (DeviceStatus.REVOKED.value, cutoff_timestamp))
                
                deleted_count = cursor.rowcount
                
                # Clean up old audit logs
                audit_cutoff = time.time() - (90 * 86400)  # 90 days
                conn.execute("""
                    DELETE FROM device_audit_log 
                    WHERE timestamp < ?
                """, (audit_cutoff,))
                
                conn.commit()
            
            if deleted_count > 0:
                self.logger.info("Cleaned up expired devices",
                               deleted_count=deleted_count)
            
            return deleted_count
            
        except Exception as e:
            self.logger.error("Device cleanup failed", error=str(e))
            return 0
    
    def _log_device_operation(self, conn: sqlite3.Connection, 
                            device_id: str, operation: str, 
                            details: str, success: bool) -> None:
        """Log device operation to audit trail"""
        conn.execute("""
            INSERT INTO device_audit_log 
            (device_id, operation, details, timestamp, success)
            VALUES (?, ?, ?, ?, ?)
        """, (device_id, operation, details, time.time(), success))
    
    def get_device_audit_log(self, device_id: Optional[str] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get device audit log entries
        
        Args:
            device_id: Filter by device ID (all devices if None)
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        try:
            with sqlite3.connect(self.storage_path) as conn:
                if device_id:
                    cursor = conn.execute("""
                        SELECT device_id, operation, details, timestamp, success
                        FROM device_audit_log 
                        WHERE device_id = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (device_id, limit))
                else:
                    cursor = conn.execute("""
                        SELECT device_id, operation, details, timestamp, success
                        FROM device_audit_log 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (limit,))
                
                entries = []
                for row in cursor.fetchall():
                    entries.append({
                        'device_id': row[0],
                        'operation': row[1],
                        'details': row[2],
                        'timestamp': row[3],
                        'datetime': datetime.fromtimestamp(row[3]).isoformat(),
                        'success': bool(row[4])
                    })
                
                return entries
                
        except Exception as e:
            self.logger.error("Failed to retrieve audit log", error=str(e))
            return []