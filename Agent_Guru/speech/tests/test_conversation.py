"""Tests for natural conversation: barge-in, diarization, prosody.

This module had no tests, and the gap hid a class that could not be
constructed at all. The defects covered here:

1. CRASH - ``ProsodyConfig`` declared ``PRESETS`` as a dataclass instance
   field and filled it in ``__post_init__`` by constructing four more
   ``ProsodyConfig`` objects, each of which did the same. Every construction,
   including ``ProsodyConfig()``, ended in ``RecursionError``, which also took
   down ``ConversationManager.get_prosody()``.
2. DUPLICATED TABLE - the same four presets were written out a second time
   inside ``get_prosody`` and rebuilt on every call.
3. UNBOUNDED SPEAKER CONTEXTS - ``_contexts`` kept one entry per speaker id
   forever.
4. UNBOUNDED TURN HISTORY - ``ConversationContext.turns`` grew for the life of
   the session.
5. LATENCY GUARD THAT CRASHED - ``detect_barge_in`` raised ``AssertionError``
   when the event loop was slow to resume it, failing the interrupt path at
   exactly the moment the user was trying to interrupt.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from Agent_Guru.speech.conversation import (
    BARGE_IN_DETECTION_MS,
    MAX_TRACKED_SPEAKERS,
    MAX_TURNS_PER_SPEAKER,
    PROSODY_PRESETS,
    RESUMPTION_WINDOW_S,
    BargeInHandler,
    ConversationContext,
    ConversationManager,
    ProsodyConfig,
    SpeakerDiarization,
)


class TestProsodyConfigConstructs:
    """Defect 1: the class must be constructible at all."""

    def test_default_construction_succeeds(self) -> None:
        config = ProsodyConfig()
        assert config.rate == 1.0
        assert config.pitch == 1.0
        assert config.emphasis == "none"

    def test_explicit_construction_succeeds(self) -> None:
        config = ProsodyConfig(rate=0.9, pitch=1.2, emphasis="strong")
        assert (config.rate, config.pitch, config.emphasis) == (0.9, 1.2, "strong")

    def test_constructing_many_is_cheap_and_terminates(self) -> None:
        """A recursive constructor would blow the stack long before this ends."""
        assert len([ProsodyConfig(rate=1.0 + i / 1000) for i in range(2000)]) == 2000

    def test_presets_attribute_still_resolves(self) -> None:
        assert set(ProsodyConfig.PRESETS) == {
            "question",
            "statement",
            "warning",
            "confirmation",
        }

    def test_presets_are_not_per_instance_state(self) -> None:
        """The table is shared module data, not rebuilt inside each object."""
        assert ProsodyConfig().PRESETS is ProsodyConfig(rate=2.0).PRESETS
        assert ProsodyConfig.PRESETS is PROSODY_PRESETS


class TestProsodyConfigImmutability:
    def test_config_is_frozen(self) -> None:
        config = ProsodyConfig()
        with pytest.raises(Exception, match="frozen|immutable|cannot assign"):
            config.rate = 2.0  # type: ignore[misc]

    def test_preset_table_is_read_only(self) -> None:
        with pytest.raises(TypeError):
            PROSODY_PRESETS["question"] = ProsodyConfig()  # type: ignore[index]

    def test_a_caller_cannot_corrupt_a_shared_preset(self) -> None:
        """Handing out shared instances is only safe because they are frozen."""
        manager = ConversationManager()
        warning = manager.get_prosody("warning")
        with pytest.raises(Exception, match="frozen|immutable|cannot assign"):
            warning.rate = 99.0  # type: ignore[misc]
        assert manager.get_prosody("warning").rate == 0.9


class TestProsodyValidation:
    @pytest.mark.parametrize("rate", [0, -1.0])
    def test_rejects_non_positive_rate(self, rate: float) -> None:
        with pytest.raises(ValueError, match="rate must be positive"):
            ProsodyConfig(rate=rate)

    @pytest.mark.parametrize("pitch", [0, -0.5])
    def test_rejects_non_positive_pitch(self, pitch: float) -> None:
        with pytest.raises(ValueError, match="pitch must be positive"):
            ProsodyConfig(pitch=pitch)

    def test_rejects_unknown_emphasis(self) -> None:
        with pytest.raises(ValueError, match="emphasis must be one of"):
            ProsodyConfig(emphasis="SHOUTING")

    def test_every_preset_is_valid(self) -> None:
        for name, preset in PROSODY_PRESETS.items():
            assert preset.rate > 0, name
            assert preset.pitch > 0, name
            assert preset.emphasis in {"none", "moderate", "strong"}, name


class TestGetProsody:
    """Defect 2: one table, read rather than rebuilt."""

    @pytest.mark.parametrize("utterance_type", list(PROSODY_PRESETS))
    def test_returns_the_shared_preset(self, utterance_type: str) -> None:
        manager = ConversationManager()
        assert manager.get_prosody(utterance_type) is PROSODY_PRESETS[utterance_type]

    def test_unknown_type_returns_neutral_default(self) -> None:
        manager = ConversationManager()
        neutral = manager.get_prosody("no-such-type")
        assert (neutral.rate, neutral.pitch, neutral.emphasis) == (1.0, 1.0, "none")

    def test_repeated_calls_do_not_allocate(self) -> None:
        """Structural proof that the table is not rebuilt per call."""
        manager = ConversationManager()
        first = manager.get_prosody("question")
        assert all(manager.get_prosody("question") is first for _ in range(100))

    def test_questions_are_higher_and_slower_than_statements(self) -> None:
        manager = ConversationManager()
        question = manager.get_prosody("question")
        statement = manager.get_prosody("statement")
        assert question.pitch > statement.pitch
        assert question.rate < statement.rate


class TestSpeakerContextsAreBounded:
    """Defect 3: speaker context must not grow with the number of voices."""

    def test_contexts_are_capped(self) -> None:
        diarization = SpeakerDiarization()
        for i in range(MAX_TRACKED_SPEAKERS * 10):
            diarization.get_or_create_context(f"speaker_{i}")
        assert diarization.tracked_speakers == MAX_TRACKED_SPEAKERS

    def test_retained_size_does_not_track_speaker_count(self) -> None:
        few, many = SpeakerDiarization(), SpeakerDiarization()
        for i in range(MAX_TRACKED_SPEAKERS + 1):
            few.get_or_create_context(f"s{i}")
        for i in range(MAX_TRACKED_SPEAKERS * 50):
            many.get_or_create_context(f"s{i}")
        assert few.tracked_speakers == many.tracked_speakers

    def test_eviction_is_least_recently_active(self) -> None:
        """A regular speaker must outlive a crowd of one-time passers-by."""
        diarization = SpeakerDiarization(max_speakers=4)
        regular = diarization.get_or_create_context("regular")
        regular.add_turn("hello")
        for i in range(3):
            diarization.get_or_create_context(f"passerby_{i}")
        assert diarization.tracked_speakers == 4

        # Touching "regular" refreshes it, making the three passers-by the
        # oldest entries. Three newcomers then displace exactly those three.
        diarization.get_or_create_context("regular")
        for i in range(3, 6):
            diarization.get_or_create_context(f"passerby_{i}")

        assert "regular" in diarization._contexts, (
            "plain FIFO eviction would have dropped the refreshed speaker"
        )
        assert not any(f"passerby_{i}" in diarization._contexts for i in range(3))
        assert diarization.get_or_create_context("regular") is regular
        assert [t["text"] for t in regular.turns] == ["hello"]

    def test_context_is_reused_not_recreated(self) -> None:
        diarization = SpeakerDiarization()
        first = diarization.get_or_create_context("alice")
        first.add_turn("hi")
        assert diarization.get_or_create_context("alice") is first
        assert len(first.turns) == 1

    def test_forget_speaker(self) -> None:
        diarization = SpeakerDiarization()
        diarization.get_or_create_context("bob")
        assert diarization.forget_speaker("bob") is True
        assert diarization.forget_speaker("bob") is False
        assert diarization.tracked_speakers == 0

    @pytest.mark.parametrize("max_speakers", [0, -1])
    def test_rejects_non_positive_capacity(self, max_speakers: int) -> None:
        with pytest.raises(ValueError, match="max_speakers must be positive"):
            SpeakerDiarization(max_speakers=max_speakers)


class TestTurnHistoryIsBounded:
    """Defect 4: one speaker's history must not grow without limit."""

    def test_turns_are_capped(self) -> None:
        context = ConversationContext(speaker_id="alice")
        for i in range(MAX_TURNS_PER_SPEAKER * 3):
            context.add_turn(f"turn {i}")
        assert len(context.turns) == MAX_TURNS_PER_SPEAKER

    def test_newest_turns_are_the_ones_kept(self) -> None:
        context = ConversationContext(speaker_id="alice")
        for i in range(MAX_TURNS_PER_SPEAKER + 3):
            context.add_turn(f"turn {i}")
        texts = [t["text"] for t in context.turns]
        assert texts[-1] == f"turn {MAX_TURNS_PER_SPEAKER + 2}"
        assert texts[0] == "turn 3"

    def test_retained_size_does_not_track_turn_count(self) -> None:
        short, long = (
            ConversationContext(speaker_id="a"),
            ConversationContext(speaker_id="b"),
        )
        for i in range(MAX_TURNS_PER_SPEAKER + 1):
            short.add_turn(str(i))
        for i in range(MAX_TURNS_PER_SPEAKER * 30):
            long.add_turn(str(i))
        assert len(short.turns) == len(long.turns)

    def test_turn_records_role_and_timestamp(self) -> None:
        context = ConversationContext(speaker_id="alice")
        context.add_turn("hello", role="assistant")
        (turn,) = context.turns
        assert turn["role"] == "assistant"
        assert turn["text"] == "hello"
        assert turn["ts"] == pytest.approx(context.last_active)

    def test_last_active_advances(self) -> None:
        context = ConversationContext(speaker_id="alice")
        first = context.last_active
        context.add_turn("hello")
        assert context.last_active >= first


