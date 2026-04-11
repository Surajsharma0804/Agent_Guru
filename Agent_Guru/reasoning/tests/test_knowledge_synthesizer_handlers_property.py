"""
Property-based tests for Knowledge Synthesizer query type handlers.

Tests invariants and edge cases using Hypothesis for comprehensive coverage.

**Validates: Requirements 38.5, 38.6, 38.7**
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.knowledge.synthesizer import KnowledgeSynthesizer
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeAnswer,
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
    TimeRange,
)
from Agent_Guru.reasoning.models.memory import Memory, MemoryType


def create_test_synthesizer():
    """Create KnowledgeSynthesizer for testing without LLM."""
    mock_retriever = Mock()
    return KnowledgeSynthesizer(mock_retriever, use_llm_synthesis=False)


# Strategy for generating valid memories
@st.composite
def memory_strategy(draw):
    """Generate valid Memory objects."""
    now = datetime.utcnow()
    days_ago = draw(st.integers(min_value=0, max_value=365))

    return Memory(
        memory_id=uuid.uuid4(),
        memory_type=draw(st.sampled_from(list(MemoryType))),
        content=draw(
            st.text(min_size=5, max_size=200, alphabet=st.characters(blacklist_categories=("Cs",)))
        ),  # Valid content
        embedding=[0.1] * 768,
        metadata=draw(
            st.dictionaries(
                st.text(
                    min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))
                ),
                st.text(
                    min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))
                ),
            )
        ),
        relevance_score=draw(st.floats(min_value=0.0, max_value=1.0)),
        timestamp=now - timedelta(days=days_ago),
        user_id="user_123",
    )


# Strategy for generating valid patterns
@st.composite
def pattern_strategy(draw):
    """Generate valid Pattern objects."""
    return Pattern(
        pattern_type=draw(st.sampled_from(["daily", "weekly", "monthly"])),
        description=draw(
            st.text(min_size=5, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",)))
        ),
        frequency=draw(st.floats(min_value=0.0, max_value=1.0)),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        examples=draw(
            st.lists(
                st.text(
                    min_size=5, max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))
                ),
                min_size=0,
                max_size=5,
            )
        ),
    )


# Strategy for generating valid queries
@st.composite
def query_strategy(draw, query_type=None):
    """Generate valid KnowledgeQuery objects."""
    if query_type is None:
        query_type = draw(st.sampled_from(list(KnowledgeQueryType)))

    return KnowledgeQuery(
        query_text=draw(
            st.text(min_size=5, max_size=200, alphabet=st.characters(blacklist_categories=("Cs",)))
        ),
        query_type=query_type,
        time_range=draw(st.one_of(st.none(), st.just(TimeRange.last_week()))),
        entities=draw(
            st.dictionaries(
                st.text(
                    min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))
                ),
                st.text(
                    min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))
                ),
            )
        ),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
    )


class TestTemporalQueryProperties:
    """Property-based tests for temporal query handler."""

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.TEMPORAL),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_temporal_query_always_returns_valid_answer(self, query, memories):
        """Property: Temporal query handler always returns valid KnowledgeAnswer.

        **Validates: Requirements 38.5**
        """
        synthesizer = create_test_synthesizer()

        statistics = {
            "total_count": len(memories),
            "most_recent": memories[0].timestamp.isoformat() if memories else None,
            "oldest": memories[-1].timestamp.isoformat() if memories else None,
        }

        answer = synthesizer.handle_temporal_query(query, memories, statistics)

        # Invariant: Always returns KnowledgeAnswer
        assert isinstance(answer, KnowledgeAnswer)
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert 0.0 <= answer.confidence <= 1.0
        assert isinstance(answer.supporting_memories, list)
        assert isinstance(answer.patterns, list)
        assert isinstance(answer.statistics, dict)

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.TEMPORAL),
        memories=st.lists(memory_strategy(), min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_temporal_confidence_bounded(self, query, memories):
        """Property: Temporal confidence is always between 0.0 and 1.0.

        **Validates: Requirements 38.5**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"time_span_days": 10}

        confidence = synthesizer._calculate_temporal_confidence(query, memories, statistics)

        # Invariant: Confidence is bounded
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.TEMPORAL),
        memories=st.lists(memory_strategy(), min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_temporal_supporting_memories_limited(self, query, memories):
        """Property: Temporal query returns at most 5 supporting memories.

        **Validates: Requirements 38.5**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"total_count": len(memories)}

        answer = synthesizer.handle_temporal_query(query, memories, statistics)

        # Invariant: Supporting memories limited to 5
        assert len(answer.supporting_memories) <= 5


class TestAggregationQueryProperties:
    """Property-based tests for aggregation query handler."""

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.AGGREGATION),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_aggregation_query_always_returns_valid_answer(self, query, memories):
        """Property: Aggregation query handler always returns valid KnowledgeAnswer.

        **Validates: Requirements 38.6**
        """
        synthesizer = create_test_synthesizer()

        statistics = {
            "total_count": len(memories),
            "top_entities": [{"entity": "test", "count": len(memories)}] if memories else [],
        }

        answer = synthesizer.handle_aggregation_query(query, memories, statistics)

        # Invariant: Always returns KnowledgeAnswer
        assert isinstance(answer, KnowledgeAnswer)
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert 0.0 <= answer.confidence <= 1.0
        assert isinstance(answer.supporting_memories, list)

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.AGGREGATION),
        memories=st.lists(memory_strategy(), min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_aggregation_confidence_increases_with_sample_size(self, query, memories):
        """Property: Aggregation confidence increases with larger sample size.

        **Validates: Requirements 38.6**
        """
        synthesizer = create_test_synthesizer()

        # Small sample
        small_sample = memories[:3]
        small_stats = {"top_entities": [{"entity": "A", "count": 3}]}
        small_confidence = synthesizer._calculate_aggregation_confidence(
            query, small_sample, small_stats
        )

        # Large sample (if available)
        if len(memories) >= 20:
            large_sample = memories[:20]
            large_stats = {"top_entities": [{"entity": "A", "count": 20}]}
            large_confidence = synthesizer._calculate_aggregation_confidence(
                query, large_sample, large_stats
            )

            # Invariant: Larger sample should have higher or equal confidence
            assert large_confidence >= small_confidence

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.AGGREGATION),
        memories=st.lists(memory_strategy(), min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_aggregation_confidence_bounded(self, query, memories):
        """Property: Aggregation confidence is always between 0.0 and 1.0.

        **Validates: Requirements 38.6**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"top_entities": [{"entity": "test", "count": len(memories)}]}

        confidence = synthesizer._calculate_aggregation_confidence(query, memories, statistics)

        # Invariant: Confidence is bounded
        assert 0.0 <= confidence <= 1.0


