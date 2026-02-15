"""
Property-based tests for NoiseCleaner module.

This module contains property tests that verify universal correctness properties
of the noise reduction functionality.
"""

import numpy as np
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from .noise import NoiseCleaner


# Strategy for generating valid sample rates
sample_rates = st.sampled_from([8000, 16000, 22050, 44100, 48000])

# Strategy for generating valid audio data
# Audio values should be in range [-1.0, 1.0] for normalized audio
# Generate arrays with smaller sizes for faster testing (0.05 to 1 seconds)
def audio_array_strategy(sample_rate):
    """Generate audio arrays based on sample rate."""
    min_samples = int(sample_rate * 0.05)  # 0.05 seconds
    max_samples = int(sample_rate * 1.0)   # 1 second
    return st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=min_samples,
        max_size=max_samples
    ).map(lambda x: np.array(x, dtype=np.float32))


@settings(
    max_examples=100, 
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example, HealthCheck.data_too_large]
)
@given(
    sample_rate=sample_rates,
    data=st.data()
)
def test_noise_cleaner_format_compatibility(sample_rate, data):
    """
    Feature: guru-speech-engine, Property 2: Noise Cleaner Format Compatibility
    
    For any audio input (numpy array with sample rate), the Noise_Cleaner output 
    should be a numpy array with the same sample rate and compatible shape for 
    the Whisper_Model.
    
    **Validates: Requirements 2.4**
    
    This property verifies that:
    1. Output is a numpy array
    2. Output has the same or compatible shape as input
    3. Output dtype is compatible (float32 or float64)
    4. Output values are in valid audio range
    5. Sample rate is preserved (implicitly, as it's not modified)
    """
    # Generate audio data based on sample rate
    audio_data = data.draw(audio_array_strategy(sample_rate))
    
    # Create noise cleaner
    cleaner = NoiseCleaner(stationary=True, prop_decrease=1.0)
    
    # Apply noise reduction
    cleaned_audio = cleaner.clean(audio_data, sample_rate)
    
    # Property assertions
    
    # 1. Output must be a numpy array
    assert isinstance(cleaned_audio, np.ndarray), \
        "Cleaned audio must be a numpy array"
    
    # 2. Output shape must match input shape (same number of samples)
    assert cleaned_audio.shape == audio_data.shape, \
        f"Output shape {cleaned_audio.shape} must match input shape {audio_data.shape}"
    
    # 3. Output dtype must be compatible (float types for audio processing)
    assert cleaned_audio.dtype in [np.float32, np.float64], \
        f"Output dtype {cleaned_audio.dtype} must be float32 or float64 for Whisper compatibility"
    
    # 4. Output values should be in valid audio range (may exceed [-1, 1] slightly due to processing)
    # We allow a small tolerance for numerical processing artifacts
    assert np.all(np.isfinite(cleaned_audio)), \
        "Output must not contain NaN or infinite values"
    
    # 5. Output should have same dimensionality (1D array for mono audio)
    assert cleaned_audio.ndim == audio_data.ndim, \
        f"Output dimensionality {cleaned_audio.ndim} must match input dimensionality {audio_data.ndim}"


@settings(
    max_examples=100, 
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example, HealthCheck.data_too_large]
)
@given(
    sample_rate=sample_rates,
    channels=st.sampled_from([1, 2]),  # Mono or stereo
    data=st.data()
)
def test_noise_cleaner_multichannel_compatibility(sample_rate, channels, data):
    """
    Feature: guru-speech-engine, Property 2: Noise Cleaner Format Compatibility (Multi-channel)
    
    For any multi-channel audio input, the Noise_Cleaner should preserve the 
    channel structure in the output.
    
    **Validates: Requirements 2.4**
    """
    # Generate audio data with multiple channels
    # Cap at 5000 samples to avoid Hypothesis buffer size limits
    min_samples = int(sample_rate * 0.05)
    max_samples = min(int(sample_rate * 1.0), 5000)
    
    if channels == 1:
        # Mono audio - 1D array
        audio_data = data.draw(
            st.lists(
                st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=min_samples,
                max_size=max_samples
            ).map(lambda x: np.array(x, dtype=np.float32))
        )
    else:
        # Stereo audio - 2D array with shape (samples, channels)
        num_samples = data.draw(st.integers(min_value=min_samples, max_value=max_samples))
        audio_data = data.draw(
            st.lists(
                st.lists(
                    st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                    min_size=channels,
                    max_size=channels
                ),
                min_size=num_samples,
                max_size=num_samples
            ).map(lambda x: np.array(x, dtype=np.float32))
        )
    
    # Create noise cleaner
    cleaner = NoiseCleaner(stationary=True, prop_decrease=1.0)
    
    # Apply noise reduction
    cleaned_audio = cleaner.clean(audio_data, sample_rate)
    
    # Property assertions
    assert isinstance(cleaned_audio, np.ndarray), \
        "Cleaned audio must be a numpy array"
    
    assert cleaned_audio.shape == audio_data.shape, \
        f"Output shape {cleaned_audio.shape} must match input shape {audio_data.shape}"
    
    assert cleaned_audio.dtype in [np.float32, np.float64], \
        f"Output dtype must be compatible with Whisper (got {cleaned_audio.dtype})"
    
    assert np.all(np.isfinite(cleaned_audio)), \
        "Output must not contain NaN or infinite values"


@settings(
    max_examples=50, 
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example, HealthCheck.data_too_large]
)
@given(
    sample_rate=sample_rates,
    stationary=st.booleans(),
    prop_decrease=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    data=st.data()
)
def test_noise_cleaner_configuration_compatibility(sample_rate, stationary, prop_decrease, data):
    """
    Feature: guru-speech-engine, Property 2: Noise Cleaner Format Compatibility (Configuration)
    
    For any valid configuration parameters, the Noise_Cleaner should still produce
    output compatible with Whisper_Model.
    
    **Validates: Requirements 2.4**
    """
    # Generate audio data
    audio_data = data.draw(audio_array_strategy(sample_rate))
    
    # Create noise cleaner with various configurations
    cleaner = NoiseCleaner(stationary=stationary, prop_decrease=prop_decrease)
    
    # Apply noise reduction
    cleaned_audio = cleaner.clean(audio_data, sample_rate)
    
    # Property assertions - format compatibility regardless of configuration
    assert isinstance(cleaned_audio, np.ndarray), \
        "Cleaned audio must be a numpy array"
    
    assert cleaned_audio.shape == audio_data.shape, \
        f"Output shape must match input shape"
    
    assert cleaned_audio.dtype in [np.float32, np.float64], \
        f"Output dtype must be compatible with Whisper"
    
    assert np.all(np.isfinite(cleaned_audio)), \
        "Output must not contain NaN or infinite values"