class TestMergeContexts:
    def test_merged_turns_are_in_timestamp_order(self) -> None:
        diarization = SpeakerDiarization()
        alice = diarization.get_or_create_context("alice")
        bob = diarization.get_or_create_context("bob")
        for i in range(10):
            (alice if i % 2 == 0 else bob).add_turn(f"turn {i}")

        merged = diarization.merge_contexts(["alice", "bob"])
        timestamps = [t["ts"] for t in merged.turns]
        assert timestamps == sorted(timestamps)
        assert [t["text"] for t in merged.turns] == [f"turn {i}" for i in range(10)]

    def test_unknown_speakers_are_skipped(self) -> None:
        diarization = SpeakerDiarization()
        diarization.get_or_create_context("alice").add_turn("hi")
        merged = diarization.merge_contexts(["alice", "ghost"])
        assert [t["text"] for t in merged.turns] == ["hi"]

    def test_merging_nothing_yields_no_turns(self) -> None:
        diarization = SpeakerDiarization()
        assert list(diarization.merge_contexts([]).turns) == []

    def test_merge_does_not_mutate_the_sources(self) -> None:
        diarization = SpeakerDiarization()
        alice = diarization.get_or_create_context("alice")
        alice.add_turn("mine")
        diarization.merge_contexts(["alice"]).add_turn("merged only")
        assert [t["text"] for t in alice.turns] == ["mine"]

    def test_merged_id_names_its_sources(self) -> None:
        diarization = SpeakerDiarization()
        merged = diarization.merge_contexts(["alice", "bob"])
        assert merged.speaker_id == "merged_alice_bob"


