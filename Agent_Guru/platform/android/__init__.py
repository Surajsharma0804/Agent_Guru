"""Android platform integration for AGENT_GURU.

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
    AppNotFoundError,
    BatteryInfo,
    NotificationConfig,
    PermissionDeniedError,
    PermissionStatus,
)
from .service import (
    AndroidForegroundService,
    AndroidServiceError,
    ServiceConfig,
    ServiceState,
    create_foreground_service,
    start_background_service,
)

__all__ = [
    # Service
    "AndroidForegroundService",
    # Integration
    "AndroidIntegration",
    "AndroidIntegrationError",
    "AndroidServiceError",
    "AppNotFoundError",
    "BatteryInfo",
    "NotificationConfig",
    "PermissionDeniedError",
    "PermissionStatus",
    "ServiceConfig",
    "ServiceState",
    "create_foreground_service",
    "start_background_service",
]
