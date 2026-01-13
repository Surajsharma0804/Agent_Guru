"""
Tests for Language Detection Engine

Comprehensive test suite for production-grade language detection including
unit tests, property-based tests, and integration tests.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.multilingual.language_detection import (
    LanguageDetectionEngine,
    LanguageDetectionResult,
    LanguageConfidenceScore,
    LanguageSegment,
    MixedLanguageResult,
    DetectionMethod,
    ConfidenceLevel
)
from src.multilingual.configuration import MultilingualConfig, SupportedLanguages
from src.multilingual.exceptions import LanguageDetectionError, ModelLoadingError


class TestLanguageDetectionEngine:
    """Test suite for LanguageDetectionEngine."""
    
    @pytest.fixture
    def temp_models_dir(self):
        """Create temporary models directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            models_path = Path(temp_dir) / "models"
            models_path.mkdir(parents=True)
            
            # Create placeholder FastText model
            fasttext_path = models_path / "fasttext" / "lid.176.bin"
            fasttext_path.parent.mkdir(parents=True)
            fasttext_path.write_bytes(b"PLACEHOLDER_FASTTEXT_MODEL")
            
            # Create placeholder Whisper models
            whisper_path = models_path / "whisper"
            whisper_path.mkdir(parents=True)
            
            for lang in ["en", "hi", "ta", "de", "fr"]:
                model_file = whisper_path / f"{lang}.bin"
                model_file.write_bytes(f"PLACEHOLDER_WHISPER_{lang.upper()}".encode())
                
            yield models_path
            
    @pytest.fixture
    def test_config(self, temp_models_dir):
        """Create test configuration."""
        return MultilingualConfig(
            enabled_languages=["en", "hi", "ta", "de", "fr"],
            primary_language="en",
            fallback_language="en",
            detection_threshold=0.85,
            model_directory=temp_models_dir,
            fasttext_model_path=temp_models_dir / "fasttext" / "lid.176.bin",
            whisper_models_path=temp_models_dir / "whisper"
        )
        
    @pytest.fixture
    def detection_engine(self, test_config):
        """Create language detection engine."""
        return LanguageDetectionEngine(test_config)
        
    def test_engine_initialization(self, detection_engine):
        """Test engine initializes correctly."""
        assert detection_engine.config is not None
        assert detection_engine.session_cache is not None
        assert not detection_engine._models_loaded  # Models loaded lazily
        
    def test_model_loading(self, detection_engine):
        """Test model loading process."""
        # Models should load on first detection
        assert not detection_engine._models_loaded
        
        # Trigger model loading
        detection_engine._initialize_models()
        
        assert detection_engine._models_loaded
        assert detection_engine._fasttext_model is not None
        
    def test_fasttext_detection_deterministic(self, detection_engine):
        """Test FastText detection produces deterministic results."""
        # Create test audio
        test_audio = b'\x00\x01\x02\x03' * 1000  # 4KB of test data
        
        # Run detection multiple times
        results = []
        for _ in range(5):
            result = detection_engine.detect_language(test_audio)
            results.append((result.language, result.confidence))
            
        # All results should be identical (deterministic)
        assert len(set(results)) == 1, "Detection results should be deterministic"
        
    def test_detection_performance_bounds(self, detection_engine):
        """Test detection meets performance requirements."""
        test_audio = b'\x00\x01\x02\x03' * 1000
        
        start_time = time.time()
        result = detection_engine.detect_language(test_audio)
        end_time = time.time()
        
        processing_time_ms = (end_time - start_time) * 1000
        
        # Should meet performance bounds (≤150ms with acceleration, ≤300ms without)
        max_time_ms = detection_engine.config.max_detection_time_fallback_ms
        assert processing_time_ms <= max_time_ms, f"Detection took {processing_time_ms}ms, max allowed {max_time_ms}ms"
        
        # Result should also report processing time
        assert result.processing_time_ms > 0
        
    def test_confidence_scoring(self, detection_engine):
        """Test confidence scoring system."""
        test_audio = b'\x00\x01\x02\x03' * 1000
        
        result = detection_engine.detect_language(test_audio)
        
        # Confidence should be valid
        assert 0.0 <= result.confidence <= 1.0
        
        # Should have confidence scores
        assert len(result.confidence_scores) > 0
        
        # Primary confidence score should match result
        primary_score = result.get_primary_confidence_score()
        assert primary_score is not None
        assert primary_score.language == result.language
        
    def test_supported_languages(self, detection_engine):
        """Test detection works for all supported languages."""
        # Test with different audio patterns that should trigger different languages
        test_cases = [
            (b'\x00\x01' * 1000, "en"),  # Should detect as English (fallback)
            (b'\x02\x03' * 1000, None),  # Any supported language is valid
            (b'\x04\x05' * 1000, None),  # Any supported language is valid
        ]
        
        for audio, expected_lang in test_cases:
            result = detection_engine.detect_language(audio)
            
            # Should detect a supported language
            assert result.language in detection_engine.config.enabled_languages
            
            # If specific language expected, verify it
            if expected_lang:
                assert result.language == expected_lang
                
    def test_session_caching(self, detection_engine):
        """Test session-based language caching."""
        test_audio = b'\x00\x01\x02\x03' * 1000
        session_id = "test_session_123"
        
        # First detection should not use cache
        result1 = detection_engine.detect_language(test_audio, session_id=session_id)
        assert not result1.session_cached
        
        # Second detection should use cache if confidence is high enough
        result2 = detection_engine.detect_language(test_audio, session_id=session_id)
        
        # Results should be consistent
        assert result1.language == result2.language
        
        # Check cache statistics
        stats = detection_engine.get_detection_statistics()
        assert stats['total_detections'] >= 2
        
    def test_fallback_handling(self, detection_engine):
        """Test fallback handling for detection failures."""
        # Test with invalid audio that should trigger fallback
        invalid_audio = b''  # Empty audio
        
        result = detection_engine.detect_language(invalid_audio)
        
        # Should fallback to configured language
        assert result.language == detection_engine.config.fallback_language
        assert result.fallback_used
        assert result.method == DetectionMethod.FALLBACK
        
    def test_mixed_language_detection(self, detection_engine):
        """Test mixed-language detection and segmentation."""
        # Create test audio for mixed languages
        test_audio = b'\x00\x01\x02\x03' * 2000  # Larger audio for segmentation
        
        result = detection_engine.detect_mixed_language(test_audio)
        
        # Should return valid segmentation result
        assert isinstance(result, MixedLanguageResult)
        assert len(result.segments) > 0
        
        # All segments should have valid properties
        for segment in result.segments:
            assert isinstance(segment, LanguageSegment)
            assert segment.language in detection_engine.config.enabled_languages
            assert 0.0 <= segment.confidence <= 1.0
            assert segment.start_time >= 0.0
            assert segment.end_time > segment.start_time
            assert len(segment.audio) > 0
            
    def test_error_handling(self, detection_engine):
        """Test error handling and recovery."""
        # Test with None audio (should raise exception)
        with pytest.raises(Exception):
            detection_engine.detect_language(None)
            
        # Test with extremely large audio (should handle gracefully)
        large_audio = b'\x00' * (10 * 1024 * 1024)  # 10MB
        
        # Should either succeed or fail gracefully with fallback
        try:
            result = detection_engine.detect_language(large_audio)
            # If it succeeds, should be valid
            assert result.language in detection_engine.config.enabled_languages
        except LanguageDetectionError:
            # If it fails, should be a proper exception
            pass
            
    def test_model_installation(self, temp_models_dir):
        """Test FastText model installation."""
        model_path = temp_models_dir / "test_fasttext.bin"
        
        # Test installation without download
        success = LanguageDetectionEngine.install_fasttext_model(model_path)
        assert success
        assert model_path.exists()
        assert model_path.stat().st_size > 0
        
    def test_detection_statistics(self, detection_engine):
        """Test detection statistics tracking."""
        test_audio = b'\x00\x01\x02\x03' * 1000
        
        # Initial statistics
        initial_stats = detection_engine.get_detection_statistics()
        initial_count = initial_stats['total_detections']
        
        # Perform some detections
        for i in range(3):
            detection_engine.detect_language(test_audio, session_id=f"session_{i}")
            
        # Check updated statistics
        final_stats = detection_engine.get_detection_statistics()
        
        assert final_stats['total_detections'] == initial_count + 3
        assert 'average_processing_time_ms' in final_stats
        assert 'cache_hit_rate' in final_stats
        assert 'fallback_rate' in final_stats
        assert final_stats['models_loaded']
        
    def test_cleanup(self, detection_engine):
        """Test engine cleanup."""
        # Add some cache entries
        test_audio = b'\x00\x01\x02\x03' * 1000
        detection_engine.detect_language(test_audio, session_id="cleanup_test")
        
        # Cleanup should succeed
        detection_engine.cleanup()
        
        # Cache should be cleared
        cached_result = detection_engine.session_cache.get_cached_language("cleanup_test")
        assert cached_result is None


