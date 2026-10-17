"""Tests for audio capture."""

import sys
import threading
import time
import types

import pytest
import numpy as np
import tempfile
from pathlib import Path

# soundfile is optional and only writes the WAV fixtures, so it is imported
# where a fixture needs it. At module scope its absence stopped this whole
# file collecting, including the tests that never touch a file.

from Agent_Guru.speech.audio import capture as capture_module
from Agent_Guru.speech.audio.capture import (
    AudioCapture,
    MicrophoneCapture,
    FileCapture
)
from Agent_Guru.speech.exceptions import AudioInputError


class TestAudioCapture:
    """Test suite for AudioCapture base class."""
    
    def test_base_class_not_implemented(self):
        """Test that base class raises NotImplementedError."""
        capture = AudioCapture()
        with pytest.raises(NotImplementedError):
            capture.capture()


class TestMicrophoneCapture:
    """Test suite for MicrophoneCapture."""
    
    def test_initialization_default(self):
        """Test microphone capture initialization with defaults."""
        capture = MicrophoneCapture()
        assert capture.sample_rate == 16000  # nosec B101
        assert capture.channels == 1  # nosec B101
        assert capture.device is None  # nosec B101
    
    def test_initialization_custom(self):
        """Test microphone capture initialization with custom settings."""
        # Device 0 has to exist for this to mean anything. On a headless host
        # (CI containers, this project's own test runners) sounddevice has no
        # devices at all and MicrophoneCapture correctly raises AudioInputError
        # - asserting otherwise would be asserting that the machine has a
        # microphone, which is not a property of this code.
        import sounddevice as sd

        try:
            devices = sd.query_devices()
        except Exception as exc:  # pragma: no cover - depends on the host
            pytest.skip(f"UNVERIFIED on this host: no audio backend ({exc})")
        if len(devices) == 0:
            pytest.skip("UNVERIFIED on this host: no audio devices present")

        capture = MicrophoneCapture(
            sample_rate=44100,
            channels=2,
            device=0
        )
        assert capture.sample_rate == 44100  # nosec B101
        assert capture.channels == 2  # nosec B101
        assert capture.device == 0  # nosec B101
    
    def test_list_devices(self):
        """Test listing audio devices."""
        devices = MicrophoneCapture.list_devices()
        assert isinstance(devices, list)  # nosec B101
        # Should have at least one input device on most systems
        # (may be 0 in CI environments without audio)
        for device in devices:
            assert 'id' in device  # nosec B101
            assert 'name' in device  # nosec B101
            assert 'channels' in device  # nosec B101
            assert 'sample_rate' in device  # nosec B101
    
    def test_capture_without_duration_raises_error(self):
        """Test that capture without duration raises error."""
        capture = MicrophoneCapture()
        with pytest.raises(AudioInputError, match="Duration is required"):
            capture.capture()
    
    @pytest.mark.skipif(
        not MicrophoneCapture.list_devices(),
        reason="No audio input devices available"
    )
    def test_capture_with_duration(self):
        """Test capturing audio with specified duration."""
        capture = MicrophoneCapture(sample_rate=16000, channels=1)
        
        try:
            audio, sample_rate = capture.capture(duration=0.5)
            
            assert isinstance(audio, np.ndarray)  # nosec B101
            assert audio.dtype == np.float32  # nosec B101
            assert sample_rate == 16000  # nosec B101
            # Should have approximately 0.5 seconds of audio
            expected_samples = int(0.5 * 16000)
            assert abs(len(audio) - expected_samples) < 100  # nosec B101
        except AudioInputError:
            # May fail in CI environments without audio devices
            pytest.skip("Audio capture not available")

    def test_a_device_that_never_delivers_audio_raises_instead_of_hanging(
        self, monkeypatch
    ):
        """A stalled input stream must end in AudioInputError, not a hang.

        capture() used to call sd.wait(), which has no timeout. On a device
        that opened but sent no frames (measured on the WSLg virtual source)
        a 0.5 s recording was still blocked after 20 s. The fake below
        behaves the same way: its stream stays active and its wait() never
        returns, so the old code blocks until the join below gives up.
        """
        never = threading.Event()
        stream = types.SimpleNamespace(active=True)
        stopped = []

        def stop():
            stopped.append(True)
            stream.active = False

        fake_sd = types.SimpleNamespace(
            rec=lambda frames, **kwargs: np.zeros((frames, 1), dtype=np.float32),
            get_stream=lambda: stream,
            stop=stop,
            wait=never.wait,
        )
        monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
        # raising=False so that, run against code without the deadline, the
        # test fails on the hang it exists to catch, not on the missing name.
        monkeypatch.setattr(
            capture_module, "_CAPTURE_START_GRACE_S", 0.2, raising=False
        )

        outcome: dict[str, object] = {}

        def run():
            try:
                MicrophoneCapture().capture(duration=0.1)
                outcome["result"] = "returned audio"
            except AudioInputError as exc:
                outcome["result"] = exc

        started = time.monotonic()
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(5.0)
        never.set()  # lets the old code's thread finish after the check
        elapsed = time.monotonic() - started

        assert "result" in outcome, "capture() was still blocked after 5 s"  # nosec B101
        assert isinstance(outcome["result"], AudioInputError)  # nosec B101
        assert "no audio" in str(outcome["result"])  # nosec B101
        assert stopped, "the stalled stream was not stopped"  # nosec B101
        assert elapsed < 2.0  # nosec B101

    def test_a_recording_that_finishes_is_returned(self, monkeypatch):
        """The deadline must not cut short a stream that ends normally."""
        class FinishingStream:
            """Active for the first three polls, then done."""

            polls = 0

            @property
            def active(self):
                self.polls += 1
                return self.polls < 4

        stream = FinishingStream()
        frames_seen = []

        def rec(frames, **kwargs):
            frames_seen.append(frames)
            return np.full((frames, 1), 0.25, dtype=np.float32)

        fake_sd = types.SimpleNamespace(
            rec=rec,
            get_stream=lambda: stream,
            stop=lambda: pytest.fail("a finished stream must not be stopped"),
            wait=lambda: None,
        )
        monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

        audio, sample_rate = MicrophoneCapture(sample_rate=16000).capture(duration=0.5)

        assert frames_seen == [8000]  # nosec B101
        assert sample_rate == 16000  # nosec B101
        assert audio.shape == (8000,)  # nosec B101
        assert float(audio[0]) == 0.25  # nosec B101


