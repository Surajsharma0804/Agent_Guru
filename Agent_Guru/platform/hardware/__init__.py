"""Hardware monitoring package for Agent Guru.

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
    "AccelerometerData",
    "BatteryInfo",
    "CPUInfo",
    "CellularInfo",
    "DeviceInfo",
    "DiskInfo",
    "GPUInfo",
    "GyroscopeData",
    # Desktop hardware monitoring
    "HardwareMonitor",
    "LocationInfo",
    "MemoryInfo",
    "MobileBatteryInfo",
    # Mobile hardware monitoring
    "MobileHardwareMonitor",
    "NetworkInterface",
    "NetworkInterfaceStatus",
    "NetworkType",
    "ThermalState",
]
