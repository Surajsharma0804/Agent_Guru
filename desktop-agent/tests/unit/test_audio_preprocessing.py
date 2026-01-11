"""
Unit tests for AudioPreprocessor

Tests cover:
- Audio format conversion and normalization
- Noise reduction and filtering
- Security validation and quality metrics
- Error handling and edge cases
- Performance and resource management
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from scipy.io import wavfile

from src.voice.audio_preprocessing import (
    AudioPreprocessor,
    PreprocessingConfig,
    AudioMetrics,
    AudioFormat,
    NoiseReductionLevel
)


class TestAudioPreprocessor:
    """Test suite for AudioPreprocessor"""
    
    @pytest.fixture
    def default_config(self):
        """Default preprocessing configuration"""
        return PreprocessingConfig()
    
    @pytest.fixture
    def custom_config(self):
        """Custom preprocessing configuration"""
        return PreprocessingConfig(
            target_sample_rate=22050,
            target_channels=2,
            normalize_audio=False,
            noise_reduction=NoiseReductionLevel.AGGRESSIVE,
            high_pass_cutoff=100.0,
            low_pass_cutoff=10000.0,
            max_duration_seconds=60.0,
            enable_security_checks=False
        )
    
    @pytest.fixture
    def sample_audio_16k(self):
        """Generate sample audio at 16kHz"""
        sample_rate = 16000
        duration = 2.0
        frequency = 440.0  # A4 note
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        return audio.astype(np.float32), sample_rate
    
    @pytest.fixture
    def sample_audio_44k(self):
        """Generate sample audio at 44.1kHz"""
        sample_rate = 44100
        duration = 1.0
        frequency = 880.0  # A5 note
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.5 * np.sin(2 * np.pi * frequency * t)
        
        return audio.astype(np.float32), sample_rate
    
    @pytest.fixture
    def stereo_audio(self):
        """Generate stereo audio"""
        sample_rate = 16000
        duration = 1.0
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        left = 0.3 * np.sin(2 * np.pi * 440 * t)
        right = 0.3 * np.sin(2 * np.pi * 880 * t)
        
        stereo = np.column_stack((left, right))
        return stereo.astype(np.float32), sample_rate
    
    @pytest.fixture
    def temp_audio_file(self, sample_audio_16k):
        """Create temporary audio file"""
        audio, sample_rate = sample_audio_16k
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            # Convert to int16 for WAV file
            audio_int16 = (audio * 32767).astype(np.int16)
            wavfile.write(f.name, sample_rate, audio_int16)
            yield f.name
        
        # Cleanup
        os.unlink(f.name)
    
    def test_initialization_default_config(self):
        """Test preprocessor initialization with default configuration"""
        preprocessor = AudioPreprocessor()
        
        assert preprocessor.config.target_sample_rate == 16000
        assert preprocessor.config.target_channels == 1
        assert preprocessor.config.normalize_audio is True
        assert preprocessor.config.noise_reduction == NoiseReductionLevel.MODERATE
        assert preprocessor.config.enable_security_checks is True
    
    def test_initialization_custom_config(self, custom_config):
        """Test preprocessor initialization with custom configuration"""
        preprocessor = AudioPreprocessor(custom_config)
        
        assert preprocessor.config.target_sample_rate == 22050
        assert preprocessor.config.target_channels == 2
        assert preprocessor.config.normalize_audio is False
        assert preprocessor.config.noise_reduction == NoiseReductionLevel.AGGRESSIVE
        assert preprocessor.config.enable_security_checks is False
    
    def test_filter_initialization(self):
        """Test that audio filters are initialized correctly"""
        preprocessor = AudioPreprocessor()
        
        # Check that filters were created
        assert hasattr(preprocessor, '_high_pass_filter')
        assert hasattr(preprocessor, '_low_pass_filter')
        assert preprocessor._high_pass_filter is not None
        assert preprocessor._low_pass_filter is not None
    
    def test_convert_sample_rate_no_change(self, sample_audio_16k):
        """Test sample rate conversion when no change needed"""
        audio, sample_rate = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._convert_sample_rate(audio, sample_rate)
        
        # Should return same audio
        np.testing.assert_array_equal(result, audio)
    
    def test_convert_sample_rate_downsample(self, sample_audio_44k):
        """Test downsampling from 44.1kHz to 16kHz"""
        audio, sample_rate = sample_audio_44k
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._convert_sample_rate(audio, sample_rate)
        
        # Should be resampled to 16kHz
        expected_length = int(len(audio) * 16000 / sample_rate)
        assert len(result) == expected_length
        assert result.dtype == np.float32
    
    def test_convert_sample_rate_upsample(self):
        """Test upsampling from 8kHz to 16kHz"""
        # Generate 8kHz audio
        sample_rate = 8000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        audio = audio.astype(np.float32)
        
        preprocessor = AudioPreprocessor()
        result = preprocessor._convert_sample_rate(audio, sample_rate)
        
        # Should be upsampled to 16kHz
        expected_length = int(len(audio) * 16000 / sample_rate)
        assert len(result) == expected_length
        assert result.dtype == np.float32
    
    def test_convert_to_mono_already_mono(self, sample_audio_16k):
        """Test mono conversion with already mono audio"""
        audio, _ = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._convert_to_mono(audio)
        
        # Should return same audio
        np.testing.assert_array_equal(result, audio)
    
    def test_convert_to_mono_from_stereo(self, stereo_audio):
        """Test mono conversion from stereo audio"""
        audio, _ = stereo_audio
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._convert_to_mono(audio)
        
        # Should be mono (1D array)
        assert len(result.shape) == 1
        assert len(result) == len(audio)
        assert result.dtype == np.float32
        
        # Should be average of channels
        expected = np.mean(audio, axis=1)
        np.testing.assert_array_almost_equal(result, expected)
    
    def test_convert_to_mono_invalid_shape(self):
        """Test mono conversion with invalid audio shape"""
        # Create 3D audio (invalid)
        audio = np.zeros((1000, 2, 3), dtype=np.float32)
        preprocessor = AudioPreprocessor()
        
        with pytest.raises(ValueError, match="Unsupported audio shape"):
            preprocessor._convert_to_mono(audio)
    
    def test_normalize_audio_disabled(self, sample_audio_16k):
        """Test audio normalization when disabled"""
        audio, _ = sample_audio_16k
        config = PreprocessingConfig(normalize_audio=False)
        preprocessor = AudioPreprocessor(config)
        
        result = preprocessor._normalize_audio(audio)
        
        # Should return same audio
        np.testing.assert_array_equal(result, audio)
    
    def test_normalize_audio_enabled(self, sample_audio_16k):
        """Test audio normalization when enabled"""
        audio, _ = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._normalize_audio(audio)
        
        # Should be normalized
        assert result.dtype == np.float32
        assert np.max(np.abs(result)) <= 0.95  # Should not clip
        
        # RMS should be closer to target
        rms = np.sqrt(np.mean(result ** 2))
        assert 0.1 <= rms <= 0.3  # Reasonable range
    
    def test_normalize_audio_silent(self):
        """Test audio normalization with silent audio"""
        audio = np.zeros(16000, dtype=np.float32)
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._normalize_audio(audio)
        
        # Should remain silent
        np.testing.assert_array_equal(result, audio)
    
    def test_normalize_audio_clipping_prevention(self):
        """Test that normalization prevents clipping"""
        # Create loud audio that would clip
        audio = np.ones(16000, dtype=np.float32) * 0.8
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._normalize_audio(audio)
        
        # Should not clip
        assert np.max(np.abs(result)) <= 0.95
    
    def test_apply_noise_reduction_none(self, sample_audio_16k):
        """Test noise reduction when disabled"""
        audio, _ = sample_audio_16k
        config = PreprocessingConfig(noise_reduction=NoiseReductionLevel.NONE)
        preprocessor = AudioPreprocessor(config)
        
        result = preprocessor._apply_noise_reduction(audio)
        
        # Should return same audio
        np.testing.assert_array_equal(result, audio)
    
    def test_apply_noise_reduction_light(self, sample_audio_16k):
        """Test light noise reduction"""
        audio, _ = sample_audio_16k
        config = PreprocessingConfig(noise_reduction=NoiseReductionLevel.LIGHT)
        preprocessor = AudioPreprocessor(config)
        
        result = preprocessor._apply_noise_reduction(audio)
        
        # Should be filtered but similar
        assert result.dtype == np.float32
        assert len(result) == len(audio)
        # Should be somewhat similar (correlation > 0.8)
        correlation = np.corrcoef(audio, result)[0, 1]
        assert correlation > 0.8
    
    def test_apply_noise_reduction_moderate(self, sample_audio_16k):
        """Test moderate noise reduction"""
        audio, _ = sample_audio_16k
        config = PreprocessingConfig(noise_reduction=NoiseReductionLevel.MODERATE)
        preprocessor = AudioPreprocessor(config)
        
        result = preprocessor._apply_noise_reduction(audio)
        
        # Should be filtered
        assert result.dtype == np.float32
        assert len(result) == len(audio)
        # Should still be recognizable
        correlation = np.corrcoef(audio, result)[0, 1]
        assert correlation > 0.7
    
    def test_apply_noise_reduction_aggressive(self, sample_audio_16k):
        """Test aggressive noise reduction"""
        audio, _ = sample_audio_16k
        config = PreprocessingConfig(noise_reduction=NoiseReductionLevel.AGGRESSIVE)
        preprocessor = AudioPreprocessor(config)
        
        result = preprocessor._apply_noise_reduction(audio)
        
        # Should be heavily filtered
        assert result.dtype == np.float32
        assert len(result) == len(audio)
        # May be significantly changed but should not be silent
        assert np.max(np.abs(result)) > 0.01
    
    def test_spectral_subtraction_short_audio(self):
        """Test spectral subtraction with very short audio"""
        audio = np.random.randn(50).astype(np.float32)  # Very short
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._spectral_subtraction(audio)
        
        # Should return original audio (too short for processing)
        np.testing.assert_array_equal(result, audio)
    
    def test_spectral_subtraction_normal_audio(self, sample_audio_16k):
        """Test spectral subtraction with normal audio"""
        audio, _ = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        result = preprocessor._spectral_subtraction(audio)
        
        # Should be processed
        assert result.dtype == np.float32
        assert len(result) == len(audio)
        # Should not be completely silent
        assert np.max(np.abs(result)) > 0.001
    
    def test_calculate_audio_metrics_normal_audio(self, sample_audio_16k):
        """Test audio metrics calculation with normal audio"""
        audio, sample_rate = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        metrics = preprocessor._calculate_audio_metrics(audio, sample_rate)
        
        assert isinstance(metrics, AudioMetrics)
        assert metrics.sample_rate == sample_rate
        assert metrics.duration_seconds == pytest.approx(2.0, rel=0.1)
        assert metrics.channels == 1
        assert metrics.bit_depth == 32
        assert metrics.rms_level > 0
        assert metrics.peak_level > 0
        assert metrics.snr_estimate > 0
        assert not metrics.clipping_detected
        assert metrics.silence_ratio < 0.5
        assert metrics.frequency_range_hz[0] >= 0
        assert metrics.frequency_range_hz[1] <= sample_rate / 2
    
    def test_calculate_audio_metrics_silent_audio(self):
        """Test audio metrics calculation with silent audio"""
        audio = np.zeros(16000, dtype=np.float32)
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        metrics = preprocessor._calculate_audio_metrics(audio, sample_rate)
        
        assert metrics.rms_level == 0.0
        assert metrics.peak_level == 0.0
        assert metrics.silence_ratio == 1.0
        assert "no_signal" in metrics.security_flags
    
    def test_calculate_audio_metrics_clipped_audio(self):
        """Test audio metrics calculation with clipped audio"""
        audio = np.ones(16000, dtype=np.float32)  # All samples at maximum
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        metrics = preprocessor._calculate_audio_metrics(audio, sample_rate)
        
        assert metrics.clipping_detected == True
        assert metrics.peak_level >= 0.99
        assert "clipping_detected" in metrics.security_flags
    
    def test_calculate_audio_metrics_too_long(self):
        """Test audio metrics calculation with audio that's too long"""
        # Create 60 seconds of audio (longer than default 30s limit)
        audio = np.random.randn(16000 * 60).astype(np.float32) * 0.1
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        metrics = preprocessor._calculate_audio_metrics(audio, sample_rate)
        
        assert any("duration_exceeded" in flag for flag in metrics.security_flags)
    
    def test_calculate_audio_metrics_security_disabled(self, sample_audio_16k):
        """Test audio metrics calculation with security checks disabled"""
        audio, sample_rate = sample_audio_16k
        config = PreprocessingConfig(enable_security_checks=False)
        preprocessor = AudioPreprocessor(config)
        
        metrics = preprocessor._calculate_audio_metrics(audio, sample_rate)
        
        # Should have no security flags
        assert len(metrics.security_flags) == 0
    
    def test_process_audio_success(self, sample_audio_16k):
        """Test successful audio processing"""
        audio, sample_rate = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio(audio, sample_rate)
        
        assert result_audio is not None
        assert isinstance(metrics, AudioMetrics)
        assert result_audio.dtype == np.float32
        assert len(result_audio) > 0
        assert metrics.is_good_quality
    
    def test_process_audio_security_rejection(self):
        """Test audio processing rejection due to security flags"""
        # Create audio that's too long
        audio = np.random.randn(16000 * 60).astype(np.float32) * 0.1  # 60 seconds
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio(audio, sample_rate, validate_security=True)
        
        assert result_audio is None
        assert len(metrics.security_flags) > 0
    
    def test_process_audio_quality_rejection(self):
        """Test audio processing rejection due to poor quality"""
        # Create very noisy, low-quality audio
        audio = np.random.randn(16000).astype(np.float32) * 0.001  # Very quiet noise
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio(audio, sample_rate)
        
        # May be rejected due to poor quality
        if result_audio is None:
            assert not metrics.is_good_quality
    
    def test_process_audio_skip_security_validation(self):
        """Test audio processing with security validation disabled"""
        # Create audio that would normally be rejected
        audio = np.random.randn(16000 * 60).astype(np.float32) * 0.1  # 60 seconds
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio(audio, sample_rate, validate_security=False)
        
        # Should not be rejected for security reasons
        # (may still be rejected for quality)
        if result_audio is None:
            # If rejected, should be for quality, not security
            assert not any("duration_exceeded" in flag for flag in metrics.security_flags)
    
    def test_process_audio_int16_conversion(self):
        """Test processing audio with int16 input"""
        # Create int16 audio
        audio_int16 = np.random.randint(-32768, 32767, 16000, dtype=np.int16)
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio(audio_int16, sample_rate)
        
        if result_audio is not None:
            assert result_audio.dtype == np.float32
            assert np.max(np.abs(result_audio)) <= 1.0
    
    def test_process_audio_int32_conversion(self):
        """Test processing audio with int32 input"""
        # Create int32 audio
        audio_int32 = np.random.randint(-2147483648, 2147483647, 16000, dtype=np.int32)
        sample_rate = 16000
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio(audio_int32, sample_rate)
        
        if result_audio is not None:
            assert result_audio.dtype == np.float32
            assert np.max(np.abs(result_audio)) <= 1.0
    
    def test_process_audio_file_success(self, temp_audio_file):
        """Test processing audio from file"""
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio_file(temp_audio_file)
        
        if result_audio is not None:
            assert result_audio.dtype == np.float32
            assert len(result_audio) > 0
            assert isinstance(metrics, AudioMetrics)
    
    def test_process_audio_file_missing(self):
        """Test processing audio from missing file"""
        preprocessor = AudioPreprocessor()
        
        result_audio, metrics = preprocessor.process_audio_file("nonexistent.wav")
        
        assert result_audio is None
        assert "file_read_failed" in metrics.security_flags
    
    def test_get_processing_stats(self, sample_audio_16k):
        """Test getting processing statistics"""
        audio, sample_rate = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        # Initial stats
        stats = preprocessor.get_processing_stats()
        assert stats['total_processed'] == 0
        assert stats['successful_processed'] == 0
        assert stats['rejected_security'] == 0
        assert stats['rejected_quality'] == 0
        
        # Process some audio
        result_audio, metrics = preprocessor.process_audio(audio, sample_rate)
        
        # Check updated stats
        stats = preprocessor.get_processing_stats()
        assert stats['total_processed'] == 1
        
        if result_audio is not None:
            assert stats['successful_processed'] == 1
        else:
            assert stats['successful_processed'] == 0
    
    def test_reset_stats(self, sample_audio_16k):
        """Test resetting processing statistics"""
        audio, sample_rate = sample_audio_16k
        preprocessor = AudioPreprocessor()
        
        # Process some audio
        preprocessor.process_audio(audio, sample_rate)
        
        # Check stats are non-zero
        stats = preprocessor.get_processing_stats()
        assert stats['total_processed'] > 0
        
        # Reset stats
        preprocessor.reset_stats()
        
        # Check stats are reset
        stats = preprocessor.get_processing_stats()
        assert stats['total_processed'] == 0
        assert stats['successful_processed'] == 0
        assert stats['rejected_security'] == 0
        assert stats['rejected_quality'] == 0
        assert stats['average_snr'] == 0.0
        assert stats['average_processing_time_ms'] == 0.0
    
    def test_thread_safety(self, sample_audio_16k):
        """Test thread safety of audio preprocessor"""
        import threading
        
        audio, sample_rate = sample_audio_16k
        preprocessor = AudioPreprocessor()
        results = []
        errors = []
        
        def worker():
            try:
                result_audio, metrics = preprocessor.process_audio(audio, sample_rate)
                results.append((result_audio, metrics))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0  # No errors should occur
        assert len(results) == 5  # All threads should complete
    
    def test_audio_metrics_is_good_quality(self):
        """Test AudioMetrics.is_good_quality property"""
        # Good quality metrics
        good_metrics = AudioMetrics(
            sample_rate=16000,
            duration_seconds=2.0,
            channels=1,
            bit_depth=32,
            rms_level=0.2,
            peak_level=0.8,
            snr_estimate=15.0,
            clipping_detected=False,
            silence_ratio=0.1,
            frequency_range_hz=(80.0, 8000.0),
            security_flags=[]
        )
        assert good_metrics.is_good_quality is True
        
        # Poor quality metrics (low SNR)
        poor_snr_metrics = AudioMetrics(
            sample_rate=16000,
            duration_seconds=2.0,
            channels=1,
            bit_depth=32,
            rms_level=0.2,
            peak_level=0.8,
            snr_estimate=5.0,  # Low SNR
            clipping_detected=False,
            silence_ratio=0.1,
            frequency_range_hz=(80.0, 8000.0),
            security_flags=[]
        )
        assert poor_snr_metrics.is_good_quality is False
        
        # Poor quality metrics (clipping)
        clipped_metrics = AudioMetrics(
            sample_rate=16000,
            duration_seconds=2.0,
            channels=1,
            bit_depth=32,
            rms_level=0.2,
            peak_level=0.8,
            snr_estimate=15.0,
            clipping_detected=True,  # Clipping detected
            silence_ratio=0.1,
            frequency_range_hz=(80.0, 8000.0),
            security_flags=[]
        )
        assert clipped_metrics.is_good_quality is False
        
        # Poor quality metrics (mostly silent)
        silent_metrics = AudioMetrics(
            sample_rate=16000,
            duration_seconds=2.0,
            channels=1,
            bit_depth=32,
            rms_level=0.2,
            peak_level=0.8,
            snr_estimate=15.0,
            clipping_detected=False,
            silence_ratio=0.9,  # Mostly silent
            frequency_range_hz=(80.0, 8000.0),
            security_flags=[]
        )
        assert silent_metrics.is_good_quality is False
        
        # Poor quality metrics (very low RMS)
        low_rms_metrics = AudioMetrics(
            sample_rate=16000,
            duration_seconds=2.0,
            channels=1,
            bit_depth=32,
            rms_level=0.005,  # Very low RMS
            peak_level=0.8,
            snr_estimate=15.0,
            clipping_detected=False,
            silence_ratio=0.1,
            frequency_range_hz=(80.0, 8000.0),
            security_flags=[]
        )
        assert low_rms_metrics.is_good_quality is False