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

__all__ = [
    "PermissionManager",
    "PermissionLevel",
    "PlatformPermissionError",
    "UserInfo",
]
