"""
Sandboxing for third-party skills.

Provides isolated execution environment with resource limits and security controls.
"""

import asyncio
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ResourceLimits:
    """Resource limits for skill execution."""

    max_cpu_percent: int = 50  # Maximum CPU usage percentage
    max_memory_mb: int = 512  # Maximum memory in MB
    max_disk_mb: int = 100  # Maximum disk space in MB
    max_execution_time_s: int = 30  # Maximum execution time in seconds
    max_network_requests: int = 100  # Maximum network requests


@dataclass
class SandboxConfig:
    """Configuration for skill sandbox."""

    skill_id: str
    resource_limits: ResourceLimits
    allowed_endpoints: list[str]  # Allowed network endpoints
    temp_dir: Path  # Temporary directory for skill
    read_only_paths: list[Path]  # Read-only filesystem paths
    use_docker: bool = False  # Whether to use Docker for isolation


class SkillSandbox:
    """Sandbox for executing third-party skills."""

    def __init__(self, config: SandboxConfig):
        """Initialize skill sandbox.

        Args:
            config: Sandbox configuration
        """
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None

    async def execute(
        self, command: list[str], env: Optional[dict[str, str]] = None
    ) -> dict[str, Any]:
        """Execute a command in the sandbox.

        Args:
            command: Command to execute
            env: Environment variables

        Returns:
            Execution result

        Raises:
            TimeoutError: If execution exceeds time limit
            RuntimeError: If execution fails
        """
        if self.config.use_docker:
            return await self._execute_docker(command, env)
        else:
            return await self._execute_process(command, env)

    async def _execute_process(
        self, command: list[str], env: Optional[dict[str, str]] = None
    ) -> dict[str, Any]:
        """Execute command in isolated process.

        Args:
            command: Command to execute
            env: Environment variables

        Returns:
            Execution result
        """
        # Prepare environment
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        # Add resource limit environment variables
        exec_env["SKILL_MAX_MEMORY_MB"] = str(self.config.resource_limits.max_memory_mb)
        exec_env["SKILL_MAX_CPU_PERCENT"] = str(
            self.config.resource_limits.max_cpu_percent
        )

        # Create temporary directory
        temp_dir = self.config.temp_dir
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                *command,
                env=exec_env,
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            self.process = process

            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.resource_limits.max_execution_time_s,
                )

                return {
                    "success": process.returncode == 0,
                    "returncode": process.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                }

            except asyncio.TimeoutError:
                # Kill process on timeout
                process.kill()
                await process.wait()
                raise TimeoutError(
                    f"Execution exceeded {self.config.resource_limits.max_execution_time_s}s limit"
                )

        finally:
            self.process = None

    async def _execute_docker(
        self, command: list[str], env: Optional[dict[str, str]] = None
    ) -> dict[str, Any]:
        """Execute command in Docker container.

        Args:
            command: Command to execute
            env: Environment variables

        Returns:
            Execution result
        """
        # Build Docker run command
        docker_cmd = [
            "docker",
            "run",
            "--rm",  # Remove container after execution
            "--network=none",  # No network access by default
            f"--cpus={self.config.resource_limits.max_cpu_percent / 100}",
            f"--memory={self.config.resource_limits.max_memory_mb}m",
            f"--storage-opt=size={self.config.resource_limits.max_disk_mb}m",
            "--read-only",  # Read-only filesystem
            f"--tmpfs=/tmp:size={self.config.resource_limits.max_disk_mb}m",
            "--security-opt=no-new-privileges",
            "--cap-drop=ALL",  # Drop all capabilities
        ]

        # Add environment variables
        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        # Add volume mounts for read-only paths
        for path in self.config.read_only_paths:
            docker_cmd.extend(["-v", f"{path}:{path}:ro"])

        # Add temporary directory mount
        docker_cmd.extend(["-v", f"{self.config.temp_dir}:/workspace"])
        docker_cmd.extend(["-w", "/workspace"])

        # Add image and command
        docker_cmd.append("python:3.11-slim")  # Base image
        docker_cmd.extend(command)

        try:
            # Execute Docker command
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            self.process = process

            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.resource_limits.max_execution_time_s,
                )

                return {
                    "success": process.returncode == 0,
                    "returncode": process.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                }

            except asyncio.TimeoutError:
                # Kill container on timeout
                if process.pid:
                    subprocess.run(
                        ["docker", "kill", str(process.pid)],
                        capture_output=True,
                    )
                process.kill()
                await process.wait()
                raise TimeoutError(
                    f"Execution exceeded {self.config.resource_limits.max_execution_time_s}s limit"
                )

        finally:
            self.process = None

    async def cleanup(self) -> None:
        """Clean up sandbox resources."""
        # Kill process if still running
        if self.process:
            self.process.kill()
            await self.process.wait()
            self.process = None

        # Clean up temporary directory
        if self.config.temp_dir.exists():
            import shutil

            shutil.rmtree(self.config.temp_dir, ignore_errors=True)


class SandboxManager:
    """Manager for skill sandboxes."""

    def __init__(self):
        """Initialize sandbox manager."""
        self.sandboxes: dict[str, SkillSandbox] = {}
        self.temp_base_dir = Path(tempfile.gettempdir()) / "agent_guru_skills"
        self.temp_base_dir.mkdir(parents=True, exist_ok=True)

    def create_sandbox(
        self,
        skill_id: str,
        resource_limits: Optional[ResourceLimits] = None,
        allowed_endpoints: Optional[list[str]] = None,
        use_docker: bool = False,
    ) -> SkillSandbox:
        """Create a sandbox for a skill.

        Args:
            skill_id: Skill ID
            resource_limits: Resource limits
            allowed_endpoints: Allowed network endpoints
            use_docker: Whether to use Docker

        Returns:
            Created sandbox
        """
        # Create temporary directory for skill
        temp_dir = self.temp_base_dir / skill_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Create sandbox config
        config = SandboxConfig(
            skill_id=skill_id,
            resource_limits=resource_limits or ResourceLimits(),
            allowed_endpoints=allowed_endpoints or [],
            temp_dir=temp_dir,
            read_only_paths=[],
            use_docker=use_docker,
        )

        # Create sandbox
        sandbox = SkillSandbox(config)
        self.sandboxes[skill_id] = sandbox

        return sandbox

    def get_sandbox(self, skill_id: str) -> Optional[SkillSandbox]:
        """Get sandbox for a skill.

        Args:
            skill_id: Skill ID

        Returns:
            Sandbox or None if not found
        """
        return self.sandboxes.get(skill_id)

    async def cleanup_sandbox(self, skill_id: str) -> None:
        """Clean up sandbox for a skill.

        Args:
            skill_id: Skill ID
        """
        sandbox = self.sandboxes.get(skill_id)
        if sandbox:
            await sandbox.cleanup()
            del self.sandboxes[skill_id]

    async def cleanup_all(self) -> None:
        """Clean up all sandboxes."""
        for skill_id in list(self.sandboxes.keys()):
            await self.cleanup_sandbox(skill_id)


# Global sandbox manager instance
_global_manager = SandboxManager()


def get_sandbox_manager() -> SandboxManager:
    """Get the global sandbox manager instance.

    Returns:
        Global SandboxManager instance
    """
    return _global_manager
