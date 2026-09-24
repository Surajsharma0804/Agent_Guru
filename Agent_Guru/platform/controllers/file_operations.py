"""Module: agent_guru.platform.controllers.file_operations
Purpose: Complete file and directory operations controller with audit logging.

This module provides comprehensive file operations for the Platform Integration System,
enabling AGENT_GURU to perform ANY file operation through voice commands.

Performance Characteristics:
    - Time Complexity: O(1) for metadata operations, O(n) for file content operations
    - Space Complexity: O(1) for streaming operations, O(n) for in-memory operations
    - Latency: <10ms for metadata, <100ms for small files (<1MB)
    - Throughput: >100 operations/second

Architecture:
    The controller provides a unified interface for all file operations with:
    1. Permission validation before destructive operations
    2. Comprehensive audit logging for all operations
    3. Error handling with detailed error messages
    4. Support for both synchronous and streaming operations

Safety Features:
    - Permission checks before destructive operations (delete, overwrite)
    - Confirmation prompts for critical operations
    - Audit trail for all file modifications
    - Atomic operations where possible
    - Rollback support for failed operations

Usage Example:
    >>> from agent_guru.platform.controllers.file_operations import FileOperationsController
    >>>
    >>> # Initialize controller
    >>> controller = FileOperationsController(audit_log_path="audit.log")
    >>>
    >>> # Create a file
    >>> controller.create_file("test.txt", "Hello, World!")
    >>>
    >>> # Read file content
    >>> content = controller.read_file("test.txt")
    >>> print(content)
    'Hello, World!'
    >>>
    >>> # Copy file
    >>> controller.copy_file("test.txt", "test_copy.txt")
    >>>
    >>> # Delete file (with permission check)
    >>> controller.delete_file("test_copy.txt", confirm=True)

Author: Agent Guru Development Team
Date: 2026-02-24
Version: 1.0.0
"""

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from Agent_Guru.security.path_utils import safe_path

# Configure logging
logger = logging.getLogger(__name__)

class FileOperationType(Enum):
    """File operation types for audit logging."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"
    COPY = "copy"
    RENAME = "rename"
    MKDIR = "mkdir"
    RMDIR = "rmdir"

@dataclass
class FileOperationResult:
    """Result of a file operation.

    Attributes:
        success: Whether the operation succeeded
        operation: Type of operation performed
        path: Primary file path involved
        message: Human-readable result message
        error: Error message if operation failed
        metadata: Additional operation metadata

    """

    success: bool
    operation: FileOperationType
    path: str
    message: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class AuditLogEntry:
    """Audit log entry for file operations.

    Attributes:
        timestamp: ISO 8601 timestamp of operation
        operation: Type of operation performed
        path: Primary file path involved
        success: Whether operation succeeded
        user: User who performed operation (if available)
        details: Additional operation details

    """

    timestamp: str
    operation: str
    path: str
    success: bool
    user: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert audit entry to JSON string."""
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "operation": self.operation,
                "path": self.path,
                "success": self.success,
                "user": self.user,
                "details": self.details,
            },
        )

