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


def _run() -> None:
    """Entry point for PyInstaller / console_scripts."""
    if sys.argv[1:2] == ["doctor"]:
        # Checks the machine instead of starting the assistant.
        from Agent_Guru.platform.error_handling.doctor import run

        sys.exit(run(sys.argv[2:]))
    if sys.argv[1:2] == ["documents"]:
        # Adds, removes or lists the documents the assistant answers from.
        from Agent_Guru.platform.features.documents import run as run_documents

        sys.exit(run_documents(sys.argv[2:]))
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