class TestFileCapture:
    """Test suite for FileCapture."""
    
    @pytest.fixture
    def temp_audio_file(self):
        """Create a temporary audio file for testing."""
        sf = pytest.importorskip("soundfile")
        # Generate test audio
        duration = 1.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, audio, sample_rate)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def temp_stereo_file(self):
        """Create a temporary stereo audio file."""
        sf = pytest.importorskip("soundfile")
        duration = 1.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Create stereo audio (2 channels)
        left = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        right = np.sin(2 * np.pi * 880 * t).astype(np.float32)
        stereo = np.column_stack([left, right])
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, stereo, sample_rate)
            temp_path = f.name
        
        yield temp_path
        
        Path(temp_path).unlink(missing_ok=True)
    
    def test_initialization(self, temp_audio_file):
        """Test file capture initialization."""
        capture = FileCapture(temp_audio_file)
        assert capture.file_path == temp_audio_file  # nosec B101
    
    def test_load_file_complete(self, temp_audio_file):
        """Test loading complete audio file."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.load_file(temp_audio_file)
        
        assert isinstance(audio, np.ndarray)  # nosec B101
        assert audio.dtype == np.float32  # nosec B101
        assert sample_rate == 16000  # nosec B101
        assert len(audio) == 16000  # 1 second at 16kHz  # nosec B101
    
    def test_load_file_with_duration(self, temp_audio_file):
        """Test loading partial audio file."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.load_file(temp_audio_file, duration=0.5)
        
        assert isinstance(audio, np.ndarray)  # nosec B101
        assert len(audio) == 8000  # 0.5 seconds at 16kHz  # nosec B101
    
    def test_load_stereo_converts_to_mono(self, temp_stereo_file):
        """Test that stereo audio is converted to mono."""
        capture = FileCapture(temp_stereo_file)
        audio, sample_rate = capture.load_file(temp_stereo_file)
        
        assert audio.ndim == 1, "Should be mono (1D array)"  # nosec B101
        assert len(audio) == 16000  # nosec B101
    
    def test_capture_method(self, temp_audio_file):
        """Test capture method (wrapper for load_file)."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.capture()
        
        assert isinstance(audio, np.ndarray)  # nosec B101
        assert sample_rate == 16000  # nosec B101
    
    def test_capture_with_duration(self, temp_audio_file):
        """Test capture method with duration."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.capture(duration=0.5)
        
        assert len(audio) == 8000  # nosec B101
    
    def test_load_nonexistent_file_raises_error(self):
        """Test loading non-existent file raises error."""
        capture = FileCapture("nonexistent.wav")
        with pytest.raises(AudioInputError):
            capture.load_file("nonexistent.wav")
    
    def test_get_file_info(self, temp_audio_file):
        """Test getting file information."""
        info = FileCapture.get_file_info(temp_audio_file)
        
        assert isinstance(info, dict)  # nosec B101
        assert 'duration' in info  # nosec B101
        assert 'sample_rate' in info  # nosec B101
        assert 'channels' in info  # nosec B101
        assert 'format' in info  # nosec B101
        
        assert info['sample_rate'] == 16000  # nosec B101
        assert info['channels'] == 1  # nosec B101
        assert abs(info['duration'] - 1.0) < 0.01  # nosec B101
    
    def test_get_file_info_nonexistent_raises_error(self):
        """Test getting info for non-existent file raises error."""
        with pytest.raises(AudioInputError):
            FileCapture.get_file_info("nonexistent.wav")
    
    def test_load_different_formats(self):
        """Test loading different audio formats."""
        sf = pytest.importorskip("soundfile")
        formats = ['.wav', '.flac']
        
        for fmt in formats:
            # Create temporary file
            duration = 0.5
            sample_rate = 16000
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
            
            with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as f:
                sf.write(f.name, audio_data, sample_rate)
                temp_path = f.name
            
            try:
                capture = FileCapture(temp_path)
                audio, sr = capture.load_file(temp_path)
                
                assert isinstance(audio, np.ndarray)  # nosec B101
                assert sr == sample_rate  # nosec B101
                assert len(audio) == len(audio_data)  # nosec B101
            finally:
                Path(temp_path).unlink(missing_ok=True)


