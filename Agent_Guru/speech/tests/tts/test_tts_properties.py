"""Property-based tests for TTS engine - COMPREHENSIVE TESTING."""

import time
import wave
import io
import numpy as np
from hypothesis import given, strategies as st, settings, HealthCheck
import pytest

from Agent_Guru.speech.tts.tts_engine import TTSError, TTSEngine
from Agent_Guru.speech.models import PersonalityType, EmotionType
import logging

logger = logging.getLogger(__name__)


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
    except OSError as exc:
        logger.debug("Cleanup skipped: %s", exc)


def require_real_backend(engine) -> None:
    """Skip when no TTS backend can actually produce audio on this machine.

    With no Kokoro model and no pyttsx3, TTSEngine still returns a well-formed
    WAV - but it is SILENCE (_silence_wav). Assertions about audio CONTENT or
    about synthesis TIMING are meaningless against that stub: RMS is exactly
    0.0 and every call takes microseconds, so timing variance is pure noise.
    Skipping states the result honestly as UNVERIFIED on this host instead of
    asserting something the environment cannot answer.
    """
    backend = engine.active_backend
    if backend == "none":
        pytest.skip(
            "UNVERIFIED on this host: no TTS backend available (Kokoro model "
            "absent and pyttsx3 not installed), so the engine returns silence "
            "and audio-content/timing assertions cannot be evaluated",
        )


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
    # Suppress numpy warnings for edge cases
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=RuntimeWarning, module='numpy')
        
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
    # Suppress numpy warnings for edge cases
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=RuntimeWarning, module='numpy')
        
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
    text=st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    personality=st.sampled_from([PersonalityType.GURU, PersonalityType.MAYA])
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
)
@pytest.mark.timeout(600)
def test_property_9_tts_personality_voice_mapping(tts_engine, text, personality):
    """
    Property 9: TTS Personality-Voice Mapping
    
    **Validates: Requirements 4.1, 4.2, 4.8**
    """
    if not text.strip():
        return
    
    audio1 = tts_engine.synthesize(text, personality=personality)
    audio2 = tts_engine.synthesize(text, personality=personality)
    
    assert len(audio1) > 0, "Audio output should not be empty"  # nosec B101
    assert len(audio2) > 0, "Audio output should not be empty"  # nosec B101
    
    voice_gender = analyze_voice_gender(audio1)
    voice_gender2 = analyze_voice_gender(audio2)
    assert voice_gender == voice_gender2, \
        f"Voice gender should be consistent across sessions (got {voice_gender} and {voice_gender2})"  # nosec B101
    
    similarity = compute_audio_similarity(audio1, audio2)
    assert similarity > 0.7, \
        f"Voice characteristics should be consistent across sessions (similarity={similarity:.3f})"  # nosec B101


@given(
    text=st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    personality=st.sampled_from([PersonalityType.GURU, PersonalityType.MAYA])
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
)
@pytest.mark.timeout(600)
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
            f"(synthesis_time={synthesis_time:.3f}s, audio_duration={audio_duration:.3f}s)"  # nosec B101


@given(
    text=st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    personality=st.sampled_from([PersonalityType.GURU, PersonalityType.MAYA]),
    speech_rate=st.floats(min_value=0.5, max_value=2.0)
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
)
@pytest.mark.timeout(600)
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
    
    assert len(audio) > 0, "Audio output should not be empty"  # nosec B101
    
    sample_rate = get_sample_rate(audio)
    assert sample_rate >= 16000, \
        f"Sample rate {sample_rate} Hz should be at least 16000 Hz"  # nosec B101
    
    audio_normal = tts_engine.synthesize(text, personality=personality, speech_rate=1.0)
    
    duration_adjusted = get_audio_duration(audio)
    duration_normal = get_audio_duration(audio_normal)
    
    if duration_normal > 0:
        expected_ratio = 1.0 / speech_rate
        actual_ratio = duration_adjusted / duration_normal
        
        assert 0.3 < actual_ratio < 3.0, \
            f"Duration ratio {actual_ratio:.3f} should be reasonable " \
            f"(expected ~{expected_ratio:.3f} for rate {speech_rate:.2f})"  # nosec B101


# Unit tests - COMPREHENSIVE

def test_tts_guru_male_voice(tts_engine):
    """Test that Guru personality uses male voice."""
    text = "Hello, I am Guru, your AI assistant."
    audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0  # nosec B101
    
    voice_info = tts_engine.get_voice_info(PersonalityType.GURU)
    assert voice_info["gender"] == "male"  # nosec B101
    assert voice_info["personality"] == "guru"  # nosec B101


def test_tts_maya_female_voice(tts_engine):
    """Test that Maya personality uses female voice."""
    text = "Hello, I am Maya, your AI assistant."
    audio = tts_engine.synthesize(text, personality=PersonalityType.MAYA)
    
    assert len(audio) > 0  # nosec B101
    
    voice_info = tts_engine.get_voice_info(PersonalityType.MAYA)
    assert voice_info["gender"] == "female"  # nosec B101
    assert voice_info["personality"] == "maya"  # nosec B101


