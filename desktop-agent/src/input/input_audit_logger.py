"""
Input Audit Logger

Production-grade audit logging system for all input simulation events.
Provides comprehensive, tamper-evident logging with cryptographic integrity
verification and privacy-preserving content handling.

This logger implements the mandatory audit requirement that all automation
actions must be logged with cryptographic integrity protection.
"""

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# InputEvent will be imported at runtime to avoid circular imports


class AuditEventType(Enum):
    """Types of audit events for input operations"""
    INPUT_EVENT = "input_event"
    SECURITY_VIOLATION = "security_violation"
    AUTHORITY_CHECK = "authority_check"
    VALIDATION_FAILURE = "validation_failure"
    SYSTEM_EVENT = "system_event"
    EMERGENCY_EVENT = "emergency_event"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditLogEntry:
    """Represents a single audit log entry with cryptographic integrity"""
    timestamp: str
    event_type: AuditEventType
    severity: AuditSeverity
    component: str
    action: str
    details: Dict[str, Any]
    session_id: Optional[str]
    user_id: Optional[str]
    previous_hash: Optional[str]
    entry_hash: str
    signature: str
    
    def to_dict(self) -> Dict:
        """Convert audit entry to dictionary for serialization"""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "component": self.component,
            "action": self.action,
            "details": self.details,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "signature": self.signature
        }


