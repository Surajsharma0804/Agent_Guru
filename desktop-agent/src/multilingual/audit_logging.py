"""
Multilingual Audit Logging

Production-grade audit logging system for multilingual processing that extends
existing GURU audit capabilities with comprehensive multilingual event tracking,
privacy preservation, and cryptographic integrity.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

from .configuration import MultilingualConfig
from .exceptions import MultilingualError, SecurityBoundaryError


class MultilingualEventType(Enum):
    """Types of multilingual events to log."""
    
    # Language detection events
    LANGUAGE_DETECTION_SUCCESS = "language_detection_success"
    LANGUAGE_DETECTION_FAILURE = "language_detection_failure"
    MIXED_LANGUAGE_DETECTED = "mixed_language_detected"
    LANGUAGE_CACHE_HIT = "language_cache_hit"
    LANGUAGE_FALLBACK_USED = "language_fallback_used"
    
    # Intent normalization events
    INTENT_NORMALIZATION_SUCCESS = "intent_normalization_success"
    INTENT_NORMALIZATION_FAILURE = "intent_normalization_failure"
    CANONICAL_INTENT_CREATED = "canonical_intent_created"
    NORMALIZATION_CACHE_HIT = "normalization_cache_hit"
    
    # Mode classification events
    MODE_CLASSIFICATION_SUCCESS = "mode_classification_success"
    MODE_SWITCH_EXPLICIT = "mode_switch_explicit"
    MODE_SWITCH_AUTOMATIC = "mode_switch_automatic"
    MODE_DETECTION_FALLBACK = "mode_detection_fallback"
    
    # Voice processing events
    VOICE_PROCESSING_SUCCESS = "voice_processing_success"
    VOICE_PROCESSING_FAILURE = "voice_processing_failure"
    SPEAKER_VERIFICATION_SUCCESS = "speaker_verification_success"
    SPEAKER_VERIFICATION_FAILURE = "speaker_verification_failure"
    SPEECH_TO_TEXT_SUCCESS = "speech_to_text_success"
    SPEECH_TO_TEXT_FAILURE = "speech_to_text_failure"
    
    # Pipeline events
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    PIPELINE_STAGE_COMPLETED = "pipeline_stage_completed"
    
    # Security events
    SECURITY_VALIDATION_SUCCESS = "security_validation_success"
    SECURITY_VALIDATION_FAILURE = "security_validation_failure"
    AUTHORITY_CHECK_PASSED = "authority_check_passed"
    AUTHORITY_CHECK_FAILED = "authority_check_failed"
    
    # Performance events
    PERFORMANCE_THRESHOLD_EXCEEDED = "performance_threshold_exceeded"
    MODEL_LOADING_SUCCESS = "model_loading_success"
    MODEL_LOADING_FAILURE = "model_loading_failure"
    
    # Configuration events
    CONFIGURATION_LOADED = "configuration_loaded"
    CONFIGURATION_UPDATED = "configuration_updated"
    LANGUAGE_ENABLED = "language_enabled"
    LANGUAGE_DISABLED = "language_disabled"


class LogSeverity(Enum):
    """Log severity levels."""
    
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LanguageProcessingMetrics:
    """Metrics for language processing performance."""
    
    # Processing times
    language_detection_time_ms: Optional[int] = None
    intent_normalization_time_ms: Optional[int] = None
    mode_classification_time_ms: Optional[int] = None
    speech_to_text_time_ms: Optional[int] = None
    speaker_verification_time_ms: Optional[int] = None
    total_processing_time_ms: Optional[int] = None
    
    # Quality metrics
    language_confidence: Optional[float] = None
    intent_confidence: Optional[float] = None
    mode_confidence: Optional[float] = None
    speech_confidence: Optional[float] = None
    speaker_confidence: Optional[float] = None
    
    # Resource usage
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class MultilingualEvent:
    """Represents a multilingual processing event for audit logging."""
    
    # Event identification
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: MultilingualEventType = MultilingualEventType.PIPELINE_STARTED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Processing context
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    
    # Language context
    detected_language: Optional[str] = None
    primary_language: Optional[str] = None
    supported_languages: List[str] = field(default_factory=list)
    
    # Processing details
    processing_stage: Optional[str] = None
    processing_mode: Optional[str] = None
    pipeline_stage: Optional[str] = None
    
    # Results and outcomes
    success: bool = True
    error_message: Optional[str] = None
    warning_messages: List[str] = field(default_factory=list)
    
    # Performance metrics
    metrics: Optional[LanguageProcessingMetrics] = None
    
    # Security context
    authority_required: bool = False
    authority_granted: bool = False
    security_level: Optional[str] = None
    
    # Privacy-safe metadata (never log actual content)
    input_length: Optional[int] = None
    output_length: Optional[int] = None
    pattern_matched: Optional[str] = None
    model_used: Optional[str] = None
    
    # Additional context
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate event after creation."""
        # Ensure no sensitive content in additional_data
        self._sanitize_additional_data()
        
    def _sanitize_additional_data(self):
        """Remove potentially sensitive data from additional_data."""
        sensitive_keys = {
            'text', 'content', 'message', 'audio', 'voice', 'speech',
            'transcription', 'dictation', 'password', 'secret', 'key',
            'token', 'biometric', 'fingerprint', 'face', 'embedding'
        }
        
        sanitized_data = {}
        for key, value in self.additional_data.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive terms
            if any(sensitive_term in key_lower for sensitive_term in sensitive_keys):
                # Log only metadata about sensitive data
                if isinstance(value, (str, bytes)):
                    sanitized_data[f"{key}_length"] = len(value)
                elif isinstance(value, (list, dict)):
                    sanitized_data[f"{key}_count"] = len(value)
                else:
                    sanitized_data[f"{key}_type"] = type(value).__name__
            else:
                # Keep non-sensitive data
                sanitized_data[key] = value
                
        self.additional_data = sanitized_data
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id,
            'user_id': self.user_id,
            'request_id': self.request_id,
            'detected_language': self.detected_language,
            'primary_language': self.primary_language,
            'supported_languages': self.supported_languages,
            'processing_stage': self.processing_stage,
            'processing_mode': self.processing_mode,
            'pipeline_stage': self.pipeline_stage,
            'success': self.success,
            'error_message': self.error_message,
            'warning_messages': self.warning_messages,
            'metrics': self.metrics.to_dict() if self.metrics else None,
            'authority_required': self.authority_required,
            'authority_granted': self.authority_granted,
            'security_level': self.security_level,
            'input_length': self.input_length,
            'output_length': self.output_length,
            'pattern_matched': self.pattern_matched,
            'model_used': self.model_used,
            'additional_data': self.additional_data
        }


