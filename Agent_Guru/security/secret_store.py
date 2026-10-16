"""Small secrets the assistant keeps on disk: its API key, account tokens.

settings.toml refuses secrets because it is plain text, and the
environment is lost whenever the app starts another way. Secrets the
assistant creates itself (the local API key) or receives (OAuth tokens)
are kept here instead: on Windows encrypted with DPAPI for the current
account, so another account or a copy of the file on another machine
cannot read them and no password is asked for; elsewhere in a file only
its owner can read. The audit signing key (security/audit/logger.py)
is kept the same way.

Files live in the data folder and their names end in .dpapi, which
security/file_policy.py keeps the assistant's own file tools away from.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_DESCRIPTION = "Agent Guru secret"


def _protect(data: bytes) -> bytes:
    if sys.platform == "win32":
        import win32crypt  # type: ignore[import-untyped]

        return win32crypt.CryptProtectData(data, _DESCRIPTION, None, None, None, 0)
    return data


def _unprotect(data: bytes) -> bytes:
    if sys.platform == "win32":
        import win32crypt  # type: ignore[import-untyped]

        return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
    return data


def path_for(name: str) -> Path:
    """Where the secret *name* is kept: <data folder>/secrets/<name>.dpapi."""
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir("secrets") / f"{name}.dpapi"


def save(name: str, data: bytes) -> None:
    from Agent_Guru.utils.secure_file import secure_write_bytes

    secure_write_bytes(path_for(name), _protect(data))


def load(name: str) -> bytes | None:
    """The secret *name*, or None when there is none; raises if it exists but cannot be decrypted."""
    path = path_for(name)
    if not path.exists():
        return None
    return _unprotect(path.read_bytes())


def load_or_create(name: str, factory: Callable[[], bytes]) -> bytes:
    """The secret *name*, made with *factory* and kept the first time it is asked for."""
    existing = load(name)
    if existing is not None:
        return existing
    data = factory()
    save(name, data)
    return data


def save_json(name: str, value: Any) -> None:
    save(name, json.dumps(value).encode("utf-8"))


def load_json(name: str) -> Any:
    raw = load(name)
    return None if raw is None else json.loads(raw.decode("utf-8"))


def delete(name: str) -> bool:
    path = path_for(name)
    if path.exists():
        path.unlink()
        return True
    return False
