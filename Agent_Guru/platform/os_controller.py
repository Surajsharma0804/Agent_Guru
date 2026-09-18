"""Module: Agent_Guru.platform.os_controller
Purpose: Main OS Controller - Unified facade for complete laptop control.

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
import inspect
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Configure logging
logger = logging.getLogger(__name__)


def _import_optional(module_path: str, *class_names: str) -> tuple[Any, ...]:
    """Import *class_names* from *module_path*, isolating failures per-module.

    BUG FIX (found 2026-09-13): all eleven controller imports used to live in
    a single `try: ... except ImportError: logger.exception(...)` block.
    Every one of those classes is later constructed through `_safe_init()`,
    which clearly exists to isolate a single controller's failure from the
    rest (missing dependency, platform-unsupported feature, whatever) — but
    the shared import block undid that entirely: if even ONE of the eleven
    modules failed to import (an optional dependency like pyautogui missing,
    a platform-only module on the wrong OS, an unrelated bug in any single
    controller file), *every* class name from *every* module in that block
    was left unbound. `_init_controllers()` then referenced an undefined
    name directly (e.g. `FileOperationsController` in `_safe_init(
    FileOperationsController, ...)`), raising a bare `NameError` that
    propagates out of `_init_controllers()` and `__init__()` uncaught — not
    the graceful "some controllers unavailable" degradation the log message
    implied, but a hard crash of the *entire* OSController over one
    unrelated missing piece.

    Importing each module independently means a broken/missing module now
    only takes down the controller(s) it defines: this returns None for
    each requested class name instead of raising, and `_safe_init()`
    already handles a None class gracefully (`None(*args, **kwargs)` raises
    TypeError, which `_safe_init()` catches and turns into `None` — exactly
    the same "controller unavailable" outcome _safe_init() already produces
    for a class that imported fine but failed to construct).

    Args:
        module_path: Fully-qualified module to import.
        *class_names: Attribute name(s) to pull from that module.

    Returns:
        A tuple the same length as *class_names* — either the real classes,
        or None per name if the module could not be imported.

    """
    try:
        mod = __import__(module_path, fromlist=list(class_names))
    except ImportError:
        logger.warning(
            "Controller module unavailable (%s) — %s will be disabled, other "
            "controllers are unaffected",
            module_path,
            ", ".join(class_names),
            exc_info=True,
        )
        return tuple(None for _ in class_names)
    return tuple(getattr(mod, name, None) for name in class_names)


(ApplicationController,) = _import_optional(
    "Agent_Guru.platform.controllers.application_control", "ApplicationController",
)
(FileOperationsController,) = _import_optional(
    "Agent_Guru.platform.controllers.file_operations", "FileOperationsController",
)
KeyboardController, MouseController = _import_optional(
    "Agent_Guru.platform.controllers.input_control", "KeyboardController", "MouseController",
)
(MediaController,) = _import_optional(
    "Agent_Guru.platform.controllers.media_control", "MediaController",
)
(MessagingController,) = _import_optional(
    "Agent_Guru.platform.controllers.messaging_controller", "MessagingController",
)
(ScreenCaptureController,) = _import_optional(
    "Agent_Guru.platform.controllers.screen_capture", "ScreenCaptureController",
)
(SystemSettingsController,) = _import_optional(
    "Agent_Guru.platform.controllers.system_settings", "SystemSettingsController",
)
(TextInputController,) = _import_optional(
    "Agent_Guru.platform.controllers.text_input", "TextInputController",
)
(WindowManager,) = _import_optional(
    "Agent_Guru.platform.controllers.window_management", "WindowManager",
)
(HardwareMonitor,) = _import_optional(
    "Agent_Guru.platform.hardware.monitor", "HardwareMonitor",
)
(ProcessManager,) = _import_optional(
    "Agent_Guru.platform.process_manager", "ProcessManager",
)


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
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


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
    user: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert audit entry to JSON string."""
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "category": self.category,
                "operation": self.operation,
                "success": self.success,
                "user": self.user,
                "details": self.details,
            },
        )


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
        _file_base_dir: Sandbox root for all file operations (defaults to the
            user's home directory — see __init__'s file_base_dir docstring)
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
        audit_log_path: str | None = None,
        require_confirmation: bool = False,
        file_base_dir: str | Path | None = None,
    ) -> None:
        """Initialize OS controller.

        Args:
            audit_log_path: Path to audit log file (None = no logging)
            require_confirmation: Whether to require confirmation for destructive ops
            file_base_dir: Root directory that create_file/read_file/update_file/
                delete_file/copy_file/move_file are sandboxed to (see
                FileOperationsController's path-traversal protection in
                security/path_utils.py::safe_path). Defaults to the current
                user's home directory (covers Desktop/Documents/Downloads and
                everything else under it, on Windows/macOS/Linux alike).

                Found and fixed 2026-09-13: this used to be left unset when
                constructing FileOperationsController below, which made ITS
                own default apply instead — Path.cwd(), i.e. whatever
                directory the *process* happened to start in. For a desktop
                companion that can be launched from a shortcut, a terminal,
                or a service, that is not a stable or meaningful security
                boundary: depending on how Agent Guru was started, "create a
                file called notes.txt" could either be confined to a
                near-arbitrary install/launch directory (most user file
                locations then correctly rejected as "path traversal", which
                is the failure mode a user actually hit — not a crash, just a
                silently-too-narrow sandbox) or, if launched from a broad cwd,
                effectively unconfined. Defaulting to the user's home
                directory makes the sandbox boundary predictable, always
                covers the places a person actually asks to save files to,
                and does not depend on launch method.

        """
        self.audit_log_path = audit_log_path
        self.require_confirmation = require_confirmation
        self.platform = sys.platform
        self._file_base_dir: Path = (
            Path(file_base_dir).expanduser().resolve() if file_base_dir else Path.home().resolve()
        )

        # Initialize audit log
        if self.audit_log_path:
            self._init_audit_log()

        # Initialize all controllers
        self._init_controllers()

        logger.info("OSController initialized on platform: %s", self.platform)

    def _init_audit_log(self) -> None:
        """Initialize audit log file."""
        try:
            if self.audit_log_path is None:
                return
            audit_path = Path(self.audit_log_path)
            audit_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not audit_path.exists():
                audit_path.touch(mode=0o600)
            logger.info("Audit log initialized: %s", self.audit_log_path)
        except Exception:
            logger.exception("Failed to initialize audit log")

    def _init_controllers(self) -> None:
        """Initialize all specialized controllers with per-controller error isolation."""
        self._file_controller = self._safe_init(
            FileOperationsController,
            audit_log_path=self.audit_log_path,
            require_confirmation=self.require_confirmation,
            base_dir=self._file_base_dir,
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
        except Exception:
            getattr(cls, "__name__", repr(cls))
            logger.exception("Controller failed to initialize")
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
        except RuntimeError as e:
            logger.info("DesktopApplicationController not available on mobile platform: %s", e)
            return None
        except Exception:
            logger.exception("DesktopApplicationController failed to initialize")
            return None

    def _log_operation(
        self,
        category: OperationCategory,
        operation: str,
        success: bool,
        details: dict[str, Any] | None = None,
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
            timestamp=datetime.now(tz=UTC).isoformat(),
            category=category.value,
            operation=operation,
            success=success,
            user=os.getenv("USER") or os.getenv("USERNAME"),
            details=details or {},
        )

        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
        except Exception:
            logger.exception("Failed to write audit log")

    def _require_confirmation(self, operation: str, details: str) -> None:
        """Check if confirmation is required for destructive operation.

        Args:
            operation: Operation name
            details: Operation details

        Raises:
            ConfirmationRequiredError: If confirmation required but not provided

        """
        if self.require_confirmation:
            msg = f"Confirmation required for destructive operation: {operation} - {details}"
            raise ConfirmationRequiredError(
                msg,
            )

    # ==================== File Operations ====================

    def create_file(
        self,
        path: str,
        content: str | bytes = "",
        overwrite: bool = False,
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
                {"path": path, "size": len(content)},
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="create_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata,
            )
        except Exception as e:
            logger.exception("Failed to create file")
            self._log_operation(OperationCategory.FILE, "create_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="create_file",
                message=f"Failed to create file: {path}",
                error=str(e),
            )

    def read_file(
        self,
        path: str,
        binary: bool = False,
        encoding: str = "utf-8",
    ) -> str | bytes | None:
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
                {"path": path, "binary": binary},
            )
            return content
        except Exception as e:
            logger.exception("Failed to read file")
            self._log_operation(OperationCategory.FILE, "read_file", False, {"error": str(e)})
            return None

    def delete_file(self, path: str, confirm: bool = False) -> OperationResult:
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
                {"path": path},
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="delete_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata,
            )
        except Exception as e:
            logger.exception("Failed to delete file")
            self._log_operation(OperationCategory.FILE, "delete_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="delete_file",
                message=f"Failed to delete file: {path}",
                error=str(e),
            )

    def copy_file(self, source: str, destination: str, overwrite: bool = False) -> OperationResult:
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
                {"source": source, "destination": destination},
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="copy_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata,
            )
        except Exception as e:
            logger.exception("Failed to copy file")
            self._log_operation(OperationCategory.FILE, "copy_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="copy_file",
                message=f"Failed to copy file: {source} -> {destination}",
                error=str(e),
            )

    def move_file(self, source: str, destination: str, overwrite: bool = False) -> OperationResult:
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
                {"source": source, "destination": destination},
            )
            return OperationResult(
                success=result.success,
                category=OperationCategory.FILE,
                operation="move_file",
                message=result.message,
                error=result.error,
                metadata=result.metadata,
            )
        except Exception as e:
            logger.exception("Failed to move file")
            self._log_operation(OperationCategory.FILE, "move_file", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,
                operation="move_file",
                message=f"Failed to move file: {source} -> {destination}",
                error=str(e),
            )

    # ==================== Application Control ====================

    def open_application(self, app_name: str, args: list[str] | None = None) -> OperationResult:
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
                    success = asyncio.run(self._desktop_app_controller.open_app(app_name))
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
        try:
            pid = self._app_controller.open_application(app_name, args)
            self._log_operation(
                OperationCategory.APPLICATION,
                "open_application",
                True,
                {"app_name": app_name, "pid": pid},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.APPLICATION,
                operation="open_application",
                message=f"Application opened successfully: {app_name}",
                metadata={"pid": pid},
            )
        except Exception as e:
            logger.exception("Failed to open application")
            self._log_operation(
                OperationCategory.APPLICATION,
                "open_application",
                False,
                {"error": str(e)},
            )
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="open_application",
                message=f"Failed to open application: {app_name}",
                error=str(e),
            )

    def close_application(self, app_identifier: str, force: bool = False) -> OperationResult:
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
                {"app_identifier": app_identifier, "force": force},
            )
            return OperationResult(
                success=success,
                category=OperationCategory.APPLICATION,
                operation="close_application",
                message=f"Application closed: {app_identifier}",
                metadata={"force": force},
            )
        except Exception as e:
            logger.exception("Failed to close application")
            self._log_operation(
                OperationCategory.APPLICATION,
                "close_application",
                False,
                {"error": str(e)},
            )
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="close_application",
                message=f"Failed to close application: {app_identifier}",
                error=str(e),
            )

    # ==================== Text Input ====================

    def type_text(self, text: str, interval: float = 0.0) -> OperationResult:
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
                {"length": len(text)},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.TEXT_INPUT,
                operation="type_text",
                message=f"Text typed successfully ({len(text)} characters)",
                metadata={"length": len(text)},
            )
        except Exception as e:
            logger.exception("Failed to type text")
            self._log_operation(OperationCategory.TEXT_INPUT, "type_text", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.TEXT_INPUT,
                operation="type_text",
                message="Failed to type text",
                error=str(e),
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
                {"level": level},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_volume",
                message=f"Volume set to {level}%",
                metadata={"level": level},
            )
        except Exception as e:
            logger.exception("Failed to set volume")
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "set_volume",
                False,
                {"error": str(e)},
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_volume",
                message=f"Failed to set volume to {level}%",
                error=str(e),
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
                OperationCategory.SYSTEM_SETTINGS,
                "volume_up",
                True,
                {"amount": amount},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="volume_up",
                message=f"Volume increased by {amount}%",
                metadata={"amount": amount},
            )
        except Exception as e:
            logger.exception("Failed to increase volume")
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "volume_up",
                False,
                {"error": str(e)},
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
                OperationCategory.SYSTEM_SETTINGS,
                "volume_down",
                True,
                {"amount": amount},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="volume_down",
                message=f"Volume decreased by {amount}%",
                metadata={"amount": amount},
            )
        except Exception as e:
            logger.exception("Failed to decrease volume")
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "volume_down",
                False,
                {"error": str(e)},
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
            logger.exception("Failed to mute")
            self._log_operation(OperationCategory.SYSTEM_SETTINGS, "mute", False, {"error": str(e)})
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
            logger.exception("Failed to unmute")
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "unmute",
                False,
                {"error": str(e)},
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
                {"level": level},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_brightness",
                message=f"Brightness set to {level}%",
                metadata={"level": level},
            )
        except Exception as e:
            logger.exception("Failed to set brightness")
            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "set_brightness",
                False,
                {"error": str(e)},
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="set_brightness",
                message=f"Failed to set brightness to {level}%",
                error=str(e),
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
                {"window": window_identifier},
            )
            return OperationResult(
                success=success,
                category=OperationCategory.WINDOW,
                operation="minimize_window",
                message=f"Window minimized: {window_identifier}",
                metadata={"window": window_identifier},
            )
        except Exception as e:
            logger.exception("Failed to minimize window")
            self._log_operation(
                OperationCategory.WINDOW,
                "minimize_window",
                False,
                {"error": str(e)},
            )
            return OperationResult(
                success=False,
                category=OperationCategory.WINDOW,
                operation="minimize_window",
                message=f"Failed to minimize window: {window_identifier}",
                error=str(e),
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
                {"window": window_identifier},
            )
            return OperationResult(
                success=success,
                category=OperationCategory.WINDOW,
                operation="maximize_window",
                message=f"Window maximized: {window_identifier}",
                metadata={"window": window_identifier},
            )
        except Exception as e:
            logger.exception("Failed to maximize window")
            self._log_operation(
                OperationCategory.WINDOW,
                "maximize_window",
                False,
                {"error": str(e)},
            )
            return OperationResult(
                success=False,
                category=OperationCategory.WINDOW,
                operation="maximize_window",
                message=f"Failed to maximize window: {window_identifier}",
                error=str(e),
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
            self._log_operation(OperationCategory.MEDIA, "play_media", True, {})
            return OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="play_media",
                message="Media play command sent",
            )
        except Exception as e:
            logger.exception("Failed to play media")
            self._log_operation(OperationCategory.MEDIA, "play_media", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="play_media",
                message="Failed to play media",
                error=str(e),
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
            self._log_operation(OperationCategory.MEDIA, "pause_media", True, {})
            return OperationResult(
                success=True,
                category=OperationCategory.MEDIA,
                operation="pause_media",
                message="Media pause command sent",
            )
        except Exception as e:
            logger.exception("Failed to pause media")
            self._log_operation(OperationCategory.MEDIA, "pause_media", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="pause_media",
                message="Failed to pause media",
                error=str(e),
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
            logger.exception("Failed to skip track")
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
            logger.exception("Failed to go to previous track")
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
            logger.exception("Failed to stop media")
            return OperationResult(
                success=False,
                category=OperationCategory.MEDIA,
                operation="stop_media",
                message="Failed to stop media",
                error=str(e),
            )

    # ==================== Web / Browser ====================

    def open_url(self, url: str, browser: str | None = None) -> OperationResult:
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
                except Exception:
                    webbrowser.open(resolved)
            else:
                webbrowser.open(resolved)

            self._log_operation(OperationCategory.APPLICATION, "open_url", True, {"url": resolved})
            return OperationResult(
                success=True,
                category=OperationCategory.APPLICATION,
                operation="open_url",
                message=f"Opened URL: {resolved}",
                metadata={"url": resolved},
            )
        except Exception as e:
            logger.exception("Failed to open URL")
            self._log_operation(OperationCategory.APPLICATION, "open_url", False, {"error": str(e)})
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="open_url",
                message=f"Failed to open URL: {resolved}",
                error=str(e),
            )

    def web_search(self, query: str, engine: str = "google") -> OperationResult:
        """Perform a web search by opening the real system browser.

        Opens the search URL in the user's default browser (Chrome/Edge/Firefox).
        No automation — the user controls playback themselves.

        Args:
            query: Search query
            engine: Search engine ("google", "youtube", "bing")

        Returns:
            OperationResult with operation status

        """
        import urllib.parse

        engine = engine.lower().strip()

        _engines = {
            "google": "https://www.google.com/search?q=",
            "youtube": "https://www.youtube.com/results?search_query=",
            "bing": "https://www.bing.com/search?q=",
        }
        base = _engines.get(engine, _engines["google"])
        url = base + urllib.parse.quote_plus(query)
        return self.open_url(url)

    # ── YouTube Playwright helpers (used by web_search + orchestrator + demo) ──

    async def play_youtube_with_controls(
        self,
        query: str,
        screenshot_path: str | None = None,
        headless: bool = False,
        play_duration_s: float = 5.0,
        max_ad_wait_s: int = 30,
        on_status: Any | None = None,
        pre_close_callback: Any | None = None,
    ) -> dict[str, bool]:
        """Open YouTube, search *query*, skip any ad, play the song, then
        demonstrate pause / resume / mute / unmute / volume-up / volume-down.

        Args:
            query:               YouTube search query.
            screenshot_path:     Optional path to save a proof screenshot.
            headless:            Run browser headlessly (default False for demo).
            play_duration_s:     Seconds to let the song play before controls demo.
            max_ad_wait_s:       Max seconds to wait for a skippable ad.
            on_status:           Optional callable(str) for status messages.
            pre_close_callback:  Optional callable() called BEFORE browser.close()
                                 — use this to flush any pending TTS/speak tasks
                                 so they finish before the browser window disappears.

        Returns:
            Dict of step → bool indicating which steps succeeded.

        """
        import urllib.parse as _up

        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright

        def _log(msg: str) -> None:
            logger.info(msg)
            if on_status:
                on_status(msg)

        search_url = "https://www.youtube.com/results?search_query=" + _up.quote_plus(query)

        results: dict[str, bool] = {
            "browser_launched": False,
            "page_loaded": False,
            "video_found": False,
            "ad_handled": False,
            "video_played": False,
            "paused": False,
            "resumed": False,
            "muted": False,
            "unmuted": False,
            "volume_up": False,
            "volume_down": False,
            "screenshot_saved": False,
            "browser_closed": False,
        }

        async with async_playwright() as p:
            # Use real installed Chrome/Edge — not Playwright's bundled Chromium.
            # channel="chrome" uses the system Google Chrome (with all codecs,
            # user profile, saved passwords, YouTube login etc.)
            # Fallback chain: chrome → msedge → bundled chromium
            browser = None
            browser_channel = os.environ.get("AGENT_GURU_BROWSER_CHANNEL", "").strip()
            _channels_to_try = (
                [browser_channel]
                if browser_channel
                else ["chrome", "msedge", "chrome-beta", "msedge-beta"]
            )
            for _ch in _channels_to_try:
                try:
                    browser = await p.chromium.launch(
                        channel=_ch,
                        headless=headless,
                        args=["--disable-background-timer-throttling"],
                    )
                    _log(f"Browser launched (real {_ch}).")
                    break
                except Exception as _ch_err:
                    logger.exception("Channel '%s' unavailable: %s", _ch, _ch_err)
            if browser is None:
                # Try Firefox as last resort before bundled Chromium
                try:
                    browser = await p.firefox.launch(headless=headless)
                    _log("Browser launched (Firefox).")
                except Exception:
                    # Final fallback: bundled Playwright Chromium
                    browser = await p.chromium.launch(headless=headless)
                    _log(
                        "Browser launched (Playwright bundled Chromium — install Chrome for best experience).",
                    )
            results["browser_launched"] = True
            try:
                context = await browser.new_context(viewport={"width": 1440, "height": 900})
                page = await context.new_page()

                # Navigate to YouTube search
                _log(f"Navigating to YouTube search: {query}")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

                # Dismiss cookie / consent dialogs
                for selector in (
                    "button:has-text('Accept all')",
                    "button:has-text('I agree')",
                    "button:has-text('Reject all')",
                ):
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible(timeout=1200):
                            await btn.click()
                            _log("Dismissed consent dialog.")
                            break
                    except Exception:
                        logger.exception("Operation failed")
                # Click first video result
                _log("Waiting for first video result…")
                first_video = page.locator("ytd-video-renderer a#video-title").first
                await first_video.wait_for(state="visible", timeout=45000)
                await first_video.click(timeout=20000)
                results["video_found"] = True
                _log("First video clicked.")

                try:
                    await page.wait_for_url("**/watch**", timeout=30000)
                    results["page_loaded"] = True
                    _log("Watch page loaded.")
                except PlaywrightTimeoutError:
                    _log("Watch URL timeout — continuing anyway.")
                # Give the player time to initialise
                await page.wait_for_timeout(2500)

                # ── Step 1: Handle ad ─────────────────────────────────
                _log("Checking for ads…")
                await self._wait_for_ad_and_skip(
                    page,
                    max_wait_s=max_ad_wait_s,
                    on_status=on_status,
                )
                results["ad_handled"] = True

                # ── Step 2: Start playback ────────────────────────────
                video = page.locator("#movie_player video.html5-main-video").first
                await video.wait_for(state="attached", timeout=20000)
                await video.evaluate(
                    "async v => { v.muted = false; v.volume = 0.8; await v.play(); }",
                )
                results["video_played"] = True
                _log("Song is playing.")

                # ── Step 3: Skip 20 seconds into the song ────────────
                _log("Skipping 20 seconds into the song.")
                await video.evaluate(
                    "v => { v.currentTime = Math.min((v.duration || v.currentTime + 20), v.currentTime + 20); }",
                )
                # Wait for playback to stabilise after seek
                await page.wait_for_timeout(1500)

                # ── Step 4: Let song play for 10-15 seconds ───────────
                _log("Letting song play for 12s…")
                await page.wait_for_timeout(12000)

                # ── Step 5: Pause ─────────────────────────────────────
                _log("Pausing the video.")
                await video.evaluate("v => v.pause()")
                results["paused"] = True
                await page.wait_for_timeout(500)

                # ── Step 6: Resume ────────────────────────────────────
                _log("Resuming playback.")
                await video.evaluate("async v => { await v.play(); }")
                results["resumed"] = True
                await page.wait_for_timeout(3000)  # let song play a bit

                # ── Step 7: Mute ──────────────────────────────────────
                _log("Muting the video.")
                await video.evaluate("v => { v.muted = true; }")
                results["muted"] = True
                await page.wait_for_timeout(500)

                # ── Step 8: Unmute ────────────────────────────────────
                _log("Unmuting the video.")
                await video.evaluate("v => { v.muted = false; }")
                results["unmuted"] = True
                await page.wait_for_timeout(500)

                # ── Step 9: Volume up ─────────────────────────────────
                _log("Increasing volume.")
                await video.evaluate("v => { v.volume = Math.min(1.0, v.volume + 0.2); }")
                results["volume_up"] = True
                await page.wait_for_timeout(500)

                # ── Step 10: Volume down ──────────────────────────────
                _log("Decreasing volume.")
                await video.evaluate("v => { v.volume = Math.max(0.0, v.volume - 0.2); }")
                results["volume_down"] = True
                await page.wait_for_timeout(500)

                # ── Step 11: Screenshot ───────────────────────────────
                if screenshot_path:
                    snap = Path(screenshot_path)
                    snap.parent.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(snap), full_page=False)
                    results["screenshot_saved"] = True
                    _log(f"Screenshot saved: {snap.name}")

                # ── Step 12: Flush all pending TTS BEFORE closing ─────
                # This ensures "I am now closing YouTube" is spoken while
                # the browser is still open — not after it's already gone.
                _log("Closing YouTube now.")
                if pre_close_callback is not None:
                    try:
                        if inspect.iscoroutinefunction(pre_close_callback):
                            await pre_close_callback()
                        else:
                            await asyncio.get_running_loop().run_in_executor(
                                None,
                                pre_close_callback,
                            )
                    except Exception as _cb_err:
                        logger.exception("pre_close_callback error")
                # Small pause after TTS finishes so user hears it before close
                await page.wait_for_timeout(500)
                await page.close()
                await context.close()

            finally:
                await browser.close()
                results["browser_closed"] = True
                _log("Browser closed.")

        return results

    async def _skip_ad_if_present(self, page: Any) -> bool:
        """Click the YouTube Skip-Ad button if visible. Returns True if clicked."""
        skip_selectors = [
            ".ytp-skip-ad-button",
            ".ytp-ad-skip-button",
            "button.ytp-skip-ad-button",
            "button.ytp-ad-skip-button",
            "[class*='skip-ad']",
            "[class*='skip_ad']",
        ]
        for selector in skip_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=800):
                    await btn.click()
                    logger.info("Ad skip button clicked: %s", selector)
                    return True
            except Exception:
                logger.exception("Operation failed")
        return False

    async def _wait_for_ad_and_skip(
        self,
        page: Any,
        max_wait_s: int = 30,
        on_status: Any | None = None,
    ) -> bool:
        """Poll for a skippable ad for up to max_wait_s seconds.

        Returns True if an ad was skipped, False if no ad was found.
        """

        def _log(msg: str) -> None:
            logger.info(msg)
            if on_status:
                on_status(msg)

        loop = asyncio.get_event_loop()
        deadline = loop.time() + max_wait_s
        skipped = False

        while loop.time() < deadline:
            try:
                ad_showing = await page.evaluate(
                    "() => {"
                    "  const p = document.querySelector('#movie_player');"
                    "  return p ? p.classList.contains('ad-showing') : false;"
                    "}",
                )
            except Exception:
                break
            if ad_showing:
                _log("Ad detected — waiting for skip button…")
                skipped = await self._skip_ad_if_present(page)
                if skipped:
                    _log("Ad skipped.")
                    await page.wait_for_timeout(1000)
                    break
                await page.wait_for_timeout(1000)
            else:
                _log("No ad detected — proceeding.")
                break

        return skipped

    @staticmethod
    def _resolve_url(raw: str) -> str:
        """Resolve a raw string to a full URL.

        Args:
            raw: URL, domain, or search query

        Returns:
            Full URL string

        """
        import urllib.parse

        from Agent_Guru.platform.browser_manager import _resolve_site_url

        raw = raw.strip()

        # Known site name, already-a-URL, or www.-prefixed string —
        # delegates to the single canonical site registry in
        # browser_manager.py. This method used to keep its own separate
        # 15-entry `_shortcuts` copy — one of three duplicate site-name
        # registries found in the codebase (the others: orchestrator.py's
        # `_URL_MAP` and browser_manager.py's own original, smaller
        # table) — consolidated into one source of truth 2026-09-13.
        resolved = _resolve_site_url(raw)
        if resolved:
            return resolved

        # Looks like a domain (contains a dot, no spaces) but isn't a
        # known site name and has no scheme/www prefix for
        # _resolve_site_url() to recognize (e.g. "example.com").
        if "." in raw and " " not in raw:
            return f"https://{raw}"

        # Treat as a Google search query. This fallback is
        # OSController-specific: _resolve_site_url() deliberately returns
        # "" for an unrecognized bare word so ITS callers (browser_manager
        # .open_website()) can choose to search instead of guessing a
        # URL, but OSController.open_url()/web_search() always need a
        # concrete URL back, so the search-query fallback lives here.
        return "https://www.google.com/search?q=" + urllib.parse.quote_plus(raw)

    # ==================== Destructive / Permission-Required Operations ====================

    def uninstall_application(self, app_name: str, confirmed: bool = False) -> OperationResult:
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
            import subprocess  # nosec B404

            if self.platform == "win32":
                # Use winget if available, else warn
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["winget", "uninstall", "--name", app_name, "--silent"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                success = result.returncode == 0
                msg = result.stdout or result.stderr
            else:
                success = False
                msg = f"Uninstall not implemented for platform: {self.platform}"

            self._log_operation(
                OperationCategory.APPLICATION,
                "uninstall_application",
                success,
                {"app_name": app_name, "confirmed": confirmed},
            )
            return OperationResult(
                success=success,
                category=OperationCategory.APPLICATION,
                operation="uninstall_application",
                message=msg,
                metadata={"app_name": app_name},
            )
        except Exception as e:
            logger.exception("Failed to uninstall")
            return OperationResult(
                success=False,
                category=OperationCategory.APPLICATION,
                operation="uninstall_application",
                message=f"Failed to uninstall {app_name}",
                error=str(e),
            )

    @staticmethod
    def _try_run_power_command(cmd: list[str], wait_seconds: float = 3.0) -> tuple[bool, str | None]:
        """Launch a shutdown/reboot command and detect a fast non-interactive failure.

        BUG FIX (found 2026-09-13): reset_pc()/shutdown_pc() used to
        fire-and-forget `subprocess.Popen(["sudo", "shutdown", ...])` (or
        `["sudo", "reboot"]`/`["sudo", "poweroff"]`) on macOS/Linux and then
        unconditionally report success — but plain `sudo` with no cached
        credentials and no NOPASSWD entry blocks waiting for a password on
        stdin, which a detached Popen has no way to supply. That means the
        call could hang forever in the background while Agent Guru had
        already told the user "PC restarting now" — a real silent failure:
        nothing happens, and there is no way to tell from the returned
        OperationResult.

        This runs the *real* command (unchanged for the success path — it
        is not weakened to a dry run) but via `sudo -n` (non-interactive):
        if sudo would need a password, `-n` makes it fail immediately
        instead of blocking, so this can tell the difference between "the
        machine is actually going down" and "nothing happened because sudo
        needs a password Agent Guru cannot provide" within a few seconds,
        and report the latter honestly instead of claiming success.

        Args:
            cmd: Full command argv, e.g. ["sudo", "shutdown", "-r", "now"].
                A leading "sudo" gets "-n" inserted after it; commands that
                don't need sudo (there are none on this path today, but this
                stays generic) run as given.
            wait_seconds: How long to wait for a fast failure before
                concluding the command is genuinely proceeding (shutdown/
                reboot/poweroff themselves don't return until the machine
                actually goes down, so still running after this long is the
                success case, not a hang).

        Returns:
            (True, None) if the command launched and is proceeding (or
            exited 0). (False, detail) if it failed fast — e.g. sudo needs a
            password, or the binary doesn't exist.

        """
        import subprocess  # nosec B404

        run_cmd = [cmd[0], "-n", *cmd[1:]] if cmd and cmd[0] == "sudo" else list(cmd)

        try:
            proc = subprocess.Popen(  # nosec B603 B607
                run_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            return False, f"required command not found: {run_cmd[0]}"

        try:
            _, stderr_bytes = proc.communicate(timeout=wait_seconds)
        except subprocess.TimeoutExpired:
            # Still running with no fast failure — genuinely proceeding.
            return True, None

        if proc.returncode == 0:
            return True, None

        detail = (stderr_bytes or b"").decode(errors="replace").strip()
        if not detail and run_cmd[0] == "sudo":
            detail = "sudo requires a password in this context (no interactive terminal available)"
        return False, detail or f"exited with code {proc.returncode}"

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
            import subprocess  # nosec B404

            if self.platform == "win32":
                subprocess.Popen(["shutdown", "/r", "/t", "5"])  # nosec B603 B607
                msg = "PC will restart in 5 seconds"
            else:
                cmd = ["sudo", "shutdown", "-r", "now"] if self.platform == "darwin" else ["sudo", "reboot"]
                ok, detail = self._try_run_power_command(cmd)
                if not ok:
                    self._log_operation(
                        OperationCategory.SYSTEM_SETTINGS,
                        "reset_pc",
                        False,
                        {"confirmed": True, "error": detail},
                    )
                    return OperationResult(
                        success=False,
                        category=OperationCategory.SYSTEM_SETTINGS,
                        operation="reset_pc",
                        message=(
                            f"Could not restart the PC: {detail}. Configure passwordless "
                            f"sudo for '{cmd[1]}' (visudo -> NOPASSWD), or restart it manually."
                        ),
                        error="sudo_failed",
                    )
                msg = "PC restarting now"

            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "reset_pc",
                True,
                {"confirmed": True},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="reset_pc",
                message=msg,
            )
        except Exception as e:
            logger.exception("Failed to reset PC")
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
            import subprocess  # nosec B404

            if self.platform == "win32":
                subprocess.Popen(["shutdown", "/s", "/t", "5"])  # nosec B603 B607
                msg = "PC will shut down in 5 seconds"
            else:
                cmd = ["sudo", "shutdown", "-h", "now"] if self.platform == "darwin" else ["sudo", "poweroff"]
                ok, detail = self._try_run_power_command(cmd)
                if not ok:
                    self._log_operation(
                        OperationCategory.SYSTEM_SETTINGS,
                        "shutdown_pc",
                        False,
                        {"confirmed": True, "error": detail},
                    )
                    return OperationResult(
                        success=False,
                        category=OperationCategory.SYSTEM_SETTINGS,
                        operation="shutdown_pc",
                        message=(
                            f"Could not shut down the PC: {detail}. Configure passwordless "
                            f"sudo for '{cmd[1]}' (visudo -> NOPASSWD), or shut it down manually."
                        ),
                        error="sudo_failed",
                    )
                msg = "PC shutting down now"

            self._log_operation(
                OperationCategory.SYSTEM_SETTINGS,
                "shutdown_pc",
                True,
                {"confirmed": True},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SYSTEM_SETTINGS,
                operation="shutdown_pc",
                message=msg,
            )
        except Exception as e:
            logger.exception("Failed to shut down PC")
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
        save_path: str | None = None,
        region: tuple | None = None,
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
            import tempfile

            # ScreenCaptureController uses capture_screenshot(output_path), not take_screenshot
            capture_fn = getattr(self._screen_controller, "capture_screenshot", None) or getattr(
                self._screen_controller,
                "take_screenshot",
                None,
            )
            if capture_fn is None:
                msg = "No screenshot method found on screen controller"
                raise AttributeError(msg)
            if save_path is None:
                save_path = os.path.join(tempfile.gettempdir(), "guru_screenshot.png")
            capture_fn(save_path)
            self._log_operation(
                OperationCategory.SCREEN_CAPTURE,
                "take_screenshot",
                True,
                {"save_path": save_path, "region": region},
            )
            return OperationResult(
                success=True,
                category=OperationCategory.SCREEN_CAPTURE,
                operation="take_screenshot",
                message=f"Screenshot captured: {save_path or 'in-memory'}",
                metadata={"save_path": save_path},
            )
        except Exception as e:
            logger.exception("Failed to take screenshot")
            self._log_operation(
                OperationCategory.SCREEN_CAPTURE,
                "take_screenshot",
                False,
                {"error": str(e)},
            )
            return OperationResult(
                success=False,
                category=OperationCategory.SCREEN_CAPTURE,
                operation="take_screenshot",
                message="Failed to capture screenshot",
                error=str(e),
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
            # BUG FIX (found 2026-09-13): this called a method,
            # get_process_list(), that ProcessManager
            # (platform/process_manager.py) has never defined -- its real
            # method is list_processes(). Every call here raised
            # AttributeError, which the broad `except Exception` below
            # caught and silently turned into an empty list. The result:
            # "list processes" (and get_system_info()'s process_count,
            # which calls this method) has always reported zero processes,
            # no matter how many were actually running, with nothing
            # visible to the user -- only a debug-level exception log entry
            # buried per-call. A completely broken, always-failing feature
            # that looked, from the outside, like "no processes" instead of
            # "this is broken."
            processes = self._process_manager.list_processes()
            self._log_operation(
                OperationCategory.PROCESS,
                "list_processes",
                True,
                {"count": len(processes)},
            )
            return [
                {
                    "pid": p.pid,
                    "name": p.name,
                    "status": p.status,
                    "cpu_percent": p.cpu_percent,
                    "memory_percent": p.memory_percent,
                }
                for p in processes
            ]
        except Exception as e:
            logger.exception("Failed to list processes")
            self._log_operation(
                OperationCategory.PROCESS,
                "list_processes",
                False,
                {"error": str(e)},
            )
            return []

    # ==================== Hardware Monitoring ====================

    def get_cpu_usage(self) -> float | None:
        """Get current CPU usage percentage.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            CPU usage percentage (0-100) or None on error

        """
        try:
            usage = self._hardware_monitor.get_cpu_usage()
            self._log_operation(OperationCategory.HARDWARE, "get_cpu_usage", True, {"usage": usage})
            return usage
        except Exception as e:
            logger.exception("Failed to get CPU usage")
            self._log_operation(
                OperationCategory.HARDWARE,
                "get_cpu_usage",
                False,
                {"error": str(e)},
            )
            return None

    def get_memory_info(self) -> dict[str, Any] | None:
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
                {"percent": info.percent},
            )
            return {
                "total": info.total,
                "available": info.available,
                "used": info.used,
                "percent": info.percent,
            }
        except Exception as e:
            logger.exception("Failed to get memory info")
            self._log_operation(
                OperationCategory.HARDWARE,
                "get_memory_info",
                False,
                {"error": str(e)},
            )
            return None

    # ==================== Utility Methods ====================

    def get_operation_history(
        self,
        limit: int | None = None,
        category: OperationCategory | None = None,
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

        except Exception:
            logger.exception("Failed to read operation history")
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
                "confirmation_required": self.require_confirmation,
            }
        except Exception as e:
            logger.exception("Failed to get system info")
            return {"platform": self.platform, "error": str(e)}

    def execute_operation(self, operation: str, **kwargs) -> OperationResult:
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
            msg = f"Operation not supported: {operation}"
            raise OperationNotSupportedError(msg)

        try:
            method = operation_map[operation]
            result = method(**kwargs)
            if isinstance(result, OperationResult):
                return result
            return OperationResult(
                success=True,
                category=OperationCategory.FILE,
                operation=operation,
                message=str(result) if result is not None else "OK",
            )
        except TypeError as e:
            logger.exception("Invalid arguments for operation")
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,  # Default category
                operation=operation,
                message=f"Invalid arguments for operation: {operation}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("Failed to execute operation")
            return OperationResult(
                success=False,
                category=OperationCategory.FILE,  # Default category
                operation=operation,
                message=f"Failed to execute operation: {operation}",
                error=str(e),
            )

    def __repr__(self) -> str:
        """String representation of OSController."""
        return (
            f"OSController(platform={self.platform}, "
            f"audit_log={self.audit_log_path is not None}, "
            f"confirmation_required={self.require_confirmation})"
        )
