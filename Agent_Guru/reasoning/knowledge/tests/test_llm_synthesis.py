"""
Unit tests for LLM-based answer synthesis in KnowledgeSynthesizer.

Tests cover:
- LLM client initialization
- Prompt template generation
- LLM API calls (mocked)
- Response parsing and validation
- Retry logic for malformed responses
- Fallback to template-based generation
- Supporting memories inclusion
- Confidence scoring

Coverage Target: >80%
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
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
    TimeRange,
)
from Agent_Guru.reasoning.models.memory import Memory, MemoryType


def create_test_memory(
    content: str, memory_type: MemoryType = MemoryType.SEMANTIC, **kwargs
) -> Memory:
    """Helper to create test Memory with valid UUID."""
    defaults = {
        "memory_id": str(uuid.uuid4()),
        "user_id": "user1",
        "content": content,
        "memory_type": memory_type,
        "timestamp": datetime.utcnow(),
        "relevance_score": 0.9,
    }
    defaults.update(kwargs)
    return Memory(**defaults)


class TestLLMClientInitialization:
    """Test LLM client initialization."""

    @patch("Agent_Guru.reasoning.knowledge.synthesizer.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.openai")
    def test_initialize_openai_client(self, mock_openai):
        """Test OpenAI client initialization."""
        mock_openai.OpenAI = Mock()
        memory_retriever = Mock(spec=MemoryRetriever)

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever,
            llm_provider="openai",
            llm_api_key="test-key",
            use_llm_synthesis=True,
        )

        assert synthesizer.llm_client is not None
        mock_openai.OpenAI.assert_called_once_with(api_key="test-key")

    @patch("Agent_Guru.reasoning.knowledge.synthesizer.ANTHROPIC_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.anthropic")
    def test_initialize_anthropic_client(self, mock_anthropic):
        """Test Anthropic client initialization."""
        mock_anthropic.Anthropic = Mock()
        memory_retriever = Mock(spec=MemoryRetriever)

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever,
            llm_provider="anthropic",
            llm_api_key="test-key",
            use_llm_synthesis=True,
        )

        assert synthesizer.llm_client is not None
        mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")

    def test_initialize_without_llm(self):
        """Test initialization without LLM synthesis."""
        memory_retriever = Mock(spec=MemoryRetriever)

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        assert synthesizer.llm_client is None

    @patch("Agent_Guru.reasoning.knowledge.synthesizer.OPENAI_AVAILABLE", False)
    def test_initialize_openai_not_available(self):
        """Test error when OpenAI not available."""
        memory_retriever = Mock(spec=MemoryRetriever)

        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            KnowledgeSynthesizer(
                memory_retriever=memory_retriever,
                llm_provider="openai",
                use_llm_synthesis=True,
            )

    def test_initialize_unsupported_provider(self):
        """Test error with unsupported provider."""
        memory_retriever = Mock(spec=MemoryRetriever)

        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            KnowledgeSynthesizer(
                memory_retriever=memory_retriever,
                llm_provider="unsupported",
                use_llm_synthesis=True,
            )


class TestPromptGeneration:
    """Test synthesis prompt generation."""

    def test_build_synthesis_prompt_temporal(self):
        """Test prompt generation for temporal query."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.95,
        )

        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Called John about project",
                memory_type=MemoryType.EPISODIC,
                timestamp=datetime.utcnow() - timedelta(days=2),
                relevance_score=0.95,
            )
        ]

        patterns = []
        statistics = {"total_count": 1}

        prompt = synthesizer._build_synthesis_prompt(query, memories, patterns, statistics)

        assert "when did I last call John?" in prompt
        assert "temporal" in prompt.lower()
        assert "Called John about project" in prompt
        assert "person" in prompt
        assert "John" in prompt

    def test_build_synthesis_prompt_with_patterns(self):
        """Test prompt generation with patterns."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        query = KnowledgeQuery(
            query_text="when do I usually exercise?",
            query_type=KnowledgeQueryType.PATTERN,
            confidence=0.90,
        )

        memories = []
        patterns = [
            Pattern(
                pattern_type="daily",
                description="Usually exercises in the morning",
                frequency=0.8,
                confidence=0.85,
                examples=["2024-01-01 07:00", "2024-01-02 07:15"],
            )
        ]
        statistics = {"total_count": 10}

        prompt = synthesizer._build_synthesis_prompt(query, memories, patterns, statistics)

        assert "pattern" in prompt.lower()
        assert "daily" in prompt
        assert "Usually exercises in the morning" in prompt
        assert "0.8" in prompt  # frequency

    def test_build_synthesis_prompt_limits_memories(self):
        """Test that prompt limits memories to top 10."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        query = KnowledgeQuery(
            query_text="test query", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        # Create 20 memories
        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content=f"Memory {i}",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9 - i * 0.01,
            )
            for i in range(20)
        ]

        prompt = synthesizer._build_synthesis_prompt(query, memories, [], {})

        # Count how many memories appear in prompt
        memory_count = sum(1 for i in range(20) if f"Memory {i}" in prompt)
        assert memory_count <= 10  # Should limit to 10