class TestLanguageConfidenceScore:
    """Test suite for LanguageConfidenceScore."""
    
    def test_confidence_level_categorization(self):
        """Test confidence level categorization."""
        test_cases = [
            (0.95, ConfidenceLevel.HIGH),
            (0.85, ConfidenceLevel.MEDIUM),
            (0.65, ConfidenceLevel.LOW),
            (0.35, ConfidenceLevel.VERY_LOW)
        ]
        
        for confidence, expected_level in test_cases:
            score = LanguageConfidenceScore(
                language="en",
                confidence=confidence,
                method=DetectionMethod.FASTTEXT,
                processing_time_ms=50
            )
            
            assert score.confidence_level == expected_level
            
    def test_score_serialization(self):
        """Test confidence score serialization."""
        score = LanguageConfidenceScore(
            language="hi",
            confidence=0.87,
            method=DetectionMethod.HYBRID,
            processing_time_ms=75,
            fasttext_score=0.85,
            whisper_score=0.89,
            session_cached=True
        )
        
        score_dict = score.to_dict()
        
        # Check all fields are present
        expected_fields = [
            'language', 'confidence', 'method', 'processing_time_ms',
            'fasttext_score', 'whisper_score', 'session_cached',
            'confidence_level'
        ]
        
        for field in expected_fields:
            assert field in score_dict
            
        assert score_dict['language'] == "hi"
        assert score_dict['confidence'] == 0.87
        assert score_dict['method'] == "hybrid"


class TestLanguageDetectionResult:
    """Test suite for LanguageDetectionResult."""
    
    def test_result_success_property(self):
        """Test result success property."""
        # Successful result
        success_result = LanguageDetectionResult(
            language="en",
            confidence=0.9,
            method=DetectionMethod.FASTTEXT,
            processing_time_ms=50
        )
        
        assert success_result.success
        
        # Failed result
        failed_result = LanguageDetectionResult(
            language="en",
            confidence=0.0,
            method=DetectionMethod.FALLBACK,
            processing_time_ms=50,
            error="Detection failed"
        )
        
        assert not failed_result.success
        
    def test_result_serialization(self):
        """Test result serialization."""
        result = LanguageDetectionResult(
            language="ta",
            confidence=0.88,
            method=DetectionMethod.HYBRID,
            processing_time_ms=120,
            is_mixed_language=True
        )
        
        result_dict = result.to_dict()
        
        # Check essential fields
        assert result_dict['language'] == "ta"
        assert result_dict['confidence'] == 0.88
        assert result_dict['method'] == "hybrid"
        assert result_dict['is_mixed_language'] is True
        assert result_dict['success'] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])