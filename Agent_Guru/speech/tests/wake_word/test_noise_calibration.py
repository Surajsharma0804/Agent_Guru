"""Regression tests for the startup microphone calibration.

main.py logged "Calibrating microphone (3s)..." and slept. The mic was read 0
times, and the threshold stayed at 0.015 * (1 - 0.5 * 0.5) = 0.0112 on every
machine, so the log line described work that never happened.
calibrate_noise_floor() now reads the room and sets the threshold from it.
"""

from __future__ import annotations

import logging

import numpy as np

from Agent_Guru.speech import wake_word_manager as wwm
from Agent_Guru.speech.audio.wake_word import WakeWordConfig, WakeWordDetector
from Agent_Guru.speech.models import PersonalityType

SR = 16_000
SHIPPED = 0.015
SHIPPED_EFFECTIVE = SHIPPED * (1 - 0.5 * 0.5)


class StubCapture:
    """Hands the manager prepared audio instead of opening a device."""

    def __init__(self, chunks: list[np.ndarray]) -> None:
        self.chunks = list(chunks)
        self.reads = 0
        self.failing_since: float | None = None

    def capture(self) -> np.ndarray:
        self.reads += 1
        return self.chunks.pop(0) if self.chunks else np.zeros(int(SR * 1.5), np.float32)

    def close(self) -> None:
        pass


def _manager(chunks: list[np.ndarray], threshold: float = SHIPPED) -> wwm.WakeWordManager:
    config = WakeWordConfig(energy_threshold=threshold)
    manager = wwm.WakeWordManager(
        wwm.WakeWordManagerConfig(wake_word_config=config, platform="windows", audio_capture_duration=1.5),
    )
    manager._detector = WakeWordDetector(config)
    manager._audio_capture = StubCapture(chunks)
    manager._initialized = True
    return manager


def _babble(seconds: float, rms: float, seed: int = 0) -> np.ndarray:
    """Speech-band noise with a syllable-rate envelope: passes the music check."""
    n = int(SR * seconds)
    rng = np.random.default_rng(seed)
    spectrum = np.fft.rfft(rng.normal(0, 1, n))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    spectrum[(freqs < 300) | (freqs > 3400)] = 0
    noise = np.fft.irfft(spectrum, n)
    t = np.arange(n) / SR
    noise *= 0.35 + 0.65 * np.abs(np.sin(2 * np.pi * 2.5 * t))
    return (noise * rms / np.sqrt(np.mean(noise**2))).astype(np.float32)


def _quiet(seconds: float) -> np.ndarray:
    return _babble(seconds, 0.00005, seed=1)


async def test_calibration_reads_the_microphone():
    """The old 'calibration' read nothing at all."""
    manager = _manager([_quiet(1.5), _quiet(1.5)])

    result = await manager.calibrate_noise_floor(3.0)

    assert manager._audio_capture.reads == 2
    assert result is not None
    assert result.seconds == 3.0
    assert result.noise_rms < 0.001


async def test_a_quiet_room_keeps_the_shipped_threshold():
    manager = _manager([_quiet(1.5), _quiet(1.5)])

    result = await manager.calibrate_noise_floor(3.0)

    assert result.threshold_after == result.threshold_before
    assert manager._detector.config.energy_threshold == SHIPPED


async def test_steady_room_noise_raises_the_threshold_above_it():
    """A floor below speech level raises the threshold, up to the cap."""
    noise = [_babble(1.5, 0.007, seed=s) for s in (2, 3)]
    manager = _manager(noise)

    result = await manager.calibrate_noise_floor(3.0)

    assert result.threshold_before == SHIPPED_EFFECTIVE
    assert not result.rejected
    assert result.threshold_after == wwm.NOISE_FLOOR_MARGIN * result.noise_rms
    assert SHIPPED_EFFECTIVE < result.threshold_after <= wwm.MAX_CALIBRATED_THRESHOLD
    scale = 1 - manager._detector.config.sensitivity * 0.5
    assert np.isclose(manager._detector.config.energy_threshold * scale, result.threshold_after)


async def test_speech_level_sound_during_calibration_does_not_deafen_it():
    """Calibrating over talking used to raise the bar above the talking itself.

    Sound at 0.02 RMS during the startup window set the threshold to about
    0.04, and the same level of speech afterwards could no longer wake the
    assistant for the whole session. On real room audio the equivalent was a
    0.156 threshold that 96% of measured speech chunks could not pass. That
    level is now rejected as a noise floor and the default kept, so speech
    at that level still wakes it.
    """
    later_speech = _babble(1.5, 0.02, seed=9)
    manager = _manager([_babble(1.5, 0.02, seed=s) for s in (2, 3)])

    result = await manager.calibrate_noise_floor(3.0)
    detector = manager._detector
    detector.config.cooldown_seconds = 0
    detector._backend = "mfcc"
    detector._match_phrase_by_spectrum = lambda audio: ("hey guru", PersonalityType.GURU)

    assert result.rejected
    assert result.threshold_after == SHIPPED_EFFECTIVE
    assert detector.config.energy_threshold == SHIPPED
    assert await detector.detect(later_speech) is not None


async def test_a_word_spoken_during_calibration_does_not_set_the_floor():
    """One loud window among six must not deafen the assistant for the session."""
    first = _quiet(1.5)
    first[: SR // 2] = _babble(0.5, 0.08, seed=4)
    manager = _manager([first, _quiet(1.5)])

    result = await manager.calibrate_noise_floor(3.0)

    assert result.threshold_after == result.threshold_before


async def test_calibration_never_lowers_a_configured_threshold():
    manager = _manager([_quiet(1.5), _quiet(1.5)], threshold=0.05)

    await manager.calibrate_noise_floor(3.0)

    assert manager._detector.config.energy_threshold == 0.05


async def test_all_zero_audio_is_reported_as_digital_silence(caplog):
    manager = _manager([np.zeros(int(SR * 1.5), np.float32)] * 2)

    with caplog.at_level(logging.WARNING):
        result = await manager.calibrate_noise_floor(3.0)

    assert result.digital_silence
    assert "muted" in caplog.text


async def test_the_gaps_a_noise_suppressor_leaves_are_not_digital_silence():
    """Measured on an Intel Smart Sound array: up to 37% exact zeros with sound present."""
    chunk = _babble(1.5, 0.005, seed=5)
    chunk[::3] = 0.0
    manager = _manager([chunk, chunk.copy()])

    result = await manager.calibrate_noise_floor(3.0)

    assert not result.digital_silence


async def test_no_working_microphone_means_no_calibration():
    manager = _manager([_quiet(1.5), _quiet(1.5)])
    manager._audio_capture.failing_since = 1.0

    result = await manager.calibrate_noise_floor(3.0)

    assert result is None
    assert manager._detector.config.energy_threshold == SHIPPED