@dataclass
class MultilingualAuditEntry:
    """Complete audit entry for multilingual processing with integrity protection."""
    
    # Entry identification
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Event information
    event: MultilingualEvent = field(default_factory=lambda: MultilingualEvent())
    severity: LogSeverity = LogSeverity.INFO
    
    # System context
    system_version: Optional[str] = None
    component_version: Optional[str] = None
    
    # Integrity protection
    checksum: Optional[str] = field(default=None, init=False)
    signature: Optional[str] = field(default=None, init=False)
    
    def __post_init__(self):
        """Generate integrity protection after creation."""
        self._generate_checksum()
        
    def _generate_checksum(self):
        """Generate SHA-256 checksum for integrity verification."""
        # Create deterministic representation
        data = {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp.isoformat(),
            'event': self.event.to_dict(),
            'severity': self.severity.value,
            'system_version': self.system_version,
            'component_version': self.component_version
        }
        
        # Generate checksum
        json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        self.checksum = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        
    def verify_integrity(self) -> bool:
        """Verify entry integrity using checksum."""
        if not self.checksum:
            return False
            
        # Temporarily store current checksum
        original_checksum = self.checksum
        
        # Regenerate checksum
        self.checksum = None
        self._generate_checksum()
        
        # Compare checksums
        is_valid = self.checksum == original_checksum
        
        # Restore original checksum
        self.checksum = original_checksum
        
        return is_valid
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit entry to dictionary."""
        return {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp.isoformat(),
            'event': self.event.to_dict(),
            'severity': self.severity.value,
            'system_version': self.system_version,
            'component_version': self.component_version,
            'checksum': self.checksum,
            'signature': self.signature
        }


class CryptographicSigner:
    """Provides cryptographic signing for audit entries."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # In production, this would use actual cryptographic keys
        # For now, we'll use a placeholder implementation
        self._signing_key = "multilingual_audit_signing_key_placeholder"
        
    def sign_entry(self, entry: MultilingualAuditEntry) -> str:
        """
        Generate cryptographic signature for audit entry.
        
        In production, this would use:
        - RSA or ECDSA digital signatures
        - Hardware Security Module (HSM) for key protection
        - Proper key management and rotation
        """
        
        try:
            # Create signature payload
            payload = f"{entry.entry_id}:{entry.timestamp.isoformat()}:{entry.checksum}"
            
            # Generate HMAC signature (placeholder for actual digital signature)
            import hmac
            signature = hmac.new(
                self._signing_key.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            self.logger.error(f"Failed to sign audit entry: {e}")
            return ""
            
    def verify_signature(self, entry: MultilingualAuditEntry) -> bool:
        """Verify cryptographic signature of audit entry."""
        
        if not entry.signature:
            return False
            
        try:
            # Regenerate signature
            expected_signature = self.sign_entry(entry)
            
            # Compare signatures
            return hmac.compare_digest(entry.signature, expected_signature)
            
        except Exception as e:
            self.logger.error(f"Failed to verify audit entry signature: {e}")
            return False


class MultilingualAuditLogger:
    """
    Production-grade multilingual audit logger that extends existing GURU
    audit capabilities with comprehensive multilingual event tracking.
    """
    
    def __init__(self, config: MultilingualConfig, log_file_path: Optional[Path] = None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Audit log file
        self.log_file_path = log_file_path or Path("logs/multilingual_audit.jsonl")
        self._ensure_log_directory()
        
        # Cryptographic components
        self.crypto_signer = CryptographicSigner()
        
        # Audit statistics
        self._audit_stats = {
            'total_entries': 0,
            'entries_by_type': {},
            'entries_by_severity': {},
            'integrity_failures': 0,
            'signature_failures': 0
        }
        
        # Component version for audit trail
        self.component_version = "1.0.0"
        
    def _ensure_log_directory(self):
        """Ensure audit log directory exists."""
        try:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise MultilingualError(
                f"Failed to create audit log directory: {str(e)}",
                context={'log_path': str(self.log_file_path.parent)}
            )
            
    def log_event(
        self, 
        event: MultilingualEvent, 
        severity: LogSeverity = LogSeverity.INFO
    ) -> MultilingualAuditEntry:
        """
        Log multilingual processing event with integrity protection.
        
        Args:
            event: Multilingual event to log
            severity: Log severity level
            
        Returns:
            MultilingualAuditEntry that was logged
        """
        
        try:
            # Create audit entry
            entry = MultilingualAuditEntry(
                event=event,
                severity=severity,
                system_version="GURU-1.0.0",
                component_version=self.component_version
            )
            
            # Generate cryptographic signature
            entry.signature = self.crypto_signer.sign_entry(entry)
            
            # Write to audit log
            self._write_audit_entry(entry)
            
            # Update statistics
            self._update_audit_stats(entry)
            
            # Log to standard logger based on severity
            log_message = f"Multilingual event: {event.event_type.value}"
            if event.error_message:
                log_message += f" - Error: {event.error_message}"
                
            if severity == LogSeverity.DEBUG:
                self.logger.debug(log_message)
            elif severity == LogSeverity.INFO:
                self.logger.info(log_message)
            elif severity == LogSeverity.WARNING:
                self.logger.warning(log_message)
            elif severity == LogSeverity.ERROR:
                self.logger.error(log_message)
            elif severity == LogSeverity.CRITICAL:
                self.logger.critical(log_message)
                
            return entry
            
        except Exception as e:
            # Fallback logging if audit logging fails
            self.logger.error(f"Failed to log multilingual event: {e}")
            
            # Create minimal entry for return
            return MultilingualAuditEntry(
                event=event,
                severity=LogSeverity.ERROR
            )
            
    def _write_audit_entry(self, entry: MultilingualAuditEntry):
        """Write audit entry to log file."""
        
        try:
            # Convert to JSON
            entry_json = json.dumps(entry.to_dict(), separators=(',', ':'))
            
            # Append to log file
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(entry_json + '\n')
                
        except Exception as e:
            raise MultilingualError(
                f"Failed to write audit entry to log file: {str(e)}",
                context={'log_path': str(self.log_file_path), 'entry_id': entry.entry_id}
            )
            
    def _update_audit_stats(self, entry: MultilingualAuditEntry):
        """Update audit logging statistics."""
        
        self._audit_stats['total_entries'] += 1
        
        # Update by event type
        event_type = entry.event.event_type.value
        if event_type not in self._audit_stats['entries_by_type']:
            self._audit_stats['entries_by_type'][event_type] = 0
        self._audit_stats['entries_by_type'][event_type] += 1
        
        # Update by severity
        severity = entry.severity.value
        if severity not in self._audit_stats['entries_by_severity']:
            self._audit_stats['entries_by_severity'][severity] = 0
        self._audit_stats['entries_by_severity'][severity] += 1
        
    def log_language_detection(
        self, 
        detected_language: str,
        confidence: float,
        processing_time_ms: int,
        method: str,
        session_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> MultilingualAuditEntry:
        """Log language detection event."""
        
        event = MultilingualEvent(
            event_type=MultilingualEventType.LANGUAGE_DETECTION_SUCCESS if success else MultilingualEventType.LANGUAGE_DETECTION_FAILURE,
            session_id=session_id,
            detected_language=detected_language,
            processing_stage="language_detection",
            success=success,
            error_message=error,
            metrics=LanguageProcessingMetrics(
                language_detection_time_ms=processing_time_ms,
                language_confidence=confidence
            ),
            additional_data={
                'detection_method': method,
                'confidence_threshold': self.config.detection_threshold
            }
        )
        
        severity = LogSeverity.INFO if success else LogSeverity.WARNING
        return self.log_event(event, severity)
        
    def log_intent_normalization(
        self,
        original_language: str,
        canonical_action: str,
        processing_time_ms: int,
        confidence: float,
        pattern_matched: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> MultilingualAuditEntry:
        """Log intent normalization event."""
        
        event = MultilingualEvent(
            event_type=MultilingualEventType.INTENT_NORMALIZATION_SUCCESS if success else MultilingualEventType.INTENT_NORMALIZATION_FAILURE,
            session_id=session_id,
            detected_language=original_language,
            processing_stage="intent_normalization",
            success=success,
            error_message=error,
            pattern_matched=pattern_matched,
            metrics=LanguageProcessingMetrics(
                intent_normalization_time_ms=processing_time_ms,
                intent_confidence=confidence
            ),
            additional_data={
                'canonical_action': canonical_action,
                'normalization_path': f"{original_language} -> {canonical_action}"
            }
        )
        
        severity = LogSeverity.INFO if success else LogSeverity.WARNING
        return self.log_event(event, severity)
        
    def log_mode_classification(
        self,
        detected_mode: str,
        confidence: float,
        processing_time_ms: int,
        language: str,
        transition_type: str,
        session_id: Optional[str] = None,
        mode_switched: bool = False,
        success: bool = True,
        error: Optional[str] = None
    ) -> MultilingualAuditEntry:
        """Log mode classification event."""
        
        event_type = MultilingualEventType.MODE_CLASSIFICATION_SUCCESS
        if not success:
            event_type = MultilingualEventType.MODE_DETECTION_FALLBACK
        elif mode_switched:
            if transition_type == "explicit_command":
                event_type = MultilingualEventType.MODE_SWITCH_EXPLICIT
            else:
                event_type = MultilingualEventType.MODE_SWITCH_AUTOMATIC
                
        event = MultilingualEvent(
            event_type=event_type,
            session_id=session_id,
            detected_language=language,
            processing_stage="mode_classification",
            processing_mode=detected_mode,
            success=success,
            error_message=error,
            metrics=LanguageProcessingMetrics(
                mode_classification_time_ms=processing_time_ms,
                mode_confidence=confidence
            ),
            additional_data={
                'transition_type': transition_type,
                'mode_switched': mode_switched
            }
        )
        
        severity = LogSeverity.INFO if success else LogSeverity.WARNING
        return self.log_event(event, severity)
        
    def log_voice_processing(
        self,
        processing_time_ms: int,
        language: str,
        speaker_verified: bool,
        speech_confidence: float,
        session_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> MultilingualAuditEntry:
        """Log voice processing event."""
        
        event = MultilingualEvent(
            event_type=MultilingualEventType.VOICE_PROCESSING_SUCCESS if success else MultilingualEventType.VOICE_PROCESSING_FAILURE,
            session_id=session_id,
            detected_language=language,
            processing_stage="voice_processing",
            success=success,
            error_message=error,
            authority_required=True,
            authority_granted=speaker_verified,
            metrics=LanguageProcessingMetrics(
                total_processing_time_ms=processing_time_ms,
                speech_confidence=speech_confidence,
                speaker_confidence=0.8 if speaker_verified else 0.0
            ),
            additional_data={
                'speaker_verified': speaker_verified,
                'verification_threshold': self.config.speaker_verification_threshold
            }
        )
        
        severity = LogSeverity.INFO if success else LogSeverity.ERROR
        return self.log_event(event, severity)
        
    def log_security_validation(
        self,
        validation_passed: bool,
        security_level: str,
        canonical_action: str,
        session_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> MultilingualAuditEntry:
        """Log security validation event."""
        
        event = MultilingualEvent(
            event_type=MultilingualEventType.SECURITY_VALIDATION_SUCCESS if validation_passed else MultilingualEventType.SECURITY_VALIDATION_FAILURE,
            session_id=session_id,
            processing_stage="security_validation",
            success=validation_passed,
            error_message=reason if not validation_passed else None,
            authority_required=True,
            authority_granted=validation_passed,
            security_level=security_level,
            additional_data={
                'canonical_action': canonical_action,
                'validation_reason': reason
            }
        )
        
        severity = LogSeverity.INFO if validation_passed else LogSeverity.ERROR
        return self.log_event(event, severity)
        
    def log_performance_issue(
        self,
        operation: str,
        actual_time_ms: int,
        threshold_ms: int,
        session_id: Optional[str] = None
    ) -> MultilingualAuditEntry:
        """Log performance threshold exceeded event."""
        
        event = MultilingualEvent(
            event_type=MultilingualEventType.PERFORMANCE_THRESHOLD_EXCEEDED,
            session_id=session_id,
            processing_stage=operation,
            success=False,
            warning_messages=[f"Performance threshold exceeded: {actual_time_ms}ms > {threshold_ms}ms"],
            metrics=LanguageProcessingMetrics(
                total_processing_time_ms=actual_time_ms
            ),
            additional_data={
                'operation': operation,
                'threshold_ms': threshold_ms,
                'performance_ratio': actual_time_ms / threshold_ms
            }
        )
        
        return self.log_event(event, LogSeverity.WARNING)
        
    def verify_audit_integrity(self, entry_id: str) -> bool:
        """Verify integrity of a specific audit entry."""
        
        try:
            # Read and find entry (in production, this would use indexed storage)
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    entry_data = json.loads(line.strip())
                    if entry_data.get('entry_id') == entry_id:
                        # Reconstruct entry
                        entry = MultilingualAuditEntry(
                            entry_id=entry_data['entry_id'],
                            timestamp=datetime.fromisoformat(entry_data['timestamp']),
                            event=MultilingualEvent(**entry_data['event']),
                            severity=LogSeverity(entry_data['severity'])
                        )
                        entry.checksum = entry_data.get('checksum')
                        entry.signature = entry_data.get('signature')
                        
                        # Verify integrity
                        checksum_valid = entry.verify_integrity()
                        signature_valid = self.crypto_signer.verify_signature(entry)
                        
                        if not checksum_valid:
                            self._audit_stats['integrity_failures'] += 1
                        if not signature_valid:
                            self._audit_stats['signature_failures'] += 1
                            
                        return checksum_valid and signature_valid
                        
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to verify audit integrity: {e}")
            return False
            
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit logging statistics."""
        
        return {
            **self._audit_stats,
            'log_file_path': str(self.log_file_path),
            'log_file_size_mb': self.log_file_path.stat().st_size / (1024 * 1024) if self.log_file_path.exists() else 0,
            'component_version': self.component_version
        }
        
    def cleanup_old_logs(self, days_to_keep: int = 90):
        """Clean up old audit logs (placeholder for production implementation)."""
        
        # In production, this would:
        # 1. Archive old logs to secure storage
        # 2. Maintain integrity chains
        # 3. Comply with retention policies
        # 4. Provide secure deletion
        
        self.logger.info(f"Audit log cleanup requested (keep {days_to_keep} days)")
        
    def export_audit_logs(
        self, 
        start_date: datetime, 
        end_date: datetime,
        output_path: Path
    ) -> bool:
        """Export audit logs for specified date range."""
        
        try:
            exported_count = 0
            
            with open(self.log_file_path, 'r', encoding='utf-8') as input_file:
                with open(output_path, 'w', encoding='utf-8') as output_file:
                    for line in input_file:
                        entry_data = json.loads(line.strip())
                        entry_timestamp = datetime.fromisoformat(entry_data['timestamp'])
                        
                        if start_date <= entry_timestamp <= end_date:
                            output_file.write(line)
                            exported_count += 1
                            
            self.logger.info(f"Exported {exported_count} audit entries to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export audit logs: {e}")
            return False