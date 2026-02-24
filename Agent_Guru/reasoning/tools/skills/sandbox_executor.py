"""
Skill sandbox executor with resource limits and permission checking.

Integrates SkillSandbox with the skill execution pipeline, providing:
- Permission checking before execution
- Resource monitoring during execution
- Cleanup after execution
- Error handling for sandbox violations
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass

from Agent_Guru.reasoning.error.error_manager import (
    ErrorContext,
    ErrorType,
    get_error_manager,
)
from Agent_Guru.reasoning.models.skill import Permission, InstalledSkill
from Agent_Guru.reasoning.tools.skills.sandbox import (
    SkillSandbox,
    SandboxConfig,
    ResourceLimits,
    get_sandbox_manager,
)
from Agent_Guru.reasoning.tools.skills.permissions import get_permission_manager


@dataclass
class ExecutionResult:
    """Result of skill execution."""

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    resource_usage: Optional[Dict[str, Any]] = None


class SkillSandboxExecutor:
    """Executor for skills with sandboxing and permission checking."""

    def __init__(self):
        """Initialize sandbox executor."""
        self.sandbox_manager = get_sandbox_manager()
        self.permission_manager = get_permission_manager()
        self._execution_count = 0
        self._violation_count = 0

    async def execute_skill(
        self,
        skill: InstalledSkill,
        entry_point: str,
        parameters: Dict[str, Any],
        user_id: str,
    ) -> ExecutionResult:
        """Execute a skill with sandboxing and permission checking.

        Args:
            skill: Installed skill to execute
            entry_point: Entry point to execute
            parameters: Parameters for execution
            user_id: User ID for permission checking

        Returns:
            Execution result

        Raises:
            ValueError: If permission denied or sandbox violation (with user-friendly message)
            TimeoutError: If execution exceeds time limit
        """
        start_time = time.perf_counter()
        self._execution_count += 1

        try:
            # Step 1: Check permissions
            await self._check_permissions(skill, user_id)

            # Step 2: Create sandbox environment
            sandbox = await self._create_sandbox(skill)

            # Step 3: Execute skill in sandbox
            result = await self._execute_in_sandbox(
                sandbox, skill, entry_point, parameters
            )

            # Step 4: Validate result
            await self._validate_result(result)

            # Step 5: Cleanup
            await self._cleanup_sandbox(skill.manifest.skill_id)

            # Calculate execution time
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)

            return ExecutionResult(
                success=True,
                result=result.get("result"),
                execution_time_ms=execution_time_ms,
                resource_usage=result.get("resource_usage"),
            )

        except ValueError as e:
            # Handle permission denied and sandbox violations
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            error_msg = str(e)
            
            # Track violation if it's a sandbox issue
            if "sandbox" in error_msg.lower() or "violation" in error_msg.lower():
                self._violation_count += 1
                await self._cleanup_sandbox(skill.manifest.skill_id)
            
            return ExecutionResult(
                success=False,
                error=error_msg,
                execution_time_ms=execution_time_ms,
            )

        except TimeoutError as e:
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            await self._cleanup_sandbox(skill.manifest.skill_id)
            return ExecutionResult(
                success=False,
                error=f"Execution timeout: {str(e)}",
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            await self._cleanup_sandbox(skill.manifest.skill_id)
            return ExecutionResult(
                success=False,
                error=f"Execution failed: {str(e)}",
                execution_time_ms=execution_time_ms,
            )

    async def _check_permissions(
        self, skill: InstalledSkill, user_id: str
    ) -> None:
        """Check if skill has required permissions.

        Args:
            skill: Skill to check
            user_id: User ID

        Raises:
            ValueError: If required permissions not granted (with user-friendly message)
        """
        error_manager = get_error_manager()
        
        # Check each required permission
        for permission in skill.manifest.required_permissions:
            if not self.permission_manager.check_permission(
                skill.manifest.skill_id, permission
            ):
                # Request permission if not granted
                granted = await self.permission_manager.request_permission(
                    skill_id=skill.manifest.skill_id,
                    permission=permission,
                    reason=f"Required by {skill.manifest.name}",
                    auto_grant=False,
                )

                if not granted:
                    context = ErrorContext(
                        user_id=user_id,
                        tool_id=skill.manifest.skill_id,
                        additional_data={
                            "permission": permission.value,
                            "skill_name": skill.manifest.name,
                        }
                    )
                    error = error_manager.create_error(
                        error_type=ErrorType.PERMISSION_DENIED,
                        message=f"Permission {permission.value} required but not granted",
                        context=context,
                    )
                    raise ValueError(error.user_message)

    async def _create_sandbox(self, skill: InstalledSkill) -> SkillSandbox:
        """Create sandbox environment for skill.

        Args:
            skill: Skill to create sandbox for

        Returns:
            Created sandbox
        """
        # Get or create sandbox
        sandbox = self.sandbox_manager.get_sandbox(skill.manifest.skill_id)

        if sandbox is None:
            # Create resource limits from manifest
            resource_limits = ResourceLimits(
                max_cpu_percent=50,
                max_memory_mb=512,
                max_disk_mb=100,
                max_execution_time_s=skill.manifest.max_latency // 1000 or 30,
                max_network_requests=100,
            )

            # Get allowed endpoints from manifest metadata
            allowed_endpoints = skill.manifest.metadata.get(
                "allowed_endpoints", []
            )

            # Create sandbox
            sandbox = self.sandbox_manager.create_sandbox(
                skill_id=skill.manifest.skill_id,
                resource_limits=resource_limits,
                allowed_endpoints=allowed_endpoints,
                use_docker=False,  # Use process isolation by default
            )

        return sandbox

    async def _execute_in_sandbox(
        self,
        sandbox: SkillSandbox,
        skill: InstalledSkill,
        entry_point: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute skill in sandbox.

        Args:
            sandbox: Sandbox to execute in
            skill: Skill to execute
            entry_point: Entry point to execute
            parameters: Parameters for execution

        Returns:
            Execution result

        Raises:
            ValueError: If sandbox constraints violated (with user-friendly message)
            TimeoutError: If execution exceeds time limit
        """
        error_manager = get_error_manager()
        
        # Get entry point command from manifest
        if entry_point not in skill.manifest.entry_points:
            raise ValueError(f"Entry point '{entry_point}' not found in manifest")

        entry_point_cmd = skill.manifest.entry_points[entry_point]

        # Build command
        command = ["python", "-c", entry_point_cmd]

        # Build environment with parameters
        env = {
            "SKILL_ID": skill.manifest.skill_id,
            "SKILL_VERSION": skill.manifest.version,
            "SKILL_PARAMETERS": str(parameters),
        }

        # Execute in sandbox
        try:
            result = await sandbox.execute(command, env)

            # Check for sandbox violations
            if not result["success"]:
                stderr = result.get("stderr", "")
                context = ErrorContext(
                    tool_id=skill.manifest.skill_id,
                    additional_data={
                        "entry_point": entry_point,
                        "stderr": stderr[:500],
                    }
                )
                
                if "MemoryError" in stderr or "memory" in stderr.lower():
                    error = error_manager.create_error(
                        error_type=ErrorType.RESOURCE_EXHAUSTED,
                        message="Memory limit exceeded",
                        context=context,
                    )
                    raise ValueError(error.user_message)
                elif "timeout" in stderr.lower():
                    error = error_manager.create_error(
                        error_type=ErrorType.TIMEOUT,
                        message="Execution time limit exceeded",
                        context=context,
                    )
                    raise ValueError(error.user_message)
                else:
                    error = error_manager.create_error(
                        error_type=ErrorType.TOOL_EXECUTION_FAILED,
                        message=f"Execution failed: {stderr}",
                        context=context,
                    )
                    raise ValueError(error.user_message)

            # Parse result
            stdout = result.get("stdout", "")
            return {
                "result": stdout,
                "resource_usage": {
                    "returncode": result.get("returncode", 0),
                },
            }

        except TimeoutError:
            raise TimeoutError(
                f"Skill execution exceeded {sandbox.config.resource_limits.max_execution_time_s}s limit"
            )

    async def _validate_result(self, result: Dict[str, Any]) -> None:
        """Validate execution result.

        Args:
            result: Result to validate

        Raises:
            ValueError: If result is invalid (with user-friendly message)
        """
        error_manager = get_error_manager()
        
        # Check result structure
        if "result" not in result:
            error = error_manager.create_error(
                error_type=ErrorType.TOOL_EXECUTION_FAILED,
                message="Result missing 'result' field",
            )
            raise ValueError(error.user_message)

        # Check result size (max 1MB)
        result_str = str(result["result"])
        if len(result_str) > 1024 * 1024:
            error = error_manager.create_error(
                error_type=ErrorType.RESOURCE_EXHAUSTED,
                message="Result exceeds 1MB size limit",
            )
            raise ValueError(error.user_message)

    async def _cleanup_sandbox(self, skill_id: str) -> None:
        """Cleanup sandbox after execution.

        Args:
            skill_id: Skill ID
        """
        try:
            await self.sandbox_manager.cleanup_sandbox(skill_id)
        except Exception as e:
            # Log cleanup error but don't fail
            print(f"Failed to cleanup sandbox for {skill_id}: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_executions": self._execution_count,
            "sandbox_violations": self._violation_count,
            "violation_rate": (
                self._violation_count / self._execution_count
                if self._execution_count > 0
                else 0.0
            ),
        }


# Global executor instance
_global_executor: Optional[SkillSandboxExecutor] = None


def get_sandbox_executor() -> SkillSandboxExecutor:
    """Get the global sandbox executor instance.

    Returns:
        Global SkillSandboxExecutor instance
    """
    global _global_executor
    if _global_executor is None:
        _global_executor = SkillSandboxExecutor()
    return _global_executor
