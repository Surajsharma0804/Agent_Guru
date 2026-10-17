"""Cloud voices and recognition: off unless switched on, shaped as each API asks, local on any failure.

No request leaves the machine: httpx's MockTransport answers in place of
OpenAI, Cartesia and Deepgram, and records what would have been sent.
"""

from __future__ import annotations

import io
import json
import wave

import httpx
import numpy as np
import pytest

from Agent_Guru.speech import cloud_speech
from Agent_Guru.speech.models import PersonalityType


def _wav(samples=(1000, -1000, 2000), rate=24000) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.array(samples, dtype=np.int16).tobytes())
    return out.getvalue()


def _client(handler):
    seen = []

    def record(request):
        seen.append(request)
        return handler(request)

    return httpx.Client(transport=httpx.MockTransport(record)), seen


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name in ("AGENT_GURU_ALLOW_CLOUD", "AGENT_GURU_CLOUD_TTS", "AGENT_GURU_CLOUD_STT", "OPENAI_API_KEY",
                 "CARTESIA_API_KEY", "CARTESIA_VOICE_GURU", "CARTESIA_VOICE_MAYA", "DEEPGRAM_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_nothing_is_sent_unless_cloud_is_allowed_and_a_provider_chosen(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AGENT_GURU_CLOUD_TTS", "openai")
    assert cloud_speech.tts_provider() == ""  # nosec B101  cloud not allowed
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    assert cloud_speech.tts_provider() == "openai"  # nosec B101
    monkeypatch.delenv("OPENAI_API_KEY")
    assert cloud_speech.tts_provider() == "" and cloud_speech.synthesize("hi", PersonalityType.GURU) is None  # nosec B101


def test_openai_voice_request_and_volume(monkeypatch):
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("AGENT_GURU_CLOUD_TTS", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client, seen = _client(lambda r: httpx.Response(200, content=_wav()))
    wav = cloud_speech.synthesize("Hello there.", PersonalityType.MAYA, 1.2, 0.5, client=client)
    request = seen[0]
    body = json.loads(request.content)
    assert str(request.url) == "https://api.openai.com/v1/audio/speech"  # nosec B101
    assert request.headers["Authorization"] == "Bearer sk-test"  # nosec B101
    assert body["voice"] == "nova" and body["response_format"] == "wav" and body["speed"] == 1.2  # nosec B101
    with wave.open(io.BytesIO(wav)) as w:
        assert list(np.frombuffer(w.readframes(3), dtype=np.int16)) == [500, -500, 1000]  # nosec B101


def test_cartesia_voice_request(monkeypatch):
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("AGENT_GURU_CLOUD_TTS", "cartesia")
    monkeypatch.setenv("CARTESIA_API_KEY", "ck")
    monkeypatch.setenv("CARTESIA_VOICE_GURU", "voice-guru-id")
    client, seen = _client(lambda r: httpx.Response(200, content=_wav()))
    assert cloud_speech.synthesize("Hi.", PersonalityType.GURU, client=client)[:4] == b"RIFF"  # nosec B101
    request = seen[0]
    body = json.loads(request.content)
    assert str(request.url) == "https://api.cartesia.ai/tts/bytes" and request.headers["X-API-Key"] == "ck"  # nosec B101
    assert request.headers["Cartesia-Version"] == "2024-06-10"  # nosec B101
    assert body["voice"] == {"mode": "id", "id": "voice-guru-id"}  # nosec B101
    assert body["output_format"] == {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000}  # nosec B101


@pytest.mark.parametrize("answer", [
    httpx.Response(500, text="server error"), httpx.Response(200, content=b"<html>not audio</html>"),
])
def test_a_failed_cloud_voice_gives_way_to_the_local_one(monkeypatch, answer):
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("AGENT_GURU_CLOUD_TTS", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client, _ = _client(lambda r: answer)
    assert cloud_speech.synthesize("Hi.", PersonalityType.GURU, client=client) is None  # nosec B101


def test_openai_recognition(monkeypatch):
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("AGENT_GURU_CLOUD_STT", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client, seen = _client(lambda r: httpx.Response(200, json={"text": " open notepad ", "language": "english"}))
    result = cloud_speech.transcribe(np.zeros(16000, np.float32), 16000, language="en", client=client)
    request = seen[0]
    assert str(request.url) == "https://api.openai.com/v1/audio/transcriptions"  # nosec B101
    assert b'name="model"' in request.content and b"RIFF" in request.content  # nosec B101
    assert (result.text, result.language, result.duration) == ("open notepad", "en", 1.0)  # nosec B101


def test_deepgram_recognition(monkeypatch):
    monkeypatch.setenv("AGENT_GURU_ALLOW_CLOUD", "1")
    monkeypatch.setenv("AGENT_GURU_CLOUD_STT", "deepgram")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg")
    body = {"results": {"channels": [{"detected_language": "hi",
                                      "alternatives": [{"transcript": "namaste guru", "confidence": 0.93}]}]}}
    client, seen = _client(lambda r: httpx.Response(200, json=body))
    result = cloud_speech.transcribe(np.zeros(8000, np.float32), 16000, client=client)
    request = seen[0]
    assert request.url.host == "api.deepgram.com" and request.url.params["detect_language"] == "true"  # nosec B101
    assert request.headers["Authorization"] == "Token dg" and request.content[:4] == b"RIFF"  # nosec B101
    assert (result.text, result.language, result.confidence) == ("namaste guru", "hi", 0.93)  # nosec B101


def test_the_voice_engine_uses_the_cloud_voice_first_and_falls_back(monkeypatch):
    from Agent_Guru.speech.tts import tts_engine

    engine = tts_engine.TTSEngine()
    monkeypatch.setattr(cloud_speech, "synthesize", lambda *a, **k: _wav())
    assert engine.synthesize("Hello.") == _wav()  # nosec B101
    monkeypatch.setattr(cloud_speech, "synthesize", lambda *a, **k: None)
    monkeypatch.setattr(engine._kokoro, "synthesize", lambda *a, **k: b"local")
    assert engine.synthesize("Hello.") == b"local"  # nosec B101
