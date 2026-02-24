"""
Agent Guru Platform Controllers

Specialized controllers for different types of system operations.
"""

from Agent_Guru.platform.controllers.system_settings import (
    SystemSettingsController,
    VolumeInfo,
    BrightnessInfo,
    NetworkInfo,
    DisplayInfo,
    SystemSettingsError,
    UnsupportedOperationError,
    InvalidSettingValueError,
)

from Agent_Guru.platform.controllers.window_management import (
    WindowManager,
    SnapPosition,
    ArrangementStyle,
    ScreenInfo,
    VirtualDesktopInfo,
)

from Agent_Guru.platform.controllers.media_control import (
    MediaController,
    MediaState,
    MediaControlError,
    UnsupportedMediaOperationError,
    MediaCommandError,
)

__all__ = [
    "SystemSettingsController",
    "VolumeInfo",
    "BrightnessInfo",
    "NetworkInfo",
    "DisplayInfo",
    "SystemSettingsError",
    "UnsupportedOperationError",
    "InvalidSettingValueError",
    "WindowManager",
    "SnapPosition",
    "ArrangementStyle",
    "ScreenInfo",
    "VirtualDesktopInfo",
    "MediaController",
    "MediaState",
    "MediaControlError",
    "UnsupportedMediaOperationError",
    "MediaCommandError",
]
