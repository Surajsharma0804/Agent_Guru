"""
Unit tests for knowledge query data models.

Tests cover:
- Model creation and validation
- Field validators
- Helper methods
- JSON serialization
- Edge cases and error handling

Coverage target: 80%+
"""

import json
from datetime import datetime

import pytest

from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeAnswer,
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
    TimeRange,
)


class TestTimeRange:
    """Unit tests for TimeRange model."""

    def test_create_time_range(self):
        """Test creating a valid time range."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 31, 23, 59, 59)
        time_range = TimeRange(start=start, end=end, description="January 2024")

        assert time_range.start == start  # nosec B101
        assert time_range.end == end  # nosec B101
        assert time_range.description == "January 2024"  # nosec B101

    def test_time_range_start_after_end_fails(self):
        """Test that start after end raises validation error."""
        start = datetime(2024, 1, 31, 23, 59, 59)
        end = datetime(2024, 1, 1, 0, 0, 0)

        with pytest.raises(ValueError, match="Start time .* must be before or equal to end time"):
            TimeRange(start=start, end=end, description="Invalid range")

    def test_time_range_empty_description_fails(self):
        """Test that empty description raises validation error."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 31, 23, 59, 59)

        with pytest.raises(ValueError, match="Description cannot be empty"):
            TimeRange(start=start, end=end, description="   ")

    def test_time_range_last_week(self):
        """Test last_week helper method."""
        time_range = TimeRange.last_week()

        assert time_range.description == "last week"  # nosec B101
        assert time_range.end > time_range.start  # nosec B101
        assert (time_range.end - time_range.start).days == 7  # nosec B101

    def test_time_range_last_month(self):
        """Test last_month helper method."""
        time_range = TimeRange.last_month()

        assert time_range.description == "last month"  # nosec B101
        assert time_range.end > time_range.start  # nosec B101
        assert (time_range.end - time_range.start).days == 30  # nosec B101

    def test_time_range_last_year(self):
        """Test last_year helper method."""
        time_range = TimeRange.last_year()

        assert time_range.description == "last year"  # nosec B101
        assert time_range.end > time_range.start  # nosec B101
        assert (time_range.end - time_range.start).days == 365  # nosec B101

    def test_time_range_last_n_days(self):
        """Test last_n_days helper method."""
        time_range = TimeRange.last_n_days(14)

        assert time_range.description == "last 14 days"  # nosec B101
        assert time_range.end > time_range.start  # nosec B101
        assert (time_range.end - time_range.start).days == 14  # nosec B101

    def test_time_range_last_n_days_negative_fails(self):
        """Test that negative days raises validation error."""
        with pytest.raises(ValueError, match="Number of days must be positive"):
            TimeRange.last_n_days(-5)

    def test_time_range_last_n_days_zero_fails(self):
        """Test that zero days raises validation error."""
        with pytest.raises(ValueError, match="Number of days must be positive"):
            TimeRange.last_n_days(0)

    def test_time_range_today(self):
        """Test today helper method."""
        time_range = TimeRange.today()

        assert time_range.description == "today"  # nosec B101
        assert time_range.end > time_range.start  # nosec B101
        assert time_range.start.hour == 0  # nosec B101
        assert time_range.start.minute == 0  # nosec B101
        assert time_range.start.second == 0  # nosec B101

    def test_time_range_yesterday(self):
        """Test yesterday helper method."""
        time_range = TimeRange.yesterday()

        assert time_range.description == "yesterday"  # nosec B101
        assert time_range.end > time_range.start  # nosec B101
        assert (time_range.end - time_range.start).days == 1  # nosec B101

    def test_time_range_json_serialization(self):
        """Test JSON serialization of time range."""
        time_range = TimeRange.last_week()
        json_str = time_range.model_dump_json()
        data = json.loads(json_str)

        assert "start" in data  # nosec B101
        assert "end" in data  # nosec B101
        assert "description" in data  # nosec B101
        assert data["description"] == "last week"  # nosec B101


