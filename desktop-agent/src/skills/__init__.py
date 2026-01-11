"""
GURU Skill System with Comprehensive Sandboxing

This module implements a production-grade skill execution system with:
- Process-level isolation using subprocess and resource limits
- Comprehensive resource monitoring (CPU, memory, disk, network)
- Sandbox escape detection and prevention
- Manifest-based permission system
- Rollback capabilities for skill actions
- Rate limiting and abuse prevention

The skill system follows GURU's core security principles:
- Authority-gated execution (requires ARMED state)
- Fail-safe defaults (deny by default)
- Comprehensive audit logging
- No silent failures or degraded operation
"""

from .skill_runner import SkillRunner
from .sandbox import ProcessSandbox, SandboxConfig, ResourceLimits
from .manifest import SkillManifest, PermissionSet, RollbackStrategy
from .registry import SkillRegistry
from .monitoring import ResourceMonitor, SandboxMonitor
from .exceptions import (
    SkillExecutionError,
    SandboxEscapeError,
    ResourceLimitExceededError,
    PermissionDeniedError,
    ManifestValidationError
)

__all__ = [
    'SkillRunner',
    'ProcessSandbox',
    'SandboxConfig', 
    'ResourceLimits',
    'SkillManifest',
    'PermissionSet',
    'RollbackStrategy',
    'SkillRegistry',
    'ResourceMonitor',
    'SandboxMonitor',
    'SkillExecutionError',
    'SandboxEscapeError',
    'ResourceLimitExceededError',
    'PermissionDeniedError',
    'ManifestValidationError'
]