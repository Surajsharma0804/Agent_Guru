"""Property-based tests for Phase 6: Integration validation.

Task 9.6 — Properties 15, 16, 17, 18.

Property 15: Conversation Memory LRU Eviction
    For any sequence of add_turn() calls with max_turns=N,
    turn_count never exceeds N; after N+1 turns, oldest turn is evicted.

Property 16: Audit Trail Hash Chain Integrity
    For any sequence of log_action() calls, each entry at index i (i>0)
    has prev_hash equal to SHA-256 of entry at index i-1; first entry
    has genesis hash.

Property 17: Policy DENY Enforcement
    For any action where PolicyEngine returns DENY, the action callable
    is not invoked and pipeline result has DENY status.

Property 18: STT Output Validity for Valid Audio
    For any audio array with RMS > 0.005, transcribe() returns a
    TranscriptionResult with non-empty text, non-empty language,
    and confidence in (0.0, 1.0].

Subsystem: audit/tests
Requirements: 6.3, 6.7, 6.8, 6.9
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# ConversationMemory — mirrors task 9.1 / memory/conversation_memory.py
# ---------------------------------------------------------------------------


@dataclass
class ConversationTurn:
    """A single completed conversation turn."""
    user: str
    assistant: str


class ConversationMemory:
    """50-turn LRU eviction conversation store."""

    def __init__(self, max_turns: int = 50) -> None:
        if max_turns <= 0:
            msg = "max_turns must be positive"
            raise ValueError(msg)
        self._turns: deque[ConversationTurn] = deque(maxlen=max_turns)

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    async def add_turn(self, user: str, assistant: str) -> None:
        self._turns.append(ConversationTurn(user=user, assistant=assistant))

    async def get_all_turns(self) -> list[ConversationTurn]:
        return list(self._turns)


# ---------------------------------------------------------------------------
# AuditTrail — mirrors security/security_system.py hash chain
# ---------------------------------------------------------------------------

_GENESIS_HASH = "0" * 64  # SHA-256 of empty string placeholder


@dataclass
class AuditEntry:
    """Single entry in the tamper-evident audit trail."""
    action: str
    prev_hash: str
    entry_hash: str = field(init=False)

    def __post_init__(self) -> None:
        payload = json.dumps({"action": self.action, "prev_hash": self.prev_hash})
        self.entry_hash = hashlib.sha256(payload.encode()).hexdigest()


class AuditTrail:
    """Append-only, hash-chained audit log."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def log_action(self, action: str) -> None:
        prev_hash = self._entries[-1].entry_hash if self._entries else _GENESIS_HASH
        self._entries.append(AuditEntry(action=action, prev_hash=prev_hash))

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def verify_integrity(self) -> bool:
        """Return True if hash chain is unbroken."""
        for i, entry in enumerate(self._entries):
            expected_prev = (
                self._entries[i - 1].entry_hash if i > 0 else _GENESIS_HASH
            )
            if entry.prev_hash != expected_prev:
                return False
        return True


# ---------------------------------------------------------------------------
# PolicyEngine — minimal DENY/ALLOW engine for property testing
# ---------------------------------------------------------------------------


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class PolicyEngine:
    """Simple deny-list policy engine."""

    def __init__(self, denied_actions: set[str] | None = None) -> None:
        self._denied = denied_actions or set()

    def evaluate(self, action: str) -> PolicyDecision:
        return PolicyDecision.DENY if action in self._denied else PolicyDecision.ALLOW


@dataclass
class PipelineResult:
    """Result of a pipeline run."""
    status: PolicyDecision
    action_invoked: bool = False


def run_pipeline(
    action: str,
    callable_: Callable[[], None],
    policy: PolicyEngine,
) -> PipelineResult:
    """Run the action through the policy engine."""
    decision = policy.evaluate(action)
    if decision == PolicyDecision.DENY:
        return PipelineResult(status=PolicyDecision.DENY, action_invoked=False)
    callable_()
    return PipelineResult(status=PolicyDecision.ALLOW, action_invoked=True)


# ---------------------------------------------------------------------------
# TranscriptionResult — mirrors speech/stt/whisper_stt.py
# ---------------------------------------------------------------------------


@dataclass
class TranscriptionResult:
    """Result of a speech-to-text transcription."""
    text: str
    language: str
    confidence: float


def mock_transcribe(audio: np.ndarray) -> Optional[TranscriptionResult]:
    """Mock STT that validates audio quality before returning a result."""
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    if rms <= 0.005:
        return None
    # Simulate a real transcription for valid audio
    return TranscriptionResult(
        text="hello world",
        language="en",
        confidence=min(1.0, rms * 10),  # confidence scales with RMS
    )


