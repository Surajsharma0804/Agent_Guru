"""A turn the MFCC fallback woke stays quiet when what was heard is too short or too poorly understood.

The fallback wakes on any loud sound, and in the live run each false wake spoke a reply of up to
17 s. The real orchestrator runs here with a speech engine that returns a fixed transcription and a
model that records whether it was asked anything; nothing is spoken.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.speech.models import TranscriptionResult


class Model:
    def __init__(self):
        self.asked = 0

    async def supports_tool_calling(self, model):
        return False

    async def complete(self, request):
        self.asked += 1
        return SimpleNamespace(content="Here is an answer.", tool_calls=[], finish_reason="stop")

    async def stream(self, request):
        self.asked += 1
        from Agent_Guru.llm.models import StreamChunk

        yield StreamChunk(content="Here is an answer.")
        yield StreamChunk(content="", finish_reason="stop")


class Heard:
    def __init__(self):
        self.next = None

    def transcribe(self, audio, sample_rate=16000):
        return self.next


@pytest.fixture
def assistant(tmp_path):
    model, heard, spoken = Model(), Heard(), []
    orch = IntegrationOrchestrator(
        speech_engine=heard, vision_engine=None, llm_runtime=model, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=None, avatar=None,
        deployment=None, gpu_pool=None, reminder_store=tmp_path / "r.json",
    )

    async def silent(*a, **k):
        return None

    async def speak(fn, text, personality, **kw):
        words = [text] if isinstance(text, str) else [c async for c in text]
        spoken.append("".join(words))
        return SimpleNamespace(spoken=1, error=None, sentences=1, audio_seconds=0.0)

    async def tts(text, personality):
        if text and str(text).strip():
            spoken.append(str(text))

    orch._fetch_web_context = silent
    orch._play_filler = silent
    orch._streamable_tts_fn = lambda: (lambda text, pt: (b"", 22050))
    orch._speak_streaming = speak
    orch._stage_tts = tts

    async def turn(text, confidence, *, quiet=True, result_type=TranscriptionResult):
        heard.next = result_type(text=text, language="en", confidence=confidence) if result_type else text
        audio = np.full(16000, 0.05, dtype=np.float32).tobytes()
        return await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=audio, quiet_if_unsure=quiet))

    yield SimpleNamespace(turn=turn, model=model, spoken=spoken)
    orch.close_scheduler()


# Each names a wake word, so it passes the name check and it is the quiet rule that stops it.
@pytest.mark.parametrize(("text", "confidence"),
                         [("Guru.", -0.4), ("Hey Maya, la vidéo.", -1.3), ("Guru chak chak chak", -1.28)])
async def test_a_short_or_poorly_heard_fallback_wake_says_nothing(assistant, text, confidence):
    result = await assistant.turn(text, confidence)
    assert assistant.spoken == [] and assistant.model.asked == 0  # nosec B101
    assert result.error == "unsure_after_fallback_wake"  # nosec B101


async def test_a_command_heard_clearly_after_a_fallback_wake_is_answered(assistant):
    # The owner's recorded commands had 3 to 8 words and confidences of -0.40 to -0.90.
    result = await assistant.turn("Hey Guru, what time is it?", -0.90)
    assert result.error is None and assistant.spoken  # nosec B101


async def test_a_one_word_answer_is_kept_when_the_wake_was_not_the_fallback(assistant):
    # Follow-up answers ("yes") and wakes from a real detector are not filtered.
    result = await assistant.turn("Yes.", -0.4, quiet=False)
    assert result.error is None and assistant.spoken  # nosec B101


async def test_a_low_confidence_from_an_earlier_turn_does_not_silence_the_next(assistant):
    await assistant.turn("Guru chak chak chak", -1.28)

    class NoConfidence:
        def __init__(self, text, language, confidence):
            self.text, self.language = text, language

    result = await assistant.turn("Hey Guru, open notepad please.", None, result_type=NoConfidence)
    assert result.error is None and assistant.spoken  # nosec B101



# ---- the name check ----
# 47 of 60 recorded false wakes were still answered after the quiet rule; Whisper wrote a
# wake name in 16 of 16 of the owner's commands and in 1 of those 60.


async def test_a_fallback_wake_that_names_nobody_is_dropped_silently(assistant):
    # Fluent and confident, as speech heard by mistake is.
    result = await assistant.turn("That's a bit of a wander around the pigeon complex.", -0.42)
    assert assistant.spoken == [] and assistant.model.asked == 0  # nosec B101
    assert result.error == "no_wake_name_after_fallback_wake"  # nosec B101


@pytest.mark.parametrize("text", ["Heguru, what time is it?", "Peeb Maya. Tell me a joke.", "Himaya open notepad"])
async def test_a_fallback_wake_that_names_guru_or_maya_goes_ahead(assistant, text):
    result = await assistant.turn(text, -0.6)
    assert result.error is None and assistant.spoken  # nosec B101


async def test_with_a_trained_wake_model_the_name_is_not_checked(assistant):
    # Not a fallback wake: the model heard the name itself.
    result = await assistant.turn("What time is it?", -0.4, quiet=False)
    assert result.error is None and assistant.spoken  # nosec B101


async def test_a_named_but_garbled_fallback_wake_still_meets_the_quiet_rule(assistant):
    result = await assistant.turn("Guru, Khoif, Manthaya, Zislain", -1.1)
    assert result.error == "unsure_after_fallback_wake" and assistant.spoken == []  # nosec B101


def test_the_name_check_is_on_only_while_the_fallback_decides_wakes():
    from Agent_Guru.speech import wake_word_manager as wwm
    from Agent_Guru.speech.audio.wake_word import WakeWordDetector

    manager = wwm.WakeWordManager(wwm.WakeWordManagerConfig(platform="windows"))
    assert manager.uses_fallback_detector is False  # nosec B101  not initialised: nothing decides
    manager._detector = WakeWordDetector()
    manager._detector._backend = "mfcc"
    assert manager.uses_fallback_detector is True  # nosec B101
    manager._detector._backend = "openwakeword"  # a trained model was found and loaded at startup
    assert manager.uses_fallback_detector is False  # nosec B101