class TestPatternQueryProperties:
    """Property-based tests for pattern query handler."""

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.PATTERN),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
        patterns=st.lists(pattern_strategy(), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_pattern_query_always_returns_valid_answer(self, query, memories, patterns):
        """Property: Pattern query handler always returns valid KnowledgeAnswer.

        **Validates: Requirements 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"total_count": len(memories)}

        answer = synthesizer.handle_pattern_query(query, memories, patterns, statistics)

        # Invariant: Always returns KnowledgeAnswer
        assert isinstance(answer, KnowledgeAnswer)
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert 0.0 <= answer.confidence <= 1.0
        assert isinstance(answer.patterns, list)
        assert answer.patterns == patterns  # Patterns preserved

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.PATTERN),
        memories=st.lists(memory_strategy(), min_size=1, max_size=20),
        patterns=st.lists(pattern_strategy(), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_pattern_confidence_increases_with_frequency(self, query, memories, patterns):
        """Property: Pattern confidence increases with higher pattern frequency.

        **Validates: Requirements 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {}

        # Weak pattern
        weak_patterns = [
            Pattern(
                pattern_type="daily",
                description="Weak",
                frequency=0.3,
                confidence=0.4,
                examples=[],
            )
        ]
        weak_confidence = synthesizer._calculate_pattern_confidence(
            query, memories, weak_patterns, statistics
        )

        # Strong pattern
        strong_patterns = [
            Pattern(
                pattern_type="daily",
                description="Strong",
                frequency=0.8,
                confidence=0.9,
                examples=[],
            )
        ]
        strong_confidence = synthesizer._calculate_pattern_confidence(
            query, memories, strong_patterns, statistics
        )

        # Invariant: Stronger pattern should have higher confidence
        assert strong_confidence >= weak_confidence

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.PATTERN),
        memories=st.lists(memory_strategy(), min_size=1, max_size=20),
        patterns=st.lists(pattern_strategy(), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_pattern_confidence_bounded(self, query, memories, patterns):
        """Property: Pattern confidence is always between 0.0 and 1.0.

        **Validates: Requirements 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {}

        confidence = synthesizer._calculate_pattern_confidence(
            query, memories, patterns, statistics
        )

        # Invariant: Confidence is bounded
        assert 0.0 <= confidence <= 1.0


class TestFactualQueryProperties:
    """Property-based tests for factual query handler."""

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.FACTUAL),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_factual_query_always_returns_valid_answer(self, query, memories):
        """Property: Factual query handler always returns valid KnowledgeAnswer.

        **Validates: Requirements 38.5, 38.6, 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"total_count": len(memories)}

        answer = synthesizer.handle_factual_query(query, memories, statistics)

        # Invariant: Always returns KnowledgeAnswer
        assert isinstance(answer, KnowledgeAnswer)
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert 0.0 <= answer.confidence <= 1.0
        assert isinstance(answer.supporting_memories, list)

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.FACTUAL),
        memories=st.lists(memory_strategy(), min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_factual_confidence_increases_with_relevance(self, query, memories):
        """Property: Factual confidence increases with higher relevance score.

        **Validates: Requirements 38.5, 38.6, 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {}

        # Low relevance
        low_relevance_memories = [
            Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.SEMANTIC,
                content="Low relevance",
                embedding=[0.1] * 768,
                metadata={},
                relevance_score=0.3,
                timestamp=datetime.utcnow(),
                user_id="user_123",
            )
        ]
        low_confidence = synthesizer._calculate_factual_confidence(
            query, low_relevance_memories, statistics
        )

        # High relevance
        high_relevance_memories = [
            Memory(
                memory_id=uuid.uuid4(),
                memory_type=MemoryType.SEMANTIC,
                content="High relevance",
                embedding=[0.1] * 768,
                metadata={},
                relevance_score=0.95,
                timestamp=datetime.utcnow(),
                user_id="user_123",
            )
        ]
        high_confidence = synthesizer._calculate_factual_confidence(
            query, high_relevance_memories, statistics
        )

        # Invariant: Higher relevance should have higher confidence
        assert high_confidence >= low_confidence

    @given(
        query=query_strategy(query_type=KnowledgeQueryType.FACTUAL),
        memories=st.lists(memory_strategy(), min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_factual_supporting_memories_limited(self, query, memories):
        """Property: Factual query returns at most 3 supporting memories.

        **Validates: Requirements 38.5, 38.6, 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"total_count": len(memories)}

        answer = synthesizer.handle_factual_query(query, memories, statistics)

        # Invariant: Supporting memories limited to 3 for factual queries
        assert len(answer.supporting_memories) <= 3


