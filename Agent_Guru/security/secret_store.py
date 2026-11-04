"""Small secrets the assistant keeps on disk: its API key, account tokens.

settings.toml refuses secrets because it is plain text, and the
environment is lost whenever the app starts another way. Secrets the
assistant creates itself (the local API key) or receives (OAuth tokens)
are kept here instead: on Windows encrypted with DPAPI for the current
account, so another account or a copy of the file on another machine
cannot read them and no password is asked for; on macOS and Linux encrypted
with a key held in the system keychain, when there is one. With no keychain
(a server, a headless session) the file is plain and only its owner can read
it, which encrypted_at_rest() reports so an install can say so. The audit
signing key (security/audit/logger.py) is kept the same way.

Files live in the data folder and their names end in .dpapi, which
security/file_policy.py keeps the assistant's own file tools away from.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

class NoCredentialBackend(RuntimeError):
    """No operating-system credential store is available to protect a secret."""


_DESCRIPTION = "Agent Guru secret"
#: Starts a file encrypted with the keychain's key. Files written before that
#: have no mark and are read as they are.
_MARK = b"AGENT-GURU-FERNET-1\n"
_KEYCHAIN_NAME = "store-key"


def _on_windows() -> bool:
    return sys.platform == "win32"


def _fernet() -> Any:
    """The cipher whose key the system keychain holds, or None where there is no keychain."""
    try:
        from cryptography.fernet import Fernet

        return Fernet(os_credential(_KEYCHAIN_NAME, Fernet.generate_key))
    except (NoCredentialBackend, ImportError):
        return None


def encrypted_at_rest() -> bool:
    """True when secrets are encrypted on disk here, not only protected by the file's owner."""
    return _on_windows() or _fernet() is not None


def _protect(data: bytes) -> bytes:
    if _on_windows():
        import win32crypt  # type: ignore[import-untyped]

        return win32crypt.CryptProtectData(data, _DESCRIPTION, None, None, None, 0)
    cipher = _fernet()
    return _MARK + cipher.encrypt(data) if cipher else data


def _unprotect(data: bytes) -> bytes:
    if _on_windows():
        import win32crypt  # type: ignore[import-untyped]

        return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
    if data.startswith(_MARK):
        cipher = _fernet()
        if cipher is None:
            msg = "this secret was encrypted with a key from a keychain that is not available now"
            raise NoCredentialBackend(msg)
        return cipher.decrypt(data[len(_MARK):])
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


_KEYRING_SERVICE = "Agent Guru"


def os_credential(name: str, factory: Callable[[], bytes]) -> bytes:
    """The secret *name*, made with *factory* the first time, kept by the operating system.

    save() and load() fall back to a plain owner-only file where no keychain exists. That is not good enough
    for a value that is itself the key to other secrets, such as a store's master password, so
    this uses only an OS credential store: DPAPI on Windows (the same as save()), and elsewhere
    the keyring package's backend when one is installed and working (Keychain, Secret Service).
    Without one it raises NoCredentialBackend, and the caller must not keep the secret at all.
    """
    if _on_windows():
        return load_or_create(name, factory)
    try:
        import keyring  # type: ignore[import-not-found]
        from keyring.backends import fail  # type: ignore[import-not-found]
    except ImportError as exc:
        msg = "no operating-system credential store: keyring is not installed"
        raise NoCredentialBackend(msg) from exc
    backend = keyring.get_keyring()
    if isinstance(backend, fail.Keyring) or getattr(backend, "priority", 0) <= 0:
        msg = f"no operating-system credential store: keyring has no working backend ({type(backend).__name__})"
        raise NoCredentialBackend(msg)
    stored = keyring.get_password(_KEYRING_SERVICE, name)
    if stored is not None:
        return bytes.fromhex(stored)
    value = factory()
    keyring.set_password(_KEYRING_SERVICE, name, value.hex())
    return value
