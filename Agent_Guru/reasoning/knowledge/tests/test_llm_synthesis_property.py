"""
Property-based tests for LLM-based answer synthesis.

Tests universal properties that should hold across all inputs:
- Prompt generation always produces valid strings
- Response parsing handles all JSON structures
- Confidence scores always in valid range
- Supporting memories always limited to top 5
- Retry logic always terminates

Uses Hypothesis for property-based testing with 100 iterations per property.

Coverage Target: Complement unit tests for edge cases
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from Agent_Guru.reasoning.knowledge.synthesizer import (
    KnowledgeSynthesizer,
    LLMSynthesisResponse,
)
from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeAnswer,
    KnowledgeQuery,
    KnowledgeQueryType,
    Pattern,
)
from Agent_Guru.reasoning.models.memory import Memory, MemoryType


# Hypothesis strategies
@st.composite
def knowledge_query_strategy(draw):
    """Generate random KnowledgeQuery."""
    query_text = draw(
        st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_characters="\n\r\t "))
    )
    if not query_text or query_text.isspace():
        query_text = "test query"  # Fallback to valid query
    query_type = draw(st.sampled_from(list(KnowledgeQueryType)))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))

    return KnowledgeQuery(query_text=query_text, query_type=query_type, confidence=confidence)


@st.composite
def memory_strategy(draw):
    """Generate random Memory."""
    memory_id = str(uuid.uuid4())
    user_id = draw(st.text(min_size=1, max_size=50))
    content = draw(st.text(min_size=1, max_size=500))
    memory_type = draw(st.sampled_from(list(MemoryType)))
    days_ago = draw(st.integers(min_value=0, max_value=365))
    timestamp = datetime.utcnow() - timedelta(days=days_ago)
    relevance_score = draw(st.floats(min_value=0.0, max_value=1.0))

    return Memory(
        memory_id=memory_id,
        user_id=user_id,
        content=content,
        memory_type=memory_type,
        timestamp=timestamp,
        relevance_score=relevance_score,
    )


@st.composite
def pattern_strategy(draw):
    """Generate random Pattern."""
    pattern_type = draw(st.sampled_from(["daily", "weekly", "monthly"]))
    description = draw(st.text(min_size=1, max_size=200))
    frequency = draw(st.floats(min_value=0.0, max_value=1.0))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    examples = draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5))

    return Pattern(
        pattern_type=pattern_type,
        description=description,
        frequency=frequency,
        confidence=confidence,
        examples=examples,
    )


class TestPromptGenerationProperties:
    """Property-based tests for prompt generation."""

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
        patterns=st.lists(pattern_strategy(), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_build_prompt_always_returns_string(self, query, memories, patterns):
        """Property: Prompt generation always returns non-empty string."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        statistics = {"total_count": len(memories)}

        prompt = synthesizer._build_synthesis_prompt(query, memories, patterns, statistics)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert query.query_text in prompt

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_build_prompt_limits_memories(self, query, memories):
        """Property: Prompt always limits memories to 10."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        prompt = synthesizer._build_synthesis_prompt(query, memories, [], {})

        # Count memory references in prompt (approximate)
        # Each memory should appear as a JSON object in the prompt
        memory_count = prompt.count('"content":')
        assert memory_count <= 10

    @given(
        query=knowledge_query_strategy(),
        memories=st.lists(memory_strategy(), min_size=1, max_size=10),
    )
    @settings(max_examples=100)
    def test_build_prompt_includes_query_type(self, query, memories):
        """Property: Prompt always includes query type."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        prompt = synthesizer._build_synthesis_prompt(query, memories, [], {})

        assert query.query_type.value in prompt


