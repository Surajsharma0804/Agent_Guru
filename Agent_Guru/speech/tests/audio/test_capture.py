"""Tests for audio capture."""

import pytest
import numpy as np
import tempfile
import soundfile as sf
from pathlib import Path

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
        assert capture.sample_rate == 16000
        assert capture.channels == 1
        assert capture.device is None
    
    def test_initialization_custom(self):
        """Test microphone capture initialization with custom settings."""
        capture = MicrophoneCapture(
            sample_rate=44100,
            channels=2,
            device=0
        )
        assert capture.sample_rate == 44100
        assert capture.channels == 2
        assert capture.device == 0
    
    def test_list_devices(self):
        """Test listing audio devices."""
        devices = MicrophoneCapture.list_devices()
        assert isinstance(devices, list)
        # Should have at least one input device on most systems
        # (may be 0 in CI environments without audio)
        for device in devices:
            assert 'id' in device
            assert 'name' in device
            assert 'channels' in device
            assert 'sample_rate' in device
    
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
            
            assert isinstance(audio, np.ndarray)
            assert audio.dtype == np.float32
            assert sample_rate == 16000
            # Should have approximately 0.5 seconds of audio
            expected_samples = int(0.5 * 16000)
            assert abs(len(audio) - expected_samples) < 100
        except AudioInputError:
            # May fail in CI environments without audio devices
            pytest.skip("Audio capture not available")


class TestFileCapture:
    """Test suite for FileCapture."""
    
    @pytest.fixture
    def temp_audio_file(self):
        """Create a temporary audio file for testing."""
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
        assert capture.file_path == temp_audio_file
    
    def test_load_file_complete(self, temp_audio_file):
        """Test loading complete audio file."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.load_file(temp_audio_file)
        
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert sample_rate == 16000
        assert len(audio) == 16000  # 1 second at 16kHz
    
    def test_load_file_with_duration(self, temp_audio_file):
        """Test loading partial audio file."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.load_file(temp_audio_file, duration=0.5)
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) == 8000  # 0.5 seconds at 16kHz
    
    def test_load_stereo_converts_to_mono(self, temp_stereo_file):
        """Test that stereo audio is converted to mono."""
        capture = FileCapture(temp_stereo_file)
        audio, sample_rate = capture.load_file(temp_stereo_file)
        
        assert audio.ndim == 1, "Should be mono (1D array)"
        assert len(audio) == 16000
    
    def test_capture_method(self, temp_audio_file):
        """Test capture method (wrapper for load_file)."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.capture()
        
        assert isinstance(audio, np.ndarray)
        assert sample_rate == 16000
    
    def test_capture_with_duration(self, temp_audio_file):
        """Test capture method with duration."""
        capture = FileCapture(temp_audio_file)
        audio, sample_rate = capture.capture(duration=0.5)
        
        assert len(audio) == 8000
    
    def test_load_nonexistent_file_raises_error(self):
        """Test loading non-existent file raises error."""
        capture = FileCapture("nonexistent.wav")
        with pytest.raises(AudioInputError):
            capture.load_file("nonexistent.wav")
    
    def test_get_file_info(self, temp_audio_file):
        """Test getting file information."""
        info = FileCapture.get_file_info(temp_audio_file)
        
        assert isinstance(info, dict)
        assert 'duration' in info
        assert 'sample_rate' in info
        assert 'channels' in info
        assert 'format' in info
        
        assert info['sample_rate'] == 16000
        assert info['channels'] == 1
        assert abs(info['duration'] - 1.0) < 0.01
    
    def test_get_file_info_nonexistent_raises_error(self):
        """Test getting info for non-existent file raises error."""
        with pytest.raises(AudioInputError):
            FileCapture.get_file_info("nonexistent.wav")
    
    def test_load_different_formats(self):
        """Test loading different audio formats."""
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
                
                assert isinstance(audio, np.ndarray)
                assert sr == sample_rate
                assert len(audio) == len(audio_data)
            finally:
                Path(temp_path).unlink(missing_ok=True)


class TestAudioCaptureIntegration:
    """Integration tests for audio capture."""
    
    def test_file_capture_to_processing_pipeline(self):
        """Test file capture in a processing pipeline."""
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
            assert captured_audio.dtype == np.float32
            assert sr == sample_rate
            
            # Simulate processing
            processed = captured_audio * 0.5  # Simple gain
            assert len(processed) == len(captured_audio)
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_format_conversion_workflow(self):
        """Test format conversion in capture workflow."""
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
                
                assert sr == original_rate
                assert len(captured_audio) == len(audio)
            finally:
                Path(temp_path).unlink(missing_ok=True)
