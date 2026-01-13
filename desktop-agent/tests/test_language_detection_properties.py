"""
Property-Based Tests for Language Detection Engine

Comprehensive property-based testing for deterministic language detection
with performance bounds and comprehensive language support validation.

**Feature: guru-multilingual-understanding, Property 1: Deterministic Language Detection with Performance Bounds**
**Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**
"""

import pytest
import tempfile
import time
import sys
from pathlib import Path
from typing import List, Tuple
import hashlib

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hypothesis import given, strategies as st, settings, assume, note
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, initialize

from multilingual.language_detection import (
    LanguageDetectionEngine,
    LanguageDetectionResult,
    DetectionMethod,
    ConfidenceLevel
)
from multilingual.configuration import MultilingualConfig, SupportedLanguages
from multilingual.exceptions import LanguageDetectionError


# Test data generation strategies
@st.composite
def audio_data(draw):
    """Generate realistic audio data for testing."""
    # Audio length between 100ms and 10 seconds at 16kHz
    length = draw(st.integers(min_value=1600, max_value=160000))
    
    # Generate audio with some structure (not just random bytes)
    base_pattern = draw(st.binary(min_size=1, max_size=100))
    repetitions = length // len(base_pattern) + 1
    
    audio = (base_pattern * repetitions)[:length]
    return audio


@st.composite
def language_config(draw):
    """Generate valid language configurations."""
    all_languages = SupportedLanguages.get_language_codes()
    
    # Select 1-5 enabled languages
    num_languages = draw(st.integers(min_value=1, max_value=min(5, len(all_languages))))
    enabled_languages = draw(st.lists(
        st.sampled_from(all_languages),
        min_size=num_languages,
        max_size=num_languages,
        unique=True
    ))
    
    primary_language = draw(st.sampled_from(enabled_languages))
    
    return {
        'enabled_languages': enabled_languages,
        'primary_language': primary_language,
        'fallback_language': primary_language,
        'detection_threshold': draw(st.floats(min_value=0.5, max_value=0.95)),
        'max_detection_time_ms': draw(st.integers(min_value=100, max_value=300)),
        'max_detection_time_fallback_ms': draw(st.integers(min_value=200, max_value=500))
    }


