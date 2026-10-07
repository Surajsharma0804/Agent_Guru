"""A connection to one MCP server: a child process speaking JSON-RPC 2.0, one message per line on stdin and stdout.

The server is someone else's program, so nothing it sends is assumed to be
well formed or on time:

- Every request waits a bounded time. A reply is matched to its request by
  id; a reply with an id nothing is waiting for (late, repeated or made up),
  a notification, or a line that is not JSON is logged and dropped, and
  never completes another request.
- A line longer than the connection's limit is not buffered: the
  connection is closed, since the rest of that stream can no longer be read
  reliably, and every waiting request fails with ResponseTooLarge.
- The server's stderr is read continuously into a short log tail. Nothing
  else reads it, and a server that fills the stderr pipe stops answering
  on stdout.
- close() ends the server and everything it started. On Windows the
  process is put in a job object that kills its whole tree when closed:
  `npx` starts a cmd.exe that starts node, and ending only cmd.exe would
  leave node running. The job also ends the tree if this process dies
  without closing it.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import logging
import os
import shutil
import sys
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

#: The protocol revision this client speaks; the server answers with its own.
PROTOCOL_VERSION = "2025-06-18"

#: Longest single message read from a server, in bytes.
DEFAULT_MAX_MESSAGE_BYTES = 1024 * 1024

#: How long close() waits for the server to exit after its stdin is closed
#: before ending it.
_EXIT_GRACE_S = 2.0

_STDERR_TAIL_LINES = 20

#: Environment variables every server gets: where programs and temporary
#: files are, and what Windows itself needs to start a process.
_BASE_ENV = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    "HOME", "LANG", "LC_ALL", "TZ", "USER", "LOGNAME", "SHELL", "TERM",
})


class MCPError(Exception):
    """A request to an MCP server did not produce a result."""


class ServerUnavailable(MCPError):
    """The server could not be started, or is no longer running."""


class ResponseTooLarge(MCPError):
    """The server sent a message longer than the connection allows."""


class RemoteError(MCPError):
    """The server answered the request with a JSON-RPC error."""

    def __init__(self, code: Any, message: str) -> None:
        super().__init__(f"{message} (code {code})")
        self.code = code


class _KillTree:
    """Ends a process and every process it started (see the module docstring)."""

    def __init__(self, pid: int) -> None:
        self._job = None
        if sys.platform != "win32":
            return
        try:
            import win32api
            import win32con
            import win32job

            job = win32job.CreateJobObject(None, "")
            info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
            info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
            handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, pid)
            try:
                win32job.AssignProcessToJobObject(job, handle)
            finally:
                win32api.CloseHandle(handle)
            self._job = job
        except Exception:
            logger.debug("Could not put MCP server %d in a job object", pid, exc_info=True)

    def kill(self) -> None:
        if self._job is not None:
            import win32job

            with contextlib.suppress(Exception):
                win32job.TerminateJobObject(self._job, 1)
            self._job.Close()
            self._job = None


class MCPConnection:
    """One running MCP server and the requests in flight to it."""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        *,
        env: dict[str, str] | None = None,
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
    ) -> None:
        self.name = name
        self._command = command
        self._args = list(args or [])
        self._env = env
        self._max_message_bytes = max_message_bytes
        self._process: asyncio.subprocess.Process | None = None
        self._tree: _KillTree | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._write_lock = asyncio.Lock()
        self._closed_reason: MCPError | None = None
        self.stderr_tail: deque[str] = deque(maxlen=_STDERR_TAIL_LINES)
        self.dropped_messages = 0
        self.server_info: dict[str, Any] = {}

    @property
    def running(self) -> bool:
        return self._process is not None and self._closed_reason is None and self._process.returncode is None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    async def start(self, timeout: float) -> dict[str, Any]:
        """Start the server and complete the initialize handshake; returns what the server said about itself."""
        executable = shutil.which(self._command) or self._command
        # The server gets what a program needs to run and what its settings
        # name, not the whole environment. Inherited, the official test
        # server's get-env tool returned all 118 variables the assistant
        # held, a token planted for the check among them; filtered, 49 (most
        # added by npm itself) and no token.
        env = {k: v for k, v in os.environ.items() if k.upper() in _BASE_ENV}
        env.update(self._env or {})
        try:
            self._process = await asyncio.create_subprocess_exec(
                executable, *self._args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                limit=self._max_message_bytes,
            )
        except OSError as exc:
            msg = f"could not start {self._command}: {exc}"
            raise ServerUnavailable(msg) from exc
        self._tree = _KillTree(self._process.pid)
        self._tasks = [
            asyncio.create_task(self._read_messages(), name=f"mcp-{self.name}-stdout"),
            asyncio.create_task(self._read_stderr(), name=f"mcp-{self.name}-stderr"),
        ]
        try:
            result = await self.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "agent-guru", "version": "1"},
                },
                timeout=timeout,
            )
            await self.notify("notifications/initialized")
        except BaseException:
            await self.close()
            raise
        self.server_info = result if isinstance(result, dict) else {}
        return self.server_info

    async def request(self, method: str, params: dict[str, Any] | None, *, timeout: float) -> Any:
        """Send one request and return its result; raises MCPError, TimeoutError or CancelledError.

        On a timeout or cancellation the server is told the request is
        cancelled (it may ignore that), and the request's id stops being
        waited for, so a reply that arrives later is dropped.
        """
        if not self.running:
            raise self._closed_reason or ServerUnavailable(f"{self.name} is not running")
        request_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
            return await asyncio.wait_for(future, timeout)
        except (TimeoutError, asyncio.CancelledError):
            if self.running:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(
                        self.notify("notifications/cancelled", {"requestId": request_id, "reason": "timed out or cancelled"}),
                        1.0,
                    )
            raise
        finally:
            self._pending.pop(request_id, None)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _send(self, message: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise ServerUnavailable(f"{self.name} is not running")
        line = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        async with self._write_lock:
            try:
                process.stdin.write(line)
                await process.stdin.drain()
            except (ConnectionError, OSError) as exc:
                self._fail_all(ServerUnavailable(f"{self.name} stopped reading: {exc}"))
                raise self._closed_reason from exc  # type: ignore[misc]

    async def _read_messages(self) -> None:
        process = self._process
        assert process is not None and process.stdout is not None  # nosec B101  set in start()
        try:
            while True:
                try:
                    line = await process.stdout.readline()
                except ValueError:
                    # The line ran past the limit given to create_subprocess_exec.
                    self._fail_all(ResponseTooLarge(f"{self.name} sent a message over {self._max_message_bytes} bytes"))
                    break
                if not line:
                    self._fail_all(ServerUnavailable(f"{self.name} exited"))
                    break
                self._handle_line(line)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("MCP server %s: reading its output failed", self.name)
            self._fail_all(ServerUnavailable(f"{self.name}: {exc}"))
        if self._closed_reason is not None:
            # Nothing reads stdout any more; end the server so it cannot
            # block on a full pipe or keep running unseen.
            self._kill()

    def _handle_line(self, line: bytes) -> None:
        text = line.strip()
        if not text:
            return
        try:
            message = json.loads(text)
        except (ValueError, UnicodeDecodeError):
            self._drop("not JSON", text)
            return
        if not isinstance(message, dict):
            self._drop("not a JSON-RPC message", text)
            return
        request_id = message.get("id")
        if "method" in message:
            # A notification or a request from the server (sampling, roots).
            # This client offers the server no capabilities, so neither is
            # acted on; a request is answered "not supported" so the server
            # does not wait on it.
            if request_id is not None:
                with contextlib.suppress(Exception):
                    asyncio.get_running_loop().create_task(self._send({
                        "jsonrpc": "2.0", "id": request_id,
                        "error": {"code": -32601, "message": "not supported by this client"},
                    }))
            return
        future = self._pending.get(request_id) if isinstance(request_id, int) and not isinstance(request_id, bool) else None
        if future is None or future.done():
            self._drop("a reply nothing is waiting for", text)
            return
        if isinstance(message.get("error"), dict):
            error = message["error"]
            future.set_exception(RemoteError(error.get("code"), str(error.get("message", "error"))[:500]))
        elif "result" in message:
            future.set_result(message["result"])
        else:
            future.set_exception(MCPError(f"{self.name} sent a reply with neither result nor error"))

    def _drop(self, why: str, text: bytes) -> None:
        self.dropped_messages += 1
        logger.debug("MCP server %s: dropped %s: %r", self.name, why, text[:200])

    async def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        # Read in chunks, not lines: readline() gives up on a line longer
        # than the stream limit, and once nothing reads stderr the server
        # blocks. A 6 MB line without a newline did exactly that.
        pending = b""
        with contextlib.suppress(ConnectionError, OSError):
            while chunk := await process.stderr.read(65536):
                *lines, pending = (pending + chunk).split(b"\n")
                pending = pending[-2000:]
                for line in lines:
                    text = line.decode("utf-8", "replace").rstrip()
                    if text:
                        self.stderr_tail.append(text[:500])
                        logger.debug("MCP server %s stderr: %s", self.name, text[:500])
        if pending.strip():
            self.stderr_tail.append(pending.decode("utf-8", "replace").rstrip()[:500])

    def _fail_all(self, reason: MCPError) -> None:
        if self._closed_reason is None:
            self._closed_reason = reason
        for future in self._pending.values():
            if not future.done():
                future.set_exception(reason)

    def _kill(self) -> None:
        if self._tree is not None:
            self._tree.kill()
            self._tree = None
        if self._process is not None and self._process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self._process.kill()

    async def close(self) -> None:
        """End the server and everything it started; safe to call more than once."""
        self._fail_all(ServerUnavailable(f"{self.name} was closed"))
        process = self._process
        if process is not None:
            if process.stdin is not None:
                with contextlib.suppress(Exception):
                    process.stdin.close()
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), _EXIT_GRACE_S)
                except TimeoutError:
                    pass
            self._kill()
            if process.returncode is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.wait(), _EXIT_GRACE_S)
            else:
                # The server exited by itself; what it started may not have.
                self._kill()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
