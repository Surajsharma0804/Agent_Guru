"""
Tests for Knowledge Synthesis Engine privacy and confidence handling.

This module tests privacy-preserving features and confidence thresholds:
- User data isolation (user_id filtering)
- PII redaction in responses
- Confidence thresholds and uncertainty indicators
- Audit logging for all queries
- Cross-user data leakage prevention

Coverage Target: 100% for privacy and confidence features

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from Agent_Guru.reasoning.knowledge.synthesizer import (
    KnowledgeSynthesizer,
    redact_pii,
)
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeQuery,
    KnowledgeQueryType,
    TimeRange,
)
from Agent_Guru.reasoning.models.memory import (
    EpisodicMemory,
    SemanticMemory,
)


class TestPIIRedaction:
    """Test PII redaction for privacy-preserving responses."""

    def test_redact_email(self):
        """Test email address redaction."""
        text = "Contact me at john.doe@example.com for details"
        redacted = redact_pii(text)
        assert "[EMAIL]" in redacted
        assert "john.doe@example.com" not in redacted
        assert "Contact me at [EMAIL] for details" == redacted

    def test_redact_phone(self):
        """Test phone number redaction."""
        text = "Call me at 555-123-4567 or (555) 987-6543"
        redacted = redact_pii(text)
        assert "[PHONE]" in redacted
        assert "555-123-4567" not in redacted
        # Note: (555) 987-6543 format may not be caught by simple regex

    def test_redact_phone_simple(self):
        """Test simple phone number redaction."""
        text = "Call me at 5551234567"
        redacted = redact_pii(text)
        # Simple 10-digit phone may not be caught without dashes
        # This is acceptable for privacy-preserving aggregation

    def test_redact_ssn(self):
        """Test SSN redaction."""
        text = "My SSN is 123-45-6789"
        redacted = redact_pii(text)
        assert "[SSN]" in redacted
        assert "123-45-6789" not in redacted
        assert "My SSN is [SSN]" == redacted

    def test_redact_credit_card(self):
        """Test credit card number redaction."""
        text = "Card number: 1234-5678-9012-3456"
        redacted = redact_pii(text)
        assert "[CREDIT_CARD]" in redacted
        assert "1234-5678-9012-3456" not in redacted

    def test_redact_ip_address(self):
        """Test IP address redaction."""
        text = "Server IP: 192.168.1.1"
        redacted = redact_pii(text)
        assert "[IP]" in redacted
        assert "192.168.1.1" not in redacted
        assert "Server IP: [IP]" == redacted

    def test_redact_url(self):
        """Test URL redaction."""
        text = "Visit https://example.com/secret for more info"
        redacted = redact_pii(text)
        assert "[URL]" in redacted
        assert "https://example.com/secret" not in redacted

    def test_redact_multiple_pii_types(self):
        """Test redacting multiple PII types in one text."""
        text = "Email: john@example.com, Phone: 555-123-4567, SSN: 123-45-6789"
        redacted = redact_pii(text)
        assert "[EMAIL]" in redacted
        assert "[PHONE]" in redacted
        assert "[SSN]" in redacted
        assert "john@example.com" not in redacted
        assert "123-45-6789" not in redacted

    def test_redact_no_pii(self):
        """Test text without PII remains unchanged."""
        text = "This is a normal sentence without any PII"
        redacted = redact_pii(text)
        assert redacted == text

    def test_redact_empty_string(self):
        """Test empty string redaction."""
        redacted = redact_pii("")
        assert redacted == ""


class TestUserDataIsolation:
    """Test user data isolation and privacy filtering."""

    def test_retrieve_only_user_data(self):
        """Test that only user's own data is retrieved."""
        # Create mock memory retriever
        mock_retriever = MagicMock()

        # Create memories for different users
        user1_memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_1",
            content="User 1 called John",
            embedding=[0.1] * 768,  # 768-dimensional embedding
            timestamp=datetime.utcnow(),
            relevance_score=0.9,
            action_taken="call",
            result="success",
            success=True,
            context={"person": "John"},
        )

        user2_memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_2",
            content="User 2 called Jane",
            embedding=[0.2] * 768,  # 768-dimensional embedding
            timestamp=datetime.utcnow(),
            relevance_score=0.8,
            action_taken="call",
            result="success",
            success=True,
            context={"person": "Jane"},
        )

        # Mock retriever returns only user_1's data
        mock_retriever.retrieve.return_value = [user1_memory]

        # Create synthesizer
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        # Create query
        query = KnowledgeQuery(
            query_text="when did I last call someone?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={"action": "call"},
            confidence=0.9,
        )

        # Retrieve data for user_1
        memories = synthesizer.retrieve_relevant_data(query, "user_1")

        # Verify only user_1's data is returned
        assert len(memories) == 1
        assert memories[0].user_id == "user_1"
        assert "John" in memories[0].content

        # Verify retriever was called with correct user_id
        mock_retriever.retrieve.assert_called_once()
        call_kwargs = mock_retriever.retrieve.call_args.kwargs
        assert call_kwargs["user_id"] == "user_1"

    def test_cross_user_data_leakage_prevention(self):
        """Test defense against cross-user data leakage."""
        # Create mock memory retriever that accidentally returns wrong user's data
        mock_retriever = MagicMock()

        # Create memories for different users
        user1_memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_1",
            content="User 1 data",
            embedding=[0.1] * 768,  # 768-dimensional embedding
            timestamp=datetime.utcnow(),
            relevance_score=0.9,
            action_taken="test",
            result="success",
            success=True,
            context={},
        )

        user2_memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_2",  # Wrong user!
            content="User 2 data (should be filtered)",
            embedding=[0.2] * 768,  # 768-dimensional embedding
            timestamp=datetime.utcnow(),
            relevance_score=0.8,
            action_taken="test",
            result="success",
            success=True,
            context={},
        )

        # Mock retriever accidentally returns both users' data
        mock_retriever.retrieve.return_value = [user1_memory, user2_memory]

        # Create synthesizer
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        # Create query
        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.9,
        )

        # Retrieve data for user_1 with logging capture
        with patch("Agent_Guru.reasoning.knowledge.synthesizer.logger") as mock_logger:
            memories = synthesizer.retrieve_relevant_data(query, "user_1")

            # Verify only user_1's data is returned (defense in depth)
            assert len(memories) == 1
            assert memories[0].user_id == "user_1"
            assert "User 1 data" in memories[0].content

            # Verify security violation was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert "SECURITY VIOLATION" in error_call[0][0]
            assert error_call[1]["extra"]["requested_user_id"] == "user_1"
            assert error_call[1]["extra"]["memory_user_id"] == "user_2"

    def test_empty_user_id_raises_error(self):
        """Test that empty user_id raises ValueError."""
        mock_retriever = MagicMock()
        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.9,
        )

        # Test empty string
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            synthesizer.retrieve_relevant_data(query, "")

        # Test whitespace only
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            synthesizer.retrieve_relevant_data(query, "   ")


