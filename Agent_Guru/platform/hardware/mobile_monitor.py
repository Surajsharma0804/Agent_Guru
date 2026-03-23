"""
Module: Agent_Guru.platform.hardware.mobile_monitor
Purpose: Mobile-specific hardware monitoring (Android/iOS)

Performance Requirements:
- Time Complexity: O(1) per metric query
- Space Complexity: O(1) (no unbounded growth)
- Query Response: <1 second (all metrics)
- Battery Optimization: Minimal impact on battery life

Design Decisions:
- Platform-specific implementations for Android/iOS
- Graceful degradation for unavailable sensors
- Permission-aware (returns None if permission denied)
- Thermal state monitoring for adaptive behavior

Author: Agent Guru Team
Date: 2026-02-24
Version: 1.0.0
"""

import platform
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ThermalState(Enum):
    """Device thermal state."""
    NORMAL = "normal"
    FAIR = "fair"
    SERIOUS = "serious"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class NetworkType(Enum):
    """Cellular network type."""
    UNKNOWN = "unknown"
    GPRS = "gprs"
    EDGE = "edge"
    UMTS = "umts"
    CDMA = "cdma"
    EVDO_0 = "evdo_0"
    EVDO_A = "evdo_a"
    RTT = "1xrtt"
    HSDPA = "hsdpa"
    HSUPA = "hsupa"
    HSPA = "hspa"
    IDEN = "iden"
    EVDO_B = "evdo_b"
    LTE = "lte"
    EHRPD = "ehrpd"
    HSPAP = "hspap"
    GSM = "gsm"
    TD_SCDMA = "td_scdma"
    IWLAN = "iwlan"
    NR = "5g"  # 5G


@dataclass
class MobileBatteryInfo:
    """Mobile battery information with temperature.

    Attributes:
        percent: Battery percentage (0-100)
        is_charging: Whether battery is charging
        temperature: Battery temperature in Celsius
        voltage: Battery voltage in millivolts
        health: Battery health status
        technology: Battery technology (e.g., "Li-ion")
    """
    percent: float
    is_charging: bool
    temperature: Optional[float]
    voltage: Optional[int]
    health: Optional[str]
    technology: Optional[str]


@dataclass
class CellularInfo:
    """Cellular network information.

    Attributes:
        network_type: Type of cellular network
        signal_strength: Signal strength (0-4 bars or dBm)
        carrier_name: Carrier/operator name
        is_roaming: Whether device is roaming
    """
    network_type: NetworkType
    signal_strength: int
    carrier_name: Optional[str]
    is_roaming: bool


@dataclass
class LocationInfo:
    """GPS location information.

    Attributes:
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        altitude: Altitude in meters
        accuracy: Accuracy in meters
        timestamp: Timestamp of location fix
    """
    latitude: float
    longitude: float
    altitude: Optional[float]
    accuracy: float
    timestamp: float


@dataclass
class AccelerometerData:
    """Accelerometer sensor data.

    Attributes:
        x: X-axis acceleration in m/s²
        y: Y-axis acceleration in m/s²
        z: Z-axis acceleration in m/s²
        timestamp: Timestamp of reading
    """
    x: float
    y: float
    z: float
    timestamp: float


@dataclass
class GyroscopeData:
    """Gyroscope sensor data.

    Attributes:
        x: X-axis rotation rate in rad/s
        y: Y-axis rotation rate in rad/s
        z: Z-axis rotation rate in rad/s
        timestamp: Timestamp of reading
    """
    x: float
    y: float
    z: float
    timestamp: float


@dataclass
class DeviceInfo:
    """Mobile device information.

    Attributes:
        model: Device model name
        manufacturer: Device manufacturer
        os_version: Operating system version
        screen_width: Screen width in pixels
        screen_height: Screen height in pixels
        screen_dpi: Screen DPI
    """
    model: str
    manufacturer: str
    os_version: str
    screen_width: int
    screen_height: int
    screen_dpi: int


