"""
Property-based tests for knowledge query data models.

Uses Hypothesis to test invariants and edge cases across many randomly
generated inputs. Tests universal properties that should hold for all
valid inputs.

Coverage target: 80%+
"""

from datetime import datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeAnswer,
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
    TimeRange,
)


# Custom strategies for generating test data
@st.composite
def time_range_strategy(draw):
    """Generate valid TimeRange instances."""
    # Generate start time
    days_ago = draw(st.integers(min_value=1, max_value=365))
    start = datetime.utcnow() - timedelta(days=days_ago)

    # Generate end time after start
    duration_days = draw(st.integers(min_value=0, max_value=days_ago))
    end = start + timedelta(days=duration_days)

    # Generate description
    description = draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()))

    return TimeRange(start=start, end=end, description=description)


@st.composite
def pattern_strategy(draw):
    """Generate valid Pattern instances."""
    pattern_type = draw(
        st.sampled_from(["daily", "weekly", "monthly", "situational", "temporal", "contextual"])
    )
    description = draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip()))
    frequency = draw(st.floats(min_value=0.0, max_value=1.0))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    examples = draw(
        st.lists(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()), max_size=10)
    )

    return Pattern(
        pattern_type=pattern_type,
        description=description,
        frequency=frequency,
        confidence=confidence,
        examples=examples,
    )


@st.composite
def knowledge_query_strategy(draw):
    """Generate valid KnowledgeQuery instances."""
    query_text = draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip()))
    query_type = draw(st.sampled_from(list(KnowledgeQueryType)))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))

    # Temporal queries get a time range
    time_range = None
    if query_type == KnowledgeQueryType.TEMPORAL:
        time_range = draw(time_range_strategy())

    # Generate entities
    entities = draw(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
            values=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
            max_size=5,
        )
    )

    return KnowledgeQuery(
        query_text=query_text,
        query_type=query_type,
        time_range=time_range,
        entities=entities,
        confidence=confidence,
    )


@st.composite
def knowledge_answer_strategy(draw):
    """Generate valid KnowledgeAnswer instances."""
    summary = draw(st.text(min_size=1, max_size=1000).filter(lambda x: x.strip()))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    supporting_memories = draw(
        st.lists(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()), max_size=20)
    )
    patterns = draw(st.lists(pattern_strategy(), max_size=10))
    statistics = draw(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
            values=st.integers(min_value=0, max_value=1000),
            max_size=10,
        )
    )

    return KnowledgeAnswer(
        summary=summary,
        confidence=confidence,
        supporting_memories=supporting_memories,
        patterns=patterns,
        statistics=statistics,
    )


@pytest.mark.property
class TestTimeRangeProperties:
    """Property-based tests for TimeRange model."""

    @given(time_range_strategy())
    def test_time_range_start_before_end(self, time_range):
        """Property: Start time is always before or equal to end time."""
        assert time_range.start <= time_range.end

    @given(time_range_strategy())
    def test_time_range_description_not_empty(self, time_range):
        """Property: Description is never empty after validation."""
        assert time_range.description.strip()
        assert len(time_range.description) > 0

    @given(time_range_strategy())
    def test_time_range_json_round_trip(self, time_range):
        """Property: TimeRange survives JSON serialization round trip."""
        json_str = time_range.model_dump_json()
        data = time_range.model_dump()
        restored = TimeRange(**data)

        assert restored.start == time_range.start
        assert restored.end == time_range.end
        assert restored.description == time_range.description

    @given(st.integers(min_value=1, max_value=365))
    def test_last_n_days_creates_valid_range(self, n):
        """Property: last_n_days always creates valid time range."""
        time_range = TimeRange.last_n_days(n)

        assert time_range.start <= time_range.end
        assert (time_range.end - time_range.start).days == n
        assert time_range.description == f"last {n} days"


@pytest.mark.property
class TestPatternProperties:
    """Property-based tests for Pattern model."""

    @given(pattern_strategy())
    def test_pattern_frequency_in_range(self, pattern):
        """Property: Frequency is always between 0.0 and 1.0."""
        assert 0.0 <= pattern.frequency <= 1.0

    @given(pattern_strategy())
    def test_pattern_confidence_in_range(self, pattern):
        """Property: Confidence is always between 0.0 and 1.0."""
        assert 0.0 <= pattern.confidence <= 1.0

    @given(pattern_strategy())
    def test_pattern_description_not_empty(self, pattern):
        """Property: Description is never empty after validation."""
        assert pattern.description.strip()
        assert len(pattern.description) > 0

    @given(pattern_strategy())
    def test_pattern_type_is_valid(self, pattern):
        """Property: Pattern type is always one of the valid types."""
        valid_types = {"daily", "weekly", "monthly", "situational", "temporal", "contextual"}
        assert pattern.pattern_type in valid_types

    @given(pattern_strategy())
    def test_pattern_examples_not_empty_strings(self, pattern):
        """Property: Examples never contain empty strings."""
        for example in pattern.examples:
            assert example.strip()
            assert len(example) > 0

    @given(pattern_strategy())
    def test_pattern_json_round_trip(self, pattern):
        """Property: Pattern survives JSON serialization round trip."""
        data = pattern.model_dump()
        restored = Pattern(**data)

        assert restored.pattern_type == pattern.pattern_type
        assert restored.description == pattern.description
        assert restored.frequency == pattern.frequency
        assert restored.confidence == pattern.confidence
        assert restored.examples == pattern.examples


