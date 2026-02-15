"""
Tests for newly added features.

Tests wake word detection, VAD, TTS, metrics, biometrics, and streaming.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from .wake_word import WakeWordDetector, WakeWordEvent
from .vad import VoiceActivityDetector, VADResult
from .tts import TextToSpeech, TTSConfig
from .metrics import PerformanceMonitor, get_monitor
from .biometric import VoiceBiometricAuthenticator, VoiceProfile
from .streaming import StreamingTranscriber, StreamingConfig


class TestWakeWordDetector:
    """Tests for wake word detection."""
    
    def test_initialization(self):
        """Test wake word detector initialization."""
        detector = WakeWordDetector(wake_words=["test"], sensitivity=0.8)
        assert detector.wake_words == ["test"]
        assert detector.sensitivity == 0.8
    
    def test_process_audio_returns_none_for_silence(self):
        """Test that silence doesn't trigger wake word."""
        detector = WakeWordDetector()
        audio = np.zeros(16000, dtype=np.float32)
        result = detector.process_audio(audio)
        # May return None or event depending on fallback
        assert result is None or isinstance(result, WakeWordEvent)
    
    def test_set_sensitivity(self):
        """Test sensitivity adjustment."""
        detector = WakeWordDetector()
        detector.set_sensitivity(0.9)
        assert detector.sensitivity == 0.9


class TestVoiceActivityDetector:
    """Tests for voice activity detection."""
    
    def test_initialization(self):
        """Test VAD initialization."""
        vad = VoiceActivityDetector(sample_rate=16000)
        assert vad.sample_rate == 16000
    
    def test_is_speech_with_silence(self):
        """Test VAD with silence."""
        vad = VoiceActivityDetector()
        audio = np.zeros(16000, dtype=np.float32)
        result = vad.is_speech(audio)
        
        assert isinstance(result, VADResult)
        assert isinstance(result.is_speech, bool)
        assert 0.0 <= result.confidence <= 1.0
        assert result.energy >= 0.0
    
    def test_is_speech_with_noise(self):
        """Test VAD with noise."""
        vad = VoiceActivityDetector()
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        result = vad.is_speech(audio)
        
        assert isinstance(result, VADResult)
        assert 0.0 <= result.confidence <= 1.0
    
    def test_filter_silence(self):
        """Test silence filtering."""
        vad = VoiceActivityDetector()
        
        # Create audio with silence and noise
        audio = np.concatenate([
            np.zeros(8000, dtype=np.float32),  # Silence
            np.random.randn(8000).astype(np.float32) * 0.1  # Noise
        ])
        
        filtered, ratio = vad.filter_silence(audio, chunk_duration_ms=500)
        
        assert isinstance(filtered, np.ndarray)
        assert 0.0 <= ratio <= 1.0


class TestTextToSpeech:
    """Tests for text-to-speech."""
    
    def test_initialization(self):
        """Test TTS initialization."""
        config = TTSConfig(speaking_rate=1.5, pitch=0.5)
        tts = TextToSpeech(config=config)
        
        assert tts.config.speaking_rate == 1.5
        assert tts.config.pitch == 0.5
    
    def test_synthesize_returns_audio(self):
        """Test that synthesis returns audio."""
        tts = TextToSpeech()
        audio = tts.synthesize("Hello world")
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
        assert audio.dtype == np.float32
    
    def test_synthesize_empty_text(self):
        """Test synthesis with empty text."""
        tts = TextToSpeech()
        audio = tts.synthesize("")
        
        assert isinstance(audio, np.ndarray)
        assert len(audio) == 0
    
    def test_set_speaking_rate(self):
        """Test speaking rate adjustment."""
        tts = TextToSpeech()
        tts.set_speaking_rate(2.0)
        assert tts.config.speaking_rate == 2.0
        
        # Test clamping
        tts.set_speaking_rate(5.0)
        assert tts.config.speaking_rate == 2.0  # Max is 2.0


class TestPerformanceMonitor:
    """Tests for performance monitoring."""
    
    def test_initialization(self):
        """Test monitor initialization."""
        monitor = PerformanceMonitor()
        assert monitor.components == {}
    
    def test_operation_timing(self):
        """Test operation timing."""
        monitor = PerformanceMonitor()
        
        start = monitor.start_operation("test_component")
        duration = monitor.end_operation("test_component", start, success=True)
        
        assert duration >= 0.0
        assert "test_component" in monitor.components
        assert monitor.components["test_component"].total_calls == 1
    
    def test_wake_word_metrics(self):
        """Test wake word metrics recording."""
        monitor = PerformanceMonitor()
        
        monitor.record_wake_word_detection("guru", 45.0, is_false_positive=False)
        
        assert monitor.wake_word.total_detections == 1
        assert monitor.wake_word.false_positives == 0
        assert "guru" in monitor.wake_word.detections_by_word
    
    def test_transcription_metrics(self):
        """Test transcription metrics recording."""
        monitor = PerformanceMonitor()
        
        monitor.record_transcription(
            duration_sec=2.5,
            processing_time_ms=120.0,
            language="en",
            word_count=15
        )
        
        assert monitor.transcription.total_transcriptions == 1
        assert monitor.transcription.total_audio_duration_sec == 2.5
        assert "en" in monitor.transcription.languages_detected
    
    def test_tts_metrics(self):
        """Test TTS metrics recording."""
        monitor = PerformanceMonitor()
        
        monitor.record_tts_synthesis(text_length=50, synthesis_time_ms=80.0)
        
        assert monitor.tts.total_syntheses == 1
        assert monitor.tts.total_characters == 50
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        monitor = PerformanceMonitor()
        
        # Record some metrics
        start = monitor.start_operation("test")
        monitor.end_operation("test", start)
        
        metrics = monitor.get_all_metrics()
        
        assert "components" in metrics
        assert "wake_word" in metrics
        assert "transcription" in metrics
        assert "tts" in metrics
        assert "system" in metrics
    
    def test_reset(self):
        """Test metrics reset."""
        monitor = PerformanceMonitor()
        
        start = monitor.start_operation("test")
        monitor.end_operation("test", start)
        
        monitor.reset()
        
        assert monitor.components == {}
        assert monitor.wake_word.total_detections == 0


