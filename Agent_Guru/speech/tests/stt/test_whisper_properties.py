"""Property-based tests for Whisper STT transcriber."""

import numpy as np
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from Agent_Guru.speech.stt.whisper_stt import WhisperTranscriber
from Agent_Guru.speech.models import TranscriptionResult


# Common settings for all property tests
COMMON_SETTINGS = settings(
    max_examples=10,
    deadline=30000,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        HealthCheck.large_base_example
    ]
)

PERFORMANCE_SETTINGS = settings(
    max_examples=5,
    deadline=60000,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        HealthCheck.large_base_example
    ]
)


# Custom strategies for audio generation
@st.composite
def audio_array(draw, min_duration=0.1, max_duration=5.0, sample_rate=16000):
    """Generate random audio arrays using numpy."""
    duration = draw(st.floats(min_value=min_duration, max_value=max_duration))
    samples = int(sample_rate * duration)
    assume(samples > 0)
    
    # Generate audio with reasonable amplitude using numpy
    # Use a seed for reproducibility within each test
    seed = draw(st.integers(min_value=0, max_value=2**31-1))
    rng = np.random.RandomState(seed)
    audio = rng.uniform(-0.5, 0.5, size=samples).astype(np.float32)
    
    return audio, sample_rate


@st.composite
def language_code(draw):
    """Generate valid language codes."""
    languages = ["en", "es", "fr", "de", "zh", "ja", "hi", "pa"]
    return draw(st.sampled_from(languages))


