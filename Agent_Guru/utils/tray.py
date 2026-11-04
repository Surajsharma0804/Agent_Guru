"""The notification-area icon of a running assistant: Open, Mute, Quit.

Without a window, nothing on screen would say that a microphone is open. The
icon is that sign, and the way to reach the window and to end the assistant
without a terminal. It is optional: on a system with no tray, or on macOS, where
a tray must own the main thread and the assistant's event loop does, the
assistant runs without one and the log says so.
"""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404 - runs this install's own launcher
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ICON = Path(__file__).resolve().parents[2] / "assets" / "icon.png"


def open_window(url: str) -> None:
    """Open the window: through the installed launcher, which uses the app's own web view, else a browser."""
    launcher, root = os.environ.get("AGENT_GURU_LAUNCHER"), os.environ.get("AGENT_GURU_INSTALL_ROOT")
    if launcher and root:
        subprocess.Popen([launcher, "--root", root])  # noqa: S603  # nosec B603 - set by this install's launcher
        return
    webbrowser.open(url)


def menu_items(workspace: Any, url: str, pystray: Any, stop: Any) -> Any:
    """The menu. Mute reads the workspace each time, so the voice command and the window stay in step."""
    def muted(_item: Any = None) -> bool:
        return workspace.state({})[1]["microphone"] == "muted"

    def can_mute(_item: Any) -> bool:
        return workspace.state({})[1]["microphone"] != "none"

    def toggle(_icon: Any, _item: Any) -> None:
        workspace.set_mic({"muted": not muted()})

    return pystray.Menu(
        pystray.MenuItem("Open Agent Guru", lambda _i, _m: open_window(url), default=True),
        pystray.MenuItem("Mute microphone", toggle, checked=muted, enabled=can_mute),
        pystray.MenuItem("Quit Agent Guru", lambda icon, _m: (stop(), icon.stop())),
    )


def start(workspace: Any, url: str) -> threading.Thread | None:
    """Show the icon on its own thread; None when this system has no tray."""
    if sys.platform == "darwin":
        logger.info("No tray icon on macOS: pystray needs the main thread, which runs the assistant")
        return None
    try:
        import pystray  # type: ignore[import-untyped]
        from PIL import Image
    except Exception as exc:  # noqa: BLE001 - pystray raises several types with no display
        logger.warning("No tray icon (%s): the assistant runs without one", exc)
        return None

    from Agent_Guru.utils import service

    icon = pystray.Icon("agent-guru", Image.open(_ICON), "Agent Guru - listening for Hey Guru and Hey Maya",
                        menu_items(workspace, url, pystray, service.request_stop))

    def run() -> None:
        try:
            icon.run()
        except Exception:
            logger.warning("The tray icon stopped", exc_info=True)

    thread = threading.Thread(target=run, name="tray-icon", daemon=True)
    thread.start()
    return thread
