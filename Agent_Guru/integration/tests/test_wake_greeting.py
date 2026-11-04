"""Hey Guru alone gets a hello by name and is listened to; noise and other speech get nothing.

"Hey Guru" with nothing after it used to end the wake in silence. The loudness
gate that stands in for a wake word sends every noise down this same path, so
the tests that matter most here are the ones where nothing is said.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies
from Agent_Guru.speech.audio import command_capture as app
from Agent_Guru.speech.audio.wake_word import only_wake_phrase

CHUNK = np.full(8000, 0.05, dtype=np.float32)


@pytest.mark.parametrize("text", ["Hey Guru.", "Hey Maya!", "hi guru", "Heguru.", "Himaya", "Himaya\u3002", "Hey Guru ji.", "okay maya",
                                  "हे गुरु", "हे माया।"])
def test_a_wake_phrase_alone(text):
    assert only_wake_phrase(text)  # nosec B101


@pytest.mark.parametrize("text", ["", "Guru.", "Maya", "Hey", "Thank you.", "Hey Guru, what time is it?", "Hey Maya, la video.",
                                  "my guru told me", "Hey Google"])
def test_anything_else_is_not(text):
    assert not only_wake_phrase(text)  # nosec B101


class Mic:
    """Answers each capture in turn with what the test scripts, and records which settings asked."""

    def __init__(self, *captured, fallback=True):
        self.captured = list(captured)
        self.uses_fallback_detector = fallback
        self.asked = []


class Orch:
    def __init__(self, alone=True):
        self.alone = alone
        self.greeted = []
        self.checked = 0

    async def wake_phrase_alone(self, audio):
        self.checked += 1
        return self.alone

    async def greet(self, wake_word, audio=b""):
        self.greeted.append(wake_word)


@pytest.fixture
def scripted(monkeypatch):
    async def capture(mic, chunk=None, vad=None, settings=None):
        mic.asked.append(settings)
        return mic.captured.pop(0)

    monkeypatch.setattr(app, "capture_after_wake", capture)
    monkeypatch.setattr(app, "capture_command", lambda mic: capture(mic, settings="command"))
    monkeypatch.setattr(app, "holds_speech", lambda audio: True)


async def test_a_command_said_in_one_breath_gets_no_greeting(scripted):
    orch, mic = Orch(), Mic(b"what time is it")
    assert await app.listen_after_wake(orch, mic, "Hey Guru", CHUNK) == (b"what time is it", False)  # nosec B101
    assert orch.greeted == [] and orch.checked == 0  # nosec B101


async def test_the_wake_phrase_alone_is_greeted_and_then_listened_to(scripted):
    orch, mic = Orch(), Mic(b"", b"open notes")
    assert await app.listen_after_wake(orch, mic, "Hey Maya", CHUNK) == (b"open notes", True)  # nosec B101
    assert orch.greeted == ["Hey Maya"] and mic.asked == [app.QUICK_AFTER_WAKE, "command"]  # nosec B101


async def test_a_noise_is_not_greeted_and_keeps_the_rest_of_its_wait(scripted):
    orch, mic = Orch(alone=False), Mic(b"", b"")
    assert await app.listen_after_wake(orch, mic, "Hey Guru", CHUNK) == (b"", False)  # nosec B101
    assert orch.greeted == [] and mic.asked == [app.QUICK_AFTER_WAKE, app.REST_AFTER_WAKE]  # nosec B101


async def test_a_sound_with_no_speech_costs_no_recognition(scripted, monkeypatch):
    monkeypatch.setattr(app, "holds_speech", lambda audio: False)
    orch, mic = Orch(), Mic(b"", b"")
    await app.listen_after_wake(orch, mic, "Hey Guru", CHUNK)
    assert orch.checked == 0 and orch.greeted == []  # nosec B101


async def test_a_trained_detector_is_taken_at_its_word(scripted):
    orch, mic = Orch(alone=False), Mic(b"", b"", fallback=False)
    await app.listen_after_wake(orch, mic, "Hey Guru", CHUNK)
    assert orch.greeted == ["Hey Guru"] and orch.checked == 0  # nosec B101


def test_the_two_waits_are_the_three_seconds_a_wake_always_had():
    assert app.QUICK_AFTER_WAKE.no_speech_seconds + app.REST_AFTER_WAKE.no_speech_seconds == 3.0  # nosec B101
    assert not app.QUICK_AFTER_WAKE.keep_without_speech and not app.REST_AFTER_WAKE.keep_without_speech  # nosec B101


@pytest.fixture
def orchestrator(monkeypatch):
    """The real orchestrator with recognition, speech and the filler scripted."""
    engine = PolicyEngine()
    install_default_policies(engine)
    orch = IntegrationOrchestrator(speech_engine=None, vision_engine=None, llm_runtime=SimpleNamespace(), platform_controller=SimpleNamespace(),
                                   agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
                                   avatar=None, deployment=None, gpu_pool=None)
    spoken = []

    async def tts(text, personality=None):
        spoken.append(text)

    orch._stage_tts = tts
    memory = {"name": "Suraj"}
    monkeypatch.setattr("Agent_Guru.platform.features.user_memory.get_user_memory",
                        lambda: SimpleNamespace(get=lambda key, default=None: memory.get(key, default)))
    yield SimpleNamespace(orch=orch, spoken=spoken, memory=memory)
    orch.close_scheduler()


def hears(orch, text, confidence=-0.4):
    async def stage(audio, personality=None):
        orch._parse_stt_result(SimpleNamespace(text=text, language="en", confidence=confidence, language_probability=1.0))
        return text, "en"

    orch._stage_stt = stage


async def test_greeted_by_name(orchestrator):
    assert await orchestrator.orch.greet("Hey Guru") == "Hello Suraj, how can I help you?"  # nosec B101
    assert orchestrator.spoken == ["Hello Suraj, how can I help you?"]  # nosec B101


async def test_a_nickname_is_preferred_and_no_name_is_not_a_blank(orchestrator):
    orchestrator.memory["nickname"] = "Chotu"
    assert await orchestrator.orch.greet("Hey Guru") == "Hello Chotu, how can I help you?"  # nosec B101
    orchestrator.memory.clear()
    assert await orchestrator.orch.greet("Hey Guru") == "Hello, how can I help you?"  # nosec B101


async def test_a_voice_that_is_not_the_owner_is_not_told_the_name(orchestrator, monkeypatch):
    monkeypatch.setattr(IntegrationOrchestrator, "_verify_speaker", staticmethod(lambda event, result: "restricted"))
    assert await orchestrator.orch.greet("Hey Guru") == "Hello, how can I help you?"  # nosec B101


def test_a_name_alone_counts_only_where_speech_was_already_found():
    assert not only_wake_phrase("Guru.")  # nosec B101
    assert only_wake_phrase("Guru.", name_alone=True) and only_wake_phrase("Maya", name_alone=True)  # nosec B101
    assert not only_wake_phrase("Guru, Maya.", name_alone=True)  # nosec B101  Whisper repeating its prompt
    assert not only_wake_phrase("Thank you.", name_alone=True)  # nosec B101


async def test_the_check_needs_the_phrase_clearly_heard(orchestrator):
    orch = orchestrator.orch
    hears(orch, "Hey Guru.", -0.4)
    assert await orch.wake_phrase_alone(b"x") is True  # nosec B101
    hears(orch, "Guru.", -0.4)
    assert await orch.wake_phrase_alone(b"x") is True  # nosec B101
    hears(orch, "Hey Guru.", -1.3)
    assert await orch.wake_phrase_alone(b"x") is False  # nosec B101
    hears(orch, "Thank you.", -0.2)
    assert await orch.wake_phrase_alone(b"x") is False  # nosec B101


async def test_the_check_is_in_english_whatever_the_audio_sounds_like(orchestrator):
    """The owner's "Hey Maya" came back as Thai, Vietnamese, Korean and Japanese with the language left to guess."""
    orch = orchestrator.orch
    asked = []

    def transcribe(samples, rate, language=None):
        asked.append(language)
        return SimpleNamespace(text="Hey Maya.", language="en", confidence=-0.3, language_probability=1.0)

    orch.speech_engine = SimpleNamespace(stt_transcriber=SimpleNamespace(transcribe=transcribe))
    assert await orch.wake_phrase_alone(np.zeros(800, np.float32).tobytes()) is True and asked == ["en"]  # nosec B101


