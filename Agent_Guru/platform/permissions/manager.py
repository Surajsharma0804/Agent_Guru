"""
Permission Manager - Cross-platform permission validation and management.

This module provides platform-independent permission checking and validation
for system operations requiring elevated privileges.

Performance Characteristics:
    - Time Complexity: O(1) for all permission checks
    - Space Complexity: O(1) - minimal state
    - Latency: <1ms per check

Architecture:
    The PermissionManager uses platform-specific APIs to detect and validate
    permissions. It provides a unified interface across Windows, macOS, and Linux.

Author: Agent Guru Team
"""

import os
import sys
import platform
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import ctypes


class PermissionLevel(Enum):
    """Permission levels for system operations."""
    USER = "user"
    ADMIN = "admin"
    ROOT = "root"


@dataclass
class UserInfo:
    """Information about the current user.
    
    Attributes:
        username: Current username
        uid: User ID (Unix) or None (Windows)
        gid: Group ID (Unix) or None (Windows)
        is_elevated: Whether running with elevated privileges
        permission_level: Current permission level
    """
    username: str
    uid: Optional[int]
    gid: Optional[int]
    is_elevated: bool
    permission_level: PermissionLevel


class PermissionError(Exception):
    """Exception raised when permission validation fails.
    
    Attributes:
        message: Error message
        required_level: Required permission level
        current_level: Current permission level
    """
    
    def __init__(
        self,
        message: str,
        required_level: PermissionLevel,
        current_level: PermissionLevel
    ):
        self.message = message
        self.required_level = required_level
        self.current_level = current_level
        super().__init__(self.message)


class PermissionManager:
    """Cross-platform permission manager.
    
    Provides unified interface for permission checking and validation
    across Windows, macOS, and Linux platforms.
    
    Time Complexity: O(1) for all operations
    Space Complexity: O(1) - minimal state
    
    Example:
        >>> manager = PermissionManager()
        >>> if manager.is_elevated():
        ...     print("Running with elevated privileges")
        >>> manager.require_elevated()  # Raises if not elevated
    """
    
    def __init__(self):
        """Initialize permission manager."""
        self._platform = platform.system()
        self._user_info: Optional[UserInfo] = None
    
    def is_elevated(self) -> bool:
        """Check if running with elevated privileges.
        
        Time Complexity: O(1)
        
        Returns:
            True if running as admin/root, False otherwise
            
        Example:
            >>> manager = PermissionManager()
            >>> if manager.is_elevated():
            ...     print("Running with admin/root privileges")
        """
        if self._platform == "Windows":
            return self._is_windows_admin()
        else:  # Unix-like (macOS, Linux)
            return self._is_unix_root()
    
    def require_elevated(self) -> None:
        """Require elevated privileges, raise error if not elevated.
        
        Time Complexity: O(1)
        
        Raises:
            PermissionError: If not running with elevated privileges
            
        Example:
            >>> manager = PermissionManager()
            >>> try:
            ...     manager.require_elevated()
            ...     # Perform privileged operation
            ... except PermissionError as e:
            ...     print(f"Permission denied: {e}")
        """
        if not self.is_elevated():
            current_level = PermissionLevel.USER
            required_level = (
                PermissionLevel.ADMIN if self._platform == "Windows"
                else PermissionLevel.ROOT
            )
            
            raise PermissionError(
                f"This operation requires {required_level.value} privileges. "
                f"Current level: {current_level.value}. "
                f"Please run with elevated privileges.",
                required_level=required_level,
                current_level=current_level
            )
    
    def can_access_path(self, path: str, mode: str = "r") -> bool:
        """Check if current user can access path with specified mode.
        
        Time Complexity: O(1)
        
        Args:
            path: File or directory path to check
            mode: Access mode - "r" (read), "w" (write), "x" (execute)
            
        Returns:
            True if access is permitted, False otherwise
            
        Raises:
            ValueError: If mode is invalid
            
        Example:
            >>> manager = PermissionManager()
            >>> if manager.can_access_path("/etc/passwd", "r"):
            ...     print("Can read /etc/passwd")
        """
        if mode not in ("r", "w", "x"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'r', 'w', or 'x'")
        
        # Map mode to os.access constants
        mode_map = {
            "r": os.R_OK,
            "w": os.W_OK,
            "x": os.X_OK
        }
        
        # Check if path exists and is accessible
        return os.path.exists(path) and os.access(path, mode_map[mode])
    
    def get_current_user(self) -> UserInfo:
        """Get current user information.
        
        Time Complexity: O(1)
        
        Returns:
            UserInfo with current user details
            
        Example:
            >>> manager = PermissionManager()
            >>> user = manager.get_current_user()
            >>> print(f"Username: {user.username}")
            >>> print(f"Elevated: {user.is_elevated}")
        """
        if self._user_info is None:
            self._user_info = self._get_user_info()
        return self._user_info
    
    def validate_permission(
        self,
        required_level: PermissionLevel,
        operation: str
    ) -> None:
        """Validate that current user has required permission level.
        
        Time Complexity: O(1)
        
        Args:
            required_level: Required permission level
            operation: Description of operation requiring permission
            
        Raises:
            PermissionError: If current level is insufficient
            
        Example:
            >>> manager = PermissionManager()
            >>> try:
            ...     manager.validate_permission(
            ...         PermissionLevel.ADMIN,
            ...         "modify system settings"
            ...     )
            ... except PermissionError as e:
            ...     print(f"Cannot modify settings: {e}")
        """
        user = self.get_current_user()
        
        if required_level == PermissionLevel.USER:
            # User level always satisfied
            return
        
        if required_level in (PermissionLevel.ADMIN, PermissionLevel.ROOT):
            if not user.is_elevated:
                raise PermissionError(
                    f"Operation '{operation}' requires {required_level.value} "
                    f"privileges. Current level: {user.permission_level.value}. "
                    f"Please run with elevated privileges.",
                    required_level=required_level,
                    current_level=user.permission_level
                )
    
    def _is_windows_admin(self) -> bool:
        """Check if running as Windows administrator.
        
        Time Complexity: O(1)
        
        Returns:
            True if running as admin, False otherwise
        """
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except AttributeError:
            # Not on Windows or ctypes not available
            return False
    
    def _is_unix_root(self) -> bool:
        """Check if running as Unix root user.
        
        Time Complexity: O(1)
        
        Returns:
            True if running as root (UID 0), False otherwise
        """
        try:
            return os.geteuid() == 0
        except AttributeError:
            # Not on Unix or os.geteuid not available
            return False
    
    def _get_user_info(self) -> UserInfo:
        """Get current user information.
        
        Time Complexity: O(1)
        
        Returns:
            UserInfo with current user details
        """
        is_elevated = self.is_elevated()
        
        if self._platform == "Windows":
            # Windows user info
            username = os.getenv("USERNAME", "unknown")
            permission_level = (
                PermissionLevel.ADMIN if is_elevated
                else PermissionLevel.USER
            )
            
            return UserInfo(
                username=username,
                uid=None,
                gid=None,
                is_elevated=is_elevated,
                permission_level=permission_level
            )
        else:
            # Unix-like user info
            username = os.getenv("USER", "unknown")
            uid = os.getuid() if hasattr(os, "getuid") else None
            gid = os.getgid() if hasattr(os, "getgid") else None
            permission_level = (
                PermissionLevel.ROOT if is_elevated
                else PermissionLevel.USER
            )
            
            return UserInfo(
                username=username,
                uid=uid,
                gid=gid,
                is_elevated=is_elevated,
                permission_level=permission_level
            )
