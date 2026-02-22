"""
System control tools for volume, brightness, WiFi, and Bluetooth.

Platform-specific implementations for Windows, macOS, and Linux.
"""

import asyncio
import platform
import subprocess
from typing import Any, Dict

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


class PlatformSystemController:
    """Platform-specific system control implementation."""

    @staticmethod
    def get_platform() -> str:
        """Get current platform."""
        return platform.system().lower()

    @staticmethod
    async def set_volume(level: int) -> Dict[str, Any]:
        """Set system volume (platform-specific).

        Args:
            level: Volume level (0-100)

        Returns:
            Result dictionary
        """
        system = PlatformSystemController.get_platform()

        try:
            if system == "windows":
                # Windows: use nircmd or PowerShell
                ps_script = f"""
                $obj = New-Object -ComObject WScript.Shell
                for ($i = 0; $i -lt 50; $i++) {{
                    $obj.SendKeys([char]174)
                }}
                for ($i = 0; $i -lt {level * 2}; $i++) {{
                    $obj.SendKeys([char]175)
                }}
                """
                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to set volume: {result.stderr}",
                    }
            elif system == "darwin":
                # macOS: use osascript
                result = subprocess.run(
                    ["osascript", "-e", f"set volume output volume {level}"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to set volume: {result.stderr}",
                    }
            elif system == "linux":
                # Linux: use amixer
                result = subprocess.run(
                    ["amixer", "set", "Master", f"{level}%"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to set volume: {result.stderr}",
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            return {
                "success": True,
                "result": {
                    "level": level,
                    "platform": system,
                    "message": f"Set volume to {level}%",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to set volume: {str(e)}",
            }

    @staticmethod
    async def set_brightness(level: int) -> Dict[str, Any]:
        """Set screen brightness (platform-specific).

        Args:
            level: Brightness level (0-100)

        Returns:
            Result dictionary
        """
        system = PlatformSystemController.get_platform()

        try:
            if system == "windows":
                # Windows: use PowerShell WMI
                ps_script = f"""
                (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})
                """
                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to set brightness: {result.stderr}",
                    }
            elif system == "darwin":
                # macOS: use brightness command if available
                result = subprocess.run(
                    ["brightness", str(level / 100.0)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to set brightness: {result.stderr}",
                    }
            elif system == "linux":
                # Linux: use xrandr or brightnessctl
                result = subprocess.run(
                    ["brightnessctl", "set", f"{level}%"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    # Try xbacklight as fallback
                    result = subprocess.run(
                        ["xbacklight", "-set", str(level)],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        return {
                            "success": False,
                            "error": f"Failed to set brightness: {result.stderr}",
                        }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            return {
                "success": True,
                "result": {
                    "level": level,
                    "platform": system,
                    "message": f"Set brightness to {level}%",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to set brightness: {str(e)}",
            }

    @staticmethod
    async def toggle_wifi(enable: bool) -> Dict[str, Any]:
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
                # Windows: use netsh
                state = "enable" if enable else "disable"
                result = subprocess.run(
                    ["netsh", "interface", "set", "interface", "Wi-Fi", state],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} WiFi: {result.stderr}",
                    }
            elif system == "darwin":
                # macOS: use networksetup
                state = "on" if enable else "off"
                result = subprocess.run(
                    ["networksetup", "-setairportpower", "en0", state],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} WiFi: {result.stderr}",
                    }
            elif system == "linux":
                # Linux: use nmcli
                state = "on" if enable else "off"
                result = subprocess.run(
                    ["nmcli", "radio", "wifi", state],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} WiFi: {result.stderr}",
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            return {
                "success": True,
                "result": {
                    "enabled": enable,
                    "platform": system,
                    "message": f"WiFi {action}d",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to {action} WiFi: {str(e)}",
            }

    @staticmethod
    async def toggle_bluetooth(enable: bool) -> Dict[str, Any]:
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
                # Windows: use PowerShell
                state = "$true" if enable else "$false"
                ps_script = f"""
                Add-Type -AssemblyName System.Runtime.WindowsRuntime
                $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
                Function Await($WinRtTask, $ResultType) {{
                    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
                    $netTask = $asTask.Invoke($null, @($WinRtTask))
                    $netTask.Wait(-1) | Out-Null
                    $netTask.Result
                }}
                [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
                [Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
                Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
                $radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
                $bluetooth = $radios | ? {{ $_.Kind -eq 'Bluetooth' }}
                [Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
                Await ($bluetooth.SetStateAsync({state})) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
                """
                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} Bluetooth: {result.stderr}",
                    }
            elif system == "darwin":
                # macOS: use blueutil if available
                state = "1" if enable else "0"
                result = subprocess.run(
                    ["blueutil", "--power", state],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} Bluetooth: {result.stderr}",
                    }
            elif system == "linux":
                # Linux: use rfkill
                state = "unblock" if enable else "block"
                result = subprocess.run(
                    ["rfkill", state, "bluetooth"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to {action} Bluetooth: {result.stderr}",
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            return {
                "success": True,
                "result": {
                    "enabled": enable,
                    "platform": system,
                    "message": f"Bluetooth {action}d",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to {action} Bluetooth: {str(e)}",
            }


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
        )
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute volume setting.

        Args:
            level: Volume level (0-100)

        Returns:
            Execution result
        """
        level = kwargs["level"]

        # Validate level
        if not 0 <= level <= 100:
            return {
                "success": False,
                "error": "Volume level must be between 0 and 100",
            }

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
        )
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute brightness setting.

        Args:
            level: Brightness level (0-100)

        Returns:
            Execution result
        """
        level = kwargs["level"]

        # Validate level
        if not 0 <= level <= 100:
            return {
                "success": False,
                "error": "Brightness level must be between 0 and 100",
            }

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
        )
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
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
        )
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute Bluetooth toggling.

        Args:
            enable: True to enable, False to disable

        Returns:
            Execution result
        """
        enable = kwargs["enable"]
        return await PlatformSystemController.toggle_bluetooth(enable)
