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
    "api": ("Agent_Guru.integration.local_api", "run", "the local HTTP API: its state, or the owner's key"),
    "telegram": ("Agent_Guru.platform.channels.inbound", "run", "the Telegram bot: its state, or who has written to it"),
    "connect": ("Agent_Guru.connectors.oauth", "run", "sign in to Google or Microsoft for mail, calendar and contacts"),
    "learn": ("Agent_Guru.self_improvement.prompt_tuning", "run", "tune the prompt from mistakes, roll back, or export training data"),
    "init": ("Agent_Guru.utils.commands", "init", "first start: this machine, the model to use, what is switched on"),
    "ask": ("Agent_Guru.utils.commands", "ask", "ask the running assistant one question, typed"),
    "chat": ("Agent_Guru.utils.commands", "chat", "a typed conversation with the running assistant"),
    "config": ("Agent_Guru.utils.commands", "config", "show or change settings.toml, checked"),
    "model": ("Agent_Guru.utils.commands", "model", "the model in use, or switch to another installed one"),
    "memory": ("Agent_Guru.utils.commands", "memory", "what the assistant remembers about you, or forget one thing"),
    "tasks": ("Agent_Guru.utils.commands", "tasks", "reminders, checks and actions that are scheduled"),
    "mic": ("Agent_Guru.utils.commands", "mic", "mute or unmute the running assistant's microphone"),
    "eval": ("Agent_Guru.utils.commands", "evaluate", "score the assistant on its evaluation set"),
    "bench": ("Agent_Guru.utils.commands", "bench", "time every stage of spoken turns"),
    "skills": ("Agent_Guru.reasoning.tools.skills.importer", "run", "import a skill after checking it, or find repeated tool sequences"),
    "injection-model": ("Agent_Guru.security.injection_classifier", "run", "install, verify or check the local prompt-injection classifier"),
    "sandbox": ("Agent_Guru.reasoning.tools.skills.wsl_sandbox", "run", "set up, check or try the WSL sandbox that runs the assistant's code"),
    "vault": ("Agent_Guru.security.vault", "run", "keep service credentials encrypted for this account instead of in .env"),
    "service": ("Agent_Guru.utils.service", "run", "run it in the background, stop it cleanly, or start it at log-in"),
    "update": ("Agent_Guru.utils.update", "run", "fast-forward this checkout to its upstream (--check to look first)"),
    "dashboard": ("Agent_Guru.utils.dashboard", "run", "a terminal view: running or not, recent turns, what is scheduled"),
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