async def test_the_check_shows_nothing_in_the_window(orchestrator):
    """A noise comes here many times an hour: no turn, no row, no change of the orb."""
    orch = orchestrator.orch
    seen = []
    orch.events.subscribe("*", lambda e: seen.append(e.topic))
    hears(orch, "Thank you.")
    await orch.wake_phrase_alone(b"x")
    await asyncio.sleep(0.01)
    assert seen == []  # nosec B101


async def test_a_phrase_split_across_the_wake_chunk_is_greeted_in_its_turn(orchestrator):
    """The chunk held "Hey" and the capture "Guru": it reaches the pipeline as a turn with no command."""
    orch = orchestrator.orch
    hears(orch, "Hey Guru.")
    result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=b"\x00" * 3200, quiet_if_unsure=True))
    assert orchestrator.spoken == ["Hello Suraj, how can I help you?"] and result.awaiting_reply is True  # nosec B101
    assert result.reply == "Hello Suraj, how can I help you?" and result.intent == "greeting"  # nosec B101


async def test_no_filler_before_the_name_check_passes(orchestrator, monkeypatch):
    """Anything the loudness gate let through used to be answered "haan bol" before it was checked."""
    orch = orchestrator.orch
    played = []

    class Cache:
        _initialized = True

        async def play_filler_async(self, **k):
            played.append(k)

    monkeypatch.setattr("Agent_Guru.speech.filler_response.get_filler_cache", lambda: Cache())
    hears(orch, "the door was open all day")
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=b"\x00" * 3200, quiet_if_unsure=True))
    hears(orch, "Hey Guru.")
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=b"\x00" * 3200, quiet_if_unsure=True))
    assert played == []  # nosec B101


async def test_warming_loads_recognition_and_the_voice_before_the_first_wake(orchestrator):
    """They loaded on first use, so the first hello of the day came 17 s after Hey Guru."""
    orch = orchestrator.orch
    used = []
    orch.speech_engine = SimpleNamespace(stt_transcriber=SimpleNamespace(transcribe=lambda *a: used.append("hear")),
                                         tts_engine=SimpleNamespace(synthesize_to_array=lambda text: used.append("say")))
    await orch.warm_voice()
    assert used == ["hear", "say"]  # nosec B101


async def test_a_failed_warm_up_leaves_the_assistant_running(orchestrator):
    def broken(*a):
        raise RuntimeError("no GPU memory")

    orchestrator.orch.speech_engine = SimpleNamespace(stt_transcriber=SimpleNamespace(transcribe=broken))
    await orchestrator.orch.warm_voice()
