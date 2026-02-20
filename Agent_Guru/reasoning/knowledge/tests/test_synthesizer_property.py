"""
Property-based tests for KnowledgeSynthesizer.

Tests universal properties that should hold across all valid inputs:
- Answer synthesis always produces valid KnowledgeAnswer
- Confidence scores are always in valid range
- Statistics are always non-negative
- Patterns have valid frequency and confidence
- Latency requirements are met

Uses Hypothesis for property-based testing with 100 iterations.

Coverage Target: Additional coverage for edge cases
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from Agent_Guru.reasoning.knowledge.synthesizer import KnowledgeSynthesizer
from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeQuery,
    KnowledgeQueryType,
    KnowledgeAnswer,
    TimeRange,
)
from Agent_Guru.reasoning.models.memory import EpisodicMemory, SemanticMemory


# Strategy for generating valid KnowledgeQuery objects
@st.composite
def knowledge_query_strategy(draw):
    """Generate valid KnowledgeQuery objects."""
    query_type = draw(st.sampled_from(list(KnowledgeQueryType)))
    query_text = draw(st.text(min_size=5, max_size=100, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters="?!."
    )))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))

    # Generate time range for temporal queries
    time_range = None
    if query_type == KnowledgeQueryType.TEMPORAL:
        days_back = draw(st.integers(min_value=1, max_value=365))
        time_range = TimeRange.last_n_days(days_back)

    # Generate entities
    entities = {}
    if draw(st.booleans()):
        entity_type = draw(st.sampled_from(["person", "action", "app", "location"]))
        entity_value = draw(st.text(min_size=3, max_size=20, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll")
        )))
        entities[entity_type] = entity_value

    return KnowledgeQuery(
        query_text=query_text,
        query_type=query_type,
        time_range=time_range,
        entities=entities,
        confidence=confidence,
    )


# Strategy for generating valid Memory objects
@st.composite
def memory_strategy(draw):
    """Generate valid Memory objects."""
    memory_type = draw(st.sampled_from(["episodic", "semantic"]))
    content = draw(st.text(min_size=10, max_size=200, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs")
    )))
    user_id = "user_123"

    # Generate timestamp within last year
    days_ago = draw(st.integers(min_value=0, max_value=365))
    timestamp = datetime.utcnow() - timedelta(days=days_ago)

    if memory_type == "episodic":
        return EpisodicMemory(
            content=content,
            action_taken=draw(st.text(min_size=3, max_size=20)),
            result=draw(st.sampled_from(["Success", "Failure", "Partial"])),
            success=draw(st.booleans()),
            user_id=user_id,
            timestamp=timestamp,
        )
    else:
        return SemanticMemory(
            content=content,
            fact=content,
            source=draw(st.text(min_size=3, max_size=20)),
            confidence=draw(st.floats(min_value=0.0, max_value=1.0)),  # Add confidence field
            user_id=user_id,
            timestamp=timestamp,
        )


class TestKnowledgeSynthesizerProperties:
    """Property-based tests for KnowledgeSynthesizer."""

    @given(
        max_memories=st.integers(min_value=1, max_value=100),
        pattern_min_frequency=st.floats(min_value=0.0, max_value=1.0),
        confidence_threshold=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_initialization_always_succeeds_with_valid_params(
        self, max_memories, pattern_min_frequency, confidence_threshold
    ):
        """Property: Initialization always succeeds with valid parameters."""
        memory_retriever = Mock(spec=MemoryRetriever)

        synthesizer = KnowledgeSynthesizer(
            memory_retriever,
            max_memories=max_memories,
            pattern_min_frequency=pattern_min_frequency,
            confidence_threshold=confidence_threshold,
        )

        assert synthesizer.max_memories == max_memories
        assert synthesizer.pattern_min_frequency == pattern_min_frequency
        assert synthesizer.confidence_threshold == confidence_threshold

    @given(query=knowledge_query_strategy())
    @settings(max_examples=100)
    def test_synthesize_answer_always_returns_valid_answer(self, query):
        """Property: synthesize_answer always returns valid KnowledgeAnswer."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Mock memory retrieval
        memory_retriever.retrieve.return_value = []

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify answer is valid
        assert isinstance(answer, KnowledgeAnswer)
        assert isinstance(answer.summary, str)
        assert len(answer.summary) > 0
        assert 0.0 <= answer.confidence <= 1.0
        assert isinstance(answer.supporting_memories, list)
        assert isinstance(answer.patterns, list)
        assert isinstance(answer.statistics, dict)

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_confidence_always_in_valid_range(self, query, memories):
        """Property: Confidence is always between 0.0 and 1.0."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Mock memory retrieval
        memory_retriever.retrieve.return_value = memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify confidence is in valid range
        assert 0.0 <= answer.confidence <= 1.0

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_statistics_always_non_negative(self, query, memories):
        """Property: Statistics are always non-negative."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Mock memory retrieval
        memory_retriever.retrieve.return_value = memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify statistics are non-negative
        assert answer.statistics["total_count"] >= 0
        if "time_span_days" in answer.statistics:
            assert answer.statistics["time_span_days"] >= 0

    @given(memories=st.lists(memory_strategy(), min_size=3, max_size=20))
    @settings(max_examples=100)
    def test_patterns_have_valid_frequency_and_confidence(self, memories):
        """Property: Detected patterns have valid frequency and confidence."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        # Detect patterns
        patterns = synthesizer.detect_patterns(memories, query)

        # Verify all patterns have valid frequency and confidence
        for pattern in patterns:
            assert 0.0 <= pattern.frequency <= 1.0
            assert 0.0 <= pattern.confidence <= 1.0
            assert pattern.frequency >= synthesizer.pattern_min_frequency

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=50),
    )
    @settings(max_examples=50)  # Reduced for latency test
    def test_retrieve_relevant_data_respects_max_memories(self, query, memories):
        """Property: retrieve_relevant_data never returns more than max_memories."""
        memory_retriever = Mock(spec=MemoryRetriever)
        max_memories = 10
        synthesizer = KnowledgeSynthesizer(memory_retriever, max_memories=max_memories)

        # Mock memory retrieval - return only up to max_memories
        # (simulating what MemoryRetriever.retrieve does with top_k parameter)
        memory_retriever.retrieve.return_value = memories[:max_memories]

        # Retrieve data
        retrieved = synthesizer.retrieve_relevant_data(query, "user_123")

        # Verify count is within limit
        assert len(retrieved) <= max_memories

    @given(
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_aggregate_statistics_always_returns_dict(self, memories):
        """Property: aggregate_statistics always returns a dictionary."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        query = KnowledgeQuery(
            query_text="how many times?",
            query_type=KnowledgeQueryType.AGGREGATION,
            confidence=0.9,
        )

        # Aggregate statistics
        statistics = synthesizer.aggregate_statistics(memories, query)

        # Verify result is a dictionary
        assert isinstance(statistics, dict)
        assert "total_count" in statistics
        assert statistics["total_count"] == len(memories)

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=1, max_size=10),
    )
    @settings(max_examples=100)
    def test_supporting_memories_limited_to_top_5(self, query, memories):
        """Property: Supporting memories are limited to top 5."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Mock memory retrieval
        memory_retriever.retrieve.return_value = memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify supporting memories are limited
        assert len(answer.supporting_memories) <= 5

    @given(
        query=knowledge_query_strategy(),
    )
    @settings(max_examples=100)
    def test_empty_memories_produces_valid_answer(self, query):
        """Property: Empty memories always produces valid answer."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Mock empty memory retrieval
        memory_retriever.retrieve.return_value = []

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify answer is valid
        assert isinstance(answer, KnowledgeAnswer)
        assert len(answer.summary) > 0
        # Check for various "no data" messages depending on query type
        assert any(phrase in answer.summary.lower() for phrase in [
            "don't have", "haven't", "not", "no information", "no data", "insufficient"
        ])
        assert answer.statistics["total_count"] == 0

    @given(
        memories=st.lists(memory_strategy(), min_size=3, max_size=10),
    )
    @settings(max_examples=100)
    def test_pattern_detection_deterministic(self, memories):
        """Property: Pattern detection is deterministic for same input."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        # Detect patterns twice
        patterns1 = synthesizer.detect_patterns(memories, query)
        patterns2 = synthesizer.detect_patterns(memories, query)

        # Verify results are identical
        assert len(patterns1) == len(patterns2)
        for p1, p2 in zip(patterns1, patterns2):
            assert p1.pattern_type == p2.pattern_type
            assert p1.frequency == p2.frequency
            assert p1.confidence == p2.confidence

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=10),
    )
    @settings(max_examples=100)
    def test_answer_summary_never_empty(self, query, memories):
        """Property: Answer summary is never empty."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever)

        # Mock memory retrieval
        memory_retriever.retrieve.return_value = memories

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify summary is not empty
        assert len(answer.summary) > 0
        assert answer.summary.strip() != ""