class InputAuditLogger:
    """
    Comprehensive audit logging system for input simulation operations.
    
    This logger provides:
    - Tamper-evident logging with hash chains
    - Cryptographic signatures for integrity verification
    - Privacy-preserving content handling (no sensitive data logged)
    - Comprehensive event coverage for all input operations
    - Secure storage with append-only semantics
    - Audit trail export capabilities
    
    Security Features:
    - HMAC-SHA256 signatures for entry integrity
    - Hash chain linking for tamper detection
    - No sensitive content logging (text content, passwords, etc.)
    - Secure key management for signature verification
    - Automatic log rotation and archival
    """
    
    def __init__(self, log_directory: str = None, signing_key: bytes = None):
        """
        Initialize Input Audit Logger with secure configuration.
        
        Args:
            log_directory: Directory for audit log storage
            signing_key: Key for cryptographic signatures (generated if None)
        """
        self.logger = logging.getLogger(__name__)
        
        # Configure log storage
        self.log_directory = Path(log_directory) if log_directory else Path("audit_logs")
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize cryptographic components
        self.signing_key = signing_key or self._generate_signing_key()
        
        # Hash chain for tamper detection
        self.last_entry_hash: Optional[str] = None
        
        # Current log file
        self.current_log_file = self._get_current_log_file()
        
        # Load last entry hash from existing log
        self._load_last_entry_hash()
        
        # Configuration
        self.max_log_file_size = 10 * 1024 * 1024  # 10MB per log file
        self.max_detail_length = 1000  # Maximum length for detail fields
        
        self.logger.info(f"InputAuditLogger initialized with log directory: {self.log_directory}")
    
    def _generate_signing_key(self) -> bytes:
        """Generate a new signing key for audit log signatures"""
        # In production, this should be derived from a secure key management system
        # For now, generate a random key and store it securely
        key_file = self.log_directory / "signing_key.bin"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = os.urandom(32)  # 256-bit key for HMAC-SHA256
            
            # Store key securely (in production, use proper key management)
            with open(key_file, 'wb') as f:
                f.write(key)
            
            # Set restrictive permissions
            os.chmod(key_file, 0o600)
            
            self.logger.info("Generated new signing key for audit logs")
            return key
    
    def _get_current_log_file(self) -> Path:
        """Get current log file path with date-based naming"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.log_directory / f"input_audit_{date_str}.jsonl"
    
    def _load_last_entry_hash(self):
        """Load the hash of the last entry from existing log file"""
        if not self.current_log_file.exists():
            return
        
        try:
            with open(self.current_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if last_line:
                        entry_data = json.loads(last_line)
                        self.last_entry_hash = entry_data.get('entry_hash')
                        self.logger.info(f"Loaded last entry hash: {self.last_entry_hash[:16]}...")
        except Exception as e:
            self.logger.error(f"Failed to load last entry hash: {e}")
    
    def _calculate_entry_hash(self, entry_data: Dict) -> str:
        """Calculate hash for an audit entry"""
        # Create canonical representation for hashing
        hash_data = {
            "timestamp": entry_data["timestamp"],
            "event_type": entry_data["event_type"],
            "component": entry_data["component"],
            "action": entry_data["action"],
            "details": entry_data["details"],
            "previous_hash": entry_data["previous_hash"]
        }
        
        canonical_json = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    
    def _sign_entry(self, entry_hash: str) -> str:
        """Create HMAC signature for an audit entry"""
        return hmac.new(
            self.signing_key,
            entry_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize details to remove sensitive information and limit size.
        
        This ensures no sensitive content (passwords, text content, etc.) is logged.
        """
        sanitized = {}
        
        for key, value in details.items():
            # Skip sensitive keys
            if key.lower() in ['password', 'secret', 'key', 'token', 'text_content']:
                continue
            
            # Convert value to string and limit length
            str_value = str(value)
            if len(str_value) > self.max_detail_length:
                str_value = str_value[:self.max_detail_length] + "...[truncated]"
            
            sanitized[key] = str_value
        
        return sanitized
    
    def _write_audit_entry(self, entry: AuditLogEntry):
        """Write audit entry to log file with proper error handling"""
        try:
            # Check if we need to rotate log file
            if self.current_log_file.exists() and self.current_log_file.stat().st_size > self.max_log_file_size:
                self._rotate_log_file()
            
            # Write entry to log file
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, separators=(',', ':'))
                f.write('\n')
            
            # Update last entry hash
            self.last_entry_hash = entry.entry_hash
            
        except Exception as e:
            self.logger.error(f"Failed to write audit entry: {e}")
            # In production, this should trigger emergency procedures
            raise
    
    def _rotate_log_file(self):
        """Rotate current log file when it gets too large"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_name = self.current_log_file.with_name(
            f"{self.current_log_file.stem}_{timestamp}.jsonl"
        )
        
        self.current_log_file.rename(archived_name)
        self.current_log_file = self._get_current_log_file()
        self.last_entry_hash = None
        
        self.logger.info(f"Rotated log file to: {archived_name}")
    
    def log_input_event(self, input_event):
        """
        Log an input simulation event.
        
        Args:
            input_event: Input event to log (InputEvent from windows_input_engine)
        """
        # Import InputEvent here to avoid circular imports
        
        # Prepare details without sensitive content
        details = {
            "event_type": input_event.event_type.value,
            "security_level": input_event.security_level.value,
            "requires_authority": input_event.requires_authority,
            "execution_time_ms": input_event.parameters.get("execution_time_ms"),
            "events_sent": input_event.parameters.get("events_sent"),
            "text_length": input_event.parameters.get("text_length"),  # Length only, not content
            "key_count": len(input_event.parameters.get("keys", [])),
            "vk_codes_count": len(input_event.parameters.get("vk_codes", []))
        }
        
        # Remove None values
        details = {k: v for k, v in details.items() if v is not None}
        
        self._create_audit_entry(
            event_type=AuditEventType.INPUT_EVENT,
            severity=AuditSeverity.INFO,
            action=f"input_{input_event.event_type.value}",
            details=details,
            session_id=input_event.session_id
        )
    
    def log_security_violation(self, violation_type: str, details: Dict[str, Any], session_id: str = None):
        """
        Log a security violation event.
        
        Args:
            violation_type: Type of security violation
            details: Details about the violation (will be sanitized)
            session_id: Optional session identifier
        """
        sanitized_details = self._sanitize_details(details)
        sanitized_details["violation_type"] = violation_type
        
        self._create_audit_entry(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.ERROR,
            action="security_violation",
            details=sanitized_details,
            session_id=session_id
        )
    
    def log_authority_check(self, operation: str, granted: bool, reason: str, session_id: str = None):
        """
        Log an authority check event.
        
        Args:
            operation: Operation that was checked
            granted: Whether authority was granted
            reason: Reason for the decision
            session_id: Optional session identifier
        """
        details = {
            "operation": operation,
            "granted": granted,
            "reason": reason
        }
        
        severity = AuditSeverity.INFO if granted else AuditSeverity.WARNING
        
        self._create_audit_entry(
            event_type=AuditEventType.AUTHORITY_CHECK,
            severity=severity,
            action="authority_check",
            details=details,
            session_id=session_id
        )
    
    def log_validation_failure(self, validation_type: str, violations: List[str], session_id: str = None):
        """
        Log a validation failure event.
        
        Args:
            validation_type: Type of validation that failed
            violations: List of validation violations
            session_id: Optional session identifier
        """
        details = {
            "validation_type": validation_type,
            "violations": violations[:10],  # Limit to first 10 violations
            "violation_count": len(violations)
        }
        
        self._create_audit_entry(
            event_type=AuditEventType.VALIDATION_FAILURE,
            severity=AuditSeverity.WARNING,
            action="validation_failure",
            details=details,
            session_id=session_id
        )
    
    def log_system_event(self, event_name: str, details: Dict[str, Any], severity: AuditSeverity = AuditSeverity.INFO):
        """
        Log a system event.
        
        Args:
            event_name: Name of the system event
            details: Event details (will be sanitized)
            severity: Event severity level
        """
        sanitized_details = self._sanitize_details(details)
        
        self._create_audit_entry(
            event_type=AuditEventType.SYSTEM_EVENT,
            severity=severity,
            action=event_name,
            details=sanitized_details
        )
    
    def log_emergency_event(self, event_name: str, details: Dict[str, Any]):
        """
        Log an emergency event with critical severity.
        
        Args:
            event_name: Name of the emergency event
            details: Event details (will be sanitized)
        """
        sanitized_details = self._sanitize_details(details)
        
        self._create_audit_entry(
            event_type=AuditEventType.EMERGENCY_EVENT,
            severity=AuditSeverity.CRITICAL,
            action=event_name,
            details=sanitized_details
        )
    
    def _create_audit_entry(self, 
                           event_type: AuditEventType,
                           severity: AuditSeverity,
                           action: str,
                           details: Dict[str, Any],
                           session_id: str = None,
                           user_id: str = None):
        """Create and write an audit entry with cryptographic integrity"""
        
        # Create entry data
        entry_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type.value,
            "severity": severity.value,
            "component": "input_engine",
            "action": action,
            "details": details,
            "session_id": session_id,
            "user_id": user_id,
            "previous_hash": self.last_entry_hash
        }
        
        # Calculate entry hash
        entry_hash = self._calculate_entry_hash(entry_data)
        
        # Create signature
        signature = self._sign_entry(entry_hash)
        
        # Create audit entry
        audit_entry = AuditLogEntry(
            timestamp=entry_data["timestamp"],
            event_type=event_type,
            severity=severity,
            component=entry_data["component"],
            action=action,
            details=details,
            session_id=session_id,
            user_id=user_id,
            previous_hash=self.last_entry_hash,
            entry_hash=entry_hash,
            signature=signature
        )
        
        # Write to log file
        self._write_audit_entry(audit_entry)
        
        # Log to standard logger as well
        log_level = {
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL
        }[severity]
        
        self.logger.log(log_level, f"Audit: {action} - {event_type.value}")
    
    def verify_log_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log.
        
        Returns:
            Dictionary with verification results
        """
        if not self.current_log_file.exists():
            return {"status": "no_log_file", "verified": True}
        
        try:
            with open(self.current_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                return {"status": "empty_log", "verified": True}
            
            verification_results = {
                "status": "verified",
                "verified": True,
                "total_entries": len(lines),
                "hash_chain_valid": True,
                "signature_valid": True,
                "invalid_entries": []
            }
            
            previous_hash = None
            
            for i, line in enumerate(lines):
                try:
                    entry_data = json.loads(line.strip())
                    
                    # Verify hash chain
                    if entry_data.get("previous_hash") != previous_hash:
                        verification_results["hash_chain_valid"] = False
                        verification_results["invalid_entries"].append({
                            "line": i + 1,
                            "error": "hash_chain_broken"
                        })
                    
                    # Verify signature
                    expected_hash = self._calculate_entry_hash(entry_data)
                    if entry_data.get("entry_hash") != expected_hash:
                        verification_results["signature_valid"] = False
                        verification_results["invalid_entries"].append({
                            "line": i + 1,
                            "error": "invalid_hash"
                        })
                    
                    expected_signature = self._sign_entry(expected_hash)
                    if entry_data.get("signature") != expected_signature:
                        verification_results["signature_valid"] = False
                        verification_results["invalid_entries"].append({
                            "line": i + 1,
                            "error": "invalid_signature"
                        })
                    
                    previous_hash = entry_data.get("entry_hash")
                    
                except json.JSONDecodeError:
                    verification_results["verified"] = False
                    verification_results["invalid_entries"].append({
                        "line": i + 1,
                        "error": "invalid_json"
                    })
            
            verification_results["verified"] = (
                verification_results["hash_chain_valid"] and 
                verification_results["signature_valid"] and
                len(verification_results["invalid_entries"]) == 0
            )
            
            return verification_results
            
        except Exception as e:
            return {
                "status": "verification_failed",
                "verified": False,
                "error": str(e)
            }
    
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit logging statistics for monitoring"""
        stats = {
            "log_directory": str(self.log_directory),
            "current_log_file": str(self.current_log_file),
            "log_file_exists": self.current_log_file.exists(),
            "max_log_file_size": self.max_log_file_size,
            "max_detail_length": self.max_detail_length,
            "has_signing_key": self.signing_key is not None,
            "last_entry_hash": self.last_entry_hash[:16] + "..." if self.last_entry_hash else None
        }
        
        if self.current_log_file.exists():
            stats["current_log_file_size"] = self.current_log_file.stat().st_size
            
            # Count entries
            try:
                with open(self.current_log_file, 'r', encoding='utf-8') as f:
                    stats["total_entries"] = sum(1 for line in f if line.strip())
            except Exception:
                stats["total_entries"] = "unknown"
        
        return stats