class TestKnowledgeQuery:
    """Unit tests for KnowledgeQuery model."""

    def test_create_knowledge_query(self):
        """Test creating a valid knowledge query."""
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )

        assert query.query_text == "when did I last call John?"  # nosec B101
        assert query.query_type == KnowledgeQueryType.TEMPORAL  # nosec B101
        assert query.time_range is not None  # nosec B101
        assert query.entities == {"person": "John", "action": "call"}  # nosec B101
        assert query.confidence == 0.95  # nosec B101

    def test_knowledge_query_empty_text_fails(self):
        """Test that empty query text raises validation error."""
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            KnowledgeQuery(
                query_text="   ",
                query_type=KnowledgeQueryType.TEMPORAL,
                confidence=0.95,
            )

    def test_knowledge_query_confidence_out_of_range_fails(self):
        """Test that confidence out of range raises validation error."""
        with pytest.raises(ValueError):
            KnowledgeQuery(
                query_text="test query",
                query_type=KnowledgeQueryType.TEMPORAL,
                confidence=1.5,
            )

        with pytest.raises(ValueError):
            KnowledgeQuery(
                query_text="test query",
                query_type=KnowledgeQueryType.TEMPORAL,
                confidence=-0.1,
            )

    def test_knowledge_query_temporal_auto_assigns_time_range(self):
        """Test that temporal queries auto-assign time range if missing."""
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            confidence=0.95,
        )

        assert query.time_range is not None  # nosec B101
        assert query.time_range.description == "last month"  # nosec B101

    def test_knowledge_query_non_temporal_no_time_range(self):
        """Test that non-temporal queries don't require time range."""
        query = KnowledgeQuery(
            query_text="who do I message most?",
            query_type=KnowledgeQueryType.AGGREGATION,
            confidence=0.95,
        )

        assert query.time_range is None  # nosec B101

    def test_knowledge_query_all_types(self):
        """Test creating queries with all query types."""
        for query_type in KnowledgeQueryType:
            query = KnowledgeQuery(
                query_text=f"test {query_type.value} query",
                query_type=query_type,
                confidence=0.9,
            )
            assert query.query_type == query_type  # nosec B101

    def test_knowledge_query_json_serialization(self):
        """Test JSON serialization of knowledge query."""
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            entities={"person": "John"},
            confidence=0.95,
        )
        json_str = query.model_dump_json()
        data = json.loads(json_str)

        assert data["query_text"] == "when did I last call John?"  # nosec B101
        assert data["query_type"] == "temporal"  # nosec B101
        assert data["entities"] == {"person": "John"}  # nosec B101
        assert data["confidence"] == 0.95  # nosec B101


class TestPattern:
    """Unit tests for Pattern model."""

    def test_create_pattern(self):
        """Test creating a valid pattern."""
        pattern = Pattern(
            pattern_type="daily",
            description="User checks email every morning at 9am",
            frequency=0.95,
            confidence=0.92,
            examples=["2024-01-15 09:00", "2024-01-16 09:05"],
        )

        assert pattern.pattern_type == "daily"  # nosec B101
        assert pattern.description == "User checks email every morning at 9am"  # nosec B101
        assert pattern.frequency == 0.95  # nosec B101
        assert pattern.confidence == 0.92  # nosec B101
        assert len(pattern.examples) == 2  # nosec B101

    def test_pattern_invalid_type_fails(self):
        """Test that invalid pattern type raises validation error."""
        with pytest.raises(ValueError, match="pattern_type must be one of"):
            Pattern(
                pattern_type="invalid_type",
                description="Test pattern",
                frequency=0.9,
                confidence=0.8,
            )

    def test_pattern_valid_types(self):
        """Test all valid pattern types."""
        valid_types = ["daily", "weekly", "monthly", "situational", "temporal", "contextual"]
        for pattern_type in valid_types:
            pattern = Pattern(
                pattern_type=pattern_type,
                description="Test pattern",
                frequency=0.9,
                confidence=0.8,
            )
            assert pattern.pattern_type == pattern_type  # nosec B101

    def test_pattern_empty_description_fails(self):
        """Test that empty description raises validation error."""
        with pytest.raises(ValueError, match="Description cannot be empty"):
            Pattern(
                pattern_type="daily",
                description="   ",
                frequency=0.9,
                confidence=0.8,
            )

    def test_pattern_frequency_out_of_range_fails(self):
        """Test that frequency out of range raises validation error."""
        with pytest.raises(ValueError):
            Pattern(
                pattern_type="daily",
                description="Test pattern",
                frequency=1.5,
                confidence=0.8,
            )

        with pytest.raises(ValueError):
            Pattern(
                pattern_type="daily",
                description="Test pattern",
                frequency=-0.1,
                confidence=0.8,
            )

    def test_pattern_confidence_out_of_range_fails(self):
        """Test that confidence out of range raises validation error."""
        with pytest.raises(ValueError):
            Pattern(
                pattern_type="daily",
                description="Test pattern",
                frequency=0.9,
                confidence=1.5,
            )

        with pytest.raises(ValueError):
            Pattern(
                pattern_type="daily",
                description="Test pattern",
                frequency=0.9,
                confidence=-0.1,
            )

    def test_pattern_empty_examples_fails(self):
        """Test that empty example strings raise validation error."""
        with pytest.raises(ValueError, match="Examples cannot be empty"):
            Pattern(
                pattern_type="daily",
                description="Test pattern",
                frequency=0.9,
                confidence=0.8,
                examples=["valid", "   ", "also valid"],
            )

    def test_pattern_no_examples(self):
        """Test pattern with no examples."""
        pattern = Pattern(
            pattern_type="daily",
            description="Test pattern",
            frequency=0.9,
            confidence=0.8,
        )
        assert pattern.examples == []  # nosec B101

    def test_pattern_json_serialization(self):
        """Test JSON serialization of pattern."""
        pattern = Pattern(
            pattern_type="daily",
            description="User checks email every morning",
            frequency=0.95,
            confidence=0.92,
            examples=["2024-01-15 09:00"],
        )
        json_str = pattern.model_dump_json()
        data = json.loads(json_str)

        assert data["pattern_type"] == "daily"  # nosec B101
        assert data["description"] == "User checks email every morning"  # nosec B101
        assert data["frequency"] == 0.95  # nosec B101
        assert data["confidence"] == 0.92  # nosec B101
        assert len(data["examples"]) == 1  # nosec B101


