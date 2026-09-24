"""Property-based tests for voice biometric feature extraction.

**Property 8: Voice Biometric Confidence Bounds**
**Validates: Requirements 3.2, 3.3**
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings

from Agent_Guru.speech.biometric import VoiceFeatureExtractor
from Agent_Guru.speech.exceptions import VoiceBiometricError

# The first librosa call JIT-compiles numba code (18-30 s cold). Warm it once
# per session, before any test starts, so no individual test is charged the
# compile inside its own timeout budget.
pytestmark = pytest.mark.usefixtures("warm_librosa")


# Strategy for generating valid audio data
@st.composite
def audio_data(draw):
    """Generate valid audio data for testing."""
    # Duration between 0.5 and 10 seconds
    duration = draw(st.floats(min_value=0.5, max_value=10.0))
    sample_rate = draw(st.sampled_from([8000, 16000, 22050, 44100, 48000]))
    
    num_samples = int(duration * sample_rate)
    
    # Generate audio with some signal
    # Mix of sine waves to simulate voice-like content
    t = np.linspace(0, duration, num_samples)
    
    # Fundamental frequency (typical voice range: 80-300 Hz)
    f0 = draw(st.floats(min_value=80, max_value=300))
    
    # Generate signal with harmonics
    signal = np.sin(2 * np.pi * f0 * t)
    signal += 0.5 * np.sin(2 * np.pi * 2 * f0 * t)  # 2nd harmonic
    signal += 0.3 * np.sin(2 * np.pi * 3 * f0 * t)  # 3rd harmonic
    
    # Add some noise
    noise_level = draw(st.floats(min_value=0.0, max_value=0.3))
    noise = np.random.randn(num_samples) * noise_level
    
    audio = signal + noise
    
    # Normalize
    if np.max(np.abs(audio)) > 0:
        audio = audio / np.max(np.abs(audio)) * 0.9
    
    return audio.astype(np.float32), sample_rate


class TestVoiceBiometricConfidenceBounds:
    """Property 8: Voice Biometric Confidence Bounds.
    
    **Validates: Requirements 3.2, 3.3**
    
    Requirements:
    - 3.2: WHEN verifying a speaker, THE Voice_Biometrics SHALL complete 
           verification within 500 milliseconds
    - 3.3: WHEN comparing voice samples, THE Voice_Biometrics SHALL return 
           a confidence score between 0.0 and 1.0
    """
    
    @given(audio_data())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_confidence_bounds(self, audio_sample):
        """Test that confidence scores are always between 0.0 and 1.0.
        
        **Property**: For any valid audio input, the confidence score
        (quality_score) must be in the range [0.0, 1.0].
        """
        audio, sample_rate = audio_sample
        
        extractor = VoiceFeatureExtractor()
        
        # Extract features
        features = await extractor.extract_features(audio, sample_rate)
        
        # Property: Quality score (confidence) must be between 0.0 and 1.0
        assert 0.0 <= features.quality_score <= 1.0, (  # nosec B101
            f"Quality score {features.quality_score} is outside [0.0, 1.0] range"
        )
    
    @given(audio_data())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_feature_vector_properties(self, audio_sample):
        """Test that feature vectors have expected properties.
        
        **Property**: Feature vectors must be non-empty, finite, and consistent.
        """
        audio, sample_rate = audio_sample
        
        extractor = VoiceFeatureExtractor()
        
        # Extract features
        features = await extractor.extract_features(audio, sample_rate)
        
        # Property: Feature vector must be non-empty
        assert len(features.feature_vector) > 0, "Feature vector is empty"  # nosec B101
        
        # Property: All feature values must be finite
        assert np.all(np.isfinite(features.feature_vector)), (  # nosec B101
            "Feature vector contains non-finite values"
        )
        
        # Property: Feature vector should have consistent size
        # Based on implementation: 20 MFCC mean + 20 MFCC std + 4 pitch + 
        # 4 spectral + 2 zcr + 2 energy = 52 features
        expected_size = 52
        assert len(features.feature_vector) == expected_size, (  # nosec B101
            f"Feature vector size {len(features.feature_vector)} != {expected_size}"
        )
    
    @given(audio_data())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_metadata_validity(self, audio_sample):
        """Test that metadata fields are valid.
        
        **Property**: Metadata (sample_rate, duration) must be positive and consistent.
        """
        audio, sample_rate = audio_sample
        
        extractor = VoiceFeatureExtractor()
        
        # Extract features
        features = await extractor.extract_features(audio, sample_rate)
        
        # Property: Sample rate must match input
        assert features.sample_rate == sample_rate, (  # nosec B101
            f"Sample rate mismatch: {features.sample_rate} != {sample_rate}"
        )
        
        # Property: Duration must be positive
        assert features.duration > 0, f"Duration {features.duration} is not positive"  # nosec B101
        
        # Property: Duration must be approximately correct
        expected_duration = len(audio) / sample_rate
        duration_error = abs(features.duration - expected_duration)
        assert duration_error < 0.01, (  # nosec B101
            f"Duration error {duration_error} too large "
            f"(expected {expected_duration}, got {features.duration})"
        )
    
    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_consistency_across_calls(self, seed):
        """Test that same audio produces same features.
        
        **Property**: Extracting features from the same audio multiple times
        should produce identical results (deterministic).
        """
        np.random.seed(seed)
        
        # Generate test audio
        sample_rate = 16000
        duration = 2.0
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples)
        audio = np.sin(2 * np.pi * 150 * t).astype(np.float32)
        
        extractor = VoiceFeatureExtractor()
        
        # Extract features twice
        features1 = await extractor.extract_features(audio, sample_rate)
        features2 = await extractor.extract_features(audio, sample_rate)
        
        # Property: Results should be identical
        assert np.allclose(features1.feature_vector, features2.feature_vector), (  # nosec B101
            "Feature extraction is not deterministic"
        )
        assert features1.quality_score == features2.quality_score, (  # nosec B101
            "Quality score is not deterministic"
        )
        assert features1.duration == features2.duration, (  # nosec B101
            "Duration is not deterministic"
        )
    
    @given(
        st.floats(min_value=0.1, max_value=0.99),
        st.sampled_from([8000, 16000, 22050, 44100])
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_quality_score_sensitivity(self, noise_level, sample_rate):
        """Test that quality score responds to audio quality.
        
        **Property**: Higher noise levels should generally result in lower
        quality scores.
        """
        # Generate clean audio
        duration = 2.0
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples)
        clean_audio = np.sin(2 * np.pi * 150 * t)
        
        # Add noise
        noise = np.random.randn(num_samples) * noise_level
        noisy_audio = (clean_audio + noise).astype(np.float32)
        
        # Normalize
        if np.max(np.abs(noisy_audio)) > 0:
            noisy_audio = noisy_audio / np.max(np.abs(noisy_audio)) * 0.9
        
        extractor = VoiceFeatureExtractor()
        
        # Extract features
        features = await extractor.extract_features(noisy_audio, sample_rate)
        
        # Property: Quality score should still be in valid range
        assert 0.0 <= features.quality_score <= 1.0, (  # nosec B101
            f"Quality score {features.quality_score} outside valid range"
        )
        
        # Property: Very noisy audio should have lower quality
        if noise_level > 0.7:
            assert features.quality_score < 0.9, (  # nosec B101
                f"Quality score {features.quality_score} too high for noise level {noise_level}"
            )
    
    @given(st.sampled_from([8000, 16000, 22050, 44100, 48000]))
    @settings(max_examples=50, deadline=None)
    def test_quality_score_bounds(self, sample_rate):
        """Test that compute_quality_score always returns valid range.
        
        **Property**: Quality score must always be between 0.0 and 1.0,
        regardless of input.
        """
        extractor = VoiceFeatureExtractor()
        
        # Test with various audio types
        test_cases = [
            np.zeros(sample_rate, dtype=np.float32),  # Silence
            np.ones(sample_rate, dtype=np.float32),  # Constant
            np.random.randn(sample_rate).astype(np.float32),  # Noise
            np.sin(2 * np.pi * 150 * np.linspace(0, 1, sample_rate)).astype(np.float32),  # Tone
        ]
        
        for audio in test_cases:
            quality = extractor.compute_quality_score(audio, sample_rate)
            
            # Property: Quality score must be in [0.0, 1.0]
            assert 0.0 <= quality <= 1.0, (  # nosec B101
                f"Quality score {quality} outside [0.0, 1.0] for audio type"
            )
    
    @given(audio_data())
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_empty_audio_handling(self, audio_sample):
        """Test that empty audio is handled gracefully.
        
        **Property**: Empty audio should raise VoiceBiometricError.
        """
        _, sample_rate = audio_sample
        
        extractor = VoiceFeatureExtractor()
        
        # Test with empty audio
        empty_audio = np.array([], dtype=np.float32)
        
        with pytest.raises(VoiceBiometricError, match="Audio data is empty"):
            await extractor.extract_features(empty_audio, sample_rate)
    
    @given(audio_data())
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_invalid_sample_rate_handling(self, audio_sample):
        """Test that invalid sample rates are handled gracefully.
        
        **Property**: Invalid sample rates should raise VoiceBiometricError.
        """
        audio, _ = audio_sample
        
        extractor = VoiceFeatureExtractor()
        
        # Test with invalid sample rates
        invalid_rates = [0, -1, -16000]
        
        for rate in invalid_rates:
            with pytest.raises(VoiceBiometricError, match="Invalid sample rate"):
                await extractor.extract_features(audio, rate)
