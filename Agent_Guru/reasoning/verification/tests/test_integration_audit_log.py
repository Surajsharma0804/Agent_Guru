"""Regression tests for VerificationIntegration's audit log.

Three defects fixed together:

1. MEMORY LEAK - ``audit_log`` was a plain list holding one entry per
   verification for the life of the process, with a
   ``# In production, persist to database`` note where the persistence should
   be. ``get_audit_log()`` only ever returns the last ``limit`` entries, so
   everything older was unreachable *and* retained.

2. ``limit=0`` RETURNED EVERYTHING - the body ended in ``filtered_log[-limit:]``
   and ``[-0:]`` is ``[0:]``. A caller whose computed limit reached zero got
   the whole audit trail serialised instead of an empty list.

3. FULL SCAN PER QUERY - filtering materialised a new list per active filter
   across the whole log before discarding all but the tail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from Agent_Guru.reasoning.models.verification import VerificationAction
from Agent_Guru.reasoning.verification.integration import (
    CircuitState,
    VerificationAuditLog,
    VerificationIntegration,
)


@pytest.fixture
def integration() -> VerificationIntegration:
    """A VerificationIntegration with no live LLM behind it.

    The audit log is pure bookkeeping - it never calls the verifier - so a
    mock client exercises the real code path without any network.
    """
    return VerificationIntegration(llm_client=MagicMock(), tool_registry=None)


def make_entry(
    index: int, user_id: str = "user-a", conversation_id: str = "conv-1"
) -> VerificationAuditLog:
    return VerificationAuditLog(
        timestamp=datetime.now(tz=UTC),
        user_id=user_id,
        conversation_id=conversation_id,
        task_id=f"task-{index}",
        original_input=f"input {index}",
        attempt=1,
        is_valid=True,
        confidence=0.9,
        recommendation=VerificationAction.PROCEED,
        issues=[],
        verification_time_ms=1.0,
        cache_hit=False,
        circuit_breaker_state=CircuitState.CLOSED,
    )


class TestBoundedAuditLog:
    def test_audit_log_is_bounded(self, integration: VerificationIntegration) -> None:
        limit = VerificationIntegration.AUDIT_LOG_SIZE
        for i in range(limit * 3):
            integration.audit_log.append(make_entry(i))

        assert len(integration.audit_log) == limit, (
            f"audit log holds {len(integration.audit_log)} entries; a long-lived "
            "process must not accumulate them without limit"
        )

    def test_oldest_entries_are_the_ones_dropped(
        self, integration: VerificationIntegration
    ) -> None:
        limit = VerificationIntegration.AUDIT_LOG_SIZE
        for i in range(limit + 5):
            integration.audit_log.append(make_entry(i))

        task_ids = [entry.task_id for entry in integration.audit_log]
        assert task_ids[0] == "task-5", "eviction must be FIFO, keeping the newest"
        assert task_ids[-1] == f"task-{limit + 4}"

    def test_retained_size_does_not_track_verification_count(
        self, integration: VerificationIntegration
    ) -> None:
        """Structural proof: retained size is a constant, not a function of n."""
        other = VerificationIntegration(llm_client=MagicMock(), tool_registry=None)
        for i in range(VerificationIntegration.AUDIT_LOG_SIZE + 1):
            integration.audit_log.append(make_entry(i))
        for i in range(VerificationIntegration.AUDIT_LOG_SIZE * 10):
            other.audit_log.append(make_entry(i))

        assert len(integration.audit_log) == len(other.audit_log)


class TestGetAuditLogLimit:
    @pytest.mark.parametrize("limit", [0, -1, -50])
    def test_non_positive_limit_returns_nothing(
        self, integration: VerificationIntegration, limit: int
    ) -> None:
        for i in range(20):
            integration.audit_log.append(make_entry(i))

        assert integration.get_audit_log(limit=limit) == [], (
            "limit<=0 must return no entries; the old slice returned the "
            "entire log for limit=0"
        )

    def test_limit_returns_most_recent_entries_oldest_first(
        self, integration: VerificationIntegration
    ) -> None:
        for i in range(20):
            integration.audit_log.append(make_entry(i))

        entries = integration.get_audit_log(limit=3)
        assert [e["task_id"] for e in entries] == ["task-17", "task-18", "task-19"]

    def test_limit_larger_than_log_returns_everything(
        self, integration: VerificationIntegration
    ) -> None:
        for i in range(5):
            integration.audit_log.append(make_entry(i))

        entries = integration.get_audit_log(limit=100)
        assert [e["task_id"] for e in entries] == [f"task-{i}" for i in range(5)]

    def test_empty_log_returns_empty_list(
        self, integration: VerificationIntegration
    ) -> None:
        assert integration.get_audit_log(limit=10) == []


class TestGetAuditLogFilters:
    def test_filter_by_user(self, integration: VerificationIntegration) -> None:
        for i in range(10):
            integration.audit_log.append(
                make_entry(i, user_id="user-a" if i % 2 == 0 else "user-b")
            )

        entries = integration.get_audit_log(user_id="user-b", limit=100)
        assert [e["task_id"] for e in entries] == ["task-1", "task-3", "task-5", "task-7", "task-9"]

    def test_filter_by_conversation(self, integration: VerificationIntegration) -> None:
        for i in range(6):
            integration.audit_log.append(
                make_entry(i, conversation_id=f"conv-{i % 3}")
            )

        entries = integration.get_audit_log(conversation_id="conv-2", limit=100)
        assert [e["task_id"] for e in entries] == ["task-2", "task-5"]

    def test_filters_combine(self, integration: VerificationIntegration) -> None:
        integration.audit_log.append(make_entry(0, user_id="a", conversation_id="x"))
        integration.audit_log.append(make_entry(1, user_id="a", conversation_id="y"))
        integration.audit_log.append(make_entry(2, user_id="b", conversation_id="x"))

        entries = integration.get_audit_log(user_id="a", conversation_id="x", limit=100)
        assert [e["task_id"] for e in entries] == ["task-0"]

    def test_limit_applies_after_filtering(
        self, integration: VerificationIntegration
    ) -> None:
        """The limit must count matches, not scanned entries.

        A tail-slice applied before filtering would return fewer rows than
        asked for whenever non-matching entries sit at the end of the log.
        """
        for i in range(10):
            integration.audit_log.append(make_entry(i, user_id="target"))
        for i in range(10, 60):
            integration.audit_log.append(make_entry(i, user_id="noise"))

        entries = integration.get_audit_log(user_id="target", limit=4)
        assert [e["task_id"] for e in entries] == ["task-6", "task-7", "task-8", "task-9"]

    def test_filter_with_no_matches(self, integration: VerificationIntegration) -> None:
        for i in range(5):
            integration.audit_log.append(make_entry(i, user_id="a"))

        assert integration.get_audit_log(user_id="nobody", limit=10) == []

    def test_entries_are_serialisable_dicts(
        self, integration: VerificationIntegration
    ) -> None:
        integration.audit_log.append(make_entry(0))
        (entry,) = integration.get_audit_log(limit=1)
        assert isinstance(entry, dict)
        assert entry["task_id"] == "task-0"
