"""Application control tools for opening, closing, and switching applications.

Platform-specific implementations for Windows, macOS, and Linux.
"""

import logging
import platform
import subprocess
from typing import Any

from Agent_Guru.platform.subprocess_utils import run_cmd
from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool
from Agent_Guru.security.redaction import redact

logger = logging.getLogger(__name__)


class PlatformAppController:
    """Platform-specific application control implementation."""

    @staticmethod
    def get_platform() -> str:
        """Get current platform."""
        return platform.system().lower()

    @staticmethod
    async def open_app(app_name: str) -> dict[str, Any]:
        """Open an application (platform-specific).

        Args:
            app_name: Application name or path

        Returns:
            Result dictionary with success status

        """
        system = PlatformAppController.get_platform()

        try:
            if system == "windows":
                # Windows: use cmd /c start to launch via App Paths registry
                run_cmd(["cmd", "/c", "start", "", app_name], check=False)  # nosec B603 B607
            elif system == "darwin":
                # macOS: use open command
                subprocess.Popen(["open", "-a", app_name])  # nosec B603 B607  # noqa: S603
            elif system == "linux":
                # Linux: try common methods
                try:
                    subprocess.Popen([app_name])  # nosec B603 B607  # noqa: S603
                except FileNotFoundError:
                    # Try with xdg-open
                    subprocess.Popen(["xdg-open", app_name])  # nosec B603 B607  # noqa: S603
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",  # nosec B200
                }

            result_data = {
                "app_name": app_name,
                "platform": system,
                "message": f"Opened {app_name}",
            }
            logger.info("App open result: %s", redact(result_data))  # nosec B200 — redacted before logging
            return {
                "success": True,
                "result": result_data,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to open {app_name}: {e!s}",  # nosec B200
            }

    @staticmethod
    async def close_app(app_name: str) -> dict[str, Any]:
        """Close an application (platform-specific).

        Args:
            app_name: Application name or process name

        Returns:
            Result dictionary with success status

        """
        system = PlatformAppController.get_platform()

        try:
            if system == "windows":
                # Windows: use taskkill
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["taskkill", "/F", "/IM", f"{app_name}.exe"],  # noqa: S607
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to close {app_name}: {result.stderr}",  # nosec B200
                    }
            elif system == "darwin":
                # macOS: use osascript to quit application
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["osascript", "-e", f'quit app "{app_name}"'],  # noqa: S607
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to close {app_name}: {result.stderr}",  # nosec B200
                    }
            elif system == "linux":
                # Linux: use pkill
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["pkill", "-f", app_name],  # noqa: S607
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode not in {0, 1}:
                    # returncode 1 means no process found, which is acceptable
                    return {
                        "success": False,
                        "error": f"Failed to close {app_name}: {result.stderr}",  # nosec B200
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",  # nosec B200
                }

            result_data = {
                "app_name": app_name,
                "platform": system,
                "message": f"Closed {app_name}",
            }
            logger.info("App close result: %s", redact(result_data))  # nosec B200 — redacted before logging
            return {
                "success": True,
                "result": result_data,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to close {app_name}: {e!s}",  # nosec B200
            }

    @staticmethod
    async def switch_app(app_name: str) -> dict[str, Any]:
        """Switch to an application (bring to foreground).

        Args:
            app_name: Application name

        Returns:
            Result dictionary with success status

        """
        system = PlatformAppController.get_platform()

        try:
            if system == "windows":
                # Windows: use PowerShell to bring window to front
                ps_script = f"""
                $app = Get-Process | Where-Object {{$_.MainWindowTitle -like "*{app_name}*"}} | Select-Object -First 1
                if ($app) {{
                    $wshell = New-Object -ComObject wscript.shell
                    $wshell.AppActivate($app.Id)
                }}
                """
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["powershell", "-Command", ps_script],  # noqa: S607
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to switch to {app_name}: {result.stderr}",  # nosec B200
                    }
            elif system == "darwin":
                # macOS: use osascript to activate application
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["osascript", "-e", f'tell application "{app_name}" to activate'],  # noqa: S607
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to switch to {app_name}: {result.stderr}",  # nosec B200
                    }
            elif system == "linux":
                # Linux: use wmctrl if available
                result = subprocess.run(  # nosec B603 B607  # noqa: S603
                    ["wmctrl", "-a", app_name],  # noqa: S607
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to switch to {app_name}: {result.stderr}",  # nosec B200
                    }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            return {
                "success": True,
                "result": {
                    "app_name": app_name,
                    "platform": system,
                    "message": f"Switched to {app_name}",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to switch to {app_name}: {e!s}",  # nosec B200
            }


@tool(
    tool_id="app.open",
    name="Open Application",
    description="Open an application by name or path",
    parameters=[
        ToolParameter(
            name="app_name",
            type=ToolParameterType.STRING,
            description="Application name or path to open",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=500,
    capabilities=["app_control", "system_control", "launch_app"],
    examples=[
        "Open Chrome",
        "Open Notepad",
        "Launch Visual Studio Code",
        "Open Calculator",
    ],
)
class OpenAppTool(Tool):
    """Tool for opening applications."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute application opening.

        Args:
            app_name: Application name or path

        Returns:
            Execution result

        """
        app_name = kwargs["app_name"]

        if not app_name or not app_name.strip():
            return {
                "success": False,
                "error": "Application name cannot be empty",
            }

        return await PlatformAppController.open_app(app_name)


@tool(
    tool_id="app.close",
    name="Close Application",
    description="Close a running application",
    parameters=[
        ToolParameter(
            name="app_name",
            type=ToolParameterType.STRING,
            description="Application name or process name to close",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=500,
    capabilities=["app_control", "system_control", "close_app"],
    examples=[
        "Close Chrome",
        "Close Notepad",
        "Quit Visual Studio Code",
        "Close Calculator",
    ],
)
class CloseAppTool(Tool):
    """Tool for closing applications."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute application closing.

        Args:
            app_name: Application name or process name

        Returns:
            Execution result

        """
        app_name = kwargs["app_name"]

        if not app_name or not app_name.strip():
            return {
                "success": False,
                "error": "Application name cannot be empty",
            }

        return await PlatformAppController.close_app(app_name)


@tool(
    tool_id="app.switch",
    name="Switch Application",
    description="Switch to an application (bring to foreground)",
    parameters=[
        ToolParameter(
            name="app_name",
            type=ToolParameterType.STRING,
            description="Application name to switch to",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=300,
    capabilities=["app_control", "system_control", "switch_app", "focus_app"],
    examples=[
        "Switch to Chrome",
        "Go to Notepad",
        "Focus on Visual Studio Code",
        "Bring Calculator to front",
    ],
)
class SwitchAppTool(Tool):
    """Tool for switching to applications."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute application switching.

        Args:
            app_name: Application name

        Returns:
            Execution result

        """
        app_name = kwargs["app_name"]

        if not app_name or not app_name.strip():
            return {
                "success": False,
                "error": "Application name cannot be empty",
            }

        return await PlatformAppController.switch_app(app_name)
