"""Python the assistant writes, run in the WSL sandbox, as a tool in the tool loop.

"What is 2 to the power 200?", "how many days between these dates?",
"sort these numbers": the model guessed, and a language model's
arithmetic and counting are unreliable. With this tool it writes a short
program, the owner hears what will run and says yes, and the answer is
what the program printed.

Served in process through the same toolbox as MCP servers, so every
call gets the policy check, the schema check, the owner's yes (the tool
is not read-only), the output guard and the audit entry. The program
runs only behind the boundary in reasoning/tools/skills/wsl_sandbox.py:
no network, none of the owner's files, no Windows programs, limits on
time, memory and processes. Off unless AGENT_GURU_CODE_SANDBOX is on,
because it keeps the WSL virtual machine running; it is offered only
when that boundary's checks pass on this machine.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from Agent_Guru.integration.mcp_tools import ServerConfig, ToolRisk, ToolRule
from Agent_Guru.reasoning.tools.skills import wsl_sandbox

logger = logging.getLogger(__name__)

SERVER_NAME = "code"
ENABLE_ENV = "AGENT_GURU_CODE_SANDBOX"
MAX_CODE_CHARS = 8000
MAX_SECONDS = 30
#: What the model is shown of the output; the toolbox caps tool output as well.
MAX_SHOWN_CHARS = 3000


def enabled() -> bool:
    return os.environ.get(ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def code_server() -> ServerConfig:
    """The ServerConfig for the code tool; local is set by the caller."""
    # Not read-only: the tool loop reads the program back and waits for the
    # owner's yes before anything runs.
    rules = {"run_python": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE),
             "run_shell": ToolRule(allow=True, risk=ToolRisk.LOW_RISK_WRITE)}
    return ServerConfig(name=SERVER_NAME, command="(in process)", timeout=MAX_SECONDS + 30.0, tools=rules)


class CodeTools:
    """The run_python and run_shell tools (see the module docstring)."""

    def __init__(self) -> None:
        self._problems: list[str] | None = None

    def _boundary_problems(self) -> list[str]:
        if self._problems is None:
            self._problems = wsl_sandbox.check()
            if self._problems:
                logger.warning("Code tool not offered: the sandbox cannot be trusted here: %s",
                               "; ".join(self._problems))
        return self._problems

    def tool_list(self) -> list[dict[str, Any]]:
        if not enabled() or self._boundary_problems():
            return []
        shell = {
            "name": "run_shell",
            "description": (
                "Run a short bash script in the same isolated Ubuntu sandbox and get what it prints: text "
                "processing, date arithmetic, standard command-line tools. No internet, none of the owner's "
                "files, nothing kept after the run. The owner confirms first."
            ),
            "annotations": {"readOnlyHint": False, "openWorldHint": False},
            "inputSchema": {"type": "object", "properties": {
                "script": {"type": "string", "minLength": 1, "maxLength": MAX_CODE_CHARS},
                "seconds": {"type": "integer", "minimum": 1, "maximum": MAX_SECONDS},
            }, "required": ["script"], "additionalProperties": False},
        }
        return [shell, {
            "name": "run_python",
            "description": (
                "Run a short Python 3 program (standard library only) in an isolated sandbox and get what it "
                "prints. Use it for exact arithmetic, dates, counting, sorting or checking code; print the "
                "answer. The sandbox has no internet and none of the owner's files. The owner confirms first."
            ),
            "annotations": {"readOnlyHint": False, "openWorldHint": False},
            "inputSchema": {"type": "object", "properties": {
                "code": {"type": "string", "minLength": 1, "maxLength": MAX_CODE_CHARS},
                "seconds": {"type": "integer", "minimum": 1, "maximum": MAX_SECONDS},
            }, "required": ["code"], "additionalProperties": False},
        }]

    def describe(self, tool: str, arguments: dict[str, Any]) -> str | None:
        """The confirmation question shows the program itself, so the owner hears what will run."""
        key = {"run_python": "code", "run_shell": "script"}.get(tool)
        code = str(arguments.get(key, "")) if key and isinstance(arguments, dict) else ""
        if not code.strip():
            return None
        lines = code.strip().splitlines()
        shown = "; ".join(line.strip() for line in lines[:4])[:240]
        more = f" (and {len(lines) - 4} more lines)" if len(lines) > 4 else ""
        language = "Python" if tool == "run_python" else "shell script"
        return f"run this {language} in the sandbox: {shown}{more}"

    async def precheck(self, tool: str, arguments: dict[str, Any]) -> list[str]:
        """Before the owner is asked: a sandbox that cannot be trusted is not offered for a yes."""
        if tool not in ("run_python", "run_shell"):
            return [f"unknown tool {tool}"]
        return await asyncio.to_thread(self._boundary_problems)

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool, bool]:
        if name not in ("run_python", "run_shell"):
            return f"unknown tool {name}", True, False
        if self._boundary_problems():
            return "The sandbox is not available: " + "; ".join(self._problems or []), True, False
        seconds = int(arguments.get("seconds", 10))
        if name == "run_shell":
            run = await wsl_sandbox.run_shell(str(arguments.get("script", "")), seconds=seconds)
        else:
            run = await wsl_sandbox.run_python(str(arguments.get("code", "")), seconds=seconds)
        return _report(run), not run.ok, run.result != "unavailable"


def _report(run: wsl_sandbox.SandboxRun) -> str:
    """What the model is told: how the run ended, then its output and errors, cut to size."""
    ended = {
        "success": "finished",
        "exit-code": f"failed with exit code {run.exit_code}",
        "timeout": "was stopped at its time limit",
        "oom-kill": "was stopped: it used more memory than allowed",
        "output-limit": "was stopped: it printed more than allowed",
        "unavailable": "did not run",
    }.get(run.result, f"ended ({run.result})")
    parts = [f"The program {ended} in {run.seconds:.1f} s."]
    if run.stdout.strip():
        parts.append("Output:\n" + _cut(run.stdout))
    if run.stderr.strip():
        parts.append("Errors:\n" + _cut(run.stderr))
    if run.ok and not run.stdout.strip():
        parts.append("It printed nothing.")
    return "\n".join(parts)


def _cut(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_SHOWN_CHARS:
        return text
    half = MAX_SHOWN_CHARS // 2
    return f"{text[:half]}\n[... {len(text) - MAX_SHOWN_CHARS} characters left out ...]\n{text[-half:]}"
