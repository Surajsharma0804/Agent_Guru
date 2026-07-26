"""Agent Guru — Package entry point.

Enables `python -m Agent_Guru` and serves as the PyInstaller entry point.
Delegates to main.py's async main() function.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Ensure the project root is on sys.path so `import Agent_Guru` works
# when running from a frozen PyInstaller bundle or `python -m Agent_Guru`.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def _run() -> None:
    """Entry point for PyInstaller / console_scripts."""
    # Import main's async entry point and run it
    try:
        # Import from the top-level main.py
        sys.path.insert(0, _project_root)
        from main import main  # type: ignore[import-untyped]
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAgent Guru shut down.")
    except Exception as exc:
        print(f"Agent Guru failed to start: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _run()