class TestAudioCaptureIntegration:
    """Integration tests for audio capture."""
    
    def test_file_capture_to_processing_pipeline(self):
        """Test file capture in a processing pipeline."""
        sf = pytest.importorskip("soundfile")
        # Create test audio file
        duration = 1.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            sf.write(f.name, audio, sample_rate)
            temp_path = f.name
        
        try:
            # Capture audio
            capture = FileCapture(temp_path)
            captured_audio, sr = capture.capture()
            
            # Verify it can be processed
            assert captured_audio.dtype == np.float32  # nosec B101
            assert sr == sample_rate  # nosec B101
            
            # Simulate processing
            processed = captured_audio * 0.5  # Simple gain
            assert len(processed) == len(captured_audio)  # nosec B101
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_format_conversion_workflow(self):
        """Test format conversion in capture workflow."""
        sf = pytest.importorskip("soundfile")
        # Create audio at different sample rates
        for original_rate in [8000, 16000, 44100]:
            duration = 0.5
            t = np.linspace(0, duration, int(original_rate * duration))
            audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                sf.write(f.name, audio, original_rate)
                temp_path = f.name
            
            try:
                capture = FileCapture(temp_path)
                captured_audio, sr = capture.capture()
                
                assert sr == original_rate  # nosec B101
                assert len(captured_audio) == len(audio)  # nosec B101
            finally:
                Path(temp_path).unlink(missing_ok=True)