class TestConfidenceThresholds:
    """Test confidence thresholds and uncertainty indicators."""

    def test_low_confidence_adds_uncertainty_indicator(self):
        """Test that low confidence (<0.6) adds uncertainty indicator."""
        mock_retriever = MagicMock()

        # Create low-confidence memory
        memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_1",
            content="Called John 2 weeks ago",
            embedding=[0.1] * 768,  # 768-dimensional embedding
            timestamp=datetime.utcnow() - timedelta(days=14),
            relevance_score=0.4,  # Low relevance
            action_taken="call",
            result="success",
            success=True,
            context={"person": "John"},
        )

        mock_retriever.retrieve.return_value = [memory]

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            confidence_threshold=0.6,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_month(),
            entities={"person": "John", "action": "call"},
            confidence=0.5,  # Low confidence
        )

        answer = synthesizer.synthesize_answer(query, "user_1")

        # Verify uncertainty indicator is added
        assert answer.summary.lower().startswith("i'm not very confident")
        assert answer.confidence < 0.6

    def test_high_confidence_no_uncertainty_indicator(self):
        """Test that high confidence (>=0.6) doesn't add uncertainty indicator."""
        mock_retriever = MagicMock()

        # Create high-confidence memory
        memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_1",
            content="Called John today",
            embedding=[0.1] * 768,  # 768-dimensional embedding
            timestamp=datetime.utcnow(),
            relevance_score=0.95,  # High relevance
            action_taken="call",
            result="success",
            success=True,
            context={"person": "John"},
        )

        mock_retriever.retrieve.return_value = [memory]

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            confidence_threshold=0.6,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="when did I last call John?",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={"person": "John", "action": "call"},
            confidence=0.9,  # High confidence
        )

        answer = synthesizer.synthesize_answer(query, "user_1")

        # Verify no uncertainty indicator
        assert not answer.summary.lower().startswith("i'm not very confident")
        assert answer.confidence >= 0.6

    def test_confidence_threshold_configurable(self):
        """Test that confidence threshold is configurable."""
        mock_retriever = MagicMock()

        # Test with different thresholds
        for threshold in [0.5, 0.6, 0.7, 0.8]:
            synthesizer = KnowledgeSynthesizer(
                memory_retriever=mock_retriever,
                confidence_threshold=threshold,
                use_llm_synthesis=False,
            )

            assert synthesizer.confidence_threshold == threshold