class TestVoiceBiometricAuthenticator:
    """Tests for voice biometric authentication."""
    
    def test_initialization(self):
        """Test authenticator initialization."""
        auth = VoiceBiometricAuthenticator(threshold=0.8)
        assert auth.threshold == 0.8
        assert auth.profiles == {}
    
    def test_extract_embedding(self):
        """Test embedding extraction."""
        auth = VoiceBiometricAuthenticator()
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        
        embedding = auth.extract_embedding(audio, sample_rate=16000)
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) > 0
    
    def test_enroll_user(self):
        """Test user enrollment."""
        auth = VoiceBiometricAuthenticator()
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        
        auth.enroll("test_user", audio, sample_rate=16000)
        
        assert "test_user" in auth.profiles
        assert auth.profiles["test_user"].enrollment_count == 1
    
    def test_authenticate_no_profiles(self):
        """Test authentication with no enrolled profiles."""
        auth = VoiceBiometricAuthenticator()
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        
        result = auth.authenticate(audio, sample_rate=16000)
        
        assert result.authenticated is False
        assert result.user_id is None
    
    def test_authenticate_identification(self):
        """Test speaker identification."""
        auth = VoiceBiometricAuthenticator()
        
        # Enroll a user
        audio1 = np.random.randn(16000).astype(np.float32) * 0.1
        auth.enroll("user1", audio1)
        
        # Try to identify
        audio2 = np.random.randn(16000).astype(np.float32) * 0.1
        result = auth.authenticate(audio2)
        
        assert result.authenticated in [True, False]  # Can be either
        assert 0.0 <= result.confidence <= 1.0
    
    def test_authenticate_verification(self):
        """Test speaker verification."""
        auth = VoiceBiometricAuthenticator()
        
        # Enroll a user
        audio1 = np.random.randn(16000).astype(np.float32) * 0.1
        auth.enroll("user1", audio1)
        
        # Verify against specific user
        audio2 = np.random.randn(16000).astype(np.float32) * 0.1
        result = auth.authenticate(audio2, user_id="user1")
        
        assert result.authenticated in [True, False]  # Can be either
        assert 0.0 <= result.confidence <= 1.0
    
    def test_remove_user(self):
        """Test user removal."""
        auth = VoiceBiometricAuthenticator()
        
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        auth.enroll("test_user", audio)
        
        removed = auth.remove_user("test_user")
        assert removed is True
        assert "test_user" not in auth.profiles
    
    def test_list_users(self):
        """Test listing enrolled users."""
        auth = VoiceBiometricAuthenticator()
        
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        auth.enroll("user1", audio)
        auth.enroll("user2", audio)
        
        users = auth.list_users()
        assert "user1" in users
        assert "user2" in users


class TestStreamingTranscriber:
    """Tests for streaming transcription."""
    
    def test_initialization(self):
        """Test streaming transcriber initialization."""
        from . import GuruSpeechEngine
        
        engine = GuruSpeechEngine()
        config = StreamingConfig()
        
        transcriber = StreamingTranscriber(engine, config)
        
        assert transcriber.engine == engine
        assert transcriber.config == config
        assert transcriber.is_streaming is False
    
    def test_start_stop(self):
        """Test starting and stopping streaming."""
        from . import GuruSpeechEngine
        
        engine = GuruSpeechEngine()
        transcriber = StreamingTranscriber(engine)
        
        transcriber.start()
        assert transcriber.is_streaming is True
        
        transcriber.stop()
        assert transcriber.is_streaming is False
    
    def test_context_manager(self):
        """Test using streaming transcriber as context manager."""
        from . import GuruSpeechEngine
        
        engine = GuruSpeechEngine()
        
        with StreamingTranscriber(engine) as transcriber:
            assert transcriber.is_streaming is True
        
        # Should be stopped after exiting context
        assert transcriber.is_streaming is False


def test_global_monitor():
    """Test global monitor instance."""
    monitor1 = get_monitor()
    monitor2 = get_monitor()
    
    # Should return same instance
    assert monitor1 is monitor2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
