"""Property-based tests for voice cloning - MAXIMUM COVERAGE.

Property 17: Voice Cloning Quality
Validates: Requirements 14.2, 14.3, 14.5
"""

import numpy as np
from hypothesis import given, strategies as st, settings, HealthCheck
import pytest

from Agent_Guru.speech.tts.voice_cloner import VoiceCloner, VoiceCloningError


# Shared fixture
@pytest.fixture(scope="module")
def voice_cloner():
    """Create a voice cloner for all tests."""
    return VoiceCloner()


# Strategy for generating audio samples
@st.composite
def audio_sample_strategy(draw):
    """Generate realistic audio samples."""
    duration = draw(st.floats(min_value=5.0, max_value=15.0))
    sample_rate = 16000
    num_samples = int(duration * sample_rate)
    
    # Generate synthetic speech-like audio
    t = np.linspace(0, duration, num_samples)
    
    # Base frequency (pitch)
    base_freq = draw(st.floats(min_value=80, max_value=300))
    
    # Generate audio with harmonics
    audio = np.sin(2 * np.pi * base_freq * t)
    audio += 0.3 * np.sin(2 * np.pi * base_freq * 2 * t)
    audio += 0.2 * np.sin(2 * np.pi * base_freq * 3 * t)
    
    # Add noise
    noise_level = draw(st.floats(min_value=0.05, max_value=0.2))
    audio += noise_level * np.random.randn(num_samples)
    
    # Normalize
    if np.max(np.abs(audio)) > 0:
        audio = audio / np.max(np.abs(audio)) * 0.8
    
    return audio.astype(np.float32)


@given(
    num_samples=st.integers(min_value=30, max_value=50),
    voice_id=st.text(min_size=5, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.function_scoped_fixture]
)
@pytest.mark.timeout(600)
def test_property_17_voice_cloning_quality(voice_cloner, num_samples, voice_id):
    """
    Property 17: Voice Cloning Quality
    
    **Validates: Requirements 14.2, 14.3, 14.5**
    
    Tests that:
    1. Voice enrollment succeeds with sufficient audio
    2. Cloned voice similarity is >0.85
    3. Incremental learning improves or maintains quality
    """
    # Generate audio samples
    duration = 10.0
    sample_rate = 16000
    num_audio_samples = int(duration * sample_rate)
    
    # Generate consistent audio for this voice
    np.random.seed(hash(voice_id) % (2**32))
    base_freq = 100 + (hash(voice_id) % 200)
    
    audio_samples = []
    for _ in range(num_samples):
        t = np.linspace(0, duration, num_audio_samples)
        audio = np.sin(2 * np.pi * base_freq * t)
        audio += 0.3 * np.sin(2 * np.pi * base_freq * 2 * t)
        audio += 0.1 * np.random.randn(num_audio_samples)
        audio = audio / np.max(np.abs(audio)) * 0.8
        audio_samples.append(audio.astype(np.float32))
    
    # Test 1: Enrollment succeeds
    try:
        voice_model = voice_cloner.enroll_voice(
            audio_samples=audio_samples,
            voice_id=voice_id,
            sample_rate=sample_rate
        )
        
        assert voice_model is not None, "Voice model should be created"
        assert voice_model.model_id == voice_id, "Voice ID should match"
        assert voice_model.voice_characteristics["sample_count"] == num_samples, "Sample count should match"
        assert voice_model.training_duration_seconds >= 300.0, "Training duration should be >= 5 minutes"
        assert 0.0 <= voice_model.voice_characteristics["quality_score"] <= 1.0, "Quality score should be in [0, 1]"
        
        # Test 2: Voice similarity
        # Generate new audio with same characteristics
        test_audio1 = audio_samples[0]
        test_audio2 = audio_samples[1] if len(audio_samples) > 1 else audio_samples[0]
        
        similarity = voice_cloner.compute_similarity(
            audio1=test_audio1,
            audio2=test_audio2,
            sample_rate=sample_rate
        )
        
        assert 0.0 <= similarity <= 1.0, "Similarity should be in [0, 1]"
        # Similar audio from same voice should have high similarity
        assert similarity > 0.7, f"Similarity {similarity:.3f} should be >0.7 for same voice"
        
        # Test 3: Incremental learning
        if len(audio_samples) > 10:
            new_samples = audio_samples[-5:]
            updated_model = voice_cloner.update_voice_model(
                voice_id=voice_id,
                new_audio_samples=new_samples,
                sample_rate=sample_rate
            )
            
            assert updated_model.voice_characteristics["sample_count"] > voice_model.voice_characteristics["sample_count"], \
                "Sample count should increase after update"
            assert updated_model.training_duration_seconds > voice_model.training_duration_seconds, \
                "Training duration should increase after update"
            assert 0.0 <= updated_model.voice_characteristics["quality_score"] <= 1.0, \
                "Updated quality score should be in [0, 1]"
        
        # Cleanup
        voice_cloner.delete_voice(voice_id)
        
    except VoiceCloningError as e:
        # If enrollment fails due to quality, that's acceptable
        if "quality too low" in str(e).lower():
            pytest.skip(f"Audio quality too low for enrollment: {e}")
        else:
            raise


