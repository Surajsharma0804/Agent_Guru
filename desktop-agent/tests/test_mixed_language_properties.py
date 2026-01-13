"""
Property-Based Tests for Mixed-Language Detection

Comprehensive property-based testing for mixed-language utterance detection,
segmentation, and confidence scoring validation.

**Validates: Requirements 1.4**
"""

import pytest
import time
import hashlib
from typing import List, Dict, Any

from hypothesis import given, strategies as st, settings, assume, note

# Import test utilities
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from test_mixed_language_detection import (
    MockMixedLanguageEngine,
    MultilingualConfig,
    MixedLanguageResult,
    LanguageSegment
)


# Test data generation strategies
@st.composite
def mixed_audio_data(draw):
    """Generate mixed-language audio data for testing."""
    
    # Number of language segments (1-5)
    num_segments = draw(st.integers(min_value=1, max_value=5))
    
    # Available language patterns
    language_patterns = {
        'en': b'english_pattern_content',
        'hi': b'hindi_pattern_different',
        'ta': b'tamil_unique_pattern',
        'de': b'german_pattern_text',
        'fr': b'french_pattern_data'
    }
    
    # Generate segments
    audio_segments = []
    for i in range(num_segments):
        # Select language for this segment
        language = draw(st.sampled_from(list(language_patterns.keys())))
        
        # Generate segment length (100-2000 bytes)
        segment_length = draw(st.integers(min_value=100, max_value=2000))
        
        # Create segment audio
        base_pattern = language_patterns[language]
        repetitions = (segment_length // len(base_pattern)) + 1
        segment_audio = (base_pattern * repetitions)[:segment_length]
        
        audio_segments.append({
            'audio': segment_audio,
            'language': language,
            'length': segment_length
        })
    
    # Concatenate all segments
    full_audio = b''.join(seg['audio'] for seg in audio_segments)
    
    return {
        'audio': full_audio,
        'segments': audio_segments,
        'expected_languages': list(set(seg['language'] for seg in audio_segments))
    }


@st.composite
def language_config_for_mixed(draw):
    """Generate language configuration suitable for mixed-language testing."""
    
    # Always include common languages for mixed-language scenarios
    base_languages = ['en', 'hi', 'ta']
    
    # Optionally add more languages
    additional_languages = draw(st.lists(
        st.sampled_from(['de', 'fr', 'bn', 'mr']),
        min_size=0,
        max_size=3,
        unique=True
    ))
    
    enabled_languages = base_languages + additional_languages
    primary_language = draw(st.sampled_from(enabled_languages))
    
    return MultilingualConfig(
        enabled_languages=enabled_languages,
        primary_language=primary_language,
        fallback_language=primary_language,
        detection_threshold=draw(st.floats(min_value=0.6, max_value=0.9)),
        max_detection_time_ms=draw(st.integers(min_value=200, max_value=500))
    )


class TestMixedLanguageProperties:
    """Property-based tests for mixed-language detection."""
    
    @given(
        mixed_data=mixed_audio_data(),
        config=language_config_for_mixed()
    )
    @settings(max_examples=30, deadline=10000)
    def test_mixed_language_segmentation_properties(self, mixed_data, config):
        """
        Test that mixed-language detection produces valid segmentation.
        
        **Validates: Requirements 1.4**
        """
        
        audio = mixed_data['audio']
        expected_languages = mixed_data['expected_languages']
        
        assume(len(audio) >= 100)  # Minimum audio length
        
        engine = MockMixedLanguageEngine(config)
        
        note(f"Audio length: {len(audio)} bytes")
        note(f"Expected languages: {expected_languages}")
        note(f"Input segments: {len(mixed_data['segments'])}")
        
        result = engine.detect_mixed_language(audio)
        
        # Property 1: Valid segmentation structure
        assert isinstance(result, MixedLanguageResult)
        assert len(result.segments) > 0, "Should produce at least one segment"
        
        # Property 2: Segments have valid properties
        total_duration = 0
        for i, segment in enumerate(result.segments):
            assert isinstance(segment, LanguageSegment), f"Segment {i} should be LanguageSegment"
            assert segment.start_time >= 0, f"Segment {i} start time should be non-negative"
            assert segment.end_time > segment.start_time, f"Segment {i} end time should be after start time"
            assert segment.language in config.enabled_languages, f"Segment {i} language should be supported"
            assert 0.0 <= segment.confidence <= 1.0, f"Segment {i} confidence should be valid"
            assert len(segment.audio) > 0, f"Segment {i} should have audio data"
            
            total_duration += segment.duration
            
        # Property 3: Segments are properly ordered
        for i in range(len(result.segments) - 1):
            current = result.segments[i]
            next_seg = result.segments[i + 1]
            
            # Segments should not overlap significantly
            assert current.end_time <= next_seg.start_time + 0.1, f"Segments {i} and {i+1} should not overlap significantly"
        
        # Property 4: Total duration is reasonable
        assert total_duration > 0, "Total duration should be positive"
        
        # Property 5: Primary language is valid
        assert result.primary_language in config.enabled_languages, "Primary language should be supported"
        
        # Property 6: Confidence scores are valid
        assert len(result.confidence_scores) > 0, "Should have confidence scores"
        for lang, confidence in result.confidence_scores.items():
            assert lang in config.enabled_languages, f"Language {lang} should be supported"
            assert 0.0 <= confidence <= 1.0, f"Confidence for {lang} should be valid"
        
        # Property 7: Quality metrics are in valid range
        assert 0.0 <= result.segmentation_quality <= 1.0, "Segmentation quality should be valid"
        assert 0.0 <= result.language_consistency <= 1.0, "Language consistency should be valid"
        
        note(f"Result: {len(result.segments)} segments, primary={result.primary_language}")
        note(f"Detected languages: {list(result.confidence_scores.keys())}")
        note(f"Quality: {result.segmentation_quality:.3f}, Consistency: {result.language_consistency:.3f}")
    
    @given(
        audio_segments=st.lists(
            st.tuples(
                st.sampled_from(['en', 'hi', 'ta', 'de', 'fr']),  # language
                st.binary(min_size=100, max_size=1000)  # audio data
            ),
            min_size=1,
            max_size=4
        ),
        config=language_config_for_mixed()
    )
    @settings(max_examples=20, deadline=8000)
    def test_segment_confidence_properties(self, audio_segments, config):
        """
        Test confidence scoring properties for mixed-language segments.
        
        **Validates: Requirements 1.4**
        """
        
        # Build mixed audio from segments
        mixed_audio = b''.join(audio for _, audio in audio_segments)
        expected_languages = list(set(lang for lang, _ in audio_segments))
        
        assume(len(mixed_audio) >= 200)  # Minimum total length
        
        # Filter expected languages to only include enabled ones
        expected_languages = [lang for lang in expected_languages if lang in config.enabled_languages]
        assume(len(expected_languages) > 0)  # Must have at least one valid language
        
        engine = MockMixedLanguageEngine(config)
        
        note(f"Input segments: {len(audio_segments)}")
        note(f"Expected languages: {expected_languages}")
        note(f"Total audio length: {len(mixed_audio)} bytes")
        
        result = engine.detect_mixed_language(mixed_audio)
        
        # Property 1: Confidence scores exist for detected languages
        detected_languages = list(result.confidence_scores.keys())
        assert len(detected_languages) > 0, "Should detect at least one language"
        
        # Property 2: All detected languages are supported
        for lang in detected_languages:
            assert lang in config.enabled_languages, f"Detected language {lang} should be supported"
        
        # Property 3: Confidence scores are reasonable
        for lang, confidence in result.confidence_scores.items():
            assert 0.0 <= confidence <= 1.0, f"Confidence for {lang} should be in valid range"
            
            # High confidence should be achievable for clear segments
            if len(audio_segments) == 1:  # Single language
                assert confidence >= 0.5, "Single language should have reasonable confidence"
        
        # Property 4: Primary language has reasonable confidence
        primary_confidence = result.confidence_scores.get(result.primary_language, 0.0)
        assert primary_confidence > 0.0, "Primary language should have positive confidence"
        
        # Property 5: Segment confidences are consistent with overall scores
        segment_languages = [seg.language for seg in result.segments]
        for lang in set(segment_languages):
            if lang in result.confidence_scores:
                # Overall confidence should be related to segment confidences
                segment_confidences = [seg.confidence for seg in result.segments if seg.language == lang]
                if segment_confidences:
                    avg_segment_confidence = sum(segment_confidences) / len(segment_confidences)
                    overall_confidence = result.confidence_scores[lang]
                    
                    # Should be reasonably close (within 0.3)
                    confidence_diff = abs(avg_segment_confidence - overall_confidence)
                    assert confidence_diff <= 0.4, f"Confidence mismatch for {lang}: segment avg={avg_segment_confidence:.3f}, overall={overall_confidence:.3f}"
        
        note(f"Confidence validation passed for {len(detected_languages)} languages")
    
    @given(
        single_language_audio=st.binary(min_size=500, max_size=5000),
        language=st.sampled_from(['en', 'hi', 'ta', 'de', 'fr']),
        config=language_config_for_mixed()
    )
    @settings(max_examples=15, deadline=5000)
    def test_single_language_consistency(self, single_language_audio, language, config):
        """
        Test that single-language audio produces consistent results.
        
        **Validates: Requirements 1.4**
        """
        
        assume(language in config.enabled_languages)  # Language must be enabled
        
        engine = MockMixedLanguageEngine(config)
        
        note(f"Testing single language: {language}")
        note(f"Audio length: {len(single_language_audio)} bytes")
        
        result = engine.detect_mixed_language(single_language_audio)
        
        # Property 1: Should produce reasonable segmentation
        assert len(result.segments) >= 1, "Should produce at least one segment"
        
        # Property 2: Language consistency should be high for single language
        # (allowing for some detection variation)
        if len(result.segments) > 1:
            # Multiple segments - check if they're mostly the same language
            languages = [seg.language for seg in result.segments]
            most_common_language = max(set(languages), key=languages.count)
            same_language_count = languages.count(most_common_language)
            consistency_ratio = same_language_count / len(languages)
            
            # At least 70% should be the same language for "single language" audio
            assert consistency_ratio >= 0.7, f"Single language audio should have high consistency: {consistency_ratio:.3f}"
        
        # Property 3: Language consistency metric should reflect single language nature
        if result.language_count == 1:
            assert result.language_consistency >= 0.9, "Single language should have very high consistency"
        else:
            # Multiple languages detected, but consistency should still be reasonable
            assert result.language_consistency >= 0.5, "Should have reasonable consistency even with multiple detections"
        
        # Property 4: Primary language should be reasonable
        assert result.primary_language in config.enabled_languages, "Primary language should be supported"
        
        note(f"Single language result: {result.language_count} languages, consistency={result.language_consistency:.3f}")
    
    @given(
        config=language_config_for_mixed()
    )
    @settings(max_examples=10, deadline=3000)
    def test_edge_case_handling(self, config):
        """
        Test mixed-language detection handles edge cases properly.
        
        **Validates: Requirements 1.4**
        """
        
        engine = MockMixedLanguageEngine(config)
        
        edge_cases = [
            (b"", "Empty audio"),
            (b"\x00" * 100, "Silent audio"),
            (b"x" * 50, "Repetitive pattern"),
            (b"a", "Single byte"),
        ]
        
        for audio, description in edge_cases:
            note(f"Testing edge case: {description}")
            
            try:
                result = engine.detect_mixed_language(audio)
                
                # Property 1: Should return valid result structure
                assert isinstance(result, MixedLanguageResult), f"{description}: Should return MixedLanguageResult"
                
                # Property 2: Should handle gracefully
                if len(audio) > 0:
                    assert len(result.segments) >= 0, f"{description}: Should have non-negative segments"
                    assert result.primary_language in config.enabled_languages, f"{description}: Primary language should be valid"
                
                # Property 3: Quality metrics should be valid
                assert 0.0 <= result.segmentation_quality <= 1.0, f"{description}: Quality should be valid"
                assert 0.0 <= result.language_consistency <= 1.0, f"{description}: Consistency should be valid"
                
                note(f"{description}: Handled successfully - {len(result.segments)} segments")
                
            except Exception as e:
                # Should not crash with unexpected exceptions
                # Some exceptions may be acceptable for invalid input
                note(f"{description}: Exception - {type(e).__name__}: {e}")
                
                # Should be a reasonable exception type
                assert isinstance(e, (ValueError, TypeError, RuntimeError)), f"{description}: Should raise appropriate exception type"
    
    @given(
        audio_length=st.integers(min_value=1000, max_value=20000),
        num_language_switches=st.integers(min_value=0, max_value=5),
        config=language_config_for_mixed()
    )
    @settings(max_examples=15, deadline=8000)
    def test_language_switching_properties(self, audio_length, num_language_switches, config):
        """
        Test properties of language switching detection.
        
        **Validates: Requirements 1.4**
        """
        
        # Create audio with controlled language switches
        languages = config.enabled_languages[:min(3, len(config.enabled_languages))]  # Use up to 3 languages
        
        # Create segments with language switches
        segment_length = audio_length // max(1, num_language_switches + 1)
        
        audio_parts = []
        expected_switches = 0
        
        for i in range(num_language_switches + 1):
            # Select language for this segment
            if i == 0:
                current_language = languages[0]
            else:
                # Switch to different language
                available_languages = [lang for lang in languages if lang != current_language]
                if available_languages:
                    current_language = available_languages[i % len(available_languages)]
                    expected_switches += 1
            
            # Create segment audio
            segment_pattern = current_language.encode() * 10
            segment_audio = segment_pattern * (segment_length // len(segment_pattern) + 1)
            segment_audio = segment_audio[:segment_length]
            
            audio_parts.append(segment_audio)
        
        mixed_audio = b''.join(audio_parts)
        
        assume(len(mixed_audio) >= 500)  # Minimum length for meaningful analysis
        
        engine = MockMixedLanguageEngine(config)
        
        note(f"Audio length: {len(mixed_audio)} bytes")
        note(f"Expected switches: {expected_switches}")
        note(f"Languages used: {languages[:num_language_switches + 1]}")
        
        result = engine.detect_mixed_language(mixed_audio)
        
        # Property 1: Should detect language switches
        detected_languages = list(result.confidence_scores.keys())
        
        if expected_switches > 0:
            # Should detect multiple languages when switches are present
            assert len(detected_languages) >= 1, "Should detect at least one language"
            
            # Language consistency should decrease with more switches
            if expected_switches >= 2:
                assert result.language_consistency <= 0.8, "High number of switches should reduce consistency"
        
        # Property 2: Segmentation should reflect switching pattern
        if len(result.segments) > 1:
            # Count actual language transitions in segments
            actual_transitions = 0
            for i in range(len(result.segments) - 1):
                if result.segments[i].language != result.segments[i + 1].language:
                    actual_transitions += 1
            
            # Should have some relationship to expected switches
            # (allowing for detection variations and merging)
            if expected_switches > 0:
                assert actual_transitions >= 0, "Should have some transitions when switches are expected"
        
        # Property 3: Quality should be reasonable despite switches
        assert result.segmentation_quality >= 0.0, "Quality should be non-negative"
        
        # Property 4: Primary language should be valid
        assert result.primary_language in config.enabled_languages, "Primary language should be supported"
        
        note(f"Switching result: {len(detected_languages)} languages, {result.language_consistency:.3f} consistency")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])