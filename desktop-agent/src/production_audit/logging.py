"""
Audit Logger - Tamper-Evident Logging Infrastructure

Provides cryptographically-signed audit logging for all audit operations.
All events are tamper-evident and can be verified for integrity.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import json
import hashlib
import hmac


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Single audit event"""
    timestamp: datetime
    severity: AuditSeverity
    component: str
    event_type: str
    message: str
    metadata: Dict = field(default_factory=dict)
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Serialize event to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity.value,
            'component': self.component,
            'event_type': self.event_type,
            'message': self.message,
            'metadata': self.metadata,
            'signature': self.signature,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AuditEvent':
        """Deserialize event from dictionary"""
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            severity=AuditSeverity(data['severity']),
            component=data['component'],
            event_type=data['event_type'],
            message=data['message'],
            metadata=data.get('metadata', {}),
            signature=data.get('signature'),
        )


class AuditLogger:
    """
    Tamper-evident audit logger.
    
    All events are cryptographically signed to prevent tampering.
    Events are written to append-only log file.
    """
    
    def __init__(self, log_file: Path, signing_key: Optional[bytes] = None):
        """
        Initialize audit logger.
        
        Args:
            log_file: Path to log file
            signing_key: HMAC signing key (generated if not provided)
        """
        self.log_file = log_file.resolve()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load signing key
        key_file = self.log_file.parent / f"{self.log_file.stem}_key.bin"
        if signing_key:
            self.signing_key = signing_key
        elif key_file.exists():
            with open(key_file, 'rb') as f:
                self.signing_key = f.read()
        else:
            # Generate new key
            self.signing_key = hashlib.sha256(
                f"audit_key_{datetime.now().isoformat()}".encode()
            ).digest()
            with open(key_file, 'wb') as f:
                f.write(self.signing_key)
        
        # Event buffer
        self.event_buffer: List[AuditEvent] = []
    
    def log(
        self,
        severity: AuditSeverity,
        component: str,
        event_type: str,
        message: str,
        metadata: Optional[Dict] = None
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            severity: Event severity
            component: Component generating event
            event_type: Type of event
            message: Event message
            metadata: Additional event metadata
            
        Returns:
            Created AuditEvent
        """
        event = AuditEvent(
            timestamp=datetime.now(),
            severity=severity,
            component=component,
            event_type=event_type,
            message=message,
            metadata=metadata or {},
        )
        
        # Sign event
        event.signature = self._sign_event(event)
        
        # Write to log file
        self._write_event(event)
        
        # Add to buffer
        self.event_buffer.append(event)
        
        return event
    
    def debug(self, component: str, event_type: str, message: str, metadata: Optional[Dict] = None) -> AuditEvent:
        """Log debug event"""
        return self.log(AuditSeverity.DEBUG, component, event_type, message, metadata)
    
    def info(self, component: str, event_type: str, message: str, metadata: Optional[Dict] = None) -> AuditEvent:
        """Log info event"""
        return self.log(AuditSeverity.INFO, component, event_type, message, metadata)
    
    def warning(self, component: str, event_type: str, message: str, metadata: Optional[Dict] = None) -> AuditEvent:
        """Log warning event"""
        return self.log(AuditSeverity.WARNING, component, event_type, message, metadata)
    
    def error(self, component: str, event_type: str, message: str, metadata: Optional[Dict] = None) -> AuditEvent:
        """Log error event"""
        return self.log(AuditSeverity.ERROR, component, event_type, message, metadata)
    
    def critical(self, component: str, event_type: str, message: str, metadata: Optional[Dict] = None) -> AuditEvent:
        """Log critical event"""
        return self.log(AuditSeverity.CRITICAL, component, event_type, message, metadata)
    
    def verify_event(self, event: AuditEvent) -> bool:
        """
        Verify event signature.
        
        Args:
            event: Event to verify
            
        Returns:
            True if signature valid, False otherwise
        """
        if not event.signature:
            return False
        
        expected_signature = self._sign_event(event)
        return hmac.compare_digest(event.signature, expected_signature)
    
    def verify_log_integrity(self) -> bool:
        """
        Verify integrity of entire log file.
        
        Returns:
            True if all events have valid signatures, False otherwise
        """
        if not self.log_file.exists():
            return True
        
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        event = AuditEvent.from_dict(json.loads(line))
                        if not self.verify_event(event):
                            return False
            return True
        except Exception:
            return False
    
    def read_events(
        self,
        severity: Optional[AuditSeverity] = None,
        component: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AuditEvent]:
        """
        Read events from log file with optional filtering.
        
        Args:
            severity: Filter by severity
            component: Filter by component
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            
        Returns:
            List of matching events
        """
        if not self.log_file.exists():
            return []
        
        events = []
        with open(self.log_file, 'r') as f:
            for line in f:
                if line.strip():
                    event = AuditEvent.from_dict(json.loads(line))
                    
                    # Apply filters
                    if severity and event.severity != severity:
                        continue
                    if component and event.component != component:
                        continue
                    if event_type and event.event_type != event_type:
                        continue
                    if start_time and event.timestamp < start_time:
                        continue
                    if end_time and event.timestamp > end_time:
                        continue
                    
                    events.append(event)
        
        return events
    
    def get_statistics(self) -> Dict:
        """
        Get log statistics.
        
        Returns:
            Dictionary with log statistics
        """
        events = self.read_events()
        
        severity_counts = {}
        component_counts = {}
        event_type_counts = {}
        
        for event in events:
            severity_counts[event.severity.value] = severity_counts.get(event.severity.value, 0) + 1
            component_counts[event.component] = component_counts.get(event.component, 0) + 1
            event_type_counts[event.event_type] = event_type_counts.get(event.event_type, 0) + 1
        
        return {
            'total_events': len(events),
            'severity_counts': severity_counts,
            'component_counts': component_counts,
            'event_type_counts': event_type_counts,
            'first_event': events[0].timestamp.isoformat() if events else None,
            'last_event': events[-1].timestamp.isoformat() if events else None,
        }
    
    def _sign_event(self, event: AuditEvent) -> str:
        """
        Generate HMAC signature for event.
        
        Args:
            event: Event to sign
            
        Returns:
            Hex-encoded signature
        """
        # Create canonical representation
        canonical = (
            f"{event.timestamp.isoformat()}|"
            f"{event.severity.value}|"
            f"{event.component}|"
            f"{event.event_type}|"
            f"{event.message}|"
            f"{json.dumps(event.metadata, sort_keys=True)}"
        )
        
        # Generate HMAC
        signature = hmac.new(
            self.signing_key,
            canonical.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _write_event(self, event: AuditEvent) -> None:
        """
        Write event to log file.
        
        Args:
            event: Event to write
        """
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(event.to_dict()) + '\n')
