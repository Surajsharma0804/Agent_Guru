"""Where an installation keeps its files.

Three kinds of place, kept apart because uninstalling treats them differently:

- the install folder: the launcher, the application source and the managed
  runtime (a private venv, and a private Python when the machine has no
  compatible one). Uninstall removes all of it. The runtime lives here, not
  in the user's data, so removing the app never leaves 300 MB to 3 GB of
  packages behind.
- the user's data folder (utils/path_utils.app_data_dir): memory, settings,
  reminders and the downloaded models. Uninstall keeps it unless the user
  ticks the box. Nothing in GENESIS deletes from it.
- the download cache inside the install folder: every file the engine
  downloads goes through it, so a repair or a reinstall of a component does
  not download the same bytes twice.

On Windows a frozen launcher puts the install folder next to its executable.
On Linux and macOS it cannot: an AppImage runs from a read-only mount that
disappears when it exits, and an app bundle must not change after it is
signed. There the install folder is per user, and the application source
is copied into it from the bundle (the app-files component). From a source
checkout it is a folder the user names (--root), so a trial install never
lands inside the repository.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from Agent_Guru.utils.path_utils import app_data_dir


@dataclass(frozen=True)
class Layout:
    install_root: Path
    app_root: Path
    #: The application source inside a frozen bundle, where it must be copied out.
    bundled_app: Path | None = None

    @property
    def runtime_root(self) -> Path:
        return self.install_root / "runtime"

    @property
    def venv_dir(self) -> Path:
        return self.runtime_root / "venv"

    @property
    def venv_python(self) -> Path:
        if os.name == "nt":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    @property
    def private_python_dir(self) -> Path:
        return self.runtime_root / "python"

    @property
    def cache_dir(self) -> Path:
        return self.runtime_root / "cache"

    @property
    def journal_path(self) -> Path:
        return self.runtime_root / "journal.jsonl"

    @property
    def ollama_pid_file(self) -> Path:
        return self.runtime_root / "ollama.pid"

    @property
    def lock_path(self) -> Path:
        return self.runtime_root / "genesis.lock"

    @property
    def data_dir(self) -> Path:
        return app_data_dir(create=False)

    @property
    def settings_path(self) -> Path:
        return self.data_dir / "settings.toml"

    @property
    def lock_file(self) -> Path:
        """The pinned versions every package install takes its versions from."""
        return self.app_root / "requirements-lock.txt"


def source_root() -> Path:
    """The checkout this module was loaded from."""
    return Path(__file__).resolve().parents[2]


def per_user_root() -> Path:
    """Where a frozen launcher installs on Linux and macOS."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AgentGuru"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "AgentGuru"


def default_layout(root: Path | None = None) -> Layout:
    """The frozen install's folders, or *root* (required from a source checkout)."""
    if getattr(sys, "frozen", False) and sys.platform != "win32":
        install = Path(root).resolve() if root else per_user_root()
        return Layout(install_root=install, app_root=install / "app",
                      bundled_app=Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "app")
    if getattr(sys, "frozen", False):
        # The application source ships next to the launcher, in app\. It is
        # not inside the frozen bundle, so --root moves the install folder
        # and never this: source_root() here would be PyInstaller's _internal.
        install = Path(sys.executable).resolve().parent
        return Layout(install_root=Path(root).resolve() if root else install, app_root=install / "app")
    if root is None:
        msg = "from a source checkout, name the install folder with --root (a trial install never goes in the repository)"
        raise ValueError(msg)
    return Layout(install_root=Path(root).resolve(), app_root=source_root())
