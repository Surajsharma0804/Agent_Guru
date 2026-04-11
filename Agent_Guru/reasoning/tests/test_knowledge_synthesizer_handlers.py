"""
Unit tests for Knowledge Synthesizer query type handlers.

Tests the specialized handler methods for temporal, aggregation, pattern,
and factual queries with confidence scoring.

Coverage Target: 80%+
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from Agent_Guru.reasoning.knowledge.synthesizer import KnowledgeSynthesizer
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeAnswer,
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
    TimeRange,
)
from Agent_Guru.reasoning.models.memory import Memory, MemoryType


@pytest.fixture
def mock_memory_retriever():
    """Create mock MemoryRetriever."""
    return Mock()


@pytest.fixture
def synthesizer(mock_memory_retriever):
    """Create KnowledgeSynthesizer instance."""
    return KnowledgeSynthesizer(
        memory_retriever=mock_memory_retriever,
        max_memories=50,
        pattern_min_frequency=0.3,
        confidence_threshold=0.6,
        use_llm_synthesis=False,  # Disable LLM to avoid API key requirement
    )


@pytest.fixture
def sample_memories():
    """Create sample memories for testing."""
    now = datetime.utcnow()
    memories = []

    # Create memories with different timestamps
    for i in range(10):
        memory = Memory(
            memory_id=uuid.uuid4(),
            memory_type=MemoryType.EPISODIC,
            content=f"Called John on {(now - timedelta(days=i)).strftime('%Y-%m-%d')}",
            embedding=[0.1] * 768,  # 768-dimensional embedding
            metadata={"action": "call", "person": "John"},
            relevance_score=0.9 - (i * 0.05),
            timestamp=now - timedelta(days=i),
            user_id="user_123",
        )
        memories.append(memory)

    return memories


class TestHandleTemporalQuery:
    """Tests for handle_temporal_query method."""

    def test_handle_temporal_query_with_recent_memory(self, synthesizer, sample_memories):
        """Test temporal query with recent memory."""
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"action": "call", "person": "John"},
            confidence=0.8,
        )

        statistics = {
            "total_count": len(sample_memories),
            "most_recent": sample_memories[0].timestamp.isoformat(),
            "oldest": sample_memories[-1].timestamp.isoformat(),
            "time_span_days": 9,
        }

        answer = synthesizer.handle_temporal_query(query, sample_memories, statistics)

        assert isinstance(answer, KnowledgeAnswer)
        assert answer.confidence > 0.8  # Should boost confidence for recent data
        assert "John" in answer.summary
        assert len(answer.supporting_memories) <= 5
        assert answer.patterns == []  # Temporal queries don't include patterns

    def test_handle_temporal_query_with_old_memory(self, synthesizer):
        """Test temporal query with old memory."""
        now = datetime.utcnow()
        old_memory = Memory(
            memory_id=uuid.uuid4(),
            memory_type=MemoryType.EPISODIC,
            content="Called John 6 months ago",
            embedding=[0.1] * 768,
            metadata={"action": "call", "person": "John"},
            relevance_score=0.7,
            timestamp=now - timedelta(days=180),
            user_id="user_123",
        )

        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_year(),
            entities={"action": "call", "person": "John"},
            confidence=0.8,
        )

        statistics = {
            "total_count": 1,
            "most_recent": old_memory.timestamp.isoformat(),
            "oldest": old_memory.timestamp.isoformat(),
            "time_span_days": 0,
        }

        answer = synthesizer.handle_temporal_query(query, [old_memory], statistics)

        assert isinstance(answer, KnowledgeAnswer)
        # Old data should not boost confidence as much
        assert answer.confidence <= 0.9
        assert "month" in answer.summary.lower()

    def test_handle_temporal_query_no_memories(self, synthesizer):
        """Test temporal query with no memories."""
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"action": "call", "person": "John"},
            confidence=0.8,
        )

        statistics = {"total_count": 0}

        answer = synthesizer.handle_temporal_query(query, [], statistics)

        assert isinstance(answer, KnowledgeAnswer)
        assert answer.confidence == 0.1  # Very low confidence
        assert "don't have" in answer.summary.lower()
        assert len(answer.supporting_memories) == 0

    def test_handle_temporal_query_low_confidence_indicator(self, synthesizer):
        """Test that low confidence adds indicator to summary."""
        now = datetime.utcnow()
        memory = Memory(
            memory_id=uuid.uuid4(),
            memory_type=MemoryType.EPISODIC,
            content="Called John",
            embedding=[0.1] * 768,
            metadata={},
            relevance_score=0.5,
            timestamp=now - timedelta(days=100),
            user_id="user_123",
        )

        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=None,
            entities={"action": "call", "person": "John"},
            confidence=0.4,  # Low initial confidence
        )

        statistics = {"total_count": 1}

        answer = synthesizer.handle_temporal_query(query, [memory], statistics)

        # Low confidence should add indicator
        assert "not very confident" in answer.summary.lower()


class TestHandleAggregationQuery:
    """Tests for handle_aggregation_query method."""

    def test_handle_aggregation_query_with_clear_winner(self, synthesizer):
        """Test aggregation query with clear winner."""
        memories = []
        now = datetime.utcnow()

        # Create memories with different entities
        for i in range(20):
            person = "John" if i < 15 else "Jane"  # John appears 15 times, Jane 5 times
            memory = Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content=f"Called {person}",
                embedding=[0.1] * 768,
                metadata={"person": person},
                relevance_score=0.8,
                timestamp=now - timedelta(days=i),
                user_id="user_123",
            )
            memories.append(memory)

        query = KnowledgeQuery(
            query_text="who do I call most often?",
            query_type=KnowledgeQueryType.AGGREGATION,
            time_range=TimeRange.last_month(),
            entities={"action": "call"},
            confidence=0.8,
        )

        statistics = {
            "total_count": 20,
            "top_entities": [
                {"entity": "John", "count": 15},
                {"entity": "Jane", "count": 5},
            ],
        }

        answer = synthesizer.handle_aggregation_query(query, memories, statistics)

        assert isinstance(answer, KnowledgeAnswer)
        assert answer.confidence > 0.9  # High confidence with clear winner
        assert "John" in answer.summary
        assert "15" in answer.summary or "most" in answer.summary.lower()

    def test_handle_aggregation_query_close_race(self, synthesizer):
        """Test aggregation query with close race."""
        memories = []
        now = datetime.utcnow()

        # Create memories with similar counts
        for i in range(10):
            person = "John" if i < 5 else "Jane"  # Close race: 5 vs 5
            memory = Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content=f"Called {person}",
                embedding=[0.1] * 768,
                metadata={"person": person},
                relevance_score=0.8,
                timestamp=now - timedelta(days=i),
                user_id="user_123",
            )
            memories.append(memory)

        query = KnowledgeQuery(
            query_text="who do I call most often?",
            query_type=KnowledgeQueryType.AGGREGATION,
            time_range=TimeRange.last_month(),
            entities={"action": "call"},
            confidence=0.8,
        )

        statistics = {
            "total_count": 10,
            "top_entities": [
                {"entity": "John", "count": 5},
                {"entity": "Jane", "count": 5},
            ],
        }

        answer = synthesizer.handle_aggregation_query(query, memories, statistics)

        assert isinstance(answer, KnowledgeAnswer)
        # Close race should not boost confidence as much
        assert answer.confidence < 1.0

    def test_handle_aggregation_query_small_sample(self, synthesizer):
        """Test aggregation query with small sample size."""
        memories = []
        now = datetime.utcnow()

        for i in range(3):
            memory = Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content="Called John",
                embedding=[0.1] * 768,
                metadata={"person": "John"},
                relevance_score=0.8,
                timestamp=now - timedelta(days=i),
                user_id="user_123",
            )
            memories.append(memory)

        query = KnowledgeQuery(
            query_text="who do I call most often?",
            query_type=KnowledgeQueryType.AGGREGATION,
            time_range=TimeRange.last_week(),
            entities={"action": "call"},
            confidence=0.8,
        )

        statistics = {
            "total_count": 3,
            "top_entities": [{"entity": "John", "count": 3}],
        }

        answer = synthesizer.handle_aggregation_query(query, memories, statistics)

        assert isinstance(answer, KnowledgeAnswer)
        # Small sample should reduce confidence
        assert answer.confidence < 0.9


class TestHandlePatternQuery:
    """Tests for handle_pattern_query method."""

    def test_handle_pattern_query_with_strong_pattern(self, synthesizer):
        """Test pattern query with strong pattern."""
        memories = []
        now = datetime.utcnow()

        # Create memories with strong daily pattern (same hour)
        for i in range(10):
            timestamp = now.replace(hour=9, minute=0) - timedelta(days=i)
            memory = Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content="Morning coffee",
                embedding=[0.1] * 768,
                metadata={"action": "coffee"},
                relevance_score=0.8,
                timestamp=timestamp,
                user_id="user_123",
            )
            memories.append(memory)

        patterns = [
            Pattern(
                pattern_type="daily",
                description="This typically happens around 09:00-10:00",
                frequency=0.9,  # Strong pattern
                confidence=0.95,
                examples=[m.timestamp.strftime("%Y-%m-%d %H:%M") for m in memories[:3]],
            )
        ]

        query = KnowledgeQuery(
            query_text="when do I usually have coffee?",
            query_type=KnowledgeQueryType.PATTERN,
            time_range=TimeRange.last_month(),
            entities={"action": "coffee"},
            confidence=0.8,
        )

        statistics = {"total_count": 10}

        answer = synthesizer.handle_pattern_query(query, memories, patterns, statistics)

        assert isinstance(answer, KnowledgeAnswer)
        assert answer.confidence > 0.9  # High confidence with strong pattern
        assert "09:00" in answer.summary or "9" in answer.summary
        assert len(answer.patterns) == 1
        assert len(answer.supporting_memories) > 0

    def test_handle_pattern_query_multiple_patterns(self, synthesizer):
        """Test pattern query with multiple patterns."""
        memories = []
        now = datetime.utcnow()

        for i in range(10):
            memory = Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content="Exercise",
                embedding=[0.1] * 768,
                metadata={"action": "exercise"},
                relevance_score=0.8,
                timestamp=now - timedelta(days=i),
                user_id="user_123",
            )
            memories.append(memory)

        patterns = [
            Pattern(
                pattern_type="daily",
                description="This typically happens around 07:00-08:00",
                frequency=0.6,
                confidence=0.7,
                examples=[],
            ),
            Pattern(
                pattern_type="weekly",
                description="This typically happens on Mondays",
                frequency=0.5,
                confidence=0.6,
                examples=[],
            ),
        ]

        query = KnowledgeQuery(
            query_text="when do I usually exercise?",
            query_type=KnowledgeQueryType.PATTERN,
            time_range=TimeRange.last_month(),
            entities={"action": "exercise"},
            confidence=0.8,
        )

        statistics = {"total_count": 10}

        answer = synthesizer.handle_pattern_query(query, memories, patterns, statistics)

        assert isinstance(answer, KnowledgeAnswer)
        # Multiple patterns should boost confidence
        assert answer.confidence > 0.8
        assert len(answer.patterns) == 2

    def test_handle_pattern_query_no_patterns(self, synthesizer):
        """Test pattern query with no patterns detected."""
        memories = []
        now = datetime.utcnow()

        for i in range(3):
            memory = Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content="Random activity",
                embedding=[0.1] * 768,
                metadata={},
                relevance_score=0.8,
                timestamp=now - timedelta(days=i * 10),  # Irregular
                user_id="user_123",
            )
            memories.append(memory)

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            time_range=TimeRange.last_month(),
            entities={},
            confidence=0.8,
        )

        statistics = {"total_count": 3}

        answer = synthesizer.handle_pattern_query(query, memories, [], statistics)

        assert isinstance(answer, KnowledgeAnswer)
        assert answer.confidence == 0.2  # Low confidence with no patterns
        assert "haven't detected" in answer.summary.lower()


class TestHandleFactualQuery:
    """Tests for handle_factual_query method."""

    def test_handle_factual_query_high_relevance(self, synthesizer):
        """Test factual query with high relevance memory."""
        memory = Memory(
            memory_id=uuid.uuid4(),
            memory_type=MemoryType.SEMANTIC,
            content="John's phone number is 555-1234",
            embedding=[0.1] * 768,
            metadata={"source": "user_correction", "entity": "John"},
            relevance_score=0.95,  # High relevance
            timestamp=datetime.utcnow(),
            user_id="user_123",
        )

        query = KnowledgeQuery(
            query_text="what is John's phone number?",
            query_type=KnowledgeQueryType.FACTUAL,
            time_range=None,
            entities={"person": "John"},
            confidence=0.8,
        )

        statistics = {"total_count": 1}

        answer = synthesizer.handle_factual_query(query, [memory], statistics)

        assert isinstance(answer, KnowledgeAnswer)
        assert answer.confidence > 0.9  # High confidence with high relevance
        assert "555-1234" in answer.summary
        assert len(answer.supporting_memories) == 1

    def test_handle_factual_query_trusted_source(self, synthesizer):
        """Test factual query with trusted source."""
        memory = Memory(
            memory_id=uuid.uuid4(),
            memory_type=MemoryType.SEMANTIC,
            content="The capital of France is Paris",
            embedding=[0.1] * 768,
            metadata={"source": "verified_fact"},  # Trusted source
            relevance_score=0.85,
            timestamp=datetime.utcnow(),
            user_id="user_123",
        )

        query = KnowledgeQuery(
            query_text="what is the capital of France?",
            query_type=KnowledgeQueryType.FACTUAL,
            time_range=None,
            entities={"location": "France"},
            confidence=0.8,
        )

        statistics = {"total_count": 1}

        answer = synthesizer.handle_factual_query(query, [memory], statistics)

        assert isinstance(answer, KnowledgeAnswer)
        # Trusted source should boost confidence
        assert answer.confidence > 0.9
        assert "Paris" in answer.summary

    def test_handle_factual_query_multiple_sources(self, synthesizer):
        """Test factual query with multiple corroborating sources."""
        memories = []
        for i in range(3):
            memory = Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.SEMANTIC,
                content=f"Python is a programming language (source {i})",
                embedding=[0.1] * 768,
                metadata={"source": f"source_{i}"},
                relevance_score=0.8 - (i * 0.1),
                timestamp=datetime.utcnow(),
                user_id="user_123",
            )
            memories.append(memory)

        query = KnowledgeQuery(
            query_text="what is Python?",
            query_type=KnowledgeQueryType.FACTUAL,
            time_range=None,
            entities={"topic": "Python"},
            confidence=0.8,
        )

        statistics = {"total_count": 3}

        answer = synthesizer.handle_factual_query(query, memories, statistics)

        assert isinstance(answer, KnowledgeAnswer)
        # Multiple sources should boost confidence
        assert answer.confidence > 0.9
        assert len(answer.supporting_memories) == 3

    def test_handle_factual_query_low_relevance(self, synthesizer):
        """Test factual query with low relevance memory."""
        memory = Memory(
            memory_id=uuid.uuid4(),
            memory_type=MemoryType.SEMANTIC,
            content="Some unrelated information",
            embedding=[0.1] * 768,
            metadata={},
            relevance_score=0.3,  # Low relevance
            timestamp=datetime.utcnow(),
            user_id="user_123",
        )

        query = KnowledgeQuery(
            query_text="what is the answer?",
            query_type=KnowledgeQueryType.FACTUAL,
            time_range=None,
            entities={},
            confidence=0.5,
        )

        statistics = {"total_count": 1}

        answer = synthesizer.handle_factual_query(query, [memory], statistics)

        assert isinstance(answer, KnowledgeAnswer)
        # Low relevance should not boost confidence
        assert answer.confidence <= 0.6


class TestConfidenceCalculations:
    """Tests for specialized confidence calculation methods."""

    def test_temporal_confidence_recent_data(self, synthesizer):
        """Test temporal confidence with recent data."""
        now = datetime.utcnow()
        memories = [
            Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content="Recent event",
                embedding=[0.1] * 768,
                metadata={},
                relevance_score=0.8,
                timestamp=now,  # Today
                user_id="user_123",
            )
            for _ in range(5)
        ]

        query = KnowledgeQuery(
            query_text="test",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.7,
        )

        statistics = {"time_span_days": 0}

        confidence = synthesizer._calculate_temporal_confidence(query, memories, statistics)

        # Recent data + good sample size should boost confidence
        assert confidence > 0.8

    def test_aggregation_confidence_large_sample(self, synthesizer):
        """Test aggregation confidence with large sample."""
        memories = [
            Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content=f"Event {i}",
                embedding=[0.1] * 768,
                metadata={},
                relevance_score=0.8,
                timestamp=datetime.utcnow(),
                user_id="user_123",
            )
            for i in range(25)
        ]

        query = KnowledgeQuery(
            query_text="test",
            query_type=KnowledgeQueryType.AGGREGATION,
            time_range=None,
            entities={},
            confidence=0.7,
        )

        statistics = {
            "top_entities": [
                {"entity": "A", "count": 20},
                {"entity": "B", "count": 5},
            ]
        }

        confidence = synthesizer._calculate_aggregation_confidence(query, memories, statistics)

        # Large sample + clear winner should boost confidence
        assert confidence > 0.9

    def test_pattern_confidence_strong_pattern(self, synthesizer):
        """Test pattern confidence with strong pattern."""
        memories = [
            Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.EPISODIC,
                content=f"Event {i}",
                embedding=[0.1] * 768,
                metadata={},
                relevance_score=0.8,
                timestamp=datetime.utcnow(),
                user_id="user_123",
            )
            for i in range(10)
        ]

        patterns = [
            Pattern(
                pattern_type="daily",
                description="Strong pattern",
                frequency=0.8,  # Strong
                confidence=0.9,
                examples=[],
            )
        ]

        query = KnowledgeQuery(
            query_text="test",
            query_type=KnowledgeQueryType.PATTERN,
            time_range=None,
            entities={},
            confidence=0.7,
        )

        statistics = {}

        confidence = synthesizer._calculate_pattern_confidence(
            query, memories, patterns, statistics
        )

        # Strong pattern + good sample should boost confidence
        assert confidence > 0.9

    def test_factual_confidence_high_relevance_trusted_source(self, synthesizer):
        """Test factual confidence with high relevance and trusted source."""
        memories = [
            Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.SEMANTIC,
                content="Fact",
                embedding=[0.1] * 768,
                metadata={"source": "verified_fact"},
                relevance_score=0.95,
                timestamp=datetime.utcnow(),
                user_id="user_123",
            )
            for _ in range(3)
        ]

        query = KnowledgeQuery(
            query_text="test",
            query_type=KnowledgeQueryType.FACTUAL,
            time_range=None,
            entities={},
            confidence=0.7,
        )

        statistics = {}

        confidence = synthesizer._calculate_factual_confidence(query, memories, statistics)

        # High relevance + trusted source + corroboration should boost confidence
        assert confidence > 0.9
