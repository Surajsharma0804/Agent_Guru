"""Platform Integration - Permission Management.

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
    "CommandCategory",
    # Command Checker
    "CommandPermissionChecker",
    "CommandValidationError",
    "CommandValidationResult",
    "ConfigurationError",
    "DangerLevel",
    # Time Checker
    "DayOfWeek",
    "FileOperation",
    "HttpMethod",
    # Network Checker
    "NetworkPermissionChecker",
    "NetworkValidationError",
    "NetworkValidationResult",
    "OperationContext",
    "OperationType",
    # Path Checker
    "PathPermissionChecker",
    "PathValidationError",
    "PathValidationResult",
    "PermissionLevel",
    # Permission Manager
    "PermissionManager",
    # Model Manager
    "PermissionModelManager",
    "PermissionType",
    "PlatformPermissionError",
    "Protocol",
    "QuotaConfig",
    "QuotaExceededException",
    # Quota Manager
    "QuotaManager",
    "QuotaStatus",
    "TimeChecker",
    "TimeRestriction",
    "TimeWindow",
    "UserInfo",
    "UserQuotaCounters",
    "business_hours",
    "extract_domain",
    "get_path_extension",
    "is_absolute_path",
    "is_dangerous_command",
    "is_hidden_path",
    "is_https_url",
    "is_valid_url",
    "night_hours",
    "parse_command_safely",
    "sanitize_command_args",
    "sanitize_url_simple",
    "validate_path_safe",
    "weekends",
]
