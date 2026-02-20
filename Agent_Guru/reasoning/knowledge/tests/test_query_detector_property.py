"""
Property-based tests for KnowledgeQueryDetector.

Uses Hypothesis to test invariants and edge cases across many inputs.
Validates Requirements: 38.1, 38.5, 38.6, 38.7

Target: 100 iterations per property
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.knowledge.query_detector import KnowledgeQueryDetector
from Agent_Guru.reasoning.models.knowledge import KnowledgeQueryType


class TestKnowledgeQueryDetectorProperties:
    """Property-based tests for KnowledgeQueryDetector."""

    @given(query_text=st.text(min_size=0, max_size=1000))
    @settings(max_examples=100)
    def test_detection_returns_valid_or_none(self, query_text):
        """Property: Detection returns valid KnowledgeQuery or None. **Validates: Requirements 38.1**"""
        detector = KnowledgeQueryDetector()
        result = detector.detect_knowledge_query(query_text, use_llm_fallback=False)

        if result is not None:
            assert hasattr(result, "query_type")
            assert isinstance(result.query_type, KnowledgeQueryType)
            assert isinstance(result.query_text, str)
            assert isinstance(result.confidence, float)
            assert isinstance(result.entities, dict)

    @given(
        query_text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=5,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_confidence_in_valid_range(self, query_text):
        """Property: Confidence is between 0.0 and 1.0. **Validates: Requirements 38.1**"""
        detector = KnowledgeQueryDetector()
        result = detector.detect_knowledge_query(query_text, use_llm_fallback=False)

        if result is not None:
            assert 0.0 <= result.confidence <= 1.0

    @given(
        query_text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=5,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_query_text_preserved(self, query_text):
        """Property: Query text is preserved (stripped). **Validates: Requirements 38.1**"""
        detector = KnowledgeQueryDetector()
        result = detector.detect_knowledge_query(query_text, use_llm_fallback=False)

        if result is not None:
            assert result.query_text == query_text.strip()

    @given(
        query_text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=5,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_classification_is_deterministic(self, query_text):
        """Property: Classification is deterministic. **Validates: Requirements 38.5**"""
        detector = KnowledgeQueryDetector()
        result1 = detector.classify_query_type(query_text)
        result2 = detector.classify_query_type(query_text)
        result3 = detector.classify_query_type(query_text)

        assert result1 == result2 == result3

    @given(whitespace=st.text(alphabet=" \t\n\r", min_size=0, max_size=100))
    @settings(max_examples=100)
    def test_empty_queries_return_none(self, whitespace):
        """Property: Empty/whitespace queries return None. **Validates: Requirements 38.1**"""
        detector = KnowledgeQueryDetector()
        result = detector.detect_knowledge_query(whitespace, use_llm_fallback=False)

        assert result is None

    @given(
        query_text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=5,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_entities_non_empty(self, query_text):
        """Property: Entity values are non-empty strings. **Validates: Requirements 38.7**"""
        detector = KnowledgeQueryDetector()
        result = detector.detect_knowledge_query(query_text, use_llm_fallback=False)

        if result is not None and result.entities:
            for entity_type, entity_value in result.entities.items():
                assert isinstance(entity_value, str)
                assert len(entity_value) > 0
                assert entity_value.strip() != ""

    @given(
        query_text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=5,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_time_range_start_before_end(self, query_text):
        """Property: Time range start <= end. **Validates: Requirements 38.6**"""
        detector = KnowledgeQueryDetector()
        time_range = detector.extract_time_range(query_text)

        if time_range is not None:
            assert time_range.start <= time_range.end

    @given(
        query_text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=5,
            max_size=200,
        )
    )
    @settings(max_examples=50)
    def test_detection_is_fast(self, query_text):
        """Property: Detection completes quickly (<50ms). **Validates: Requirements 38.1**"""
        import time

        detector = KnowledgeQueryDetector()
        start = time.perf_counter()
        detector.detect_knowledge_query(query_text, use_llm_fallback=False)
        end = time.perf_counter()

        elapsed = end - start
        assert elapsed < 0.05  # 50ms

    @given(
        query_text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=5,
            max_size=200,
        )
    )
    @settings(max_examples=100)
    def test_query_type_is_valid(self, query_text):
        """Property: Query type is one of valid types. **Validates: Requirements 38.5**"""
        detector = KnowledgeQueryDetector()
        result = detector.detect_knowledge_query(query_text, use_llm_fallback=False)

        if result is not None:
            valid_types = {
                KnowledgeQueryType.TEMPORAL,
                KnowledgeQueryType.AGGREGATION,
                KnowledgeQueryType.PATTERN,
                KnowledgeQueryType.FACTUAL,
            }
            assert result.query_type in valid_types
