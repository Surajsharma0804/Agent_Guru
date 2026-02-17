"""Unit tests for voice cloning - COMPREHENSIVE COVERAGE."""

import numpy as np
import pytest
import tempfile
import os

from Agent_Guru.speech.tts.voice_cloner import VoiceCloner, VoiceCloningError
from Agent_Guru.speech.models import VoiceModel


@pytest.fixture
def voice_cloner():
    """Create a voice cloner for testing."""
    return VoiceCloner()


@pytest.fixture
def sample_audio():
    """Generate sample audio for testing."""
    # Generate 10 seconds of audio at 16kHz
    duration = 10.0
    sample_rate = 16000
    num_samples = int(duration * sample_rate)
    
    # Generate synthetic speech-like audio
    t = np.linspace(0, duration, num_samples)
    audio = np.sin(2 * np.pi * 150 * t)  # 150 Hz base frequency
    audio += 0.3 * np.sin(2 * np.pi * 300 * t)  # Harmonic
    audio += 0.1 * np.random.randn(num_samples)  # Noise
    
    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.8
    
    return audio.astype(np.float32)


def test_voice_cloner_initialization(voice_cloner):
    """Test voice cloner initialization."""
    assert voice_cloner is not None
    assert voice_cloner.n_mfcc == 40
    assert voice_cloner.sample_rate == 16000
    assert voice_cloner.min_enrollment_duration == 300.0
    assert len(voice_cloner.list_voices()) == 0


def test_enroll_voice_success(voice_cloner, sample_audio):
    """Test successful voice enrollment."""
    # Create 30 samples of 10 seconds each (300 seconds total)
    audio_samples = [sample_audio for _ in range(30)]
    
    voice_model = voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_voice_1",
        sample_rate=16000,
        metadata={"name": "Test User"}
    )
    
    assert voice_model is not None
    assert voice_model.model_id == "test_voice_1"
    assert voice_model.voice_characteristics["sample_count"] == 30
    assert voice_model.training_duration_seconds >= 300.0
    assert voice_model.voice_characteristics["quality_score"] > 0.0
    
    # Check voice is in list
    assert "test_voice_1" in voice_cloner.list_voices()


def test_enroll_voice_insufficient_audio(voice_cloner, sample_audio):
    """Test enrollment fails with insufficient audio."""
    # Only 1 sample (10 seconds) - need 300 seconds
    audio_samples = [sample_audio]
    
    with pytest.raises(VoiceCloningError, match="Insufficient audio"):
        voice_cloner.enroll_voice(
            audio_samples=audio_samples,
            voice_id="test_voice_fail",
            sample_rate=16000
        )


def test_enroll_voice_empty_samples(voice_cloner):
    """Test enrollment fails with empty samples."""
    with pytest.raises(VoiceCloningError, match="No audio samples"):
        voice_cloner.enroll_voice(
            audio_samples=[],
            voice_id="test_voice_empty",
            sample_rate=16000
        )


def test_enroll_voice_low_quality(voice_cloner):
    """Test enrollment with low quality audio (should succeed but with lower quality score)."""
    # Generate audio with low SNR (noisy)
    duration = 10.0
    sample_rate = 16000
    num_samples = int(duration * sample_rate)
    
    # Generate noisy audio (high noise, low signal)
    t = np.linspace(0, duration, num_samples)
    signal = np.sin(2 * np.pi * 150 * t) * 0.1  # Weak signal
    noise = np.random.randn(num_samples) * 0.5  # Strong noise
    audio = (signal + noise).astype(np.float32)
    
    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.8
    
    audio_samples = [audio for _ in range(30)]
    
    # This should succeed
    voice_model = voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_voice_low_quality",
        sample_rate=16000
    )
    
    # Check that it enrolled successfully
    assert voice_model is not None
    assert voice_model.model_id == "test_voice_low_quality"


def test_update_voice_model(voice_cloner, sample_audio):
    """Test voice model update with new samples."""
    # Initial enrollment
    audio_samples = [sample_audio for _ in range(30)]
    initial_model = voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_voice_update",
        sample_rate=16000
    )
    
    initial_sample_count = initial_model.voice_characteristics["sample_count"]
    initial_duration = initial_model.training_duration_seconds
    
    # Update with new samples
    new_samples = [sample_audio for _ in range(10)]
    updated_model = voice_cloner.update_voice_model(
        voice_id="test_voice_update",
        new_audio_samples=new_samples,
        sample_rate=16000
    )
    
    assert updated_model.voice_characteristics["sample_count"] == initial_sample_count + 10
    assert updated_model.training_duration_seconds > initial_duration
    assert updated_model.model_id == "test_voice_update"


