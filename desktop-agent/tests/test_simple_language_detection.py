"""
Simple test for language detection to verify basic functionality.
"""

import sys
import tempfile
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import directly from the module file
import importlib.util

def test_language_detection_import():
    """Test that we can import and instantiate the language detection engine."""
    
    # Load the module directly
    spec = importlib.util.spec_from_file_location(
        "language_detection", 
        Path(__file__).parent.parent / "src" / "multilingual" / "language_detection.py"
    )
    language_detection = importlib.util.module_from_spec(spec)
    
    # Load configuration module
    config_spec = importlib.util.spec_from_file_location(
        "configuration",
        Path(__file__).parent.parent / "src" / "multilingual" / "configuration.py"
    )
    configuration = importlib.util.module_from_spec(config_spec)
    
    # Load exceptions module
    exceptions_spec = importlib.util.spec_from_file_location(
        "exceptions",
        Path(__file__).parent.parent / "src" / "multilingual" / "exceptions.py"
    )
    exceptions = importlib.util.module_from_spec(exceptions_spec)
    
    # Execute the modules
    spec.loader.exec_module(language_detection)
    config_spec.loader.exec_module(configuration)
    exceptions_spec.loader.exec_module(exceptions)
    
    # Inject dependencies
    language_detection.MultilingualConfig = configuration.MultilingualConfig
    language_detection.SupportedLanguages = configuration.SupportedLanguages
    language_detection.LanguageConfig = configuration.LanguageConfig
    language_detection.LanguageDetectionError = exceptions.LanguageDetectionError
    language_detection.ModelLoadingError = exceptions.ModelLoadingError
    language_detection.PerformanceError = exceptions.PerformanceError
    language_detection.UnsupportedLanguageError = exceptions.UnsupportedLanguageError
    
    # Test that we can access the class
    assert hasattr(language_detection, 'LanguageDetectionEngine')
    
    # Create temporary models directory
    with tempfile.TemporaryDirectory() as temp_dir:
        models_path = Path(temp_dir) / "models"
        models_path.mkdir(parents=True)
        
        # Create placeholder FastText model
        fasttext_path = models_path / "fasttext" / "lid.176.bin"
        fasttext_path.parent.mkdir(parents=True)
        fasttext_path.write_bytes(b"PLACEHOLDER_FASTTEXT_MODEL")
        
        # Create test configuration
        config = configuration.MultilingualConfig(
            enabled_languages=["en", "hi"],
            primary_language="en",
            fallback_language="en",
            detection_threshold=0.85,
            model_directory=models_path,
            fasttext_model_path=fasttext_path,
            whisper_models_path=models_path / "whisper"
        )
        
        # Test instantiation
        engine = language_detection.LanguageDetectionEngine(config)
        assert engine is not None
        assert engine.config == config
        
        # Test basic detection
        test_audio = b'\x00\x01\x02\x03' * 1000
        result = engine.detect_language(test_audio)
        
        # Verify result structure
        assert hasattr(result, 'language')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'processing_time_ms')
        assert result.language in config.enabled_languages
        assert 0.0 <= result.confidence <= 1.0
        assert result.processing_time_ms >= 0
        
        print(f"Detection result: {result.language} (confidence: {result.confidence:.3f})")
        print("Language detection test passed!")


if __name__ == "__main__":
    test_language_detection_import()