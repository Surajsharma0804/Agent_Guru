"""File operation tools for reading, writing, deleting, moving, and copying files.

Implements safe file operations with validation and error handling.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool

# Maximum file size for read operations (10MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


@tool(
    tool_id="file.read",
    name="Read File",
    description="Read contents of a file",
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="Path to the file to read",
            required=True,
        ),
        ToolParameter(
            name="encoding",
            type=ToolParameterType.STRING,
            description="File encoding (default: utf-8)",
            required=False,
            default="utf-8",
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=100,
    capabilities=["file_operations", "file_read", "read_file"],
    examples=[
        "Read the file config.txt",
        "Show me the contents of notes.md",
        "Read document.pdf",
    ],
)
class FileReadTool(Tool):
    """Tool for reading files."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute file reading.

        Args:
            file_path: Path to file
            encoding: File encoding

        Returns:
            Execution result with file contents

        """
        file_path = kwargs["file_path"]
        encoding = kwargs.get("encoding", "utf-8")

        try:
            path = Path(file_path).resolve()

            # Validate file exists
            if not path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                }

            # Validate it's a file
            if not path.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {file_path}",
                }

            # Check file size
            file_size = path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                return {
                    "success": False,
                    "error": f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE_BYTES})",
                }

            # Read file
            content = await asyncio.to_thread(path.read_text, encoding=encoding)

            return {
                "success": True,
                "result": {
                    "file_path": str(path),
                    "content": content,
                    "size_bytes": file_size,
                    "encoding": encoding,
                    "message": f"Read {file_size} bytes from {path.name}",
                },
            }

        except UnicodeDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to decode file with encoding {encoding}",
            }
            return {
                "success": False,
                "error": f"Failed to read file: {e!s}",
            }
@tool(
    tool_id="file.write",
    name="Write File",
    description="Write content to a file",
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="Path to the file to write",
            required=True,
        ),
        ToolParameter(
            name="content",
            type=ToolParameterType.STRING,
            description="Content to write to the file",
            required=True,
        ),
        ToolParameter(
            name="encoding",
            type=ToolParameterType.STRING,
            description="File encoding (default: utf-8)",
            required=False,
            default="utf-8",
        ),
        ToolParameter(
            name="append",
            type=ToolParameterType.BOOLEAN,
            description="Append to file instead of overwriting (default: false)",
            required=False,
            default=False,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=100,
    capabilities=["file_operations", "file_write", "write_file", "create_file"],
    examples=[
        "Write 'Hello World' to notes.txt",
        "Create a file called todo.md with my tasks",
        "Append text to log.txt",
    ],
)
class FileWriteTool(Tool):
    """Tool for writing files."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute file writing.

        Args:
            file_path: Path to file
            content: Content to write
            encoding: File encoding
            append: Whether to append

        Returns:
            Execution result

        """
        file_path = kwargs["file_path"]
        content = kwargs["content"]
        encoding = kwargs.get("encoding", "utf-8")
        append = kwargs.get("append", False)

        try:
            path = Path(file_path).resolve()

            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            if append:
                await asyncio.to_thread(lambda: path.open("a", encoding=encoding).write(content))
                mode = "appended to"
            else:
                await asyncio.to_thread(path.write_text, content, encoding=encoding)
                mode = "written to"

            size_bytes = path.stat().st_size

            return {
                "success": True,
                "result": {
                    "file_path": str(path),
                    "size_bytes": size_bytes,
                    "encoding": encoding,
                    "append": append,
                    "message": f"Content {mode} {path.name} ({size_bytes} bytes)",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write file: {e!s}",
            }
@tool(
    tool_id="file.delete",
    name="Delete File",
    description="Delete a file",
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="Path to the file to delete",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.DANGEROUS,
    estimated_latency_ms=50,
    capabilities=["file_operations", "file_delete", "delete_file", "remove_file"],
    examples=[
        "Delete the file temp.txt",
        "Remove old_notes.md",
        "Delete backup.zip",
    ],
)
class FileDeleteTool(Tool):
    """Tool for deleting files."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute file deletion.

        Args:
            file_path: Path to file

        Returns:
            Execution result

        """
        file_path = kwargs["file_path"]

        try:
            path = Path(file_path).resolve()

            # Validate file exists
            if not path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                }

            # Validate it's a file
            if not path.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {file_path}",
                }

            # Delete file
            await asyncio.to_thread(path.unlink)

            return {
                "success": True,
                "result": {
                    "file_path": str(path),
                    "message": f"Deleted {path.name}",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete file: {e!s}",
            }
@tool(
    tool_id="file.move",
    name="Move File",
    description="Move or rename a file",
    parameters=[
        ToolParameter(
            name="source_path",
            type=ToolParameterType.STRING,
            description="Source file path",
            required=True,
        ),
        ToolParameter(
            name="destination_path",
            type=ToolParameterType.STRING,
            description="Destination file path",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SENSITIVE,
    estimated_latency_ms=100,
    capabilities=["file_operations", "file_move", "move_file", "rename_file"],
    examples=[
        "Move notes.txt to Documents folder",
        "Rename old.txt to new.txt",
        "Move file to backup directory",
    ],
)
class FileMoveTool(Tool):
    """Tool for moving/renaming files."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute file moving.

        Args:
            source_path: Source file path
            destination_path: Destination file path

        Returns:
            Execution result

        """
        source_path = kwargs["source_path"]
        destination_path = kwargs["destination_path"]

        try:
            source = Path(source_path).resolve()
            destination = Path(destination_path).resolve()

            # Validate source exists
            if not source.exists():
                return {
                    "success": False,
                    "error": f"Source file not found: {source_path}",
                }

            # Validate source is a file
            if not source.is_file():
                return {
                    "success": False,
                    "error": f"Source path is not a file: {source_path}",
                }

            # Create destination parent directories if needed
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            await asyncio.to_thread(shutil.move, str(source), str(destination))

            return {
                "success": True,
                "result": {
                    "source_path": str(source),
                    "destination_path": str(destination),
                    "message": f"Moved {source.name} to {destination}",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to move file: {e!s}",
            }
@tool(
    tool_id="file.copy",
    name="Copy File",
    description="Copy a file to a new location",
    parameters=[
        ToolParameter(
            name="source_path",
            type=ToolParameterType.STRING,
            description="Source file path",
            required=True,
        ),
        ToolParameter(
            name="destination_path",
            type=ToolParameterType.STRING,
            description="Destination file path",
            required=True,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=200,
    capabilities=["file_operations", "file_copy", "copy_file", "duplicate_file"],
    examples=[
        "Copy notes.txt to backup folder",
        "Duplicate config.json",
        "Copy file to Documents",
    ],
)
class FileCopyTool(Tool):
    """Tool for copying files."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Execute file copying.

        Args:
            source_path: Source file path
            destination_path: Destination file path

        Returns:
            Execution result

        """
        source_path = kwargs["source_path"]
        destination_path = kwargs["destination_path"]

        try:
            source = Path(source_path).resolve()
            destination = Path(destination_path).resolve()

            # Validate source exists
            if not source.exists():
                return {
                    "success": False,
                    "error": f"Source file not found: {source_path}",
                }

            # Validate source is a file
            if not source.is_file():
                return {
                    "success": False,
                    "error": f"Source path is not a file: {source_path}",
                }

            # Create destination parent directories if needed
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            await asyncio.to_thread(shutil.copy2, str(source), str(destination))

            size_bytes = destination.stat().st_size

            return {
                "success": True,
                "result": {
                    "source_path": str(source),
                    "destination_path": str(destination),
                    "size_bytes": size_bytes,
                    "message": f"Copied {source.name} to {destination} ({size_bytes} bytes)",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to copy file: {e!s}",
            }
