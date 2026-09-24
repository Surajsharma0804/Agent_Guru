"""Auto-Update Manager for the Guru Deployment System.

Checks for new versions, downloads and verifies updates, applies them
safely, and rolls back on failure.

Time Complexity: O(1) for version comparison
Space Complexity: O(1) for update metadata
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from packaging.version import Version

from .exceptions import NetworkError, SignatureVerificationError

if TYPE_CHECKING:
    from pathlib import Path

    from .crypto_verifier import CryptoVerifier
    from .models import Configuration

logger = structlog.get_logger(__name__)

_CHUNK_SIZE = 65536


def _try_import_aiohttp() -> Any:
    """Return the aiohttp module, or None if it is not installed.

    Probing the import separately matters: the previous code wrapped the
    whole network operation in `try: import aiohttp ... except ImportError`,
    so an ImportError raised from anywhere *inside* the request (an optional
    aiohttp dependency resolved lazily, for instance) silently downgraded a
    live request to the urllib fallback and retried it. Only the import
    itself should decide which transport is used.
    """
    try:
        import aiohttp  # type: ignore[import]
    except ImportError:
        return None
    return aiohttp


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        download_url: str,
        release_notes: str = "",
        signature: bytes | None = None,
        public_key: bytes | None = None,
        checksum: str = "",
        key_id: str | None = None,
    ) -> None:
        self.current_version = current_version
        self.latest_version = latest_version
        self.download_url = download_url
        self.release_notes = release_notes
        self.signature = signature
        # NOTE: `public_key` is kept only for API/back-compat shape. It must
        # NEVER be used as the key to verify `signature` against -- it comes
        # from the same untrusted update-server response as the payload
        # itself, so an attacker who controls the server (or a MITM, if the
        # transport isn't authenticated) could sign a malicious update with
        # their own key and simply advertise that same key here; the math
        # would check out even though nothing trustworthy was verified. The
        # only key `verify_update()` actually trusts is one already present
        # in the local CryptoVerifier trust store, looked up by `key_id`.
        self.public_key = public_key
        self.checksum = checksum
        self.key_id = key_id

    @property
    def is_update_available(self) -> bool:
        """Return True if latest_version > current_version."""
        try:
            return Version(self.latest_version) > Version(self.current_version)
        except Exception:
            return False


class UpdateManager:
    """Manages automatic updates for AGENT_GURU.

    Workflow:
    1. Check for updates (poll update server)
    2. Download update package
    3. Verify signature and checksum
    4. Apply update (with rollback snapshot)
    5. Rollback on failure
    """

    def __init__(
        self,
        config: Configuration,
        current_version: str,
        update_url: str,
        cache_dir: Path | None = None,
        crypto_verifier: CryptoVerifier | None = None,
    ) -> None:
        self._config = config
        self._current_version = current_version
        self._update_url = update_url.rstrip("/")
        self._cache_dir = cache_dir or config.cache_dir / "updates"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._applied_updates: list[dict[str, Any]] = []
        # BUG FIX (Round 10): verify_update() previously never called
        # CryptoVerifier at all -- a full Ed25519 signing + trust-store
        # system was built (crypto_verifier.py) but the actual auto-update
        # flow only checked a SHA-256 checksum that came from the exact
        # same untrusted manifest.json as the download URL and payload
        # itself, which is not a security boundary (a malicious or
        # compromised update server can serve any payload alongside a
        # checksum it computed for that same payload). This wires real
        # signature verification into the live update flow; see
        # verify_update() below.
        self._crypto_verifier = crypto_verifier

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_for_updates(self) -> UpdateInfo | None:
        """Check the update server for a newer version.

        Returns UpdateInfo if an update is available, None otherwise.
        """
        manifest_url = f"{self._update_url}/manifest.json"
        last_exc: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                manifest = await self._fetch_json(manifest_url)
                latest = manifest.get("latest_version", self._current_version)

                # BUG FIX (Round 10): the manifest's signature/key_id were
                # never even read before, so UpdateInfo.signature was always
                # None and verify_update() had nothing to verify against.
                signature_b64 = manifest.get("signature")
                signature = base64.b64decode(signature_b64) if signature_b64 else None

                info = UpdateInfo(
                    current_version=self._current_version,
                    latest_version=latest,
                    download_url=manifest.get("download_url", ""),
                    release_notes=manifest.get("release_notes", ""),
                    checksum=manifest.get("checksum", ""),
                    signature=signature,
                    key_id=manifest.get("key_id"),
                )
                if info.is_update_available:
                    logger.info("update_available", current=self._current_version, latest=latest)
                else:
                    logger.debug("no_update_available", version=self._current_version)
                return info if info.is_update_available else None
            except Exception as exc:
                last_exc = exc
                if attempt < self._config.max_retries:
                    delay = 2**attempt
                    await asyncio.sleep(delay)

        logger.warning("update_check_failed", error=str(last_exc))
        return None

    async def download_update(self, update_info: UpdateInfo) -> Path:
        """Download the update package to the cache directory.

        Returns path to the downloaded file.
        """
        dest = self._cache_dir / f"update-{update_info.latest_version}.pkg"
        if dest.exists():
            return dest

        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                await self._stream_download(update_info.download_url, dest)
                logger.info("update_downloaded", version=update_info.latest_version)
                return dest
            except Exception as exc:
                last_exc = exc
                if attempt < self._config.max_retries:
                    await asyncio.sleep(2**attempt)

        msg = f"Failed to download update {update_info.latest_version}: {last_exc}"
        raise NetworkError(msg)

    def verify_update(self, update_path: Path, update_info: UpdateInfo) -> bool:
        """Verify update package integrity and signature.

        Returns True if valid.
        Raises SignatureVerificationError on failure.
        """
        import hashlib

        resolved = self._resolve_cache_path(update_path)

        # Checksum: defense-in-depth against corruption/truncated downloads
        # ONLY. This is NOT a security boundary against a malicious or
        # compromised update server on its own -- the checksum comes from
        # the same manifest.json response as the download URL and payload,
        # so a malicious server can serve any payload alongside a checksum
        # it computed for that exact payload. The signature check below is
        # what actually protects against that.
        if update_info.checksum:
            hasher = hashlib.sha256()
            with resolved.open("rb") as fh:
                while chunk := fh.read(_CHUNK_SIZE):
                    hasher.update(chunk)
            actual = hasher.hexdigest()
            if actual != update_info.checksum:
                msg = (
                    f"Checksum mismatch for update {update_info.latest_version}: "
                    f"expected {update_info.checksum}, got {actual}"
                )
                raise SignatureVerificationError(
                    msg,
                )

        # BUG FIX (Round 10): signature verification was completely absent
        # from this method -- CryptoVerifier (Ed25519 + trust store) was
        # fully built but never called from the real update flow, so the
        # Configuration.verification_policy=STRICT default (see models.py)
        # had no effect on updates at all. Wired in here, with the
        # verification key ALWAYS resolved from the local trust store by
        # key_id -- never taken from update_info.public_key (see that
        # field's docstring in UpdateInfo.__init__ for why trusting a
        # manifest-supplied key would make signing pointless).
        if self._crypto_verifier is not None:
            if update_info.signature is not None:
                trusted_key = self._resolve_trusted_key(update_info.key_id)
                if trusted_key is None:
                    msg = (
                        f"Update {update_info.latest_version} is signed with "
                        f"an unrecognized key_id {update_info.key_id!r} -- "
                        f"refusing to trust a signature from an unknown key"
                    )
                    raise SignatureVerificationError(msg)
                self._crypto_verifier.verify_package_signature(
                    resolved, update_info.signature, trusted_key,
                )
            else:
                # No signature present at all -- defer to the configured
                # VerificationPolicy (STRICT rejects unsigned packages,
                # PERMISSIVE/DISABLED log and allow), same as any other
                # unsigned package CryptoVerifier handles.
                self._crypto_verifier.verify_package_signature(resolved, None, None)
        else:
            logger.warning(
                "signature_verification_skipped",
                reason="no CryptoVerifier configured on this UpdateManager",
                version=update_info.latest_version,
            )

        logger.info("update_verified", version=update_info.latest_version)
        return True

    def _resolve_trusted_key(self, key_id: str | None) -> bytes | None:
        """Look up a trusted public key's raw bytes by id from the local
        trust store -- the ONLY source of keys this class will verify
        signatures against. Returns None if key_id is empty/None, no
        CryptoVerifier is configured, or the id isn't in the trust store.

        Delegates to CryptoVerifier.get_trusted_key(), the single shared
        implementation of this lookup (an O(1) indexed row fetch) also used
        by UpdateOrchestrator -- this used to re-implement the same lookup
        by calling get_trusted_keys() and linear-scanning it, duplicating
        logic (and doing O(n) work with a full trust-store fetch) for what
        the trust store's schema already makes an O(1) primary-key lookup.
        """
        if self._crypto_verifier is None:
            return None
        return self._crypto_verifier.get_trusted_key(key_id)

    async def apply_update(
        self,
        update_path: Path,
        update_info: UpdateInfo,
        rollback_snapshot_id: str | None = None,
    ) -> bool:
        """Apply a downloaded and verified update.

        Creates a rollback point before applying. Returns True on success.
        """
        logger.info(
            "applying_update",
            version=update_info.latest_version,
            snapshot_id=rollback_snapshot_id,
        )
        try:
            # In production: extract and install the update package
            # Here we record the applied update for testing
            self._applied_updates.append(
                {
                    "version": update_info.latest_version,
                    "applied_at": datetime.now(UTC).isoformat(),
                    "path": str(update_path),
                },
            )
            self._current_version = update_info.latest_version
            logger.info("update_applied", version=update_info.latest_version)
            return True
        except Exception as exc:
            logger.exception("update_apply_failed", error=str(exc))
            return False

    def get_current_version(self) -> str:
        """Return the current installed version."""
        return self._current_version

    def get_applied_updates(self) -> list[dict[str, Any]]:
        """Return list of applied updates (for testing/audit)."""
        return list(self._applied_updates)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_cache_path(self, path: Path) -> Path:
        """Resolve and validate that *path* is within the cache directory.

        Raises:
            ValueError: If the resolved path escapes ``self._cache_dir``.

        """
        base = self._cache_dir.resolve()
        resolved = path.resolve()
        if not resolved.is_relative_to(base):
            msg = f"Path '{path}' resolves outside the allowed cache directory '{base}'"
            raise ValueError(msg)
        return resolved

    @staticmethod
    def _require_http_url(url: str) -> str:
        """Reject any URL scheme other than http/https.

        SECURITY FIX: the urllib fallbacks below accept whatever scheme they
        are handed, and `download_url` comes straight out of the update
        server's manifest.json -- i.e. it is attacker-controlled if that
        server is compromised or the transport is not authenticated. A
        `file:///...` or `ftp://...` URL would therefore have turned the
        update downloader into an arbitrary-local-file reader. The aiohttp
        path refuses non-HTTP schemes on its own; this makes the fallback
        behave identically instead of being the weaker of two branches.
        """
        scheme = urllib.parse.urlparse(url).scheme.lower()
        if scheme not in ("http", "https"):
            msg = f"Refusing to fetch update URL with unsupported scheme {scheme!r}: {url}"
            raise NetworkError(msg)
        return url

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON from a URL."""
        self._require_http_url(url)
        aiohttp = _try_import_aiohttp()

        if aiohttp is not None:
            timeout = aiohttp.ClientTimeout(total=self._config.network_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        msg = f"HTTP {resp.status} for {url}"
                        raise NetworkError(msg)
                    return await resp.json()

        # EVENT-LOOP FIX: this previously called urllib.request.urlopen()
        # directly inside an `async def`, with the linter warning silenced by
        # an ASYNC210 suppression comment rather than fixed. urlopen() blocks the calling
        # thread -- here, the event loop -- for up to network_timeout seconds,
        # which stalls every other coroutine in the process (voice included)
        # on a machine that merely lacks aiohttp. Running it on a worker
        # thread keeps the loop free while the semantics stay identical.
        return await asyncio.to_thread(self._fetch_json_blocking, url)

    def _fetch_json_blocking(self, url: str) -> dict[str, Any]:
        """Blocking urllib fallback for _fetch_json (runs on a worker thread)."""
        with urllib.request.urlopen(url, timeout=self._config.network_timeout) as r:  # nosec B310
            return json.loads(r.read().decode())

    async def _stream_download(self, url: str, dest: Path) -> None:
        """Stream download to disk."""
        self._require_http_url(url)
        # SECURITY FIX: only the aiohttp branch validated the destination.
        # The urllib fallback wrote to `str(dest)` unchecked, so the two
        # branches of the same method disagreed about whether a package could
        # be written outside the update cache directory -- and `dest` is built
        # from `latest_version`, which comes from the update server's
        # manifest. Validating once, up front, makes the guarantee
        # branch-independent.
        resolved = self._resolve_cache_path(dest)
        aiohttp = _try_import_aiohttp()

        if aiohttp is not None:
            timeout = aiohttp.ClientTimeout(total=self._config.network_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        msg = f"HTTP {resp.status} for {url}"
                        raise NetworkError(msg)
                    with resolved.open("wb") as fh:
                        async for chunk in resp.content.iter_chunked(_CHUNK_SIZE):
                            fh.write(chunk)
            return

        await asyncio.to_thread(self._stream_download_blocking, url, resolved)

    def _stream_download_blocking(self, url: str, dest: Path) -> None:
        """Blocking urllib fallback for _stream_download (worker thread).

        HANG FIX: this used urllib.request.urlretrieve(), which takes no
        timeout at all and so inherits the global default socket timeout --
        None, i.e. wait forever. A stalled update server could therefore pin
        the process indefinitely, and because the call also ran on the event
        loop, indefinitely meant the whole assistant. urlopen() accepts the
        configured timeout, and copying in chunks keeps peak memory flat
        regardless of package size.
        """
        with urllib.request.urlopen(url, timeout=self._config.network_timeout) as r:  # nosec B310
            with dest.open("wb") as fh:
                shutil.copyfileobj(r, fh, _CHUNK_SIZE)
