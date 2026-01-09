"""
Unit tests for VoiceProcessingPipeline

Tests cover:
- Pipeline initialization and state management
- Complete voice processing workflow
- Error handling and recovery
- Security validation and monitoring
- Performance and resource management
- Event system and callbacks
"""

import pytest
import numpy as np
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.voice.voice_pipeline import (
    VoiceProcessingPipeline,
    PipelineConfig,
    VoiceProcessingResult,
    PipelineState
)
from src.voice.speech_to_text import ModelSize, STTResult
from src.voice.audio_preprocessing import PreprocessingConfig, AudioMetrics


class TestVoiceProcessingPipeline:
    """Test suite for VoiceProcessingPipeline"""
    
    @pytest.fixture
    def default_config(self):
        """Default pipeline configuration"""
        return PipelineConfig()
    
    @pytest.fixture
    def sample_audio(self):
        """Generate sample audio data for testing"""
        sample_rate = 16000
        duration = 2.0
        frequency = 440.0
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        return audio.astype(np.float32), sample_rate
    
    @pytest.fixture
    def mock_stt_result(self):
        """Mock STT result"""
        return STTResult(
            text="Hello world",
            confidence=0.9,
            processing_time_ms=100,
            model_used="base",
            audio_duration_ms=2000,
            language_detected="en",
            segments=[{
                'text': 'Hello world',
                'confidence': 0.9,
                'start': 0.0,
                'end': 2.0
            }],
            security_flags=[]
        )
    
    @pytest.fixture
    def mock_audio_metrics(self):
        """Mock audio metrics"""
        return AudioMetrics(
            sample_rate=16000,
            duration_seconds=2.0,
            channels=1,
            bit_depth=32,
            rms_level=0.2,
            peak_level=0.6,
            snr_estimate=15.0,
            clipping_detected=False,
            silence_ratio=0.1,
            frequency_range_hz=(80.0, 8000.0),
            security_flags=[]
        )
    
    @patch('src.voice.voice_pipeline.WhisperSTTEngine')
    @patch('src.voice.voice_pipeline.AudioPreprocessor')
    def test_initialization_default_config(self, mock_preprocessor_class, mock_stt_class):
        """Test pipeline initialization with default configuration"""
        # Mock successful model loading
        mock_stt = Mock()
        mock_stt.load_model.return_value = True
        mock_stt_class.return_value = mock_stt
        
        mock_preprocessor = Mock()
        mock_preprocessor_class.return_value = mock_preprocessor
        
        pipeline = VoiceProcessingPipeline()
        
        assert pipeline.config.whisper_model_size == ModelSize.BASE
        assert pipeline.config.stt_confidence_threshold == 0.7
        assert pipeline.config.enable_security_validation is True
        assert pipeline.get_state() == PipelineState.READY
        
        # Verify components were initialized
        mock_stt_class.assert_called_once()
        mock_preprocessor_class.assert_called_once()
        mock_stt.load_model.assert_called_once()
    
    @patch('src.voice.voice_pipeline.WhisperSTTEngine')
    @patch('src.voice.voice_pipeline.AudioPreprocessor')
    def test_process_voice_command_success(self, mock_preprocessor_class, mock_stt_class, 
                                         sample_audio, mock_stt_result, mock_audio_metrics):
        """Test successful voice command processing"""
        audio, sample_rate = sample_audio
        
        # Mock successful processing
        mock_stt = Mock()
        mock_stt.load_model.return_value = True
        mock_stt.transcribe.return_value = mock_stt_result
        mock_stt_class.return_value = mock_stt
        
        mock_preprocessor = Mock()
        mock_preprocessor.process_audio.return_value = (audio, mock_audio_metrics)
        mock_preprocessor_class.return_value = mock_preprocessor
        
        pipeline = VoiceProcessingPipeline()
        result = pipeline.process_voice_command(audio, sample_rate)
        
        assert result.success is True
        assert result.text == "Hello world"
        assert result.confidence == 0.9
        assert result.speaker_verified is True  # Default when verification disabled
        assert result.processing_time_ms >= 0  # Allow 0 for very fast processing
        assert result.audio_metrics == mock_audio_metrics
        assert result.stt_result == mock_stt_result
        assert len(result.security_flags) == 0
        assert result.error_message is None
        assert result.is_high_quality is True