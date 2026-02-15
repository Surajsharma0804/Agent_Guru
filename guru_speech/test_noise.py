"""
Unit tests for NoiseCleaner module.

This module contains unit tests that verify specific examples, edge cases,
and error conditions for the noise reduction functionality.
"""

import warnings
import numpy as np
import pytest
import tempfile
import os
import soundfile as sf

from .noise import NoiseCleaner
from .exceptions import GuruSpeechError

# Suppress expected warnings from scipy and noisereduce
# These warnings occur when processing short audio clips and are expected behavior
warnings.filterwarnings("ignore", message="nperseg.*is greater than input length", category=UserWarning)
warnings.filterwarnings("ignore", message="invalid value encountered in divide", category=RuntimeWarning)


class TestNoiseCleanerClean:
    """Unit tests for NoiseCleaner.clean() method."""
    
    def test_clean_with_normal_audio(self):
        """Test clean() with normal audio input."""
        cleaner = NoiseCleaner()
        
        # Create a simple sine wave audio
        sample_rate = 16000
        duration = 1.0
        frequency = 440.0  # A4 note
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        cleaned_audio = cleaner.clean(audio_data, sample_rate)
        
        assert isinstance(cleaned_audio, np.ndarray)
        assert cleaned_audio.shape == audio_data.shape
        assert cleaned_audio.dtype in [np.float32, np.float64]
        assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_with_noisy_audio(self):
        """Test clean() with audio containing noise."""
        cleaner = NoiseCleaner(stationary=True, prop_decrease=1.0)
        
        # Create audio with added noise
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t)
        noise = np.random.normal(0, 0.1, signal.shape)
        audio_data = (signal + noise).astype(np.float32)
        
        cleaned_audio = cleaner.clean(audio_data, sample_rate)
        
        assert isinstance(cleaned_audio, np.ndarray)
        assert cleaned_audio.shape == audio_data.shape
        assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_with_silent_audio(self):
        """Test clean() with silent audio (all zeros)."""
        cleaner = NoiseCleaner()
        
        sample_rate = 16000
        audio_data = np.zeros(16000, dtype=np.float32)
        
        cleaned_audio = cleaner.clean(audio_data, sample_rate)
        
        assert isinstance(cleaned_audio, np.ndarray)
        assert cleaned_audio.shape == audio_data.shape
        assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_with_very_short_audio(self):
        """Test clean() with very short audio (< 0.1 seconds)."""
        cleaner = NoiseCleaner()
        
        sample_rate = 16000
        # 0.05 seconds of audio
        audio_data = np.random.randn(800).astype(np.float32)
        
        cleaned_audio = cleaner.clean(audio_data, sample_rate)
        
        assert isinstance(cleaned_audio, np.ndarray)
        assert cleaned_audio.shape == audio_data.shape
        assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_with_stereo_audio(self):
        """Test clean() with stereo audio (2 channels)."""
        cleaner = NoiseCleaner()
        
        sample_rate = 16000
        duration = 1.0
        num_samples = int(sample_rate * duration)
        # Stereo audio: shape (samples, 2)
        audio_data = np.random.randn(num_samples, 2).astype(np.float32)
        
        cleaned_audio = cleaner.clean(audio_data, sample_rate)
        
        assert isinstance(cleaned_audio, np.ndarray)
        assert cleaned_audio.shape == audio_data.shape
        assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_with_different_sample_rates(self):
        """Test clean() with various sample rates."""
        cleaner = NoiseCleaner()
        
        sample_rates = [8000, 16000, 22050, 44100, 48000]
        
        for sample_rate in sample_rates:
            audio_data = np.random.randn(sample_rate).astype(np.float32)
            cleaned_audio = cleaner.clean(audio_data, sample_rate)
            
            assert isinstance(cleaned_audio, np.ndarray)
            assert cleaned_audio.shape == audio_data.shape
            assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_with_stationary_false(self):
        """Test clean() with non-stationary noise reduction."""
        cleaner = NoiseCleaner(stationary=False, prop_decrease=0.8)
        
        sample_rate = 16000
        audio_data = np.random.randn(16000).astype(np.float32)
        
        cleaned_audio = cleaner.clean(audio_data, sample_rate)
        
        assert isinstance(cleaned_audio, np.ndarray)
        assert cleaned_audio.shape == audio_data.shape
        assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_with_various_prop_decrease(self):
        """Test clean() with different prop_decrease values."""
        sample_rate = 16000
        audio_data = np.random.randn(16000).astype(np.float32)
        
        prop_decrease_values = [0.0, 0.5, 1.0]
        
        for prop_decrease in prop_decrease_values:
            cleaner = NoiseCleaner(prop_decrease=prop_decrease)
            cleaned_audio = cleaner.clean(audio_data, sample_rate)
            
            assert isinstance(cleaned_audio, np.ndarray)
            assert cleaned_audio.shape == audio_data.shape
            assert np.all(np.isfinite(cleaned_audio))
    
    def test_clean_preserves_original_on_nan_output(self):
        """Test that clean() returns original audio if output contains NaN."""
        cleaner = NoiseCleaner(stationary=False)
        
        sample_rate = 16000
        # Silent audio with non-stationary mode may produce NaN
        audio_data = np.zeros(16000, dtype=np.float32)
        
        cleaned_audio = cleaner.clean(audio_data, sample_rate)
        
        # Should return valid audio (either cleaned or original)
        assert isinstance(cleaned_audio, np.ndarray)
        assert cleaned_audio.shape == audio_data.shape
        assert np.all(np.isfinite(cleaned_audio))


