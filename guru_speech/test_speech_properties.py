"""
Property-based tests for WhisperTranscriber module.

This module contains property tests that verify universal correctness properties
of the speech transcription functionality.
"""

import numpy as np
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from .speech import WhisperTranscriber
from .models import TranscriptionResult


# Strategy for generating valid sample rates
sample_rates = st.sampled_from([8000, 16000, 22050, 44100, 48000])

# Strategy for generating valid audio data
# Audio values should be in range [-1.0, 1.0] for normalized audio
# Generate arrays with smaller sizes for faster testing (0.1 to 2 seconds)
def audio_array_strategy(sample_rate):
    """Generate audio arrays based on sample rate."""
    min_samples = int(sample_rate * 0.1)  # 0.1 seconds
    max_samples = int(sample_rate * 2.0)   # 2 seconds
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
def test_transcription_result_completeness(sample_rate, data):
    """
    Feature: guru-speech-engine, Property 1: Transcription Result Completeness
    
    For any valid audio input, transcription should return a TranscriptionResult 
    containing non-empty text, a valid language code, a confidence score between 
    0.0 and 1.0, and a non-negative duration.
    
    **Validates: Requirements 1.4, 7.1, 7.2**
    
    This property verifies that:
    1. Result is a TranscriptionResult instance
    2. Text field is a string (may be empty for silent audio)
    3. Language is a valid language code string
    4. Confidence is between 0.0 and 1.0
    5. Duration is non-negative
    6. Segments list exists (may be empty)
    """
    # Generate audio data based on sample rate
    audio_data = data.draw(audio_array_strategy(sample_rate))
    
    # Create transcriber (using tiny model for faster testing)
    transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
    
    # Transcribe audio
    result = transcriber.transcribe(audio_data, sample_rate)
    
    # Property assertions
    
    # 1. Result must be a TranscriptionResult instance
    assert isinstance(result, TranscriptionResult), \
        "Result must be a TranscriptionResult instance"
    
    # 2. Text must be a string (can be empty for silent/unintelligible audio)
    assert isinstance(result.text, str), \
        "Text field must be a string"
    assert result.text is not None, \
        "Text field must not be None"
    
    # 3. Language must be a valid string
    assert isinstance(result.language, str), \
        "Language field must be a string"
    assert len(result.language) > 0, \
        "Language field must not be empty"
    # Language should be a valid code (typically 2-3 characters) or "unknown"
    assert len(result.language) <= 10, \
        f"Language code '{result.language}' seems invalid (too long)"
    
    # 4. Confidence must be between 0.0 and 1.0
    assert isinstance(result.confidence, (int, float)), \
        "Confidence must be a numeric value"
    assert 0.0 <= result.confidence <= 1.0, \
        f"Confidence {result.confidence} must be between 0.0 and 1.0"
    
    # 5. Duration must be non-negative
    assert isinstance(result.duration, (int, float)), \
        "Duration must be a numeric value"
    assert result.duration >= 0.0, \
        f"Duration {result.duration} must be non-negative"
    
    # 6. Segments must be a list
    assert isinstance(result.segments, list), \
        "Segments must be a list"
    
    # 7. Verify duration matches expected duration from audio length
    expected_duration = len(audio_data) / sample_rate
    # Allow small tolerance for rounding
    assert abs(result.duration - expected_duration) < 0.1, \
        f"Duration {result.duration} should be close to expected {expected_duration}"


@settings(
    max_examples=50, 
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example, HealthCheck.data_too_large]
)
@given(
    sample_rate=sample_rates,
    language=st.sampled_from(["en", "hi", "pa", None]),
    data=st.data()
)
def test_transcription_result_language_handling(sample_rate, language, data):
    """
    Feature: guru-speech-engine, Property 1: Transcription Result Completeness (Language)
    
    For any valid audio input with specified or auto-detected language, 
    transcription should return a complete result with proper language handling.
    
    **Validates: Requirements 7.1, 7.2**
    
    This property verifies that:
    1. When language is specified, it's respected or a valid alternative is returned
    2. When language is None, auto-detection provides a valid language code
    3. All other result fields remain complete and valid
    """
    # Generate audio data
    audio_data = data.draw(audio_array_strategy(sample_rate))
    
    # Create transcriber
    transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
    
    # Transcribe with specified or auto-detected language
    result = transcriber.transcribe(audio_data, sample_rate, language=language)
    
    # Property assertions
    
    # Result must be complete
    assert isinstance(result, TranscriptionResult), \
        "Result must be a TranscriptionResult instance"
    
    # Language must be valid
    assert isinstance(result.language, str), \
        "Language must be a string"
    assert len(result.language) > 0, \
        "Language must not be empty"
    
    # If language was specified, result should have a valid language
    # (may not match exactly due to auto-detection, but should be valid)
    if language is not None:
        assert result.language in ["en", "hi", "pa", "unknown"] or len(result.language) == 2, \
            f"Language '{result.language}' should be valid when specified as '{language}'"
    
    # All other fields must be complete
    assert isinstance(result.text, str), "Text must be a string"
    assert 0.0 <= result.confidence <= 1.0, "Confidence must be in [0.0, 1.0]"
    assert result.duration >= 0.0, "Duration must be non-negative"
    assert isinstance(result.segments, list), "Segments must be a list"


@settings(
    max_examples=50, 
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.large_base_example, HealthCheck.data_too_large]
)
@given(
    sample_rate=sample_rates,
    data=st.data()
)
def test_transcription_segments_completeness(sample_rate, data):
    """
    Feature: guru-speech-engine, Property 1: Transcription Result Completeness (Segments)
    
    For any valid audio input, if segments are present in the transcription result,
    each segment should be complete with valid timing and text information.
    
    **Validates: Requirements 1.4**
    
    This property verifies that:
    1. Each segment has valid text, start, end, and confidence
    2. Segment timing is logical (start < end, within audio duration)
    3. Segments are ordered chronologically
    """
    # Generate audio data
    audio_data = data.draw(audio_array_strategy(sample_rate))
    
    # Create transcriber
    transcriber = WhisperTranscriber(model_size="tiny", compute_type="int8", beam_size=5)
    
    # Transcribe audio
    result = transcriber.transcribe(audio_data, sample_rate)
    
    # If there are segments, verify their completeness
    if len(result.segments) > 0:
        for i, segment in enumerate(result.segments):
            # Each segment must have valid fields
            assert isinstance(segment.text, str), \
                f"Segment {i} text must be a string"
            
            assert isinstance(segment.start, (int, float)), \
                f"Segment {i} start must be numeric"
            assert segment.start >= 0.0, \
                f"Segment {i} start must be non-negative"
            
            assert isinstance(segment.end, (int, float)), \
                f"Segment {i} end must be numeric"
            assert segment.end >= segment.start, \
                f"Segment {i} end must be >= start"
            
            assert isinstance(segment.confidence, (int, float)), \
                f"Segment {i} confidence must be numeric"
            
            # Segment timing should be reasonable (Whisper may pad segments slightly)
            # Allow up to 2 seconds of padding for very short audio clips
            assert segment.end <= result.duration + 2.0, \
                f"Segment {i} end {segment.end} should not greatly exceed audio duration {result.duration}"
        
        # Segments should be chronologically ordered
        for i in range(len(result.segments) - 1):
            assert result.segments[i].start <= result.segments[i + 1].start, \
                f"Segments should be chronologically ordered (segment {i} vs {i+1})"
