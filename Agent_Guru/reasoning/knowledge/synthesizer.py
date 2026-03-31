"""
Knowledge Synthesizer for personal knowledge reasoning.

This module implements the Knowledge Synthesis Engine that retrieves, analyzes,
and synthesizes answers to knowledge queries. It combines data from Memory Retrieval,
World State, Behavioral Learning, and Task History to provide comprehensive answers
with supporting evidence, patterns, and statistics.

Performance Characteristics:
    - Time Complexity: O(n log n) for pattern detection where n=memories
    - Space Complexity: O(k) where k=retrieved memories (max 50)
    - Synthesis Latency: <1.5s (target), <1.0s (typical)
    - Retrieval: <100ms, Pattern Detection: <200ms, Aggregation: <100ms
    - LLM Synthesis: <1.0s (target)

Design Principles:
    - Fast data retrieval with semantic search
    - Efficient pattern detection algorithms
    - Multi-source data aggregation
    - Privacy-preserving (user_id filtering)
    - Confidence scoring for uncertainty handling
    - LLM-based natural language synthesis
    - PII redaction in responses
    - Comprehensive audit logging

Security & Privacy:
    - User data isolation (strict user_id filtering)
    - PII redaction (email, phone, SSN, credit card)
    - Confidence thresholds (indicate uncertainty <0.6)
    - Audit logging for all queries
    - No cross-user data leakage

Competitive Advantage:
    - Comprehensive personal knowledge synthesis
    - Multi-source data integration
    - Pattern detection for behavioral insights
    - Statistical aggregation for quantitative answers
    - Natural language answer generation with LLM
    - Privacy-first architecture

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import asyncio
import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeAnswer,
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
)
from Agent_Guru.reasoning.models.memory import Memory, MemoryType

# Set up logger for audit logging
logger = logging.getLogger(__name__)

# Try to import LLM clients
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai: Any = None  # type: ignore[assignment]

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic: Any = None  # type: ignore[assignment]


class LLMSynthesisResponse(BaseModel):
    """Structured response from LLM answer synthesis.

    Attributes:
        summary: Natural language answer summary
        confidence: Confidence score (0.0-1.0)
        reasoning: Brief explanation of synthesis
        key_insights: List of key insights from data
    """

    summary: str = Field(..., description="Natural language answer summary")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(default="", description="Synthesis reasoning")
    key_insights: list[str] = Field(default_factory=list, description="Key insights")


# PII redaction patterns (privacy-preserving aggregation)
PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
    "url": re.compile(r"https?://[^\s]+"),
}


def redact_pii(text: str) -> str:
    """Redact PII from text for privacy-preserving responses.

    Time Complexity: O(n) where n is text length
    Space Complexity: O(n) for redacted text

    Redacts:
    - Email addresses → [EMAIL]
    - Phone numbers → [PHONE]
    - SSN → [SSN]
    - Credit card numbers → [CREDIT_CARD]
    - IP addresses → [IP]
    - URLs → [URL]

    Args:
        text: Text potentially containing PII

    Returns:
        Text with PII redacted

    Example:
        >>> redact_pii("Contact me at john@example.com or 555-123-4567")
        'Contact me at [EMAIL] or [PHONE]'
    """
    redacted = text

    # Redact each PII type
    redacted = PII_PATTERNS["email"].sub("[EMAIL]", redacted)
    redacted = PII_PATTERNS["phone"].sub("[PHONE]", redacted)
    redacted = PII_PATTERNS["ssn"].sub("[SSN]", redacted)
    redacted = PII_PATTERNS["credit_card"].sub("[CREDIT_CARD]", redacted)
    redacted = PII_PATTERNS["ip_address"].sub("[IP]", redacted)
    redacted = PII_PATTERNS["url"].sub("[URL]", redacted)

    return redacted


class KnowledgeSynthesizer:
    """Synthesizes answers to knowledge queries from multiple data sources.

    This class retrieves relevant data from Memory Retrieval Layer, World State,
    Behavioral Learning Engine, and Task History, then synthesizes comprehensive
    answers with supporting evidence, patterns, and statistics.

    Time Complexity:
        - synthesize_answer: O(n log n) where n=retrieved memories
        - retrieve_relevant_data: O(log n) with semantic search
        - detect_patterns: O(n log n) for sorting and grouping
        - aggregate_statistics: O(n) for counting and averaging
        - generate_answer: O(1) for formatting

    Space Complexity:
        - O(k) where k=retrieved memories (max 50)

    Attributes:
        memory_retriever: MemoryRetriever for semantic search
        max_memories: Maximum memories to retrieve (default 50)
        pattern_min_frequency: Minimum frequency for pattern detection (default 0.3)
        confidence_threshold: Minimum confidence for answers (default 0.6)

    Example:
        >>> synthesizer = KnowledgeSynthesizer(memory_retriever)
        >>> query = KnowledgeQuery(
        ...     query_text="when did I last call John?",
        ...     query_type=KnowledgeQueryType.TEMPORAL,
        ...     time_range=TimeRange.last_month(),
        ...     entities={"person": "John", "action": "call"},
        ...     confidence=0.95
        ... )
        >>> answer = synthesizer.synthesize_answer(query, user_id="user_123")
        >>> print(answer.summary)
    """

    def __init__(
        self,
        memory_retriever: MemoryRetriever,
        max_memories: int = 50,
        pattern_min_frequency: float = 0.3,
        confidence_threshold: float = 0.6,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4-turbo-preview",
        llm_api_key: Optional[str] = None,
        llm_timeout_ms: float = 1000.0,
        llm_max_retries: int = 3,
        use_llm_synthesis: bool = True,
    ) -> None:
        """Initialize KnowledgeSynthesizer.

        Args:
            memory_retriever: MemoryRetriever instance for data retrieval
            max_memories: Maximum memories to retrieve (default 50)
            pattern_min_frequency: Minimum frequency for pattern detection (default 0.3)
            confidence_threshold: Minimum confidence for answers (default 0.6)
            llm_provider: LLM provider ("openai" or "anthropic")
            llm_model: LLM model name
            llm_api_key: API key for LLM provider
            llm_timeout_ms: LLM timeout in milliseconds (default 1000ms)
            llm_max_retries: Maximum LLM retries (default 3)
            use_llm_synthesis: Whether to use LLM for answer synthesis (default True)

        Raises:
            ValueError: If parameters are out of valid range
        """
        if max_memories < 1:
            raise ValueError(f"max_memories must be >= 1, got {max_memories}")
        if not 0.0 <= pattern_min_frequency <= 1.0:
            raise ValueError(f"pattern_min_frequency must be 0.0-1.0, got {pattern_min_frequency}")
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(f"confidence_threshold must be 0.0-1.0, got {confidence_threshold}")

        self.memory_retriever = memory_retriever
        self.max_memories = max_memories
        self.pattern_min_frequency = pattern_min_frequency
        self.confidence_threshold = confidence_threshold

        # LLM configuration
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm_api_key = llm_api_key
        self.llm_timeout_ms = llm_timeout_ms
        self.llm_max_retries = llm_max_retries
        self.use_llm_synthesis = use_llm_synthesis

        # Initialize LLM client if enabled
        self.llm_client: Optional[Any] = None
        if self.use_llm_synthesis:
            self._initialize_llm_client()

    def synthesize_answer(self, query: KnowledgeQuery, user_id: str) -> KnowledgeAnswer:
        """Synthesize comprehensive answer to knowledge query.

        Time Complexity: O(n log n) where n=retrieved memories
        Latency Budget: <1.5s (target), <1.0s (typical)

        This is the main entry point for knowledge synthesis. It orchestrates
        data retrieval, pattern detection, aggregation, and answer generation.

        Privacy & Security:
        - Strict user_id filtering (only user's own data)
        - PII redaction in responses
        - Confidence thresholds (indicate uncertainty <0.6)
        - Audit logging for all queries

        Args:
            query: KnowledgeQuery to answer
            user_id: User ID for data filtering and privacy

        Returns:
            KnowledgeAnswer with summary, evidence, patterns, and statistics

        Example:
            >>> synthesizer = KnowledgeSynthesizer(memory_retriever)
            >>> answer = synthesizer.synthesize_answer(query, "user_123")
            >>> print(f"Confidence: {answer.confidence:.2f}")
        """
        start_time = time.perf_counter()

        # Audit log: Query received
        logger.info(
            "Knowledge query received",
            extra={
                "user_id": user_id,
                "query_text": query.query_text,
                "query_type": query.query_type.value,
                "query_confidence": query.confidence,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

        # Step 1: Retrieve relevant data (<100ms) - PRIVACY: user_id filtering
        memories = self.retrieve_relevant_data(query, user_id)

        # Audit log: Data retrieved
        logger.info(
            "Knowledge query data retrieved",
            extra={
                "user_id": user_id,
                "memories_count": len(memories),
                "query_type": query.query_type.value,
            },
        )

        # Step 2: Detect patterns (<200ms)
        patterns = self.detect_patterns(memories, query)

        # Step 3: Aggregate statistics (<100ms)
        statistics = self.aggregate_statistics(memories, query)

        # Step 4: Generate answer (<100ms)
        answer = self.generate_answer(query, memories, patterns, statistics)

        # PRIVACY: Redact PII from summary
        answer.summary = redact_pii(answer.summary)

        # CONFIDENCE: Add uncertainty indicator if below threshold
        if answer.confidence < self.confidence_threshold:
            if not answer.summary.lower().startswith("i'm not very confident"):
                answer.summary = f"I'm not very confident, but {answer.summary.lower()}"

        # Check latency budget
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Audit log: Query completed
        logger.info(
            "Knowledge query completed",
            extra={
                "user_id": user_id,
                "query_type": query.query_type.value,
                "answer_confidence": answer.confidence,
                "memories_used": len(answer.supporting_memories),
                "patterns_detected": len(answer.patterns),
                "latency_ms": round(elapsed_ms, 2),
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            },
        )

        if elapsed_ms > 1500:
            # Log warning but don't fail
            logger.warning(
                "Knowledge query exceeded latency budget",
                extra={
                    "user_id": user_id,
                    "query_type": query.query_type.value,
                    "latency_ms": round(elapsed_ms, 2),
                    "budget_ms": 1500,
                },
            )

        return answer

    def retrieve_relevant_data(self, query: KnowledgeQuery, user_id: str) -> list[Memory]:
        """Retrieve relevant data from multiple sources.

        Time Complexity: O(log n) with semantic search
        Latency Budget: <100ms

        Currently retrieves from Memory Retrieval Layer. Future versions will
        integrate World State, Behavioral Learning Engine, and Task History.

        Privacy & Security:
        - STRICT user_id filtering (only user's own data)
        - No cross-user data leakage
        - Validates all memories belong to user_id

        Args:
            query: KnowledgeQuery to retrieve data for
            user_id: User ID for data filtering

        Returns:
            List of relevant Memory objects (max self.max_memories)

        Raises:
            ValueError: If user_id is empty or invalid

        Example:
            >>> synthesizer = KnowledgeSynthesizer(memory_retriever)
            >>> memories = synthesizer.retrieve_relevant_data(query, "user_123")
            >>> print(f"Retrieved {len(memories)} memories")
        """
        # PRIVACY: Validate user_id
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")

        # Determine memory types based on query type
        memory_types: Optional[list[MemoryType]] = None
        if query.query_type == KnowledgeQueryType.FACTUAL:
            # Factual queries prefer semantic memories (facts)
            memory_types = [MemoryType.SEMANTIC, MemoryType.PREFERENCE]
        elif query.query_type == KnowledgeQueryType.PATTERN:
            # Pattern queries prefer episodic and task memories
            memory_types = [MemoryType.EPISODIC, MemoryType.TASK]
        # For temporal and aggregation queries, use all memory types

        # Retrieve memories using semantic search - PRIVACY: user_id filtering
        memories = self.memory_retriever.retrieve(
            query=query.query_text,
            user_id=user_id,
            memory_types=memory_types,
            top_k=self.max_memories,
        )

        # PRIVACY: Double-check all memories belong to user_id (defense in depth)
        validated_memories = []
        for memory in memories:
            if memory.user_id == user_id:
                validated_memories.append(memory)
            else:
                # Log security violation
                logger.error(
                    "SECURITY VIOLATION: Cross-user data leakage detected",
                    extra={
                        "requested_user_id": user_id,
                        "memory_user_id": memory.user_id,
                        "memory_id": str(memory.memory_id),
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    },
                )

        # Filter by time range if specified
        if query.time_range is not None:
            validated_memories = [
                m
                for m in validated_memories
                if query.time_range.start <= m.timestamp <= query.time_range.end
            ]

        return validated_memories

    def detect_patterns(self, memories: list[Memory], query: KnowledgeQuery) -> list[Pattern]:
        """Detect behavioral patterns from memories.

        Time Complexity: O(n log n) for sorting and grouping
        Latency Budget: <200ms

        Detects temporal patterns (daily, weekly, monthly routines) by analyzing
        memory timestamps and content. Patterns must occur with frequency >=
        pattern_min_frequency to be included.

        Args:
            memories: List of Memory objects to analyze
            query: KnowledgeQuery for context

        Returns:
            List of detected Pattern objects

        Example:
            >>> synthesizer = KnowledgeSynthesizer(memory_retriever)
            >>> patterns = synthesizer.detect_patterns(memories, query)
            >>> for pattern in patterns:
            ...     print(f"{pattern.pattern_type}: {pattern.description}")
        """
        if not memories:
            return []

        patterns: list[Pattern] = []

        # Detect daily patterns (same time of day)
        daily_pattern = self._detect_daily_pattern(memories)
        if daily_pattern:
            patterns.append(daily_pattern)

        # Detect weekly patterns (same day of week)
        weekly_pattern = self._detect_weekly_pattern(memories)
        if weekly_pattern:
            patterns.append(weekly_pattern)

        # Detect monthly patterns (same day of month)
        monthly_pattern = self._detect_monthly_pattern(memories)
        if monthly_pattern:
            patterns.append(monthly_pattern)

        return patterns

    def aggregate_statistics(self, memories: list[Memory], query: KnowledgeQuery) -> dict[str, Any]:
        """Aggregate statistical data from memories.

        Time Complexity: O(n) for counting and averaging
        Latency Budget: <100ms

        Computes statistics like count, average, ranking, and top-k based on
        query type and entities.

        Args:
            memories: List of Memory objects to aggregate
            query: KnowledgeQuery for context

        Returns:
            Dictionary of statistical data

        Example:
            >>> synthesizer = KnowledgeSynthesizer(memory_retriever)
            >>> stats = synthesizer.aggregate_statistics(memories, query)
            >>> print(f"Total count: {stats.get('total_count', 0)}")
        """
        if not memories:
            return {"total_count": 0}

        statistics: dict[str, Any] = {
            "total_count": len(memories),
            "time_range": None,
            "most_recent": None,
            "oldest": None,
        }

        # Time range statistics
        if memories:
            timestamps = [m.timestamp for m in memories]
            statistics["most_recent"] = max(timestamps).isoformat()
            statistics["oldest"] = min(timestamps).isoformat()
            statistics["time_span_days"] = (max(timestamps) - min(timestamps)).days

        # Entity-based aggregation
        if query.entities:
            # Count occurrences of entities
            entity_counts: dict[str, Counter] = defaultdict(Counter)
            for memory in memories:
                for entity_type, entity_value in query.entities.items():
                    # Check if entity appears in memory content
                    if entity_value.lower() in memory.content.lower():
                        entity_counts[entity_type][entity_value] += 1

            # Add entity statistics
            for entity_type, counter in entity_counts.items():
                statistics[f"{entity_type}_count"] = dict(counter)
                if counter:
                    most_common = counter.most_common(1)[0]
                    statistics[f"most_common_{entity_type}"] = {
                        "value": most_common[0],
                        "count": most_common[1],
                    }

        # Query-specific aggregation
        if query.query_type == KnowledgeQueryType.AGGREGATION:
            # Compute averages, rankings, top-k
            statistics.update(self._compute_aggregation_stats(memories, query))

        return statistics

    def generate_answer(
        self,
        query: KnowledgeQuery,
        memories: list[Memory],
        patterns: list[Pattern],
        statistics: dict[str, Any],
    ) -> KnowledgeAnswer:
        """Generate natural language answer from synthesized data.

        Time Complexity: O(1) for formatting
        Latency Budget: <100ms (template-based), <1.0s (LLM-based)

        Formats the synthesized data into a natural language answer with
        supporting evidence, patterns, and statistics. Routes to specialized
        handlers based on query type.

        If LLM synthesis is enabled, attempts to use LLM for natural language
        generation. Falls back to template-based generation on failure.

        Args:
            query: Original KnowledgeQuery
            memories: Retrieved memories
            patterns: Detected patterns
            statistics: Aggregated statistics

        Returns:
            KnowledgeAnswer with formatted summary

        Example:
            >>> synthesizer = KnowledgeSynthesizer(memory_retriever)
            >>> answer = synthesizer.generate_answer(query, memories, patterns, stats)
            >>> print(answer.summary)
        """
        # Try LLM synthesis if enabled
        if self.use_llm_synthesis and self.llm_client is not None:
            try:
                # Run async LLM synthesis in sync context
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    # If event loop is already running, create a new task
                    # This handles the case where we're called from async context
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.synthesize_answer_with_llm(query, memories, patterns, statistics),
                        )
                        return future.result(timeout=self.llm_timeout_ms / 1000.0)
                else:
                    # If no event loop is running, use asyncio.run
                    return asyncio.run(
                        self.synthesize_answer_with_llm(query, memories, patterns, statistics)
                    )
            except Exception:
                # Fall back to template-based generation on any error
                pass

        # Template-based generation (fallback or default)
        # Route to specialized handler based on query type
        if query.query_type == KnowledgeQueryType.TEMPORAL:
            return self.handle_temporal_query(query, memories, statistics)
        elif query.query_type == KnowledgeQueryType.AGGREGATION:
            return self.handle_aggregation_query(query, memories, statistics)
        elif query.query_type == KnowledgeQueryType.PATTERN:
            return self.handle_pattern_query(query, memories, patterns, statistics)
        else:  # FACTUAL
            return self.handle_factual_query(query, memories, statistics)

    def handle_temporal_query(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> KnowledgeAnswer:
        """Handle temporal queries (when, how long ago, last time).

        Retrieves memories, sorts by timestamp, and formats answer with
        temporal context. Calculates confidence based on data recency and
        completeness.

        Time Complexity: O(n log n) for sorting
        Latency Budget: <100ms

        Args:
            query: Temporal KnowledgeQuery
            memories: Retrieved memories (already filtered by time range)
            statistics: Pre-computed statistics

        Returns:
            KnowledgeAnswer with temporal summary and confidence

        Example:
            >>> answer = synthesizer.handle_temporal_query(query, memories, stats)
            >>> print(f"Last occurrence: {answer.summary}")
        """
        # Sort memories by timestamp (most recent first)
        sorted_memories = sorted(memories, key=lambda m: m.timestamp, reverse=True)

        # Generate temporal summary
        summary = self._generate_temporal_summary(query, sorted_memories, statistics)

        # Calculate confidence for temporal queries
        confidence = self._calculate_temporal_confidence(query, sorted_memories, statistics)

        # Add confidence indicator if below threshold
        if confidence < self.confidence_threshold:
            summary = f"I'm not very confident, but {summary.lower()}"

        # Extract supporting memory IDs (top 5 most recent)
        supporting_memories = [str(m.memory_id) for m in sorted_memories[:5]]

        return KnowledgeAnswer(
            summary=summary,
            confidence=confidence,
            supporting_memories=supporting_memories,
            patterns=[],
            statistics=statistics,
        )

    def handle_aggregation_query(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> KnowledgeAnswer:
        """Handle aggregation queries (who most, what most, how many).

        Retrieves memories, counts/aggregates entities, ranks results, and
        formats answer with statistics. Calculates confidence based on sample
        size and distribution.

        Time Complexity: O(n) for counting and aggregation
        Latency Budget: <100ms

        Args:
            query: Aggregation KnowledgeQuery
            memories: Retrieved memories
            statistics: Pre-computed statistics with entity counts

        Returns:
            KnowledgeAnswer with aggregation summary and confidence

        Example:
            >>> answer = synthesizer.handle_aggregation_query(query, memories, stats)
            >>> print(f"Most frequent: {answer.summary}")
        """
        # Generate aggregation summary
        summary = self._generate_aggregation_summary(query, memories, statistics)

        # Calculate confidence for aggregation queries
        confidence = self._calculate_aggregation_confidence(query, memories, statistics)

        # Add confidence indicator if below threshold
        if confidence < self.confidence_threshold:
            summary = f"I'm not very confident, but {summary.lower()}"

        # Extract supporting memory IDs (top 5 by relevance)
        supporting_memories = [str(m.memory_id) for m in memories[:5]]

        return KnowledgeAnswer(
            summary=summary,
            confidence=confidence,
            supporting_memories=supporting_memories,
            patterns=[],
            statistics=statistics,
        )

    def handle_pattern_query(
        self,
        query: KnowledgeQuery,
        memories: list[Memory],
        patterns: list[Pattern],
        statistics: dict[str, Any],
    ) -> KnowledgeAnswer:
        """Handle pattern queries (usually, typically, routine).

        Retrieves memories by time pattern, detects routines (daily, weekly,
        monthly), and formats patterns with frequency and examples. Calculates
        confidence based on pattern strength and consistency.

        Time Complexity: O(n log n) for pattern detection
        Latency Budget: <200ms

        Args:
            query: Pattern KnowledgeQuery
            memories: Retrieved memories
            patterns: Detected patterns (daily, weekly, monthly)
            statistics: Pre-computed statistics

        Returns:
            KnowledgeAnswer with pattern summary and confidence

        Example:
            >>> answer = synthesizer.handle_pattern_query(query, memories, patterns, stats)
            >>> print(f"Pattern: {answer.summary}")
        """
        # Generate pattern summary
        summary = self._generate_pattern_summary(query, patterns, statistics)

        # Calculate confidence for pattern queries
        confidence = self._calculate_pattern_confidence(query, memories, patterns, statistics)

        # Add confidence indicator if below threshold
        if confidence < self.confidence_threshold:
            summary = f"I'm not very confident, but {summary.lower()}"

        # Extract supporting memory IDs (examples from strongest pattern)
        supporting_memories = []
        if patterns:
            # Get examples from strongest pattern
            strongest_pattern = max(patterns, key=lambda p: p.frequency)
            # Find memories matching pattern examples
            for memory in memories:
                timestamp_str = memory.timestamp.strftime("%Y-%m-%d %H:%M")
                if timestamp_str in strongest_pattern.examples:
                    supporting_memories.append(str(memory.memory_id))
                    if len(supporting_memories) >= 5:
                        break

        return KnowledgeAnswer(
            summary=summary,
            confidence=confidence,
            supporting_memories=supporting_memories,
            patterns=patterns,
            statistics=statistics,
        )

    def handle_factual_query(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> KnowledgeAnswer:
        """Handle factual queries (what is, who is, where is).

        Retrieves semantic memories (facts), synthesizes answer from most
        relevant memory, and includes source information. Calculates confidence
        based on memory relevance and source reliability.

        Time Complexity: O(1) for retrieval (already sorted by relevance)
        Latency Budget: <50ms

        Args:
            query: Factual KnowledgeQuery
            memories: Retrieved semantic memories (sorted by relevance)
            statistics: Pre-computed statistics

        Returns:
            KnowledgeAnswer with factual summary and confidence

        Example:
            >>> answer = synthesizer.handle_factual_query(query, memories, stats)
            >>> print(f"Fact: {answer.summary}")
        """
        # Generate factual summary
        summary = self._generate_factual_summary(query, memories, statistics)

        # Calculate confidence for factual queries
        confidence = self._calculate_factual_confidence(query, memories, statistics)

        # Add confidence indicator if below threshold
        if confidence < self.confidence_threshold:
            summary = f"I'm not very confident, but {summary.lower()}"

        # Extract supporting memory IDs (top 3 most relevant)
        supporting_memories = [str(m.memory_id) for m in memories[:3]]

        return KnowledgeAnswer(
            summary=summary,
            confidence=confidence,
            supporting_memories=supporting_memories,
            patterns=[],
            statistics=statistics,
        )

    def _detect_daily_pattern(self, memories: list[Memory]) -> Optional[Pattern]:
        """Detect daily patterns (same time of day).

        Args:
            memories: List of memories to analyze

        Returns:
            Pattern if detected, None otherwise
        """
        if len(memories) < 3:  # Need at least 3 occurrences
            return None

        # Group by hour of day
        hour_counts: Counter = Counter()
        for memory in memories:
            hour = memory.timestamp.hour
            hour_counts[hour] += 1

        # Find most common hour
        if not hour_counts:
            return None

        most_common_hour, count = hour_counts.most_common(1)[0]
        frequency = count / len(memories)

        if frequency < self.pattern_min_frequency:
            return None

        # Format time range
        time_str = f"{most_common_hour:02d}:00-{(most_common_hour + 1) % 24:02d}:00"

        # Get examples
        examples = [
            memory.timestamp.strftime("%Y-%m-%d %H:%M")
            for memory in memories
            if memory.timestamp.hour == most_common_hour
        ][:3]

        return Pattern(
            pattern_type="daily",
            description=f"This typically happens around {time_str}",
            frequency=frequency,
            confidence=min(0.95, frequency + 0.1),
            examples=examples,
        )

    def _detect_weekly_pattern(self, memories: list[Memory]) -> Optional[Pattern]:
        """Detect weekly patterns (same day of week).

        Args:
            memories: List of memories to analyze

        Returns:
            Pattern if detected, None otherwise
        """
        if len(memories) < 3:  # Need at least 3 occurrences
            return None

        # Group by day of week
        day_counts: Counter = Counter()
        for memory in memories:
            day = memory.timestamp.strftime("%A")  # Monday, Tuesday, etc.
            day_counts[day] += 1

        # Find most common day
        if not day_counts:
            return None

        most_common_day, count = day_counts.most_common(1)[0]
        frequency = count / len(memories)

        if frequency < self.pattern_min_frequency:
            return None

        # Get examples
        examples = [
            memory.timestamp.strftime("%Y-%m-%d")
            for memory in memories
            if memory.timestamp.strftime("%A") == most_common_day
        ][:3]

        return Pattern(
            pattern_type="weekly",
            description=f"This typically happens on {most_common_day}s",
            frequency=frequency,
            confidence=min(0.95, frequency + 0.1),
            examples=examples,
        )

    def _detect_monthly_pattern(self, memories: list[Memory]) -> Optional[Pattern]:
        """Detect monthly patterns (same day of month).

        Args:
            memories: List of memories to analyze

        Returns:
            Pattern if detected, None otherwise
        """
        if len(memories) < 3:  # Need at least 3 occurrences
            return None

        # Group by day of month
        day_counts: Counter = Counter()
        for memory in memories:
            day = memory.timestamp.day
            day_counts[day] += 1

        # Find most common day
        if not day_counts:
            return None

        most_common_day, count = day_counts.most_common(1)[0]
        frequency = count / len(memories)

        if frequency < self.pattern_min_frequency:
            return None

        # Get examples
        examples = [
            memory.timestamp.strftime("%Y-%m-%d")
            for memory in memories
            if memory.timestamp.day == most_common_day
        ][:3]

        # Format day with ordinal suffix
        suffix = (
            "th"
            if 11 <= most_common_day <= 13
            else {1: "st", 2: "nd", 3: "rd"}.get(most_common_day % 10, "th")
        )

        return Pattern(
            pattern_type="monthly",
            description=f"This typically happens on the {most_common_day}{suffix} of the month",
            frequency=frequency,
            confidence=min(0.95, frequency + 0.1),
            examples=examples,
        )

    def _compute_aggregation_stats(
        self, memories: list[Memory], query: KnowledgeQuery
    ) -> dict[str, Any]:
        """Compute aggregation statistics for aggregation queries.

        Args:
            memories: List of memories to aggregate
            query: KnowledgeQuery for context

        Returns:
            Dictionary of aggregation statistics
        """
        stats: dict[str, Any] = {}

        # Extract entities from memory content
        entity_mentions: dict[str, int] = defaultdict(int)
        for memory in memories:
            # Simple entity extraction (can be improved with NER)
            words = memory.content.split()
            for word in words:
                if word[0].isupper() and len(word) > 2:  # Capitalized words
                    entity_mentions[word] += 1

        # Top entities
        if entity_mentions:
            top_entities = sorted(entity_mentions.items(), key=lambda x: x[1], reverse=True)[:5]
            stats["top_entities"] = [{"entity": e, "count": c} for e, c in top_entities]

        # Average frequency
        if memories and query.time_range:
            time_span_days = (query.time_range.end - query.time_range.start).days
            if time_span_days > 0:
                stats["average_per_day"] = len(memories) / time_span_days

        return stats

    def _calculate_confidence(
        self,
        query: KnowledgeQuery,
        memories: list[Memory],
        patterns: list[Pattern],
        statistics: dict[str, Any],
    ) -> float:
        """Calculate confidence score for the answer (legacy method).

        This method is kept for backward compatibility but is now superseded
        by specialized confidence calculation methods for each query type.

        Args:
            query: Original query
            memories: Retrieved memories
            patterns: Detected patterns
            statistics: Aggregated statistics

        Returns:
            Confidence score (0.0-1.0)
        """
        # Start with query confidence
        confidence = query.confidence

        # Boost confidence based on data quality
        if memories:
            # More memories = higher confidence (up to +0.2)
            memory_boost = min(0.2, len(memories) / 50.0)
            confidence = min(1.0, confidence + memory_boost)

        if patterns:
            # Patterns increase confidence (+0.1)
            confidence = min(1.0, confidence + 0.1)

        # Reduce confidence if insufficient data
        if len(memories) < 3:
            confidence *= 0.7

        return round(confidence, 2)

    def _calculate_temporal_confidence(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> float:
        """Calculate confidence for temporal queries.

        Confidence factors:
        - Query confidence (base)
        - Data recency (more recent = higher confidence)
        - Sample size (more memories = higher confidence)
        - Time range coverage (full coverage = higher confidence)

        Args:
            query: Temporal query
            memories: Retrieved memories
            statistics: Statistics with time range info

        Returns:
            Confidence score (0.0-1.0)
        """
        if not memories:
            return 0.1  # Very low confidence with no data

        # Start with query confidence
        confidence = query.confidence

        # Factor 1: Recency boost (more recent = higher confidence)
        most_recent = max(memories, key=lambda m: m.timestamp)
        days_ago = (datetime.now(tz=timezone.utc) - most_recent.timestamp).days
        if days_ago == 0:
            recency_boost = 0.15  # Today
        elif days_ago <= 7:
            recency_boost = 0.10  # This week
        elif days_ago <= 30:
            recency_boost = 0.05  # This month
        else:
            recency_boost = 0.0  # Older

        confidence = min(1.0, confidence + recency_boost)

        # Factor 2: Sample size boost (more memories = higher confidence)
        if len(memories) >= 5:
            confidence = min(1.0, confidence + 0.10)
        elif len(memories) >= 3:
            confidence = min(1.0, confidence + 0.05)
        else:
            # Penalize small sample size
            confidence *= 0.8

        # Factor 3: Time range coverage
        if query.time_range and len(memories) > 1:
            time_span_days = statistics.get("time_span_days", 0)
            requested_days = (query.time_range.end - query.time_range.start).days
            if requested_days > 0:
                coverage = min(1.0, time_span_days / requested_days)
                if coverage > 0.8:
                    confidence = min(1.0, confidence + 0.05)

        return round(confidence, 2)

    def _calculate_aggregation_confidence(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> float:
        """Calculate confidence for aggregation queries.

        Confidence factors:
        - Query confidence (base)
        - Sample size (larger sample = higher confidence)
        - Distribution clarity (clear winner = higher confidence)
        - Entity coverage (more entities = higher confidence)

        Args:
            query: Aggregation query
            memories: Retrieved memories
            statistics: Statistics with entity counts

        Returns:
            Confidence score (0.0-1.0)
        """
        if not memories:
            return 0.1  # Very low confidence with no data

        # Start with query confidence
        confidence = query.confidence

        # Factor 1: Sample size boost (statistical significance)
        sample_size = len(memories)
        if sample_size >= 20:
            confidence = min(1.0, confidence + 0.15)  # Large sample
        elif sample_size >= 10:
            confidence = min(1.0, confidence + 0.10)  # Medium sample
        elif sample_size >= 5:
            confidence = min(1.0, confidence + 0.05)  # Small sample
        else:
            # Penalize very small sample
            confidence *= 0.7

        # Factor 2: Distribution clarity (clear winner vs close race)
        top_entities = statistics.get("top_entities", [])
        if len(top_entities) >= 2:
            top_count = top_entities[0]["count"]
            second_count = top_entities[1]["count"]
            if top_count > second_count * 2:
                # Clear winner (2x more than runner-up)
                confidence = min(1.0, confidence + 0.10)
            elif top_count > second_count * 1.5:
                # Moderate winner
                confidence = min(1.0, confidence + 0.05)
            # Close race: no boost

        # Factor 3: Entity coverage
        if len(top_entities) >= 3:
            # Multiple entities tracked = more comprehensive data
            confidence = min(1.0, confidence + 0.05)

        return round(confidence, 2)

    def _calculate_pattern_confidence(
        self,
        query: KnowledgeQuery,
        memories: list[Memory],
        patterns: list[Pattern],
        statistics: dict[str, Any],
    ) -> float:
        """Calculate confidence for pattern queries.

        Confidence factors:
        - Query confidence (base)
        - Pattern strength (higher frequency = higher confidence)
        - Pattern consistency (multiple patterns = higher confidence)
        - Sample size (more occurrences = higher confidence)

        Args:
            query: Pattern query
            memories: Retrieved memories
            patterns: Detected patterns
            statistics: Statistics

        Returns:
            Confidence score (0.0-1.0)
        """
        if not patterns:
            return 0.2  # Low confidence with no patterns

        # Start with query confidence
        confidence = query.confidence

        # Factor 1: Pattern strength (frequency)
        strongest_pattern = max(patterns, key=lambda p: p.frequency)
        if strongest_pattern.frequency >= 0.7:
            confidence = min(1.0, confidence + 0.15)  # Very strong pattern
        elif strongest_pattern.frequency >= 0.5:
            confidence = min(1.0, confidence + 0.10)  # Strong pattern
        elif strongest_pattern.frequency >= 0.3:
            confidence = min(1.0, confidence + 0.05)  # Moderate pattern
        # Weak pattern: no boost

        # Factor 2: Pattern consistency (multiple patterns detected)
        if len(patterns) >= 2:
            # Multiple patterns reinforce each other
            confidence = min(1.0, confidence + 0.10)

        # Factor 3: Sample size (more occurrences = more reliable pattern)
        if len(memories) >= 10:
            confidence = min(1.0, confidence + 0.10)
        elif len(memories) >= 5:
            confidence = min(1.0, confidence + 0.05)
        else:
            # Penalize small sample for pattern detection
            confidence *= 0.8

        return round(confidence, 2)

    def _calculate_factual_confidence(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> float:
        """Calculate confidence for factual queries.

        Confidence factors:
        - Query confidence (base)
        - Memory relevance (higher relevance = higher confidence)
        - Source reliability (trusted source = higher confidence)
        - Corroboration (multiple sources = higher confidence)

        Args:
            query: Factual query
            memories: Retrieved semantic memories
            statistics: Statistics

        Returns:
            Confidence score (0.0-1.0)
        """
        if not memories:
            return 0.1  # Very low confidence with no data

        # Start with query confidence
        confidence = query.confidence

        # Factor 1: Memory relevance (first memory is most relevant)
        most_relevant = memories[0]
        if most_relevant.relevance_score >= 0.9:
            confidence = min(1.0, confidence + 0.15)  # Highly relevant
        elif most_relevant.relevance_score >= 0.7:
            confidence = min(1.0, confidence + 0.10)  # Relevant
        elif most_relevant.relevance_score >= 0.5:
            confidence = min(1.0, confidence + 0.05)  # Moderately relevant
        # Low relevance: no boost

        # Factor 2: Source reliability (if available)
        source = most_relevant.metadata.get("source")
        if source:
            # Trusted sources boost confidence
            trusted_sources = ["user_correction", "verified_fact", "official_source"]
            if source in trusted_sources:
                confidence = min(1.0, confidence + 0.10)

        # Factor 3: Corroboration (multiple sources agree)
        if len(memories) >= 3:
            # Multiple memories support the answer
            confidence = min(1.0, confidence + 0.10)
        elif len(memories) >= 2:
            confidence = min(1.0, confidence + 0.05)

        return round(confidence, 2)

    def _generate_temporal_summary(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> str:
        """Generate summary for temporal queries.

        Args:
            query: Original query
            memories: Retrieved memories
            statistics: Aggregated statistics

        Returns:
            Natural language summary
        """
        if not memories:
            return "I don't have any information about that in my memory."

        # Get most recent memory
        most_recent = max(memories, key=lambda m: m.timestamp)
        days_ago = (datetime.now(tz=timezone.utc) - most_recent.timestamp).days

        # Format time reference
        if days_ago == 0:
            time_ref = "today"
        elif days_ago == 1:
            time_ref = "yesterday"
        elif days_ago < 7:
            time_ref = f"{days_ago} days ago"
        elif days_ago < 30:
            weeks = days_ago // 7
            time_ref = f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            months = days_ago // 30
            time_ref = f"{months} month{'s' if months > 1 else ''} ago"

        # Extract action and entity from query
        action = query.entities.get("action", "did that")
        entity = (
            query.entities.get("person")
            or query.entities.get("app")
            or query.entities.get("location")
        )

        if entity:
            summary = f"You last {action} {entity} {time_ref}"
        else:
            summary = f"You last {action} {time_ref}"

        # Add frequency if multiple occurrences
        total_count = statistics.get("total_count", 0)
        if total_count > 1:
            summary += f" (total: {total_count} times"
            if query.time_range:
                summary += f" in {query.time_range.description}"
            summary += ")"

        return summary

    def _generate_aggregation_summary(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> str:
        """Generate summary for aggregation queries.

        Args:
            query: Original query
            memories: Retrieved memories
            statistics: Aggregated statistics

        Returns:
            Natural language summary
        """
        if not memories:
            return "I don't have enough data to answer that question."

        total_count = statistics.get("total_count", 0)

        # Check for top entities
        top_entities = statistics.get("top_entities", [])
        if top_entities:
            top_entity = top_entities[0]
            summary = f"Based on {total_count} records, {top_entity['entity']} appears most often ({top_entity['count']} times)"

            # Add runner-up if available
            if len(top_entities) > 1:
                runner_up = top_entities[1]
                summary += f", followed by {runner_up['entity']} ({runner_up['count']} times)"

            return summary

        # Fallback to count-based summary
        action = query.entities.get("action", "that")
        return f"You've done {action} {total_count} times"

    def _generate_pattern_summary(
        self, query: KnowledgeQuery, patterns: list[Pattern], statistics: dict[str, Any]
    ) -> str:
        """Generate summary for pattern queries.

        Args:
            query: Original query
            patterns: Detected patterns
            statistics: Aggregated statistics

        Returns:
            Natural language summary
        """
        if not patterns:
            return "I haven't detected any clear patterns for that behavior yet."

        # Use the strongest pattern (highest frequency)
        strongest_pattern = max(patterns, key=lambda p: p.frequency)

        summary = strongest_pattern.description

        # Add frequency information
        frequency_pct = int(strongest_pattern.frequency * 100)
        summary += f" (about {frequency_pct}% of the time)"

        # Add additional patterns if available
        if len(patterns) > 1:
            other_patterns = [p for p in patterns if p != strongest_pattern]
            summary += f". I also noticed {len(other_patterns)} other pattern{'s' if len(other_patterns) > 1 else ''}"

        return summary

    def _generate_factual_summary(
        self, query: KnowledgeQuery, memories: list[Memory], statistics: dict[str, Any]
    ) -> str:
        """Generate summary for factual queries.

        Args:
            query: Original query
            memories: Retrieved memories
            statistics: Aggregated statistics

        Returns:
            Natural language summary
        """
        if not memories:
            return "I don't have that information in my memory."

        # Use the most relevant memory (first in list)
        most_relevant = memories[0]

        # Extract the answer from memory content
        summary = most_relevant.content

        # Add source information if available
        if hasattr(most_relevant, "source") and most_relevant.metadata.get("source"):
            summary += f" (Source: {most_relevant.metadata['source']})"

        return summary

    def _initialize_llm_client(self) -> None:
        """Initialize LLM client based on provider.

        Raises:
            RuntimeError: If LLM client not available
        """
        if self.llm_provider == "openai":
            if not OPENAI_AVAILABLE:
                raise RuntimeError("OpenAI client not available. Install with: pip install openai")
            self.llm_client = openai.OpenAI(api_key=self.llm_api_key)
        elif self.llm_provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise RuntimeError(
                    "Anthropic client not available. Install with: pip install anthropic"
                )
            self.llm_client = anthropic.Anthropic(api_key=self.llm_api_key)
        else:
            raise ValueError(
                f"Unsupported LLM provider: {self.llm_provider}. Supported: openai, anthropic"
            )

    async def synthesize_answer_with_llm(
        self,
        query: KnowledgeQuery,
        memories: list[Memory],
        patterns: list[Pattern],
        statistics: dict[str, Any],
    ) -> KnowledgeAnswer:
        """Synthesize answer using LLM for natural language generation.

        Time Complexity: O(1) per LLM call
        Latency Budget: <1.0s (target)

        This method uses LLM to generate natural language answers from structured
        data (memories, patterns, statistics). It includes retry logic for malformed
        responses and confidence scoring.

        Args:
            query: Original KnowledgeQuery
            memories: Retrieved memories
            patterns: Detected patterns
            statistics: Aggregated statistics

        Returns:
            KnowledgeAnswer with LLM-generated summary

        Example:
            >>> synthesizer = KnowledgeSynthesizer(memory_retriever)
            >>> answer = await synthesizer.synthesize_answer_with_llm(
            ...     query, memories, patterns, stats
            ... )
            >>> print(answer.summary)
        """
        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(query, memories, patterns, statistics)

        # Call LLM with retry logic
        for attempt in range(self.llm_max_retries):
            try:
                # Call LLM with timeout
                llm_response = await asyncio.wait_for(
                    self._call_llm_for_synthesis(prompt),
                    timeout=self.llm_timeout_ms / 1000.0,
                )

                # Parse LLM response
                parsed_response = self._parse_llm_synthesis_response(llm_response)

                # Create KnowledgeAnswer from LLM response
                return self._create_answer_from_llm_response(
                    parsed_response, query, memories, patterns, statistics
                )

            except asyncio.TimeoutError:
                if attempt == self.llm_max_retries - 1:
                    # Final attempt failed, fall back to template-based generation
                    return self.generate_answer(query, memories, patterns, statistics)
                # Exponential backoff
                await asyncio.sleep(0.1 * (2**attempt))

            except (ValidationError, json.JSONDecodeError, KeyError):
                if attempt == self.llm_max_retries - 1:
                    # Final attempt failed, fall back to template-based generation
                    return self.generate_answer(query, memories, patterns, statistics)
                # Exponential backoff
                await asyncio.sleep(0.1 * (2**attempt))

            except Exception:
                if attempt == self.llm_max_retries - 1:
                    # Final attempt failed, fall back to template-based generation
                    return self.generate_answer(query, memories, patterns, statistics)
                # Exponential backoff
                await asyncio.sleep(0.1 * (2**attempt))

        # Should never reach here, but fall back to template-based generation
        return self.generate_answer(query, memories, patterns, statistics)

    def _build_synthesis_prompt(
        self,
        query: KnowledgeQuery,
        memories: list[Memory],
        patterns: list[Pattern],
        statistics: dict[str, Any],
    ) -> str:
        """Build synthesis prompt for LLM.

        Args:
            query: Original query
            memories: Retrieved memories
            patterns: Detected patterns
            statistics: Aggregated statistics

        Returns:
            Formatted prompt string
        """
        # System prompt
        system_prompt = """You are an expert knowledge synthesizer for a personal AI assistant.
Your task is to synthesize natural language answers from structured data including:
- Retrieved memories (personal experiences, facts, preferences)
- Detected patterns (behavioral routines, habits)
- Statistical aggregations (counts, frequencies, rankings)

Generate concise, natural, conversational answers that:
1. Directly answer the user's question
2. Include relevant supporting details
3. Mention patterns or trends when significant
4. Use appropriate temporal language (today, yesterday, last week, etc.)
5. Express uncertainty when confidence is low

Output format (JSON):
{
  "summary": "Natural language answer",
  "confidence": 0.85,
  "reasoning": "Brief explanation of synthesis",
  "key_insights": ["insight 1", "insight 2"]
}"""

        # Build data context
        data_context = {
            "query": {
                "text": query.query_text,
                "type": query.query_type.value,
                "entities": query.entities,
                "time_range": (
                    {
                        "start": query.time_range.start.isoformat(),
                        "end": query.time_range.end.isoformat(),
                        "description": query.time_range.description,
                    }
                    if query.time_range
                    else None
                ),
            },
            "memories": [
                {
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "type": m.memory_type.value
                    if hasattr(m.memory_type, "value")
                    else m.memory_type,
                    "relevance": m.relevance_score,
                }
                for m in memories[:10]  # Limit to top 10 for prompt size
            ],
            "patterns": [
                {
                    "type": p.pattern_type,
                    "description": p.description,
                    "frequency": p.frequency,
                    "examples": p.examples[:3],  # Limit examples
                }
                for p in patterns
            ],
            "statistics": statistics,
        }

        # Build user prompt
        user_prompt = f"""Synthesize an answer to the user's query using the provided data.

Query: "{query.query_text}"
Query Type: {query.query_type.value}

Data:
{json.dumps(data_context, indent=2)}

Generate a natural language answer that directly addresses the query."""

        return f"{system_prompt}\n\n{user_prompt}"

    async def _call_llm_for_synthesis(self, prompt: str) -> str:
        """Call LLM API for answer synthesis.

        Args:
            prompt: Synthesis prompt

        Returns:
            LLM response text

        Raises:
            RuntimeError: If LLM call fails
        """
        if self.llm_provider == "openai":
            return await self._call_openai_synthesis(prompt)
        elif self.llm_provider == "anthropic":
            return await self._call_anthropic_synthesis(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    async def _call_openai_synthesis(self, prompt: str) -> str:
        """Call OpenAI API for synthesis.

        Args:
            prompt: Synthesis prompt

        Returns:
            LLM response text
        """
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Low temperature for factual synthesis
                max_tokens=512,
                response_format={"type": "json_object"},
            ),
        )
        return str(response.choices[0].message.content) if response and response.choices else ""[0].message.content

    async def _call_anthropic_synthesis(self, prompt: str) -> str:
        """Call Anthropic API for synthesis.

        Args:
            prompt: Synthesis prompt

        Returns:
            LLM response text
        """
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.llm_client.messages.create(
                model=self.llm_model,
                max_tokens=512,
                temperature=0.3,  # Low temperature for factual synthesis
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return str(response.content[0].text) if response and response.content else ""[0].text

    def _parse_llm_synthesis_response(self, response_text: str) -> LLMSynthesisResponse:
        """Parse and validate LLM synthesis response.

        Args:
            response_text: Raw LLM response

        Returns:
            Validated response object

        Raises:
            ValidationError: If response doesn't match schema
            json.JSONDecodeError: If response is not valid JSON
        """
        # Parse JSON
        response_data = json.loads(response_text)

        # Validate with Pydantic
        return LLMSynthesisResponse(**response_data)

    def _create_answer_from_llm_response(
        self,
        llm_response: LLMSynthesisResponse,
        query: KnowledgeQuery,
        memories: list[Memory],
        patterns: list[Pattern],
        statistics: dict[str, Any],
    ) -> KnowledgeAnswer:
        """Create KnowledgeAnswer from LLM response.

        Args:
            llm_response: Parsed LLM response
            query: Original query
            memories: Retrieved memories
            patterns: Detected patterns
            statistics: Aggregated statistics

        Returns:
            KnowledgeAnswer with LLM-generated summary
        """
        # Extract supporting memory IDs (top 5 most relevant)
        supporting_memories = [str(m.memory_id) for m in memories[:5]]

        # Use LLM confidence, but adjust based on data quality
        confidence = llm_response.confidence

        # Adjust confidence based on data availability
        if not memories:
            confidence *= 0.5  # Reduce confidence if no supporting data
        elif len(memories) < 3:
            confidence *= 0.8  # Reduce confidence for small sample

        # Ensure confidence is within bounds
        confidence = max(0.0, min(1.0, confidence))

        # Add confidence indicator if below threshold
        summary = llm_response.summary
        if confidence < self.confidence_threshold:
            summary = f"I'm not very confident, but {summary.lower()}"

        return KnowledgeAnswer(
            summary=summary,
            confidence=round(confidence, 2),
            supporting_memories=supporting_memories,
            patterns=patterns,
            statistics=statistics,
        )
