"""Cloud voices and cloud speech recognition, used only when the owner turns them on.

The assistant could only speak with Kokoro (or the pyttsx3 fallback) and
hear with the local Whisper. Some owners want a cloud voice, or a cloud
recogniser for languages or accents the local model handles badly. These
backends send the reply text, or the recorded speech, off the machine,
so each needs three things set on purpose:

    AGENT_GURU_ALLOW_CLOUD=1                 the same switch as cloud models
    AGENT_GURU_CLOUD_TTS=openai|cartesia     and the provider's key
    AGENT_GURU_CLOUD_STT=openai|deepgram     and the provider's key

    OPENAI_API_KEY, CARTESIA_API_KEY (+ CARTESIA_VOICE_GURU, CARTESIA_VOICE_MAYA), DEEPGRAM_API_KEY

A cloud call that fails returns None and the local engine answers instead,
so a lost connection never silences the assistant. Keys can be kept in the
vault (`python -m Agent_Guru vault set OPENAI_API_KEY`).
"""

from __future__ import annotations

import io
import logging
import os
import wave
from typing import Any

import numpy as np

from Agent_Guru.speech.models import PersonalityType, TranscriptionResult

logger = logging.getLogger(__name__)

_TIMEOUT_S = 20.0
_OPENAI = "https://api.openai.com/v1"
_CARTESIA = "https://api.cartesia.ai/tts/bytes"
_CARTESIA_VERSION = "2024-06-10"
_DEEPGRAM = "https://api.deepgram.com/v1/listen"
#: OpenAI's voices for the two personalities: a deep male and a warm female voice.
_OPENAI_VOICES = {PersonalityType.GURU: "onyx", PersonalityType.MAYA: "nova"}
_TTS_SAMPLE_RATE = 24000


def _on(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def tts_provider() -> str:
    """The cloud voice to use, or "" when none is switched on and usable."""
    if not _on("AGENT_GURU_ALLOW_CLOUD"):
        return ""
    choice = _env("AGENT_GURU_CLOUD_TTS").lower()
    if choice == "openai" and _env("OPENAI_API_KEY"):
        return choice
    if choice == "cartesia" and _env("CARTESIA_API_KEY") and _env("CARTESIA_VOICE_GURU"):
        return choice
    return ""


def stt_provider() -> str:
    """The cloud recogniser to use, or "" when none is switched on and usable."""
    if not _on("AGENT_GURU_ALLOW_CLOUD"):
        return ""
    choice = _env("AGENT_GURU_CLOUD_STT").lower()
    if (choice == "openai" and _env("OPENAI_API_KEY")) or (choice == "deepgram" and _env("DEEPGRAM_API_KEY")):
        return choice
    return ""


def _scale_wav(wav: bytes, volume: float) -> bytes:
    """*wav* with its 16-bit samples scaled by *volume* (the cloud APIs have no volume)."""
    if volume >= 0.999:
        return wav
    with wave.open(io.BytesIO(wav), "rb") as src:
        params = src.getparams()
        frames = src.readframes(src.getnframes())
    if params.sampwidth != 2:
        return wav
    samples = (np.frombuffer(frames, dtype=np.int16).astype(np.float32) * volume).clip(-32768, 32767)
    out = io.BytesIO()
    with wave.open(out, "wb") as dst:
        dst.setparams(params)
        dst.writeframes(samples.astype(np.int16).tobytes())
    return out.getvalue()


def openai_tts_request(text: str, personality: PersonalityType, speech_rate: float) -> dict[str, Any]:
    return {"model": _env("AGENT_GURU_OPENAI_TTS_MODEL") or "gpt-4o-mini-tts", "input": text,
            "voice": _OPENAI_VOICES.get(personality, "onyx"), "response_format": "wav",
            "speed": max(0.25, min(4.0, speech_rate))}


def cartesia_tts_request(text: str, personality: PersonalityType, speech_rate: float) -> dict[str, Any]:
    voice = _env("CARTESIA_VOICE_MAYA") if personality == PersonalityType.MAYA else ""
    return {"model_id": _env("CARTESIA_MODEL") or "sonic-2", "transcript": text,
            "voice": {"mode": "id", "id": voice or _env("CARTESIA_VOICE_GURU")},
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": _TTS_SAMPLE_RATE},
            "language": "en", "speed": "normal" if 0.9 <= speech_rate <= 1.1 else ("fast" if speech_rate > 1 else "slow")}


def synthesize(text: str, personality: PersonalityType, speech_rate: float = 1.0, volume: float = 1.0,
               *, client: Any = None) -> bytes | None:
    """WAV bytes from the chosen cloud voice, or None (no cloud voice, or it failed)."""
    provider = tts_provider()
    if not provider:
        return None
    import httpx

    try:
        with (client or httpx.Client(timeout=_TIMEOUT_S)) as http:
            if provider == "openai":
                response = http.post(f"{_OPENAI}/audio/speech", json=openai_tts_request(text, personality, speech_rate),
                                     headers={"Authorization": f"Bearer {_env('OPENAI_API_KEY')}"})
            else:
                response = http.post(_CARTESIA, json=cartesia_tts_request(text, personality, speech_rate),
                                     headers={"X-API-Key": _env("CARTESIA_API_KEY"), "Cartesia-Version": _CARTESIA_VERSION})
        if response.status_code != 200 or response.content[:4] != b"RIFF":
            logger.warning("Cloud voice %s answered %s; the local voice speaks instead", provider, response.status_code)
            return None
        return _scale_wav(response.content, volume)
    except Exception as exc:
        logger.warning("Cloud voice %s failed (%s); the local voice speaks instead", provider, type(exc).__name__)
        return None


def _wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0) * 32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(sample_rate)
        dst.writeframes(pcm.tobytes())
    return out.getvalue()


