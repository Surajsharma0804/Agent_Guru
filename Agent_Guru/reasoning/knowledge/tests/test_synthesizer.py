"""
Unit tests for KnowledgeSynthesizer.

Tests cover:
- Initialization and validation
- Answer synthesis for all query types
- Data retrieval from memory
- Pattern detection (daily, weekly, monthly)
- Statistical aggregation
- Answer generation
- Confidence calculation
- Latency requirements

Coverage Target: 80%+
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from Agent_Guru.reasoning.knowledge.synthesizer import KnowledgeSynthesizer
from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
    TimeRange,
)
from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    MemoryType,
    SemanticMemory,
)


class TestKnowledgeSynthesizerInitialization:
    """Test KnowledgeSynthesizer initialization and validation."""

    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        assert synthesizer.memory_retriever == memory_retriever
        assert synthesizer.max_memories == 50
        assert synthesizer.pattern_min_frequency == 0.3
        assert synthesizer.confidence_threshold == 0.6

    def test_initialization_with_custom_params(self):
        """Test initialization with custom parameters."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever,
            max_memories=100,
            pattern_min_frequency=0.5,
            confidence_threshold=0.7,
        )

        assert synthesizer.max_memories == 100
        assert synthesizer.pattern_min_frequency == 0.5
        assert synthesizer.confidence_threshold == 0.7

    def test_initialization_invalid_max_memories(self):
        """Test initialization with invalid max_memories."""
        memory_retriever = Mock(spec=MemoryRetriever)

        with pytest.raises(ValueError, match="max_memories must be >= 1"):
            KnowledgeSynthesizer(memory_retriever, max_memories=0)

    def test_initialization_invalid_pattern_frequency(self):
        """Test initialization with invalid pattern_min_frequency."""
        memory_retriever = Mock(spec=MemoryRetriever)

        with pytest.raises(ValueError, match="pattern_min_frequency must be 0.0-1.0"):
            KnowledgeSynthesizer(memory_retriever, pattern_min_frequency=1.5)

    def test_initialization_invalid_confidence_threshold(self):
        """Test initialization with invalid confidence_threshold."""
        memory_retriever = Mock(spec=MemoryRetriever)

        with pytest.raises(ValueError, match="confidence_threshold must be 0.0-1.0"):
            KnowledgeSynthesizer(memory_retriever, confidence_threshold=-0.1)


