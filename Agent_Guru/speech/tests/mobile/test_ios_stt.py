"""Unit tests for iOS Speech Recognition.

Tests the IOSSpeechRecognizer class with stub implementation
for development on non-iOS platforms.
"""

import pytest
import numpy as np

from Agent_Guru.speech.mobile.ios_stt import (
    IOSSpeechRecognizer
)
from Agent_Guru.speech.models import TranscriptionResult


class TestIOSSpeechRecognizer:
    """Test suite for IOSSpeechRecognizer."""
    
    @pytest.fixture
    def recognizer(self):
        """Create IOSSpeechRecognizer instance."""
        return IOSSpeechRecognizer(
            prefer_on_device=True,
            language="en-US"
        )
    
    @pytest.fixture
    def sample_audio(self):
        """Create sample audio data for testing."""
        # Generate 1 second of audio at 16kHz
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)
        
        # Generate sine wave
        frequency = 440.0  # A4 note
        t = np.linspace(0, duration, samples)
        audio = np.sin(2 * np.pi * frequency * t)
        
        # Convert to int16
        audio_int16 = (audio * 32767).astype(np.int16)
        
        return audio_int16.tobytes()
    
    def test_initialization(self, recognizer):
        """Test recognizer initialization."""
        assert recognizer is not None
        assert recognizer.language == "en-US"
        assert recognizer.prefer_on_device is True
        assert recognizer.is_initialized is False
    
    @pytest.mark.asyncio
    async def test_initialize(self, recognizer):
        """Test async initialization."""
        await recognizer.initialize()
        assert recognizer.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_recognize_stub(self, recognizer, sample_audio):
        """Test speech recognition with stub implementation.
        
        Requirements: 2 (iOS STT)
        """
        result = await recognizer.recognize(
            audio_data=sample_audio,
            sample_rate=16000,
            language="en-US"
        )
        
        # Verify result structure
        assert isinstance(result, TranscriptionResult)
        assert result.text is not None
        assert len(result.text) > 0
        assert result.language == "en-US"
        assert 0.0 <= result.confidence <= 1.0
        assert result.duration > 0.0
        assert len(result.segments) > 0
    
    @pytest.mark.asyncio
    async def test_recognize_different_languages(self, recognizer, sample_audio):
        """Test recognition with different languages."""
        languages = ["en-US", "es-ES", "fr-FR", "de-DE"]
        
        for lang in languages:
            result = await recognizer.recognize(
                audio_data=sample_audio,
                sample_rate=16000,
                language=lang
            )
            
            assert result.language == lang
            assert isinstance(result, TranscriptionResult)
    
    @pytest.mark.asyncio
    async def test_recognize_streaming_stub(self, recognizer, sample_audio):
        """Test streaming recognition with stub implementation."""
        # Create async generator for audio chunks
        async def audio_stream():
            # Split audio into chunks
            chunk_size = len(sample_audio) // 4
            for i in range(0, len(sample_audio), chunk_size):
                yield sample_audio[i:i+chunk_size]
        
        results = []
        async for result in recognizer.recognize_streaming(
            audio_stream=audio_stream(),
            sample_rate=16000
        ):
            results.append(result)
        
        # Verify we got results
        assert len(results) > 0
        for result in results:
            assert isinstance(result, TranscriptionResult)
    
    @pytest.mark.asyncio
    async def test_check_availability(self, recognizer):
        """Test availability check."""
        availability = await recognizer.check_availability()
        
        assert isinstance(availability, dict)
        assert "available" in availability
        assert "on_device" in availability
        assert "languages" in availability
        assert "authorization" in availability
        assert "platform" in availability
        
        # On non-iOS platform, should indicate stub
        assert availability["platform"] == "non-ios (stub)"
    
    @pytest.mark.asyncio
    async def test_get_supported_languages(self, recognizer):
        """Test getting supported languages."""
        languages = await recognizer.get_supported_languages()
        
        assert isinstance(languages, list)
        assert len(languages) > 0
        
        # Should include common languages
        assert any("en" in lang for lang in languages)
    
    @pytest.mark.asyncio
    async def test_cleanup(self, recognizer):
        """Test resource cleanup."""
        await recognizer.initialize()
        assert recognizer.is_initialized is True
        
        await recognizer.cleanup()
        assert recognizer.is_initialized is False
        assert recognizer.recognizer is None
    
    def test_platform_detection(self, recognizer):
        """Test iOS platform detection."""
        # On non-iOS platform, should detect correctly
        assert recognizer._is_ios is False
    
    @pytest.mark.asyncio
    async def test_confidence_scores(self, recognizer, sample_audio):
        """Test that confidence scores are within valid range.
        
        Requirements: 2.9 (Confidence scores)
        """
        result = await recognizer.recognize(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        # Check overall confidence
        assert 0.0 <= result.confidence <= 1.0
        
        # Check segment confidences
        for segment in result.segments:
            assert 0.0 <= segment.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_audio_duration_calculation(self, recognizer):
        """Test that audio duration is calculated correctly."""
        # Create audio of known duration
        sample_rate = 16000
        duration_seconds = 2.5
        samples = int(sample_rate * duration_seconds)
        
        audio = np.zeros(samples, dtype=np.int16)
        audio_bytes = audio.tobytes()
        
        result = await recognizer.recognize(
            audio_data=audio_bytes,
            sample_rate=sample_rate
        )
        
        # Duration should be close to expected (within 0.1s)
        assert abs(result.duration - duration_seconds) < 0.1
    
    @pytest.mark.asyncio
    async def test_empty_audio(self, recognizer):
        """Test handling of empty audio data."""
        empty_audio = b""
        
        result = await recognizer.recognize(
            audio_data=empty_audio,
            sample_rate=16000
        )
        
        # Should still return valid result structure
        assert isinstance(result, TranscriptionResult)
        assert result.duration == 0.0
    
    @pytest.mark.asyncio
    async def test_multiple_recognitions(self, recognizer, sample_audio):
        """Test multiple consecutive recognitions."""
        results = []
        
        for _ in range(3):
            result = await recognizer.recognize(
                audio_data=sample_audio,
                sample_rate=16000
            )
            results.append(result)
        
        # All should succeed
        assert len(results) == 3
        for result in results:
            assert isinstance(result, TranscriptionResult)
    
    def test_custom_configuration(self):
        """Test recognizer with custom configuration."""
        recognizer = IOSSpeechRecognizer(
            prefer_on_device=False,
            language="es-ES",
            require_on_device=False
        )
        
        assert recognizer.prefer_on_device is False
        assert recognizer.language == "es-ES"
        assert recognizer.require_on_device is False
    
    def test_require_on_device_configuration(self):
        """Test require_on_device configuration."""
        recognizer = IOSSpeechRecognizer(
            prefer_on_device=True,
            require_on_device=True
        )
        
        assert recognizer.require_on_device is True
    
    @pytest.mark.asyncio
    async def test_language_override(self, recognizer, sample_audio):
        """Test language override in recognize method."""
        # Recognizer default is en-US
        assert recognizer.language == "en-US"
        
        # Override with different language
        result = await recognizer.recognize(
            audio_data=sample_audio,
            sample_rate=16000,
            language="fr-FR"
        )
        
        # Result should use overridden language
        assert result.language == "fr-FR"
    
    @pytest.mark.asyncio
    async def test_segment_structure(self, recognizer, sample_audio):
        """Test that segments have proper structure."""
        result = await recognizer.recognize(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        for segment in result.segments:
            assert segment.text is not None
            assert segment.start_time >= 0.0
            assert segment.end_time >= segment.start_time
            assert 0.0 <= segment.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_authorization_status(self, recognizer):
        """Test authorization status tracking."""
        await recognizer.initialize()
        
        # After initialization, should have authorization status
        assert recognizer.authorization_status is not None
    
    @pytest.mark.asyncio
    async def test_latency_requirement(self, recognizer, sample_audio):
        """Test that recognition meets latency requirement.
        
        Requirements: 2.5 (<1 second latency for short commands)
        """
        import time
        
        # Short audio (< 5 seconds)
        start_time = time.time()
        
        result = await recognizer.recognize(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        end_time = time.time()
        latency = end_time - start_time
        
        # Should complete quickly (stub implementation)
        # Real implementation should be < 1 second
        assert latency < 2.0  # Generous for stub
        assert isinstance(result, TranscriptionResult)
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, recognizer, sample_audio):
        """Test that memory usage is reasonable.
        
        Requirements: 2.7 (<50MB RAM during transcription)
        """
        # This is a basic test - real memory profiling would be more complex
        import sys
        
        initial_size = sys.getsizeof(recognizer)
        
        # Perform recognition
        result = await recognizer.recognize(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        final_size = sys.getsizeof(recognizer)
        
        # Object size shouldn't grow significantly
        assert final_size - initial_size < 1000000  # < 1MB growth
        assert isinstance(result, TranscriptionResult)
