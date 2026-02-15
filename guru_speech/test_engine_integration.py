"""
Integration tests for GuruSpeechEngine module.

This module contains integration tests that verify the end-to-end functionality
of the GuruSpeechEngine, including the complete pipeline from audio capture
through transcription to command interpretation.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import soundfile as sf

from . import GuruSpeechEngine
from .models import TranscriptionResult, CommandResult, TranscriptionSegment
from .exceptions import GuruSpeechError, AudioCaptureError


class TestEndToEndPipelineWithFileInput:
    """Test the complete pipeline with file input."""
    
    def test_transcribe_file_end_to_end(self):
        """
        Test end-to-end pipeline with file input.
        
        Verifies that:
        - File is loaded correctly
        - Noise reduction is applied (if enabled)
        - Audio is transcribed
        - Result contains expected fields
        
        Requirements: 9.3
        """
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate test audio (1 second of sine wave)
            sample_rate = 16000
            duration = 1.0
            frequency = 440.0  # A4 note
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = (np.sin(2 * np.pi * frequency * t) * 0.3).astype(np.float32)
            
            # Write audio file
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Mock the Whisper model to avoid loading the actual model
            with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
                mock_model = MagicMock()
                
                # Mock transcribe method
                def mock_transcribe(audio, beam_size=5, language=None):
                    mock_segment = MagicMock()
                    mock_segment.text = "test audio transcription"
                    mock_segment.start = 0.0
                    mock_segment.end = 1.0
                    mock_segment.avg_logprob = -0.3
                    
                    mock_info = MagicMock()
                    mock_info.language = "en"
                    
                    return iter([mock_segment]), mock_info
                
                mock_model.transcribe = mock_transcribe
                mock_whisper_class.return_value = mock_model
                
                # Create engine
                engine = GuruSpeechEngine(enable_noise_reduction=True)
                
                # Transcribe the file
                result = engine.transcribe_file(tmp_path)
                
                # Verify result structure
                assert isinstance(result, TranscriptionResult)
                assert result.text == "test audio transcription"
                assert result.language == "en"
                assert 0.0 <= result.confidence <= 1.0
                assert result.duration >= 0.0
                assert len(result.segments) > 0
                
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    
    def test_transcribe_file_without_noise_reduction(self):
        """
        Test file transcription with noise reduction disabled.
        
        Requirements: 9.3, 11.2
        """
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate test audio
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            
            # Write audio file
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Mock the Whisper model
            with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
                mock_model = MagicMock()
                
                def mock_transcribe(audio, beam_size=5, language=None):
                    mock_segment = MagicMock()
                    mock_segment.text = "noise reduction disabled"
                    mock_segment.start = 0.0
                    mock_segment.end = 0.5
                    mock_segment.avg_logprob = -0.4
                    
                    mock_info = MagicMock()
                    mock_info.language = "en"
                    
                    return iter([mock_segment]), mock_info
                
                mock_model.transcribe = mock_transcribe
                mock_whisper_class.return_value = mock_model
                
                # Create engine with noise reduction disabled
                engine = GuruSpeechEngine(enable_noise_reduction=False)
                
                # Verify noise cleaner is None
                assert engine.noise_cleaner is None
                
                # Transcribe the file
                result = engine.transcribe_file(tmp_path)
                
                # Verify result
                assert result.text == "noise reduction disabled"
                assert result.language == "en"
                
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)



class TestEndToEndPipelineWithMicrophoneInput:
    """Test the complete pipeline with microphone input (mocked)."""
    
    def test_transcribe_microphone_end_to_end(self):
        """
        Test end-to-end pipeline with microphone input (mocked).
        
        Verifies that:
        - Microphone capture works
        - Audio is processed through the pipeline
        - Result is returned correctly
        
        Requirements: 9.3
        """
        # Mock the Whisper model
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            
            def mock_transcribe(audio, beam_size=5, language=None):
                mock_segment = MagicMock()
                mock_segment.text = "microphone test transcription"
                mock_segment.start = 0.0
                mock_segment.end = 2.0
                mock_segment.avg_logprob = -0.25
                
                mock_info = MagicMock()
                mock_info.language = "en"
                
                return iter([mock_segment]), mock_info
            
            mock_model.transcribe = mock_transcribe
            mock_whisper_class.return_value = mock_model
            
            # Mock microphone capture
            with patch('guru_speech.MicrophoneCapture') as mock_mic_class:
                mock_mic = Mock()
                
                # Generate mock audio data
                sample_rate = 16000
                duration = 2.0
                audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
                
                mock_mic.capture.return_value = (audio_data, sample_rate)
                mock_mic_class.return_value = mock_mic
                
                # Create engine
                engine = GuruSpeechEngine()
                
                # Transcribe from microphone
                result = engine.transcribe_microphone(duration=2.0)
                
                # Verify result
                assert isinstance(result, TranscriptionResult)
                assert result.text == "microphone test transcription"
                assert result.language == "en"
                assert 0.0 <= result.confidence <= 1.0
                assert result.duration >= 0.0
                
                # Verify microphone was called with correct duration
                mock_mic.capture.assert_called_once_with(duration=2.0)

    
    def test_transcribe_microphone_requires_duration(self):
        """
        Test that microphone transcription requires duration parameter.
        
        Requirements: 9.3
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            engine = GuruSpeechEngine()
            
            # Attempt to transcribe without duration
            with pytest.raises(GuruSpeechError) as exc_info:
                engine.transcribe_microphone(duration=None)
            
            assert "Duration must be specified" in str(exc_info.value)