def test_update_voice_model_not_found(voice_cloner, sample_audio):
    """Test update fails for non-existent voice."""
    with pytest.raises(VoiceCloningError, match="not found"):
        voice_cloner.update_voice_model(
            voice_id="nonexistent_voice",
            new_audio_samples=[sample_audio],
            sample_rate=16000
        )


def test_synthesize_with_cloned_voice(voice_cloner, sample_audio):
    """Test synthesis with cloned voice."""
    # Enroll voice
    audio_samples = [sample_audio for _ in range(30)]
    voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_voice_synth",
        sample_rate=16000
    )
    
    # Synthesize
    text = "Hello, this is a test of voice cloning."
    synthesized = voice_cloner.synthesize_with_cloned_voice(
        text=text,
        voice_id="test_voice_synth"
    )
    
    assert synthesized is not None
    assert len(synthesized) > 0
    assert synthesized.dtype == np.float32
    assert np.max(np.abs(synthesized)) <= 1.0


def test_synthesize_voice_not_found(voice_cloner):
    """Test synthesis fails for non-existent voice."""
    with pytest.raises(VoiceCloningError, match="not found"):
        voice_cloner.synthesize_with_cloned_voice(
            text="Test",
            voice_id="nonexistent_voice"
        )


def test_compute_similarity_identical(voice_cloner, sample_audio):
    """Test similarity computation for identical audio."""
    similarity = voice_cloner.compute_similarity(
        audio1=sample_audio,
        audio2=sample_audio,
        sample_rate=16000
    )
    
    # Identical audio should have very high similarity
    assert similarity > 0.95


def test_compute_similarity_different(voice_cloner, sample_audio):
    """Test similarity computation for different audio."""
    # Generate different audio
    duration = 10.0
    sample_rate = 16000
    num_samples = int(duration * sample_rate)
    
    t = np.linspace(0, duration, num_samples)
    audio2 = np.sin(2 * np.pi * 200 * t).astype(np.float32)  # Different frequency
    
    similarity = voice_cloner.compute_similarity(
        audio1=sample_audio,
        audio2=audio2,
        sample_rate=16000
    )
    
    # Different audio should have lower similarity
    assert 0.0 <= similarity <= 1.0
    assert similarity < 0.95  # Should be less than identical


def test_compute_similarity_similar(voice_cloner, sample_audio):
    """Test similarity computation for similar audio."""
    # Create slightly modified version
    audio2 = sample_audio + np.random.randn(len(sample_audio)).astype(np.float32) * 0.05
    audio2 = audio2 / np.max(np.abs(audio2)) * 0.8
    
    similarity = voice_cloner.compute_similarity(
        audio1=sample_audio,
        audio2=audio2,
        sample_rate=16000
    )
    
    # Similar audio should have high similarity
    assert similarity > 0.7


def test_get_voice_model(voice_cloner, sample_audio):
    """Test retrieving voice model."""
    # Enroll voice
    audio_samples = [sample_audio for _ in range(30)]
    voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_voice_get",
        sample_rate=16000
    )
    
    # Get model
    model = voice_cloner.get_voice_model("test_voice_get")
    
    assert model is not None
    assert model.model_id == "test_voice_get"
    assert model.voice_characteristics["sample_count"] == 30


def test_get_voice_model_not_found(voice_cloner):
    """Test get_voice_model returns None for non-existent voice."""
    model = voice_cloner.get_voice_model("nonexistent_voice")
    assert model is None


def test_list_voices(voice_cloner, sample_audio):
    """Test listing enrolled voices."""
    # Initially empty
    assert len(voice_cloner.list_voices()) == 0
    
    # Enroll multiple voices
    audio_samples = [sample_audio for _ in range(30)]
    
    voice_cloner.enroll_voice(audio_samples, "voice1", 16000)
    voice_cloner.enroll_voice(audio_samples, "voice2", 16000)
    voice_cloner.enroll_voice(audio_samples, "voice3", 16000)
    
    voices = voice_cloner.list_voices()
    assert len(voices) == 3
    assert "voice1" in voices
    assert "voice2" in voices
    assert "voice3" in voices


