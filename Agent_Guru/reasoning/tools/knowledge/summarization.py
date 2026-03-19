"""
Summarization tools for text, articles, and documents.

Uses LLM for intelligent summarization.
"""

from typing import Any, Dict

from Agent_Guru.reasoning.tools.base import (
    Tool,
    ToolParameter,
    ToolParameterType,
    ToolSensitivity,
)
from Agent_Guru.reasoning.tools.registry import tool


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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
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

            if word_count <= max_length:
                summary = text
            else:
                summary = " ".join(words[:max_length]) + "..."

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
                "error": f"Failed to summarize text: {str(e)}",
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
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
            # Note: In a real implementation, this would:
            # 1. Fetch the article content
            # 2. Extract main text
            # 3. Use LLM for summarization
            return {
                "success": True,
                "result": {
                    "url": url,
                    "max_length": max_length,
                    "summary": "Article summary would appear here",
                    "message": f"Article from {url} would be summarized",
                    "note": "This is a placeholder. Real implementation would fetch and summarize article content.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to summarize article: {str(e)}",
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

    async def execute(self, **kwargs: Any) -> Dict[str, Any]:
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
            # Note: In a real implementation, this would:
            # 1. Read the document (PDF, DOCX, TXT, etc.)
            # 2. Extract text content
            # 3. Use LLM for summarization
            return {
                "success": True,
                "result": {
                    "file_path": file_path,
                    "max_length": max_length,
                    "summary": "Document summary would appear here",
                    "message": f"Document {file_path} would be summarized",
                    "note": "This is a placeholder. Real implementation would read and summarize document content.",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to summarize document: {str(e)}",
            }
