"""Property-based tests for TTS engine - COMPREHENSIVE TESTING."""

import time
import wave
import io
import numpy as np
from hypothesis import given, strategies as st, settings, HealthCheck
import pytest

from Agent_Guru.speech.tts.tts_engine import TTSEngine
from Agent_Guru.speech.models import PersonalityType, EmotionType


# Shared TTS engine fixture - module scope for performance
@pytest.fixture(scope="module")
def tts_engine():
    """Create a TTS engine for all tests in module."""
    engine = TTSEngine()
    yield engine
    # Cleanup
    try:
        if hasattr(engine, 'engine') and engine.engine:
            del engine.engine
    except:
        pass


# Helper functions

def analyze_voice_gender(audio_bytes: bytes) -> str:
    """
    Analyze audio to determine voice gender based on pitch.
    
    Male voices typically have lower pitch (85-180 Hz)
    Female voices typically have higher pitch (165-255 Hz)
    
    Args:
        audio_bytes: WAV audio data
        
    Returns:
        "male" or "female"
    """
    with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())
        sample_width = wav_file.getsampwidth()
        
        # Convert to numpy array
        if sample_width == 2:
            audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_array = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
    
    if len(audio_array) < sample_rate:
        return "male"
    
    segment = audio_array[:sample_rate]
    autocorr = np.correlate(segment, segment, mode='full')
    autocorr = autocorr[len(autocorr)//2:]
    
    min_lag = int(sample_rate / 400)
    max_lag = int(sample_rate / 50)
    
    if max_lag >= len(autocorr):
        return "male"
    
    peak_lag = np.argmax(autocorr[min_lag:max_lag]) + min_lag
    
    if peak_lag == 0:
        return "male"
    
    f0 = sample_rate / peak_lag
    
    return "male" if f0 < 150 else "female"


def compute_audio_similarity(audio1: bytes, audio2: bytes) -> float:
    """Compute similarity between two audio samples."""
    with wave.open(io.BytesIO(audio1), 'rb') as wav1:
        frames1 = wav1.readframes(wav1.getnframes())
        width1 = wav1.getsampwidth()
    
    with wave.open(io.BytesIO(audio2), 'rb') as wav2:
        frames2 = wav2.readframes(wav2.getnframes())
        width2 = wav2.getsampwidth()
    
    if width1 == 2:
        arr1 = np.frombuffer(frames1, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        arr1 = np.frombuffer(frames1, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
    
    if width2 == 2:
        arr2 = np.frombuffer(frames2, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        arr2 = np.frombuffer(frames2, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
    
    max_len = max(len(arr1), len(arr2))
    arr1_padded = np.pad(arr1, (0, max_len - len(arr1)))
    arr2_padded = np.pad(arr2, (0, max_len - len(arr2)))
    
    correlation = np.corrcoef(arr1_padded, arr2_padded)[0, 1]
    
    if np.isnan(correlation):
        return 1.0
    
    return (correlation + 1.0) / 2.0


def get_audio_duration(audio_bytes: bytes) -> float:
    """Get duration of audio in seconds."""
    with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        return frames / float(rate)


def get_sample_rate(audio_bytes: bytes) -> int:
    """Get sample rate of audio."""
    with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
        return wav_file.getframerate()


# Property Tests - MAXIMUM COVERAGE

@given(
    text=st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    personality=st.sampled_from([PersonalityType.GURU, PersonalityType.MAYA])
)
@settings(
    max_examples=10,
    deadline=60000,
    suppress_health_check=[HealthCheck.too_slow]
)
@pytest.mark.timeout(120)
def test_property_9_tts_personality_voice_mapping(tts_engine, text, personality):
    """
    Property 9: TTS Personality-Voice Mapping
    
    **Validates: Requirements 4.1, 4.2, 4.8**
    """
    if not text.strip():
        return
    
    audio1 = tts_engine.synthesize(text, personality=personality)
    audio2 = tts_engine.synthesize(text, personality=personality)
    
    assert len(audio1) > 0, "Audio output should not be empty"
    assert len(audio2) > 0, "Audio output should not be empty"
    
    voice_gender = analyze_voice_gender(audio1)
    voice_gender2 = analyze_voice_gender(audio2)
    assert voice_gender == voice_gender2, \
        f"Voice gender should be consistent across sessions (got {voice_gender} and {voice_gender2})"
    
    similarity = compute_audio_similarity(audio1, audio2)
    assert similarity > 0.7, \
        f"Voice characteristics should be consistent across sessions (similarity={similarity:.3f})"


@given(
    text=st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    personality=st.sampled_from([PersonalityType.GURU, PersonalityType.MAYA])
)
@settings(
    max_examples=10,
    deadline=60000,
    suppress_health_check=[HealthCheck.too_slow]
)
@pytest.mark.timeout(120)
def test_property_10_tts_real_time_performance(tts_engine, text, personality):
    """
    Property 10: TTS Real-Time Performance
    
    **Validates: Requirements 4.3, 4.19**
    """
    if not text.strip():
        return
    
    start_time = time.time()
    audio = tts_engine.synthesize(text, personality=personality)
    synthesis_time = time.time() - start_time
    
    audio_duration = get_audio_duration(audio)
    
    if audio_duration > 0:
        real_time_factor = synthesis_time / audio_duration
        assert real_time_factor < 1.0, \
            f"Real-time factor {real_time_factor:.3f} should be below 1.0 " \
            f"(synthesis_time={synthesis_time:.3f}s, audio_duration={audio_duration:.3f}s)"


@given(
    text=st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    personality=st.sampled_from([PersonalityType.GURU, PersonalityType.MAYA]),
    speech_rate=st.floats(min_value=0.5, max_value=2.0)
)
@settings(
    max_examples=10,
    deadline=60000,
    suppress_health_check=[HealthCheck.too_slow]
)
@pytest.mark.timeout(120)
def test_property_11_tts_output_format(tts_engine, text, personality, speech_rate):
    """
    Property 11: TTS Output Format
    
    **Validates: Requirements 4.7, 4.24**
    """
    if not text.strip():
        return
    
    audio = tts_engine.synthesize(
        text,
        personality=personality,
        speech_rate=speech_rate
    )
    
    assert len(audio) > 0, "Audio output should not be empty"
    
    sample_rate = get_sample_rate(audio)
    assert sample_rate >= 16000, \
        f"Sample rate {sample_rate} Hz should be at least 16000 Hz"
    
    audio_normal = tts_engine.synthesize(text, personality=personality, speech_rate=1.0)
    
    duration_adjusted = get_audio_duration(audio)
    duration_normal = get_audio_duration(audio_normal)
    
    if duration_normal > 0:
        expected_ratio = 1.0 / speech_rate
        actual_ratio = duration_adjusted / duration_normal
        
        assert 0.3 < actual_ratio < 3.0, \
            f"Duration ratio {actual_ratio:.3f} should be reasonable " \
            f"(expected ~{expected_ratio:.3f} for rate {speech_rate:.2f})"


# Unit tests - COMPREHENSIVE

def test_tts_guru_male_voice(tts_engine):
    """Test that Guru personality uses male voice."""
    text = "Hello, I am Guru, your AI assistant."
    audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0
    
    voice_info = tts_engine.get_voice_info(PersonalityType.GURU)
    assert voice_info["gender"] == "male"
    assert voice_info["personality"] == "guru"


def test_tts_maya_female_voice(tts_engine):
    """Test that Maya personality uses female voice."""
    text = "Hello, I am Maya, your AI assistant."
    audio = tts_engine.synthesize(text, personality=PersonalityType.MAYA)
    
    assert len(audio) > 0
    
    voice_info = tts_engine.get_voice_info(PersonalityType.MAYA)
    assert voice_info["gender"] == "female"
    assert voice_info["personality"] == "maya"


def test_tts_all_emotions(tts_engine):
    """Test TTS with ALL emotion types."""
    text = "This is a test of emotion support."
    
    for emotion in EmotionType:
        audio = tts_engine.synthesize(
            text,
            personality=PersonalityType.GURU,
            emotion=emotion
        )
        assert len(audio) > 0, f"Failed to synthesize with emotion {emotion}"


def test_tts_speech_rate_bounds(tts_engine):
    """Test that speech rate is clamped to valid range."""
    text = "Testing speech rate bounds."
    
    # Valid rates
    for rate in [0.5, 1.0, 1.5, 2.0]:
        audio = tts_engine.synthesize(
            text,
            personality=PersonalityType.GURU,
            speech_rate=rate
        )
        assert len(audio) > 0
    
    # Invalid rates
    with pytest.raises(Exception):
        tts_engine.synthesize(text, speech_rate=0.3)
    
    with pytest.raises(Exception):
        tts_engine.synthesize(text, speech_rate=2.5)


def test_tts_volume_bounds(tts_engine):
    """Test volume parameter bounds."""
    text = "Testing volume."
    
    # Valid volumes
    for vol in [0.0, 0.5, 1.0]:
        audio = tts_engine.synthesize(text, volume=vol)
        assert len(audio) > 0
    
    # Invalid volumes
    with pytest.raises(Exception):
        tts_engine.synthesize(text, volume=-0.1)
    
    with pytest.raises(Exception):
        tts_engine.synthesize(text, volume=1.1)


def test_tts_empty_text(tts_engine):
    """Test that empty text raises error."""
    with pytest.raises(Exception):
        tts_engine.synthesize("", personality=PersonalityType.GURU)
    
    with pytest.raises(Exception):
        tts_engine.synthesize("   ", personality=PersonalityType.GURU)


def test_tts_synthesize_to_array(tts_engine):
    """Test synthesize_to_array method."""
    text = "Testing array output."
    audio_array, sample_rate = tts_engine.synthesize_to_array(
        text,
        personality=PersonalityType.GURU
    )
    
    assert isinstance(audio_array, np.ndarray)
    assert audio_array.dtype == np.float32
    assert len(audio_array) > 0
    assert sample_rate >= 16000
    
    assert np.all(audio_array >= -1.0)
    assert np.all(audio_array <= 1.0)


def test_tts_long_text(tts_engine):
    """Test TTS with long text."""
    text = "This is a very long text. " * 50
    audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
    assert len(audio) > 0


def test_tts_special_characters(tts_engine):
    """Test TTS with special characters."""
    text = "Hello! How are you? I'm fine, thanks. 123 test."
    audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
    assert len(audio) > 0


def test_tts_concurrent_synthesis(tts_engine):
    """Test that concurrent synthesis is handled properly."""
    import concurrent.futures
    
    def synthesize_text(text):
        return tts_engine.synthesize(text, personality=PersonalityType.GURU)
    
    texts = [f"Test text number {i}" for i in range(5)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(synthesize_text, text) for text in texts]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert len(results) == 5
    for audio in results:
        assert len(audio) > 0
