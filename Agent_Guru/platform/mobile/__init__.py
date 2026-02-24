"""
Mobile platform integration package.

This package provides mobile-specific functionality including:
- Background service management for always-on operation
- Battery optimization and tracking
- Thermal state monitoring
- Sleep/wake cycle management
"""

from Agent_Guru.platform.mobile.background_service import (
    MobileBackgroundService,
    ServiceConfig,
    ServiceState,
    ThermalState,
    BatteryUsageStats,
    BatteryUsageTracker,
)

__all__ = [
    "MobileBackgroundService",
    "ServiceConfig",
    "ServiceState",
    "ThermalState",
    "BatteryUsageStats",
    "BatteryUsageTracker",
]
