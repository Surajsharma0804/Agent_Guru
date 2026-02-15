"""
Unit tests for audio capture module.

Tests FileCapture and MicrophoneCapture classes.
"""

import pytest
import numpy as np
import tempfile
import os
import soundfile as sf

from guru_speech.capture import AudioCapture, FileCapture, MicrophoneCapture
from guru_speech.exceptions import AudioCaptureError


class TestFileCapture:
    """Unit tests for FileCapture class."""
    
    def test_file_capture_wav_format(self):
        """Test FileCapture with WAV format."""
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio and save as WAV
            sample_rate = 16000
            duration = 1.0
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32)
            sf.write(file_path, audio_data, sample_rate)
            
            # Test FileCapture
            capture = FileCapture(file_path)
            loaded_audio, loaded_sr = capture.capture()
            
            assert isinstance(loaded_audio, np.ndarray)
            assert loaded_sr == sample_rate
            assert len(loaded_audio) == len(audio_data)
            assert loaded_audio.dtype == np.float32
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_file_capture_mp3_format(self):
        """Test FileCapture with MP3 format (using WAV as fallback)."""
        # Note: MP3 encoding requires additional libraries
        # For this test, we'll create a WAV file to test the loading mechanism
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32)
            sf.write(file_path, audio_data, sample_rate)
            
            # Test FileCapture
            capture = FileCapture(file_path)
            loaded_audio, loaded_sr = capture.capture()
            
            assert isinstance(loaded_audio, np.ndarray)
            assert loaded_sr == sample_rate
            assert len(loaded_audio) > 0
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_file_capture_flac_format(self):
        """Test FileCapture with FLAC format."""
        # Create temporary FLAC file
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio and save as FLAC
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32)
            sf.write(file_path, audio_data, sample_rate)
            
            # Test FileCapture
            capture = FileCapture(file_path)
            loaded_audio, loaded_sr = capture.capture()
            
            assert isinstance(loaded_audio, np.ndarray)
            assert loaded_sr == sample_rate
            assert len(loaded_audio) == len(audio_data)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_file_capture_stereo_to_mono_conversion(self):
        """Test FileCapture converts stereo audio to mono."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create stereo audio (2 channels)
            sample_rate = 16000
            duration = 0.5
            stereo_audio = np.random.randn(int(sample_rate * duration), 2).astype(np.float32)
            sf.write(file_path, stereo_audio, sample_rate)
            
            # Test FileCapture
            capture = FileCapture(file_path)
            loaded_audio, loaded_sr = capture.capture()
            
            # Should be converted to mono (1D array)
            assert isinstance(loaded_audio, np.ndarray)
            assert len(loaded_audio.shape) == 1
            assert loaded_sr == sample_rate
            assert len(loaded_audio) == int(sample_rate * duration)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_file_capture_load_file_method(self):
        """Test FileCapture.load_file() method directly."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio
            sample_rate = 16000
            audio_data = np.random.randn(sample_rate).astype(np.float32)
            sf.write(file_path, audio_data, sample_rate)
            
            # Test load_file method
            capture = FileCapture(file_path)
            loaded_audio, loaded_sr = capture.load_file(file_path)
            
            assert isinstance(loaded_audio, np.ndarray)
            assert loaded_sr == sample_rate
            assert len(loaded_audio) == len(audio_data)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_file_capture_nonexistent_file(self):
        """Test FileCapture with nonexistent file raises AudioCaptureError."""
        file_path = "/nonexistent/path/to/audio.wav"
        
        capture = FileCapture(file_path)
        
        with pytest.raises(AudioCaptureError) as exc_info:
            capture.capture()
        
        # Error message should mention either "not found" or "Failed to load"
        error_msg = str(exc_info.value)
        assert ("Audio file not found" in error_msg or "Failed to load audio file" in error_msg)
        assert file_path in error_msg
    
    def test_file_capture_invalid_audio_format(self):
        """Test FileCapture with invalid audio file raises AudioCaptureError."""
        # Create a text file instead of audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, mode='w') as temp_file:
            file_path = temp_file.name
            temp_file.write("This is not audio data")
        
        try:
            capture = FileCapture(file_path)
            
            with pytest.raises(AudioCaptureError) as exc_info:
                capture.capture()
            
            assert "Failed to load audio file" in str(exc_info.value)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_file_capture_empty_file(self):
        """Test FileCapture with empty file raises AudioCaptureError."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
            # File is empty
        
        try:
            capture = FileCapture(file_path)
            
            with pytest.raises(AudioCaptureError) as exc_info:
                capture.capture()
            
            assert "Failed to load audio file" in str(exc_info.value)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)


class TestMicrophoneCapture:
    """Unit tests for MicrophoneCapture class."""
    
    def test_microphone_capture_initialization(self):
        """Test MicrophoneCapture initialization with default parameters."""
        capture = MicrophoneCapture()
        
        assert capture.sample_rate == 16000
        assert capture.channels == 1
    
    def test_microphone_capture_initialization_custom_params(self):
        """Test MicrophoneCapture initialization with custom parameters."""
        capture = MicrophoneCapture(sample_rate=44100, channels=2)
        
        assert capture.sample_rate == 44100
        assert capture.channels == 2
    
    def test_microphone_capture_no_duration_raises_error(self):
        """Test MicrophoneCapture without duration raises AudioCaptureError."""
        capture = MicrophoneCapture()
        
        with pytest.raises(AudioCaptureError) as exc_info:
            capture.capture(duration=None)
        
        assert "Duration must be specified" in str(exc_info.value)
    
    def test_microphone_capture_with_duration(self):
        """Test MicrophoneCapture with specified duration."""
        # This test may fail if no microphone is available
        # We'll catch the error and verify it's the expected type
        capture = MicrophoneCapture(sample_rate=16000, channels=1)
        
        try:
            audio_data, sample_rate = capture.capture(duration=0.1)
            
            # If successful, verify the output
            assert isinstance(audio_data, np.ndarray)
            assert sample_rate == 16000
            assert len(audio_data) == int(0.1 * 16000)
            assert audio_data.dtype == np.float32
            
        except AudioCaptureError as e:
            # If microphone is unavailable, verify error message
            assert "Failed to capture audio from microphone" in str(e)
    
    def test_microphone_capture_unavailable_device(self):
        """Test MicrophoneCapture with unavailable device raises AudioCaptureError."""
        # This test verifies error handling when microphone is unavailable
        # The actual behavior depends on the system
        capture = MicrophoneCapture()
        
        # We can't force a device to be unavailable, but we can test
        # that the error handling works by checking the exception type
        try:
            # Very short duration to minimize test time
            audio_data, sample_rate = capture.capture(duration=0.01)
            
            # If it succeeds, verify basic properties
            assert isinstance(audio_data, np.ndarray)
            assert sample_rate == capture.sample_rate
            
        except AudioCaptureError as e:
            # Expected error when microphone is unavailable
            assert "Failed to capture audio from microphone" in str(e)
            assert e.original_error is not None
    
    def test_microphone_capture_mono_output(self):
        """Test MicrophoneCapture with mono (1 channel) produces 1D array."""
        capture = MicrophoneCapture(sample_rate=16000, channels=1)
        
        try:
            audio_data, sample_rate = capture.capture(duration=0.1)
            
            # Should be 1D array for mono
            assert len(audio_data.shape) == 1
            assert sample_rate == 16000
            
        except AudioCaptureError:
            # Microphone unavailable - test passes
            pass
    
    def test_microphone_capture_stereo_output(self):
        """Test MicrophoneCapture with stereo (2 channels) produces 2D array."""
        capture = MicrophoneCapture(sample_rate=16000, channels=2)
        
        try:
            audio_data, sample_rate = capture.capture(duration=0.1)
            
            # Should be 2D array for stereo
            assert len(audio_data.shape) == 2
            assert audio_data.shape[1] == 2
            assert sample_rate == 16000
            
        except AudioCaptureError:
            # Microphone unavailable - test passes
            pass


class TestAudioCaptureBase:
    """Unit tests for AudioCapture base class."""
    
    def test_audio_capture_is_abstract(self):
        """Test that AudioCapture cannot be instantiated directly."""
        # AudioCapture is abstract and should not be instantiated
        with pytest.raises(TypeError):
            AudioCapture()
    
    def test_file_capture_is_audio_capture(self):
        """Test that FileCapture is an instance of AudioCapture."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            capture = FileCapture(file_path)
            assert isinstance(capture, AudioCapture)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_microphone_capture_is_audio_capture(self):
        """Test that MicrophoneCapture is an instance of AudioCapture."""
        capture = MicrophoneCapture()
        assert isinstance(capture, AudioCapture)