class TestKnowledgeAnswer:
    """Unit tests for KnowledgeAnswer model."""

    def test_create_knowledge_answer(self):
        """Test creating a valid knowledge answer."""
        pattern = Pattern(
            pattern_type="weekly",
            description="You typically call John on Mondays",
            frequency=0.85,
            confidence=0.90,
            examples=["2024-01-08", "2024-01-15"],
        )

        answer = KnowledgeAnswer(
            summary="You last called John 3 days ago on January 15th at 2:30pm",
            confidence=0.98,
            supporting_memories=["mem_123", "mem_456"],
            patterns=[pattern],
            statistics={"total_calls": 15, "avg_duration": 300},
            visualization_data={"type": "timeline", "data": []},
        )

        assert answer.summary == "You last called John 3 days ago on January 15th at 2:30pm"  # nosec B101
        assert answer.confidence == 0.98  # nosec B101
        assert len(answer.supporting_memories) == 2  # nosec B101
        assert len(answer.patterns) == 1  # nosec B101
        assert answer.statistics["total_calls"] == 15  # nosec B101
        assert answer.visualization_data is not None  # nosec B101

    def test_knowledge_answer_empty_summary_fails(self):
        """Test that empty summary raises validation error."""
        with pytest.raises(ValueError, match="Summary cannot be empty"):
            KnowledgeAnswer(
                summary="   ",
                confidence=0.98,
            )

    def test_knowledge_answer_confidence_out_of_range_fails(self):
        """Test that confidence out of range raises validation error."""
        with pytest.raises(ValueError):
            KnowledgeAnswer(
                summary="Test answer",
                confidence=1.5,
            )

        with pytest.raises(ValueError):
            KnowledgeAnswer(
                summary="Test answer",
                confidence=-0.1,
            )

    def test_knowledge_answer_empty_memory_ids_fails(self):
        """Test that empty memory IDs raise validation error."""
        with pytest.raises(ValueError, match="Memory IDs cannot be empty"):
            KnowledgeAnswer(
                summary="Test answer",
                confidence=0.98,
                supporting_memories=["mem_123", "   ", "mem_456"],
            )

    def test_knowledge_answer_too_many_patterns_fails(self):
        """Test that too many patterns raise validation error."""
        patterns = [
            Pattern(
                pattern_type="daily",
                description=f"Pattern {i}",
                frequency=0.9,
                confidence=0.8,
            )
            for i in range(11)
        ]

        with pytest.raises(ValueError, match="Too many patterns"):
            KnowledgeAnswer(
                summary="Test answer",
                confidence=0.98,
                patterns=patterns,
            )

    def test_knowledge_answer_no_optional_fields(self):
        """Test knowledge answer with only required fields."""
        answer = KnowledgeAnswer(
            summary="Test answer",
            confidence=0.98,
        )

        assert answer.summary == "Test answer"  # nosec B101
        assert answer.confidence == 0.98  # nosec B101
        assert answer.supporting_memories == []  # nosec B101
        assert answer.patterns == []  # nosec B101
        assert answer.statistics == {}  # nosec B101
        assert answer.visualization_data is None  # nosec B101

    def test_knowledge_answer_json_serialization(self):
        """Test JSON serialization of knowledge answer."""
        answer = KnowledgeAnswer(
            summary="You last called John 3 days ago",
            confidence=0.98,
            supporting_memories=["mem_123"],
            statistics={"total_calls": 15},
        )
        json_str = answer.model_dump_json()
        data = json.loads(json_str)

        assert data["summary"] == "You last called John 3 days ago"  # nosec B101
        assert data["confidence"] == 0.98  # nosec B101
        assert len(data["supporting_memories"]) == 1  # nosec B101
        assert data["statistics"]["total_calls"] == 15  # nosec B101


