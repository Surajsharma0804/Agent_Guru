"""
Hardware monitoring package for Agent Guru.

Provides cross-platform hardware monitoring with mobile-specific extensions.
"""

from Agent_Guru.platform.hardware.mobile_monitor import (
    AccelerometerData,
    CellularInfo,
    DeviceInfo,
    GyroscopeData,
    LocationInfo,
    MobileBatteryInfo,
    MobileHardwareMonitor,
    NetworkType,
    ThermalState,
)
from Agent_Guru.platform.hardware.monitor import (
    BatteryInfo,
    CPUInfo,
    DiskInfo,
    GPUInfo,
    HardwareMonitor,
    MemoryInfo,
    NetworkInterface,
    NetworkInterfaceStatus,
)

__all__ = [
    # Desktop hardware monitoring
    "HardwareMonitor",
    "CPUInfo",
    "MemoryInfo",
    "DiskInfo",
    "NetworkInterface",
    "NetworkInterfaceStatus",
    "GPUInfo",
    "BatteryInfo",
    # Mobile hardware monitoring
    "MobileHardwareMonitor",
    "MobileBatteryInfo",
    "CellularInfo",
    "LocationInfo",
    "AccelerometerData",
    "GyroscopeData",
    "DeviceInfo",
    "ThermalState",
    "NetworkType",
]
