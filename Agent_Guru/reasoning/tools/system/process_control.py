"""
Process control tools for listing and killing processes.

Platform-specific implementations for Windows, macOS, and Linux.
"""

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


class PlatformProcessController:
    """Platform-specific process control implementation."""

    @staticmethod
    def get_platform() -> str:
        """Get current platform."""
        return platform.system().lower()

    @staticmethod
    async def list_processes() -> Dict[str, Any]:
        """List running processes (platform-specific).

        Returns:
            Result dictionary with process list
        """
        system = PlatformProcessController.get_platform()

        try:
            if system == "windows":
                # Windows: use tasklist
                result = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to list processes: {result.stderr}",
                    }

                # Parse CSV output
                processes = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2:
                            processes.append(
                                {
                                    "name": parts[0],
                                    "pid": parts[1],
                                }
                            )

            elif system == "darwin" or system == "linux":
                # macOS/Linux: use ps
                result = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to list processes: {result.stderr}",
                    }

                # Parse ps output
                processes = []
                lines = result.stdout.strip().split("\n")[1:]  # Skip header
                for line in lines:
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        processes.append(
                            {
                                "user": parts[0],
                                "pid": parts[1],
                                "cpu": parts[2],
                                "mem": parts[3],
                                "command": parts[10],
                            }
                        )

            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            return {
                "success": True,
                "result": {
                    "platform": system,
                    "process_count": len(processes),
                    "processes": processes[:100],  # Limit to first 100
                    "message": f"Found {len(processes)} running processes",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list processes: {str(e)}",
            }

    @staticmethod
    async def kill_process(pid: int, force: bool = False) -> Dict[str, Any]:
        """Kill a process by PID (platform-specific).

        Args:
            pid: Process ID to kill
            force: Force kill (SIGKILL on Unix, /F on Windows)

        Returns:
            Result dictionary
        """
        system = PlatformProcessController.get_platform()

        try:
            if system == "windows":
                # Windows: use taskkill
                cmd = ["taskkill", "/PID", str(pid)]
                if force:
                    cmd.append("/F")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to kill process {pid}: {result.stderr}",
                    }

            elif system == "darwin" or system == "linux":
                # macOS/Linux: use kill
                signal = "-9" if force else "-15"
                result = subprocess.run(
                    ["kill", signal, str(pid)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to kill process {pid}: {result.stderr}",
                    }

            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            return {
                "success": True,
                "result": {
                    "pid": pid,
                    "force": force,
                    "platform": system,
                    "message": f"Killed process {pid}",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to kill process: {str(e)}",
            }


@tool(
    tool_id="process.list",
    name="List Processes",
    description="List all running processes",
    parameters=[],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=500,
    capabilities=["process_control", "system_info", "list_processes"],
    examples=[
        "Show running processes",
        "List all processes",
        "What processes are running",
    ],
)
class ProcessListTool(Tool):
    """Tool for listing processes."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute process listing.

        Returns:
            Execution result with process list
        """
        return await PlatformProcessController.list_processes()


@tool(
    tool_id="process.kill",
    name="Kill Process",
    description="Kill a process by PID",
    parameters=[
        ToolParameter(
            name="pid",
            type=ToolParameterType.INTEGER,
            description="Process ID to kill",
            required=True,
        ),
        ToolParameter(
            name="force",
            type=ToolParameterType.BOOLEAN,
            description="Force kill the process (default: false)",
            required=False,
            default=False,
        ),
    ],
    sensitivity=ToolSensitivity.DANGEROUS,
    estimated_latency_ms=300,
    capabilities=["process_control", "kill_process", "terminate_process"],
    examples=[
        "Kill process 1234",
        "Force kill process 5678",
        "Terminate process 9999",
    ],
)
class ProcessKillTool(Tool):
    """Tool for killing processes."""

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute process killing.

        Args:
            pid: Process ID
            force: Force kill

        Returns:
            Execution result
        """
        pid = kwargs["pid"]
        force = kwargs.get("force", False)

        # Validate PID
        if pid <= 0:
            return {
                "success": False,
                "error": "Process ID must be positive",
            }

        return await PlatformProcessController.kill_process(pid, force)
