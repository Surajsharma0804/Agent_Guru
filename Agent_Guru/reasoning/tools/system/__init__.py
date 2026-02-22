"""
System tools for application control, file operations, and system control.

This module provides core system tools for Agent_Guru.
"""

from Agent_Guru.reasoning.tools.system.app_control import (
    OpenAppTool,
    CloseAppTool,
    SwitchAppTool,
)
from Agent_Guru.reasoning.tools.system.file_operations import (
    FileReadTool,
    FileWriteTool,
    FileDeleteTool,
    FileMoveTool,
    FileCopyTool,
)
from Agent_Guru.reasoning.tools.system.system_control import (
    SetVolumeTool,
    SetBrightnessTool,
    ToggleWifiTool,
    ToggleBluetoothTool,
)
from Agent_Guru.reasoning.tools.system.process_control import (
    ProcessListTool,
    ProcessKillTool,
)

__all__ = [
    # App control
    "OpenAppTool",
    "CloseAppTool",
    "SwitchAppTool",
    # File operations
    "FileReadTool",
    "FileWriteTool",
    "FileDeleteTool",
    "FileMoveTool",
    "FileCopyTool",
    # System control
    "SetVolumeTool",
    "SetBrightnessTool",
    "ToggleWifiTool",
    "ToggleBluetoothTool",
    # Process control
    "ProcessListTool",
    "ProcessKillTool",
]
