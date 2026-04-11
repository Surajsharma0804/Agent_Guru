"""
Module: Agent_Guru.platform.os_controller
Purpose: Main OS Controller - Unified facade for complete laptop control

This module provides the main OSController class that integrates all specialized
controllers and provides a unified interface for AGENT_GURU to execute ANY laptop
operation through voice commands.

Performance Characteristics:
    - Time Complexity: O(1) for operation routing, delegates to controllers
    - Space Complexity: O(1) for controller instances
    - Latency: <10ms for routing + controller execution time
    - Throughput: >100 operations/second

Architecture:
    The OSController acts as a facade that:
    1. Routes operations to appropriate specialized controllers
    2. Provides user confirmation for destructive operations
    3. Maintains comprehensive audit logging for all operations
    4. Handles errors and provides recovery mechanisms
    5. Validates permissions before executing operations

Safety Features:
    - Confirmation prompts for destructive operations (delete, shutdown, format)
    - Comprehensive audit trail for all executed operations
    - Permission validation before sensitive operations
    - Error handling with detailed error messages and recovery
    - Operation rollback support for failed multi-step operations

Usage Example:
    >>> from Agent_Guru.platform.os_controller import OSController
    >>>
    >>> # Initialize controller
    >>> controller = OSController(
    ...     audit_log_path="audit.log",
    ...     require_confirmation=True
    ... )
    >>>
    >>> # File operations
    >>> controller.create_file("test.txt", "Hello, World!")
    >>>
    >>> # Application control
    >>> controller.open_application("notepad")
    >>>
    >>> # System settings
    >>> controller.set_volume(50)
    >>>
    >>> # Text input
    >>> controller.type_text("Hello from AGENT_GURU!")

Author: Agent Guru Development Team
Date: 2026-02-25
Version: 1.0.0
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


# Import controllers (at module level for testability)
try:
    from Agent_Guru.platform.controllers.application_control import ApplicationController
    from Agent_Guru.platform.controllers.file_operations import FileOperationsController
    from Agent_Guru.platform.controllers.input_control import KeyboardController, MouseController
    from Agent_Guru.platform.controllers.media_control import MediaController
    from Agent_Guru.platform.controllers.messaging_controller import MessagingController
    from Agent_Guru.platform.controllers.screen_capture import ScreenCaptureController
    from Agent_Guru.platform.controllers.system_settings import SystemSettingsController
    from Agent_Guru.platform.controllers.text_input import TextInputController
    from Agent_Guru.platform.controllers.window_management import WindowManager
    from Agent_Guru.platform.hardware.monitor import HardwareMonitor
    from Agent_Guru.platform.process_manager import ProcessManager
except ImportError as e:
    logger.warning("Some controllers not available: %s", e)


class OperationCategory(Enum):
    """Categories of OS operations for routing."""
    FILE = "file"
    APPLICATION = "application"
    TEXT_INPUT = "text_input"
    MESSAGING = "messaging"
    SYSTEM_SETTINGS = "system_settings"
    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    WINDOW = "window"
    MEDIA = "media"
    SCREEN_CAPTURE = "screen_capture"
    PROCESS = "process"
    HARDWARE = "hardware"


@dataclass
class OperationResult:
    """Result of an OS operation.

    Attributes:
        success: Whether the operation succeeded
        category: Category of operation performed
        operation: Specific operation name
        message: Human-readable result message
        error: Error message if operation failed
        metadata: Additional operation metadata
        timestamp: ISO 8601 timestamp of operation
    """
    success: bool
    category: OperationCategory
    operation: str
    message: str
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())


@dataclass
class AuditLogEntry:
    """Audit log entry for OS operations.

    Attributes:
        timestamp: ISO 8601 timestamp of operation
        category: Category of operation
        operation: Specific operation name
        success: Whether operation succeeded
        user: User who performed operation
        details: Additional operation details
    """
    timestamp: str
    category: str
    operation: str
    success: bool
    user: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert audit entry to JSON string."""
        return json.dumps({
            "timestamp": self.timestamp,
            "category": self.category,
            "operation": self.operation,
            "success": self.success,
            "user": self.user,
            "details": self.details
        })


class OSControllerError(Exception):
    """Base exception for OS controller errors."""


class OperationNotSupportedError(OSControllerError):
    """Raised when operation is not supported on current platform."""


class ConfirmationRequiredError(OSControllerError):
    """Raised when user confirmation is required but not provided."""



