"""
Device Registry for GURU Pairing System

Manages trusted device identities, authentication keys, and pairing relationships.
Provides secure storage and retrieval of device information with encryption
and comprehensive audit logging.

Security Features:
- All device data encrypted at rest
- Cryptographic device fingerprint verification
- Comprehensive audit trail of all operations
- Rate limiting and access control
- Secure device revocation and cleanup
"""

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog
from cryptography.fernet import Fernet

logger = structlog.get_logger(__name__)


class DeviceStatus(Enum):
    """Device status in registry"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class DeviceIdentity:
    """Device identity information"""
    device_id: str
    device_name: str
    device_type: str  # "phone", "tablet", "desktop", etc.
    public_key_pem: str
    key_fingerprint: str
    hardware_fingerprint: str
    pairing_timestamp: float
    last_seen_timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceIdentity':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class TrustedDevice:
    """Trusted device record with metadata"""
    identity: DeviceIdentity
    status: DeviceStatus
    shared_secret_hash: str
    rate_limits: Dict[str, int]
    command_count_today: int
    last_command_timestamp: float
    trust_level: str  # "full", "limited", "restricted"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "identity": self.identity.to_dict(),
            "status": self.status.value,
            "shared_secret_hash": self.shared_secret_hash,
            "rate_limits": self.rate_limits,
            "command_count_today": self.command_count_today,
            "last_command_timestamp": self.last_command_timestamp,
            "trust_level": self.trust_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrustedDevice':
        """Create from dictionary"""
        return cls(
            identity=DeviceIdentity.from_dict(data["identity"]),
            status=DeviceStatus(data["status"]),
            shared_secret_hash=data["shared_secret_hash"],
            rate_limits=data["rate_limits"],
            command_count_today=data["command_count_today"],
            last_command_timestamp=data["last_command_timestamp"],
            trust_level=data["trust_level"]
        )


class DeviceRegistry:
    """
    Secure device registry for managing trusted device relationships
    
    Provides encrypted storage and retrieval of device identities,
    authentication keys, and pairing metadata with comprehensive
    audit logging and security controls.
    """
    
    def __init__(self, db_path: str, encryption_key: bytes):
        """
        Initialize device registry
        
        Args:
            db_path: Path to SQLite database file
            encryption_key: Fernet encryption key for data protection
        """
        self.db_path = db_path
        self.cipher = Fernet(encryption_key)
        self._lock = threading.RLock()
        
        self.logger = structlog.get_logger(__name__).bind(component="DeviceRegistry")
        
        # Initialize database
        self._init_database()
        
        self.logger.info("Device registry initialized", db_path=db_path)
    
    def _init_database(self) -> None:
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trusted_devices (
                    device_id TEXT PRIMARY KEY,
                    encrypted_data BLOB NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    details TEXT,
                    success BOOLEAN NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_device_id 
                ON device_audit_log(device_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON device_audit_log(timestamp)
            """)
            
            conn.commit()
    
    def _log_operation(self, device_id: str, operation: str, 
                      success: bool, details: Optional[str] = None) -> None:
        """Log operation to audit trail"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO device_audit_log 
                    (device_id, operation, timestamp, details, success)
                    VALUES (?, ?, ?, ?, ?)
                """, (device_id, operation, time.time(), details, success))
                conn.commit()
        except Exception as e:
            self.logger.error("Failed to log operation", 
                            device_id=device_id, 
                            operation=operation, 
                            error=str(e))
    
    def register_device(self, device_identity: DeviceIdentity, 
                       shared_secret: str,
                       rate_limits: Optional[Dict[str, int]] = None,
                       trust_level: str = "full") -> bool:
        """
        Register a new trusted device
        
        Args:
            device_identity: Device identity information
            shared_secret: Shared secret from pairing process
            rate_limits: Optional rate limits for device
            trust_level: Trust level ("full", "limited", "restricted")
            
        Returns:
            True if registration successful
        """
        with self._lock:
            try:
                # Check if device already exists
                existing = self.get_trusted_device(device_identity.device_id)
                if existing:
                    self.logger.warning("Device already registered", 
                                      device_id=device_identity.device_id)
                    self._log_operation(device_identity.device_id, "register", 
                                      False, "Device already exists")
                    return False
                
                # Create trusted device record
                shared_secret_hash = hashlib.sha256(shared_secret.encode()).hexdigest()
                
                trusted_device = TrustedDevice(
                    identity=device_identity,
                    status=DeviceStatus.ACTIVE,
                    shared_secret_hash=shared_secret_hash,
                    rate_limits=rate_limits or {"commands_per_day": 1000},
                    command_count_today=0,
                    last_command_timestamp=0.0,
                    trust_level=trust_level
                )
                
                # Encrypt device data
                device_data = json.dumps(trusted_device.to_dict()).encode('utf-8')
                encrypted_data = self.cipher.encrypt(device_data)
                
                # Store in database
                current_time = time.time()
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO trusted_devices 
                        (device_id, encrypted_data, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (device_identity.device_id, encrypted_data, 
                         current_time, current_time))
                    conn.commit()
                
                self._log_operation(device_identity.device_id, "register", 
                                  True, f"Trust level: {trust_level}")
                
                self.logger.info("Device registered successfully",
                               device_id=device_identity.device_id,
                               device_name=device_identity.device_name,
                               trust_level=trust_level)
                
                return True
                
            except Exception as e:
                self.logger.error("Failed to register device",
                                device_id=device_identity.device_id,
                                error=str(e))
                self._log_operation(device_identity.device_id, "register", 
                                  False, f"Error: {str(e)}")
                return False
    
    def get_trusted_device(self, device_id: str) -> Optional[TrustedDevice]:
        """
        Get trusted device by ID
        
        Args:
            device_id: Device identifier
            
        Returns:
            TrustedDevice or None if not found
        """
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT encrypted_data FROM trusted_devices 
                        WHERE device_id = ?
                    """, (device_id,))
                    
                    result = cursor.fetchone()
                    if not result:
                        return None
                    
                    # Decrypt device data
                    encrypted_data = result[0]
                    decrypted_data = self.cipher.decrypt(encrypted_data)
                    device_dict = json.loads(decrypted_data.decode('utf-8'))
                    
                    return TrustedDevice.from_dict(device_dict)
                    
            except Exception as e:
                self.logger.error("Failed to get trusted device",
                                device_id=device_id,
                                error=str(e))
                return None
    
    def update_device_last_seen(self, device_id: str) -> bool:
        """
        Update device last seen timestamp
        
        Args:
            device_id: Device identifier
            
        Returns:
            True if update successful
        """
        with self._lock:
            try:
                trusted_device = self.get_trusted_device(device_id)
                if not trusted_device:
                    return False
                
                # Update last seen timestamp
                trusted_device.identity = DeviceIdentity(
                    device_id=trusted_device.identity.device_id,
                    device_name=trusted_device.identity.device_name,
                    device_type=trusted_device.identity.device_type,
                    public_key_pem=trusted_device.identity.public_key_pem,
                    key_fingerprint=trusted_device.identity.key_fingerprint,
                    hardware_fingerprint=trusted_device.identity.hardware_fingerprint,
                    pairing_timestamp=trusted_device.identity.pairing_timestamp,
                    last_seen_timestamp=time.time()
                )
                
                # Encrypt and store updated data
                device_data = json.dumps(trusted_device.to_dict()).encode('utf-8')
                encrypted_data = self.cipher.encrypt(device_data)
                
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE trusted_devices 
                        SET encrypted_data = ?, updated_at = ?
                        WHERE device_id = ?
                    """, (encrypted_data, time.time(), device_id))
                    conn.commit()
                
                self._log_operation(device_id, "update_last_seen", True)
                return True
                
            except Exception as e:
                self.logger.error("Failed to update device last seen",
                                device_id=device_id,
                                error=str(e))
                self._log_operation(device_id, "update_last_seen", 
                                  False, f"Error: {str(e)}")
                return False
    
    def revoke_device(self, device_id: str, reason: str = "Manual revocation") -> bool:
        """
        Revoke trust for a device
        
        Args:
            device_id: Device identifier
            reason: Reason for revocation
            
        Returns:
            True if revocation successful
        """
        with self._lock:
            try:
                trusted_device = self.get_trusted_device(device_id)
                if not trusted_device:
                    return False
                
                # Update device status to revoked
                trusted_device.status = DeviceStatus.REVOKED
                
                # Encrypt and store updated data
                device_data = json.dumps(trusted_device.to_dict()).encode('utf-8')
                encrypted_data = self.cipher.encrypt(device_data)
                
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE trusted_devices 
                        SET encrypted_data = ?, updated_at = ?
                        WHERE device_id = ?
                    """, (encrypted_data, time.time(), device_id))
                    conn.commit()
                
                self._log_operation(device_id, "revoke", True, reason)
                
                self.logger.info("Device revoked",
                               device_id=device_id,
                               reason=reason)
                
                return True
                
            except Exception as e:
                self.logger.error("Failed to revoke device",
                                device_id=device_id,
                                error=str(e))
                self._log_operation(device_id, "revoke", 
                                  False, f"Error: {str(e)}")
                return False
    
    def verify_device_fingerprint(self, device_id: str, 
                                fingerprint: str) -> bool:
        """
        Verify device hardware fingerprint
        
        Args:
            device_id: Device identifier
            fingerprint: Hardware fingerprint to verify
            
        Returns:
            True if fingerprint matches
        """
        trusted_device = self.get_trusted_device(device_id)
        if not trusted_device:
            return False
        
        return trusted_device.identity.hardware_fingerprint == fingerprint
    
    def check_rate_limit(self, device_id: str, limit_type: str) -> bool:
        """
        Check if device is within rate limits
        
        Args:
            device_id: Device identifier
            limit_type: Type of rate limit to check
            
        Returns:
            True if within limits, False if exceeded
        """
        trusted_device = self.get_trusted_device(device_id)
        if not trusted_device:
            return False
        
        if limit_type not in trusted_device.rate_limits:
            return True  # No limit set
        
        limit = trusted_device.rate_limits[limit_type]
        
        if limit_type == "commands_per_day":
            # Check daily command limit
            current_date = datetime.now().date()
            last_command_date = datetime.fromtimestamp(
                trusted_device.last_command_timestamp
            ).date()
            
            if current_date != last_command_date:
                # Reset daily counter
                trusted_device.command_count_today = 0
            
            return trusted_device.command_count_today < limit
        
        # For other limit types, assume they're allowed
        return True
    
    def get_all_trusted_devices(self) -> List[TrustedDevice]:
        """
        Get all trusted devices
        
        Returns:
            List of all trusted devices
        """
        with self._lock:
            devices = []
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT device_id, encrypted_data FROM trusted_devices
                    """)
                    
                    for device_id, encrypted_data in cursor.fetchall():
                        try:
                            decrypted_data = self.cipher.decrypt(encrypted_data)
                            device_dict = json.loads(decrypted_data.decode('utf-8'))
                            devices.append(TrustedDevice.from_dict(device_dict))
                        except Exception as e:
                            self.logger.error("Failed to decrypt device data",
                                            device_id=device_id,
                                            error=str(e))
                            continue
                
                return devices
                
            except Exception as e:
                self.logger.error("Failed to get all trusted devices",
                                error=str(e))
                return []
    
    def get_device_audit_log(self, device_id: Optional[str] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get device audit log entries
        
        Args:
            device_id: Optional device ID to filter by
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if device_id:
                    cursor = conn.execute("""
                        SELECT device_id, operation, timestamp, details, success
                        FROM device_audit_log
                        WHERE device_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (device_id, limit))
                else:
                    cursor = conn.execute("""
                        SELECT device_id, operation, timestamp, details, success
                        FROM device_audit_log
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (limit,))
                
                entries = []
                for row in cursor.fetchall():
                    entries.append({
                        "device_id": row[0],
                        "operation": row[1],
                        "timestamp": row[2],
                        "details": row[3],
                        "success": bool(row[4])
                    })
                
                return entries
                
        except Exception as e:
            self.logger.error("Failed to get audit log",
                            device_id=device_id,
                            error=str(e))
            return []
    
    def cleanup_revoked_devices(self, older_than_days: int = 30) -> int:
        """
        Clean up revoked devices older than specified days
        
        Args:
            older_than_days: Remove revoked devices older than this many days
            
        Returns:
            Number of devices removed
        """
        with self._lock:
            try:
                cutoff_time = time.time() - (older_than_days * 24 * 3600)
                removed_count = 0
                
                # Get all devices to check which ones to remove
                all_devices = self.get_all_trusted_devices()
                
                for device in all_devices:
                    if (device.status == DeviceStatus.REVOKED and 
                        device.identity.last_seen_timestamp < cutoff_time):
                        
                        # Remove from database
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute("""
                                DELETE FROM trusted_devices 
                                WHERE device_id = ?
                            """, (device.identity.device_id,))
                            conn.commit()
                        
                        self._log_operation(device.identity.device_id, "cleanup", 
                                          True, f"Removed after {older_than_days} days")
                        removed_count += 1
                
                self.logger.info("Cleaned up revoked devices",
                               removed_count=removed_count,
                               older_than_days=older_than_days)
                
                return removed_count
                
            except Exception as e:
                self.logger.error("Failed to cleanup revoked devices",
                                error=str(e))
                return 0


# Aliases for test compatibility and enterprise naming
CryptographicDeviceIdentity = DeviceIdentity
CryptographicTrustedDevice = TrustedDevice
CryptographicDeviceRegistry = DeviceRegistry
DeviceAuthorityStatus = DeviceStatus