class TestLLMResponseParsing:
    """Test LLM response parsing and validation."""

    def test_parse_valid_response(self):
        """Test parsing valid LLM response."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_text = json.dumps(
            {
                "summary": "You last called John 2 days ago",
                "confidence": 0.85,
                "reasoning": "Based on recent call history",
                "key_insights": ["Regular contact with John", "Usually calls in evening"],
            }
        )

        parsed = synthesizer._parse_llm_synthesis_response(response_text)

        assert isinstance(parsed, LLMSynthesisResponse)
        assert parsed.summary == "You last called John 2 days ago"
        assert parsed.confidence == 0.85
        assert parsed.reasoning == "Based on recent call history"
        assert len(parsed.key_insights) == 2

    def test_parse_minimal_response(self):
        """Test parsing minimal valid response."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_text = json.dumps({"summary": "Test answer", "confidence": 0.7})

        parsed = synthesizer._parse_llm_synthesis_response(response_text)

        assert parsed.summary == "Test answer"
        assert parsed.confidence == 0.7
        assert parsed.reasoning == ""
        assert parsed.key_insights == []

    def test_parse_invalid_json(self):
        """Test error on invalid JSON."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_text = "not valid json"

        with pytest.raises(json.JSONDecodeError):
            synthesizer._parse_llm_synthesis_response(response_text)

    def test_parse_missing_required_fields(self):
        """Test error on missing required fields."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_text = json.dumps({"confidence": 0.8})  # Missing summary

        with pytest.raises(ValidationError):
            synthesizer._parse_llm_synthesis_response(response_text)

    def test_parse_invalid_confidence(self):
        """Test error on invalid confidence value."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        response_text = json.dumps({"summary": "Test", "confidence": 1.5})  # > 1.0

        with pytest.raises(ValidationError):
            synthesizer._parse_llm_synthesis_response(response_text)


class TestLLMSynthesis:
    """Test end-to-end LLM synthesis."""

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.openai")
    async def test_synthesize_answer_with_llm_success(self, mock_openai):
        """Test successful LLM synthesis."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "summary": "You last called John 2 days ago",
                            "confidence": 0.85,
                            "reasoning": "Based on call history",
                            "key_insights": ["Regular contact"],
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create = Mock(return_value=mock_response)
        mock_openai.OpenAI = Mock(return_value=mock_client)

        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever,
            llm_provider="openai",
            llm_api_key="test-key",
            use_llm_synthesis=True,
        )

        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            confidence=0.95,
        )

        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Called John",
                memory_type=MemoryType.EPISODIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
        ]

        answer = await synthesizer.synthesize_answer_with_llm(query, memories, [], {})

        assert isinstance(answer, KnowledgeAnswer)
        assert "You last called John 2 days ago" in answer.summary
        assert 0.0 <= answer.confidence <= 1.0
        assert len(answer.supporting_memories) > 0

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.openai")
    async def test_synthesize_answer_with_llm_timeout(self, mock_openai):
        """Test LLM synthesis timeout fallback."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.OpenAI = Mock(return_value=mock_client)

        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever,
            llm_provider="openai",
            llm_api_key="test-key",
            llm_timeout_ms=100.0,
            llm_max_retries=1,  # Only 1 attempt (no retries)
            use_llm_synthesis=True,
        )

        # Mock the _call_llm_for_synthesis method to raise TimeoutError directly
        async def timeout_llm_call(prompt):
            raise asyncio.TimeoutError("Simulated timeout")

        synthesizer._call_llm_for_synthesis = timeout_llm_call

        # Mock generate_answer to avoid recursion issue
        def mock_generate_answer(query, memories, patterns, statistics):
            return KnowledgeAnswer(
                summary="Fallback answer",
                confidence=0.5,
                supporting_memories=[],
                patterns=[],
                statistics={},
            )

        synthesizer.generate_answer = mock_generate_answer

        query = KnowledgeQuery(
            query_text="test query", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Test memory",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
        ]

        # Should fall back to template-based generation after timeout
        answer = await synthesizer.synthesize_answer_with_llm(query, memories, [], {})

        assert isinstance(answer, KnowledgeAnswer)
        assert answer.summary == "Fallback answer"  # Should use mocked fallback

    @pytest.mark.asyncio
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.OPENAI_AVAILABLE", True)
    @patch("Agent_Guru.reasoning.knowledge.synthesizer.openai")
    async def test_synthesize_answer_with_llm_malformed_response(self, mock_openai):
        """Test LLM synthesis with malformed response."""
        # Mock OpenAI client that returns malformed JSON
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="not valid json"))]
        mock_client.chat.completions.create = Mock(return_value=mock_response)
        mock_openai.OpenAI = Mock(return_value=mock_client)

        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever,
            llm_provider="openai",
            llm_api_key="test-key",
            llm_max_retries=1,  # Only 1 retry to speed up test
            use_llm_synthesis=True,
        )

        # Mock generate_answer to avoid recursion issue
        def mock_generate_answer(query, memories, patterns, statistics):
            return KnowledgeAnswer(
                summary="Fallback answer after malformed response",
                confidence=0.5,
                supporting_memories=[],
                patterns=[],
                statistics={},
            )

        synthesizer.generate_answer = mock_generate_answer

        query = KnowledgeQuery(
            query_text="test query", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Test memory",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
        ]

        # Should fall back to template-based generation after retries
        answer = await synthesizer.synthesize_answer_with_llm(query, memories, [], {})

        assert isinstance(answer, KnowledgeAnswer)
        assert "Fallback answer" in answer.summary  # Should use mocked fallback


class TestSupportingMemories:
    """Test supporting memories inclusion."""

    def test_create_answer_includes_supporting_memories(self):
        """Test that answer includes supporting memory IDs."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary="Test answer", confidence=0.85, reasoning="Test", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        memory_ids = [str(uuid.uuid4()) for _ in range(10)]
        memories = [
            Memory(
                memory_id=memory_ids[i],
                user_id="user1",
                content=f"Memory {i}",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9 - i * 0.1,
            )
            for i in range(10)
        ]

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        assert len(answer.supporting_memories) == 5  # Top 5
        assert answer.supporting_memories[0] == memory_ids[0]  # Most relevant first
        assert answer.supporting_memories[4] == memory_ids[4]

    def test_create_answer_adjusts_confidence_no_memories(self):
        """Test confidence adjustment when no memories."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary="Test answer", confidence=0.9, reasoning="Test", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, [], [], {})

        # Confidence should be reduced (0.9 * 0.5 = 0.45)
        assert answer.confidence < 0.9
        assert answer.confidence == 0.45

    def test_create_answer_adjusts_confidence_few_memories(self):
        """Test confidence adjustment with few memories."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary="Test answer", confidence=0.9, reasoning="Test", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.FACTUAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Memory 1",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            ),
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Memory 2",
                memory_type=MemoryType.SEMANTIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.8,
            ),
        ]

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        # Confidence should be reduced (0.9 * 0.8 = 0.72)
        assert answer.confidence < 0.9
        assert answer.confidence == 0.72