class TestBargeIn:
    """Defect 5: a congested loop must not break interrupt detection."""

    @pytest.mark.asyncio
    async def test_slow_event_loop_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        handler = BargeInHandler()

        # Simulate a congested loop: make the awaited yield appear to take
        # longer than the detection target.
        real_sleep = asyncio.sleep

        async def slow_yield(delay: float) -> None:
            await real_sleep(delay)
            clock[0] += BARGE_IN_DETECTION_MS * 2 / 1000

        clock = [0.0]
        import time as time_module

        real_perf = time_module.perf_counter
        monkeypatch.setattr(
            "Agent_Guru.speech.conversation.asyncio.sleep", slow_yield
        )
        monkeypatch.setattr(
            "Agent_Guru.speech.conversation.time.perf_counter",
            lambda: real_perf() + clock[0],
        )

        with caplog.at_level(logging.WARNING):
            result = await handler.detect_barge_in(b"")

        assert result is False, "detection must still return a verdict"
        assert any("exceeds target" in r.message for r in caplog.records), (
            "a missed latency target must be recorded, not raised"
        )

    @pytest.mark.asyncio
    async def test_silence_is_not_a_barge_in(self) -> None:
        handler = BargeInHandler()
        assert await handler.detect_barge_in(b"") is False
        assert await handler.detect_barge_in(bytes([0] * 20)) is False

    @pytest.mark.asyncio
    async def test_first_speech_chunk_only_arms_the_detector(self) -> None:
        """A cough must not interrupt; onset alone is not a barge-in."""
        handler = BargeInHandler()
        loud = bytes([200] * 20)
        assert await handler.detect_barge_in(loud) is False

    @pytest.mark.asyncio
    async def test_sustained_speech_triggers_barge_in(self) -> None:
        handler = BargeInHandler()
        loud = bytes([200] * 20)
        await handler.detect_barge_in(loud)
        # Backdate the onset past the minimum-duration guard.
        handler._speech_onset -= BargeInHandler._MIN_SPEECH_DURATION_MS / 1000 + 0.01
        assert await handler.detect_barge_in(loud) is True

    @pytest.mark.asyncio
    async def test_silence_resets_the_onset_tracker(self) -> None:
        handler = BargeInHandler()
        await handler.detect_barge_in(bytes([200] * 20))
        assert handler._speech_onset is not None
        await handler.detect_barge_in(b"")
        assert handler._speech_onset is None


