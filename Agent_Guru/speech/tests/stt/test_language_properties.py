"""
Property-based tests for language detector.

Property 23: Language Detection and Switching

Validates: Requirements 19.2, 19.3, 19.4
"""

import pytest
from hypothesis import given, strategies as st, settings

from Agent_Guru.speech.stt.language_detector import (
    LanguageDetector,
    Language
)


class TestLanguageDetectorProperties:
    """Property-based tests for language detector."""
    
    # ========================================================================
    # PROPERTY 23: LANGUAGE DETECTION AND SWITCHING
    # ========================================================================
    
    @given(
        text=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_23_confidence_range(self, text: str):
        """
        Property 23: Language Detection and Switching
        
        For any text, confidence score must be in [0.0, 1.0].
        
        Validates: Requirements 19.2
        """
        detector = LanguageDetector()
        
        result = detector.detect_language(text)
        
        # PROPERTY ASSERTION: Confidence must be in valid range
        assert 0.0 <= result.confidence <= 1.0, \
            f"Confidence {result.confidence} outside [0.0, 1.0] for text: {text}"
    
    @given(
        text=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_23_language_detection(self, text: str):
        """
        Property 23: Language Detection and Switching
        
        For any text, language detection should return a valid Language enum.
        
        Validates: Requirements 19.2
        """
        detector = LanguageDetector()
        
        result = detector.detect_language(text)
        
        # PROPERTY ASSERTION: Should return valid Language
        assert isinstance(result.language, Language)
        assert result.language in Language
    
    @given(
        text=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_23_code_switching(self, text: str):
        """
        Property 23: Language Detection and Switching
        
        For any text, code-switching detection should return list of segments.
        
        Validates: Requirements 19.4
        """
        detector = LanguageDetector()
        
        segments = detector.detect_code_switching(text)
        
        # PROPERTY ASSERTION: Should return list
        assert isinstance(segments, list)
        
        # Each segment should have text and language
        for segment_text, language in segments:
            assert isinstance(segment_text, str)
            assert isinstance(language, Language)
    
    @given(
        min_confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_23_min_confidence_threshold(self, min_confidence: float):
        """
        Property 23: Language Detection and Switching
        
        For any min_confidence threshold, detection should respect it.
        
        Validates: Requirements 19.2
        """
        detector = LanguageDetector()
        text = "Hello world"
        
        result = detector.detect_language(text, min_confidence=min_confidence)
        
        # PROPERTY ASSERTION: If confidence below threshold, should return UNKNOWN
        if result.confidence < min_confidence:
            assert result.language == Language.UNKNOWN
    
    # ========================================================================
    # PROPERTY: CONSISTENCY
    # ========================================================================
    
    @given(
        text=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_consistency(self, text: str):
        """
        Property: Consistency
        
        For any text, detecting language multiple times should give same result.
        """
        detector = LanguageDetector()
        
        # Detect multiple times
        results = [detector.detect_language(text) for _ in range(3)]
        
        # PROPERTY ASSERTION: Results should be consistent
        for i in range(1, len(results)):
            assert results[i].language == results[0].language
            assert results[i].confidence == results[0].confidence
    
    # ========================================================================
    # PROPERTY: ROBUSTNESS
    # ========================================================================
    
    @given(
        text=st.text(max_size=1000),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_robustness_to_any_text(self, text: str):
        """
        Property: Robustness
        
        For any text (including empty, special chars, unicode), system should handle gracefully.
        """
        detector = LanguageDetector()
        
        # Should not crash
        result = detector.detect_language(text)
        
        # PROPERTY ASSERTION
        assert result is not None
        assert isinstance(result.language, Language)
        assert 0.0 <= result.confidence <= 1.0
    
    @given(
        language=st.sampled_from([
            Language.ENGLISH, Language.SPANISH, Language.FRENCH, Language.GERMAN,
            Language.CHINESE, Language.JAPANESE, Language.HINDI, Language.PUNJABI
        ]),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_supported_languages(self, language: Language):
        """
        Property: Supported Languages
        
        For any supported language, it should be in the supported list.
        """
        detector = LanguageDetector()
        
        supported = detector.get_supported_languages()
        
        # PROPERTY ASSERTION
        assert language in supported