class TestProcessVoiceCommand:
    """Test the process_voice_command method."""
    
    def test_process_voice_command_returns_command_result(self):
        """
        Test that process_voice_command returns CommandResult.
        
        Verifies the complete pipeline:
        - Audio capture
        - Transcription
        - Command interpretation
        
        Requirements: 9.3, 11.2
        """
        # Mock the Whisper model
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            
            def mock_transcribe(audio, beam_size=5, language=None):
                mock_segment = MagicMock()
                mock_segment.text = "open youtube"
                mock_segment.start = 0.0
                mock_segment.end = 1.0
                mock_segment.avg_logprob = -0.2
                
                mock_info = MagicMock()
                mock_info.language = "en"
                
                return iter([mock_segment]), mock_info
            
            mock_model.transcribe = mock_transcribe
            mock_whisper_class.return_value = mock_model
            
            # Mock microphone capture
            with patch('guru_speech.MicrophoneCapture') as mock_mic_class:
                mock_mic = Mock()
                audio_data = np.random.randn(16000).astype(np.float32) * 0.1
                mock_mic.capture.return_value = (audio_data, 16000)
                mock_mic_class.return_value = mock_mic
                
                # Create engine
                engine = GuruSpeechEngine()
                
                # Process voice command from microphone
                result = engine.process_voice_command(duration=1.0, source="microphone")
                
                # Verify result is CommandResult
                assert isinstance(result, CommandResult)
                assert result.raw_text == "open youtube"
                assert result.is_command is True
                assert result.action_id == "OPEN_YOUTUBE"
                assert result.language == "en"

    
    def test_process_voice_command_from_file(self):
        """
        Test process_voice_command with file source.
        
        Requirements: 9.3, 11.2
        """
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate test audio
            sample_rate = 16000
            duration = 1.0
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Mock the Whisper model
            with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
                mock_model = MagicMock()
                
                def mock_transcribe(audio, beam_size=5, language=None):
                    mock_segment = MagicMock()
                    mock_segment.text = "search for python tutorials"
                    mock_segment.start = 0.0
                    mock_segment.end = 1.0
                    mock_segment.avg_logprob = -0.3
                    
                    mock_info = MagicMock()
                    mock_info.language = "en"
                    
                    return iter([mock_segment]), mock_info
                
                mock_model.transcribe = mock_transcribe
                mock_whisper_class.return_value = mock_model
                
                # Create engine
                engine = GuruSpeechEngine()
                
                # Process voice command from file
                result = engine.process_voice_command(source="file", file_path=tmp_path)
                
                # Verify result
                assert isinstance(result, CommandResult)
                assert result.raw_text == "search for python tutorials"
                assert result.is_command is True
                assert result.action_id == "SEARCH"
                assert "query" in result.parameters
                
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    
    def test_process_voice_command_invalid_source(self):
        """
        Test that invalid source raises error.
        
        Requirements: 9.3
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            engine = GuruSpeechEngine()
            
            with pytest.raises(GuruSpeechError) as exc_info:
                engine.process_voice_command(source="invalid_source")
            
            assert "Invalid source" in str(exc_info.value)
    
    def test_process_voice_command_file_without_path(self):
        """
        Test that file source without file_path raises error.
        
        Requirements: 9.3
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            engine = GuruSpeechEngine()
            
            with pytest.raises(GuruSpeechError) as exc_info:
                engine.process_voice_command(source="file", file_path=None)
            
            assert "file_path must be specified" in str(exc_info.value)