class TestConfidenceInvariants:
    """Property-based tests for confidence calculation invariants."""

    @given(
        query=query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_confidence_never_exceeds_one(self, query, memories):
        """Property: Confidence never exceeds 1.0 for any query type.

        **Validates: Requirements 38.5, 38.6, 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"total_count": len(memories)}
        patterns = []

        if query.query_type == KnowledgeQueryType.TEMPORAL:
            confidence = synthesizer._calculate_temporal_confidence(query, memories, statistics)
        elif query.query_type == KnowledgeQueryType.AGGREGATION:
            confidence = synthesizer._calculate_aggregation_confidence(query, memories, statistics)
        elif query.query_type == KnowledgeQueryType.PATTERN:
            confidence = synthesizer._calculate_pattern_confidence(
                query, memories, patterns, statistics
            )
        else:  # FACTUAL
            confidence = synthesizer._calculate_factual_confidence(query, memories, statistics)

        # Invariant: Confidence never exceeds 1.0
        assert confidence <= 1.0

    @given(
        query=query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_confidence_never_negative(self, query, memories):
        """Property: Confidence is never negative for any query type.

        **Validates: Requirements 38.5, 38.6, 38.7**
        """
        synthesizer = create_test_synthesizer()

        statistics = {"total_count": len(memories)}
        patterns = []

        if query.query_type == KnowledgeQueryType.TEMPORAL:
            confidence = synthesizer._calculate_temporal_confidence(query, memories, statistics)
        elif query.query_type == KnowledgeQueryType.AGGREGATION:
            confidence = synthesizer._calculate_aggregation_confidence(query, memories, statistics)
        elif query.query_type == KnowledgeQueryType.PATTERN:
            confidence = synthesizer._calculate_pattern_confidence(
                query, memories, patterns, statistics
            )
        else:  # FACTUAL
            confidence = synthesizer._calculate_factual_confidence(query, memories, statistics)

        # Invariant: Confidence is never negative
        assert confidence >= 0.0
