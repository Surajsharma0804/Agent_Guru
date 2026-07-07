"""Package Manager for the Guru Deployment System.

Handles downloading, installing, updating, and removing Python packages.
Implements streaming downloads and retry with exponential backoff.

Time Complexity: O(1) per chunk for streaming operations
Space Complexity: O(chunk_size) — bounded memory for large packages
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import subprocess  # nosec B404
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import structlog

from .exceptions import (
    InstallationError,
    NetworkError,
    PackageNotFoundError,
)
from .models import AuditLogEntry, Configuration, OperationType, PackageInfo

logger = structlog.get_logger(__name__)

_CHUNK_SIZE = 65536  # 64 KB
_DEFAULT_TIMEOUT = 30

class PackageManager:
    """Downloads, installs, updates, and removes Python packages.

    Uses pip subprocess for actual installation. Maintains a SQLite
    registry of installed packages.
    """

    def __init__(self, config: Configuration, db_path: Path | None = None) -> None:
        self._config = config
        self._cache_dir = config.cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path or (config.cache_dir / "package_registry.db")
        self._init_db()
        self._audit_entries: list[AuditLogEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def download_package(
        self,
        package_name: str,
        version: str,
        repo_url: str,
    ) -> Path:
        """Download a package from a repository with retry + exponential backoff.

        Returns path to the downloaded file.
        Raises NetworkError after max_retries exhausted.
        """
        dest = self._cache_dir / f"{package_name}-{version}.whl"
        if dest.exists():
            logger.debug("package_cache_hit", package=package_name, version=version)
            return dest

        url = f"{repo_url.rstrip('/')}/{package_name}/{version}/{package_name}-{version}.whl"
        last_exc: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                await self._stream_download(url, dest)
                self._audit(OperationType.DOWNLOAD, package_name, version, "SUCCESS", {})
                logger.info("package_downloaded", package=package_name, version=version)
                return dest
            except Exception as exc:
                last_exc = exc
                if attempt < self._config.max_retries:
                    delay = 2**attempt
                    logger.exception(
                        "download_retry",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
        self._audit(
            OperationType.DOWNLOAD,
            package_name,
            version,
            "FAILURE",
            {"error": str(last_exc)},
        )
        msg = (
            f"Failed to download '{package_name}=={version}' after "
            f"{self._config.max_retries} retries: {last_exc}"
        )
        raise NetworkError(
            msg,
        )

    def install_package(self, package_path: Path, target_env: Path) -> None:
        """Install a package into the target Python environment using pip.

        Raises InstallationError on failure and cleans up partial artifacts.
        """
        if not package_path.exists():
            msg = f"Package file not found: {package_path}"
            raise InstallationError(msg)

        python = target_env / "bin" / "python"
        if not python.exists():
            python = target_env / "Scripts" / "python.exe"  # Windows
        if not python.exists():
            python = Path(sys.executable)

        start = time.monotonic()
        try:
            result = subprocess.run(  # nosec B603  # noqa: S603
                [str(python), "-m", "pip", "install", str(package_path), "--quiet", "--no-deps"],
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                msg = f"pip install failed: {result.stderr.strip()}"
                raise InstallationError(msg)
        except subprocess.TimeoutExpired as exc:
            self._cleanup_partial(package_path)
            msg = f"Installation timed out: {exc}"
            raise InstallationError(msg) from exc
        duration = time.monotonic() - start
        pkg_name = package_path.stem.split("-")[0]
        pkg_version = package_path.stem.split("-")[1] if "-" in package_path.stem else "0.0.0"
        self._register_package(pkg_name, pkg_version, target_env, package_path)
        self._audit(
            OperationType.INSTALL,
            pkg_name,
            pkg_version,
            "SUCCESS",
            {"duration_s": round(duration, 3)},
        )
        logger.info(
            "package_installed",
            package=pkg_name,
            version=pkg_version,
            duration_s=round(duration, 3),
        )

    def remove_package(self, package_name: str, target_env: Path) -> None:
        """Remove a package from the target environment.

        Raises PackageNotFoundError if not installed.
        """
        if not self._is_registered(package_name):
            msg = f"Package '{package_name}' is not installed"
            raise PackageNotFoundError(msg)

        python = self._resolve_python(target_env)
        result = subprocess.run(  # nosec B603  # noqa: S603
            [str(python), "-m", "pip", "uninstall", package_name, "-y", "--quiet"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            msg = f"pip uninstall failed: {result.stderr.strip()}"
            raise InstallationError(msg)

        self._unregister_package(package_name)
        self._audit(OperationType.REMOVE, package_name, None, "SUCCESS", {})
        logger.info("package_removed", package=package_name)

    def get_installed_packages(self, target_env: Path) -> list[PackageInfo]:
        """Return list of installed packages from the registry."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, version, install_path, dependencies, metadata, "
                "install_timestamp, checksum FROM packages",
            ).fetchall()
        packages = []
        for row in rows:
            packages.append(
                PackageInfo(
                    name=row[0],
                    version=row[1],
                    install_path=Path(row[2]),
                    dependencies=json.loads(row[3]) if row[3] else [],
                    metadata=json.loads(row[4]) if row[4] else {},
                    install_timestamp=datetime.fromisoformat(row[5]),
                    checksum=row[6] or "",
                ),
            )
        return packages

    def verify_checksum(self, package_path: Path, expected_hash: str) -> bool:
        """Verify package integrity using SHA-256.

        Streams the file to avoid loading large packages into memory.
        """
        hasher = hashlib.sha256()
        with self._resolve_cache_path(package_path).open("rb") as fh:
            while chunk := fh.read(_CHUNK_SIZE):
                hasher.update(chunk)
        actual = hasher.hexdigest()
        return actual == expected_hash

    def get_audit_entries(self) -> list[AuditLogEntry]:
        """Return in-memory audit entries."""
        return list(self._audit_entries)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _stream_download(self, url: str, dest: Path) -> None:
        """Stream download to disk. Raises on HTTP error."""
        try:
            import aiohttp  # type: ignore[import]
        except ImportError:
            # Fallback: use urllib for environments without aiohttp
            import urllib.request

            urllib.request.urlretrieve(url, str(dest))  # nosec B310
        timeout = aiohttp.ClientTimeout(total=self._config.network_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    msg = f"HTTP {resp.status} for {url}"
                    raise NetworkError(msg)
                with self._resolve_cache_path(dest).open("wb") as fh:
                    async for chunk in resp.content.iter_chunked(_CHUNK_SIZE):
                        fh.write(chunk)

    def _cleanup_partial(self, package_path: Path) -> None:
        """Remove partial installation artifacts."""
        tmp = self._cache_dir / f"_partial_{package_path.name}"
        for p in [tmp]:
            if p.exists():
                p.unlink(missing_ok=True)

    def _register_package(
        self,
        name: str,
        version: str,
        target_env: Path,
        package_path: Path,
    ) -> None:
        checksum = ""
        if package_path.exists():
            hasher = hashlib.sha256()
            with self._resolve_cache_path(package_path).open("rb") as fh:
                while chunk := fh.read(_CHUNK_SIZE):
                    hasher.update(chunk)
            checksum = hasher.hexdigest()

        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO packages
                    (name, version, install_path, dependencies, metadata,
                     install_timestamp, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, version, str(target_env), "[]", "{}", now, checksum),
            )

    def _unregister_package(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM packages WHERE name = ?", (name,))

    def _is_registered(self, name: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM packages WHERE name = ?", (name,)).fetchone()
        return row is not None

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

    def _resolve_python(self, target_env: Path) -> Path:
        """Resolve the Python executable inside *target_env*.

        Tries ``bin/python`` (Unix) then ``Scripts/python.exe`` (Windows),
        falling back to the current interpreter.
        """
        python = target_env / "bin" / "python"
        if not python.exists():
            python = target_env / "Scripts" / "python.exe"
        if not python.exists():
            python = Path(sys.executable)
        return python

    def _audit(
        self,
        operation: OperationType,
        package_name: str,
        version: str | None,
        result: str,
        details: dict,
    ) -> None:
        self._audit_entries.append(
            AuditLogEntry(
                timestamp=datetime.now(UTC),
                operation=operation,
                result=result,
                package_name=package_name,
                version=version,
                details=details,
            ),
        )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS packages (
                    name TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    install_path TEXT NOT NULL,
                    dependencies TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    install_timestamp TEXT NOT NULL,
                    checksum TEXT NOT NULL DEFAULT ''
                )
                """,
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.isolation_level = None  # autocommit for context manager usage
        return conn