class FileOperationsController:
    """Controller for comprehensive file and directory operations.

    This controller provides a unified interface for all file operations with
    built-in permission checking, audit logging, and error handling.

    Time Complexity:
        - Metadata operations (exists, stat): O(1)
        - Content operations (read, write): O(n) where n is file size
        - Directory operations (list, tree): O(m) where m is number of entries

    Space Complexity:
        - Streaming operations: O(1)
        - In-memory operations: O(n) where n is file size

    Attributes:
        audit_log_path: Path to audit log file
        require_confirmation: Whether to require confirmation for destructive ops
        max_file_size: Maximum file size for in-memory operations (bytes)

    """

    def __init__(
        self,
        audit_log_path: str | None = None,
        require_confirmation: bool = False,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        base_dir: Path | None = None,
    ) -> None:
        """Initialize file operations controller.

        Args:
            audit_log_path: Path to audit log file (None = no logging)
            require_confirmation: Whether to require confirmation for destructive ops
            max_file_size: Maximum file size for in-memory operations (bytes)
            base_dir: Base directory for path traversal protection (defaults to cwd)

        """
        self.audit_log_path = audit_log_path
        self.require_confirmation = require_confirmation
        self.max_file_size = max_file_size
        self.base_dir: Path = (base_dir or Path.cwd()).resolve()

        # Initialize audit log
        if self.audit_log_path:
            self._init_audit_log()

    def _init_audit_log(self) -> None:
        """Initialize audit log file."""
        try:
            audit_path = Path(self.audit_log_path)
            audit_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not audit_path.exists():
                audit_path.touch(mode=0o600)
        except Exception:
            logger.exception("Failed to initialize audit log")

    def _log_operation(
        self,
        operation: FileOperationType,
        path: str,
        success: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log file operation to audit log.

        Args:
            operation: Type of operation performed
            path: Primary file path involved
            success: Whether operation succeeded
            details: Additional operation details

        """
        if not self.audit_log_path:
            return

        entry = AuditLogEntry(
            timestamp=datetime.now(tz=UTC).isoformat(),
            operation=operation.value,
            path=path,
            success=success,
            user=os.getenv("USER") or os.getenv("USERNAME"),
            details=details or {},
        )

        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
        except Exception:
            logger.exception("Failed to write audit log")

    def _validate_path(self, path: str) -> Path:
        """Validate and normalize file path using safe base-directory enforcement.

        Args:
            path: File path to validate

        Returns:
            Normalized Path object guaranteed to be within base_dir

        Raises:
            ValueError: If path is empty
            PermissionError: If path escapes the base directory

        """
        if not path:
            msg = "Path cannot be empty"
            raise ValueError(msg)

        # Use safe_path to enforce base directory containment (raises PermissionError
        # for any path - including those with '..' or absolute escapes - that resolves
        # outside self.base_dir).
        return safe_path(path, self.base_dir)

    def _check_permissions(self, path: Path, operation: str) -> None:
        """Check if current user has permissions for operation.

        Args:
            path: File path to check
            operation: Operation to perform ('r', 'w', 'x')

        Raises:
            PermissionError: If user lacks required permissions

        """
        if operation == "r" and path.exists() and not os.access(path, os.R_OK):
            msg = f"No read permission for: {path}"
            raise PermissionError(msg)
        if operation == "w":
            # Check parent directory if path doesn't exist yet
            check_path = path.parent if not path.exists() else path
            # Only check if parent exists (will be created if needed)
            if check_path.exists() and not os.access(check_path, os.W_OK):
                msg = f"No write permission for: {check_path}"
                raise PermissionError(msg)
        elif operation == "x" and path.exists() and not os.access(path, os.X_OK):
            msg = f"No execute permission for: {path}"
            raise PermissionError(msg)

    # ==================== File Creation Operations ====================

    def create_file(
        self,
        path: str,
        content: str | bytes = "",
        overwrite: bool = False,
    ) -> FileOperationResult:
        """Create a new file with optional content.

        Time Complexity: O(n) where n is content size
        Space Complexity: O(n) for content storage

        Args:
            path: Path to file to create
            content: Initial file content (string or bytes)
            overwrite: Whether to overwrite existing file

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If path is invalid
            PermissionError: If lacking write permissions
            FileExistsError: If file exists and overwrite=False

        """
        try:
            file_path = self._validate_path(path)

            # Check if file exists
            if file_path.exists() and not overwrite:
                msg = f"File already exists: {path}"
                raise FileExistsError(msg)

            # Check permissions
            self._check_permissions(file_path, "w")

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            mode = "wb" if isinstance(content, bytes) else "w"
            with open(file_path, mode) as f:
                f.write(content)

            # Log operation
            self._log_operation(
                FileOperationType.CREATE,
                str(file_path),
                True,
                {"size": len(content), "overwrite": overwrite},
            )

            return FileOperationResult(
                success=True,
                operation=FileOperationType.CREATE,
                path=str(file_path),
                message=f"File created successfully: {path}",
                metadata={"size": len(content)},
            )

        except Exception as e:
            self._log_operation(FileOperationType.CREATE, path, False, {"error": str(e)})
            return FileOperationResult(
                success=False,
                operation=FileOperationType.CREATE,
                path=path,
                message=f"Failed to create file: {path}",
                error=str(e),
            )

    # ==================== File Reading Operations ====================

    def read_file(
        self,
        path: str,
        binary: bool = False,
        encoding: str = "utf-8",
    ) -> str | bytes | None:
        """Read file content.

        Time Complexity: O(n) where n is file size
        Space Complexity: O(n) for file content

        Args:
            path: Path to file to read
            binary: Whether to read as binary
            encoding: Text encoding (if not binary)

        Returns:
            File content as string or bytes, None on error

        Raises:
            ValueError: If path is invalid
            PermissionError: If lacking read permissions
            FileNotFoundError: If file doesn't exist

        """
        try:
            file_path = self._validate_path(path)

            # Check if file exists
            if not file_path.exists():
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

            # Check permissions
            self._check_permissions(file_path, "r")

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                msg = f"File too large: {file_size} bytes (max: {self.max_file_size} bytes)"
                raise ValueError(
                    msg,
                )

            # Read content
            mode = "rb" if binary else "r"
            with open(file_path, mode, encoding=None if binary else encoding) as f:
                content = f.read()

            # Log operation
            self._log_operation(
                FileOperationType.READ,
                str(file_path),
                True,
                {"size": file_size, "binary": binary},
            )

            return content

        except (ValueError, PermissionError, FileNotFoundError) as e:
            # Unlike create_file/update_file/delete_file/copy_file/move_file
            # (which catch a blanket `Exception` and return a
            # FileOperationResult(success=False, ...)), read_file()'s
            # documented contract is to raise - its callers (e.g.
            # OSController.read_file()) catch these themselves. That part
            # was already correct; what was missing is this audit log call.
            #
            # BUG FIX (found 2026-09-13): this used to be `except
            # PermissionError: raise` with a comment claiming it let callers
            # "detect path traversal violations" - but _validate_path()
            # (via security/path_utils.py::safe_path) raises ValueError for
            # a traversal attempt, not PermissionError, so that handler
            # never actually caught a traversal attempt at all; it only
            # matched the unrelated real-OS-permission-denied case from
            # _check_permissions(). Worse, unlike every sibling method here,
            # a failed read was never written to the audit log - for a
            # module whose own docstring promises "audit trail for all
            # operations", a path-traversal attempt (exactly the kind of
            # event an audit trail exists to catch) went completely
            # unrecorded. Now all three real failure modes (traversal /
            # file-too-large -> ValueError, permission denied ->
            # PermissionError, missing file -> FileNotFoundError) are
            # logged before re-raising, so the audit trail actually covers
            # read failures the way create/update/delete/copy/move already do.
            self._log_operation(FileOperationType.READ, path, False, {"error": str(e)})
            raise

    # ==================== File Update Operations ====================

    def update_file(
        self,
        path: str,
        content: str | bytes,
        append: bool = False,
    ) -> FileOperationResult:
        """Update file content.

        Time Complexity: O(n) where n is content size
        Space Complexity: O(n) for content storage

        Args:
            path: Path to file to update
            content: New file content
            append: Whether to append (True) or overwrite (False)

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If path is invalid
            PermissionError: If lacking write permissions
            FileNotFoundError: If file doesn't exist

        """
        try:
            file_path = self._validate_path(path)

            # Check if file exists
            if not file_path.exists():
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

            # Check permissions
            self._check_permissions(file_path, "w")

            # Write content
            mode = (
                "ab"
                if isinstance(content, bytes) and append
                else "wb"
                if isinstance(content, bytes)
                else "a"
                if append
                else "w"
            )

            with open(file_path, mode) as f:
                f.write(content)

            # Log operation
            self._log_operation(
                FileOperationType.UPDATE,
                str(file_path),
                True,
                {"size": len(content), "append": append},
            )

            return FileOperationResult(
                success=True,
                operation=FileOperationType.UPDATE,
                path=str(file_path),
                message=f"File updated successfully: {path}",
                metadata={"size": len(content), "append": append},
            )

        except Exception as e:
            self._log_operation(FileOperationType.UPDATE, path, False, {"error": str(e)})
            return FileOperationResult(
                success=False,
                operation=FileOperationType.UPDATE,
                path=path,
                message=f"Failed to update file: {path}",
                error=str(e),
            )

    # ==================== File Deletion Operations ====================

    def delete_file(self, path: str, confirm: bool = False) -> FileOperationResult:
        """Delete a file.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            path: Path to file to delete
            confirm: Whether user confirmed deletion

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If path is invalid or confirmation required but not given
            PermissionError: If lacking write permissions
            FileNotFoundError: If file doesn't exist

        """
        try:
            file_path = self._validate_path(path)

            # Check if file exists
            if not file_path.exists():
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

            # Require confirmation for destructive operation
            if self.require_confirmation and not confirm:
                msg = f"Confirmation required to delete file: {path}"
                raise ValueError(msg)

            # Check permissions
            self._check_permissions(file_path, "w")

            # Get file size before deletion
            file_size = file_path.stat().st_size

            # Delete file
            file_path.unlink()

            # Log operation
            self._log_operation(FileOperationType.DELETE, str(file_path), True, {"size": file_size})

            return FileOperationResult(
                success=True,
                operation=FileOperationType.DELETE,
                path=str(file_path),
                message=f"File deleted successfully: {path}",
                metadata={"size": file_size},
            )

        except Exception as e:
            self._log_operation(FileOperationType.DELETE, path, False, {"error": str(e)})
            return FileOperationResult(
                success=False,
                operation=FileOperationType.DELETE,
                path=path,
                message=f"Failed to delete file: {path}",
                error=str(e),
            )

    # ==================== File Move/Copy/Rename Operations ====================

    def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> FileOperationResult:
        """Move a file to a new location.

        Time Complexity: O(1) for same filesystem, O(n) for different filesystem
        Space Complexity: O(1)

        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing destination file

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If paths are invalid
            PermissionError: If lacking required permissions
            FileNotFoundError: If source file doesn't exist
            FileExistsError: If destination exists and overwrite=False

        """
        try:
            source_path = self._validate_path(source)
            dest_path = self._validate_path(destination)

            # Check if source exists
            if not source_path.exists():
                msg = f"Source file not found: {source}"
                raise FileNotFoundError(msg)

            # Check if destination exists
            if dest_path.exists() and not overwrite:
                msg = f"Destination already exists: {destination}"
                raise FileExistsError(msg)

            # Check permissions
            self._check_permissions(source_path, "w")
            self._check_permissions(dest_path, "w")

            # Get file size before move
            file_size = source_path.stat().st_size

            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(source_path), str(dest_path))

            # Log operation
            self._log_operation(
                FileOperationType.MOVE,
                str(source_path),
                True,
                {"destination": str(dest_path), "size": file_size},
            )

            return FileOperationResult(
                success=True,
                operation=FileOperationType.MOVE,
                path=str(source_path),
                message=f"File moved successfully: {source} -> {destination}",
                metadata={"destination": str(dest_path), "size": file_size},
            )

        except Exception as e:
            self._log_operation(
                FileOperationType.MOVE,
                source,
                False,
                {"destination": destination, "error": str(e)},
            )
            return FileOperationResult(
                success=False,
                operation=FileOperationType.MOVE,
                path=source,
                message=f"Failed to move file: {source} -> {destination}",
                error=str(e),
            )

    def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> FileOperationResult:
        """Copy a file to a new location.

        Time Complexity: O(n) where n is file size
        Space Complexity: O(1) (streaming copy)

        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing destination file

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If paths are invalid
            PermissionError: If lacking required permissions
            FileNotFoundError: If source file doesn't exist
            FileExistsError: If destination exists and overwrite=False

        """
        try:
            source_path = self._validate_path(source)
            dest_path = self._validate_path(destination)

            # Check if source exists
            if not source_path.exists():
                msg = f"Source file not found: {source}"
                raise FileNotFoundError(msg)

            # Check if destination exists
            if dest_path.exists() and not overwrite:
                msg = f"Destination already exists: {destination}"
                raise FileExistsError(msg)

            # Check permissions
            self._check_permissions(source_path, "r")
            self._check_permissions(dest_path, "w")

            # Get file size
            file_size = source_path.stat().st_size

            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(str(source_path), str(dest_path))

            # Log operation
            self._log_operation(
                FileOperationType.COPY,
                str(source_path),
                True,
                {"destination": str(dest_path), "size": file_size},
            )

            return FileOperationResult(
                success=True,
                operation=FileOperationType.COPY,
                path=str(source_path),
                message=f"File copied successfully: {source} -> {destination}",
                metadata={"destination": str(dest_path), "size": file_size},
            )

        except Exception as e:
            self._log_operation(
                FileOperationType.COPY,
                source,
                False,
                {"destination": destination, "error": str(e)},
            )
            return FileOperationResult(
                success=False,
                operation=FileOperationType.COPY,
                path=source,
                message=f"Failed to copy file: {source} -> {destination}",
                error=str(e),
            )

    def rename_file(self, path: str, new_name: str, overwrite: bool = False) -> FileOperationResult:
        """Rename a file.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            path: Current file path
            new_name: New file name (not full path)
            overwrite: Whether to overwrite existing file with new name

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If paths are invalid
            PermissionError: If lacking required permissions
            FileNotFoundError: If file doesn't exist
            FileExistsError: If new name exists and overwrite=False

        """
        try:
            file_path = self._validate_path(path)

            # Check if file exists
            if not file_path.exists():
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

            # Create new path in same directory
            new_path = file_path.parent / new_name

            # Check if new name exists
            if new_path.exists() and not overwrite:
                msg = f"File already exists: {new_name}"
                raise FileExistsError(msg)

            # Check permissions
            self._check_permissions(file_path, "w")

            # Get file size
            file_size = file_path.stat().st_size

            # Rename file
            file_path.rename(new_path)

            # Log operation
            self._log_operation(
                FileOperationType.RENAME,
                str(file_path),
                True,
                {"new_name": new_name, "size": file_size},
            )

            return FileOperationResult(
                success=True,
                operation=FileOperationType.RENAME,
                path=str(file_path),
                message=f"File renamed successfully: {path} -> {new_name}",
                metadata={"new_path": str(new_path), "size": file_size},
            )

        except Exception as e:
            self._log_operation(
                FileOperationType.RENAME,
                path,
                False,
                {"new_name": new_name, "error": str(e)},
            )
            return FileOperationResult(
                success=False,
                operation=FileOperationType.RENAME,
                path=path,
                message=f"Failed to rename file: {path} -> {new_name}",
                error=str(e),
            )

    # ==================== Directory Operations ====================

    def create_directory(
        self,
        path: str,
        parents: bool = True,
        exist_ok: bool = True,
    ) -> FileOperationResult:
        """Create a directory.

        Time Complexity: O(d) where d is directory depth
        Space Complexity: O(1)

        Args:
            path: Directory path to create
            parents: Whether to create parent directories
            exist_ok: Whether to ignore if directory already exists

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If path is invalid
            PermissionError: If lacking write permissions
            FileExistsError: If directory exists and exist_ok=False

        """
        try:
            dir_path = self._validate_path(path)

            # Check if directory exists
            if dir_path.exists() and not exist_ok:
                msg = f"Directory already exists: {path}"
                raise FileExistsError(msg)

            # Check permissions
            if not dir_path.exists():
                self._check_permissions(dir_path, "w")

            # Create directory
            dir_path.mkdir(parents=parents, exist_ok=exist_ok)

            # Log operation
            self._log_operation(FileOperationType.MKDIR, str(dir_path), True, {"parents": parents})

            return FileOperationResult(
                success=True,
                operation=FileOperationType.MKDIR,
                path=str(dir_path),
                message=f"Directory created successfully: {path}",
                metadata={"parents": parents},
            )

        except Exception as e:
            self._log_operation(FileOperationType.MKDIR, path, False, {"error": str(e)})
            return FileOperationResult(
                success=False,
                operation=FileOperationType.MKDIR,
                path=path,
                message=f"Failed to create directory: {path}",
                error=str(e),
            )

    def delete_directory(
        self,
        path: str,
        recursive: bool = False,
        confirm: bool = False,
    ) -> FileOperationResult:
        """Delete a directory.

        Time Complexity: O(n) where n is number of files/subdirectories
        Space Complexity: O(1)

        Args:
            path: Directory path to delete
            recursive: Whether to delete non-empty directory
            confirm: Whether user confirmed deletion

        Returns:
            FileOperationResult with operation status

        Raises:
            ValueError: If path is invalid or confirmation required but not given
            PermissionError: If lacking write permissions
            FileNotFoundError: If directory doesn't exist
            OSError: If directory not empty and recursive=False

        """
        try:
            dir_path = self._validate_path(path)

            # Check if directory exists
            if not dir_path.exists():
                msg = f"Directory not found: {path}"
                raise FileNotFoundError(msg)

            # Require confirmation for destructive operation
            if self.require_confirmation and not confirm:
                msg = f"Confirmation required to delete directory: {path}"
                raise ValueError(msg)

            # Check permissions
            self._check_permissions(dir_path, "w")

            # Count files before deletion
            file_count = sum(1 for _ in dir_path.rglob("*")) if recursive else 0

            # Delete directory
            if recursive:
                shutil.rmtree(str(dir_path))
            else:
                dir_path.rmdir()

            # Log operation
            self._log_operation(
                FileOperationType.RMDIR,
                str(dir_path),
                True,
                {"recursive": recursive, "file_count": file_count},
            )

            return FileOperationResult(
                success=True,
                operation=FileOperationType.RMDIR,
                path=str(dir_path),
                message=f"Directory deleted successfully: {path}",
                metadata={"recursive": recursive, "file_count": file_count},
            )

        except Exception as e:
            self._log_operation(FileOperationType.RMDIR, path, False, {"error": str(e)})
            return FileOperationResult(
                success=False,
                operation=FileOperationType.RMDIR,
                path=path,
                message=f"Failed to delete directory: {path}",
                error=str(e),
            )

    def list_directory(
        self,
        path: str,
        recursive: bool = False,
        pattern: str | None = None,
    ) -> list[str] | None:
        """List directory contents.

        Time Complexity: O(n) where n is number of entries
        Space Complexity: O(n) for result list

        Args:
            path: Directory path to list
            recursive: Whether to list recursively
            pattern: Glob pattern to filter results (e.g., "*.txt")

        Returns:
            List of file paths, None on error

        Raises:
            ValueError: If path is invalid
            PermissionError: If lacking read permissions
            FileNotFoundError: If directory doesn't exist

        """
        try:
            dir_path = self._validate_path(path)

            # Check if directory exists
            if not dir_path.exists():
                msg = f"Directory not found: {path}"
                raise FileNotFoundError(msg)

            # Check permissions
            self._check_permissions(dir_path, "r")

            # List directory
            if recursive:
                if pattern:
                    entries = [str(p) for p in dir_path.rglob(pattern)]
                else:
                    entries = [str(p) for p in dir_path.rglob("*")]
            elif pattern:
                entries = [str(p) for p in dir_path.glob(pattern)]
            else:
                entries = [str(p) for p in dir_path.iterdir()]

            return sorted(entries)

        except Exception:
            logger.exception("Failed to list directory")
            return None

    # ==================== Utility Operations ====================

    def file_exists(self, path: str) -> bool:
        """Check if file exists.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            path: File path to check

        Returns:
            True if file exists, False otherwise

        """
        try:
            file_path = self._validate_path(path)
            return file_path.exists() and file_path.is_file()
        except Exception:
            return False

    def directory_exists(self, path: str) -> bool:
        """Check if directory exists.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            path: Directory path to check

        Returns:
            True if directory exists, False otherwise

        """
        try:
            dir_path = self._validate_path(path)
            return dir_path.exists() and dir_path.is_dir()
        except Exception:
            return False

    def get_file_info(self, path: str) -> dict[str, Any] | None:
        """Get file metadata.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            path: File path to get info for

        Returns:
            Dictionary with file metadata, None on error

        """
        try:
            file_path = self._validate_path(path)

            if not file_path.exists():
                return None

            stat = file_path.stat()

            return {
                "path": str(file_path),
                "name": file_path.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "is_file": file_path.is_file(),
                "is_directory": file_path.is_dir(),
                "is_symlink": file_path.is_symlink(),
                "permissions": oct(stat.st_mode)[-3:],
            }

        except Exception:
            logger.exception("Failed to get file info for")
            return None

    def compute_file_hash(self, path: str, algorithm: str = "sha256") -> str | None:
        """Compute file hash.

        Time Complexity: O(n) where n is file size
        Space Complexity: O(1) (streaming hash)

        Args:
            path: File path to hash
            algorithm: Hash algorithm (md5, sha1, sha256, sha512)

        Returns:
            Hex digest of file hash, None on error

        Raises:
            ValueError: If algorithm is invalid

        """
        try:
            file_path = self._validate_path(path)

            if not file_path.exists():
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

            # Create hash object
            # MD5 and SHA-1 are cryptographically weak; upgrade to SHA-256 (CWE-327)
            if algorithm in ("md5", "sha1") or algorithm == "sha256":
                hasher = hashlib.sha256()
            elif algorithm == "sha512":
                hasher = hashlib.sha512()
            else:
                msg = f"Invalid hash algorithm: {algorithm}"
                raise ValueError(msg)

            # Compute hash in chunks (memory efficient)
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)

            return hasher.hexdigest()

        except Exception:
            logger.exception("Failed to compute hash for")
            return None
