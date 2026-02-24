"""
Platform Integration Controllers

This package provides specialized controllers for different types of
platform operations, enabling complete laptop control through voice commands.

Available Controllers:
    - FileOperationsController: Complete file and directory operations
    - ApplicationController: Application and window management
    - TextInputController: Text input and keyboard simulation
"""

from Agent_Guru.platform.controllers.file_operations import (
    FileOperationsController,
    FileOperationType,
    FileOperationResult,
    AuditLogEntry
)

from Agent_Guru.platform.controllers.application_control import (
    ApplicationController,
    ApplicationState,
    WindowInfo,
    ApplicationInfo
)

from Agent_Guru.platform.controllers.text_input import (
    TextInputController,
    TextInputConfig,
    TypingSpeed
)

__all__ = [
    "FileOperationsController",
    "FileOperationType",
    "FileOperationResult",
    "AuditLogEntry",
    "ApplicationController",
    "ApplicationState",
    "WindowInfo",
    "ApplicationInfo",
    "TextInputController",
    "TextInputConfig",
    "TypingSpeed"
]
