"""Model files checked against pinned sizes and hashes before anything loads them.

One implementation for every downloaded model: the Kokoro voice
(speech/tts/tts_engine.py, speech/filler_response.py) and the injection
classifier (security/injection_classifier.py).

Kokoro's downloader used to rename a file to its real name and only then
check its hash, and its hashes were never pinned, so any bytes that
arrived were loaded. Here a download is written to "<name>.part", its
size and hash are checked, and only then is it renamed: a cut-off or
altered download never carries the real name. After a full check the
folder gets a stamp of each file's size and modification time; a later
start that finds them unchanged skips re-hashing (the Kokoro model takes
about 0.5 s to hash), and any change means a full check again.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

STAMP_NAME = "verified.json"
_CHUNK = 1 << 20


@dataclass(frozen=True)
class PinnedFile:
    """A file's expected name, size and digest. kind is "sha256" or "git-sha1" (a git blob id)."""

    name: str
    size: int
    digest: str
    kind: str = "sha256"


class VerificationError(RuntimeError):
    """A file is missing or is not the pinned file; the message says which and how."""


def file_digest(path: Path, kind: str = "sha256") -> str:
    if kind == "sha256":
        h = hashlib.sha256()
    elif kind == "git-sha1":
        h = hashlib.sha1(f"blob {path.stat().st_size}\0".encode(), usedforsecurity=False)
    else:
        msg = f"unknown digest kind {kind!r}"
        raise ValueError(msg)
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def problems(path: Path, pin: PinnedFile) -> str:
    """Why *path* is not the pinned file, or "" when it is."""
    if not path.is_file():
        return f"{path.name} is missing"
    size = path.stat().st_size
    if size != pin.size:
        return f"{path.name} is {size} bytes, expected {pin.size}"
    if file_digest(path, pin.kind) != pin.digest:
        return f"{path.name} does not match its pinned {pin.kind} hash"
    return ""


def verify(directory: Path, pins: Iterable[PinnedFile]) -> list[str]:
    """Every problem with the files in *directory*; empty when all match."""
    return [p for pin in pins if (p := problems(directory / pin.name, pin))]


def _stamp_entry(path: Path) -> list[int]:
    st = path.stat()
    return [st.st_size, st.st_mtime_ns]


def write_stamp(directory: Path, pins: Iterable[PinnedFile], extra: dict | None = None) -> None:
    stamp = {"files": {pin.name: [*_stamp_entry(directory / pin.name), pin.digest] for pin in pins}, **(extra or {})}
    (directory / STAMP_NAME).write_text(json.dumps(stamp), encoding="utf-8")


def stamp_matches(directory: Path, pins: Iterable[PinnedFile], extra: dict | None = None) -> bool:
    """True if every file is the one last fully verified here (same size, time and pinned digest)."""
    pins = list(pins)
    try:
        stamp = json.loads((directory / STAMP_NAME).read_text(encoding="utf-8"))
        if any(stamp.get(k) != v for k, v in (extra or {}).items()):
            return False
        files = stamp["files"]
        if set(files) != {pin.name for pin in pins}:
            return False
        return all(files[pin.name] == [*_stamp_entry(directory / pin.name), pin.digest] for pin in pins)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def ensure_verified(directory: Path, pins: Iterable[PinnedFile], extra: dict | None = None) -> None:
    """Return if the files are the pinned ones; raise VerificationError otherwise.

    Uses the stamp when nothing changed since the last full check, so a
    normal start does not re-hash; works offline.
    """
    pins = list(pins)
    if stamp_matches(directory, pins, extra):
        return
    found = verify(directory, pins)
    if found:
        raise VerificationError("; ".join(found))
    write_stamp(directory, pins, extra)


def _replace_verified(part: Path, dest: Path, pin: PinnedFile) -> None:
    """Rename *part* to *dest* only if it is the pinned file; delete it otherwise."""
    try:
        found = problems(part, pin)
        if found:
            msg = f"{dest.name}: {found.replace(part.name, 'the download')}"
            raise VerificationError(msg)
        os.replace(part, dest)
    finally:
        part.unlink(missing_ok=True)


class DownloadError(OSError):
    """A download that stopped early. The message names the host, the file and how far it got."""


class DownloadCancelled(Exception):  # noqa: N818 - a request, not a failure
    """The caller asked the download to stop; the bytes so far are kept for a resume."""


def download(url: str, dest: Path, pin: PinnedFile, *, timeout: float = 60.0,
             progress: Callable[[str, int, int], None] | None = None, resume: bool = False,
             should_stop: Callable[[], bool] | None = None) -> None:
    """Fetch *url* into *dest*, verified; *dest* is untouched unless the new file is the pinned one.

    With resume=False (the model loaders) a download that stops for any
    reason leaves nothing behind, as before. With resume=True (the
    installer) the bytes already in "<name>.part" are kept when the
    connection drops or the caller cancels, and the next call asks the
    server for the rest with an HTTP Range request. Without it, a 743 MB
    cuDNN wheel cut off at 700 MB started again from zero. A server that
    ignores Range gets a fresh start; a partial file longer than the pin is
    discarded. Bytes from two attempts are still checked as one file
    against the pinned size and hash before the real name is given.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    host = urllib.parse.urlsplit(url).hostname or url
    have = part.stat().st_size if resume and part.exists() else 0
    if have > pin.size:
        part.unlink()
        have = 0
    if resume and have == pin.size:
        _replace_verified(part, dest, pin)
        return
    headers = {"User-Agent": "Agent_Guru"}
    if have:
        headers["Range"] = f"bytes={have}-"
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    done = have
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310  # nosec B310
            if have and getattr(response, "status", 200) != 206:
                done = 0  # the server sent the whole file: start the part again
            with part.open("ab" if done else "wb") as fh:
                while chunk := response.read(_CHUNK):
                    done += len(chunk)
                    if done > pin.size:
                        msg = f"{dest.name}: more data than the pinned {pin.size} bytes"
                        raise VerificationError(msg)
                    fh.write(chunk)
                    if progress:
                        progress(dest.name, done, pin.size)
                    if should_stop and should_stop():
                        raise DownloadCancelled(f"{dest.name}: stopped at {done} of {pin.size} bytes")
    except VerificationError:
        part.unlink(missing_ok=True)
        raise
    except BaseException as exc:
        if not resume:
            part.unlink(missing_ok=True)
            raise
        if isinstance(exc, OSError):
            msg = (f"{host}: {dest.name}: {type(exc).__name__}: {exc} after {done} of {pin.size} bytes; "
                   "the bytes so far are kept and the next attempt resumes")
            raise DownloadError(msg) from exc
        raise
    _replace_verified(part, dest, pin)


def copy_in(source: Path, dest: Path, pin: PinnedFile) -> None:
    """Copy *source* to *dest*, verified (an install without internet)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        shutil.copyfile(source, part)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    _replace_verified(part, dest, pin)
