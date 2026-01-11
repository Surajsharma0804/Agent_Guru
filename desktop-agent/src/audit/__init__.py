"""
Comprehensive Audit Logging System

Production-grade audit logging infrastructure for GURU Personal Assistant.
Provides cryptographically signed, tamper-evident audit trails for all system operations
with comprehensive event coverage and integrity verification.

This module implements the mandatory audit requirement that all automation actions,
security events, and system operations must be logged with cryptographic integrity
protection and comprehensive coverage.

Key Features:
- Cryptographically signed audit entries using HMAC-SHA256
- Tamper-evident hash chain linking for integrity verification
- Comprehensive event coverage across all system components
- Privacy-preserving content handling (no sensitive data logged)
- Append-only log structure with secure storage
- Real-time integrity verification and tamper detection
- Audit trail export capabilities for forensic analysis
- Component-specific audit loggers with unified interface

Security Guarantees:
- All audit entries are cryptographically signed and tamper-evident
- Hash chain linking prevents insertion, deletion, or modification of entries
- No sensitive content (passwords, text content, biometric data) is ever logged
- Audit log integrity can be verified at any time
- Failed audit logging triggers immediate system halt (fail-safe)

Components:
- AuditLogger: Core comprehensive audit logging system
- ComponentAuditLogger: Base class for component-specific loggers
- AuditEvent: Structured audit event representation
- IntegrityVerifier: Audit log integrity verification system
"""

from .audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditLogEntry,
    IntegrityVerificationResult
)

from .component_logger import ComponentAuditLogger
from .integrity_verifier import IntegrityVerifier

__all__ = [
    'AuditLogger',
    'AuditEvent', 
    'AuditEventType',
    'AuditSeverity',
    'AuditLogEntry',
    'IntegrityVerificationResult',
    'ComponentAuditLogger',
    'IntegrityVerifier'
]