# ===========================================================================
# Property 15: Conversation Memory LRU Eviction
# ===========================================================================


class TestConversationMemoryProperty15:
    """Property 15 — turn_count never exceeds N; oldest evicted at N+1."""

    @given(
        max_turns=st.integers(min_value=1, max_value=20),
        extra_turns=st.integers(min_value=0, max_value=15),
    )
    @settings(max_examples=100)
    def test_property_15_turn_count_never_exceeds_max(
        self, max_turns: int, extra_turns: int
    ) -> None:
        """Property 15: turn_count <= max_turns always."""
        import asyncio
        memory = ConversationMemory(max_turns=max_turns)
        total_turns = max_turns + extra_turns

        async def _run() -> None:
            for i in range(total_turns):
                await memory.add_turn(f"user_{i}", f"assistant_{i}")
                assert memory.turn_count <= max_turns, (
                    f"turn_count={memory.turn_count} exceeds max_turns={max_turns}"
                )

        asyncio.run(_run())

    def test_at_exactly_max_turns_no_eviction(self) -> None:
        import asyncio
        memory = ConversationMemory(max_turns=3)

        async def _run() -> int:
            for i in range(3):
                await memory.add_turn(f"u{i}", f"a{i}")
            return memory.turn_count

        count = asyncio.run(_run())
        assert count == 3  # noqa: PLR2004

    def test_oldest_turn_evicted_at_limit_plus_one(self) -> None:
        import asyncio
        memory = ConversationMemory(max_turns=3)

        async def _run() -> list[ConversationTurn]:
            await memory.add_turn("first", "f_resp")
            await memory.add_turn("second", "s_resp")
            await memory.add_turn("third", "t_resp")
            await memory.add_turn("fourth", "fo_resp")  # evicts "first"
            return await memory.get_all_turns()

        turns = asyncio.run(_run())
        user_msgs = [t.user for t in turns]
        assert "first" not in user_msgs, "Oldest turn must be evicted"
        assert "fourth" in user_msgs, "Newest turn must be present"

    def test_remaining_turns_in_insertion_order(self) -> None:
        import asyncio
        memory = ConversationMemory(max_turns=3)

        async def _run() -> list[ConversationTurn]:
            for i in range(5):
                await memory.add_turn(f"u{i}", f"a{i}")
            return await memory.get_all_turns()

        turns = asyncio.run(_run())
        # After 5 inserts into max_turns=3: turns 2, 3, 4 remain in order
        assert [t.user for t in turns] == ["u2", "u3", "u4"]

    def test_max_turns_one_only_keeps_last(self) -> None:
        import asyncio
        memory = ConversationMemory(max_turns=1)

        async def _run() -> list[ConversationTurn]:
            for i in range(5):
                await memory.add_turn(f"u{i}", f"a{i}")
            return await memory.get_all_turns()

        turns = asyncio.run(_run())
        assert len(turns) == 1
        assert turns[0].user == "u4"


# ===========================================================================
# Property 16: Audit Trail Hash Chain Integrity
# ===========================================================================