def test_delete_voice(voice_cloner, sample_audio):
    """Test deleting a voice."""
    # Enroll voice
    audio_samples = [sample_audio for _ in range(30)]
    voice_cloner.enroll_voice(audio_samples, "test_voice_delete", 16000)
    
    assert "test_voice_delete" in voice_cloner.list_voices()
    
    # Delete voice
    result = voice_cloner.delete_voice("test_voice_delete")
    
    assert result is True
    assert "test_voice_delete" not in voice_cloner.list_voices()


def test_delete_voice_not_found(voice_cloner):
    """Test deleting non-existent voice returns False."""
    result = voice_cloner.delete_voice("nonexistent_voice")
    assert result is False


def test_save_and_load_voice_profile(voice_cloner, sample_audio):
    """Test saving and loading voice profile."""
    # Enroll voice
    audio_samples = [sample_audio for _ in range(30)]
    original_model = voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_voice_save",
        sample_rate=16000,
        metadata={"name": "Test User"}
    )
    
    # Save profile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
        filepath = f.name
    
    try:
        voice_cloner.save_voice_profile("test_voice_save", filepath)
        
        # Create new cloner and load profile
        new_cloner = VoiceCloner()
        loaded_voice_id = new_cloner.load_voice_profile(filepath)
        
        assert loaded_voice_id == "test_voice_save"
        
        # Get loaded model
        loaded_model = new_cloner.get_voice_model("test_voice_save")
        
        assert loaded_model is not None
        assert loaded_model.model_id == original_model.model_id
        assert loaded_model.voice_characteristics["sample_count"] == original_model.voice_characteristics["sample_count"]
    finally:
        if os.path.exists(filepath):
            os.unlink(filepath)


def test_save_voice_profile_not_found(voice_cloner):
    """Test save fails for non-existent voice."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
        filepath = f.name
    
    try:
        with pytest.raises(VoiceCloningError, match="not found"):
            voice_cloner.save_voice_profile("nonexistent_voice", filepath)
    finally:
        if os.path.exists(filepath):
            os.unlink(filepath)


def test_load_voice_profile_invalid_file(voice_cloner):
    """Test load fails for invalid file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl', mode='wb') as f:
        # Write invalid data
        f.write(b"invalid data")
        filepath = f.name
    
    try:
        with pytest.raises(VoiceCloningError):
            voice_cloner.load_voice_profile(filepath)
    finally:
        if os.path.exists(filepath):
            os.unlink(filepath)


def test_enroll_voice_with_metadata(voice_cloner, sample_audio):
    """Test enrollment with metadata."""
    audio_samples = [sample_audio for _ in range(30)]
    metadata = {
        "name": "John Doe",
        "age": 30,
        "gender": "male"
    }
    
    voice_model = voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_voice_metadata",
        sample_rate=16000,
        metadata=metadata
    )
    
    assert voice_model is not None
    assert voice_model.model_id == "test_voice_metadata"


def test_multiple_voice_enrollment(voice_cloner, sample_audio):
    """Test enrolling multiple voices."""
    audio_samples = [sample_audio for _ in range(30)]
    
    # Enroll 5 different voices
    for i in range(5):
        voice_model = voice_cloner.enroll_voice(
            audio_samples=audio_samples,
            voice_id=f"voice_{i}",
            sample_rate=16000
        )
        assert voice_model.model_id == f"voice_{i}"
    
    # Check all voices are enrolled
    voices = voice_cloner.list_voices()
    assert len(voices) == 5
    for i in range(5):
        assert f"voice_{i}" in voices


def test_voice_cloner_feature_extraction(voice_cloner, sample_audio):
    """Test feature extraction."""
    features = voice_cloner._extract_voice_features(sample_audio, 16000)
    
    assert features is not None
    assert len(features) > 0
    assert features.dtype == np.float32
    
    # Should have MFCC features (40 mean + 40 std) + pitch + spectral
    expected_size = 40 * 2 + 5  # 85 features
    assert len(features) == expected_size


