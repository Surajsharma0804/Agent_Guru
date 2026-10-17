"""The Kokoro voice loads only the pinned model files.

Both hashes used to be None: any bytes in the cache or from the download
were loaded, and a download was renamed before it was checked. The filler
voice loaded the same files with no check at all.
"""

from __future__ import annotations

import hashlib
import sys
import types

import pytest

from Agent_Guru.speech.tts import tts_engine
from Agent_Guru.speech.tts.tts_engine import KOKORO_PINS, KokoroTTSEngine, TTSError
from Agent_Guru.utils.verified_files import PinnedFile

MODEL, VOICES = b"onnx graph " * 300, b"voice table " * 100


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """A Kokoro cache with small files pinned the way the real ones are."""
    pins = (
        PinnedFile("kokoro-v1.0.onnx", len(MODEL), hashlib.sha256(MODEL).hexdigest()),
        PinnedFile("voices-v1.0.bin", len(VOICES), hashlib.sha256(VOICES).hexdigest()),
    )
    monkeypatch.setattr(tts_engine, "KOKORO_PINS", pins)
    monkeypatch.setattr(tts_engine, "_PINS_BY_NAME", {p.name: p for p in pins})
    monkeypatch.setattr(tts_engine, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(tts_engine, "_MODEL_PATH", tmp_path / "kokoro-v1.0.onnx")
    monkeypatch.setattr(tts_engine, "_VOICES_PATH", tmp_path / "voices-v1.0.bin")
    loaded: list[str] = []

    class Session:
        def __init__(self, path, providers=None):
            loaded.append(path)

        def get_providers(self):
            return ["CPUExecutionProvider"]

    monkeypatch.setitem(sys.modules, "kokoro_onnx", types.SimpleNamespace(
        Kokoro=types.SimpleNamespace(from_session=lambda session, voices: object())))
    import onnxruntime

    monkeypatch.setattr(onnxruntime, "InferenceSession", Session)
    downloads: list[str] = []

    def fake_download(url, dest):
        downloads.append(dest.name)
        dest.write_bytes(MODEL if dest.name.endswith(".onnx") else VOICES)

    monkeypatch.setattr(tts_engine, "_download", fake_download)
    return types.SimpleNamespace(dir=tmp_path, loaded=loaded, downloads=downloads)


def test_the_real_pins_are_the_documented_files():
    assert {p.name: p.size for p in KOKORO_PINS} == {"kokoro-v1.0.onnx": 325532387,  # nosec B101
                                                     "voices-v1.0.bin": 28214398}
    assert all(len(p.digest) == 64 and p.kind == "sha256" for p in KOKORO_PINS)  # nosec B101


def test_verified_files_load(cache):
    (cache.dir / "kokoro-v1.0.onnx").write_bytes(MODEL)
    (cache.dir / "voices-v1.0.bin").write_bytes(VOICES)
    KokoroTTSEngine()._ensure_loaded()
    assert len(cache.loaded) == 1 and cache.downloads == []  # nosec B101


def test_a_corrupted_cached_model_is_replaced_by_a_verified_download(cache):
    (cache.dir / "kokoro-v1.0.onnx").write_bytes(b"X" + MODEL[1:])
    (cache.dir / "voices-v1.0.bin").write_bytes(VOICES)
    KokoroTTSEngine()._ensure_loaded()
    assert cache.downloads == ["kokoro-v1.0.onnx"]  # nosec B101
    assert (cache.dir / "kokoro-v1.0.onnx").read_bytes() == MODEL  # nosec B101


def test_a_file_that_still_fails_is_never_loaded(cache, monkeypatch):
    (cache.dir / "kokoro-v1.0.onnx").write_bytes(b"X" + MODEL[1:])
    (cache.dir / "voices-v1.0.bin").write_bytes(VOICES)

    def refuse(url, dest):
        msg = f"{dest.name} is missing and AGENT_GURU_NO_DOWNLOAD is set"
        raise TTSError(msg)

    monkeypatch.setattr(tts_engine, "_download", refuse)
    with pytest.raises(TTSError):
        KokoroTTSEngine()._ensure_loaded()
    assert cache.loaded == []  # nosec B101


def test_missing_files_are_fetched_then_verified(cache):
    KokoroTTSEngine()._ensure_loaded()
    assert sorted(cache.downloads) == ["kokoro-v1.0.onnx", "voices-v1.0.bin"]  # nosec B101
    assert len(cache.loaded) == 1  # nosec B101


def test_an_offline_start_with_verified_files_touches_no_network(cache, monkeypatch):
    (cache.dir / "kokoro-v1.0.onnx").write_bytes(MODEL)
    (cache.dir / "voices-v1.0.bin").write_bytes(VOICES)
    KokoroTTSEngine()._ensure_loaded()

    def no_network(*a, **k):
        msg = "network used"
        raise AssertionError(msg)

    monkeypatch.setattr(tts_engine, "_download", no_network)
    monkeypatch.setattr("urllib.request.urlopen", no_network)
    KokoroTTSEngine()._ensure_loaded()
    assert len(cache.loaded) == 2  # nosec B101


def test_the_filler_voice_does_not_load_unverified_files(tmp_path, monkeypatch):
    from Agent_Guru.speech import filler_response

    monkeypatch.setattr(filler_response, "_KOKORO_CACHE_DIR", tmp_path)
    monkeypatch.setattr(filler_response, "_DEFAULT_KOKORO_MODEL_PATH", tmp_path / "kokoro-v1.0.onnx")
    monkeypatch.setattr(filler_response, "_DEFAULT_KOKORO_VOICES_PATH", tmp_path / "voices-v1.0.bin")
    monkeypatch.delenv("KOKORO_MODEL_PATH", raising=False)
    monkeypatch.delenv("KOKORO_VOICES_PATH", raising=False)
    (tmp_path / "kokoro-v1.0.onnx").write_bytes(b"not the model")
    (tmp_path / "voices-v1.0.bin").write_bytes(b"not the voices")
    built: list[tuple] = []
    monkeypatch.setitem(sys.modules, "kokoro_onnx", types.SimpleNamespace(Kokoro=lambda *a: built.append(a)))
    cache = filler_response.FillerResponseCache()
    assert cache._get_kokoro_engine() is None and built == []  # nosec B101


@pytest.mark.skipif(not (tts_engine._CACHE_DIR / "kokoro-v1.0.onnx").is_file(), reason="Kokoro files not downloaded")
def test_the_downloaded_files_on_this_machine_are_the_pinned_ones():
    tts_engine.verify_kokoro_files()