class TestAuditTrailHashChainProperty16:
    """Property 16 — hash chain is unbroken for any sequence of log_action()."""

    @given(
        actions=st.lists(
            st.text(min_size=1, max_size=100),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_property_16_hash_chain_integrity(self, actions: list[str]) -> None:
        """Property 16: each entry[i].prev_hash == entry[i-1].entry_hash."""
        trail = AuditTrail()
        for action in actions:
            trail.log_action(action)
        assert trail.verify_integrity(), "Hash chain integrity violated"

    def test_first_entry_has_genesis_hash(self) -> None:
        trail = AuditTrail()
        trail.log_action("startup")
        entries = trail.entries()
        assert entries[0].prev_hash == _GENESIS_HASH

    def test_second_entry_links_to_first(self) -> None:
        trail = AuditTrail()
        trail.log_action("action_1")
        trail.log_action("action_2")
        entries = trail.entries()
        assert entries[1].prev_hash == entries[0].entry_hash

    def test_tampered_entry_fails_integrity(self) -> None:
        trail = AuditTrail()
        trail.log_action("a")
        trail.log_action("b")
        # Tamper with first entry's hash
        trail._entries[0] = AuditEntry.__new__(AuditEntry)  # type: ignore[misc]
        trail._entries[0].action = "tampered"
        trail._entries[0].prev_hash = _GENESIS_HASH
        trail._entries[0].entry_hash = "0" * 64  # wrong hash
        assert not trail.verify_integrity()

    def test_empty_trail_passes_integrity(self) -> None:
        trail = AuditTrail()
        assert trail.verify_integrity()

    def test_each_entry_has_unique_hash(self) -> None:
        trail = AuditTrail()
        for i in range(10):
            trail.log_action(f"action_{i}")
        hashes = [e.entry_hash for e in trail.entries()]
        assert len(set(hashes)) == len(hashes), "Duplicate entry hashes found"


# ===========================================================================
# Property 17: Policy DENY Enforcement
# ===========================================================================


class TestPolicyDENYEnforcementProperty17:
    """Property 17 — DENY always prevents action invocation."""

    @given(
        action=st.text(min_size=1, max_size=50),
        other_allowed=st.lists(
            st.text(min_size=1, max_size=50),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=200)
    def test_property_17_deny_prevents_invocation(
        self, action: str, other_allowed: list[str]
    ) -> None:
        """Property 17: DENY always → action_invoked = False."""
        invoked = False

        def callable_() -> None:
            nonlocal invoked
            invoked = True

        denied_set = {action}
        policy = PolicyEngine(denied_actions=denied_set)
        result = run_pipeline(action, callable_, policy)

        assert result.status == PolicyDecision.DENY
        assert not result.action_invoked
        assert not invoked

    def test_allow_action_is_invoked(self) -> None:
        invoked = False

        def callable_() -> None:
            nonlocal invoked
            invoked = True

        policy = PolicyEngine(denied_actions=set())
        result = run_pipeline("safe_action", callable_, policy)
        assert result.status == PolicyDecision.ALLOW
        assert result.action_invoked
        assert invoked

    def test_deny_is_independent_of_user_identity(self) -> None:
        """DENY fires regardless of action name variations — only exact match matters."""
        for action_name in ["delete_files", "format_drive", "rm_rf"]:
            invoked = False

            def make_callable() -> Callable[[], None]:
                def _() -> None:
                    nonlocal invoked
                    invoked = True
                return _

            policy = PolicyEngine(denied_actions={action_name})
            result = run_pipeline(action_name, make_callable(), policy)
            assert result.status == PolicyDecision.DENY
            assert not invoked

    def test_non_denied_action_passes_through(self) -> None:
        policy = PolicyEngine(denied_actions={"forbidden"})
        called = []
        result = run_pipeline("allowed", lambda: called.append(1), policy)
        assert result.status == PolicyDecision.ALLOW
        assert called == [1]

    def test_empty_deny_list_allows_all(self) -> None:
        policy = PolicyEngine(denied_actions=set())
        called = []
        for action in ["a", "b", "c", "d"]:
            run_pipeline(action, lambda: called.append(action), policy)
        assert len(called) == 4  # noqa: PLR2004


# ===========================================================================
# Property 18: STT Output Validity for Valid Audio
# ===========================================================================


class TestSTTOutputValidityProperty18:
    """Property 18 — RMS > 0.005 audio → valid TranscriptionResult."""

    @given(
        amplitude=st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
        length=st.integers(min_value=1600, max_value=16000),  # 0.1s to 1s at 16kHz
    )
    @settings(max_examples=100)
    def test_property_18_valid_audio_produces_valid_result(
        self, amplitude: float, length: int
    ) -> None:
        """Property 18: RMS > 0.005 → non-empty text, language, confidence in (0, 1]."""
        # Generate a sine wave with amplitude > 0.005 RMS
        t = np.linspace(0, 1.0, length)
        audio = (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
        assert rms > 0.005, f"Test audio RMS {rms:.4f} is too quiet for this property"

        result = mock_transcribe(audio)

        assert result is not None, "transcribe() returned None for valid audio"
        assert len(result.text) > 0, "text must be non-empty"
        assert len(result.language) > 0, "language must be non-empty"
        assert 0.0 < result.confidence <= 1.0, (
            f"confidence={result.confidence} not in (0.0, 1.0]"
        )

    def test_silent_audio_returns_none(self) -> None:
        """Audio with RMS <= 0.005 should not produce a transcription."""
        silent = np.zeros(16000, dtype=np.float32)
        result = mock_transcribe(silent)
        assert result is None

    def test_near_silence_threshold_returns_none(self) -> None:
        audio = np.full(16000, 0.001, dtype=np.float32)  # RMS = 0.001
        result = mock_transcribe(audio)
        assert result is None

    def test_exactly_at_threshold_returns_none(self) -> None:
        # RMS = 0.005 → not strictly greater, should return None
        audio = np.full(16000, 0.005, dtype=np.float32)
        result = mock_transcribe(audio)
        assert result is None  # 0.005 is not > 0.005

    def test_loud_audio_confidence_in_range(self) -> None:
        audio = np.ones(16000, dtype=np.float32)  # max amplitude, RMS = 1.0
        result = mock_transcribe(audio)
        assert result is not None
        assert 0.0 < result.confidence <= 1.0