class TestWhisperSTTProperties:
    """Property-based tests for Whisper STT."""
    
    @pytest.fixture(scope="class")
    def transcriber(self):
        """Create a shared WhisperTranscriber instance."""
        return WhisperTranscriber(model_size="tiny", device="cpu")
    
    @COMMON_SETTINGS
    @given(audio_data=audio_array())
    def test_property_4_transcription_completeness(self, transcriber, audio_data):
        """
        **Property 4: STT Transcription Completeness**
        **Validates: Requirements 2.1, 2.14**
        
        For all valid audio inputs, transcription SHALL return a complete
        TranscriptionResult with all required fields populated.
        """
        audio, sample_rate = audio_data
        
        result = transcriber.transcribe(audio, sample_rate)
        
        # Verify result is complete
        assert isinstance(result, TranscriptionResult)
        assert result.text is not None
        assert isinstance(result.text, str)
        assert result.language is not None
        assert isinstance(result.language, str)
        assert result.confidence is not None
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
        assert result.segments is not None
        assert isinstance(result.segments, list)
        assert result.duration >= 0.0
    
    @PERFORMANCE_SETTINGS
    @given(
        duration=st.floats(min_value=1.0, max_value=10.0),
        sample_rate=st.sampled_from([16000, 22050, 44100])
    )
    def test_property_5_stt_real_time_performance(self, transcriber, duration, sample_rate):
        """
        **Property 5: STT Real-Time Performance**
        **Validates: Requirements 2.2, 2.11**
        
        For all audio inputs, the real-time factor (processing_time / audio_duration)
        SHALL be less than 0.5 on production hardware.
        
        Note: This test uses a lenient threshold for CI environments.
        """
        import time
        
        samples = int(sample_rate * duration)
        audio = np.random.randn(samples).astype(np.float32) * 0.1
        
        start_time = time.time()
        result = transcriber.transcribe(audio, sample_rate)
        processing_time = time.time() - start_time
        
        rtf = processing_time / duration
        
        # Verify transcription completed
        assert isinstance(result, TranscriptionResult)
        
        # Real-time factor should be < 0.5 on production hardware
        # Using lenient threshold for CI (< 5.0)
        assert rtf < 5.0, f"RTF {rtf:.2f} exceeds threshold (target: <0.5 on production)"
    
    @COMMON_SETTINGS
    @given(audio_data=audio_array())
    def test_property_6_stt_output_format(self, transcriber, audio_data):
        """
        **Property 6: STT Output Format**
        **Validates: Requirements 2.3**
        
        For all transcriptions, the output SHALL include proper punctuation
        and capitalization where appropriate.
        """
        audio, sample_rate = audio_data
        
        result = transcriber.transcribe(audio, sample_rate)
        
        # Verify output format
        assert isinstance(result, TranscriptionResult)
        assert isinstance(result.text, str)
        
        # If text is not empty, verify it's properly formatted
        if result.text.strip():
            # Text should not have excessive whitespace
            assert not result.text.startswith(" ")
            assert not result.text.endswith(" ")
            assert "  " not in result.text  # No double spaces
    
    @COMMON_SETTINGS
    @given(audio_data=audio_array())
    def test_property_7_speaker_diarization_completeness(self, transcriber, audio_data):
        """
        **Property 7: Speaker Diarization Completeness**
        **Validates: Requirements 2.5**
        
        When speaker diarization is enabled, all segments SHALL have
        speaker information (even if speaker_id is None for single speaker).
        """
        audio, sample_rate = audio_data
        
        result = transcriber.transcribe_with_diarization(audio, sample_rate)
        
        # Verify diarization result structure
        assert isinstance(result, TranscriptionResult)
        assert isinstance(result.segments, list)
        
        # All segments should have speaker_id field (even if None)
        for segment in result.segments:
            assert hasattr(segment, 'speaker_id')
            # speaker_id can be None, int, or any valid identifier
            assert segment.speaker_id is None or isinstance(segment.speaker_id, (int, str))
    
    @COMMON_SETTINGS
    @given(
        audio_data=audio_array(),
        lang=language_code()
    )
    def test_language_consistency(self, transcriber, audio_data, lang):
        """
        Test that specified language is respected in transcription.
        
        When a language is specified, the result SHALL use that language.
        """
        audio, sample_rate = audio_data
        
        result = transcriber.transcribe(audio, sample_rate, language=lang)
        
        assert isinstance(result, TranscriptionResult)
        assert result.language == lang
    
    @COMMON_SETTINGS
    @given(audio_data=audio_array())
    def test_segments_temporal_consistency(self, transcriber, audio_data):
        """
        Test that segment timestamps are temporally consistent.
        
        For all segments, start_time SHALL be <= end_time, and segments
        SHALL be ordered chronologically.
        """
        audio, sample_rate = audio_data
        
        result = transcriber.transcribe(audio, sample_rate)
        
        assert isinstance(result, TranscriptionResult)
        
        # Check each segment's temporal consistency
        for segment in result.segments:
            assert segment.start_time <= segment.end_time
            assert segment.start_time >= 0.0
        
        # Check segments are ordered chronologically
        for i in range(len(result.segments) - 1):
            assert result.segments[i].end_time <= result.segments[i + 1].start_time
    
    @COMMON_SETTINGS
    @given(
        audio_data=audio_array(),
        dtype=st.sampled_from([np.float32, np.float64, np.int16, np.int32])
    )
    def test_audio_dtype_handling(self, transcriber, audio_data, dtype):
        """
        Test that transcriber handles different audio dtypes correctly.
        
        For all supported dtypes, transcription SHALL succeed and return
        valid results.
        """
        audio, sample_rate = audio_data
        
        # Convert to target dtype
        if dtype in [np.int16, np.int32]:
            # Scale to integer range
            max_val = np.iinfo(dtype).max
            audio_converted = (audio * max_val).astype(dtype)
        else:
            audio_converted = audio.astype(dtype)
        
        result = transcriber.transcribe(audio_converted, sample_rate)
        
        assert isinstance(result, TranscriptionResult)
        assert result.text is not None
        assert result.language is not None
    
    @COMMON_SETTINGS
    @given(
        sample_rate=st.sampled_from([8000, 16000, 22050, 44100, 48000])
    )
    def test_sample_rate_handling(self, transcriber, sample_rate):
        """
        Test that transcriber handles different sample rates correctly.
        
        For all common sample rates, transcription SHALL succeed.
        """
        duration = 1.0
        samples = int(sample_rate * duration)
        audio = np.random.randn(samples).astype(np.float32) * 0.1
        
        result = transcriber.transcribe(audio, sample_rate)
        
        assert isinstance(result, TranscriptionResult)
        assert result.duration > 0
    
    @COMMON_SETTINGS
    @given(audio_data=audio_array())
    def test_confidence_bounds(self, transcriber, audio_data):
        """
        Test that confidence scores are properly bounded.
        
        For all transcriptions, confidence scores SHALL be in [0.0, 1.0].
        """
        audio, sample_rate = audio_data
        
        result = transcriber.transcribe(audio, sample_rate)
        
        assert isinstance(result, TranscriptionResult)
        assert 0.0 <= result.confidence <= 1.0
        
        # Check segment confidences
        for segment in result.segments:
            assert 0.0 <= segment.confidence <= 1.0
    
    @COMMON_SETTINGS
    @given(audio_data=audio_array())
    def test_idempotency(self, transcriber, audio_data):
        """
        Test that transcription is deterministic (idempotent).
        
        For the same audio input, transcription SHALL produce consistent results.
        """
        audio, sample_rate = audio_data
        
        result1 = transcriber.transcribe(audio, sample_rate)
        result2 = transcriber.transcribe(audio, sample_rate)
        
        # Results should be identical
        assert result1.text == result2.text
        assert result1.language == result2.language
        assert len(result1.segments) == len(result2.segments)
