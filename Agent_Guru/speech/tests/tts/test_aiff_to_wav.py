"""pyttsx3 on macOS writes AIFF; the fallback voice hands callers WAV.

NSSpeechSynthesizer writes AIFF whatever the file is called. The macOS CI leg got b"FORM" where it
expected b"RIFF" and the audio quality test raised wave.Error, so on a Mac the fallback voice gave
callers bytes they could not read. The AIFF files here are built by hand, as macOS writes them, so
the conversion runs on any machine.
"""

from __future__ import annotations

import io
import struct
import wave

import numpy as np
import pytest

from Agent_Guru.speech.tts import tts_engine
from Agent_Guru.speech.tts.tts_engine import _aiff_to_wav


def _extended(rate: float) -> bytes:
    """An integer sample rate as the 80-bit IEEE extended float AIFF stores."""
    exponent = int(rate).bit_length() - 1
    mantissa = int(rate) << (63 - exponent)
    return struct.pack(">HQ", exponent + 16383, mantissa)


def _aiff(samples: np.ndarray, rate: int, *, aifc: bytes | None = None) -> bytes:
    comm = struct.pack(">hIh", 1, len(samples), 16) + _extended(rate)
    if aifc is not None:
        comm += aifc + b"\x00\x00"
    pcm = samples.astype("<i2").tobytes() if aifc == b"sowt" else samples.astype(">i2").tobytes()
    ssnd = struct.pack(">II", 0, 0) + pcm
    chunks = b"COMM" + struct.pack(">I", len(comm)) + comm + b"SSND" + struct.pack(">I", len(ssnd)) + ssnd
    return b"FORM" + struct.pack(">I", 4 + len(chunks)) + (b"AIFC" if aifc is not None else b"AIFF") + chunks


SAMPLES = (np.sin(np.linspace(0, 40, 2205)) * 12000).astype(np.int16)


@pytest.mark.parametrize("aifc", [None, b"NONE", b"sowt"])
def test_an_aiff_file_becomes_the_same_samples_as_wav(aifc):
    wav = _aiff_to_wav(_aiff(SAMPLES, 22050, aifc=aifc))
    assert wav is not None and wav[:4] == b"RIFF"  # nosec B101
    with wave.open(io.BytesIO(wav)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 22050)  # nosec B101
        assert np.array_equal(np.frombuffer(w.readframes(w.getnframes()), dtype="<i2"), SAMPLES)  # nosec B101


def test_a_compressed_aiff_is_refused_not_misread():
    assert _aiff_to_wav(_aiff(SAMPLES, 22050, aifc=b"ulaw")) is None  # nosec B101


def test_the_fallback_voice_returns_wav_when_pyttsx3_writes_aiff(monkeypatch, tmp_path):
    aiff = _aiff(SAMPLES, 22050)

    def fake_run(args, **kwargs):
        with open(args[3], "wb") as f:  # argv[1] of the child script is the output path
            f.write(aiff)
        return type("Done", (), {"returncode": 0, "stderr": b""})()

    monkeypatch.setattr("subprocess.run", fake_run)  # synthesize() imports subprocess when it runs
    engine = tts_engine._Pyttsx3Engine()
    engine._engine = object()
    out = engine.synthesize("Hello there.", tts_engine.PersonalityType.GURU)
    assert out[:4] == b"RIFF"  # nosec B101
    with wave.open(io.BytesIO(out)) as w:
        assert w.getnframes() == len(SAMPLES)  # nosec B101