class TestConfidenceIndicator:
    """Test confidence indicator in summary."""

    def test_low_confidence_adds_indicator(self):
        """Test that low confidence adds indicator to summary."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, confidence_threshold=0.7, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary="You called John yesterday", confidence=0.5, reasoning="Test", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.TEMPORAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Called John",
                memory_type=MemoryType.EPISODIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
        ]

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        assert "I'm not very confident" in answer.summary
        assert "you called john yesterday" in answer.summary.lower()

    def test_high_confidence_no_indicator(self):
        """Test that high confidence doesn't add indicator."""
        memory_retriever = Mock(spec=MemoryRetriever)
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=memory_retriever, confidence_threshold=0.6, use_llm_synthesis=False
        )

        llm_response = LLMSynthesisResponse(
            summary="You called John yesterday", confidence=0.9, reasoning="Test", key_insights=[]
        )

        query = KnowledgeQuery(
            query_text="test", query_type=KnowledgeQueryType.TEMPORAL, confidence=0.9
        )

        memories = [
            Memory(
                memory_id=str(uuid.uuid4()),
                user_id="user1",
                content="Called John",
                memory_type=MemoryType.EPISODIC,
                timestamp=datetime.utcnow(),
                relevance_score=0.9,
            )
        ]

        answer = synthesizer._create_answer_from_llm_response(llm_response, query, memories, [], {})

        assert "I'm not very confident" not in answer.summary
        assert answer.summary == "You called John yesterday"
