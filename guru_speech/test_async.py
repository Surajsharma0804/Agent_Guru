"""
Unit tests for async methods in GuruSpeechEngine.

Tests async transcription methods, async command processing, and concurrent async requests.
Requirements: 12.4
"""

import pytest
import asyncio
import numpy as np
import soundfile as sf
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from guru_speech import GuruSpeechEngine, TranscriptionResult, CommandResult
from guru_speech.models import TranscriptionSegment
from guru_speech.exceptions import GuruSpeechError, AudioCaptureError


class TestAsyncTranscriptionMethods:
    """Test async transcription methods."""
    
    @pytest.mark.asyncio
    async def test_transcribe_file_async_returns_transcription_result(self):
        """Test that transcribe_file_async returns a TranscriptionResult."""
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate simple audio data (1 second of silence)
            sample_rate = 16000
            duration = 1.0
            audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Test async transcription
            result = await engine.transcribe_file_async(tmp_path)
            
            # Verify result structure
            assert isinstance(result, TranscriptionResult)
            assert isinstance(result.text, str)
            assert isinstance(result.language, str)
            assert isinstance(result.confidence, float)
            assert 0.0 <= result.confidence <= 1.0
            assert result.duration >= 0.0
            
        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_transcribe_file_async_with_language_parameter(self):
        """Test that transcribe_file_async accepts language parameter."""
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate simple audio data
            sample_rate = 16000
            duration = 1.0
            audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Test async transcription with language
            result = await engine.transcribe_file_async(tmp_path, language="en")
            
            # Verify result
            assert isinstance(result, TranscriptionResult)
            assert result.language == "en"
            
        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_transcribe_microphone_async_with_mocked_capture(self):
        """Test transcribe_microphone_async with mocked microphone capture."""
        # Mock the MicrophoneCapture to avoid actual microphone access
        with patch('guru_speech.MicrophoneCapture') as mock_mic:
            # Setup mock to return audio data
            sample_rate = 16000
            duration = 2.0
            audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
            
            mock_instance = MagicMock()
            mock_instance.capture.return_value = (audio_data, sample_rate)
            mock_mic.return_value = mock_instance
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Test async microphone transcription
            result = await engine.transcribe_microphone_async(duration=duration)
            
            # Verify result structure
            assert isinstance(result, TranscriptionResult)
            assert isinstance(result.text, str)
            assert isinstance(result.language, str)
            assert isinstance(result.confidence, float)
            assert 0.0 <= result.confidence <= 1.0
            
            # Verify mock was called
            mock_mic.assert_called_once()
            mock_instance.capture.assert_called_once_with(duration=duration)
    
    @pytest.mark.asyncio
    async def test_transcribe_microphone_async_requires_duration(self):
        """Test that transcribe_microphone_async requires duration parameter."""
        engine = GuruSpeechEngine()
        
        # Should raise error when duration is None
        with pytest.raises(GuruSpeechError) as exc_info:
            await engine.transcribe_microphone_async(duration=None)
        
        assert "Duration must be specified" in str(exc_info.value)


class TestAsyncCommandProcessing:
    """Test async command processing methods."""
    
    @pytest.mark.asyncio
    async def test_process_voice_command_async_with_file_source(self):
        """Test process_voice_command_async with file source."""
        # Create a temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate simple audio data
            sample_rate = 16000
            duration = 1.0
            audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
            sf.write(tmp_path, audio_data, sample_rate)
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Test async command processing
            result = await engine.process_voice_command_async(
                source="file",
                file_path=tmp_path
            )
            
            # Verify result structure
            assert isinstance(result, CommandResult)
            assert isinstance(result.raw_text, str)
            assert isinstance(result.is_command, bool)
            assert isinstance(result.confidence, float)
            assert 0.0 <= result.confidence <= 1.0
            
        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_process_voice_command_async_with_microphone_source(self):
        """Test process_voice_command_async with microphone source."""
        # Mock the MicrophoneCapture
        with patch('guru_speech.MicrophoneCapture') as mock_mic:
            # Setup mock
            sample_rate = 16000
            duration = 2.0
            audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
            
            mock_instance = MagicMock()
            mock_instance.capture.return_value = (audio_data, sample_rate)
            mock_mic.return_value = mock_instance
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Test async command processing
            result = await engine.process_voice_command_async(
                duration=duration,
                source="microphone"
            )
            
            # Verify result structure
            assert isinstance(result, CommandResult)
            assert isinstance(result.raw_text, str)
            assert isinstance(result.is_command, bool)
            
            # Verify mock was called
            mock_mic.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_voice_command_async_invalid_source(self):
        """Test that process_voice_command_async raises error for invalid source."""
        engine = GuruSpeechEngine()
        
        # Should raise error for invalid source
        with pytest.raises(GuruSpeechError) as exc_info:
            await engine.process_voice_command_async(
                source="invalid_source"
            )
        
        assert "Invalid source" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_voice_command_async_file_source_requires_path(self):
        """Test that file source requires file_path parameter."""
        engine = GuruSpeechEngine()
        
        # Should raise error when file_path is None with file source
        with pytest.raises(GuruSpeechError) as exc_info:
            await engine.process_voice_command_async(
                source="file",
                file_path=None
            )
        
        assert "file_path must be specified" in str(exc_info.value)


