"""Mobile platform integration package.

This package provides mobile-specific functionality including:
- Background service management for always-on operation
- Battery optimization and tracking
- Thermal state monitoring
- Sleep/wake cycle management
"""

from Agent_Guru.platform.mobile.background_service import (
    BatteryUsageStats,
    BatteryUsageTracker,
    MobileBackgroundService,
    ServiceConfig,
    ServiceState,
    ThermalState,
)

__all__ = [
    "BatteryUsageStats",
    "BatteryUsageTracker",
    "MobileBackgroundService",
    "ServiceConfig",
    "ServiceState",
    "ThermalState",
]
