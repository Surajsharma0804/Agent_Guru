"""
Skill System Exception Hierarchy

Defines all exceptions used by the skill system with clear error categories
and security-focused error handling.
"""

from typing import Any, Dict, Optional


class SkillSystemError(Exception):
    """Base exception for all skill system errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SkillExecutionError(SkillSystemError):
    """Raised when skill execution fails."""
    
    def __init__(self, skill_id: str, message: str, exit_code: Optional[int] = None, 
                 stderr: Optional[str] = None):
        super().__init__(f"Skill '{skill_id}' execution failed: {message}")
        self.skill_id = skill_id
        self.exit_code = exit_code
        self.stderr = stderr


class SandboxEscapeError(SkillSystemError):
    """Raised when sandbox escape attempt is detected."""
    
    def __init__(self, skill_id: str, violation_type: str, details: str):
        super().__init__(f"Sandbox escape detected for skill '{skill_id}': {violation_type}")
        self.skill_id = skill_id
        self.violation_type = violation_type
        self.violation_details = details


class ResourceLimitExceededError(SkillSystemError):
    """Raised when skill exceeds resource limits."""
    
    def __init__(self, skill_id: str, resource_type: str, limit: float, actual: float):
        super().__init__(
            f"Skill '{skill_id}' exceeded {resource_type} limit: "
            f"{actual} > {limit}"
        )
        self.skill_id = skill_id
        self.resource_type = resource_type
        self.limit = limit
        self.actual = actual


class PermissionDeniedError(SkillSystemError):
    """Raised when skill attempts unauthorized operation."""
    
    def __init__(self, skill_id: str, permission: str, operation: str):
        super().__init__(
            f"Skill '{skill_id}' denied permission '{permission}' for operation: {operation}"
        )
        self.skill_id = skill_id
        self.permission = permission
        self.operation = operation


class ManifestValidationError(SkillSystemError):
    """Raised when skill manifest is invalid."""
    
    def __init__(self, skill_id: str, validation_errors: list[str]):
        error_list = "; ".join(validation_errors)
        super().__init__(f"Skill '{skill_id}' manifest validation failed: {error_list}")
        self.skill_id = skill_id
        self.validation_errors = validation_errors


class SkillNotFoundError(SkillSystemError):
    """Raised when requested skill is not found."""
    
    def __init__(self, skill_id: str):
        super().__init__(f"Skill '{skill_id}' not found in registry")
        self.skill_id = skill_id


class SkillRegistrationError(SkillSystemError):
    """Raised when skill registration fails."""
    
    def __init__(self, skill_id: str, reason: str):
        super().__init__(f"Failed to register skill '{skill_id}': {reason}")
        self.skill_id = skill_id
        self.reason = reason


class SandboxInitializationError(SkillSystemError):
    """Raised when sandbox initialization fails."""
    
    def __init__(self, reason: str, system_error: Optional[str] = None):
        super().__init__(f"Sandbox initialization failed: {reason}")
        self.reason = reason
        self.system_error = system_error


class RateLimitExceededError(SkillSystemError):
    """Raised when skill exceeds rate limits."""
    
    def __init__(self, skill_id: str, limit_type: str, current_rate: float, max_rate: float):
        super().__init__(
            f"Skill '{skill_id}' exceeded {limit_type} rate limit: "
            f"{current_rate} > {max_rate}"
        )
        self.skill_id = skill_id
        self.limit_type = limit_type
        self.current_rate = current_rate
        self.max_rate = max_rate