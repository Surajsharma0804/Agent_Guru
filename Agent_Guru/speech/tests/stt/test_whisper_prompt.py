"""Whisper's names prompt: no trailing-window loop, no prompt read back as speech, and settings that reach it.

With the old 23-entry prompt, Whisper decoded "How many legs does a spider have?" correctly and then
looped on the trailing audio ("No, no, no..." for 224 tokens), retried by the temperature fallback:
a median 11.9 s and 5 to 6 decoding attempts on the CPU, every time. These tests count decoding
attempts rather than timing them, so a busy machine cannot make them pass or fail.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from Agent_Guru.speech.stt import whisper_stt
from Agent_Guru.speech.stt.whisper_stt import DEFAULT_INITIAL_PROMPT, WhisperTranscriber

SPIDER = Path(__file__).parent / "data" / "spider_question.wav"


class _StandIn:
    """Records what transcribe() asked Whisper for and answers with the given segment texts."""

    def __init__(self, texts=("Hello there.",)):
        self.texts, self.calls = texts, []

    def transcribe(self, audio, **options):
        self.calls.append(options)
        segments = [SimpleNamespace(text=t, start=0.0, end=1.0, avg_logprob=-0.2) for t in self.texts]
        return iter(segments), SimpleNamespace(language="en", language_probability=0.99)


def _with_stand_in(stand_in, **kwargs) -> WhisperTranscriber:
    transcriber = WhisperTranscriber(device="cpu", **kwargs)
    transcriber._model = stand_in
    return transcriber


def _speak(transcriber, language="en"):
    return transcriber.transcribe(np.full(16000, 0.1, dtype=np.float32), 16000, language=language)


def test_the_default_prompt_is_the_short_one_with_a_repeat_guard():
    stand_in = _StandIn()
    _speak(_with_stand_in(stand_in))
    [options] = stand_in.calls
    assert options["initial_prompt"] == DEFAULT_INITIAL_PROMPT  # nosec B101
    assert options["no_repeat_ngram_size"] == 3  # nosec B101
    # The old list, whose trailing window looped, must not come back by accident.
    assert "Kumar" not in DEFAULT_INITIAL_PROMPT and len(DEFAULT_INITIAL_PROMPT.split(",")) <= 10  # nosec B101


@pytest.mark.parametrize(("configured", "sent"), [
    ("Guru, Maya, Anjali, Andheri.", "Guru, Maya, Anjali, Andheri."),
    ("", None),
])
def test_a_configured_prompt_or_none_is_what_whisper_gets(configured, sent):
    stand_in = _StandIn()
    _speak(_with_stand_in(stand_in, initial_prompt=configured))
    assert stand_in.calls[0]["initial_prompt"] == sent  # nosec B101


def test_another_language_gets_no_names_prompt():
    stand_in = _StandIn()
    _speak(_with_stand_in(stand_in), language="fr")
    assert stand_in.calls[0]["initial_prompt"] is None  # nosec B101


@pytest.mark.parametrize("echo", [
    "Guru, Maya, Suraj, Priya, Rahul, Sharma, Namaste.",
    "Guru, Maya, Suraj, Rahul, Sharma, namaste, WhatsApp, crore, lakh.",  # one name left out
])
def test_the_prompt_read_back_is_not_speech(echo):
    """On audio with no speech Whisper read its prompt back, naming Guru and Maya.

    That is what the fallback wake's name check accepts, so it would have started a turn
    from room noise. Seen for 1 of 300 noise, hum and silence clips with language detection on.
    """
    result = _speak(_with_stand_in(_StandIn([echo])))
    assert result.text == "" and result.segments == []  # nosec B101


@pytest.mark.parametrize("spoken", [
    "Guru.",
    "Guru, Maya.",
    "Hey Guru, call Rahul Sharma.",
    "Maya, Guru, Suraj.",  # prompt words, but not in the prompt's order
    "Namaste Guru, how are you?",
])
def test_speech_that_uses_prompt_words_is_kept(spoken):
    result = _speak(_with_stand_in(_StandIn([spoken])))
    assert result.text == spoken  # nosec B101


def _base_model_cached() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache("Systran/faster-whisper-base", "model.bin"), str)


@pytest.mark.skipif(not _base_model_cached(), reason="needs the Whisper base model in the local cache")
def test_the_spider_question_is_decoded_without_a_loop():
    """The real base model, the app's options: one window, at most one retry, never the fallback chain."""
    soundfile = pytest.importorskip("soundfile")
    audio, rate = soundfile.read(str(SPIDER), dtype="float32")
    transcriber = WhisperTranscriber(model_size="base", device="cpu")
    model = transcriber._load_model()
    attempts = []
    generate = model.model.generate

    class Counting:
        """Passes every call through to the CTranslate2 model and counts decoding attempts."""

        def __getattr__(self, name):
            return getattr(generate.__self__, name)

        def generate(self, *args, **kwargs):
            out = generate(*args, **kwargs)
            attempts.append(len(out))
            return out

    model.model = Counting()
    result = transcriber.transcribe(audio, rate, language="en")
    assert "spider" in result.text.lower()  # nosec B101
    # Old prompt: 6 attempts on every run (the question, then the trailing window at
    # temperatures 0 to 0.8). New prompt: 1. Two leaves room for one honest retry.
    assert sum(attempts) <= 2, f"{sum(attempts)} decoding attempts: the trailing window looped"  # nosec B101