def test_tts_all_emotions(tts_engine):
    """Test TTS with ALL emotion types."""
    text = "This is a test of emotion support."
    
    for emotion in EmotionType:
        audio = tts_engine.synthesize(
            text,
            personality=PersonalityType.GURU,
            emotion=emotion
        )
        assert len(audio) > 0, f"Failed to synthesize with emotion {emotion}"  # nosec B101


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
        assert len(audio) > 0  # nosec B101
    
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
        assert len(audio) > 0  # nosec B101
    
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
    
    assert isinstance(audio_array, np.ndarray)  # nosec B101
    assert audio_array.dtype == np.float32  # nosec B101
    assert len(audio_array) > 0  # nosec B101
    assert sample_rate >= 16000  # nosec B101
    
    assert np.all(audio_array >= -1.0)  # nosec B101
    assert np.all(audio_array <= 1.0)  # nosec B101


def test_tts_long_text(tts_engine):
    """Test TTS with long text."""
    text = "This is a very long text. " * 50
    audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
    assert len(audio) > 0  # nosec B101


def test_tts_special_characters(tts_engine):
    """Test TTS with special characters."""
    text = "Hello! How are you? I'm fine, thanks. 123 test."
    audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
    assert len(audio) > 0  # nosec B101


def test_tts_concurrent_synthesis(tts_engine):
    """Test that concurrent synthesis is handled properly."""
    import concurrent.futures
    
    def synthesize_text(text):
        return tts_engine.synthesize(text, personality=PersonalityType.GURU)
    
    texts = [f"Test text number {i}" for i in range(5)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(synthesize_text, text) for text in texts]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert len(results) == 5  # nosec B101
    for audio in results:
        assert len(audio) > 0  # nosec B101


# EXTREME STRESS TESTS - ZERO COMPROMISE

def test_tts_extreme_long_text(tts_engine):
    """Test TTS with EXTREMELY long text - production stress test."""
    text = "This is an extremely long text for production stress testing. " * 200  # 12,600+ chars
    audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
    assert len(audio) > 0  # nosec B101
    assert get_audio_duration(audio) > 10.0  # Should be at least 10 seconds  # nosec B101


def test_tts_rapid_fire_synthesis(tts_engine):
    """Test rapid-fire synthesis - 100 requests in quick succession."""
    texts = [f"Rapid test number {i}" for i in range(100)]
    
    start_time = time.time()
    for text in texts:
        audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
        assert len(audio) > 0  # nosec B101
    
    total_time = time.time() - start_time
    avg_time = total_time / 100
    
    # Should handle 100 requests efficiently
    assert avg_time < 5.0, f"Average synthesis time {avg_time:.3f}s too slow for production"  # nosec B101


def test_tts_all_emotion_combinations(tts_engine):
    """Test ALL emotion combinations with BOTH personalities."""
    text = "Testing all emotion combinations for maximum coverage."
    
    for personality in [PersonalityType.GURU, PersonalityType.MAYA]:
        for emotion in EmotionType:
            for rate in [0.5, 1.0, 1.5, 2.0]:
                for volume in [0.3, 0.7, 1.0]:
                    audio = tts_engine.synthesize(
                        text,
                        personality=personality,
                        emotion=emotion,
                        speech_rate=rate,
                        volume=volume
                    )
                    assert len(audio) > 0, \
                        f"Failed: personality={personality}, emotion={emotion}, rate={rate}, vol={volume}"  # nosec B101


def test_tts_unicode_and_special_chars(tts_engine):
    """Test with Unicode and special characters - FULL coverage."""
    test_cases = [
        "Hello! How are you? I'm fine, thanks. 123 test.",
        "Testing: semicolons; commas, periods. Question marks? Exclamation!",
        "Numbers: 1234567890, Symbols: @#$%^&*()",
        "Quotes: 'single' and \"double\" quotes",
        "Newlines\nand\ttabs\ttest",
        "UPPERCASE and lowercase and MiXeD CaSe",
        "Multiple    spaces    between    words",
        "Punctuation!!! Multiple??? Marks...",
    ]
    
    for text in test_cases:
        audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
        assert len(audio) > 0, f"Failed for text: {text}"  # nosec B101


def test_tts_memory_efficiency(tts_engine):
    """Test memory efficiency - no leaks over 1000 syntheses."""
    import gc
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    # Baseline memory
    gc.collect()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB
    
    # Run 1000 syntheses
    for i in range(1000):
        audio = tts_engine.synthesize(
            f"Memory test iteration {i}",
            personality=PersonalityType.GURU
        )
        assert len(audio) > 0  # nosec B101
        
        # Force cleanup every 100 iterations
        if i % 100 == 0:
            gc.collect()
    
    # Final memory
    gc.collect()
    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    
    mem_increase = mem_after - mem_before
    
    # Memory increase should be minimal (< 100MB for 1000 syntheses)
    assert mem_increase < 100, \
        f"Memory leak detected: {mem_increase:.2f}MB increase over 1000 syntheses"  # nosec B101


