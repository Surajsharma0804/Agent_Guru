"""
Unit tests for WhisperSTTEngine

Tests cover:
- Model loading and integrity verification
- Audio transcription with various inputs
- Security validation and injection detection
- Error handling and edge cases
- Performance and resource management
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.voice.speech_to_text import (
    WhisperSTTEngine, 
    ModelSize, 
    STTResult, 
    ModelInfo
)


class TestWhisperSTTEngine:
    """Test suite for WhisperSTTEngine"""
    
    @pytest.fixture
    def temp_models_dir(self):
        """Create temporary directory for test models"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_audio(self):
        """Generate sample audio data for testing"""
        # Generate 1 second of 16kHz sine wave
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0  # A4 note
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        return audio.astype(np.float32)
    
    def test_initialization_default_config(self, temp_models_dir):
        """Test STT engine initialization with default configuration"""
        engine = WhisperSTTEngine(models_dir=temp_models_dir)
        
        assert engine.model_size == ModelSize.BASE
        assert engine.models_dir == temp_models_dir
        assert engine.confidence_threshold == 0.7
        assert engine.max_audio_duration_seconds == 30
        assert engine.enable_security_checks is True
        assert engine._model is None
        assert engine._model_info is None
    
    def test_models_directory_creation(self, temp_models_dir):
        """Test that models directory is created with proper permissions"""
        models_subdir = temp_models_dir / "whisper_models"
        engine = WhisperSTTEngine(models_dir=models_subdir)
        
        assert models_subdir.exists()
        assert models_subdir.is_dir()
    
    def test_get_model_path(self, temp_models_dir):
        """Test model path generation for different sizes"""
        engine = WhisperSTTEngine(models_dir=temp_models_dir)
        
        tiny_path = engine._get_model_path(ModelSize.TINY)
        base_path = engine._get_model_path(ModelSize.BASE)
        large_path = engine._get_model_path(ModelSize.LARGE)
        
        assert tiny_path == temp_models_dir / "ggml-tiny.bin"
        assert base_path == temp_models_dir / "ggml-base.bin"
        assert large_path == temp_models_dir / "ggml-large.bin"
    
    def test_verify_model_integrity_missing_file(self, temp_models_dir):
        """Test model integrity verification with missing file"""
        engine = WhisperSTTEngine(models_dir=temp_models_dir)
        
        missing_file = temp_models_dir / "missing.bin"
        result = engine._verify_model_integrity(missing_file)
        
        assert result is False
    
    def test_verify_model_integrity_valid_file(self, temp_models_dir):
        """Test model integrity verification with valid file"""
        engine = WhisperSTTEngine(models_dir=temp_models_dir)
        
        # Create file larger than 1MB
        valid_file = temp_models_dir / "valid.bin"
        valid_content = b"x" * (2 * 1024 * 1024)  # 2MB
        valid_file.write_bytes(valid_content)
        
        result = engine._verify_model_integrity(valid_file)
        
        assert result is True
    
    def test_validate_audio_input_security_disabled(self, temp_models_dir, sample_audio):
        """Test audio validation with security checks disabled"""
        engine = WhisperSTTEngine(models_dir=temp_models_dir, enable_security_checks=False)
        
        flags = engine._validate_audio_input(sample_audio)
        
        assert flags == []
    
    def test_validate_audio_input_silent(self, temp_models_dir):
        """Test audio validation with silent audio"""
        engine = WhisperSTTEngine(models_dir=temp_models_dir)
        
        # Create silent audio
        silent_audio = np.zeros(16000, dtype=np.float32)
        
        flags = engine._validate_audio_input(silent_audio)
        
        assert "silent_audio" in flags
    
    def test_get_processing_stats(self, temp_models_dir):
        """Test getting processing statistics"""
        engine = WhisperSTTEngine(models_dir=temp_models_dir)
        
        # Initial stats
        stats = engine.get_processing_stats()
        assert stats['total_requests'] == 0
        assert stats['successful_requests'] == 0
        assert stats['failed_requests'] == 0