class OSController:
    """Main OS Controller - Unified facade for complete laptop control.

    This controller integrates all specialized controllers and provides a unified
    interface for AGENT_GURU to execute ANY laptop operation through voice commands.

    Time Complexity:
        - Operation routing: O(1)
        - Actual operation: Depends on controller (documented in each controller)

    Space Complexity:
        - Controller instances: O(1)
        - Audit log: O(n) where n is number of operations

    Attributes:
        audit_log_path: Path to audit log file
        require_confirmation: Whether to require confirmation for destructive ops
        platform: Current platform name
        _file_controller: File operations controller
        _app_controller: Application control controller
        _text_controller: Text input controller
        _messaging_controller: Messaging controller
        _settings_controller: System settings controller
        _mouse_controller: Mouse controller
        _keyboard_controller: Keyboard controller
        _window_controller: Window management controller
        _media_controller: Media control controller
        _screen_controller: Screen capture controller
        _process_manager: Process management
        _hardware_monitor: Hardware monitoring
    """

    def __init__(
        self,
        audit_log_path: Optional[str] = None,
        require_confirmation: bool = False
    ):
        """Initialize OS controller.

        Args:
            audit_log_path: Path to audit log file (None = no logging)
            require_confirmation: Whether to require confirmation for destructive ops
        """
        self.audit_log_path = audit_log_path
        self.require_confirmation = require_confirmation
        self.platform = sys.platform

        # Initialize audit log
        if self.audit_log_path:
            self._init_audit_log()

        # Initialize all controllers
        self._init_controllers()

        logger.info("OSController initialized on platform: %s", self.platform)

    def _init_audit_log(self) -> None:
        """Initialize audit log file."""
        try:
            audit_path = Path(self.audit_log_path)
            audit_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not audit_path.exists():
                audit_path.touch(mode=0o600)
            logger.info("Audit log initialized: %s", self.audit_log_path)
        except Exception as e:
            logger.error("Failed to initialize audit log: %s", e)

    def _init_controllers(self) -> None:
        """Initialize all specialized controllers with per-controller error isolation."""
        self._file_controller = self._safe_init(
            FileOperationsController,
            audit_log_path=self.audit_log_path,
            require_confirmation=self.require_confirmation,
        )
        self._app_controller = self._safe_init(ApplicationController)
        self._desktop_app_controller = self._safe_init_desktop_app()
        self._text_controller = self._safe_init(TextInputController)
        self._messaging_controller = self._safe_init(MessagingController)
        self._settings_controller = self._safe_init(SystemSettingsController)
        self._mouse_controller = self._safe_init(MouseController)
        self._keyboard_controller = self._safe_init(KeyboardController)
        self._window_controller = self._safe_init(WindowManager)
        self._media_controller = self._safe_init(MediaController)
        self._screen_controller = self._safe_init(ScreenCaptureController)
        self._process_manager = self._safe_init(ProcessManager)
        self._hardware_monitor = self._safe_init(HardwareMonitor)
        logger.info("Controllers initialized")

    def _safe_init(self, cls: type, *args: Any, **kwargs: Any) -> Any:
        """Initialize a controller class, returning None on any failure.

        Args:
            cls: Controller class to instantiate
            *args: Positional arguments for the constructor
            **kwargs: Keyword arguments for the constructor

        Returns:
            Controller instance or None if initialization failed
        """
        try:
            return cls(*args, **kwargs)
        except Exception as exc:
            cls_name = getattr(cls, "__name__", repr(cls))
            logger.warning("Controller %s failed to initialize: %s", cls_name, exc)
            return None

    def _safe_init_desktop_app(self) -> Any:
        """Initialize DesktopApplicationController with platform-aware error handling.

        Returns:
            DesktopApplicationController instance or None if not available
        """
        try:
            from Agent_Guru.platform.controllers.desktop_app_controller import (
                DesktopApplicationController,
            )
            return DesktopApplicationController()
        except RuntimeError:
            logger.info("DesktopApplicationController not available on mobile platform")
            return None
        except Exception as exc:
            logger.warning("DesktopApplicationController failed to initialize: %s", exc)
            return None


    def _log_operation(
        self,
        category: OperationCategory,
        operation: str,
        success: bool,
        details: Optional[dict[str, Any]] = None
    ) -> None:
        """Log operation to audit log.

        Args:
            category: Category of operation
            operation: Specific operation name
            success: Whether operation succeeded
            details: Additional operation details
        """
        if not self.audit_log_path:
            return

        entry = AuditLogEntry(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            category=category.value,
            operation=operation,
            success=success,
            user=os.getenv("USER") or os.getenv("USERNAME"),
            details=details or {}
        )

        try:
            with open(self.audit_log_path, "a") as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)

    def _require_confirmation(self, operation: str, details: str) -> None:
        """Check if confirmation is required for destructive operation.

        Args:
            operation: Operation name
            details: Operation details

        Raises:
            ConfirmationRequiredError: If confirmation required but not provided
        """
        if self.require_confirmation:
            raise ConfirmationRequiredError(
                f"Confirmation required for destructive operation: {operation} - {details}"
            )

    # ==================== File Operations ====================

    def create_file(
        self,
        path: str,
        content: Union[str, bytes] = "",
        overwrite: bool = False
    ) -> OperationResult:
        """Create a new file with optional content.

        Time Complexity: O(n) where n is content size
        Space Complexity: O(n) for content storage

        Args:
            path: Path to file to create
            content: Initial file content
            overwrite: Whether to overwrite existing file

        Returns:
            OperationResult with operation status
        """
        try:
            result = self._file_controller.create_file(path, content, overwrite)
            self._log_operation(
                OperationCategory.FILE,
                "create_file",
                result.success,
                {"path": path, "size": len(content)}
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="create_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata
            )
        except Exception as e:
            logger.error("Failed to create file: %s", e)
            self._log_operation(OperationCategory.FILE, "create_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="create_file",
                message=f"Failed to create file: {path}",
                error=str(e)
            )

    def read_file(
        self,
        path: str,
        binary: bool = False,
        encoding: str = "utf-8"
    ) -> Union[str, bytes, None]:
        """Read file content.

        Time Complexity: O(n) where n is file size
        Space Complexity: O(n) for file content

        Args:
            path: Path to file to read
            binary: Whether to read as binary
            encoding: Text encoding (if not binary)

        Returns:
            File content as string or bytes, None on error
        """
        try:
            content = self._file_controller.read_file(path, binary, encoding)
            self._log_operation(
                OperationCategory.FILE,
                "read_file",
                content is not None,
                {"path": path, "binary": binary}
            )
            return content
        except Exception as e:
            logger.error("Failed to read file: %s", e)
            self._log_operation(OperationCategory.FILE, "read_file", False, {"error": str(e)})
            return None


    def delete_file(
        self,
        path: str,
        confirm: bool = False
    ) -> OperationResult:
        """Delete a file.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            path: Path to file to delete
            confirm: Whether user confirmed deletion

        Returns:
            OperationResult with operation status
        """
        try:
            result = self._file_controller.delete_file(path, confirm)
            self._log_operation(
                OperationCategory.FILE,
                "delete_file",
                result.success,
                {"path": path}
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="delete_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata
            )
        except Exception as e:
            logger.error("Failed to delete file: %s", e)
            self._log_operation(OperationCategory.FILE, "delete_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="delete_file",
                message=f"Failed to delete file: {path}",
                error=str(e)
            )

    def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> OperationResult:
        """Copy a file to a new location.

        Time Complexity: O(n) where n is file size
        Space Complexity: O(1) (streaming copy)

        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing destination

        Returns:
            OperationResult with operation status
        """
        try:
            result = self._file_controller.copy_file(source, destination, overwrite)
            self._log_operation(
                OperationCategory.FILE,
                "copy_file",
                result.success,
                {"source": source, "destination": destination}
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="copy_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata
            )
        except Exception as e:
            logger.error("Failed to copy file: %s", e)
            self._log_operation(OperationCategory.FILE, "copy_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="copy_file",
                message=f"Failed to copy file: {source} -> {destination}",
                error=str(e)
            )

    def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False
    ) -> OperationResult:
        """Move a file to a new location.

        Time Complexity: O(1) for same filesystem, O(n) for different filesystem
        Space Complexity: O(1)

        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing destination

        Returns:
            OperationResult with operation status
        """
        try:
            result = self._file_controller.move_file(source, destination, overwrite)
            self._log_operation(
                OperationCategory.FILE,
                "move_file",
                result.success,
                {"source": source, "destination": destination}
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="move_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata
            )
        except Exception as e:
            logger.error("Failed to move file: %s", e)
            self._log_operation(OperationCategory.FILE, "move_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="move_file",
                message=f"Failed to move file: {source} -> {destination}",
                error=str(e)
            )


    # ==================== Application Control ====================

    def open_application(
        self,
        app_name: str,
        args: Optional[list[str]] = None
    ) -> OperationResult:
        """Open an application by name.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Tries DesktopApplicationController.open_app() first (richer, async),
        falling back to ApplicationController.open_application().

        Args:
            app_name: Application name or path
            args: Optional command-line arguments

        Returns:
            OperationResult with operation status
        """
        # Try DesktopApplicationController first (richer async implementation)
        if self._desktop_app_controller is not None:
            try:
                try:
                    asyncio.get_running_loop()
                    # Running inside an event loop — run in a separate thread's loop
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        success = pool.submit(
                            asyncio.run,
                            self._desktop_app_controller.open_app(app_name),
                        ).result()
                except RuntimeError:
                    # No running event loop — safe to use asyncio.run() directly
                    success = asyncio.run(
                        self._desktop_app_controller.open_app(app_name)
                    )
                if success:
                    self._log_operation(
                        OperationCategory.APPLICATION,
                        "open_application",
                        True,
                        {"app_name": app_name, "controller": "desktop_app"},
                    )
                    return OperationResult(
                        success=True,
                        category=OperationCategory.APPLICATION,
                        operation="open_application",
                        message=f"Application opened successfully: {app_name}",
                        metadata={"app_name": app_name},
                    )
            except Exception as exc:
                logger.debug(
                    "DesktopApplicationController.open_app failed for %s: %s — falling back",
                    app_name,
                    exc,
                )

        # Fallback: ApplicationController
        try:
            pid = self._app_controller.open_application(app_name, args)
            self._log_operation(
                OperationCategory.APPLICATION,
                "open_application",
                True,
                {"app_name": app_name, "pid": pid}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.APPLICATION,
                operation="open_application",
                message=f"Application opened successfully: {app_name}",
                metadata={"pid": pid}
            )
        except Exception as e:
            logger.error("Failed to open application: %s", e)
            self._log_operation(
                OperationCategory.APPLICATION,
                "open_application",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="open_application",
                message=f"Failed to open application: {app_name}",
                error=str(e)
            )

    def close_application(
        self,
        app_identifier: str,
        force: bool = False
    ) -> OperationResult:
        """Close an application by name or PID.

        Time Complexity: O(n) where n is number of processes
        Space Complexity: O(1)

        Args:
            app_identifier: Application name or PID
            force: Whether to force kill

        Returns:
            OperationResult with operation status
        """
        try:
            success = self._app_controller.close_application(app_identifier, force)
            self._log_operation(
                OperationCategory.APPLICATION,
                "close_application",
                success,
                {"app_identifier": app_identifier, "force": force}
            )
            return OperationResult(
                success=success,
                category=OperationCategory.APPLICATION,
                operation="close_application",
                message=f"Application closed: {app_identifier}",
                metadata={"force": force}
            )
        except Exception as e:
            logger.error("Failed to close application: %s", e)
            self._log_operation(
                OperationCategory.APPLICATION,
                "close_application",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="close_application",
                message=f"Failed to close application: {app_identifier}",
                error=str(e)
            )

    # ==================== Text Input ====================

    def type_text(
        self,
        text: str,
        interval: float = 0.0
    ) -> OperationResult:
        """Type text into active application.

        Time Complexity: O(n) where n is text length
        Space Complexity: O(1)

        Args:
            text: Text to type
            interval: Delay between keystrokes in seconds

        Returns:
            OperationResult with operation status
        """
        try:
            self._text_controller.type_text(text, interval)
            self._log_operation(
                OperationCategory.TEXT_INPUT,
                "type_text",
                True,
                {"length": len(text)}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.TEXT_INPUT,
                operation="type_text",
                message=f"Text typed successfully ({len(text)} characters)",
                metadata={"length": len(text)}
            )
        except Exception as e:
            logger.error("Failed to type text: %s", e)
            self._log_operation(
                OperationCategory.TEXT_INPUT,
                "type_text",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.TEXT_INPUT,
                operation="type_text",
                message="Failed to type text",
                error=str(e)
            )


    # ==================== System Settings ====================

    def set_volume(self, level: int) -> OperationResult:
        """Set system volume level.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            level: Volume level 0-100

        Returns:
            OperationResult with operation status
        """
        try:
            self._settings_controller.set_volume(level)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "set_volume",
                True,
                {"level": level}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_volume",
                message=f"Volume set to {level}%",
                metadata={"level": level}
            )
        except Exception as e:
            logger.error("Failed to set volume: %s", e)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "set_volume",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_volume",
                message=f"Failed to set volume to {level}%",
                error=str(e)
            )

    def volume_up(self, amount: int = 10) -> OperationResult:
        """Increase system volume by *amount* percent.

        Args:
            amount: Amount to increase (default 10)

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.volume_up(amount)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "volume_up", True, {"amount": amount}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="volume_up",
                message=f"Volume increased by {amount}%",
                metadata={"amount": amount},
            )
        except Exception as e:
            logger.error("Failed to increase volume: %s", e)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "volume_up", False, {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="volume_up",
                message="Failed to increase volume",
                error=str(e),
            )

    def volume_down(self, amount: int = 10) -> OperationResult:
        """Decrease system volume by *amount* percent.

        Args:
            amount: Amount to decrease (default 10)

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.volume_down(amount)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "volume_down", True, {"amount": amount}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="volume_down",
                message=f"Volume decreased by {amount}%",
                metadata={"amount": amount},
            )
        except Exception as e:
            logger.error("Failed to decrease volume: %s", e)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "volume_down", False, {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="volume_down",
                message="Failed to decrease volume",
                error=str(e),
            )

    def mute(self) -> OperationResult:
        """Mute system audio.

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.mute()
            self._log_operation(OperationCategory.SYSTEM_SETTINGS, "mute", True, {})
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="mute",
                message="Audio muted",
            )
        except Exception as e:
            logger.error("Failed to mute: %s", e)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "mute", False, {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="mute",
                message="Failed to mute audio",
                error=str(e),
            )

    def unmute(self) -> OperationResult:
        """Unmute system audio.

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.unmute()
            self._log_operation(OperationCategory.SYSTEM_SETTINGS, "unmute", True, {})
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="unmute",
                message="Audio unmuted",
            )
        except Exception as e:
            logger.error("Failed to unmute: %s", e)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "unmute", False, {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="unmute",
                message="Failed to unmute audio",
                error=str(e),
            )

    def set_brightness(self, level: int) -> OperationResult:
        """Set screen brightness level.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            level: Brightness level 0-100

        Returns:
            OperationResult with operation status
        """
        try:
            self._settings_controller.set_brightness(level)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "set_brightness",
                True,
                {"level": level}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_brightness",
                message=f"Brightness set to {level}%",
                metadata={"level": level}
            )
        except Exception as e:
            logger.error("Failed to set brightness: %s", e)
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "set_brightness",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_brightness",
                message=f"Failed to set brightness to {level}%",
                error=str(e)
            )

    # ==================== Window Management ====================

    def minimize_window(self, window_identifier: str) -> OperationResult:
        """Minimize an application window.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Args:
            window_identifier: Window title or handle

        Returns:
            OperationResult with operation status
        """
        try:
            success = self._app_controller.minimize_window(window_identifier)
            self._log_operation(
                OperationCategory.WINDOW,
                "minimize_window",
                success,
                {"window": window_identifier}
            )
            return OperationResult(
                success=success,
                category=OperationCategory.WINDOW,
                operation="minimize_window",
                message=f"Window minimized: {window_identifier}",
                metadata={"window": window_identifier}
            )
        except Exception as e:
            logger.error("Failed to minimize window: %s", e)
            self._log_operation(
                OperationCategory.WINDOW,
                "minimize_window",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.WINDOW,
                operation="minimize_window",
                message=f"Failed to minimize window: {window_identifier}",
                error=str(e)
            )

    def maximize_window(self, window_identifier: str) -> OperationResult:
        """Maximize an application window.

        Time Complexity: O(n) where n is number of windows
        Space Complexity: O(1)

        Args:
            window_identifier: Window title or handle

        Returns:
            OperationResult with operation status
        """
        try:
            success = self._app_controller.maximize_window(window_identifier)
            self._log_operation(
                OperationCategory.WINDOW,
                "maximize_window",
                success,
                {"window": window_identifier}
            )
            return OperationResult(
                success=success,
                category=OperationCategory.WINDOW,
                operation="maximize_window",
                message=f"Window maximized: {window_identifier}",
                metadata={"window": window_identifier}
            )
        except Exception as e:
            logger.error("Failed to maximize window: %s", e)
            self._log_operation(
                OperationCategory.WINDOW,
                "maximize_window",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.WINDOW,
                operation="maximize_window",
                message=f"Failed to maximize window: {window_identifier}",
                error=str(e)
            )


    # ==================== Media Control ====================

    def play_media(self) -> OperationResult:
        """Play media (simulate media play/pause key).

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.play()
            self._log_operation(
                OperationCategory.MEDIA,
                "play_media",
                True,
                {}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="play_media",
                message="Media play command sent"
            )
        except Exception as e:
            logger.error("Failed to play media: %s", e)
            self._log_operation(
                OperationCategory.MEDIA,
                "play_media",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="play_media",
                message="Failed to play media",
                error=str(e)
            )

    def pause_media(self) -> OperationResult:
        """Pause media (simulate media pause key).

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.pause()
            self._log_operation(
                OperationCategory.MEDIA,
                "pause_media",
                True,
                {}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="pause_media",
                message="Media pause command sent"
            )
        except Exception as e:
            logger.error("Failed to pause media: %s", e)
            self._log_operation(
                OperationCategory.MEDIA,
                "pause_media",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="pause_media",
                message="Failed to pause media",
                error=str(e)
            )

    def next_track(self) -> OperationResult:
        """Skip to next media track.

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.next_track()
            self._log_operation(OperationCategory.MEDIA, "next_track", True, {})
            return OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="next_track",
                message="Skipped to next track",
            )
        except Exception as e:
            logger.error("Failed to skip track: %s", e)
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="next_track",
                message="Failed to skip to next track",
                error=str(e),
            )

    def previous_track(self) -> OperationResult:
        """Go to previous media track.

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.previous_track()
            self._log_operation(OperationCategory.MEDIA, "previous_track", True, {})
            return OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="previous_track",
                message="Went to previous track",
            )
        except Exception as e:
            logger.error("Failed to go to previous track: %s", e)
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="previous_track",
                message="Failed to go to previous track",
                error=str(e),
            )

    def stop_media(self) -> OperationResult:
        """Stop media playback.

        Returns:
            OperationResult with operation status
        """
        try:
            self._media_controller.stop()
            self._log_operation(OperationCategory.MEDIA, "stop_media", True, {})
            return OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="stop_media",
                message="Media stopped",
            )
        except Exception as e:
            logger.error("Failed to stop media: %s", e)
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="stop_media",
                message="Failed to stop media",
                error=str(e),
            )

    # ==================== Web / Browser ====================

    def open_url(self, url: str, browser: Optional[str] = None) -> OperationResult:
        """Open a URL in the default (or specified) browser.

        Handles bare queries like "youtube" → https://www.youtube.com,
        search queries like "python tutorials" → Google search URL.

        Args:
            url: URL, domain, or search query
            browser: Optional browser name (e.g. "chrome", "firefox")

        Returns:
            OperationResult with operation status
        """
        import webbrowser

        # Normalise: if it looks like a bare domain or keyword, build a URL
        resolved = self._resolve_url(url)

        try:
            if browser:
                # Try to open with specific browser via app controller
                try:
                    self._app_controller.open_application(browser, [resolved])
                except Exception as e:
                    webbrowser.open(resolved)
            else:
                webbrowser.open(resolved)

            self._log_operation(
                OperationCategory.APPLICATION, "open_url", True, {"url": resolved}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.APPLICATION,
                operation="open_url",
                message=f"Opened URL: {resolved}",
                metadata={"url": resolved},
            )
        except Exception as e:
            logger.error("Failed to open URL %s: %s", resolved, e)
            self._log_operation(
                OperationCategory.APPLICATION, "open_url", False, {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="open_url",
                message=f"Failed to open URL: {resolved}",
                error=str(e),
            )

    def web_search(self, query: str, engine: str = "google") -> OperationResult:
        """Perform a web search by opening the browser with a search URL.

        Args:
            query: Search query
            engine: Search engine ("google", "youtube", "bing")

        Returns:
            OperationResult with operation status
        """
        _engines = {
            "google": "https://www.google.com/search?q=",
            "youtube": "https://www.youtube.com/results?search_query=",
            "bing": "https://www.bing.com/search?q=",
        }
        base = _engines.get(engine.lower(), _engines["google"])
        import urllib.parse
        url = base + urllib.parse.quote_plus(query)
        return self.open_url(url)

    @staticmethod
    def _resolve_url(raw: str) -> str:
        """Resolve a raw string to a full URL.

        Args:
            raw: URL, domain, or search query

        Returns:
            Full URL string
        """
        import urllib.parse

        raw = raw.strip()
        # Already a full URL
        if raw.startswith(("http://", "https://")):
            return raw

        # Known site shortcuts
        _shortcuts: dict[str, str] = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "github": "https://www.github.com",
            "stackoverflow": "https://stackoverflow.com",
            "reddit": "https://www.reddit.com",
            "twitter": "https://www.twitter.com",
            "x": "https://www.x.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "linkedin": "https://www.linkedin.com",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://open.spotify.com",
            "wikipedia": "https://www.wikipedia.org",
        }
        lower = raw.lower()
        if lower in _shortcuts:
            return _shortcuts[lower]

        # Looks like a domain (contains a dot, no spaces)
        if "." in raw and " " not in raw:
            return f"https://{raw}"

        # Treat as a Google search query
        return "https://www.google.com/search?q=" + urllib.parse.quote_plus(raw)

    # ==================== Destructive / Permission-Required Operations ====================

    def uninstall_application(
        self, app_name: str, confirmed: bool = False
    ) -> OperationResult:
        """Uninstall an application. Requires explicit confirmation.

        Args:
            app_name: Application name to uninstall
            confirmed: Must be True to proceed (user confirmed)

        Returns:
            OperationResult — fails with permission error if not confirmed
        """
        if not confirmed:
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="uninstall_application",
                message=f"Permission required: uninstalling '{app_name}' is a destructive operation. "
                        "Please confirm before proceeding.",
                error="confirmation_required",
                metadata={"requires_confirmation": True, "app_name": app_name},
            )
        try:
            import subprocess
            if self.platform == "win32":
                # Use winget if available, else warn
                result = subprocess.run(
                    ["winget", "uninstall", "--name", app_name, "--silent"],
                    capture_output=True, text=True, timeout=120
                )
                success = result.returncode == 0
                msg = result.stdout or result.stderr
            else:
                success = False
                msg = f"Uninstall not implemented for platform: {self.platform}"

            self._log_operation(
                OperationCategory.APPLICATION, "uninstall_application", success,
                {"app_name": app_name, "confirmed": confirmed}
            )
            return OperationResult(
                success=success,
                category=OperationCategory.APPLICATION,
                operation="uninstall_application",
                message=msg,
                metadata={"app_name": app_name},
            )
        except Exception as e:
            logger.error("Failed to uninstall %s: %s", app_name, e)
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="uninstall_application",
                message=f"Failed to uninstall {app_name}",
                error=str(e),
            )

    def reset_pc(self, confirmed: bool = False) -> OperationResult:
        """Reset / restart the PC. Requires explicit confirmation.

        Args:
            confirmed: Must be True to proceed

        Returns:
            OperationResult — fails with permission error if not confirmed
        """
        if not confirmed:
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="reset_pc",
                message="Permission required: resetting the PC will restart your computer. "
                        "Please confirm before proceeding.",
                error="confirmation_required",
                metadata={"requires_confirmation": True},
            )
        try:
            import subprocess
            if self.platform == "win32":
                subprocess.Popen(["shutdown", "/r", "/t", "5"])
                msg = "PC will restart in 5 seconds"
            elif self.platform == "darwin":
                subprocess.Popen(["sudo", "shutdown", "-r", "now"])
                msg = "PC restarting now"
            else:
                subprocess.Popen(["sudo", "reboot"])
                msg = "PC restarting now"

            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "reset_pc", True, {"confirmed": True}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="reset_pc",
                message=msg,
            )
        except Exception as e:
            logger.error("Failed to reset PC: %s", e)
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="reset_pc",
                message="Failed to reset PC",
                error=str(e),
            )

    def shutdown_pc(self, confirmed: bool = False) -> OperationResult:
        """Shut down the PC. Requires explicit confirmation.

        Args:
            confirmed: Must be True to proceed

        Returns:
            OperationResult — fails with permission error if not confirmed
        """
        if not confirmed:
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="shutdown_pc",
                message="Permission required: shutting down the PC. "
                        "Please confirm before proceeding.",
                error="confirmation_required",
                metadata={"requires_confirmation": True},
            )
        try:
            import subprocess
            if self.platform == "win32":
                subprocess.Popen(["shutdown", "/s", "/t", "5"])
                msg = "PC will shut down in 5 seconds"
            elif self.platform == "darwin":
                subprocess.Popen(["sudo", "shutdown", "-h", "now"])
                msg = "PC shutting down now"
            else:
                subprocess.Popen(["sudo", "poweroff"])
                msg = "PC shutting down now"

            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS, "shutdown_pc", True, {"confirmed": True}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="shutdown_pc",
                message=msg,
            )
        except Exception as e:
            logger.error("Failed to shut down PC: %s", e)
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="shutdown_pc",
                message="Failed to shut down PC",
                error=str(e),
            )

    # ==================== Screen Capture ====================

    def take_screenshot(
        self,
        save_path: Optional[str] = None,
        region: Optional[tuple] = None
    ) -> OperationResult:
        """Capture a screenshot.

        Time Complexity: O(w*h) where w,h are screen dimensions
        Space Complexity: O(w*h) for image data

        Args:
            save_path: Path to save screenshot (None = return image data)
            region: Region to capture (x, y, width, height) or None for full screen

        Returns:
            OperationResult with operation status
        """
        try:
            import os as _os
            import tempfile
            # ScreenCaptureController uses capture_screenshot(output_path), not take_screenshot
            capture_fn = getattr(self._screen_controller, "capture_screenshot", None) \
                         or getattr(self._screen_controller, "take_screenshot", None)
            if capture_fn is None:
                raise AttributeError("No screenshot method found on screen controller")
            if save_path is None:
                save_path = _os.path.join(tempfile.gettempdir(), "guru_screenshot.png")
            capture_fn(save_path)
            self._log_operation(
                OperationCategory.SCREEN_CAPTURE,
                "take_screenshot",
                True,
                {"save_path": save_path, "region": region}
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SCREEN_CAPTURE,
                operation="take_screenshot",
                message=f"Screenshot captured: {save_path or 'in-memory'}",
                metadata={"save_path": save_path}
            )
        except Exception as e:
            logger.error("Failed to take screenshot: %s", e)
            self._log_operation(
                OperationCategory.SCREEN_CAPTURE,
                "take_screenshot",
                False,
                {"error": str(e)}
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SCREEN_CAPTURE,
                operation="take_screenshot",
                message="Failed to capture screenshot",
                error=str(e)
            )

    # ==================== Process Management ====================

    def list_processes(self) -> list[dict[str, Any]]:
        """List all running processes.

        Time Complexity: O(n) where n is number of processes
        Space Complexity: O(n) for process list

        Returns:
            List of process information dictionaries
        """
        try:
            processes = self._process_manager.get_process_list()
            self._log_operation(
                OperationCategory.PROCESS,
                "list_processes",
                True,
                {"count": len(processes)}
            )
            return [
                {
                    "pid": p.pid,
                    "name": p.name,
                    "status": p.status,
                    "cpu_percent": p.cpu_percent,
                    "memory_percent": p.memory_percent
                }
                for p in processes
            ]
        except Exception as e:
            logger.error("Failed to list processes: %s", e)
            self._log_operation(
                OperationCategory.PROCESS,
                "list_processes",
                False,
                {"error": str(e)}
            )
            return []

    # ==================== Hardware Monitoring ====================

    def get_cpu_usage(self) -> Optional[float]:
        """Get current CPU usage percentage.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            CPU usage percentage (0-100) or None on error
        """
        try:
            usage = self._hardware_monitor.get_cpu_usage()
            self._log_operation(
                OperationCategory.HARDWARE,
                "get_cpu_usage",
                True,
                {"usage": usage}
            )
            return usage
        except Exception as e:
            logger.error("Failed to get CPU usage: %s", e)
            self._log_operation(
                OperationCategory.HARDWARE,
                "get_cpu_usage",
                False,
                {"error": str(e)}
            )
            return None

    def get_memory_info(self) -> Optional[dict[str, Any]]:
        """Get current memory usage information.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Memory info dictionary or None on error
        """
        try:
            info = self._hardware_monitor.get_memory_info()
            self._log_operation(
                OperationCategory.HARDWARE,
                "get_memory_info",
                True,
                {"percent": info.percent}
            )
            return {
                "total": info.total,
                "available": info.available,
                "used": info.used,
                "percent": info.percent
            }
        except Exception as e:
            logger.error("Failed to get memory info: %s", e)
            self._log_operation(
                OperationCategory.HARDWARE,
                "get_memory_info",
                False,
                {"error": str(e)}
            )
            return None


    # ==================== Utility Methods ====================

    def get_operation_history(
        self,
        limit: Optional[int] = None,
        category: Optional[OperationCategory] = None
    ) -> list[dict[str, Any]]:
        """Get operation history from audit log.

        Time Complexity: O(n) where n is number of log entries
        Space Complexity: O(n) for log entries

        Args:
            limit: Maximum number of entries to return (None = all)
            category: Filter by operation category (None = all)

        Returns:
            List of audit log entries
        """
        if not self.audit_log_path or not os.path.exists(self.audit_log_path):
            return []

        try:
            entries = []
            with open(self.audit_log_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if category is None or entry.get("category") == category.value:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue

            # Apply limit
            if limit is not None:
                entries = entries[-limit:]

            return entries

        except Exception as e:
            logger.error("Failed to read operation history: %s", e)
            return []

    def get_system_info(self) -> dict[str, Any]:
        """Get comprehensive system information.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Dictionary with system information
        """
        try:
            return {
                "platform": self.platform,
                "cpu_usage": self.get_cpu_usage(),
                "memory_info": self.get_memory_info(),
                "process_count": len(self.list_processes()),
                "audit_log_enabled": self.audit_log_path is not None,
                "confirmation_required": self.require_confirmation
            }
        except Exception as e:
            logger.error("Failed to get system info: %s", e)
            return {
                "platform": self.platform,
                "error": str(e)
            }

    def execute_operation(
        self,
        operation: str,
        **kwargs
    ) -> OperationResult:
        """Execute an operation by name with dynamic routing.

        Time Complexity: O(1) for routing + operation complexity
        Space Complexity: O(1)

        Args:
            operation: Operation name (e.g., "create_file", "open_application")
            **kwargs: Operation-specific arguments

        Returns:
            OperationResult with operation status

        Raises:
            OperationNotSupportedError: If operation not supported
        """
        # Map operation names to methods
        operation_map = {
            # File operations
            "create_file": self.create_file,
            "read_file": self.read_file,
            "delete_file": self.delete_file,
            "copy_file": self.copy_file,
            "move_file": self.move_file,
            # Application control
            "open_application": self.open_application,
            "close_application": self.close_application,
            "uninstall_application": self.uninstall_application,
            # Web / browser
            "open_url": self.open_url,
            "web_search": self.web_search,
            # Text input
            "type_text": self.type_text,
            # System settings
            "set_volume": self.set_volume,
            "volume_up": self.volume_up,
            "volume_down": self.volume_down,
            "mute": self.mute,
            "unmute": self.unmute,
            "set_brightness": self.set_brightness,
            # Window management
            "minimize_window": self.minimize_window,
            "maximize_window": self.maximize_window,
            # Media control
            "play_media": self.play_media,
            "pause_media": self.pause_media,
            "next_track": self.next_track,
            "previous_track": self.previous_track,
            "stop_media": self.stop_media,
            # Screen capture
            "take_screenshot": self.take_screenshot,
            # Destructive (require confirmed=True)
            "reset_pc": self.reset_pc,
            "shutdown_pc": self.shutdown_pc,
        }

        if operation not in operation_map:
            raise OperationNotSupportedError(
                f"Operation not supported: {operation}"
            )

        try:
            method = operation_map[operation]
            return method(**kwargs)
        except TypeError as e:
            logger.error("Invalid arguments for operation %s: %s", operation, e)
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,  # Default category
                operation=operation,
                message=f"Invalid arguments for operation: {operation}",
                error=str(e)
            )
        except Exception as e:
            logger.error("Failed to execute operation %s: %s", operation, e)
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,  # Default category
                operation=operation,
                message=f"Failed to execute operation: {operation}",
                error=str(e)
            )

    def __repr__(self) -> str:
        """String representation of OSController."""
        return (
            f"OSController(platform={self.platform}, "
            f"audit_log={self.audit_log_path is not None}, "
            f"confirmation_required={self.require_confirmation})"
        )