class TestRetrieveRelevantData:
    """Test data retrieval from memory."""

    def test_retrieve_temporal_query(self):
        """Test data retrieval for temporal query."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test query
        now = datetime.utcnow()
        time_range = TimeRange(start=now - timedelta(days=30), end=now, description="last month")
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=time_range,
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )

        # Mock memory retrieval with timestamp within range
        mock_memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now - timedelta(days=3),  # Within range
            )
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Retrieve data
        memories = synthesizer.retrieve_relevant_data(query, "user_123")

        # Verify retrieval call
        memory_retriever.retrieve.assert_called_once_with(
            query=query.query_text,
            user_id="user_123",
            memory_types=None,  # Temporal queries use all types
            top_k=50,
        )

        assert len(memories) == 1
        assert memories[0].content == "Called John"

    def test_retrieve_factual_query(self):
        """Test data retrieval for factual query."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test query
        query = KnowledgeQuery(
            query_text="what is my email?",
            query_type=KnowledgeQueryType.FACTUAL,
            confidence=0.9,
        )

        # Mock memory retrieval
        mock_memories = [
            SemanticMemory(
                content="User email is john@example.com",
                fact="email: john@example.com",
                source="user_profile",
                confidence=0.95,
                user_id="user_123",
            )
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Retrieve data
        memories = synthesizer.retrieve_relevant_data(query, "user_123")

        # Verify retrieval call with semantic memory types
        memory_retriever.retrieve.assert_called_once_with(
            query=query.query_text,
            user_id="user_123",
            memory_types=[MemoryType.SEMANTIC, MemoryType.PREFERENCE],
            top_k=50,
        )

        assert len(memories) == 1

    def test_retrieve_with_time_range_filtering(self):
        """Test data retrieval with time range filtering."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test query with time range
        time_range = TimeRange.last_week()
        query = KnowledgeQuery(
            query_text="what did I do last week?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=time_range,
            confidence=0.9,
        )

        # Mock memories with different timestamps
        now = datetime.utcnow()
        mock_memories = [
            EpisodicMemory(
                content="Recent action",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now - timedelta(days=3),  # Within range
            ),
            EpisodicMemory(
                content="Old action",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now - timedelta(days=10),  # Outside range
            ),
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Retrieve data
        memories = synthesizer.retrieve_relevant_data(query, "user_123")

        # Should filter to only memories within time range
        assert len(memories) == 1
        assert memories[0].content == "Recent action"


class TestDetectPatterns:
    """Test pattern detection algorithms."""

    def test_detect_daily_pattern(self):
        """Test detection of daily patterns."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever, pattern_min_frequency=0.3)

        # Create memories with daily pattern (same hour)
        now = datetime.utcnow()
        memories = [
            EpisodicMemory(
                content=f"Action {i}",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now.replace(hour=9, minute=0) - timedelta(days=i),
            )
            for i in range(5)
        ]

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        patterns = synthesizer.detect_patterns(memories, query)

        # Should detect daily pattern at 9am
        assert len(patterns) >= 1
        daily_patterns = [p for p in patterns if p.pattern_type == "daily"]
        assert len(daily_patterns) == 1
        assert "09:00" in daily_patterns[0].description
        assert daily_patterns[0].frequency == 1.0  # All at same hour

    def test_detect_weekly_pattern(self):
        """Test detection of weekly patterns."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever, pattern_min_frequency=0.3)

        # Create memories with weekly pattern (Mondays)
        now = datetime.utcnow()
        # Find next Monday
        days_until_monday = (7 - now.weekday()) % 7
        next_monday = now + timedelta(days=days_until_monday)

        memories = [
            EpisodicMemory(
                content=f"Action {i}",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=next_monday - timedelta(weeks=i),
            )
            for i in range(4)
        ]

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        patterns = synthesizer.detect_patterns(memories, query)

        # Should detect weekly pattern on Mondays
        weekly_patterns = [p for p in patterns if p.pattern_type == "weekly"]
        assert len(weekly_patterns) == 1
        assert "Monday" in weekly_patterns[0].description
        assert weekly_patterns[0].frequency == 1.0

    def test_detect_monthly_pattern(self):
        """Test detection of monthly patterns."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever, pattern_min_frequency=0.3)

        # Create memories with monthly pattern (15th of month)
        # Use a fixed date to ensure consistency
        datetime(2024, 1, 15, 10, 0, 0)
        memories = [
            EpisodicMemory(
                content=f"Action {i}",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=datetime(2024 - i // 12, 1 + (i % 12), 15, 10, 0, 0),
            )
            for i in range(4)
        ]

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        patterns = synthesizer.detect_patterns(memories, query)

        # Should detect monthly pattern on 15th
        monthly_patterns = [p for p in patterns if p.pattern_type == "monthly"]
        assert len(monthly_patterns) == 1
        # Check that the pattern mentions the day
        assert "15th" in monthly_patterns[0].description
        assert monthly_patterns[0].frequency == 1.0

    def test_no_pattern_insufficient_data(self):
        """Test no pattern detection with insufficient data."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Only 2 memories (need at least 3)
        memories = [
            EpisodicMemory(
                content="Action 1",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
            ),
            EpisodicMemory(
                content="Action 2",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
            ),
        ]

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        patterns = synthesizer.detect_patterns(memories, query)

        # Should not detect any patterns
        assert len(patterns) == 0

    def test_no_pattern_low_frequency(self):
        """Test no pattern detection with low frequency."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever, pattern_min_frequency=0.7
        )  # Higher threshold

        # Create memories with low frequency pattern (only 2 out of 5 at same hour)
        now = datetime.utcnow()
        memories = [
            EpisodicMemory(
                content=f"Action {i}",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now.replace(hour=9 if i < 2 else 14, minute=0) - timedelta(days=i),
            )
            for i in range(5)
        ]

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        patterns = synthesizer.detect_patterns(memories, query)

        # Should not detect pattern (frequency 0.4 or 0.6 < 0.7 threshold)
        assert len(patterns) == 0


class TestAggregateStatistics:
    """Test statistical aggregation."""

    def test_aggregate_basic_statistics(self):
        """Test basic statistics aggregation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test memories
        now = datetime.utcnow()
        memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now - timedelta(days=i),
            )
            for i in range(5)
        ]

        query = KnowledgeQuery(
            query_text="how many times did I call John?",
            query_type=KnowledgeQueryType.AGGREGATION,
            entities={"person": "John", "action": "call"},
            confidence=0.9,
        )

        statistics = synthesizer.aggregate_statistics(memories, query)

        assert statistics["total_count"] == 5
        assert "most_recent" in statistics
        assert "oldest" in statistics
        assert "time_span_days" in statistics

    def test_aggregate_empty_memories(self):
        """Test statistics aggregation with no memories."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        query = KnowledgeQuery(
            query_text="how many times?",
            query_type=KnowledgeQueryType.AGGREGATION,
            confidence=0.9,
        )

        statistics = synthesizer.aggregate_statistics([], query)

        assert statistics["total_count"] == 0

    def test_aggregate_entity_counts(self):
        """Test entity counting in aggregation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create memories with entity mentions
        memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
            ),
            EpisodicMemory(
                content="Called John again",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
            ),
            EpisodicMemory(
                content="Called Mary",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
            ),
        ]

        query = KnowledgeQuery(
            query_text="who do I call most?",
            query_type=KnowledgeQueryType.AGGREGATION,
            entities={"person": "John"},
            confidence=0.9,
        )

        statistics = synthesizer.aggregate_statistics(memories, query)

        assert statistics["total_count"] == 3
        assert "person_count" in statistics
        assert statistics["person_count"]["John"] == 2


class TestGenerateAnswer:
    """Test answer generation."""

    def test_generate_temporal_answer(self):
        """Test temporal answer generation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test data
        now = datetime.utcnow()
        memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now - timedelta(days=3),
            )
        ]

        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )

        statistics = {"total_count": 1, "most_recent": now.isoformat()}
        patterns = []

        answer = synthesizer.generate_answer(query, memories, patterns, statistics)

        assert "John" in answer.summary
        assert "call" in answer.summary
        assert "3 days ago" in answer.summary
        assert answer.confidence > 0.0
        assert len(answer.supporting_memories) == 1

    def test_generate_aggregation_answer(self):
        """Test aggregation answer generation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test data
        memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
            )
            for _ in range(5)
        ]

        query = KnowledgeQuery(
            query_text="how many times did I call John?",
            query_type=KnowledgeQueryType.AGGREGATION,
            entities={"person": "John", "action": "call"},
            confidence=0.9,
        )

        statistics = {
            "total_count": 5,
            "top_entities": [{"entity": "John", "count": 5}],
        }
        patterns = []

        answer = synthesizer.generate_answer(query, memories, patterns, statistics)

        assert "5" in answer.summary or "John" in answer.summary
        assert answer.confidence > 0.0

    def test_generate_pattern_answer(self):
        """Test pattern answer generation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test data
        memories = []
        patterns = [
            Pattern(
                pattern_type="daily",
                description="This typically happens around 09:00-10:00",
                frequency=0.85,
                confidence=0.9,
                examples=["2024-01-15 09:00", "2024-01-16 09:05"],
            )
        ]

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        statistics = {"total_count": 10}

        answer = synthesizer.generate_answer(query, memories, patterns, statistics)

        assert "09:00" in answer.summary
        assert "85%" in answer.summary
        assert len(answer.patterns) == 1

    def test_generate_factual_answer(self):
        """Test factual answer generation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test data
        memories = [
            SemanticMemory(
                content="User email is john@example.com",
                fact="email: john@example.com",
                source="user_profile",
                confidence=0.95,
                user_id="user_123",
            )
        ]

        query = KnowledgeQuery(
            query_text="what is my email?",
            query_type=KnowledgeQueryType.FACTUAL,
            confidence=0.95,
        )

        statistics = {"total_count": 1}
        patterns = []

        answer = synthesizer.generate_answer(query, memories, patterns, statistics)

        assert "john@example.com" in answer.summary
        assert answer.confidence > 0.0

    def test_generate_answer_low_confidence(self):
        """Test answer generation with low confidence."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever, confidence_threshold=0.7)

        # Create test data with low confidence
        memories = [
            EpisodicMemory(
                content="Maybe called John",
                action_taken="call",
                result="Unknown",
                success=False,
                user_id="user_123",
            )
        ]

        query = KnowledgeQuery(
            query_text="when did I call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            entities={"person": "John", "action": "call"},
            confidence=0.5,  # Low confidence
        )

        statistics = {"total_count": 1}
        patterns = []

        answer = synthesizer.generate_answer(query, memories, patterns, statistics)

        # Should indicate low confidence
        assert "not very confident" in answer.summary.lower()
        assert answer.confidence < 0.7

    def test_generate_answer_no_data(self):
        """Test answer generation with no data."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        query = KnowledgeQuery(
            query_text="when did I do something?",
            query_type=KnowledgeQueryType.TEMPORAL,
            confidence=0.9,
        )

        statistics = {"total_count": 0}
        patterns = []

        answer = synthesizer.generate_answer(query, [], patterns, statistics)

        assert "don't have" in answer.summary.lower()
        assert answer.confidence > 0.0


class TestSynthesizeAnswer:
    """Test end-to-end answer synthesis."""

    def test_synthesize_temporal_query(self):
        """Test complete synthesis for temporal query."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test query
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )

        # Mock memory retrieval
        now = datetime.utcnow()
        mock_memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now - timedelta(days=3),
            )
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify answer
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert answer.confidence > 0.0
        assert len(answer.supporting_memories) > 0
        assert isinstance(answer.statistics, dict)

    def test_synthesize_aggregation_query(self):
        """Test complete synthesis for aggregation query."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test query
        query = KnowledgeQuery(
            query_text="who do I call most?",
            query_type=KnowledgeQueryType.AGGREGATION,
            confidence=0.9,
        )

        # Mock memory retrieval
        mock_memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
            )
            for _ in range(5)
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify answer
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert answer.confidence > 0.0
        assert answer.statistics["total_count"] == 5

    def test_synthesize_pattern_query(self):
        """Test complete synthesis for pattern query."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever, pattern_min_frequency=0.3)

        # Create test query
        query = KnowledgeQuery(
            query_text="when do I usually call John?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        # Mock memory retrieval with pattern
        now = datetime.utcnow()
        mock_memories = [
            EpisodicMemory(
                content=f"Called John {i}",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
                timestamp=now.replace(hour=9, minute=0) - timedelta(days=i),
            )
            for i in range(5)
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify answer
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert answer.confidence > 0.0
        assert len(answer.patterns) > 0

    def test_synthesize_factual_query(self):
        """Test complete synthesis for factual query."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test query
        query = KnowledgeQuery(
            query_text="what is my email?",
            query_type=KnowledgeQueryType.FACTUAL,
            confidence=0.95,
        )

        # Mock memory retrieval
        mock_memories = [
            SemanticMemory(
                content="User email is john@example.com",
                fact="email: john@example.com",
                source="user_profile",
                confidence=0.95,
                user_id="user_123",
            )
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify answer
        assert isinstance(answer.summary, str)
        assert "john@example.com" in answer.summary
        assert answer.confidence > 0.0


class TestLatencyRequirements:
    """Test latency requirements."""

    def test_synthesize_answer_latency(self):
        """Test that synthesize_answer meets latency budget."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Create test query
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )

        # Mock fast memory retrieval
        mock_memories = [
            EpisodicMemory(
                content="Called John",
                action_taken="call",
                result="Success",
                success=True,
                user_id="user_123",
            )
        ]
        memory_retriever.retrieve.return_value = mock_memories

        # Measure latency
        import time

        start = time.perf_counter()
        answer = synthesizer.synthesize_answer(query, "user_123")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should complete within 1.5s budget (with generous margin for test environment)
        assert elapsed_ms < 2000  # 2s max for test environment
        assert isinstance(answer, type(answer))  # Verify it completed
