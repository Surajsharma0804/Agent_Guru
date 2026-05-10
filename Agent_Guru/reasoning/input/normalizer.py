"""Input Normalizer for Reasoning Engine.

This module implements input normalization for text, voice, and system event inputs.
It standardizes inputs from different sources into a common format with metadata extraction,
validation, and sanitization for security.

Performance Characteristics:
    - Time Complexity: O(n) where n is input length
    - Space Complexity: O(n) for normalized output
    - Latency: <30ms (95th percentile)

Design Principles:
    - Fast validation and normalization
    - Comprehensive metadata extraction
    - Security-first input sanitization
    - Descriptive error messages
    - Type-safe with Pydantic models

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class InputSource(str, Enum):
    """Enumeration of input sources.

    Sources:
        TEXT: Direct text input from user
        VOICE: Transcribed voice input
        SYSTEM_EVENT: System-generated event
    """

    TEXT = "text"
    VOICE = "voice"
    SYSTEM_EVENT = "system_event"


class RawInput(BaseModel):
    """Raw input from various sources.

    Attributes:
        content: Raw input content (text, bytes, or dict)
        source: Input source type
        user_id: User identifier
        timestamp: Input timestamp
        metadata: Additional metadata

    """

    content: Any = Field(..., description="Raw input content")
    source: InputSource = Field(..., description="Input source type")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="Input timestamp",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user ID is not empty."""
        if not v or not v.strip():
            msg = "User ID cannot be empty"
            raise ValueError(msg)
        return v.strip()


class NormalizedInput(BaseModel):
    """Normalized input with extracted metadata.

    Attributes:
        text: Normalized text content
        source: Input source type
        user_id: User identifier
        timestamp: Input timestamp
        metadata: Extracted and preserved metadata
        original_content: Original raw content (for debugging)

    """

    text: str = Field(..., description="Normalized text content")
    source: InputSource = Field(..., description="Input source type")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(..., description="Input timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extracted metadata")
    original_content: str | None = Field(default=None, description="Original raw content")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Validate text is not empty."""
        if not v or not v.strip():
            msg = "Normalized text cannot be empty"
            raise ValueError(msg)
        return v

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user ID is not empty."""
        if not v or not v.strip():
            msg = "User ID cannot be empty"
            raise ValueError(msg)
        return v