class TestResponseParsingProperties:
    """Property-based tests for response parsing."""

    @given(
        summary=st.text(min_size=1, max_size=500),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        reasoning=st.text(min_size=0, max_size=200),
        key_insights=st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_parse_valid_response_always_succeeds(
        self, summary, confidence, reasoning, key_insights
    ):
        """Property: Valid JSON response always parses successfully."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_data = {
            "summary": summary,
            "confidence": confidence,
            "reasoning": reasoning,
            "key_insights": key_insights,
        }
        response_text = json.dumps(response_data)

        parsed = synthesizer._parse_llm_synthesis_response(response_text)

        assert isinstance(parsed, LLMSynthesisResponse)
        assert parsed.summary == summary
        assert parsed.confidence == confidence
        assert parsed.reasoning == reasoning
        assert parsed.key_insights == key_insights

    @given(
        summary=st.text(min_size=1, max_size=500),
        confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_parse_minimal_response_always_succeeds(self, summary, confidence):
        """Property: Minimal valid response always parses successfully."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_data = {"summary": summary, "confidence": confidence}
        response_text = json.dumps(response_data)

        parsed = synthesizer._parse_llm_synthesis_response(response_text)

        assert isinstance(parsed, LLMSynthesisResponse)
        assert parsed.summary == summary
        assert parsed.confidence == confidence

    @given(confidence=st.floats(min_value=-10.0, max_value=-0.01))
    @settings(max_examples=50)
    def test_parse_negative_confidence_fails(self, confidence):
        """Property: Negative confidence always fails validation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_data = {"summary": "Test", "confidence": confidence}
        response_text = json.dumps(response_data)

        with pytest.raises(ValidationError):
            synthesizer._parse_llm_synthesis_response(response_text)

    @given(confidence=st.floats(min_value=1.01, max_value=10.0))
    @settings(max_examples=50)
    def test_parse_high_confidence_fails(self, confidence):
        """Property: Confidence > 1.0 always fails validation."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_data = {"summary": "Test", "confidence": confidence}
        response_text = json.dumps(response_data)

        with pytest.raises(ValidationError):
            synthesizer._parse_llm_synthesis_response(response_text)


class TestAnswerCreationProperties:
    """Property-based tests for answer creation from LLM response."""

    @given(
        summary=st.text(min_size=1, max_size=500),
        llm_confidence=st.floats(min_value=0.0, max_value=1.0),
        memories=st.lists(memory_strategy(), min_size=0, max_size=20),
    )
    @settings(max_examples=100)
    def test_create_answer_confidence_always_valid(self, summary, llm_confidence, memories):
        """Property: Created answer always has valid confidence (0.0-1.0)."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary=summary, confidence=llm_confidence, reasoning="", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        assert isinstance(answer, KnowledgeAnswer)
        assert 0.0 <= answer.confidence <= 1.0

    @given(
        summary=st.text(min_size=1, max_size=500),
        llm_confidence=st.floats(min_value=0.0, max_value=1.0),
        memories=st.lists(memory_strategy(), min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_create_answer_supporting_memories_limited(self, summary, llm_confidence, memories):
        """Property: Supporting memories always limited to 5."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary=summary, confidence=llm_confidence, reasoning="", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        assert len(answer.supporting_memories) <= 5

    @given(
        summary=st.text(min_size=1, max_size=500),
        llm_confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_create_answer_no_memories_reduces_confidence(self, summary, llm_confidence):
        """Property: No memories always reduces confidence."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary=summary, confidence=llm_confidence, reasoning="", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, [], [], {})

        # Confidence should be reduced (multiplied by 0.5)
        expected_confidence = max(0.0, min(1.0, llm_confidence * 0.5))
        assert answer.confidence == round(expected_confidence, 2)

    @given(
        summary=st.text(min_size=1, max_size=500),
        llm_confidence=st.floats(min_value=0.0, max_value=1.0),
        num_memories=st.integers(min_value=1, max_value=2),
    )
    @settings(max_examples=100)
    def test_create_answer_few_memories_reduces_confidence(
        self, summary, llm_confidence, num_memories
    ):
        """Property: Few memories (1-2) always reduces confidence."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary=summary, confidence=llm_confidence, reasoning="", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id=f"mem{i}",
                user_id="user1",
                content=f"Memory {i}",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
            for i in range(num_memories)
        ]

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        # Confidence should be reduced (multiplied by 0.8)
        expected_confidence = max(0.0, min(1.0, llm_confidence * 0.8))
        assert answer.confidence == round(expected_confidence, 2)


class TestConfidenceIndicatorProperties:
    """Property-based tests for confidence indicator."""

    @given(
        summary=st.text(min_size=1, max_size=500),
        llm_confidence=st.floats(min_value=0.0, max_value=0.59),
        threshold=st.floats(min_value=0.6, max_value=0.9),
    )
    @settings(max_examples=100)
    def test_low_confidence_always_adds_indicator(self, summary, llm_confidence, threshold):
        """Property: Confidence below threshold always adds indicator."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever,
            confidence_threshold=threshold,
            use_llm_synthesis=False,
        )

        llm_response = LLMSynthesisResponse(
            summary=summary, confidence=llm_confidence, reasoning="", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id="mem1",
                user_id="user1",
                content="Test",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
        ]

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        # Should add confidence indicator
        assert "I'm not very confident" in answer.summary

    @given(
        summary=st.text(min_size=1, max_size=500),
        llm_confidence=st.floats(min_value=0.7, max_value=1.0),
        threshold=st.floats(min_value=0.5, max_value=0.69),
    )
    @settings(max_examples=100)
    def test_high_confidence_never_adds_indicator(self, summary, llm_confidence, threshold):
        """Property: Confidence above threshold never adds indicator."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever,
            confidence_threshold=threshold,
            use_llm_synthesis=False,
        )

        llm_response = LLMSynthesisResponse(
            summary=summary, confidence=llm_confidence, reasoning="", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id="mem1",
                user_id="user1",
                content="Test",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
        ]

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        # Should NOT add confidence indicator
        assert "I'm not very confident" not in answer.summary
        assert answer.summary == summary