def test_voice_cloner_audio_quality(voice_cloner, sample_audio):
    """Test audio quality computation."""
    quality = voice_cloner._compute_audio_quality(sample_audio, 16000)
    
    assert 0.0 <= quality <= 1.0
    assert quality > 0.5  # Sample audio should have decent quality


def test_voice_cloner_short_audio_handling(voice_cloner):
    """Test handling of very short audio."""
    # Generate 0.1 second of audio
    short_audio = np.random.randn(1600).astype(np.float32)
    
    # Should not crash
    features = voice_cloner._extract_voice_features(short_audio, 16000)
    assert features is not None
    
    quality = voice_cloner._compute_audio_quality(short_audio, 16000)
    assert 0.0 <= quality <= 1.0


def test_voice_cloner_different_sample_rates(voice_cloner):
    """Test with different sample rates."""
    for sample_rate in [8000, 16000, 22050, 44100]:
        duration = 10.0
        num_samples = int(duration * sample_rate)
        audio = np.random.randn(num_samples).astype(np.float32) * 0.5
        
        features = voice_cloner._extract_voice_features(audio, sample_rate)
        assert features is not None
        assert len(features) > 0


def test_enroll_voice_various_audio_types(voice_cloner):
    """Test enrollment with various audio characteristics."""
    sample_rate = 16000
    duration = 10.0
    num_samples = int(duration * sample_rate)
    
    # Test with different audio types
    audio_types = []
    
    # 1. Pure sine wave
    t = np.linspace(0, duration, num_samples)
    audio_types.append(np.sin(2 * np.pi * 150 * t).astype(np.float32))
    
    # 2. Complex harmonic
    audio = np.sin(2 * np.pi * 150 * t)
    audio += 0.5 * np.sin(2 * np.pi * 300 * t)
    audio += 0.3 * np.sin(2 * np.pi * 450 * t)
    audio_types.append(audio.astype(np.float32))
    
    # 3. Noisy audio
    audio = np.sin(2 * np.pi * 150 * t) + 0.2 * np.random.randn(num_samples)
    audio_types.append(audio.astype(np.float32))
    
    # Enroll with each type
    for i, audio in enumerate(audio_types):
        # Normalize
        audio = audio / np.max(np.abs(audio)) * 0.8
        
        audio_samples = [audio for _ in range(30)]
        
        voice_model = voice_cloner.enroll_voice(
            audio_samples=audio_samples,
            voice_id=f"voice_type_{i}",
            sample_rate=sample_rate
        )
        
        assert voice_model is not None
        assert voice_model.model_id == f"voice_type_{i}"


def test_incremental_learning_convergence(voice_cloner, sample_audio):
    """Test that incremental learning converges."""
    # Initial enrollment
    audio_samples = [sample_audio for _ in range(30)]
    initial_model = voice_cloner.enroll_voice(
        audio_samples=audio_samples,
        voice_id="test_convergence",
        sample_rate=16000
    )
    
    # Get initial profile
    initial_profile = voice_cloner._voice_profiles["test_convergence"]
    initial_features = initial_profile.features.copy()
    
    # Multiple updates with same audio
    for _ in range(5):
        voice_cloner.update_voice_model(
            voice_id="test_convergence",
            new_audio_samples=[sample_audio],
            sample_rate=16000
        )
    
    final_model = voice_cloner.get_voice_model("test_convergence")
    final_profile = voice_cloner._voice_profiles["test_convergence"]
    final_features = final_profile.features
    
    # Features should be similar (convergence)
    similarity = np.dot(initial_features, final_features) / (
        np.linalg.norm(initial_features) * np.linalg.norm(final_features)
    )
    
    assert similarity > 0.9  # Should be very similar


def test_voice_cloner_memory_efficiency(voice_cloner, sample_audio):
    """Test memory efficiency with many voices."""
    import gc
    
    # Enroll 10 voices
    audio_samples = [sample_audio for _ in range(30)]
    
    for i in range(10):
        voice_cloner.enroll_voice(
            audio_samples=audio_samples,
            voice_id=f"memory_test_{i}",
            sample_rate=16000
        )
    
    # Force garbage collection
    gc.collect()
    
    # Should have 10 voices
    assert len(voice_cloner.list_voices()) == 10
    
    # Delete all voices
    for i in range(10):
        voice_cloner.delete_voice(f"memory_test_{i}")
    
    # Should be empty
    assert len(voice_cloner.list_voices()) == 0