def test_speech_engine_passes_the_configured_prompt(monkeypatch):
    """STTConfig.initial_prompt was added; SpeechEngine must hand it to the transcriber."""
    import inspect

    from Agent_Guru.speech import engine

    source = inspect.getsource(engine.SpeechEngine.initialize)
    call = source[source.index("WhisperTranscriber("):]
    call = call[: call.index(")") + 1]
    assert "initial_prompt=stt.initial_prompt" in call  # nosec B101


class TestSettings:
    """AGENT_GURU_STT_PROMPT, _DEVICE and _COMPUTE_TYPE reach STTConfig; unset changes nothing."""

    @staticmethod
    def _config(monkeypatch, **env):
        for name in ("AGENT_GURU_STT_PROMPT", "AGENT_GURU_STT_DEVICE", "AGENT_GURU_STT_COMPUTE_TYPE"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(f"AGENT_GURU_STT_{name}", value)
        from Agent_Guru.speech.config import STTConfig

        return STTConfig()

    def test_unset_is_what_was_used_before(self, monkeypatch):
        config = self._config(monkeypatch)
        assert (config.initial_prompt, config.device, config.compute_type) == (None, "auto", None)  # nosec B101

    def test_each_setting_is_read(self, monkeypatch):
        config = self._config(monkeypatch, PROMPT="Guru, Anjali.", DEVICE="CPU", COMPUTE_TYPE="int8")
        assert (config.initial_prompt, config.device, config.compute_type) == ("Guru, Anjali.", "cpu", "int8")  # nosec B101

    def test_none_turns_the_prompt_off(self, monkeypatch):
        assert self._config(monkeypatch, PROMPT="None").initial_prompt == ""  # nosec B101

    def test_an_unknown_device_or_compute_type_is_refused_with_a_warning(self, monkeypatch, caplog):
        with caplog.at_level(logging.WARNING, logger="Agent_Guru.speech.config"):
            config = self._config(monkeypatch, DEVICE="gpu", COMPUTE_TYPE="int4")
        assert (config.device, config.compute_type) == ("auto", None)  # nosec B101
        assert len(caplog.records) == 2  # nosec B101


def test_the_echo_rule_needs_three_words():
    assert not whisper_stt._echoes_prompt("Guru, Maya", DEFAULT_INITIAL_PROMPT)  # nosec B101
    assert whisper_stt._echoes_prompt("Guru, Maya, Suraj", DEFAULT_INITIAL_PROMPT)  # nosec B101