def transcribe(audio: np.ndarray, sample_rate: int = 16000, language: str | None = None,
               *, client: Any = None) -> TranscriptionResult | None:
    """The cloud recogniser's transcription, or None (none chosen, or it failed)."""
    provider = stt_provider()
    if not provider:
        return None
    import httpx

    wav = _wav_bytes(audio, sample_rate)
    duration = len(audio) / float(sample_rate or 16000)
    try:
        with (client or httpx.Client(timeout=_TIMEOUT_S)) as http:
            if provider == "openai":
                data = {"model": _env("AGENT_GURU_OPENAI_STT_MODEL") or "whisper-1", "response_format": "verbose_json"}
                if language:
                    data["language"] = language
                response = http.post(f"{_OPENAI}/audio/transcriptions", data=data,
                                     files={"file": ("speech.wav", wav, "audio/wav")},
                                     headers={"Authorization": f"Bearer {_env('OPENAI_API_KEY')}"})
            else:
                params = {"model": _env("DEEPGRAM_MODEL") or "nova-3", "smart_format": "true"}
                params.update({"language": language} if language else {"detect_language": "true"})
                response = http.post(_DEEPGRAM, params=params, content=wav,
                                     headers={"Authorization": f"Token {_env('DEEPGRAM_API_KEY')}",
                                              "Content-Type": "audio/wav"})
        if response.status_code != 200:
            logger.warning("Cloud recogniser %s answered %s; the local one listens instead", provider, response.status_code)
            return None
        body = response.json()
    except Exception as exc:
        logger.warning("Cloud recogniser %s failed (%s); the local one listens instead", provider, type(exc).__name__)
        return None
    if provider == "openai":
        text, lang = str(body.get("text", "")).strip(), str(body.get("language") or language or "")
        confidence = 0.9
    else:
        channel = ((body.get("results") or {}).get("channels") or [{}])[0]
        best = (channel.get("alternatives") or [{}])[0]
        text, lang = str(best.get("transcript", "")).strip(), str(channel.get("detected_language") or language or "")
        confidence = float(best.get("confidence") or 0.0)
    # OpenAI names the language ("english"); the rest of the assistant uses codes.
    lang = {"english": "en", "hindi": "hi"}.get(lang.lower(), lang.lower()[:5])
    return TranscriptionResult(text=text, language=lang or "en", confidence=confidence, duration=duration)
