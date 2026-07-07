"""System control tools for volume, brightness, WiFi, and Bluetooth.

Platform-specific implementations for Windows, macOS, and Linux.
"""

import logging
import platform
import subprocess  # nosec B404
from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool
from Agent_Guru.security.redaction import redact

logger = logging.getLogger(__name__)


class PlatformSystemController:
    """Platform-specific system control implementation."""

    @staticmethod
    def get_platform() -> str:
        """Get current platform."""
        return platform.system().lower()

    @staticmethod
    async def set_volume(level: int) -> dict[str, Any]:
        """Set system volume (platform-specific).

        Args:
            level: Volume level (0-100)

        Returns:
            Result dictionary

        """
        system = PlatformSystemController.get_platform()

        try:
            if system == "windows":
                ps_script = (
                    "$obj = New-Object -ComObject WScript.Shell; "
                    f"for ($i = 0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}; "
                    f"for ($i = 0; $i -lt {level * 2}; $i++) {{ $obj.SendKeys([char]175) }}"
                )
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["powershell", "-Command", ps_script],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to set volume: {result.stderr}"}
            elif system == "darwin":
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["osascript", "-e", f"set volume output volume {level}"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to set volume: {result.stderr}"}
            elif system == "linux":
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["amixer", "set", "Master", f"{level}%"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to set volume: {result.stderr}"}
            else:
                return {"success": False, "error": "Unsupported platform"}

            result_data = {
                "level": level,
                "message": f"Set volume to {level}%",
            }
            logger.info("Volume result: %s", redact(result_data))  # nosec B506
            return {"success": True, "result": result_data}

        except Exception as e:
            return {"success": False, "error": f"Failed to set volume: {e!s}"}

    @staticmethod
    async def set_brightness(level: int) -> dict[str, Any]:
        """Set screen brightness (platform-specific).

        Args:
            level: Brightness level (0-100)

        Returns:
            Result dictionary

        """
        system = PlatformSystemController.get_platform()

        try:
            if system == "windows":
                ps_script = (
                    "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
                    f".WmiSetBrightness(1,{level})"
                )
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["powershell", "-Command", ps_script],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to set brightness: {result.stderr}"}
            elif system == "darwin":
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["brightness", str(level / 100.0)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to set brightness: {result.stderr}"}
            elif system == "linux":
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["brightnessctl", "set", f"{level}%"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    result = subprocess.run(  # nosec B603 B607  # noqa: S603
                        ["xbacklight", "-set", str(level)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        return {
                            "success": False,
                            "error": f"Failed to set brightness: {result.stderr}",
                        }
            else:
                return {"success": False, "error": "Unsupported platform"}

            result_data = {
                "level": level,
                "message": f"Set brightness to {level}%",
            }
            logger.info("Brightness result: %s", redact(result_data))  # nosec B506
            return {"success": True, "result": result_data}

        except Exception as e:
            return {"success": False, "error": f"Failed to set brightness: {e!s}"}

    @staticmethod
    async def toggle_wifi(enable: bool) -> dict[str, Any]:
        """Toggle WiFi on/off (platform-specific).

        Args:
            enable: True to enable, False to disable

        Returns:
            Result dictionary

        """
        system = PlatformSystemController.get_platform()
        action = "enable" if enable else "disable"

        try:
            if system == "windows":
                state = "enable" if enable else "disable"
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["netsh", "interface", "set", "interface", "Wi-Fi", state],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to {action} WiFi: {result.stderr}"}
            elif system == "darwin":
                state = "on" if enable else "off"
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["networksetup", "-setairportpower", "en0", state],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to {action} WiFi: {result.stderr}"}
            elif system == "linux":
                state = "on" if enable else "off"
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["nmcli", "radio", "wifi", state],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {"success": False, "error": f"Failed to {action} WiFi: {result.stderr}"}
            else:
                return {"success": False, "error": "Unsupported platform"}

            result_data = {
                "enabled": enable,
                "message": f"WiFi {action}d",
            }
            logger.info("WiFi toggle result: %s", redact(result_data))  # nosec B506
            return {"success": True, "result": result_data}

        except Exception as e:
            return {"success": False, "error": f"Failed to {action} WiFi: {e!s}"}

    @staticmethod
    async def toggle_bluetooth(enable: bool) -> dict[str, Any]:
        """Toggle Bluetooth on/off (platform-specific).

        Args:
            enable: True to enable, False to disable

        Returns:
            Result dictionary

        """
        system = PlatformSystemController.get_platform()
        action = "enable" if enable else "disable"

        try:
            if system == "windows":
                state = "$true" if enable else "$false"
                ps_script = (
                    "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                    "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null; "
                    f"$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetAwaiter().GetResult(); "
                    "$bluetooth = $radios | Where-Object { $_.Kind -eq 'Bluetooth' }; "
                    f"$bluetooth.SetStateAsync({state}).GetAwaiter().GetResult() | Out-Null"
                )
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["powershell", "-Command", ps_script],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} Bluetooth: {result.stderr}",
                    }
            elif system == "darwin":
                state = "1" if enable else "0"
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["blueutil", "--power", state],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} Bluetooth: {result.stderr}",
                    }
            elif system == "linux":
                state = "unblock" if enable else "block"
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["rfkill", state, "bluetooth"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} Bluetooth: {result.stderr}",
                    }
            else:
                return {"success": False, "error": "Unsupported platform"}

            result_data = {
                "enabled": enable,
                "message": f"Bluetooth {action}d",
            }
            logger.info("Bluetooth toggle result: %s", redact(result_data))  # nosec B506
            return {"success": True, "result": result_data}

        except Exception as e:
            return {"success": False, "error": f"Failed to {action} Bluetooth: {e!s}"}


@tool(
    tool_id="system.set_volume",
    name="Set Volume",
    description="Set system volume level",
    parameters=[
        ToolParameter(
            name="level",
            type=ToolParameterType.INTEGER,
            description="Volume level (0-100)",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=200,
    capabilities=["system_control", "volume_control", "audio_control"],
    examples=[
        "Set volume to 50%",
        "Turn volume up to 80",
        "Set volume to maximum",
        "Lower volume to 20",
    ],
)
class SetVolumeTool(Tool):
    """Tool for setting system volume."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute volume setting.

        Args:
            level: Volume level (0-100)

        Returns:
            Execution result

        """
        level = kwargs["level"]
        if not 0 <= level <= 100:
            return {"success": False, "error": "Volume level must be between 0 and 100"}
        return await PlatformSystemController.set_volume(level)


@tool(
    tool_id="system.set_brightness",
    name="Set Brightness",
    description="Set screen brightness level",
    parameters=[
        ToolParameter(
            name="level",
            type=ToolParameterType.INTEGER,
            description="Brightness level (0-100)",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=200,
    capabilities=["system_control", "brightness_control", "display_control"],
    examples=[
        "Set brightness to 50%",
        "Increase brightness to 80",
        "Dim screen to 20",
        "Set brightness to maximum",
    ],
)
class SetBrightnessTool(Tool):
    """Tool for setting screen brightness."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute brightness setting.

        Args:
            level: Brightness level (0-100)

        Returns:
            Execution result

        """
        level = kwargs["level"]
        if not 0 <= level <= 100:
            return {"success": False, "error": "Brightness level must be between 0 and 100"}
        return await PlatformSystemController.set_brightness(level)


@tool(
    tool_id="system.toggle_wifi",
    name="Toggle WiFi",
    description="Enable or disable WiFi",
    parameters=[
        ToolParameter(
            name="enable",
            type=ToolParameterType.BOOLEAN,
            description="True to enable, False to disable",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=500,
    capabilities=["system_control", "wifi_control", "network_control"],
    examples=[
        "Turn on WiFi",
        "Disable WiFi",
        "Enable wireless",
        "Turn off WiFi",
    ],
)
class ToggleWifiTool(Tool):
    """Tool for toggling WiFi."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute WiFi toggling.

        Args:
            enable: True to enable, False to disable

        Returns:
            Execution result

        """
        enable = kwargs["enable"]
        return await PlatformSystemController.toggle_wifi(enable)


@tool(
    tool_id="system.toggle_bluetooth",
    name="Toggle Bluetooth",
    description="Enable or disable Bluetooth",
    parameters=[
        ToolParameter(
            name="enable",
            type=ToolParameterType.BOOLEAN,
            description="True to enable, False to disable",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=500,
    capabilities=["system_control", "bluetooth_control", "wireless_control"],
    examples=[
        "Turn on Bluetooth",
        "Disable Bluetooth",
        "Enable Bluetooth",
        "Turn off Bluetooth",
    ],
)
class ToggleBluetoothTool(Tool):
    """Tool for toggling Bluetooth."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute Bluetooth toggling.

        Args:
            enable: True to enable, False to disable

        Returns:
            Execution result

        """
        enable = kwargs["enable"]
        return await PlatformSystemController.toggle_bluetooth(enable)
