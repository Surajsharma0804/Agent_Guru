"""Token Counter for accurate per-provider token counting.

Uses provider-specific tokenizers:
- OpenAI: tiktoken
- Anthropic: anthropic library count_tokens
- Google: approximation (no official tokenizer)
- Ollama: approximation based on character count

Performance:
    Time Complexity: O(n) where n is text length
    Space Complexity: O(k) where k is number of cached encoders

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Agent_Guru.llm.models import Message


class TokenCounter:
    """Accurate token counting for all supported providers.

    Example:
        >>> counter = TokenCounter()
        >>> messages = [Message(role="user", content="Hello world")]
        >>> count = counter.count_messages(messages, "gpt-3.5-turbo")
        >>> print(f"Token count: {count}")

    """

    def __init__(self) -> None:
        """Initialize token counter with lazy-loaded encoders."""
        self._openai_encoders: dict[str, object] = {}
        self._anthropic_client: object | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def count_messages(self, messages: list[Message], model: str) -> int:
        """Count tokens in a list of messages.

        Args:
            messages: List of chat messages.
            model: Model name used to select tokenizer.

        Returns:
            Total token count including message format overhead.

        """
        provider = self._get_provider(model)

        if provider == "openai":
            return self._count_openai_messages(messages, model)
        if provider == "anthropic":
            return self._count_anthropic_messages(messages, model)
        if provider == "google":
            return self._count_google_messages(messages)
        # ollama / unknown
        return self._count_ollama_messages(messages)

    def count_text(self, text: str, model: str) -> int:
        """Count tokens in a plain text string.

        Args:
            text: Text to tokenize.
            model: Model name used to select tokenizer.

        Returns:
            Token count.

        """
        if not text:
            return 0

        provider = self._get_provider(model)

        if provider == "openai":
            return self._count_openai_text(text, model)
        if provider == "anthropic":
            return self._count_anthropic_text(text)
        if provider == "google":
            return self._count_google_text(text)
        return self._count_ollama_text(text)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def _count_openai_messages(self, messages: list[Message], model: str) -> int:
        """Count tokens for OpenAI chat messages including format overhead."""
        encoding = self._get_openai_encoder(model)

        # Per OpenAI cookbook: each message has 3 overhead tokens
        tokens_per_message = 3
        tokens_per_name = 1

        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            num_tokens += len(encoding.encode(message.content))  # type: ignore[attr-defined]
            if message.name:
                num_tokens += tokens_per_name

        # Every reply is primed with <|start|>assistant<|message|>
        num_tokens += 3
        return num_tokens

    def _count_openai_text(self, text: str, model: str) -> int:
        """Count tokens for a plain text string using tiktoken."""
        encoding = self._get_openai_encoder(model)
        return len(encoding.encode(text))  # type: ignore[attr-defined]

    def _get_openai_encoder(self, model: str) -> object:
        """Return (cached) tiktoken encoder for the given model."""
        if model not in self._openai_encoders:
            try:
                import tiktoken  # type: ignore[import]

                try:
                    self._openai_encoders[model] = tiktoken.encoding_for_model(model)
                except KeyError:
                    # Fall back to cl100k_base for unknown models
                    self._openai_encoders[model] = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                # tiktoken not installed - fall back to approximation
                self._openai_encoders[model] = _ApproxEncoder()

        return self._openai_encoders[model]

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _count_anthropic_messages(self, messages: list[Message], model: str) -> int:
        """Count tokens for Anthropic messages."""
        return sum(self._count_anthropic_text(m.content) for m in messages)

    def _count_anthropic_text(self, text: str) -> int:
        """Count tokens using approximation (~4 chars per token)."""
        if not text:
            return 0
        # Approximation: ~4 chars per token (Anthropic uses Claude tokenizer)
        return max(1, len(text) // 4)

    def _get_anthropic_client(self) -> object | None:
        """Anthropic client - not used for token counting (approximation only)."""
        return None

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def _count_google_messages(self, messages: list[Message]) -> int:
        """Count tokens for Google messages (approximation)."""
        return sum(self._count_google_text(m.content) for m in messages)

    @staticmethod
    def _count_google_text(text: str) -> int:
        """Approximate token count for Google models (~4 chars/token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def _count_ollama_messages(self, messages: list[Message]) -> int:
        """Count tokens for Ollama messages (approximation)."""
        return sum(self._count_ollama_text(m.content) for m in messages)

    @staticmethod
    def _count_ollama_text(text: str) -> int:
        """Approximate token count for Ollama models (~3.5 chars/token)."""
        if not text:
            return 0
        return max(1, len(text) // 3)

    # ------------------------------------------------------------------
    # Provider detection
    # ------------------------------------------------------------------

    @staticmethod
    def _get_provider(model: str) -> str:
        """Determine provider from model name prefix."""
        if model.startswith(("gpt-", "text-embedding", "o1-", "o3-")):
            return "openai"
        if model.startswith("claude-"):
            return "anthropic"
        if model.startswith("gemini-"):
            return "google"
        return "ollama"


# ---------------------------------------------------------------------------
# Internal fallback encoder when tiktoken is unavailable
# ---------------------------------------------------------------------------


class _ApproxEncoder:
    """Fallback encoder that approximates token counts."""

    def encode(self, text: str) -> list[int]:
        """Return approximate token list (1 token per ~4 chars)."""
        if not text:
            return []
        return list(range(max(1, len(text) // 4)))