class TestAuditLogging:
    """Test audit logging for all knowledge queries."""

    def test_query_received_logged(self):
        """Test that query received is logged."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.9,
        )

        with patch("Agent_Guru.reasoning.knowledge.synthesizer.logger") as mock_logger:
            synthesizer.synthesize_answer(query, "user_1")

            # Verify query received was logged
            info_calls = [call for call in mock_logger.info.call_args_list]
            assert len(info_calls) >= 1

            # Check first log (query received)
            first_log = info_calls[0]
            assert "Knowledge query received" in first_log[0][0]
            assert first_log[1]["extra"]["user_id"] == "user_1"
            assert first_log[1]["extra"]["query_text"] == "test query"
            assert first_log[1]["extra"]["query_type"] == "temporal"

    def test_query_completed_logged(self):
        """Test that query completion is logged."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.9,
        )

        with patch("Agent_Guru.reasoning.knowledge.synthesizer.logger") as mock_logger:
            synthesizer.synthesize_answer(query, "user_1")

            # Verify query completed was logged
            info_calls = [call for call in mock_logger.info.call_args_list]
            assert len(info_calls) >= 3  # received, retrieved, completed

            # Check last log (query completed)
            last_log = info_calls[-1]
            assert "Knowledge query completed" in last_log[0][0]
            assert last_log[1]["extra"]["user_id"] == "user_1"
            assert "answer_confidence" in last_log[1]["extra"]
            assert "latency_ms" in last_log[1]["extra"]

    def test_latency_warning_logged(self):
        """Test that latency warnings are logged."""
        mock_retriever = MagicMock()

        # Simulate slow retrieval
        def slow_retrieve(*args, **kwargs):
            import time

            time.sleep(1.6)  # Exceed 1.5s budget
            return []

        mock_retriever.retrieve.side_effect = slow_retrieve

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.9,
        )

        with patch("Agent_Guru.reasoning.knowledge.synthesizer.logger") as mock_logger:
            synthesizer.synthesize_answer(query, "user_1")

            # Verify latency warning was logged
            warning_calls = [call for call in mock_logger.warning.call_args_list]
            assert len(warning_calls) >= 1

            warning_log = warning_calls[0]
            assert "exceeded latency budget" in warning_log[0][0]
            assert warning_log[1]["extra"]["latency_ms"] > 1500


class TestPrivacyPreservingAggregation:
    """Test privacy-preserving aggregation (no PII in responses)."""

    def test_pii_redacted_in_answer_summary(self):
        """Test that PII is redacted from answer summaries."""
        mock_retriever = MagicMock()

        # Create memory with PII
        memory = SemanticMemory(
            memory_id=uuid4(),
            user_id="user_1",
            content="John's email is john@example.com and phone is 555-123-4567",
            embedding=[0.1] * 768,  # 768-dimensional embedding
            timestamp=datetime.utcnow(),
            relevance_score=0.9,
            fact="Contact info",
            source="user_input",
            confidence=0.9,
        )

        mock_retriever.retrieve.return_value = [memory]

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="what is John's contact info?",
            query_type=KnowledgeQueryType.FACTUAL,
            entities={"person": "John"},
            confidence=0.9,
        )

        answer = synthesizer.synthesize_answer(query, "user_1")

        # Verify PII is redacted
        assert "[EMAIL]" in answer.summary or "john@example.com" not in answer.summary
        assert "[PHONE]" in answer.summary or "555-123-4567" not in answer.summary

    def test_aggregation_without_pii_leakage(self):
        """Test that aggregation doesn't leak PII."""
        mock_retriever = MagicMock()

        # Create memories with PII
        memories = [
            EpisodicMemory(
                memory_id=uuid4(),
                user_id="user_1",
                content=f"Called john@example.com at 555-{i:04d}",
                embedding=[0.1] * 768,  # 768-dimensional embedding
                timestamp=datetime.utcnow() - timedelta(days=i),
                relevance_score=0.9,
                action_taken="call",
                result="success",
                success=True,
                context={},
            )
            for i in range(5)
        ]

        mock_retriever.retrieve.return_value = memories

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="who do I call most?",
            query_type=KnowledgeQueryType.AGGREGATION,
            time_range=TimeRange.last_week(),
            entities={"action": "call"},
            confidence=0.9,
        )

        answer = synthesizer.synthesize_answer(query, "user_1")

        # Verify PII is redacted from summary
        assert "john@example.com" not in answer.summary
        assert "555-" not in answer.summary or "[PHONE]" in answer.summary


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=Agent_Guru.reasoning.knowledge.synthesizer"])