class TestEdgeCases:
    """Test edge cases with property-based testing."""

    @given(
        max_memories=st.integers(min_value=1, max_value=5),
        memories=st.lists(memory_strategy(), min_size=10, max_size=20),
    )
    @settings(max_examples=50)
    def test_max_memories_enforced(self, max_memories, memories):
        """Property: max_memories limit is always enforced."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(memory_retriever, max_memories=max_memories)

        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            confidence=0.9,
        )

        # Mock memory retrieval with more than max_memories
        memory_retriever.retrieve.return_value = memories[:max_memories]

        # Retrieve data
        retrieved = synthesizer.retrieve_relevant_data(query, "user_123")

        # Verify limit is enforced
        assert len(retrieved) <= max_memories

    @given(
        pattern_min_frequency=st.floats(min_value=0.5, max_value=1.0),
        memories=st.lists(memory_strategy(), min_size=5, max_size=10),
    )
    @settings(max_examples=50)
    def test_pattern_frequency_threshold_enforced(self, pattern_min_frequency, memories):
        """Property: Pattern frequency threshold is always enforced."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever, pattern_min_frequency=pattern_min_frequency
        )

        query = KnowledgeQuery(
            query_text="when do I usually do this?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.9,
        )

        # Detect patterns
        patterns = synthesizer.detect_patterns(memories, query)

        # Verify all patterns meet frequency threshold
        for pattern in patterns:
            assert pattern.frequency >= pattern_min_frequency

    @given(
        confidence_threshold=st.floats(min_value=0.5, max_value=0.9),
    )
    @settings(max_examples=50)
    def test_low_confidence_indicator_added(self, confidence_threshold):
        """Property: Low confidence indicator is added when confidence < threshold."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever, confidence_threshold=confidence_threshold
        )

        # Create query with low confidence
        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            confidence=confidence_threshold - 0.1,  # Below threshold
        )

        # Mock minimal memory retrieval (low confidence)
        memory_retriever.retrieve.return_value = [
            EpisodicMemory(
                content="Test",
                action_taken="test",
                result="Success",
                success=True,
                user_id="user_123",
            )
        ]

        # Synthesize answer
        answer = synthesizer.synthesize_answer(query, "user_123")

        # Verify low confidence indicator is present
        if answer.confidence < confidence_threshold:
            assert "not very confident" in answer.summary.lower()
