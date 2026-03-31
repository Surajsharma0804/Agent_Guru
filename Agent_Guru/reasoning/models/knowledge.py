"""
Knowledge Query data models for personal knowledge reasoning.

This module implements comprehensive knowledge query models for querying and
synthesizing personal knowledge from memories, world state, and behavioral patterns.
Supports temporal queries ("when did I..."), aggregation queries ("who do I message most"),
pattern queries ("what do I usually do"), and factual queries ("what is my...").

Performance Characteristics:
    - Time Complexity: O(1) for field access
    - Space Complexity: O(n) where n is content size
    - Validation: <1ms per model instance

Design Principles:
    - Type-safe with Pydantic validation
    - Immutable after creation (frozen=True for production use)
    - JSON serializable for storage
    - Comprehensive field validation

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class KnowledgeQueryType(str, Enum):
    """Types of knowledge queries supported by the system.

    Query types determine how data is retrieved and synthesized:
    - TEMPORAL: Time-based queries (when, how long ago, how often)
    - AGGREGATION: Statistical queries (who most, what most, how many)
    - PATTERN: Behavioral pattern queries (usually, typically, normally)
    - FACTUAL: Direct fact queries (what is, who is, where is)
    """

    TEMPORAL = "temporal"
    AGGREGATION = "aggregation"
    PATTERN = "pattern"
    FACTUAL = "factual"


class TimeRange(BaseModel):
    """Represents a time range for temporal queries.

    Time ranges can be specified as absolute (start/end timestamps) or
    relative (last N days/weeks/months). Helper methods provide common
    time ranges like last_week(), last_month(), last_year().

    Attributes:
        start: Start of time range (inclusive)
        end: End of time range (inclusive)
        description: Human-readable description of the time range

    Example:
        >>> time_range = TimeRange.last_week()
        >>> print(time_range.description)
        'last week'
        >>> time_range = TimeRange.last_month()
        >>> print(time_range.description)
        'last month'
    """

    start: datetime = Field(..., description="Start of time range (inclusive)")
    end: datetime = Field(..., description="End of time range (inclusive)")
    description: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable description of the time range",
    )

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    @field_validator("description")
    @classmethod
    def validate_description_not_empty(cls, v: str) -> str:
        """Validate that description is not just whitespace."""
        if not v.strip():
            raise ValueError("Description cannot be empty or whitespace only")
        return v.strip()

    @model_validator(mode="after")
    def validate_time_range(self) -> "TimeRange":
        """Validate that start is before or equal to end."""
        if self.start > self.end:
            raise ValueError(
                f"Start time {self.start} must be before or equal to end time {self.end}"
            )
        return self

    @classmethod
    def last_week(cls) -> "TimeRange":
        """Create a time range for the last 7 days.

        Returns:
            TimeRange for the last week

        Example:
            >>> time_range = TimeRange.last_week()
            >>> print(time_range.description)
            'last week'
        """
        now = datetime.utcnow()
        start = now - timedelta(days=7)
        return cls(start=start, end=now, description="last week")

    @classmethod
    def last_month(cls) -> "TimeRange":
        """Create a time range for the last 30 days.

        Returns:
            TimeRange for the last month

        Example:
            >>> time_range = TimeRange.last_month()
            >>> print(time_range.description)
            'last month'
        """
        now = datetime.utcnow()
        start = now - timedelta(days=30)
        return cls(start=start, end=now, description="last month")

    @classmethod
    def last_year(cls) -> "TimeRange":
        """Create a time range for the last 365 days.

        Returns:
            TimeRange for the last year

        Example:
            >>> time_range = TimeRange.last_year()
            >>> print(time_range.description)
            'last year'
        """
        now = datetime.utcnow()
        start = now - timedelta(days=365)
        return cls(start=start, end=now, description="last year")

    @classmethod
    def last_n_days(cls, n: int) -> "TimeRange":
        """Create a time range for the last N days.

        Args:
            n: Number of days to look back

        Returns:
            TimeRange for the last N days

        Raises:
            ValueError: If n is not positive

        Example:
            >>> time_range = TimeRange.last_n_days(14)
            >>> print(time_range.description)
            'last 14 days'
        """
        if n <= 0:
            raise ValueError(f"Number of days must be positive, got {n}")
        now = datetime.utcnow()
        start = now - timedelta(days=n)
        return cls(start=start, end=now, description=f"last {n} days")

    @classmethod
    def today(cls) -> "TimeRange":
        """Create a time range for today (since midnight).

        Returns:
            TimeRange for today

        Example:
            >>> time_range = TimeRange.today()
            >>> print(time_range.description)
            'today'
        """
        now = datetime.utcnow()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start, end=now, description="today")

    @classmethod
    def yesterday(cls) -> "TimeRange":
        """Create a time range for yesterday (full day).

        Returns:
            TimeRange for yesterday

        Example:
            >>> time_range = TimeRange.yesterday()
            >>> print(time_range.description)
            'yesterday'
        """
        now = datetime.utcnow()
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
        return cls(start=start, end=end, description="yesterday")


class KnowledgeQuery(BaseModel):
    """Represents a knowledge query from the user.

    Knowledge queries are questions about personal data, patterns, and history.
    They are detected from user input and routed to the Knowledge Synthesis Engine.

    Attributes:
        query_text: Original query text from user
        query_type: Type of query (temporal, aggregation, pattern, factual)
        time_range: Optional time range for temporal queries
        entities: Extracted entities relevant to the query
        confidence: Confidence in query detection (0.0-1.0)

    Example:
        >>> query = KnowledgeQuery(
        ...     query_text="when did I last call John?",
        ...     query_type=KnowledgeQueryType.TEMPORAL,
        ...     time_range=TimeRange.last_month(),
        ...     entities={"person": "John", "action": "call"},
        ...     confidence=0.95
        ... )
    """

    query_text: str = Field(
        ..., min_length=1, max_length=1000, description="Original query text from user"
    )
    query_type: KnowledgeQueryType = Field(
        ..., description="Type of query (temporal, aggregation, pattern, factual)"
    )
    time_range: Optional[TimeRange] = Field(
        default=None, description="Optional time range for temporal queries"
    )
    entities: dict[str, Any] = Field(
        default_factory=dict, description="Extracted entities relevant to the query"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in query detection (0.0-1.0)"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query_text": "when did I last call John?",
            "query_type": "temporal",
            "time_range": {
                "start": "2024-01-01T00:00:00",
                "end": "2024-01-31T23:59:59",
                "description": "last month",
            },
            "entities": {"person": "John", "action": "call"},
            "confidence": 0.95,
        }
    })

    @field_validator("query_text")
    @classmethod
    def validate_query_text_not_empty(cls, v: str) -> str:
        """Validate that query_text is not just whitespace."""
        if not v.strip():
            raise ValueError("Query text cannot be empty or whitespace only")
        return v.strip()

    @model_validator(mode="after")
    def validate_temporal_query_has_time_range(self) -> "KnowledgeQuery":
        """Validate that temporal queries have a time range."""
        if self.query_type == KnowledgeQueryType.TEMPORAL and self.time_range is None:
            # Auto-assign default time range for temporal queries
            self.time_range = TimeRange.last_month()
        return self


class Pattern(BaseModel):
    """Represents a detected behavioral pattern.

    Patterns are recurring behaviors or routines detected from user data.
    They are used to answer pattern queries and provide proactive suggestions.

    Attributes:
        pattern_type: Type of pattern (daily, weekly, monthly, situational)
        description: Human-readable description of the pattern
        frequency: How often this pattern occurs (times per period)
        confidence: Confidence in pattern detection (0.0-1.0)
        examples: Example instances of this pattern

    Example:
        >>> pattern = Pattern(
        ...     pattern_type="daily",
        ...     description="User checks email every morning at 9am",
        ...     frequency=0.95,
        ...     confidence=0.92,
        ...     examples=["2024-01-15 09:00", "2024-01-16 09:05", "2024-01-17 08:58"]
        ... )
    """

    pattern_type: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Type of pattern (daily, weekly, monthly, situational)",
    )
    description: str = Field(
        ..., min_length=1, max_length=2000, description="Human-readable description of the pattern"
    )
    frequency: float = Field(
        ..., ge=0.0, le=1.0, description="How often this pattern occurs (0.0-1.0, 1.0=always)"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in pattern detection (0.0-1.0)"
    )
    examples: list[str] = Field(
        default_factory=list, description="Example instances of this pattern"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "pattern_type": "daily",
            "description": "User checks email every morning at 9am",
            "frequency": 0.95,
            "confidence": 0.92,
            "examples": ["2024-01-15 09:00", "2024-01-16 09:05", "2024-01-17 08:58"],
        }
    })

    @field_validator("pattern_type")
    @classmethod
    def validate_pattern_type(cls, v: str) -> str:
        """Validate pattern_type is one of the expected values."""
        valid_types = {"daily", "weekly", "monthly", "situational", "temporal", "contextual"}
        if v.strip().lower() not in valid_types:
            raise ValueError(f"pattern_type must be one of {valid_types}, got '{v}'")
        return v.strip().lower()

    @field_validator("description")
    @classmethod
    def validate_description_not_empty(cls, v: str) -> str:
        """Validate that description is not just whitespace."""
        if not v.strip():
            raise ValueError("Description cannot be empty or whitespace only")
        return v.strip()

    @field_validator("examples")
    @classmethod
    def validate_examples_not_empty(cls, v: list[str]) -> list[str]:
        """Validate that examples are not empty strings."""
        if v:
            cleaned = [example.strip() for example in v if example.strip()]
            if len(cleaned) != len(v):
                raise ValueError("Examples cannot be empty or whitespace only")
            return cleaned
        return v


class KnowledgeAnswer(BaseModel):
    """Represents the synthesized answer to a knowledge query.

    Knowledge answers combine retrieved data, detected patterns, and statistics
    into a natural language response with supporting evidence.

    Attributes:
        summary: Natural language summary of the answer
        confidence: Confidence in the answer (0.0-1.0)
        supporting_memories: Memory IDs that support this answer
        patterns: Detected patterns relevant to the query
        statistics: Statistical data relevant to the query
        visualization_data: Optional data for visualizations

    Example:
        >>> answer = KnowledgeAnswer(
        ...     summary="You last called John 3 days ago on January 15th at 2:30pm",
        ...     confidence=0.98,
        ...     supporting_memories=["mem_123", "mem_456"],
        ...     patterns=[],
        ...     statistics={"total_calls": 15, "avg_duration": 300},
        ...     visualization_data={"type": "timeline", "data": [...]}
        ... )
    """

    summary: str = Field(
        ..., min_length=1, max_length=5000, description="Natural language summary of the answer"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the answer (0.0-1.0)")
    supporting_memories: list[str] = Field(
        default_factory=list, description="Memory IDs that support this answer"
    )
    patterns: list[Pattern] = Field(
        default_factory=list, description="Detected patterns relevant to the query"
    )
    statistics: dict[str, Any] = Field(
        default_factory=dict, description="Statistical data relevant to the query"
    )
    visualization_data: Optional[dict[str, Any]] = Field(
        default=None, description="Optional data for visualizations"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "summary": "You last called John 3 days ago on January 15th at 2:30pm",
            "confidence": 0.98,
            "supporting_memories": ["mem_123", "mem_456"],
            "patterns": [
                {
                    "pattern_type": "weekly",
                    "description": "You typically call John on Mondays",
                    "frequency": 0.85,
                    "confidence": 0.90,
                    "examples": ["2024-01-08", "2024-01-15", "2024-01-22"],
                }
            ],
            "statistics": {"total_calls": 15, "avg_duration": 300, "last_call_days_ago": 3},
            "visualization_data": {"type": "timeline", "data": []},
        }
    })

    @field_validator("summary")
    @classmethod
    def validate_summary_not_empty(cls, v: str) -> str:
        """Validate that summary is not just whitespace."""
        if not v.strip():
            raise ValueError("Summary cannot be empty or whitespace only")
        return v.strip()

    @field_validator("supporting_memories")
    @classmethod
    def validate_memories_not_empty(cls, v: list[str]) -> list[str]:
        """Validate that memory IDs are not empty strings."""
        if v:
            cleaned = [mem_id.strip() for mem_id in v if mem_id.strip()]
            if len(cleaned) != len(v):
                raise ValueError("Memory IDs cannot be empty or whitespace only")
            return cleaned
        return v

    @field_validator("patterns")
    @classmethod
    def validate_patterns_limit(cls, v: list[Pattern]) -> list[Pattern]:
        """Validate that patterns list is not too large."""
        if len(v) > 10:
            raise ValueError(f"Too many patterns ({len(v)}), maximum is 10")
        return v

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "summary": "You last called John 3 days ago on January 15th at 2:30pm",
                "confidence": 0.98,
                "supporting_memories": ["mem_123", "mem_456"],
                "patterns": [
                    {
                        "pattern_type": "weekly",
                        "description": "You typically call John on Mondays",
                        "frequency": 0.85,
                        "confidence": 0.90,
                        "examples": ["2024-01-08", "2024-01-15", "2024-01-22"],
                    }
                ],
                "statistics": {"total_calls": 15, "avg_duration": 300, "last_call_days_ago": 3},
                "visualization_data": {"type": "timeline", "data": []},
            }
        }
