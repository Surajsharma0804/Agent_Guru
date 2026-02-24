"""
Android platform integration for AGENT_GURU.

This package provides comprehensive Android platform control including:
- Intent system for app launching
- Accessibility Service for UI automation
- Storage Access Framework for file operations
- NotificationManager integration
- Permission request flows
- ForegroundService implementation
- Battery optimization handling

Example:
    >>> from Agent_Guru.platform.android import AndroidIntegration
    >>> integration = AndroidIntegration()
    >>> integration.launch_app_by_package("com.whatsapp")
    True
"""

from .integration import (
    AndroidIntegration,
    AndroidIntegrationError,
    PermissionDeniedError,
    AppNotFoundError,
    PermissionStatus,
    BatteryInfo,
    NotificationConfig,
)

from .service import (
    AndroidForegroundService,
    AndroidServiceError,
    ServiceState,
    ServiceConfig,
    create_foreground_service,
    start_background_service,
)

__all__ = [
    # Integration
    "AndroidIntegration",
    "AndroidIntegrationError",
    "PermissionDeniedError",
    "AppNotFoundError",
    "PermissionStatus",
    "BatteryInfo",
    "NotificationConfig",
    # Service
    "AndroidForegroundService",
    "AndroidServiceError",
    "ServiceState",
    "ServiceConfig",
    "create_foreground_service",
    "start_background_service",
]
