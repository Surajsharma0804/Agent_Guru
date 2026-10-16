"""Paths the assistant never reads, writes, moves or hands to a tool: keys, credentials, secrets.

File operations were confined to a base directory, but inside it nothing
told an SSH key from a shopping list: "read the file id_rsa in .ssh" or a
tool call with path "C:/Users/me/.aws/credentials" went ahead like any
other. Those files are worth more to someone steering the assistant (a
web page, a tool's output, a misheard command) than anything else on the
machine, and no spoken request needs them.

sensitive_reason(path) says why a path is one of them, or "" when it is
not. It looks at names and folders only and never opens the file, so it
costs nothing and works for files that do not exist yet (a write is
refused before anything lands). The owner can still open these files
themselves; only the assistant is kept out.
"""

from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePath
from typing import Any

#: Folders whose whole content is secret, matched on any path component.
_SECRET_FOLDERS = {
    ".ssh": "SSH keys",
    ".gnupg": "GnuPG keys",
    ".aws": "AWS credentials",
    ".azure": "Azure credentials",
    ".kube": "Kubernetes credentials",
    ".docker": "Docker credentials",
    ".password-store": "password store",
}

#: File names (lower case, glob) that hold keys or credentials wherever they are.
_SECRET_NAMES = (
    ("id_rsa*", "private SSH key"), ("id_dsa*", "private SSH key"), ("id_ecdsa*", "private SSH key"),
    ("id_ed25519*", "private SSH key"), ("*.pem", "key or certificate"), ("*.key", "private key"),
    ("*.p12", "certificate store"), ("*.pfx", "certificate store"), ("*.jks", "Java keystore"),
    ("*.keystore", "keystore"), ("*.kdbx", "KeePass database"), ("*.ppk", "PuTTY private key"),
    (".env", "environment secrets"), (".env.*", "environment secrets"), ("*.env", "environment secrets"),
    (".netrc", "login credentials"), ("_netrc", "login credentials"), (".git-credentials", "Git credentials"),
    (".npmrc", "package registry token"), (".pypirc", "package registry token"),
    ("credentials", "credentials"), ("credentials.json", "credentials"), ("credentials.*", "credentials"),
    ("client_secret*.json", "OAuth client secret"), ("token.json", "OAuth token"),
    ("*.tfstate", "infrastructure secrets"), ("secrets.*", "secrets"), ("wallet.dat", "crypto wallet"),
    ("login data", "browser saved passwords"), ("login data-journal", "browser saved passwords"),
    ("cookies", "browser cookies"), ("key4.db", "browser saved passwords"), ("logins.json", "browser saved passwords"),
    ("local state", "browser encryption key"),
)

#: Path fragments (lower case, forward slashes) that mark operating-system secret stores.
_SECRET_FRAGMENTS = (
    ("/appdata/roaming/microsoft/credentials/", "Windows credential store"),
    ("/appdata/local/microsoft/credentials/", "Windows credential store"),
    ("/appdata/roaming/microsoft/protect/", "Windows DPAPI master keys"),
    ("/appdata/roaming/microsoft/crypto/", "Windows key store"),
    ("/windows/system32/config/", "Windows registry hives"),
    ("/library/keychains/", "macOS keychain"),
    ("/etc/shadow", "system password hashes"),
    ("/etc/sudoers", "system privileges"),
)

#: Files in the assistant's own data folder that steer or prove what it does.
_OWN_SECRETS = (
    ("audit_signing.key", "the assistant's audit signing key"),
    ("*.dpapi", "a key protected for this account"),
    ("oauth_tokens*", "the assistant's account tokens"),
    ("api_key*", "the assistant's API key"),
    ("settings.toml", "the assistant's settings"),
)


def _components(path: PurePath) -> list[str]:
    return [p.lower() for p in path.parts]


def sensitive_reason(path: str | os.PathLike[str]) -> str:
    """Why the assistant must not touch *path* ("SSH keys", ...), or "" when it may."""
    text = os.fspath(path).strip().strip('"').strip("'")
    if not text:
        return ""
    expanded = os.path.expandvars(os.path.expanduser(text))
    try:
        resolved = Path(expanded).resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        resolved = Path(expanded)
    for candidate in {PurePath(expanded), PurePath(resolved)}:
        reason = _reason_for(candidate)
        if reason:
            return reason
    return ""


def _reason_for(path: PurePath) -> str:
    parts = _components(path)
    for part in parts[:-1] if len(parts) > 1 else []:
        if part in _SECRET_FOLDERS:
            return _SECRET_FOLDERS[part]
    if parts and parts[-1] in _SECRET_FOLDERS:
        return _SECRET_FOLDERS[parts[-1]]
    name = parts[-1] if parts else ""
    for pattern, reason in _SECRET_NAMES:
        if fnmatch.fnmatchcase(name, pattern):
            # A template is meant to be shared and holds no secret.
            if name.endswith((".example", ".sample", ".template", ".dist")):
                return ""
            return reason
    joined = "/" + "/".join(parts).replace("\\", "/")
    for fragment, reason in _SECRET_FRAGMENTS:
        if fragment in joined + "/":
            return reason
    if _in_own_data(path):
        for pattern, reason in _OWN_SECRETS:
            if fnmatch.fnmatchcase(name, pattern):
                return reason
    return ""


def _in_own_data(path: PurePath) -> bool:
    try:
        from Agent_Guru.utils.path_utils import app_data_dir

        own = app_data_dir(create=False)
    except Exception:
        return False
    try:
        return PurePath(Path(path).resolve(strict=False)).is_relative_to(own.resolve(strict=False))
    except (OSError, ValueError):
        return False


class SensitivePathError(PermissionError):
    """A path the assistant is not allowed to touch; the message says why without the content."""


def check_path(path: str | os.PathLike[str], action: str = "use") -> None:
    """Raise SensitivePathError if *path* is one the assistant must not *action*."""
    reason = sensitive_reason(path)
    if reason:
        msg = f"I don't {action} {Path(os.fspath(path)).name or os.fspath(path)}: it holds {reason}"
        raise SensitivePathError(msg)


# A path-looking token inside free text or a tool argument: drive or root
# anchored, home-relative, or a bare name with a path separator.
_PATHISH = re.compile(r"(?:[A-Za-z]:[\\/]|~[\\/]|\.{0,2}[\\/]|%[A-Za-z_]+%[\\/])[^\s\"'<>|]*|[^\s\"'<>|]*[\\/][^\s\"'<>|]+")


def _strings(value: Any, depth: int = 0) -> Iterator[str]:
    if depth > 8:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(k, depth + 1)
            yield from _strings(v, depth + 1)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v, depth + 1)


def sensitive_paths_in(value: Any) -> list[tuple[str, str]]:
    """(path, reason) for every sensitive path named anywhere in *value* (a string, dict or list)."""
    found: list[tuple[str, str]] = []
    for text in _strings(value):
        # The whole string is a path candidate only when no path-like token
        # was found inside it, so a sentence is not reported as a path.
        tokens = _PATHISH.findall(text)
        candidates: Iterable[str] = tokens or ([text] if len(text) < 400 else [])
        for candidate in candidates:
            reason = sensitive_reason(candidate)
            if reason and all(candidate != p for p, _ in found):
                found.append((candidate, reason))
    return found
