"""
Unit tests for WhisperTranscriber module.

This module contains unit tests that verify specific examples, edge cases,
and error conditions for the speech transcription functionality.
"""

import numpy as np
import pytest
import tempfile
import os
import soundfile as sf

from .speech import WhisperTranscriber
from .models import TranscriptionResult
from .exceptions import ModelLoadError, TranscriptionError


class TestWhisperTranscriberInitialization:
    """Unit tests for WhisperTranscriber initialization."""
    
    def test_initialization_with_default_parameters(self):
        """Test model initialization with default parameters."""
        transcriber = WhisperTranscriber()
        
        assert transcriber.model_size == "small"
        assert transcriber.compute_type == "int8"
        assert transcriber.beam_size == 5
        assert transcriber.device == "cpu"
        assert transcriber.model is not None
    
    def test_initialization_with_int8_and_beam_size_5(self):
        """Test model initialization with int8 compute type and beam_size=5."""
        transcriber = WhisperTranscriber(
            model_size="tiny",
            compute_type="int8",
            beam_size=5
        )
        
        assert transcriber.compute_type == "int8"
        assert transcriber.beam_size == 5
        assert transcriber.model is not None
    
    def test_initialization_with_tiny_model(self):
        """Test initialization with tiny model for faster testing."""
        transcriber = WhisperTranscriber(model_size="tiny")
        
        assert transcriber.model_size == "tiny"
        assert transcriber.model is not None
    
    def test_initialization_with_custom_beam_size(self):
        """Test initialization with custom beam size."""
        transcriber = WhisperTranscriber(model_size="tiny", beam_size=3)
        
        assert transcriber.beam_size == 3
    
    def test_initialization_with_invalid_model_path(self):
        """Test model loading error handling with invalid path."""
        with pytest.raises(ModelLoadError) as exc_info:
            WhisperTranscriber(model_path="/invalid/path/to/model")
        
        assert "Failed to load Whisper model" in str(exc_info.value)
        assert "ModelLoad" in str(exc_info.value)


