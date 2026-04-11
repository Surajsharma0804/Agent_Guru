"""
Property-based tests for Knowledge Synthesis Engine privacy and confidence handling.

This module uses Hypothesis to test privacy and confidence properties across
a wide range of inputs to ensure robustness and correctness.

Properties tested:
- PII redaction is complete and consistent
- User data isolation is enforced
- Confidence thresholds are respected
- Audit logging is comprehensive

Coverage Target: 100% property coverage

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from Agent_Guru.reasoning.knowledge.synthesizer import (
    KnowledgeSynthesizer,
    redact_pii,
)
from Agent_Guru.reasoning.models.knowledge import (
    KnowledgeQuery,
    KnowledgeQueryType,
    TimeRange,
)
from Agent_Guru.reasoning.models.memory import EpisodicMemory


class TestPIIRedactionProperties:
    """Property-based tests for PII redaction."""

    @given(
        text_before=st.text(min_size=0, max_size=50),
        text_after=st.text(min_size=0, max_size=50),
    )
    def test_email_pattern_redacted(self, text_before: str, text_after: str):
        """Property: Email-like patterns are always redacted.

        **Validates: Requirements 38.10, 38.12**
        """
        # Use a simple email pattern instead of st.emails() which is slow
        email = "test@example.com"
        text = f"{text_before} {email} {text_after}"
        redacted = redact_pii(text)

        # Email should not appear in redacted text
        assert email not in redacted, f"Email {email} was not redacted"

        # [EMAIL] should be in redacted text
        assert "[EMAIL]" in redacted, "Email marker not found in redacted text"

    @given(
        text=st.text(min_size=0, max_size=200),
    )
    def test_redaction_idempotent(self, text: str):
        """Property: Redacting twice produces same result as redacting once.

        **Validates: Requirements 38.10, 38.12**
        """
        redacted_once = redact_pii(text)
        redacted_twice = redact_pii(redacted_once)

        assert redacted_once == redacted_twice, "Redaction is not idempotent"

    @given(
        text=st.text(min_size=0, max_size=200),
    )
    def test_redaction_preserves_length_order(self, text: str):
        """Property: Redaction doesn't make text significantly longer.

        **Validates: Requirements 38.10, 38.12**
        """
        redacted = redact_pii(text)

        # Redacted text should not be more than 2x original length
        # (accounting for replacement markers like [EMAIL])
        assert len(redacted) <= len(text) * 2, "Redaction made text too long"

    @given(
        text=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
            min_size=0,
            max_size=100,
        ),
    )
    def test_redaction_never_crashes(self, text: str):
        """Property: Redaction never raises exceptions.

        **Validates: Requirements 38.10, 38.12**
        """
        try:
            redacted = redact_pii(text)
            assert isinstance(redacted, str), "Redaction must return string"
        except Exception as e:
            pytest.fail(f"Redaction raised exception: {e}")


class TestUserDataIsolationProperties:
    """Property-based tests for user data isolation."""

    @given(
        user_id=st.text(
            min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
        ),
        query_text=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        ).filter(
            lambda x: x.strip()
        ),  # Ensure non-whitespace
    )
    def test_user_id_always_validated(self, user_id: str, query_text: str):
        """Property: User ID is always validated before data retrieval.

        **Validates: Requirements 38.10**
        """
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text=query_text,
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.9,
        )

        # Should not raise for valid user_id
        try:
            synthesizer.retrieve_relevant_data(query, user_id)
        except ValueError:
            # Only acceptable if user_id is empty/whitespace
            assert not user_id.strip(), f"Valid user_id {user_id} was rejected"

    @given(
        requested_user=st.text(
            min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
        ),
        memory_user=st.text(
            min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
        ),
    )
    def test_cross_user_data_always_filtered(self, requested_user: str, memory_user: str):
        """Property: Cross-user data is always filtered out.

        **Validates: Requirements 38.10**
        """
        # Skip if users are the same
        if requested_user == memory_user:
            return

        mock_retriever = MagicMock()

        # Create memory for different user
        memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id=memory_user,
            content="Test data",
            embedding=[0.1] * 768,
            timestamp=datetime.utcnow(),
            relevance_score=0.9,
            action_taken="test",
            result="success",
            success=True,
            context={},
        )

        mock_retriever.retrieve.return_value = [memory]

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

        # Retrieve data for requested_user
        with patch("Agent_Guru.reasoning.knowledge.synthesizer.logger"):
            memories = synthesizer.retrieve_relevant_data(query, requested_user)

            # Should not contain memory from different user
            for mem in memories:
                assert (
                    mem.user_id == requested_user
                ), f"Cross-user data leaked: {mem.user_id} != {requested_user}"


class TestConfidenceThresholdProperties:
    """Property-based tests for confidence thresholds."""

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0),
        threshold=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_confidence_threshold_respected(self, confidence: float, threshold: float):
        """Property: Confidence threshold is always respected.

        **Validates: Requirements 38.11**
        """
        mock_retriever = MagicMock()

        # Create memory with specific confidence
        memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_1",
            content="Test data",
            embedding=[0.1] * 768,
            timestamp=datetime.utcnow(),
            relevance_score=confidence,
            action_taken="test",
            result="success",
            success=True,
            context={},
        )

        mock_retriever.retrieve.return_value = [memory]

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            confidence_threshold=threshold,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=confidence,
        )

        answer = synthesizer.synthesize_answer(query, "user_1")

        # If confidence < threshold, uncertainty indicator should be present
        if answer.confidence < threshold:
            assert answer.summary.lower().startswith(
                "i'm not very confident"
            ), f"Uncertainty indicator missing for confidence {answer.confidence} < threshold {threshold}"

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_confidence_always_in_range(self, confidence: float):
        """Property: Answer confidence is always between 0.0 and 1.0.

        **Validates: Requirements 38.11**
        """
        mock_retriever = MagicMock()

        memory = EpisodicMemory(
            memory_id=uuid4(),
            user_id="user_1",
            content="Test data",
            embedding=[0.1] * 768,
            timestamp=datetime.utcnow(),
            relevance_score=confidence,
            action_taken="test",
            result="success",
            success=True,
            context={},
        )

        mock_retriever.retrieve.return_value = [memory]

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text="test query",
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=confidence,
        )

        answer = synthesizer.synthesize_answer(query, "user_1")

        # Confidence must be in valid range
        assert (
            0.0 <= answer.confidence <= 1.0
        ), f"Confidence {answer.confidence} out of range [0.0, 1.0]"


class TestAuditLoggingProperties:
    """Property-based tests for audit logging."""

    @given(
        user_id=st.text(
            min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
        ),
        query_text=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        ).filter(
            lambda x: x.strip()
        ),  # Ensure non-whitespace
    )
    def test_all_queries_logged(self, user_id: str, query_text: str):
        """Property: All knowledge queries are logged for audit.

        **Validates: Requirements 38.12**
        """
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []

        synthesizer = KnowledgeSynthesizer(
            memory_retriever=mock_retriever,
            use_llm_synthesis=False,
        )

        query = KnowledgeQuery(
            query_text=query_text,
            query_type=KnowledgeQueryType.TEMPORAL,
            time_range=TimeRange.last_week(),
            entities={},
            confidence=0.9,
        )

        with patch("Agent_Guru.reasoning.knowledge.synthesizer.logger") as mock_logger:
            try:
                synthesizer.synthesize_answer(query, user_id)

                # Verify logging occurred
                assert mock_logger.info.called, "No audit logs were created"

                # Verify user_id is in logs
                log_calls = mock_logger.info.call_args_list
                user_ids_logged = [
                    call[1]["extra"]["user_id"]
                    for call in log_calls
                    if "extra" in call[1] and "user_id" in call[1]["extra"]
                ]

                assert user_id in user_ids_logged, f"User ID {user_id} not found in audit logs"

            except ValueError:
                # Only acceptable if user_id is empty/whitespace
                assert not user_id.strip(), f"Valid user_id {user_id} caused error"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