class MobileHardwareMonitor:
    """Mobile-specific hardware monitor for Android and iOS.

    Time Complexity: O(1) per metric query
    Space Complexity: O(1) (no unbounded growth)
    Query Response: <1 second (all metrics)

    Note: This is a base implementation. Platform-specific implementations
    should be provided by AndroidIntegration and IOSIntegration classes.

    Example:
        >>> monitor = MobileHardwareMonitor()
        >>> battery = monitor.get_battery_info()
        >>> if battery:
        ...     print(f"Battery: {battery.percent}%, Temp: {battery.temperature}°C")
        >>> thermal = monitor.get_thermal_state()
        >>> print(f"Thermal state: {thermal.value}")
    """

    def __init__(self) -> None:
        """Initialize mobile hardware monitor."""
        self._platform = platform.system()

    def get_battery_info(self) -> Optional[MobileBatteryInfo]:
        """Get mobile battery information with temperature.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            MobileBatteryInfo or None if unavailable

        Note: Requires BATTERY_STATS permission on Android
        """
        # Platform-specific implementation required
        # This is a placeholder that returns None
        return None

    def get_battery_temperature(self) -> Optional[float]:
        """Get battery temperature in Celsius.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Temperature in Celsius or None if unavailable
        """
        battery_info = self.get_battery_info()
        return battery_info.temperature if battery_info else None

    def get_screen_brightness(self) -> Optional[int]:
        """Get screen brightness level.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Brightness level (0-255) or None if unavailable

        Note: Requires WRITE_SETTINGS permission on Android
        """
        # Platform-specific implementation required
        return None

    def set_screen_brightness(self, level: int) -> bool:
        """Set screen brightness level.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            level: Brightness level (0-255)

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If level is out of range
            PermissionError: If WRITE_SETTINGS permission not granted
        """
        if not 0 <= level <= 255:
            raise ValueError(f"Brightness level must be 0-255, got {level}")

        # Platform-specific implementation required
        raise PermissionError("WRITE_SETTINGS permission required")

    def get_cellular_info(self) -> Optional[CellularInfo]:
        """Get cellular network information.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            CellularInfo or None if unavailable

        Note: Requires READ_PHONE_STATE permission on Android
        """
        # Platform-specific implementation required
        return None

    def get_location(self) -> Optional[LocationInfo]:
        """Get GPS location.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            LocationInfo or None if unavailable

        Raises:
            PermissionError: If location permission not granted

        Note: Requires ACCESS_FINE_LOCATION permission
        """
        # Platform-specific implementation required
        return None

    def get_accelerometer_data(self) -> Optional[AccelerometerData]:
        """Get accelerometer sensor data.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            AccelerometerData or None if unavailable
        """
        # Platform-specific implementation required
        return None

    def get_gyroscope_data(self) -> Optional[GyroscopeData]:
        """Get gyroscope sensor data.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            GyroscopeData or None if unavailable
        """
        # Platform-specific implementation required
        return None

    def get_thermal_state(self) -> ThermalState:
        """Get device thermal state.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            ThermalState indicating current thermal condition

        Note: Used for adaptive behavior (throttle when overheating)
        """
        # Platform-specific implementation required
        # Default to UNKNOWN if not implemented
        return ThermalState.UNKNOWN

    def is_low_power_mode(self) -> bool:
        """Check if device is in low power mode.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            True if low power mode is active, False otherwise

        Note: iOS: Low Power Mode, Android: Battery Saver
        """
        # Platform-specific implementation required
        return False

    def get_device_info(self) -> DeviceInfo:
        """Get device information.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            DeviceInfo with device details

        Raises:
            RuntimeError: If device info cannot be retrieved
        """
        # Platform-specific implementation required
        # Return placeholder data
        return DeviceInfo(
            model="Unknown",
            manufacturer="Unknown",
            os_version=platform.version(),
            screen_width=0,
            screen_height=0,
            screen_dpi=0
        )

    def should_throttle(self) -> bool:
        """Determine if operations should be throttled.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            True if should throttle (low battery or high temperature)

        Decision Logic:
        - Battery <20%: Throttle
        - Thermal state SERIOUS or CRITICAL: Throttle
        - Low power mode active: Throttle
        """
        # Check battery level
        battery = self.get_battery_info()
        if battery and battery.percent < 20:
            return True

        # Check thermal state
        thermal = self.get_thermal_state()
        if thermal in (ThermalState.SERIOUS, ThermalState.CRITICAL):
            return True

        # Check low power mode
        if self.is_low_power_mode():
            return True

        return False

    def get_adaptive_config(self) -> tuple[bool, str]:
        """Get adaptive configuration based on device state.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Returns:
            Tuple of (should_reduce_processing, reason)

        Example:
            >>> monitor = MobileHardwareMonitor()
            >>> should_reduce, reason = monitor.get_adaptive_config()
            >>> if should_reduce:
            ...     print(f"Reducing processing: {reason}")
        """
        battery = self.get_battery_info()
        thermal = self.get_thermal_state()
        low_power = self.is_low_power_mode()

        # Critical thermal state - highest priority
        if thermal == ThermalState.CRITICAL:
            return True, "Critical thermal state - pausing operations"

        # Serious thermal state
        if thermal == ThermalState.SERIOUS:
            return True, "High temperature - reducing processing"

        # Very low battery
        if battery and battery.percent < 10:
            return True, "Very low battery (<10%) - minimal processing"

        # Low battery
        if battery and battery.percent < 20:
            return True, "Low battery (<20%) - reduced processing"

        # Low power mode
        if low_power:
            return True, "Low power mode active - reduced processing"

        return False, "Normal operation"
