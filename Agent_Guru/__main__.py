"""Agent Guru - Package entry point.

Enables `python -m Agent_Guru` and serves as the PyInstaller entry point.
Delegates to main.py's main(), which restarts the assistant after a crash.
"""
from __future__ import annotations

import os
import sys

# Ensure the project root is on sys.path so `import Agent_Guru` works
# when running from a frozen PyInstaller bundle or `python -m Agent_Guru`.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


#: Commands that do one job instead of starting the assistant: name ->
#: (module, function, what it does). Each function takes the remaining
#: arguments and returns an exit code; its module is imported only when
#: the command is used, so a plain launch does not pay for them.
COMMANDS: dict[str, tuple[str, str, str]] = {
    "doctor": ("Agent_Guru.platform.error_handling.doctor", "run", "check the machine"),
    "documents": ("Agent_Guru.platform.features.documents", "run", "add, remove or list documents to answer from"),
    "mcp": ("Agent_Guru.integration.mcp_tools", "run", "list or call tools on MCP servers, through the policy"),
    "models": ("Agent_Guru.llm.model_catalog", "run", "the models installed in Ollama and whether they fit the GPU"),
    "recipes": ("Agent_Guru.utils.recipes", "run", "list, show or apply a named set of settings"),
}


def _run() -> None:
    """Entry point for PyInstaller / console_scripts."""
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name in COMMANDS:
        import importlib

        module, function, _ = COMMANDS[name]
        sys.exit(getattr(importlib.import_module(module), function)(sys.argv[2:]))
    if name in ("help", "--help", "-h"):
        print("python -m Agent_Guru [command]\n\nWith no command, starts the assistant. Commands:")
        for command, (_, _, what) in COMMANDS.items():
            print(f"  {command:12} {what}")
        sys.exit(0)
    # Import main's async entry point and run it
    try:
        # Import from the top-level main.py
        sys.path.insert(0, _project_root)
        # main() runs the assistant with main.py's restart-on-crash loop.
        # This used to be asyncio.run(main()) against a main.py that had no
        # main(), so every launch through here failed at the import.
        from main import main  # type: ignore[import-untyped]
        main()
    except KeyboardInterrupt:
        print("\nAgent Guru shut down.")
    except Exception as exc:
        print(f"Agent Guru failed to start: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _run()