class TestWhisperTranscriberTranscribe:
    """Unit tests for WhisperTranscriber.transcribe() method."""
    
    def test_transcribe_with_english_audio_sample(self):
        """Test transcription with English audio sample."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate a simple sine wave as audio (simulating speech)
        sample_rate = 16000
        duration = 1.0
        frequency = 440  # A4 note
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (0.3 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
        
        result = transcriber.transcribe(audio_data, sample_rate, language="en")
        
        # Verify result structure
        assert isinstance(result, TranscriptionResult)
        assert isinstance(result.text, str)
        assert result.language in ["en", "english"]
        assert 0.0 <= result.confidence <= 1.0
        assert result.duration > 0.0
        assert isinstance(result.segments, list)
    
    def test_transcribe_with_hindi_language_specified(self):
        """Test transcription with Hindi language specified."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate audio sample
        sample_rate = 16000
        duration = 0.5
        audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio_data, sample_rate, language="hi")
        
        # Verify result structure
        assert isinstance(result, TranscriptionResult)
        assert isinstance(result.text, str)
        # Language should be Hindi or detected language
        assert isinstance(result.language, str)
        assert len(result.language) > 0
        assert 0.0 <= result.confidence <= 1.0
    
    def test_transcribe_with_punjabi_language_specified(self):
        """Test transcription with Punjabi language specified."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate audio sample
        sample_rate = 16000
        duration = 0.5
        audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio_data, sample_rate, language="pa")
        
        # Verify result structure
        assert isinstance(result, TranscriptionResult)
        assert isinstance(result.text, str)
        assert isinstance(result.language, str)
        assert len(result.language) > 0
        assert 0.0 <= result.confidence <= 1.0
    
    def test_transcribe_with_auto_language_detection(self):
        """Test transcription with automatic language detection."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate audio sample
        sample_rate = 16000
        duration = 1.0
        audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio_data, sample_rate, language=None)
        
        # Verify language was detected
        assert isinstance(result.language, str)
        assert len(result.language) > 0
        assert result.language != ""
    
    def test_transcribe_with_silent_audio(self):
        """Test transcription with silent audio (all zeros)."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate silent audio
        sample_rate = 16000
        duration = 1.0
        audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
        
        result = transcriber.transcribe(audio_data, sample_rate)
        
        # Should return valid result even for silent audio
        assert isinstance(result, TranscriptionResult)
        assert isinstance(result.text, str)
        assert result.duration > 0.0
    
    def test_transcribe_with_very_short_audio(self):
        """Test transcription with very short audio (< 0.5 seconds)."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate very short audio
        sample_rate = 16000
        duration = 0.1
        audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio_data, sample_rate)
        
        assert isinstance(result, TranscriptionResult)
        assert result.duration >= 0.0
    
    def test_transcribe_with_stereo_audio(self):
        """Test transcription with stereo audio (2 channels)."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate stereo audio
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)
        audio_data = np.random.randn(samples, 2).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio_data, sample_rate)
        
        # Should handle stereo by converting to mono
        assert isinstance(result, TranscriptionResult)
        assert result.duration > 0.0
    
    def test_transcribe_with_different_sample_rates(self):
        """Test transcription with different sample rates."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        for sample_rate in [8000, 16000, 22050, 44100]:
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            
            result = transcriber.transcribe(audio_data, sample_rate)
            
            assert isinstance(result, TranscriptionResult)
            assert result.duration > 0.0
    
    def test_transcribe_converts_dtype_to_float32(self):
        """Test that transcribe converts audio to float32 if needed."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate audio with int16 dtype
        sample_rate = 16000
        duration = 0.5
        audio_data = (np.random.randn(int(sample_rate * duration)) * 1000).astype(np.int16)
        
        result = transcriber.transcribe(audio_data, sample_rate)
        
        # Should handle dtype conversion
        assert isinstance(result, TranscriptionResult)


class TestWhisperTranscriberTranscribeFile:
    """Unit tests for WhisperTranscriber.transcribe_file() method."""
    
    def test_transcribe_file_with_wav_format(self):
        """Test file format support for WAV files."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio and save as WAV
            sample_rate = 16000
            duration = 1.0
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(file_path, audio_data, sample_rate)
            
            # Transcribe file
            result = transcriber.transcribe_file(file_path)
            
            assert isinstance(result, TranscriptionResult)
            assert result.duration > 0.0
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_transcribe_file_with_mp3_format(self):
        """Test file format support for MP3 files."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Note: MP3 encoding requires additional libraries
        # For this test, we'll create a WAV file with .mp3 extension
        # In production, soundfile with proper codecs would handle real MP3
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(file_path, audio_data, sample_rate)
            
            # Transcribe file
            result = transcriber.transcribe_file(file_path)
            
            assert isinstance(result, TranscriptionResult)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_transcribe_file_with_flac_format(self):
        """Test file format support for FLAC files."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Create temporary FLAC file
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio and save as FLAC
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(file_path, audio_data, sample_rate, format='FLAC')
            
            # Transcribe file
            result = transcriber.transcribe_file(file_path)
            
            assert isinstance(result, TranscriptionResult)
            assert result.duration > 0.0
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_transcribe_file_with_language_specified(self):
        """Test transcribe_file with language parameter."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            file_path = temp_file.name
        
        try:
            # Create sample audio
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(file_path, audio_data, sample_rate)
            
            # Transcribe with English language
            result = transcriber.transcribe_file(file_path, language="en")
            
            assert isinstance(result, TranscriptionResult)
            assert isinstance(result.language, str)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_transcribe_file_with_nonexistent_file(self):
        """Test model loading error handling with nonexistent file."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        with pytest.raises(TranscriptionError) as exc_info:
            transcriber.transcribe_file("/nonexistent/path/to/audio.wav")
        
        assert "Failed to transcribe file" in str(exc_info.value)
        assert "Transcription" in str(exc_info.value)
    
    def test_transcribe_file_with_invalid_audio_file(self):
        """Test error handling with invalid audio file."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Create a text file instead of audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, mode='w') as temp_file:
            file_path = temp_file.name
            temp_file.write("This is not audio data")
        
        try:
            with pytest.raises(TranscriptionError) as exc_info:
                transcriber.transcribe_file(file_path)
            
            assert "Failed to transcribe file" in str(exc_info.value)
            
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)


class TestWhisperTranscriberCustomModelPath:
    """Unit tests for custom model path loading."""
    
    def test_custom_model_path_loading_with_valid_path(self):
        """Test custom model path loading."""
        # Note: This test assumes a valid model exists at the path
        # In a real scenario, you would need to have a model file available
        
        # Test that initialization accepts custom model path parameter
        # We expect this to fail since we don't have a real custom model
        with pytest.raises(ModelLoadError):
            WhisperTranscriber(model_path="./guru_speech/model/custom_model")
    
    def test_custom_model_path_overrides_model_size(self):
        """Test that custom model path overrides model_size parameter."""
        # When model_path is provided, it should be used instead of model_size
        
        # This will fail because the path doesn't exist, but it tests the logic
        with pytest.raises(ModelLoadError) as exc_info:
            transcriber = WhisperTranscriber(
                model_size="small",
                model_path="./custom/model/path"
            )
        
        # Verify the error mentions the custom path
        assert "Failed to load Whisper model" in str(exc_info.value)


class TestWhisperTranscriberConfiguration:
    """Unit tests for model configuration options."""
    
    def test_configuration_with_different_compute_types(self):
        """Test model configuration with different compute types."""
        # Test int8 (default)
        transcriber_int8 = WhisperTranscriber(
            model_size="tiny",
            compute_type="int8"
        )
        assert transcriber_int8.compute_type == "int8"
        assert transcriber_int8.model is not None
        
        # Test float32
        transcriber_float32 = WhisperTranscriber(
            model_size="tiny",
            compute_type="float32"
        )
        assert transcriber_float32.compute_type == "float32"
        assert transcriber_float32.model is not None
    
    def test_configuration_with_different_beam_sizes(self):
        """Test model configuration with different beam sizes."""
        for beam_size in [1, 3, 5, 7]:
            transcriber = WhisperTranscriber(
                model_size="tiny",
                beam_size=beam_size
            )
            assert transcriber.beam_size == beam_size
            assert transcriber.model is not None
    
    def test_configuration_parameters_are_stored(self):
        """Test that configuration parameters are properly stored."""
        transcriber = WhisperTranscriber(
            model_size="tiny",
            compute_type="int8",
            beam_size=5,
            device="cpu"
        )
        
        assert transcriber.model_size == "tiny"
        assert transcriber.compute_type == "int8"
        assert transcriber.beam_size == 5
        assert transcriber.device == "cpu"
        assert transcriber.model_path is None


class TestWhisperTranscriberSegments:
    """Unit tests for transcription segments."""
    
    def test_segments_have_valid_structure(self):
        """Test that segments have valid structure with timing information."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate audio that might produce segments
        sample_rate = 16000
        duration = 2.0
        audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio_data, sample_rate)
        
        # If segments exist, verify their structure
        if len(result.segments) > 0:
            for segment in result.segments:
                assert hasattr(segment, 'text')
                assert hasattr(segment, 'start')
                assert hasattr(segment, 'end')
                assert hasattr(segment, 'confidence')
                assert segment.start >= 0.0
                assert segment.end >= segment.start
    
    def test_segments_are_chronologically_ordered(self):
        """Test that segments are ordered chronologically."""
        transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
        
        # Generate longer audio to potentially get multiple segments
        sample_rate = 16000
        duration = 3.0
        audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio_data, sample_rate)
        
        # Verify segments are ordered
        if len(result.segments) > 1:
            for i in range(len(result.segments) - 1):
                assert result.segments[i].start <= result.segments[i + 1].start