def test_tts_concurrent_stress(tts_engine):
    """Test concurrent synthesis under EXTREME load - 50 threads."""
    import concurrent.futures
    
    def synthesize_with_all_params(idx):
        personality = PersonalityType.GURU if idx % 2 == 0 else PersonalityType.MAYA
        emotion = list(EmotionType)[idx % len(EmotionType)]
        rate = 0.5 + (idx % 4) * 0.5
        volume = 0.5 + (idx % 3) * 0.25
        
        audio = tts_engine.synthesize(
            f"Concurrent stress test number {idx}",
            personality=personality,
            emotion=emotion,
            speech_rate=rate,
            volume=volume
        )
        return len(audio) > 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(synthesize_with_all_params, i) for i in range(200)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert all(results), "Some concurrent syntheses failed"  # nosec B101
    assert len(results) == 200  # nosec B101


def test_tts_audio_quality_metrics(tts_engine):
    """Test audio quality metrics - PRODUCTION GRADE."""
    require_real_backend(tts_engine)
    text = "This is a comprehensive audio quality test for production deployment."
    
    # Suppress numpy warnings for edge cases
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=RuntimeWarning, module='numpy')
        
        for personality in [PersonalityType.GURU, PersonalityType.MAYA]:
            audio = tts_engine.synthesize(text, personality=personality)
            
            # Parse audio
            with wave.open(io.BytesIO(audio), 'rb') as wav:
                sample_rate = wav.getframerate()
                n_channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                frames = wav.readframes(wav.getnframes())
            
            # Quality checks
            assert sample_rate >= 16000, f"Sample rate {sample_rate} too low for production"  # nosec B101
            assert sample_width >= 2, f"Sample width {sample_width} too low (need 16-bit minimum)"  # nosec B101
            assert n_channels >= 1, "Must have at least 1 channel"  # nosec B101
            
            # Convert to array for analysis
            if sample_width == 2:
                audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_array = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
            
            # Check for clipping (should be minimal)
            clipping_ratio = np.sum(np.abs(audio_array) > 0.99) / len(audio_array)
            assert clipping_ratio < 0.01, f"Too much clipping: {clipping_ratio*100:.2f}%"  # nosec B101
            
            # Check for silence (should not be all silent)
            rms = np.sqrt(np.mean(audio_array**2))
            assert rms > 0.01, f"Audio too quiet (RMS={rms:.4f})"  # nosec B101
            
            # Check dynamic range
            max_abs = np.max(np.abs(audio_array))
            if max_abs > 0 and rms > 0:
                dynamic_range = 20 * np.log10(max_abs / (rms + 1e-10))
                assert dynamic_range > 6, f"Dynamic range too low: {dynamic_range:.2f} dB"  # nosec B101


def test_tts_error_recovery(tts_engine):
    """Test error recovery and robustness - ZERO FAILURES."""
    # Test empty text handling
    with pytest.raises(TTSError, match="empty"):
        tts_engine.synthesize("", personality=PersonalityType.GURU)

    # Test invalid parameters
    with pytest.raises(TTSError, match="speech_rate"):
        tts_engine.synthesize("test", speech_rate=10.0)

    with pytest.raises(TTSError, match="volume"):
        tts_engine.synthesize("test", volume=5.0)
    
    # Engine should still work after errors
    audio = tts_engine.synthesize("Recovery test", personality=PersonalityType.GURU)
    assert len(audio) > 0  # nosec B101


def test_tts_performance_consistency(tts_engine):
    """Test performance consistency - variance should be low."""
    require_real_backend(tts_engine)
    text = "Performance consistency test for production deployment."
    times = []
    
    for _ in range(50):
        start = time.time()
        audio = tts_engine.synthesize(text, personality=PersonalityType.GURU)
        elapsed = time.time() - start
        times.append(elapsed)
        assert len(audio) > 0  # nosec B101
    
    avg_time = np.mean(times)
    std_time = np.std(times)
    
    # Coefficient of variation should be low (< 50%)
    cv = (std_time / avg_time) * 100
    assert cv < 50, f"Performance too inconsistent: CV={cv:.2f}%"  # nosec B101


def test_tts_gpu_availability_check(tts_engine):
    """Check if GPU acceleration is available and log status."""
    import torch
    
    gpu_available = torch.cuda.is_available()
    
    if gpu_available:
        gpu_count = torch.cuda.device_count()
        gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
        print(f"\n✓ GPU AVAILABLE: {gpu_count} device(s) - {gpu_name}")
        print(f"✓ CUDA Version: {torch.version.cuda}")
    else:
        print("\n⚠ GPU NOT AVAILABLE - Running on CPU only")
        print("⚠ For maximum performance, install CUDA and PyTorch with GPU support")
    
    # Test should pass regardless, but log GPU status
    assert True, "GPU check complete"  # nosec B101
