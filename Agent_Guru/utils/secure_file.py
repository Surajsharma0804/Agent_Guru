"""Shared secure-file helpers for Agent Guru.

This module exists to REMOVE duplication, not to add another way of doing
things. Two byte-identical copies of ``_restrict_file_permissions`` lived in
``platform/features/user_memory.py`` and ``speech/biometric/speaker_verifier.py``
(each one's docstring notes the gap was "already found and fixed" in a sibling
module -- which is what copy-paste looks like from the inside). Both now call
the single implementation here, and a third site that had no protection at all
-- ``memory/conversation_memory.py``, which writes the AES-256 key for the
user's entire conversation history -- uses it too.

It also closes a gap every copy shared: they chmod'd the file *after* writing
it, so the data sat on disk under the process umask (commonly world-readable)
for the duration of the write. ``secure_write_bytes`` creates the file
owner-only from its first byte and swaps it into place atomically, so a crash
mid-write cannot truncate the previous contents either.

Security scope:
    Owner-only permissions are defense-in-depth for personal data on a
    shared machine. They are not a boundary against a local attacker running
    as the same user, nor against root/Administrator.

Performance:
    - restrict_file_permissions: one syscall on Unix; one short subprocess on
      Windows, bounded by a 5s timeout.
    - secure_write_bytes: O(n) in the payload, one fsync per write.
"""

from __future__ import annotations

import contextlib
import logging
import os
import stat
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

#: Owner read/write only (0o600).
OWNER_ONLY = stat.S_IRUSR | stat.S_IWUSR


def restrict_file_permissions(path: Path) -> None:
    """Best-effort: restrict *path* to owner-only access.

    Unix: chmod 0600.
    Windows: ``icacls`` granting only the current user and removing inherited
    broader ACEs, using the built-in tool so no extra dependency (pywin32) is
    needed. chmod alone is close to a no-op on Windows, which is why the ACL
    path exists at all.

    Failures are logged at debug level and never raise: this is hardening
    layered on top of a save, and it must not be able to fail the save.
    """
    try:
        if os.name != "nt":
            path.chmod(OWNER_ONLY)
            return

        import subprocess  # nosec B404

        user = os.environ.get("USERNAME", "")
        if not user:
            logger.debug("Could not determine USERNAME - skipping Windows ACL restriction")
            return
        subprocess.run(  # nosec B603 B607
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        logger.debug("Best-effort file-permission restriction failed for %s", path, exc_info=True)


def restrict_dir_permissions(path: Path) -> None:
    """Best-effort: restrict a directory to owner-only access (0o700 on Unix).

    A 0600 file inside a 0755 directory is still unreadable by others, but a
    private directory also hides the file's existence, size and mtime -- which
    for a conversation-history store is itself information about the user.
    """
    try:
        if os.name != "nt":
            path.chmod(stat.S_IRWXU)  # 0o700
            return
        restrict_file_permissions(path)
    except Exception:
        logger.debug(
            "Best-effort directory-permission restriction failed for %s", path, exc_info=True,
        )


def secure_write_bytes(path: Path, data: bytes) -> None:
    """Atomically write *data* to *path*, owner-only from the first byte.

    Why both properties matter together:

    * **Owner-only from the start.** Writing the file and *then* chmod'ing it
      leaves a window in which sensitive bytes are readable under whatever the
      process umask allows. ``tempfile.mkstemp`` creates its file 0600, so the
      data is never on disk under looser permissions.
    * **Atomic replace.** ``Path.write_bytes`` truncates before writing, so a
      crash partway through destroys the previous contents. For an AES-GCM
      blob a truncated file is not partially readable, it is *entirely*
      unreadable -- the whole history would be gone. Writing to a temporary
      file in the same directory and calling ``os.replace`` means a reader
      sees either the old file or the new one, never a torn one.

    ``os.replace`` is atomic on POSIX and on Windows, and the temporary file is
    created in the destination directory so the rename never crosses a
    filesystem boundary.

    Note: the file's bytes are fsync'd, but the parent directory entry is not
    (there is no portable way to fsync a directory on Windows). That guarantees
    readers never observe a torn file; it does not guarantee the rename itself
    survives a power loss on every filesystem.

    Raises:
        OSError: if the file cannot be written or replaced.

    """
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    replaced = False
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        restrict_file_permissions(tmp)
        os.replace(tmp, path)
        replaced = True
    finally:
        if not replaced:
            with contextlib.suppress(OSError):
                tmp.unlink()

    # Re-apply to the final name: on Windows the ACL is attached to the path,
    # and on Unix this is a cheap idempotent chmod.
    restrict_file_permissions(path)
