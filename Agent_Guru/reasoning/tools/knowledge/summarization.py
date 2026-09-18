"""Summarization tools for text, articles, and documents.

DOC FIX (Round 21): this previously claimed "Uses LLM for intelligent
summarization" -- none of the tools in this module do; SummarizeTextTool
and SummarizeDocumentTool perform honest word-count truncation (real
content, extractive, not LLM-generated), and SummarizeArticleTool honestly
reports that arbitrary-URL fetching isn't implemented yet rather than
fabricating a summary. See this module's per-tool fix notes and the
Round 21 audit report for details.
"""

import asyncio
from pathlib import Path
from typing import Any

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool

# Maximum document size for summarization (5MB) -- smaller than
# file_operations.py's 10MB read cap since this also has to hold the
# word-split copy in memory.
MAX_DOCUMENT_SIZE_BYTES = 5 * 1024 * 1024


@tool(
    tool_id="summarize.text",
    name="Summarize Text",
    description="Summarize a piece of text",
    parameters=[
        ToolParameter(
            name="text",
            type=ToolParameterType.STRING,
            description="Text to summarize",
            required=True,
        ),
        ToolParameter(
            name="max_length",
            type=ToolParameterType.INTEGER,
            description="Maximum summary length in words (default: 100)",
            required=False,
            default=100,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=1500,
    capabilities=["summarization", "text_processing", "summarize"],
    examples=[
        "Summarize this article",
        "Give me a summary of this text",
        "Condense this paragraph",
    ],
)
class SummarizeTextTool(Tool):
    """Tool for summarizing text."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute text summarization.

        Args:
            text: Text to summarize
            max_length: Maximum summary length

        Returns:
            Execution result with summary

        """
        text = kwargs["text"]
        max_length = kwargs.get("max_length", 100)

        # Validate text
        if not text or not text.strip():
            return {
                "success": False,
                "error": "Text cannot be empty",
            }

        # Validate max_length
        if max_length <= 0 or max_length > 1000:
            return {
                "success": False,
                "error": "max_length must be between 1 and 1000",
            }

        try:
            # Note: In a real implementation, this would use an LLM for summarization
            # For now, we return a simple truncation
            words = text.split()
            word_count = len(words)

            summary = text if word_count <= max_length else " ".join(words[:max_length]) + "..."

            return {
                "success": True,
                "result": {
                    "original_length": word_count,
                    "summary_length": min(word_count, max_length),
                    "summary": summary,
                    "compression_ratio": min(word_count, max_length) / word_count,
                    "message": f"Summarized {word_count} words to {min(word_count, max_length)} words",
                    "note": "This is a placeholder. Real implementation would use LLM for intelligent summarization.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to summarize text: {e!s}",
            }


@tool(
    tool_id="summarize.article",
    name="Summarize Article",
    description="Summarize an article from a URL",
    parameters=[
        ToolParameter(
            name="url",
            type=ToolParameterType.STRING,
            description="Article URL",
            required=True,
        ),
        ToolParameter(
            name="max_length",
            type=ToolParameterType.INTEGER,
            description="Maximum summary length in words (default: 150)",
            required=False,
            default=150,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=2000,
    capabilities=["summarization", "article_processing", "web_content"],
    examples=[
        "Summarize this article",
        "Give me a summary of this news article",
        "What's this article about",
    ],
)
class SummarizeArticleTool(Tool):
    """Tool for summarizing articles."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute article summarization.

        Args:
            url: Article URL
            max_length: Maximum summary length

        Returns:
            Execution result with summary

        """
        url = kwargs["url"]
        max_length = kwargs.get("max_length", 150)

        # Validate URL
        if not url or not url.strip():
            return {
                "success": False,
                "error": "URL cannot be empty",
            }

        # Validate max_length
        if max_length <= 0 or max_length > 1000:
            return {
                "success": False,
                "error": "max_length must be between 1 and 1000",
            }

        try:
            # BUG FIX (Round 21): this used to claim success with a literal
            # placeholder string ("Article summary would appear here") --
            # the article at `url` was never fetched at all. Left as an
            # honest failure rather than fabricated content: unlike
            # web_search.py/information.py's fixes (this same round), there
            # is no already-built, already-tested "fetch this specific
            # arbitrary URL's content" capability in this codebase to
            # delegate to yet -- platform/browser_manager.py can navigate to
            # a URL and extract page text (used by web_search.py's tier-3
            # search fallback), but wiring an LLM-agent-facing tool to
            # navigate to an arbitrary, user/LLM-supplied URL is a distinct
            # capability with its own safety surface (the shared browser
            # instance is also used for other live features like YouTube
            # playback, so a long-running fetch here could interfere with
            # those; and unlike a search query, an arbitrary URL needs its
            # own scrutiny e.g. against local-network/internal-address
            # targets) that deserves a dedicated audit rather than being
            # folded into this fix. See this round's report for the
            # specific follow-up recommendation.
            return {
                "success": False,
                "error": (
                    "Article summarization is not available: this build has "
                    "no capability to fetch arbitrary article URLs yet. "
                    "Provide the article text directly and use "
                    "'summarize.text' instead."
                ),
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to summarize article: {e!s}",
            }


@tool(
    tool_id="summarize.document",
    name="Summarize Document",
    description="Summarize a document file",
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="Path to document file",
            required=True,
        ),
        ToolParameter(
            name="max_length",
            type=ToolParameterType.INTEGER,
            description="Maximum summary length in words (default: 200)",
            required=False,
            default=200,
        ),
    ],
    sensitivity=ToolSensitivity.SAFE,
    estimated_latency_ms=2500,
    capabilities=["summarization", "document_processing", "file_processing"],
    examples=[
        "Summarize this PDF",
        "Give me a summary of this document",
        "What's in this file",
    ],
)
class SummarizeDocumentTool(Tool):
    """Tool for summarizing documents."""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute document summarization.

        Args:
            file_path: Path to document
            max_length: Maximum summary length

        Returns:
            Execution result with summary

        """
        file_path = kwargs["file_path"]
        max_length = kwargs.get("max_length", 200)

        # Validate file_path
        if not file_path or not file_path.strip():
            return {
                "success": False,
                "error": "File path cannot be empty",
            }

        # Validate max_length
        if max_length <= 0 or max_length > 1000:
            return {
                "success": False,
                "error": "max_length must be between 1 and 1000",
            }

        try:
            # BUG FIX (Round 21): this used to claim success with a literal
            # placeholder string ("Document summary would appear here") --
            # the file was never opened. Unlike SummarizeArticleTool (see
            # that method's fix note), a real, already-audited building
            # block for this DOES exist: the same safe_path()-sandboxed
            # file read pattern already applied to
            # reasoning/tools/system/file_operations.py::FileReadTool
            # (Round 8) -- containment-checked to the user's home directory,
            # raising ValueError on any traversal attempt. Only plain-text
            # formats are handled here (.txt/.md/.markdown/.rst/.log, or no
            # extension); PDF/DOCX would need a real parser this codebase
            # doesn't have wired up yet, so those are honestly rejected
            # rather than read as garbled binary and "summarized" into
            # nonsense.
            from Agent_Guru.security.path_utils import safe_path

            _base_dir = Path.home().resolve()
            try:
                resolved_path = safe_path(file_path, _base_dir)
            except ValueError as e:
                return {"success": False, "error": str(e)}

            if not resolved_path.exists() or not resolved_path.is_file():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                }

            _TEXT_SUFFIXES = {"", ".txt", ".md", ".markdown", ".rst", ".log"}
            if resolved_path.suffix.lower() not in _TEXT_SUFFIXES:
                return {
                    "success": False,
                    "error": (
                        f"Cannot summarize '{resolved_path.suffix}' files yet -- "
                        "only plain text documents (.txt, .md, .rst, .log) are "
                        "supported. PDF/DOCX extraction is not implemented."
                    ),
                }

            file_size = resolved_path.stat().st_size
            if file_size > MAX_DOCUMENT_SIZE_BYTES:
                return {
                    "success": False,
                    "error": (
                        f"File too large to summarize: {file_size} bytes "
                        f"(max: {MAX_DOCUMENT_SIZE_BYTES})"
                    ),
                }

            content = await asyncio.to_thread(resolved_path.read_text, encoding="utf-8")

            # Same honest extractive approach as SummarizeTextTool above
            # (word-count truncation, not LLM-generated) -- real content,
            # real truncation, clearly not claimed to be more than that.
            words = content.split()
            word_count = len(words)
            summary = content if word_count <= max_length else " ".join(words[:max_length]) + "..."

            return {
                "success": True,
                "result": {
                    "file_path": str(resolved_path),
                    "max_length": max_length,
                    "original_length": word_count,
                    "summary_length": min(word_count, max_length),
                    "summary": summary,
                    "message": f"Summarized {resolved_path.name} ({word_count} words)",
                },
            }

        except UnicodeDecodeError:
            return {
                "success": False,
                "error": "Failed to decode file as UTF-8 text",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to summarize document: {e!s}",
            }