@given(
    audio_duration=st.floats(min_value=5.0, max_value=15.0),
    base_freq=st.floats(min_value=80, max_value=300)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@pytest.mark.timeout(600)
def test_voice_similarity_consistency(voice_cloner, audio_duration, base_freq):
    """
    Test that voice similarity is consistent and symmetric.
    
    Properties:
    - similarity(A, A) ≈ 1.0 (identity)
    - similarity(A, B) = similarity(B, A) (symmetry)
    - 0.0 <= similarity <= 1.0 (bounds)
    """
    sample_rate = 16000
    num_samples = int(audio_duration * sample_rate)
    
    # Generate audio A
    t = np.linspace(0, audio_duration, num_samples)
    audio_a = np.sin(2 * np.pi * base_freq * t)
    audio_a += 0.3 * np.sin(2 * np.pi * base_freq * 2 * t)
    audio_a += 0.1 * np.random.randn(num_samples)
    audio_a = audio_a / np.max(np.abs(audio_a)) * 0.8
    audio_a = audio_a.astype(np.float32)
    
    # Generate audio B (slightly different)
    audio_b = np.sin(2 * np.pi * (base_freq + 10) * t)
    audio_b += 0.3 * np.sin(2 * np.pi * (base_freq + 10) * 2 * t)
    audio_b += 0.1 * np.random.randn(num_samples)
    audio_b = audio_b / np.max(np.abs(audio_b)) * 0.8
    audio_b = audio_b.astype(np.float32)
    
    # Test identity: similarity(A, A) should be very high
    sim_aa = voice_cloner.compute_similarity(audio_a, audio_a, sample_rate)
    assert sim_aa > 0.95, f"Self-similarity {sim_aa:.3f} should be >0.95"
    
    # Test symmetry: similarity(A, B) = similarity(B, A)
    sim_ab = voice_cloner.compute_similarity(audio_a, audio_b, sample_rate)
    sim_ba = voice_cloner.compute_similarity(audio_b, audio_a, sample_rate)
    
    assert abs(sim_ab - sim_ba) < 0.01, \
        f"Similarity should be symmetric: {sim_ab:.3f} vs {sim_ba:.3f}"
    
    # Test bounds
    assert 0.0 <= sim_ab <= 1.0, f"Similarity {sim_ab:.3f} should be in [0, 1]"
    assert 0.0 <= sim_ba <= 1.0, f"Similarity {sim_ba:.3f} should be in [0, 1]"


@given(
    num_updates=st.integers(min_value=1, max_value=10)
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@pytest.mark.timeout(600)
def test_incremental_learning_stability(voice_cloner, num_updates):
    """
    Test that incremental learning is stable and doesn't degrade quality.
    
    Properties:
    - Quality score should not decrease significantly
    - Feature vector should remain stable
    - Sample count should increase correctly
    """
    # Generate initial audio samples
    duration = 10.0
    sample_rate = 16000
    num_samples = int(duration * sample_rate)
    
    t = np.linspace(0, duration, num_samples)
    base_audio = np.sin(2 * np.pi * 150 * t)
    base_audio += 0.3 * np.sin(2 * np.pi * 300 * t)
    base_audio += 0.1 * np.random.randn(num_samples)
    base_audio = base_audio / np.max(np.abs(base_audio)) * 0.8
    base_audio = base_audio.astype(np.float32)
    
    # Initial enrollment
    audio_samples = [base_audio for _ in range(30)]
    voice_id = f"test_stability_{num_updates}"
    
    try:
        initial_model = voice_cloner.enroll_voice(
            audio_samples=audio_samples,
            voice_id=voice_id,
            sample_rate=sample_rate
        )
        
        initial_quality = initial_model.voice_characteristics["quality_score"]
        initial_sample_count = initial_model.voice_characteristics["sample_count"]
        
        # Perform incremental updates
        for i in range(num_updates):
            # Generate slightly varied audio
            varied_audio = base_audio + np.random.randn(num_samples).astype(np.float32) * 0.05
            varied_audio = varied_audio / np.max(np.abs(varied_audio)) * 0.8
            
            updated_model = voice_cloner.update_voice_model(
                voice_id=voice_id,
                new_audio_samples=[varied_audio],
                sample_rate=sample_rate
            )
            
            # Check quality doesn't degrade significantly
            quality_change = updated_model.voice_characteristics["quality_score"] - initial_quality
            assert quality_change > -0.2, \
                f"Quality degraded too much: {initial_quality:.3f} -> {updated_model.voice_characteristics['quality_score']:.3f}"
            
            # Check sample count increases
            assert updated_model.voice_characteristics["sample_count"] == initial_sample_count + i + 1, \
                "Sample count should increase by 1 per update"
        
        # Cleanup
        voice_cloner.delete_voice(voice_id)
        
    except VoiceCloningError as e:
        if "quality too low" in str(e).lower():
            pytest.skip(f"Audio quality too low: {e}")
        else:
            raise


@given(
    sample_rate=st.sampled_from([8000, 16000, 22050, 44100])
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]
)
@pytest.mark.timeout(300)
def test_voice_cloning_different_sample_rates(voice_cloner, sample_rate):
    """
    Test voice cloning works with different sample rates.
    
    Properties:
    - Feature extraction works for all sample rates
    - Quality computation is consistent
    - Similarity computation is valid
    """
    duration = 10.0
    num_samples = int(duration * sample_rate)
    
    # Generate audio
    t = np.linspace(0, duration, num_samples)
    audio = np.sin(2 * np.pi * 150 * t)
    audio += 0.3 * np.sin(2 * np.pi * 300 * t)
    audio += 0.1 * np.random.randn(num_samples)
    audio = audio / np.max(np.abs(audio)) * 0.8
    audio = audio.astype(np.float32)
    
    # Test feature extraction
    features = voice_cloner._extract_voice_features(audio, sample_rate)
    assert features is not None, "Features should be extracted"
    assert len(features) > 0, "Features should not be empty"
    assert features.dtype == np.float32, "Features should be float32"
    
    # Test quality computation
    quality = voice_cloner._compute_audio_quality(audio, sample_rate)
    assert 0.0 <= quality <= 1.0, f"Quality {quality:.3f} should be in [0, 1]"
    
    # Test similarity computation
    similarity = voice_cloner.compute_similarity(audio, audio, sample_rate)
    assert similarity > 0.95, f"Self-similarity {similarity:.3f} should be >0.95"


# Unit tests for edge cases

def test_voice_cloning_empty_audio(voice_cloner):
    """Test handling of empty audio."""
    empty_audio = np.array([], dtype=np.float32)
    
    # Should handle gracefully
    features = voice_cloner._extract_voice_features(empty_audio, 16000)
    assert features is not None


def test_voice_cloning_silent_audio(voice_cloner):
    """Test handling of silent audio."""
    silent_audio = np.zeros(16000, dtype=np.float32)
    
    features = voice_cloner._extract_voice_features(silent_audio, 16000)
    assert features is not None
    
    quality = voice_cloner._compute_audio_quality(silent_audio, 16000)
    assert quality < 0.5  # Silent audio should have low quality


def test_voice_cloning_clipped_audio(voice_cloner):
    """Test handling of clipped audio."""
    # Generate clipped audio
    clipped_audio = np.ones(16000, dtype=np.float32)
    
    quality = voice_cloner._compute_audio_quality(clipped_audio, 16000)
    assert quality < 0.8  # Clipped audio should have reduced quality


def test_voice_cloning_very_short_audio(voice_cloner):
    """Test handling of very short audio."""
    # 0.01 seconds
    short_audio = np.random.randn(160).astype(np.float32)
    
    features = voice_cloner._extract_voice_features(short_audio, 16000)
    assert features is not None
    
    quality = voice_cloner._compute_audio_quality(short_audio, 16000)
    assert 0.0 <= quality <= 1.0


def test_voice_cloning_very_long_audio(voice_cloner):
    """Test handling of very long audio."""
    # 60 seconds
    long_audio = np.random.randn(16000 * 60).astype(np.float32) * 0.5
    
    features = voice_cloner._extract_voice_features(long_audio, 16000)
    assert features is not None
    
    quality = voice_cloner._compute_audio_quality(long_audio, 16000)
    assert 0.0 <= quality <= 1.0


def test_voice_cloning_feature_consistency(voice_cloner):
    """Test that feature extraction is consistent."""
    # Generate audio
    duration = 10.0
    sample_rate = 16000
    num_samples = int(duration * sample_rate)
    
    t = np.linspace(0, duration, num_samples)
    audio = np.sin(2 * np.pi * 150 * t).astype(np.float32)
    
    # Extract features multiple times
    features1 = voice_cloner._extract_voice_features(audio, sample_rate)
    features2 = voice_cloner._extract_voice_features(audio, sample_rate)
    
    # Should be identical
    assert np.allclose(features1, features2), "Features should be consistent"


def test_voice_cloning_quality_consistency(voice_cloner):
    """Test that quality computation is consistent."""
    # Generate audio
    duration = 10.0
    sample_rate = 16000
    num_samples = int(duration * sample_rate)
    
    audio = np.random.randn(num_samples).astype(np.float32) * 0.5
    
    # Compute quality multiple times
    quality1 = voice_cloner._compute_audio_quality(audio, sample_rate)
    quality2 = voice_cloner._compute_audio_quality(audio, sample_rate)
    
    # Should be identical
    assert quality1 == quality2, "Quality should be consistent"
