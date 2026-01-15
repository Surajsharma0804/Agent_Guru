"""
GURU Input Simulation Engine

This module provides voice-driven input simulation capabilities with strict authority enforcement
and comprehensive security validation. All input simulation requires ARMED authority state.

Core Components:
- WindowsInputEngine: Windows API keyboard/mouse simulation
- InputValidator: Security validation and sanitization
- AuthorityGate: Authority state enforcement
- AuditLogger: Comprehensive input event logging

Security Boundaries:
- All input simulation requires Authority_State == ARMED
- Input validation prevents injection attacks
- Comprehensive audit logging without content exposure
- Immediate halt on authority revocation
"""

from .authority_gate import AuthorityGate
from .input_audit_logger import InputAuditLogger
from .input_validator import InputValidator
from .windows_input_engine import WindowsInputEngine

__all__ = [
    'WindowsInputEngine',
    'InputValidator', 
    'AuthorityGate',
    'InputAuditLogger'
]