class TestConcurrentAsyncRequests:
    """Test concurrent async request handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_file_transcriptions(self):
        """Test multiple concurrent file transcriptions."""
        # Create multiple temporary audio files
        tmp_files = []
        try:
            for i in range(3):
                tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()
                
                # Generate audio data
                sample_rate = 16000
                duration = 1.0
                audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
                sf.write(tmp_path, audio_data, sample_rate)
                
                tmp_files.append(tmp_path)
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Create concurrent transcription tasks
            tasks = [
                engine.transcribe_file_async(tmp_path)
                for tmp_path in tmp_files
            ]
            
            # Execute concurrently
            results = await asyncio.gather(*tasks)
            
            # Verify all results
            assert len(results) == 3
            for result in results:
                assert isinstance(result, TranscriptionResult)
                assert isinstance(result.text, str)
                assert isinstance(result.language, str)
                assert 0.0 <= result.confidence <= 1.0
            
        finally:
            # Clean up
            for tmp_path in tmp_files:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_concurrent_command_processing(self):
        """Test multiple concurrent command processing requests."""
        # Create multiple temporary audio files
        tmp_files = []
        try:
            for i in range(3):
                tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()
                
                # Generate audio data
                sample_rate = 16000
                duration = 1.0
                audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
                sf.write(tmp_path, audio_data, sample_rate)
                
                tmp_files.append(tmp_path)
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Create concurrent command processing tasks
            tasks = [
                engine.process_voice_command_async(source="file", file_path=tmp_path)
                for tmp_path in tmp_files
            ]
            
            # Execute concurrently
            results = await asyncio.gather(*tasks)
            
            # Verify all results
            assert len(results) == 3
            for result in results:
                assert isinstance(result, CommandResult)
                assert isinstance(result.raw_text, str)
                assert isinstance(result.is_command, bool)
                assert 0.0 <= result.confidence <= 1.0
            
        finally:
            # Clean up
            for tmp_path in tmp_files:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self):
        """Test concurrent mix of transcription and command processing."""
        # Create temporary audio files
        tmp_files = []
        try:
            for i in range(2):
                tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()
                
                # Generate audio data
                sample_rate = 16000
                duration = 1.0
                audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
                sf.write(tmp_path, audio_data, sample_rate)
                
                tmp_files.append(tmp_path)
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Create mixed concurrent tasks
            tasks = [
                engine.transcribe_file_async(tmp_files[0]),
                engine.process_voice_command_async(source="file", file_path=tmp_files[1]),
                engine.transcribe_file_async(tmp_files[1]),
            ]
            
            # Execute concurrently
            results = await asyncio.gather(*tasks)
            
            # Verify results
            assert len(results) == 3
            assert isinstance(results[0], TranscriptionResult)
            assert isinstance(results[1], CommandResult)
            assert isinstance(results[2], TranscriptionResult)
            
        finally:
            # Clean up
            for tmp_path in tmp_files:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_share_model(self):
        """Test that concurrent requests reuse the same model instance."""
        # Create temporary audio files
        tmp_files = []
        try:
            for i in range(2):
                tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()
                
                # Generate audio data
                sample_rate = 16000
                duration = 1.0
                audio_data = np.zeros(int(sample_rate * duration), dtype=np.float32)
                sf.write(tmp_path, audio_data, sample_rate)
                
                tmp_files.append(tmp_path)
            
            # Initialize engine
            engine = GuruSpeechEngine()
            
            # Store reference to transcriber
            transcriber_id = id(engine.transcriber)
            
            # Create concurrent tasks
            tasks = [
                engine.transcribe_file_async(tmp_path)
                for tmp_path in tmp_files
            ]
            
            # Execute concurrently
            results = await asyncio.gather(*tasks)
            
            # Verify model instance is still the same
            assert id(engine.transcriber) == transcriber_id
            
            # Verify all results are valid
            assert len(results) == 2
            for result in results:
                assert isinstance(result, TranscriptionResult)
            
        finally:
            # Clean up
            for tmp_path in tmp_files:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