class TestPipelineConsistency:
    """Test that pipeline processes files and microphone input consistently."""
    
    def test_file_and_microphone_produce_same_output_format(self):
        """
        Test that file and microphone input produce consistent output format.
        
        Both should return TranscriptionResult with the same structure.
        
        Requirements: 9.3, 11.2
        """
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate test audio
            sample_rate = 16000
            duration = 1.0
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Mock the Whisper model
            with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
                mock_model = MagicMock()
                
                def mock_transcribe(audio, beam_size=5, language=None):
                    mock_segment = MagicMock()
                    mock_segment.text = "consistent output"
                    mock_segment.start = 0.0
                    mock_segment.end = 1.0
                    mock_segment.avg_logprob = -0.3
                    
                    mock_info = MagicMock()
                    mock_info.language = "en"
                    
                    return iter([mock_segment]), mock_info
                
                mock_model.transcribe = mock_transcribe
                mock_whisper_class.return_value = mock_model
                
                # Mock microphone capture
                with patch('guru_speech.MicrophoneCapture') as mock_mic_class:
                    mock_mic = Mock()
                    mock_mic.capture.return_value = (audio_data, sample_rate)
                    mock_mic_class.return_value = mock_mic
                    
                    # Create engine
                    engine = GuruSpeechEngine()
                    
                    # Transcribe from file
                    file_result = engine.transcribe_file(tmp_path)
                    
                    # Transcribe from microphone
                    mic_result = engine.transcribe_microphone(duration=1.0)
                    
                    # Verify both results have the same structure
                    assert type(file_result) == type(mic_result)
                    assert isinstance(file_result, TranscriptionResult)
                    assert isinstance(mic_result, TranscriptionResult)
                    
                    # Verify both have the same fields
                    assert hasattr(file_result, 'text')
                    assert hasattr(mic_result, 'text')
                    assert hasattr(file_result, 'language')
                    assert hasattr(mic_result, 'language')
                    assert hasattr(file_result, 'confidence')
                    assert hasattr(mic_result, 'confidence')
                    assert hasattr(file_result, 'segments')
                    assert hasattr(mic_result, 'segments')
                    assert hasattr(file_result, 'duration')
                    assert hasattr(mic_result, 'duration')
                    
                    # Verify field types are consistent
                    assert type(file_result.text) == type(mic_result.text)
                    assert type(file_result.language) == type(mic_result.language)
                    assert type(file_result.confidence) == type(mic_result.confidence)
                    assert type(file_result.segments) == type(mic_result.segments)
                    assert type(file_result.duration) == type(mic_result.duration)
                    
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)



class TestResourceCleanup:
    """Test resource cleanup after processing."""
    
    def test_file_handle_cleanup_after_transcription(self):
        """
        Test that file handles are properly closed after transcription.
        
        Requirements: 11.2, 11.4
        """
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate test audio
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Mock the Whisper model
            with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
                mock_model = MagicMock()
                
                def mock_transcribe(audio, beam_size=5, language=None):
                    mock_segment = MagicMock()
                    mock_segment.text = "cleanup test"
                    mock_segment.start = 0.0
                    mock_segment.end = 0.5
                    mock_segment.avg_logprob = -0.3
                    
                    mock_info = MagicMock()
                    mock_info.language = "en"
                    
                    return iter([mock_segment]), mock_info
                
                mock_model.transcribe = mock_transcribe
                mock_whisper_class.return_value = mock_model
                
                # Create engine
                engine = GuruSpeechEngine()
                
                # Transcribe the file
                result = engine.transcribe_file(tmp_path)
                
                # Verify transcription succeeded
                assert result.text == "cleanup test"
                
                # Try to delete the file - should succeed if file handle is closed
                os.unlink(tmp_path)
                
                # Verify file was deleted
                assert not os.path.exists(tmp_path)
                
        except Exception:
            # Clean up if test fails
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    
    def test_multiple_transcriptions_dont_leak_resources(self):
        """
        Test that multiple transcriptions don't leak file handles or memory.
        
        Requirements: 11.2, 11.4
        """
        # Create temporary audio files
        temp_files = []
        
        try:
            for i in range(5):
                tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()
                temp_files.append(tmp_path)
                
                # Generate test audio
                sample_rate = 16000
                duration = 0.3
                audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
                sf.write(tmp_path, audio_data, sample_rate)
            
            # Mock the Whisper model
            with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
                mock_model = MagicMock()
                
                def mock_transcribe(audio, beam_size=5, language=None):
                    mock_segment = MagicMock()
                    mock_segment.text = f"transcription {len(audio)}"
                    mock_segment.start = 0.0
                    mock_segment.end = 0.3
                    mock_segment.avg_logprob = -0.3
                    
                    mock_info = MagicMock()
                    mock_info.language = "en"
                    
                    return iter([mock_segment]), mock_info
                
                mock_model.transcribe = mock_transcribe
                mock_whisper_class.return_value = mock_model
                
                # Create engine
                engine = GuruSpeechEngine()
                
                # Transcribe all files
                for tmp_path in temp_files:
                    result = engine.transcribe_file(tmp_path)
                    assert result.text is not None
                
                # All files should be closeable/deletable after transcription
                for tmp_path in temp_files:
                    os.unlink(tmp_path)
                    assert not os.path.exists(tmp_path)
                
                temp_files = []  # Clear list since files are deleted
                
        finally:
            # Clean up any remaining files
            for tmp_path in temp_files:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)



