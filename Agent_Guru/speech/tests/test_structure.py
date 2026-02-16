"""Unit tests for project structure validation."""

import pytest
from pathlib import Path
import importlib


class TestProjectStructure:
    """Tests for validating the speech engine project structure."""
    
    def test_speech_package_exists(self):
        """Test that the speech package can be imported."""
        import Agent_Guru.speech
        assert Agent_Guru.speech is not None
    
    def test_core_modules_exist(self):
        """Test that core modules exist and can be imported."""
        # Test models module
        from Agent_Guru.speech import models
        assert models is not None
        
        # Test exceptions module
        from Agent_Guru.speech import exceptions
        assert exceptions is not None
        
        # Test config module
        from Agent_Guru.speech import config
        assert config is not None
    
    def test_subdirectories_exist(self):
        """Test that all required subdirectories exist."""
        speech_dir = Path(__file__).parent.parent
        
        required_dirs = [
            "audio",
            "stt",
            "tts",
            "emotion",
            "biometric",
            "commands",
            "context",
            "mobile",
            "tests"
        ]
        
        for dir_name in required_dirs:
            dir_path = speech_dir / dir_name
            assert dir_path.exists(), f"Directory {dir_name} does not exist"
            assert dir_path.is_dir(), f"{dir_name} is not a directory"
    
    def test_subdirectory_packages(self):
        """Test that all subdirectories are valid Python packages."""
        subdirs = [
            "audio",
            "stt",
            "tts",
            "emotion",
            "biometric",
            "commands",
            "context",
            "mobile"
        ]
        
        for subdir in subdirs:
            module_name = f"Agent_Guru.speech.{subdir}"
            try:
                module = importlib.import_module(module_name)
                assert module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")
    
    def test_test_subdirectories_exist(self):
        """Test that test subdirectories exist."""
        tests_dir = Path(__file__).parent
        
        required_test_dirs = [
            "audio",
            "stt",
            "tts",
            "emotion",
            "biometric",
            "commands",
            "context",
            "integration"
        ]
        
        for dir_name in required_test_dirs:
            dir_path = tests_dir / dir_name
            assert dir_path.exists(), f"Test directory {dir_name} does not exist"
            assert dir_path.is_dir(), f"Test {dir_name} is not a directory"
    
    def test_requirements_file_exists(self):
        """Test that requirements.txt exists."""
        speech_dir = Path(__file__).parent.parent
        requirements_file = speech_dir / "requirements.txt"
        
        assert requirements_file.exists(), "requirements.txt does not exist"
        assert requirements_file.is_file(), "requirements.txt is not a file"
    
    def test_requirements_file_content(self):
        """Test that requirements.txt contains expected dependencies."""
        speech_dir = Path(__file__).parent.parent
        requirements_file = speech_dir / "requirements.txt"
        
        content = requirements_file.read_text()
        
        # Check for key dependencies
        expected_deps = [
            "faster-whisper",
            "noisereduce",
            "librosa",
            "sounddevice",
            "soundfile",
            "pyttsx3",
            "numpy",
            "scipy",
            "hypothesis",
            "pytest",
            "pytest-cov",
            "pytest-asyncio",
            "transformers"
        ]
        
        for dep in expected_deps:
            assert dep in content, f"Dependency {dep} not found in requirements.txt"


class TestModelsModule:
    """Tests for models module structure."""
    
    def test_personality_type_enum(self):
        """Test PersonalityType enum is defined."""
        from Agent_Guru.speech.models import PersonalityType
        assert hasattr(PersonalityType, "GURU")
        assert hasattr(PersonalityType, "MAYA")
    
    def test_emotion_type_enum(self):
        """Test EmotionType enum is defined."""
        from Agent_Guru.speech.models import EmotionType
        assert hasattr(EmotionType, "HAPPY")
        assert hasattr(EmotionType, "SAD")
        assert hasattr(EmotionType, "ANGRY")
        assert hasattr(EmotionType, "NEUTRAL")
        assert hasattr(EmotionType, "SURPRISED")
        assert hasattr(EmotionType, "FEARFUL")
        assert hasattr(EmotionType, "DISGUSTED")
    
    def test_dataclasses_defined(self):
        """Test that all required dataclasses are defined."""
        from Agent_Guru.speech import models
        
        required_classes = [
            "WakeWordDetection",
            "TranscriptionResult",
            "TranscriptionSegment",
            "VoiceFeatures",
            "EmotionResult",
            "EmotionHistory",
            "VoiceModel",
            "NoiseProfile",
            "StreamMetrics",
            "ConversationContext",
            "ConversationTurn",
            "TTSConfig",
            "CommandResult"
        ]
        
        for class_name in required_classes:
            assert hasattr(models, class_name), f"Class {class_name} not found in models"


class TestExceptionsModule:
    """Tests for exceptions module structure."""
    
    def test_base_exception(self):
        """Test base exception is defined."""
        from Agent_Guru.speech.exceptions import GuruSpeechError
        assert issubclass(GuruSpeechError, Exception)
    
    def test_specific_exceptions(self):
        """Test that all specific exceptions are defined."""
        from Agent_Guru.speech import exceptions
        
        required_exceptions = [
            "AudioInputError",
            "AudioProcessingError",
            "WakeWordDetectionError",
            "TranscriptionError",
            "VoiceBiometricError",
            "EmotionDetectionError",
            "TTSError",
            "VoiceCloningError",
            "CommandParsingError",
            "ContextManagementError",
            "StreamingError",
            "ModelLoadError",
            "ConfigurationError"
        ]
        
        for exc_name in required_exceptions:
            assert hasattr(exceptions, exc_name), f"Exception {exc_name} not found"
            exc_class = getattr(exceptions, exc_name)
            assert issubclass(exc_class, exceptions.GuruSpeechError)


class TestConfigModule:
    """Tests for config module structure."""
    
    def test_config_classes_defined(self):
        """Test that all config classes are defined."""
        from Agent_Guru.speech import config
        
        required_configs = [
            "AudioConfig",
            "AudioProcessingConfig",
            "WakeWordConfig",
            "STTConfig",
            "TTSConfigSettings",
            "EmotionConfig",
            "VoiceBiometricConfig",
            "VoiceCloningConfig",
            "NoiseCancellationConfig",
            "StreamingConfig",
            "CommandConfig",
            "ContextConfig",
            "LanguageConfig",
            "ModelRouterConfig",
            "BackgroundServiceConfig",
            "BatteryConfig",
            "SpeechEngineConfig"
        ]
        
        for config_name in required_configs:
            assert hasattr(config, config_name), f"Config {config_name} not found"
    
    def test_speech_engine_config_factory_methods(self):
        """Test SpeechEngineConfig factory methods."""
        from Agent_Guru.speech.config import SpeechEngineConfig
        
        # Test Guru personality config
        guru_config = SpeechEngineConfig.for_guru_personality()
        assert guru_config is not None
        
        # Test Maya personality config
        maya_config = SpeechEngineConfig.for_maya_personality()
        assert maya_config is not None