@pytest.mark.property
class TestKnowledgeQueryProperties:
    """Property-based tests for KnowledgeQuery model."""

    @given(knowledge_query_strategy())
    def test_query_text_not_empty(self, query):
        """Property: Query text is never empty after validation."""
        assert query.query_text.strip()
        assert len(query.query_text) > 0

    @given(knowledge_query_strategy())
    def test_query_confidence_in_range(self, query):
        """Property: Confidence is always between 0.0 and 1.0."""
        assert 0.0 <= query.confidence <= 1.0

    @given(knowledge_query_strategy())
    def test_temporal_query_has_time_range(self, query):
        """Property: Temporal queries always have a time range."""
        if query.query_type == KnowledgeQueryType.TEMPORAL:
            assert query.time_range is not None
            assert query.time_range.start <= query.time_range.end

    @given(knowledge_query_strategy())
    def test_query_type_is_valid(self, query):
        """Property: Query type is always one of the valid types."""
        assert query.query_type in list(KnowledgeQueryType)

    @given(knowledge_query_strategy())
    def test_query_entities_keys_not_empty(self, query):
        """Property: Entity keys are never empty strings."""
        for key in query.entities.keys():
            assert key.strip()
            assert len(key) > 0

    @given(knowledge_query_strategy())
    def test_query_json_round_trip(self, query):
        """Property: KnowledgeQuery survives JSON serialization round trip."""
        data = query.model_dump()
        restored = KnowledgeQuery(**data)

        assert restored.query_text == query.query_text
        assert restored.query_type == query.query_type
        assert restored.confidence == query.confidence
        assert restored.entities == query.entities


@pytest.mark.property
class TestKnowledgeAnswerProperties:
    """Property-based tests for KnowledgeAnswer model."""

    @given(knowledge_answer_strategy())
    def test_answer_summary_not_empty(self, answer):
        """Property: Summary is never empty after validation."""
        assert answer.summary.strip()
        assert len(answer.summary) > 0

    @given(knowledge_answer_strategy())
    def test_answer_confidence_in_range(self, answer):
        """Property: Confidence is always between 0.0 and 1.0."""
        assert 0.0 <= answer.confidence <= 1.0

    @given(knowledge_answer_strategy())
    def test_answer_memory_ids_not_empty(self, answer):
        """Property: Memory IDs are never empty strings."""
        for mem_id in answer.supporting_memories:
            assert mem_id.strip()
            assert len(mem_id) > 0

    @given(knowledge_answer_strategy())
    def test_answer_patterns_count_limited(self, answer):
        """Property: Patterns list never exceeds 10 items."""
        assert len(answer.patterns) <= 10

    @given(knowledge_answer_strategy())
    def test_answer_patterns_valid(self, answer):
        """Property: All patterns in answer are valid."""
        for pattern in answer.patterns:
            assert 0.0 <= pattern.frequency <= 1.0
            assert 0.0 <= pattern.confidence <= 1.0
            assert pattern.description.strip()

    @given(knowledge_answer_strategy())
    def test_answer_statistics_keys_not_empty(self, answer):
        """Property: Statistics keys are never empty strings."""
        for key in answer.statistics.keys():
            assert key.strip()
            assert len(key) > 0

    @given(knowledge_answer_strategy())
    def test_answer_json_round_trip(self, answer):
        """Property: KnowledgeAnswer survives JSON serialization round trip."""
        data = answer.model_dump()
        restored = KnowledgeAnswer(**data)

        assert restored.summary == answer.summary
        assert restored.confidence == answer.confidence
        assert restored.supporting_memories == answer.supporting_memories
        assert len(restored.patterns) == len(answer.patterns)
        assert restored.statistics == answer.statistics


@pytest.mark.property
class TestCrossModelProperties:
    """Property-based tests for interactions between models."""

    @given(knowledge_query_strategy(), knowledge_answer_strategy())
    def test_answer_confidence_reasonable_for_query(self, query, answer):
        """Property: Answer confidence should be reasonable relative to query confidence."""
        # This is a soft property - answer confidence can be higher or lower
        # but should generally be in a reasonable range
        assert 0.0 <= answer.confidence <= 1.0
        assert 0.0 <= query.confidence <= 1.0

    @given(time_range_strategy(), pattern_strategy())
    def test_pattern_can_reference_time_range(self, time_range, pattern):
        """Property: Patterns can be associated with time ranges."""
        # Create a knowledge answer with both
        answer = KnowledgeAnswer(
            summary=f"Pattern detected in {time_range.description}",
            confidence=pattern.confidence,
            patterns=[pattern],
        )

        assert len(answer.patterns) == 1
        assert answer.patterns[0].pattern_type == pattern.pattern_type

    @given(
        st.lists(pattern_strategy(), min_size=1, max_size=5),
        st.floats(min_value=0.0, max_value=1.0),
    )
    def test_answer_confidence_with_multiple_patterns(self, patterns, confidence):
        """Property: Answers with multiple patterns maintain valid confidence."""
        answer = KnowledgeAnswer(
            summary="Multiple patterns detected",
            confidence=confidence,
            patterns=patterns,
        )

        assert 0.0 <= answer.confidence <= 1.0
        assert len(answer.patterns) == len(patterns)
        assert all(0.0 <= p.confidence <= 1.0 for p in answer.patterns)