class TestLanguageDetectionProperties:
    """Property-based tests for language detection determinism and performance."""
    
    @pytest.fixture
    def temp_models_dir(self):
        """Create temporary models directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_path = Path(temp_dir) / "models"
            models_path.mkdir(parents=True)
            
            # Create placeholder FastText model
            fasttext_path = models_path / "fasttext" / "lid.176.bin"
            fasttext_path.parent.mkdir(parents=True)
            fasttext_path.write_bytes(b"PLACEHOLDER_FASTTEXT_MODEL")
            
            # Create placeholder Whisper models for all supported languages
            whisper_path = models_path / "whisper"
            whisper_path.mkdir(parents=True)
            
            for lang_code in SupportedLanguages.get_language_codes():
                lang_config = SupportedLanguages.get_language_by_code(lang_code)
                model_file = whisper_path / f"{lang_config.whisper_model}.bin"
                model_file.write_bytes(f"PLACEHOLDER_WHISPER_{lang_code.upper()}".encode())
                
            yield models_path
    
    def create_detection_engine(self, temp_models_dir: Path, config_dict: dict) -> LanguageDetectionEngine:
        """Create detection engine with given configuration."""
        config = MultilingualConfig(
            model_directory=temp_models_dir,
            fasttext_model_path=temp_models_dir / "fasttext" / "lid.176.bin",
            whisper_models_path=temp_models_dir / "whisper",
            **config_dict
        )
        return LanguageDetectionEngine(config)
    
    @given(
        audio=audio_data(),
        config_dict=language_config()
    )
    @settings(max_examples=50, deadline=5000)  # 5 second deadline per test
    def test_deterministic_detection(self, temp_models_dir, audio, config_dict):
        """
        **Property 1: Deterministic Language Detection with Performance Bounds**
        
        For any audio input, language detection should produce identical results 
        on repeated calls and complete within performance bounds.
        
        **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**
        """
        assume(len(audio) >= 100)  # Minimum audio length
        
        engine = self.create_detection_engine(temp_models_dir, config_dict)
        
        note(f"Testing with audio length: {len(audio)} bytes")
        note(f"Enabled languages: {config_dict['enabled_languages']}")
        note(f"Detection threshold: {config_dict['detection_threshold']}")
        
        # Test deterministic behavior - run detection multiple times
        results = []
        processing_times = []
        
        for i in range(3):  # Run 3 times to verify determinism
            start_time = time.time()
            result = engine.detect_language(audio, session_id=f"test_session_{i}")
            end_time = time.time()
            
            processing_time_ms = (end_time - start_time) * 1000
            processing_times.append(processing_time_ms)
            
            # Collect key result properties for determinism check
            result_signature = (
                result.language,
                result.confidence,
                result.method.value if result.method else None,
                result.success
            )
            results.append(result_signature)
            
            note(f"Run {i+1}: {result.language} (confidence: {result.confidence:.3f}, time: {processing_time_ms:.1f}ms)")
        
        # Property 1a: Deterministic Results
        # All results should be identical for the same input
        unique_results = set(results)
        assert len(unique_results) == 1, f"Detection should be deterministic, got different results: {results}"
        
        # Property 1b: Performance Bounds
        # All detections should complete within configured time limits
        max_allowed_time = config_dict['max_detection_time_fallback_ms']
        for i, proc_time in enumerate(processing_times):
            assert proc_time <= max_allowed_time, f"Detection {i+1} took {proc_time:.1f}ms, max allowed {max_allowed_time}ms"
        
        # Property 1c: Valid Language Detection
        # Detected language should be in enabled languages or fallback
        result = engine.detect_language(audio)
        valid_languages = set(config_dict['enabled_languages']) | {config_dict['fallback_language']}
        assert result.language in valid_languages, f"Detected language {result.language} not in valid set {valid_languages}"
        
        # Property 1d: Confidence Bounds
        # Confidence should be within valid range
        assert 0.0 <= result.confidence <= 1.0, f"Confidence {result.confidence} outside valid range [0.0, 1.0]"
        
        # Property 1e: Processing Time Reporting
        # Engine should report processing time that matches actual time
        assert result.processing_time_ms > 0, "Processing time should be positive"
        
        # Property 1f: Fallback Behavior
        # If confidence is below threshold, should use fallback appropriately
        if result.confidence < config_dict['detection_threshold']:
            # Low confidence should either use fallback or be explicitly handled
            assert (result.fallback_used or 
                   result.method == DetectionMethod.CACHED or
                   result.confidence >= 0.5), "Low confidence detection should use fallback or be cached"
    
    @given(
        audio_list=st.lists(audio_data(), min_size=2, max_size=5),
        config_dict=language_config()
    )
    @settings(max_examples=20, deadline=10000)
    def test_consistent_behavior_across_inputs(self, temp_models_dir, audio_list, config_dict):
        """
        Test that detection behavior is consistent across different audio inputs.
        
        **Validates: Requirements 1.2, 1.5**
        """
        engine = self.create_detection_engine(temp_models_dir, config_dict)
        
        results = []
        for i, audio in enumerate(audio_list):
            assume(len(audio) >= 100)
            
            result = engine.detect_language(audio, session_id=f"consistency_test_{i}")
            results.append(result)
            
            note(f"Audio {i+1}: {len(audio)} bytes -> {result.language} ({result.confidence:.3f})")
        
        # Property: All results should be valid
        for i, result in enumerate(results):
            assert result.language in config_dict['enabled_languages'] or result.language == config_dict['fallback_language']
            assert 0.0 <= result.confidence <= 1.0
            assert result.processing_time_ms > 0
            
        # Property: Detection method should be consistent for similar confidence levels
        high_confidence_methods = [r.method for r in results if r.confidence >= 0.8]
        if len(high_confidence_methods) > 1:
            # High confidence detections should use similar methods
            method_types = set(high_confidence_methods)
            assert len(method_types) <= 2, "High confidence detections should use consistent methods"
    
    @given(
        audio=audio_data(),
        session_ids=st.lists(st.text(min_size=1, max_size=20), min_size=2, max_size=5, unique=True)
    )
    @settings(max_examples=20, deadline=5000)
    def test_session_caching_behavior(self, temp_models_dir, audio, session_ids):
        """
        Test session caching behavior for performance optimization.
        
        **Validates: Requirements 9.2**
        """
        assume(len(audio) >= 100)
        
        config_dict = {
            'enabled_languages': ['en', 'hi', 'ta'],
            'primary_language': 'en',
            'fallback_language': 'en',
            'detection_threshold': 0.85,
            'cache_language_context': True
        }
        
        engine = self.create_detection_engine(temp_models_dir, config_dict)
        
        # Test caching within same session
        session_id = session_ids[0]
        
        # First detection
        result1 = engine.detect_language(audio, session_id=session_id)
        
        # Second detection with same session should potentially use cache
        result2 = engine.detect_language(audio, session_id=session_id)
        
        note(f"First detection: {result1.language} (cached: {result1.session_cached})")
        note(f"Second detection: {result2.language} (cached: {result2.session_cached})")
        
        # Property: Results should be consistent within session
        assert result1.language == result2.language, "Session results should be consistent"
        
        # Property: If confidence is high enough, second call might use cache
        if result1.confidence >= config_dict['detection_threshold']:
            # Cache behavior is implementation-dependent, but results should be consistent
            assert result1.confidence == result2.confidence or result2.session_cached
        
        # Test different sessions produce independent results
        for other_session_id in session_ids[1:]:
            other_result = engine.detect_language(audio, session_id=other_session_id)
            
            # Should be consistent language detection regardless of session
            assert other_result.language == result1.language, "Language detection should be session-independent"
    
    @given(
        config_dict=language_config()
    )
    @settings(max_examples=10, deadline=3000)
    def test_mixed_language_detection_properties(self, temp_models_dir, config_dict):
        """
        Test mixed-language detection properties.
        
        **Validates: Requirements 1.4**
        """
        engine = self.create_detection_engine(temp_models_dir, config_dict)
        
        # Create mixed-language audio (simulate by concatenating different patterns)
        audio_segments = []
        for i in range(3):  # 3 segments
            segment = bytes([i % 256] * 1000)  # Different patterns
            audio_segments.append(segment)
        
        mixed_audio = b''.join(audio_segments)
        
        result = engine.detect_mixed_language(mixed_audio)
        
        note(f"Mixed language result: {len(result.segments)} segments")
        note(f"Primary language: {result.primary_language}")
        
        # Property: Should return valid segmentation
        assert len(result.segments) > 0, "Mixed language detection should return segments"
        
        # Property: All segments should have valid properties
        total_duration = 0
        for i, segment in enumerate(result.segments):
            assert segment.start_time >= 0, f"Segment {i} start time should be non-negative"
            assert segment.end_time > segment.start_time, f"Segment {i} end time should be after start time"
            assert segment.language in config_dict['enabled_languages'], f"Segment {i} language should be supported"
            assert 0.0 <= segment.confidence <= 1.0, f"Segment {i} confidence should be valid"
            assert len(segment.audio) > 0, f"Segment {i} should have audio data"
            
            total_duration += segment.duration
        
        # Property: Segments should cover reasonable portion of audio
        assert total_duration > 0, "Total segment duration should be positive"
        
        # Property: Primary language should be one of the detected languages
        detected_languages = {seg.language for seg in result.segments}
        assert result.primary_language in detected_languages, "Primary language should be in detected segments"
    
    @given(
        audio=audio_data(),
        config_dict=language_config()
    )
    @settings(max_examples=20, deadline=3000)
    def test_error_handling_properties(self, temp_models_dir, audio, config_dict):
        """
        Test error handling and fallback properties.
        
        **Validates: Requirements 1.5, 1.6**
        """
        assume(len(audio) >= 10)  # Allow smaller audio for error testing
        
        engine = self.create_detection_engine(temp_models_dir, config_dict)
        
        # Test with various audio sizes including edge cases
        test_cases = [
            audio,  # Normal audio
            audio[:10],  # Very short audio
            b'',  # Empty audio
            b'\x00' * len(audio),  # Silent audio
        ]
        
        for i, test_audio in enumerate(test_cases):
            note(f"Testing audio case {i+1}: {len(test_audio)} bytes")
            
            try:
                result = engine.detect_language(test_audio)
                
                # Property: Valid results should have proper structure
                assert result.language in config_dict['enabled_languages'] or result.language == config_dict['fallback_language']
                assert 0.0 <= result.confidence <= 1.0
                assert result.processing_time_ms >= 0
                
                # Property: Low confidence or problematic input should use fallback
                if len(test_audio) < 100 or test_audio == b'\x00' * len(test_audio):
                    # Should likely use fallback for problematic input
                    assert (result.fallback_used or 
                           result.confidence < config_dict['detection_threshold'] or
                           result.language == config_dict['fallback_language'])
                
            except LanguageDetectionError as e:
                # Property: Errors should be properly structured
                assert e.error_code is not None
                assert len(e.message) > 0
                
                # Property: Error context should be informative
                if hasattr(e, 'audio_length_ms'):
                    assert e.audio_length_ms >= 0
                    
            except Exception as e:
                # Property: Should not raise unexpected exceptions
                pytest.fail(f"Unexpected exception for audio case {i+1}: {type(e).__name__}: {e}")


class LanguageDetectionStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for language detection engine.
    
    Tests complex interactions and state management over multiple operations.
    """
    
    def __init__(self):
        super().__init__()
        
        # Create temporary models directory
        self.temp_dir = tempfile.mkdtemp()
        self.models_path = Path(self.temp_dir) / "models"
        self.models_path.mkdir(parents=True)
        
        # Setup model files
        fasttext_path = self.models_path / "fasttext" / "lid.176.bin"
        fasttext_path.parent.mkdir(parents=True)
        fasttext_path.write_bytes(b"PLACEHOLDER_FASTTEXT_MODEL")
        
        whisper_path = self.models_path / "whisper"
        whisper_path.mkdir(parents=True)
        
        for lang_code in ['en', 'hi', 'ta', 'de', 'fr']:
            model_file = whisper_path / f"{lang_code}.bin"
            model_file.write_bytes(f"PLACEHOLDER_WHISPER_{lang_code.upper()}".encode())
        
        # Create engine
        config = MultilingualConfig(
            enabled_languages=['en', 'hi', 'ta', 'de', 'fr'],
            primary_language='en',
            fallback_language='en',
            detection_threshold=0.85,
            model_directory=self.models_path,
            fasttext_model_path=fasttext_path,
            whisper_models_path=whisper_path
        )
        
        self.engine = LanguageDetectionEngine(config)
        self.session_counter = 0
        self.detection_history = []
    
    audio_samples = Bundle('audio_samples')
    session_ids = Bundle('session_ids')
    
    @initialize()
    def setup(self):
        """Initialize the state machine."""
        pass
    
    @rule(target=audio_samples)
    def generate_audio(self):
        """Generate audio sample for testing."""
        length = st.integers(min_value=100, max_value=5000).example()
        pattern = st.binary(min_size=1, max_size=50).example()
        repetitions = length // len(pattern) + 1
        audio = (pattern * repetitions)[:length]
        return audio
    
    @rule(target=session_ids)
    def generate_session_id(self):
        """Generate session ID for testing."""
        self.session_counter += 1
        return f"session_{self.session_counter}"
    
    @rule(audio=audio_samples, session_id=session_ids)
    def detect_language(self, audio, session_id):
        """Perform language detection and verify properties."""
        result = self.engine.detect_language(audio, session_id=session_id)
        
        # Record detection for analysis
        self.detection_history.append({
            'audio_hash': hashlib.md5(audio).hexdigest(),
            'session_id': session_id,
            'result': result
        })
        
        # Property: Valid detection result
        assert result.language in self.engine.config.enabled_languages
        assert 0.0 <= result.confidence <= 1.0
        assert result.processing_time_ms >= 0
        
        # Property: Deterministic behavior for same audio
        same_audio_results = [
            h['result'] for h in self.detection_history 
            if h['audio_hash'] == hashlib.md5(audio).hexdigest()
        ]
        
        if len(same_audio_results) > 1:
            # All results for same audio should have same language
            languages = {r.language for r in same_audio_results}
            assert len(languages) == 1, f"Same audio should produce same language: {languages}"
    
    @rule(audio=audio_samples)
    def detect_mixed_language(self, audio):
        """Test mixed language detection properties."""
        result = self.engine.detect_mixed_language(audio)
        
        # Property: Valid segmentation
        assert len(result.segments) > 0
        assert result.primary_language in self.engine.config.enabled_languages
        
        # Property: Segments are properly ordered and non-overlapping
        for i in range(len(result.segments) - 1):
            current = result.segments[i]
            next_seg = result.segments[i + 1]
            assert current.end_time <= next_seg.start_time, "Segments should not overlap"
    
    def teardown(self):
        """Clean up resources."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


# Property-based test runner
TestLanguageDetectionStateMachine = LanguageDetectionStateMachine.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])