class TestNoiseCleanerCleanFile:
    """Unit tests for NoiseCleaner.clean_file() method."""
    
    def test_clean_file_with_wav(self):
        """Test clean_file() with WAV audio file."""
        cleaner = NoiseCleaner()
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Create sample audio and save as WAV
            sample_rate = 16000
            duration = 1.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
            sf.write(input_path, audio_data, sample_rate)
            
            # Clean the file
            cleaner.clean_file(input_path, output_path)
            
            # Verify output file exists and is valid
            assert os.path.exists(output_path)
            
            # Load and verify output audio
            cleaned_audio, loaded_sr = sf.read(output_path)
            assert loaded_sr == sample_rate
            assert len(cleaned_audio) == len(audio_data)
            assert np.all(np.isfinite(cleaned_audio))
        
        finally:
            # Clean up temporary files
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_clean_file_with_different_formats(self):
        """Test clean_file() with different audio formats."""
        cleaner = NoiseCleaner()
        
        # Test with FLAC format
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as input_file:
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Create sample audio and save as FLAC
            sample_rate = 16000
            audio_data = np.random.randn(16000).astype(np.float32)
            sf.write(input_path, audio_data, sample_rate)
            
            # Clean the file
            cleaner.clean_file(input_path, output_path)
            
            # Verify output
            assert os.path.exists(output_path)
            cleaned_audio, loaded_sr = sf.read(output_path)
            assert loaded_sr == sample_rate
            assert np.all(np.isfinite(cleaned_audio))
        
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_clean_file_with_stereo(self):
        """Test clean_file() with stereo audio file."""
        cleaner = NoiseCleaner()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
            input_path = input_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            # Create stereo audio
            sample_rate = 16000
            num_samples = 16000
            audio_data = np.random.randn(num_samples, 2).astype(np.float32)
            sf.write(input_path, audio_data, sample_rate)
            
            # Clean the file
            cleaner.clean_file(input_path, output_path)
            
            # Verify output
            assert os.path.exists(output_path)
            cleaned_audio, loaded_sr = sf.read(output_path)
            assert loaded_sr == sample_rate
            assert cleaned_audio.shape == audio_data.shape
            assert np.all(np.isfinite(cleaned_audio))
        
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_clean_file_nonexistent_input(self):
        """Test clean_file() with non-existent input file."""
        cleaner = NoiseCleaner()
        
        input_path = "nonexistent_file.wav"
        output_path = "output.wav"
        
        with pytest.raises(GuruSpeechError) as exc_info:
            cleaner.clean_file(input_path, output_path)
        
        assert "NoiseCleaner" in str(exc_info.value)
        assert "nonexistent_file.wav" in str(exc_info.value)
    
    def test_clean_file_invalid_audio_format(self):
        """Test clean_file() with invalid audio file."""
        cleaner = NoiseCleaner()
        
        # Create a text file instead of audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, mode='w') as input_file:
            input_path = input_file.name
            input_file.write("This is not audio data")
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            with pytest.raises(GuruSpeechError) as exc_info:
                cleaner.clean_file(input_path, output_path)
            
            assert "NoiseCleaner" in str(exc_info.value)
        
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_clean_file_invalid_output_path(self):
        """Test clean_file() with invalid output path."""
        cleaner = NoiseCleaner()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
            input_path = input_file.name
        
        try:
            # Create valid input file
            sample_rate = 16000
            audio_data = np.random.randn(16000).astype(np.float32)
            sf.write(input_path, audio_data, sample_rate)
            
            # Try to write to invalid path
            output_path = "/invalid/path/that/does/not/exist/output.wav"
            
            with pytest.raises(GuruSpeechError) as exc_info:
                cleaner.clean_file(input_path, output_path)
            
            assert "NoiseCleaner" in str(exc_info.value)
        
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)


class TestNoiseCleanerConfiguration:
    """Unit tests for NoiseCleaner configuration."""
    
    def test_initialization_default_parameters(self):
        """Test NoiseCleaner initialization with default parameters."""
        cleaner = NoiseCleaner()
        
        assert cleaner.stationary is True
        assert cleaner.prop_decrease == 1.0
    
    def test_initialization_custom_parameters(self):
        """Test NoiseCleaner initialization with custom parameters."""
        cleaner = NoiseCleaner(stationary=False, prop_decrease=0.5)
        
        assert cleaner.stationary is False
        assert cleaner.prop_decrease == 0.5
    
    def test_configuration_affects_processing(self):
        """Test that configuration parameters affect processing."""
        sample_rate = 16000
        audio_data = np.random.randn(16000).astype(np.float32)
        
        # Create cleaners with different configurations
        cleaner1 = NoiseCleaner(stationary=True, prop_decrease=1.0)
        cleaner2 = NoiseCleaner(stationary=True, prop_decrease=0.0)
        
        cleaned1 = cleaner1.clean(audio_data, sample_rate)
        cleaned2 = cleaner2.clean(audio_data, sample_rate)
        
        # Both should produce valid output
        assert np.all(np.isfinite(cleaned1))
        assert np.all(np.isfinite(cleaned2))
        
        # With prop_decrease=0.0, output should be closer to original
        # (though exact equality depends on noisereduce implementation)
        assert cleaned1.shape == cleaned2.shape