class TestConfigurationOptions:
    """Test various configuration options."""
    
    def test_compute_type_configuration(self):
        """
        Test that compute_type configuration is applied correctly.
        
        Requirements: 11.2
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            # Test int8 (default)
            engine_int8 = GuruSpeechEngine(compute_type="int8")
            assert engine_int8.transcriber.compute_type == "int8"
            
            # Test float16
            engine_float16 = GuruSpeechEngine(compute_type="float16")
            assert engine_float16.transcriber.compute_type == "float16"
            
            # Test float32
            engine_float32 = GuruSpeechEngine(compute_type="float32")
            assert engine_float32.transcriber.compute_type == "float32"
    
    def test_beam_size_configuration(self):
        """
        Test that beam_size configuration is applied correctly.
        
        Requirements: 11.2
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            # Test default beam_size=5
            engine_default = GuruSpeechEngine()
            assert engine_default.transcriber.beam_size == 5
            
            # Test custom beam_size
            engine_custom = GuruSpeechEngine(beam_size=10)
            assert engine_custom.transcriber.beam_size == 10
    
    def test_noise_reduction_configuration(self):
        """
        Test that noise reduction can be enabled/disabled.
        
        Requirements: 11.2
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            # Test with noise reduction enabled (default)
            engine_enabled = GuruSpeechEngine(enable_noise_reduction=True)
            assert engine_enabled.enable_noise_reduction is True
            assert engine_enabled.noise_cleaner is not None
            
            # Test with noise reduction disabled
            engine_disabled = GuruSpeechEngine(enable_noise_reduction=False)
            assert engine_disabled.enable_noise_reduction is False
            assert engine_disabled.noise_cleaner is None
    
    def test_noise_reduction_parameters_configuration(self):
        """
        Test that noise reduction parameters can be configured.
        
        Requirements: 11.2
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            # Test custom noise reduction parameters
            engine = GuruSpeechEngine(
                enable_noise_reduction=True,
                noise_stationary=False,
                noise_prop_decrease=0.8
            )
            
            assert engine.noise_cleaner is not None
            assert engine.noise_cleaner.stationary is False
            assert engine.noise_cleaner.prop_decrease == 0.8
    
    def test_sample_rate_configuration(self):
        """
        Test that sample rate configuration is applied correctly.
        
        Requirements: 11.2
        """
        with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            # Test default sample rate
            engine_default = GuruSpeechEngine()
            assert engine_default.sample_rate == 16000
            
            # Test custom sample rate
            engine_custom = GuruSpeechEngine(sample_rate=22050)
            assert engine_custom.sample_rate == 22050
    
    def test_configuration_integration_with_transcription(self):
        """
        Test that configuration options work correctly during transcription.
        
        Requirements: 11.2, 11.4
        """
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate test audio
            sample_rate = 16000
            duration = 0.5
            audio_data = np.random.randn(int(sample_rate * duration)).astype(np.float32) * 0.1
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Mock the Whisper model
            with patch('guru_speech.speech.WhisperModel') as mock_whisper_class:
                mock_model = MagicMock()
                
                def mock_transcribe(audio, beam_size=5, language=None):
                    mock_segment = MagicMock()
                    mock_segment.text = f"beam_size_{beam_size}"
                    mock_segment.start = 0.0
                    mock_segment.end = 0.5
                    mock_segment.avg_logprob = -0.3
                    
                    mock_info = MagicMock()
                    mock_info.language = "en"
                    
                    return iter([mock_segment]), mock_info
                
                mock_model.transcribe = mock_transcribe
                mock_whisper_class.return_value = mock_model
                
                # Create engine with custom configuration
                engine = GuruSpeechEngine(
                    compute_type="float16",
                    beam_size=8,
                    enable_noise_reduction=False
                )
                
                # Transcribe file
                result = engine.transcribe_file(tmp_path)
                
                # Verify configuration was used
                assert result.text == "beam_size_8"
                assert engine.transcriber.compute_type == "float16"
                assert engine.transcriber.beam_size == 8
                assert engine.noise_cleaner is None
                
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
