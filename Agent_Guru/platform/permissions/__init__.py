"""
Platform Integration - Permission Management

This module provides cross-platform permission management and validation.
"""

from Agent_Guru.platform.permissions.manager import (
    PermissionManager,
    PermissionLevel,
    PermissionError as PlatformPermissionError,
    UserInfo,
)

from Agent_Guru.platform.permissions.path_checker import (
    PathPermissionChecker,
    PermissionType,
    PathValidationResult,
    PathValidationError,
    validate_path_safe,
    is_absolute_path,
    get_path_extension,
    is_hidden_path,
)

from Agent_Guru.platform.permissions.model_manager import (
    PermissionModelManager,
    FileOperation,
    HttpMethod,
    OperationType,
    OperationContext,
    QuotaStatus,
    ConfigurationError,
)

from Agent_Guru.platform.permissions.command_checker import (
    CommandPermissionChecker,
    CommandValidationResult,
    CommandCategory,
    DangerLevel,
    CommandValidationError,
    is_dangerous_command,
    sanitize_command_args,
    parse_command_safely,
)

from Agent_Guru.platform.permissions.network_checker import (
    NetworkPermissionChecker,
    NetworkValidationResult,
    NetworkValidationError,
    Protocol,
    is_valid_url,
    extract_domain,
    is_https_url,
    sanitize_url_simple,
)

from Agent_Guru.platform.permissions.time_checker import (
    DayOfWeek,
    TimeWindow,
    TimeRestriction,
    TimeChecker,
    business_hours,
    weekends,
    night_hours,
)

__all__ = [
    # Permission Manager
    "PermissionManager",
    "PermissionLevel",
    "PlatformPermissionError",
    "UserInfo",
    # Path Checker
    "PathPermissionChecker",
    "PermissionType",
    "PathValidationResult",
    "PathValidationError",
    "validate_path_safe",
    "is_absolute_path",
    "get_path_extension",
    "is_hidden_path",
    # Model Manager
    "PermissionModelManager",
    "FileOperation",
    "HttpMethod",
    "OperationType",
    "OperationContext",
    "QuotaStatus",
    "ConfigurationError",
    # Command Checker
    "CommandPermissionChecker",
    "CommandValidationResult",
    "CommandCategory",
    "DangerLevel",
    "CommandValidationError",
    "is_dangerous_command",
    "sanitize_command_args",
    "parse_command_safely",
    # Network Checker
    "NetworkPermissionChecker",
    "NetworkValidationResult",
    "NetworkValidationError",
    "Protocol",
    "is_valid_url",
    "extract_domain",
    "is_https_url",
    "sanitize_url_simple",
    # Time Checker
    "DayOfWeek",
    "TimeWindow",
    "TimeRestriction",
    "TimeChecker",
    "business_hours",
    "weekends",
    "night_hours",
]

