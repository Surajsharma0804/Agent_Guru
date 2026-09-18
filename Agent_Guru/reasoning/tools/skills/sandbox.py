"""Sandboxing for third-party skills.

Provides isolated execution environment with resource limits and security controls.
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

# Maximum combined stdout/stderr bytes read from a sandboxed process before
# it is killed. Matches the 1MB result-size cap sandbox_executor.py already
# enforces on the *returned* result -- this enforces the same limit while
# reading, so a chatty process can't inflate this process's memory before
# that check ever runs (see _read_stream_capped()).
_MAX_OUTPUT_BYTES = 1024 * 1024

# How long to wait for a killed subprocess to actually be reaped before
# giving up (see _kill_and_wait()'s docstring for why this exists at all).
_PROCESS_REAP_GRACE_S = 5.0

# Environment variables that may be safely inherited by a sandboxed skill
# subprocess. SECURITY FIX (Round 14): _execute_process() previously did
# `exec_env = os.environ.copy()`, handing third-party skill code the ENTIRE
# parent process environment -- including anything sensitive an operator or
# another subsystem might have set there (API keys, tokens, connection
# strings). A skill has no legitimate need for any of that; only what
# `python` and basic OS plumbing need to run is allowlisted here. Anything
# skill-specific is passed explicitly via the `env` parameter instead.
_SAFE_ENV_ALLOWLIST = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",  # Windows: required by many stdlib/socket operations
    "SYSTEMDRIVE",
    "COMSPEC",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "PYTHONIOENCODING",
)


@dataclass
class ResourceLimits:
    """Resource limits for skill execution."""

    max_cpu_percent: int = 50  # Maximum CPU usage percentage
    max_memory_mb: int = 512  # Maximum memory in MB
    max_disk_mb: int = 100  # Maximum disk space in MB
    max_execution_time_s: int = 30  # Maximum execution time in seconds
    max_network_requests: int = 100  # Maximum network requests


def _build_sandbox_env(
    extra: dict[str, str] | None,
    limits: ResourceLimits,
) -> dict[str, str]:
    """Build a minimal subprocess environment for skill execution.

    Only the explicit allowlist above is inherited from the parent process;
    `extra` (the skill-specific parameters/ids the caller builds) is then
    applied on top, so nothing else from this process's environment reaches
    the skill.
    """
    exec_env = {key: os.environ[key] for key in _SAFE_ENV_ALLOWLIST if key in os.environ}
    if extra:
        exec_env.update(extra)
    exec_env["SKILL_MAX_MEMORY_MB"] = str(limits.max_memory_mb)
    exec_env["SKILL_MAX_CPU_PERCENT"] = str(limits.max_cpu_percent)
    return exec_env


def _make_resource_limiter(limits: ResourceLimits):
    """Return a preexec_fn applying best-effort POSIX resource limits.

    RESOURCE-LIMIT FIX (Round 14): max_cpu_percent/max_memory_mb were
    previously passed to the child ONLY as informational environment
    variables (SKILL_MAX_MEMORY_MB / SKILL_MAX_CPU_PERCENT) that nothing
    ever read back -- an attacker-controlled subprocess would have had to
    voluntarily enforce limits on itself. This applies real, kernel-enforced
    limits via `resource.setrlimit`, executed in the child after fork() and
    before exec(), so they hold regardless of what the child's own code
    does: RLIMIT_CPU bounds CPU seconds (using max_execution_time_s as a
    hard backstop alongside the existing wall-clock timeout), and RLIMIT_AS
    bounds total address space to approximately max_memory_mb.

    Returns None on non-POSIX platforms: Windows has no equivalent
    lightweight primitive here (Job Objects would be the real equivalent
    and are a separate, larger piece of work), so no resource limiting is
    applied there beyond the existing wall-clock timeout.
    """
    if os.name != "posix":
        return None

    import resource

    cpu_seconds = max(1, limits.max_execution_time_s)
    mem_bytes = max(1, limits.max_memory_mb) * 1024 * 1024

    # OBSERVABILITY FIX: setrlimit() below runs in the forked child, between
    # fork() and exec(), where only async-signal-safe work is permitted --
    # calling into logging there can deadlock if another thread held a logging
    # lock at fork time. So the child genuinely cannot report anything, and a
    # sandbox silently running third-party skill code with NO CPU or memory
    # ceiling looked exactly like a working one.
    # The one failure mode that is knowable up front -- this process's own hard
    # limit being below what the sandbox wants to impose, which makes the
    # child's setrlimit raise -- is therefore checked HERE, in the parent,
    # where reporting is safe.
    for res_name, requested in (("RLIMIT_CPU", cpu_seconds), ("RLIMIT_AS", mem_bytes)):
        res_id = getattr(resource, res_name, None)
        if res_id is None:  # pragma: no cover - platform dependent
            _logger.warning(
                "Sandbox cannot enforce %s on this platform; skills run without "
                "that ceiling",
                res_name,
            )
            continue
        try:
            _soft, hard = resource.getrlimit(res_id)
        except (ValueError, OSError):  # pragma: no cover - platform dependent
            _logger.warning(
                "Sandbox could not read %s; resource limiting may not be enforced",
                res_name,
            )
            continue
        if hard != resource.RLIM_INFINITY and requested > hard:
            _logger.warning(
                "Sandbox %s cannot be set to %s: this process's hard limit is %s. "
                "Sandboxed skills will run under the lower inherited ceiling "
                "instead of the configured one.",
                res_name,
                requested,
                hard,
            )

    def _apply_limits() -> None:
        import resource

        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        except (ValueError, OSError):
            # Post-fork, pre-exec: logging here is not fork-safe. The knowable
            # causes are reported by the parent-side check above.
            pass

        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass  # See above -- no reporting is possible after fork().

    return _apply_limits


async def _read_stream_capped(
    stream: asyncio.StreamReader | None,
    limit: int,
) -> tuple[bytes, bool]:
    """Read a stream incrementally, stopping once `limit` bytes are collected.

    RESOURCE-EXHAUSTION FIX (Round 14): the previous code used
    `process.communicate()`, which reads stdout/stderr to completion --
    buffering the ENTIRE output in memory -- before any size check ever ran;
    sandbox_executor.py's 1MB result-size cap was only applied to the
    result *after* that call returned. A skill that printed unbounded
    output could inflate this process's memory for up to
    max_execution_time_s (default 30s) before the wall-clock timeout even
    fired. Reading incrementally and stopping as soon as the cap is
    exceeded bounds memory use to ~`limit` regardless of how much the child
    tries to write.

    Returns:
        (data, truncated) -- `truncated` is True if `limit` was reached
        before the stream ended.

    """
    if stream is None:
        return b"", False

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            break
        remaining = limit - total
        if remaining <= 0:
            return b"".join(chunks), True
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining])
            return b"".join(chunks), True
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks), False


async def _kill_and_wait(process: "asyncio.subprocess.Process", skill_id: str = "") -> None:
    """Kill a subprocess and wait for it to be reaped, without risking an
    indefinite hang.

    RELIABILITY FIX (Round 14): every teardown path here used to call
    `process.kill()` followed directly by a bare `await process.wait()`.
    That was empirically reproduced to hang **indefinitely** in exactly the
    scenario the streaming-cap fix above introduces: once
    `_read_stream_capped()` returns early (cap exceeded) and the sibling
    stream-reader task gets cancelled by the surrounding `asyncio.wait_for`,
    a subsequent `await process.wait()` can simply never resolve -- even
    though `/proc/<pid>` confirms the OS process is already dead. This
    reproduces consistently for the output-cap path and appears to be an
    asyncio subprocess-transport/child-watcher edge case triggered by
    cancelling a stream reader while the transport is still open, not
    something a kill()/wait() call sequence can fix by trying harder. A
    sandbox teardown step must never be allowed to block forever regardless
    of the cause -- that would freeze the entire sandbox executor over a
    single misbehaving skill, precisely the denial-of-service a sandboxing
    subsystem is supposed to prevent. So the wait is bounded: if it doesn't
    resolve in time we log a warning and move on. The process itself is
    already killed (confirmed dead at the OS level in every reproduction of
    this); what's being skipped is asyncio's own bookkeeping about it, not
    real cleanup work.
    """
    try:
        await asyncio.wait_for(process.wait(), timeout=_PROCESS_REAP_GRACE_S)
    except TimeoutError:
        _logger.warning(
            "process.wait() did not resolve within %.1fs after kill() for "
            "skill '%s' (pid=%s) -- the process was already killed; "
            "continuing without waiting further to avoid hanging the "
            "sandbox executor",
            _PROCESS_REAP_GRACE_S,
            skill_id,
            getattr(process, "pid", "?"),
        )


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

    def __init__(self, config: SandboxConfig) -> None:
        """Initialize skill sandbox.

        Args:
            config: Sandbox configuration

        """
        self.config = config
        self.process: asyncio.subprocess.Process | None = None

    async def execute(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
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
        return await self._execute_process(command, env)

    async def _execute_process(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute command in isolated process.

        Args:
            command: Command to execute
            env: Environment variables

        Returns:
            Execution result

        """
        # Prepare a minimal environment (see _build_sandbox_env() docstring)
        # instead of inheriting the full parent process environment.
        exec_env = _build_sandbox_env(env, self.config.resource_limits)

        # Create temporary directory
        temp_dir = self.config.temp_dir
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Real, kernel-enforced CPU/memory limits on POSIX (see
        # _make_resource_limiter() docstring); None (no-op) on Windows.
        preexec_fn = _make_resource_limiter(self.config.resource_limits)

        try:
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                *command,
                env=exec_env,
                cwd=str(temp_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=preexec_fn,
            )

            self.process = process

            # OUTPUT-CAP FIX (Round 14 follow-up): the previous approach
            # read stdout/stderr concurrently via `asyncio.gather(...)`
            # under a single `asyncio.wait_for(..., timeout=...)`. gather()
            # only resolves once BOTH coroutines finish -- so a skill that
            # floods only stdout (the realistic case; stderr stays empty)
            # never actually triggered the intended "kill as soon as the
            # cap is hit" branch below it: gather() just sat blocked on the
            # still-open stderr stream (which cannot reach EOF until the
            # process exits, and the process never exits because it's
            # blocked writing to a stdout pipe nobody is draining anymore)
            # until the *unrelated* overall wall-clock timeout eventually
            # fired anyway -- confirmed by direct reproduction. The output
            # cap DID still bound this process's own memory use (that part
            # of the fix works, since the capped reader itself returns
            # early), but the fast-kill this branch exists for silently
            # never ran for the common single-stream-flood case.
            #
            # Reading each stream as its own task and waking up on
            # `FIRST_COMPLETED` lets us react the moment *either* stream
            # reports truncated=True: we kill the process right then, which
            # lets the still-pending sibling stream reach EOF immediately
            # (the process that was writing to it no longer exists),
            # instead of waiting for it to finish on its own.
            stdout_task = asyncio.ensure_future(
                _read_stream_capped(process.stdout, _MAX_OUTPUT_BYTES),
            )
            stderr_task = asyncio.ensure_future(
                _read_stream_capped(process.stderr, _MAX_OUTPUT_BYTES),
            )
            pending = {stdout_task, stderr_task}
            stdout_result: tuple[bytes, bool] | None = None
            stderr_result: tuple[bytes, bool] | None = None
            killed_for_output_cap = False
            loop = asyncio.get_event_loop()
            deadline = loop.time() + self.config.resource_limits.max_execution_time_s

            def _timeout_message() -> str:
                return (
                    f"Execution exceeded "
                    f"{self.config.resource_limits.max_execution_time_s}s limit"
                )

            def _safe_kill() -> None:
                # The process may have already exited naturally in the
                # narrow window between a stream reporting truncation and
                # this call -- kill() on an already-reaped process raises
                # ProcessLookupError, which is not a real error here.
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

            try:
                while pending:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        raise TimeoutError(_timeout_message())

                    done, pending = await asyncio.wait(
                        pending,
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        raise TimeoutError(_timeout_message())

                    for task in done:
                        data, truncated = task.result()
                        if task is stdout_task:
                            stdout_result = (data, truncated)
                        else:
                            stderr_result = (data, truncated)

                        if truncated and not killed_for_output_cap:
                            killed_for_output_cap = True
                            _safe_kill()

                stdout_data = stdout_result[0] if stdout_result else b""
                stderr_data = stderr_result[0] if stderr_result else b""

                if killed_for_output_cap:
                    await _kill_and_wait(process, self.config.skill_id)
                    return {
                        "success": False,
                        "returncode": process.returncode,
                        "stdout": stdout_data.decode("utf-8", errors="replace"),
                        "stderr": (
                            stderr_data.decode("utf-8", errors="replace")
                            + "\n[sandbox] output exceeded 1MB limit; process terminated"
                        ),
                    }

                await process.wait()
                return {
                    "success": process.returncode == 0,
                    "returncode": process.returncode,
                    "stdout": stdout_data.decode("utf-8", errors="replace"),
                    "stderr": stderr_data.decode("utf-8", errors="replace"),
                }

            except TimeoutError as e:
                # Kill process on timeout (genuine wall-clock exhaustion,
                # not an output-cap kill, which is handled above).
                for task in pending:
                    task.cancel()
                _safe_kill()
                await _kill_and_wait(process, self.config.skill_id)
                raise TimeoutError(_timeout_message()) from e

        finally:
            self.process = None

    async def _execute_docker(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
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

            except TimeoutError:
                # Kill container on timeout
                if process.pid:
                    kill_proc = await asyncio.create_subprocess_exec(
                        "docker", "kill", str(process.pid),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await kill_proc.wait()
                process.kill()
                await _kill_and_wait(process, self.config.skill_id)
                msg = (
                    f"Execution exceeded {self.config.resource_limits.max_execution_time_s}s limit"
                )
                raise TimeoutError(
                    msg,
                ) from None

        finally:
            self.process = None

    async def cleanup(self) -> None:
        """Clean up sandbox resources."""
        # Kill process if still running
        if self.process:
            self.process.kill()
            await _kill_and_wait(self.process, self.config.skill_id)
            self.process = None

        # Clean up temporary directory
        if self.config.temp_dir.exists():
            import shutil

            shutil.rmtree(self.config.temp_dir, ignore_errors=True)


class SandboxManager:
    """Manager for skill sandboxes."""

    def __init__(self) -> None:
        """Initialize sandbox manager."""
        self.sandboxes: dict[str, SkillSandbox] = {}
        self.temp_base_dir = Path(tempfile.gettempdir()) / "agent_guru_skills"
        self.temp_base_dir.mkdir(parents=True, exist_ok=True)

    def create_sandbox(
        self,
        skill_id: str,
        resource_limits: ResourceLimits | None = None,
        allowed_endpoints: list[str] | None = None,
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

    def get_sandbox(self, skill_id: str) -> SkillSandbox | None:
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