class InputNormalizer:
    """Input normalizer for reasoning engine.

    This class normalizes inputs from different sources (text, voice, system events)
    into a standardized format with metadata extraction and security sanitization.

    Time Complexity:
        - normalize: O(n) where n is input length
        - Latency: <30ms (95th percentile)

    Space Complexity:
        - O(n) for normalized output

    Features:
        - Text normalization (whitespace, encoding)
        - Voice input handling (already transcribed)
        - System event conversion to natural language
        - Metadata extraction and preservation
        - Input validation with descriptive errors
        - Security sanitization (XSS, injection prevention)

    Example:
        >>> normalizer = InputNormalizer()
        >>> raw = RawInput(
        ...     content="  Set a timer for 5 minutes  ",
        ...     source=InputSource.TEXT,
        ...     user_id="user_123"
        ... )
        >>> normalized = normalizer.normalize(raw)
        >>> print(normalized.text)
        "Set a timer for 5 minutes"

    """

    # Maximum input length (10KB)
    MAX_INPUT_LENGTH = 10 * 1024

    # Dangerous patterns for sanitization
    DANGEROUS_PATTERNS = [
        r"<script[^>]*>.*?</script>",  # Script tags
        r"javascript:",  # JavaScript protocol
        r"on\w+\s*=",  # Event handlers
        r"<iframe[^>]*>",  # Iframes
    ]

    def __init__(self, max_length: int = MAX_INPUT_LENGTH) -> None:
        """Initialize InputNormalizer.

        Args:
            max_length: Maximum input length in characters

        """
        self.max_length = max_length
        self._dangerous_pattern = re.compile(
            "|".join(self.DANGEROUS_PATTERNS),
            re.IGNORECASE | re.DOTALL,
        )

    def normalize(self, raw_input: RawInput) -> NormalizedInput:
        """Normalize raw input into standardized format.

        Time Complexity: O(n) where n is input length
        Latency Budget: <30ms

        This is the main entry point for input normalization. It handles different
        input sources and applies appropriate normalization strategies.

        Args:
            raw_input: Raw input from user or system

        Returns:
            NormalizedInput with standardized format

        Raises:
            ValueError: If input is invalid or exceeds size limits

        Example:
            >>> normalizer = InputNormalizer()
            >>> raw = RawInput(content="hello", source=InputSource.TEXT, user_id="user_123")
            >>> normalized = normalizer.normalize(raw)

        """
        # Route to appropriate normalization method based on source
        if raw_input.source == InputSource.TEXT:
            return self._normalize_text(raw_input)
        if raw_input.source == InputSource.VOICE:
            return self._normalize_voice(raw_input)
        if raw_input.source == InputSource.SYSTEM_EVENT:
            return self._normalize_system_event(raw_input)
        msg = f"Unknown input source: {raw_input.source}"
        raise ValueError(msg)

    def _normalize_text(self, raw_input: RawInput) -> NormalizedInput:
        """Normalize text input.

        Time Complexity: O(n) where n is input length

        Args:
            raw_input: Raw text input

        Returns:
            NormalizedInput with normalized text

        Raises:
            ValueError: If text is invalid

        """
        # Validate content is string
        if not isinstance(raw_input.content, str):
            msg = f"Text input content must be string, got {type(raw_input.content).__name__}"
            raise ValueError(
                msg,
            )

        # Check length
        if len(raw_input.content) > self.max_length:
            msg = f"Input exceeds maximum length of {self.max_length} characters"
            raise ValueError(msg)

        # Validate encoding
        try:
            raw_input.content.encode("utf-8")
        except UnicodeEncodeError as e:
            msg = f"Invalid text encoding: {e}"
            raise ValueError(msg) from e

        # Sanitize input for security
        sanitized = self._sanitize_input(raw_input.content)

        # Normalize whitespace
        normalized_text = self._normalize_whitespace(sanitized)

        # Validate not empty after normalization
        if not normalized_text:
            msg = "Input is empty after normalization"
            raise ValueError(msg)

        # Extract metadata
        metadata = self._extract_text_metadata(raw_input.content, normalized_text)
        metadata.update(raw_input.metadata)  # Preserve original metadata

        return NormalizedInput(
            text=normalized_text,
            source=raw_input.source,
            user_id=raw_input.user_id,
            timestamp=raw_input.timestamp,
            metadata=metadata,
            original_content=raw_input.content[:100],  # Store first 100 chars for debugging
        )

    def _normalize_voice(self, raw_input: RawInput) -> NormalizedInput:
        """Normalize voice input (already transcribed by speech engine).

        Time Complexity: O(n) where n is input length

        Args:
            raw_input: Raw voice input (transcribed text)

        Returns:
            NormalizedInput with normalized text

        Raises:
            ValueError: If voice input is invalid

        """
        # Voice input should already be transcribed to text
        if not isinstance(raw_input.content, str):
            msg = f"Voice input content must be transcribed string, got {type(raw_input.content).__name__}"
            raise ValueError(
                msg,
            )

        # Check length
        if len(raw_input.content) > self.max_length:
            msg = f"Input exceeds maximum length of {self.max_length} characters"
            raise ValueError(msg)

        # Normalize whitespace (voice transcription may have extra spaces)
        normalized_text = self._normalize_whitespace(raw_input.content)

        # Validate not empty
        if not normalized_text:
            msg = "Voice input is empty after normalization"
            raise ValueError(msg)

        # Extract metadata
        metadata = self._extract_voice_metadata(raw_input.content, normalized_text)
        metadata.update(raw_input.metadata)  # Preserve original metadata

        return NormalizedInput(
            text=normalized_text,
            source=raw_input.source,
            user_id=raw_input.user_id,
            timestamp=raw_input.timestamp,
            metadata=metadata,
            original_content=raw_input.content[:100],
        )

    def _normalize_system_event(self, raw_input: RawInput) -> NormalizedInput:
        """Normalize system event input.

        Time Complexity: O(n) where n is event data size

        Args:
            raw_input: Raw system event

        Returns:
            NormalizedInput with natural language representation

        Raises:
            ValueError: If system event is invalid

        """
        # System events can be dict or string
        if isinstance(raw_input.content, dict):
            # Convert dict to natural language
            normalized_text = self._event_dict_to_text(raw_input.content)
        elif isinstance(raw_input.content, str):
            # Already text, just normalize
            normalized_text = self._normalize_whitespace(raw_input.content)
        else:
            msg = f"System event content must be dict or string, got {type(raw_input.content).__name__}"
            raise ValueError(
                msg,
            )

        # Validate not empty
        if not normalized_text:
            msg = "System event is empty after normalization"
            raise ValueError(msg)

        # Extract metadata
        metadata = self._extract_system_event_metadata(raw_input.content)
        metadata.update(raw_input.metadata)  # Preserve original metadata

        return NormalizedInput(
            text=normalized_text,
            source=raw_input.source,
            user_id=raw_input.user_id,
            timestamp=raw_input.timestamp,
            metadata=metadata,
            original_content=str(raw_input.content)[:100],
        )

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.

        Time Complexity: O(n) where n is text length

        Args:
            text: Input text

        Returns:
            Text with normalized whitespace

        """
        # Strip leading/trailing whitespace
        text = text.strip()

        # Replace multiple spaces with single space
        text = " ".join(text.split())

        # Remove control characters except newline and tab
        return "".join(char for char in text if char.isprintable() or char in "\n\t")

    def _sanitize_input(self, text: str) -> str:
        """Sanitize input for security (prevent XSS, injection).

        Time Complexity: O(n) where n is text length

        Args:
            text: Input text

        Returns:
            Sanitized text

        """
        # Remove dangerous patterns
        sanitized = self._dangerous_pattern.sub("", text)

        # HTML entity encoding for special characters
        return sanitized.replace("<", "&lt;").replace(">", "&gt;")

    def _extract_text_metadata(self, original: str, normalized: str) -> dict[str, Any]:
        """Extract metadata from text input.

        Args:
            original: Original text
            normalized: Normalized text

        Returns:
            Dictionary of extracted metadata

        """
        return {
            "original_length": len(original),
            "normalized_length": len(normalized),
            "has_uppercase": any(c.isupper() for c in original),
            "has_numbers": any(c.isdigit() for c in original),
            "has_special_chars": any(not c.isalnum() and not c.isspace() for c in original),
        }

    def _extract_voice_metadata(self, original: str, normalized: str) -> dict[str, Any]:
        """Extract metadata from voice input.

        Args:
            original: Original transcribed text
            normalized: Normalized text

        Returns:
            Dictionary of extracted metadata

        """
        metadata = self._extract_text_metadata(original, normalized)
        metadata["transcribed"] = True
        return metadata

    def _extract_system_event_metadata(self, content: Any) -> dict[str, Any]:  # noqa: ANN401
        """Extract metadata from system event.

        Args:
            content: System event content

        Returns:
            Dictionary of extracted metadata

        """
        metadata = {"system_generated": True}

        if isinstance(content, dict):
            metadata["event_type"] = content.get("type", "unknown")
            metadata["event_keys"] = list(content.keys())

        return metadata

    def _event_dict_to_text(self, event: dict[str, Any]) -> str:
        """Convert system event dict to natural language text.

        Args:
            event: System event dictionary

        Returns:
            Natural language representation

        Raises:
            ValueError: If event is empty or has no meaningful content

        """
        if not event:
            msg = "System event dictionary is empty"
            raise ValueError(msg)

        event_type = event.get("type", "unknown")

        # Handle common event types
        if event_type == "timer_expired":
            return f"Timer expired: {event.get('name', 'unnamed')}"
        if event_type == "alarm_triggered":
            return f"Alarm triggered: {event.get('name', 'unnamed')}"
        if event_type == "reminder":
            return f"Reminder: {event.get('message', 'no message')}"
        if event_type == "notification":
            return f"Notification from {event.get('app', 'unknown')}: {event.get('message', '')}"
        # Generic conversion
        parts = [f"{key}: {value}" for key, value in event.items() if key != "type"]
        if not parts and event_type == "unknown":
            msg = "System event has no meaningful content"
            raise ValueError(msg)
        return f"{event_type} - {', '.join(parts)}" if parts else event_type