class TestPreservedContext:
    @pytest.mark.asyncio
    async def test_halt_preserves_the_interrupted_response(self) -> None:
        handler = BargeInHandler()
        await handler.halt_output("as I was saying")
        preserved = handler.get_preserved_context()
        assert preserved is not None
        assert preserved["response"] == "as I was saying"
        assert preserved["interrupted_at"] is not None

    def test_no_context_before_any_interruption(self) -> None:
        assert BargeInHandler().get_preserved_context() is None

    def test_clear_preserved_context(self) -> None:
        handler = BargeInHandler()
        handler.preserve_context("something")
        handler.clear_preserved_context()
        assert handler.get_preserved_context() is None

    @pytest.mark.asyncio
    async def test_halt_resets_onset_for_the_next_cycle(self) -> None:
        handler = BargeInHandler()
        await handler.detect_barge_in(bytes([200] * 20))
        await handler.halt_output("interrupted")
        assert handler._speech_onset is None


class TestSessionResumption:
    def test_cannot_resume_before_any_session(self) -> None:
        assert ConversationManager().can_resume() is False

    def test_can_resume_immediately_after_a_session(self) -> None:
        manager = ConversationManager()
        manager.end_session("we were discussing dinner")
        assert manager.can_resume() is True

    def test_cannot_resume_past_the_window(self) -> None:
        manager = ConversationManager()
        manager.end_session("old chat")
        manager._last_session_end -= RESUMPTION_WINDOW_S + 1
        assert manager.can_resume() is False

    def test_boundary_of_the_window_still_resumes(self) -> None:
        manager = ConversationManager()
        manager.end_session("edge")
        manager._last_session_end -= RESUMPTION_WINDOW_S - 1
        assert manager.can_resume() is True


class TestStressDetection:
    @pytest.mark.parametrize(
        "text",
        ["I am stressed", "feeling ANXIOUS today", "so overwhelmed", "Frustrated!"],
    )
    def test_detects_stress_markers_case_insensitively(self, text: str) -> None:
        assert ConversationManager().detect_stress(text) is True

    @pytest.mark.parametrize("text", ["what a lovely day", "", "all good here"])
    def test_calm_text_is_not_flagged(self, text: str) -> None:
        assert ConversationManager().detect_stress(text) is False


class TestDiarizationLatency:
    @pytest.mark.asyncio
    async def test_identify_speakers_returns_a_speaker(self) -> None:
        speakers = await SpeakerDiarization().identify_speakers(b"audio")
        assert speakers == ["speaker_1"]