class TestKnowledgeQueryType:
    """Unit tests for KnowledgeQueryType enum."""

    def test_all_query_types_exist(self):
        """Test that all expected query types exist."""
        assert KnowledgeQueryType.TEMPORAL == "temporal"  # nosec B101
        assert KnowledgeQueryType.AGGREGATION == "aggregation"  # nosec B101
        assert KnowledgeQueryType.PATTERN == "pattern"  # nosec B101
        assert KnowledgeQueryType.FACTUAL == "factual"  # nosec B101

    def test_query_type_count(self):
        """Test that we have exactly 4 query types."""
        assert len(list(KnowledgeQueryType)) == 4  # nosec B101


class TestIntegration:
    """Integration tests for knowledge models."""

    def test_complete_knowledge_query_flow(self):
        """Test complete flow from query to answer."""
        # Create query
        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )

        # Create pattern
        pattern = Pattern(
            pattern_type="weekly",
            description="You typically call John on Mondays",
            frequency=0.85,
            confidence=0.90,
            examples=["2024-01-08", "2024-01-15", "2024-01-22"],
        )

        # Create answer
        answer = KnowledgeAnswer(
            summary="You last called John 3 days ago on January 15th at 2:30pm",
            confidence=0.98,
            supporting_memories=["mem_123", "mem_456"],
            patterns=[pattern],
            statistics={"total_calls": 15, "avg_duration": 300, "last_call_days_ago": 3},
            visualization_data={"type": "timeline", "data": []},
        )

        # Verify all components work together
        assert query.query_type == KnowledgeQueryType.TEMPORAL  # nosec B101
        assert query.time_range is not None  # nosec B101
        assert len(answer.patterns) == 1  # nosec B101
        assert answer.patterns[0].pattern_type == "weekly"  # nosec B101
        assert answer.confidence > query.confidence * 0.9  # Answer confidence should be high  # nosec B101

    def test_json_round_trip(self):
        """Test JSON serialization and deserialization."""
        # Create complex answer
        pattern = Pattern(
            pattern_type="daily",
            description="Morning routine",
            frequency=0.95,
            confidence=0.92,
            examples=["09:00", "09:05"],
        )

        answer = KnowledgeAnswer(
            summary="Test summary",
            confidence=0.98,
            supporting_memories=["mem_1", "mem_2"],
            patterns=[pattern],
            statistics={"count": 10},
        )

        # Serialize to JSON
        json_str = answer.model_dump_json()

        # Deserialize from JSON
        data = json.loads(json_str)
        restored = KnowledgeAnswer(**data)

        # Verify round trip
        assert restored.summary == answer.summary  # nosec B101
        assert restored.confidence == answer.confidence  # nosec B101
        assert len(restored.patterns) == len(answer.patterns)  # nosec B101
        assert restored.patterns[0].pattern_type == answer.patterns[0].pattern_type  # nosec B101
