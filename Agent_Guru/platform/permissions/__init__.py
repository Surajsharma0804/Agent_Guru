"""
Platform Integration - Permission Management

This module provides cross-platform permission management and validation.
"""

from Agent_Guru.platform.permissions.command_checker import (
    CommandCategory,
    CommandPermissionChecker,
    CommandValidationError,
    CommandValidationResult,
    DangerLevel,
    is_dangerous_command,
    parse_command_safely,
    sanitize_command_args,
)
from Agent_Guru.platform.permissions.manager import (
    PermissionError as PlatformPermissionError,
)
from Agent_Guru.platform.permissions.manager import (
    PermissionLevel,
    PermissionManager,
    UserInfo,
)
from Agent_Guru.platform.permissions.model_manager import (
    ConfigurationError,
    FileOperation,
    HttpMethod,
    OperationContext,
    OperationType,
    PermissionModelManager,
    QuotaStatus,
)
from Agent_Guru.platform.permissions.network_checker import (
    NetworkPermissionChecker,
    NetworkValidationError,
    NetworkValidationResult,
    Protocol,
    extract_domain,
    is_https_url,
    is_valid_url,
    sanitize_url_simple,
)
from Agent_Guru.platform.permissions.path_checker import (
    PathPermissionChecker,
    PathValidationError,
    PathValidationResult,
    PermissionType,
    get_path_extension,
    is_absolute_path,
    is_hidden_path,
    validate_path_safe,
)
from Agent_Guru.platform.permissions.quota_manager import (
    QuotaConfig,
    QuotaExceededException,
    QuotaManager,
    UserQuotaCounters,
)
from Agent_Guru.platform.permissions.time_checker import (
    DayOfWeek,
    TimeChecker,
    TimeRestriction,
    TimeWindow,
    business_hours,
    night_hours,
    weekends,
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
    # Quota Manager
    "QuotaManager",
    "QuotaConfig",
    "UserQuotaCounters",
    "QuotaExceededException",
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

