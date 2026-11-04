"""Start the assistant at sign-in, in the background, with no window.

Each system's own per-user place, so nothing needs administrator rights and
turning it off is deleting one file: a shortcut in the Startup folder on Windows
(not the registry), an XDG autostart entry on Linux, a LaunchAgent on macOS.
Standard library only: the frozen launcher runs this.
"""

from __future__ import annotations

from html import escape
import os
import shlex
import subprocess  # nosec B404 - fixed program, values passed in the environment
import sys
from pathlib import Path

from Agent_Guru.genesis.layout import Layout

LABEL = "com.agentguru.assistant"
_REPO = Path(__file__).resolve().parents[2]

#: Values go in through the environment, so a quote in an install path cannot
#: become PowerShell.
_MAKE_SHORTCUT = (
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:AG_LINK);"
    "$s.TargetPath = $env:AG_TARGET; $s.Arguments = $env:AG_ARGS; $s.WorkingDirectory = $env:AG_DIR;"
    "$s.Description = 'Start Agent Guru in the background'; $s.WindowStyle = 7; $s.Save()"
)


def entry_path(platform: str) -> Path:
    if platform == "windows":
        return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Agent Guru.lnk"
    if platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    config = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config) / "autostart" / "agent-guru.desktop"


def _windowless(python: Path) -> Path:
    """pythonw on Windows: python.exe flashes a console at every sign-in."""
    quiet = python.with_name("pythonw.exe")
    return quiet if sys.platform == "win32" and quiet.exists() else python


def launcher_command(layout: Layout) -> tuple[list[str], Path]:
    """What to run at sign-in, and where."""
    tail = ["--root", str(layout.install_root), "--background"]
    if getattr(sys, "frozen", False):
        # An AppImage's sys.executable is inside a mount that is gone by the
        # next sign-in. The console build would open a window: use the other.
        exe = Path(os.environ.get("APPIMAGE") or sys.executable)
        if exe.name.lower().startswith("agentgurucli"):
            exe = exe.with_name("AgentGuru" + exe.suffix)
        return [str(exe), *tail], exe.parent
    return [str(_windowless(Path(sys.executable))), "-m", "Agent_Guru.genesis.launcher", *tail], _REPO


def _desktop_entry(command: list[str]) -> str:
    return ("[Desktop Entry]\nType=Application\nName=Agent Guru\nComment=Start Agent Guru in the background\n"
            f"Exec={shlex.join(command)}\nTerminal=false\nNoDisplay=true\nX-GNOME-Autostart-enabled=true\n")


def _launch_agent(command: list[str], cwd: Path) -> str:
    arguments = "".join(f"<string>{escape(part, quote=False)}</string>" for part in command)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            f'<plist version="1.0"><dict>\n  <key>Label</key><string>{LABEL}</string>\n'
            f"  <key>ProgramArguments</key><array>{arguments}</array>\n"
            f"  <key>WorkingDirectory</key><string>{escape(str(cwd), quote=False)}</string>\n"
            "  <key>RunAtLoad</key><true/>\n</dict></plist>\n")


def write(platform: str, command: list[str], cwd: Path, entry: Path | None = None) -> Path:
    """Write the sign-in entry that runs *command*; its path."""
    entry = entry or entry_path(platform)
    entry.parent.mkdir(parents=True, exist_ok=True)
    if platform == "windows":
        env = {**os.environ, "AG_LINK": str(entry), "AG_TARGET": command[0], "AG_DIR": str(cwd),
               "AG_ARGS": subprocess.list2cmdline(command[1:])}
        done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _MAKE_SHORTCUT],  # noqa: S603,S607  # nosec B603 B607
                              env=env, capture_output=True, text=True, timeout=60, check=False,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if done.returncode or not entry.exists():
            msg = f"could not make the Startup shortcut: {done.stderr.strip()[-300:]}"
            raise OSError(msg)
    elif platform == "darwin":
        entry.write_text(_launch_agent(command, cwd), encoding="utf-8")
    else:
        entry.write_text(_desktop_entry(command), encoding="utf-8")
    return entry


def install(layout: Layout, platform: str) -> Path:
    command, cwd = launcher_command(layout)
    return write(platform, command, cwd)


def remove(platform: str) -> bool:
    """Delete the sign-in entry; True when there was one."""
    entry = entry_path(platform)
    if not entry.exists():
        return False
    entry.unlink()
    return True
