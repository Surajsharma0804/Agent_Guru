"""Process control tools for listing and killing processes.

Platform-specific implementations for Windows, macOS, and Linux.
"""

import logging
import platform
from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool
from Agent_Guru.reasoning.tools.system._command import run_cmd_async
from Agent_Guru.security.redaction import redact

logger = logging.getLogger(__name__)


class PlatformProcessController:
    """Platform-specific process control implementation."""

    @staticmethod
    def get_platform() -> str:
        """Get current platform."""
        return platform.system().lower()

    @staticmethod
    async def list_processes() -> dict[str, Any]:
        """List running processes (platform-specific).

        Returns:
            Result dictionary with process list

        """
        system = PlatformProcessController.get_platform()

        try:
            if system == "windows":
                # Windows: use tasklist
                returncode, stdout, stderr = await run_cmd_async(
                    ["tasklist", "/FO", "CSV", "/NH"],
                )
                if returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to list processes: {stderr}",
                    }

                # Parse CSV output
                processes = []
                for line in stdout.strip().split("\n"):
                    if line:
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2:
                            processes.append(
                                {
                                    "name": parts[0],
                                    "pid": parts[1],
                                },
                            )

            elif system in {"darwin", "linux"}:
                # macOS/Linux: use ps
                returncode, stdout, stderr = await run_cmd_async(["ps", "aux"])
                if returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to list processes: {stderr}",
                    }

                # Parse ps output
                processes = []
                lines = stdout.strip().split("\n")[1:]  # Skip header
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
                            },
                        )

            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            result_data = {
                "platform": system,
                "process_count": len(processes),
                "processes": processes[:100],  # Limit to first 100
                "message": f"Found {len(processes)} running processes",
            }
            logger.info("Process list result: %s", redact(result_data))
            return {
                "success": True,
                "result": result_data,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list processes: {e!s}",
            }

    @staticmethod
    async def kill_process(pid: int, force: bool = False) -> dict[str, Any]:
        """Kill a process by PID (platform-specific).

        Args:
            pid: Process ID to kill
            force: Force kill (SIGKILL on Unix, /F on Windows)

        Returns:
            Result dictionary

        """
        system = PlatformProcessController.get_platform()

        # SECURITY FIX (found 2026-09-13): this tool -- the actual
        # LLM-facing "kill process" tool the agent calls, reachable by bare
        # PID -- had ZERO protected-process check. platform/process_manager.py
        # (a separate, duplicate reimplementation of the same feature; see
        # the module docstring) got exactly this guard in an earlier audit
        # round after finding that a bare terminate_process(pid) call could
        # kill explorer.exe/lsass.exe/init with no protection at all. This
        # parallel implementation never got that fix because it exists
        # independently and wasn't discovered until this pass. Resolve the
        # real process name via psutil (never trust that a caller somehow
        # already knows the PID is safe) and refuse before ever touching
        # taskkill/kill. PID 1 is refused unconditionally, independent of
        # name resolution succeeding: on POSIX it is always the
        # init/systemd process no matter what a name lookup reports.
        # Lazy import: keeps reasoning/ free of a module-level platform/
        # dependency, matching the existing convention in this package
        # (see app_control.py's open_app()).
        from Agent_Guru.platform.protected_processes import (  # layer-exempt: lazy import avoids module-level reasoning→platform dependency
            is_protected_process_name,
        )

        if pid == 1:
            return {
                "success": False,
                "error": f"Refusing to kill protected process: PID={pid} (PID 1 is the OS's init/launch process)",
            }

        try:
            import psutil  # already a project dependency (see platform/process_manager.py)

            real_name = psutil.Process(pid).name()
        except Exception:
            # Process may not exist, or psutil may be unavailable -- either
            # way, fall through to the normal kill attempt below, which
            # will fail on its own (e.g. "no such process") with an honest
            # error rather than a fabricated protection claim.
            real_name = None

        if is_protected_process_name(real_name):
            return {
                "success": False,
                "error": f"Refusing to kill protected process: PID={pid} (resolved name={real_name!r})",
            }

        try:
            if system == "windows":
                # Windows: use taskkill
                cmd = ["taskkill", "/PID", str(pid)]
                if force:
                    cmd.append("/F")

                returncode, _stdout, stderr = await run_cmd_async(cmd)
                if returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to kill process {pid}: {stderr}",
                    }

            elif system in {"darwin", "linux"}:
                # macOS/Linux: use kill
                signal = "-9" if force else "-15"
                returncode, _stdout, stderr = await run_cmd_async(
                    ["kill", signal, str(pid)],
                )
                if returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to kill process {pid}: {stderr}",
                    }

            else:
                return {
                    "success": False,
                    "error": f"Unsupported platform: {system}",
                }

            result_data = {
                "pid": pid,
                "force": force,
                "platform": system,
                "message": f"Killed process {pid}",
            }
            logger.info("Process kill result: %s", redact(result_data))
            return {
                "success": True,
                "result": result_data,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to kill process: {e!s}",
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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
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
