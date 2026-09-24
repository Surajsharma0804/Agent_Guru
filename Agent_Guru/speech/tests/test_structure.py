"""Unit tests for project structure validation."""

import pytest
from pathlib import Path
import importlib


class TestProjectStructure:
    """Tests for validating the speech engine project structure."""
    
    def test_speech_package_exists(self):
        """Test that the speech package can be imported."""
        import Agent_Guru.speech
        assert Agent_Guru.speech is not None  # nosec B101
    
    def test_core_modules_exist(self):
        """Test that core modules exist and can be imported."""
        # Test models module
        from Agent_Guru.speech import models
        assert models is not None  # nosec B101
        
        # Test exceptions module
        from Agent_Guru.speech import exceptions
        assert exceptions is not None  # nosec B101
        
        # Test config module
        from Agent_Guru.speech import config
        assert config is not None  # nosec B101
    
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
            assert dir_path.exists(), f"Directory {dir_name} does not exist"  # nosec B101
            assert dir_path.is_dir(), f"{dir_name} is not a directory"  # nosec B101
    
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
                assert module is not None  # nosec B101
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
            assert dir_path.exists(), f"Test directory {dir_name} does not exist"  # nosec B101
            assert dir_path.is_dir(), f"Test {dir_name} is not a directory"  # nosec B101
    
    def test_requirements_file_exists(self):
        """Test that requirements.txt exists."""
        speech_dir = Path(__file__).parent.parent
        requirements_file = speech_dir / "requirements.txt"
        
        assert requirements_file.exists(), "requirements.txt does not exist"  # nosec B101
        assert requirements_file.is_file(), "requirements.txt is not a file"  # nosec B101
    
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
            assert dep in content, f"Dependency {dep} not found in requirements.txt"  # nosec B101


class TestModelsModule:
    """Tests for models module structure."""
    
    def test_personality_type_enum(self):
        """Test PersonalityType enum is defined."""
        from Agent_Guru.speech.models import PersonalityType
        assert hasattr(PersonalityType, "GURU")  # nosec B101
        assert hasattr(PersonalityType, "MAYA")  # nosec B101
    
    def test_emotion_type_enum(self):
        """Test EmotionType enum is defined."""
        from Agent_Guru.speech.models import EmotionType
        assert hasattr(EmotionType, "HAPPY")  # nosec B101
        assert hasattr(EmotionType, "SAD")  # nosec B101
        assert hasattr(EmotionType, "ANGRY")  # nosec B101
        assert hasattr(EmotionType, "NEUTRAL")  # nosec B101
        assert hasattr(EmotionType, "SURPRISED")  # nosec B101
        assert hasattr(EmotionType, "FEARFUL")  # nosec B101
        assert hasattr(EmotionType, "DISGUSTED")  # nosec B101
    
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
            assert hasattr(models, class_name), f"Class {class_name} not found in models"  # nosec B101


class TestExceptionsModule:
    """Tests for exceptions module structure."""
    
    def test_base_exception(self):
        """Test base exception is defined."""
        from Agent_Guru.speech.exceptions import GuruSpeechError
        assert issubclass(GuruSpeechError, Exception)  # nosec B101
    
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
            assert hasattr(exceptions, exc_name), f"Exception {exc_name} not found"  # nosec B101
            exc_class = getattr(exceptions, exc_name)
            assert issubclass(exc_class, exceptions.GuruSpeechError)  # nosec B101


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
            assert hasattr(config, config_name), f"Config {config_name} not found"  # nosec B101
    
    def test_speech_engine_config_factory_methods(self):
        """Test SpeechEngineConfig factory methods."""
        from Agent_Guru.speech.config import SpeechEngineConfig
        
        # Test Guru personality config
        guru_config = SpeechEngineConfig.for_guru_personality()
        assert guru_config is not None  # nosec B101
        
        # Test Maya personality config
        maya_config = SpeechEngineConfig.for_maya_personality()
        assert maya_config is not None  # nosec B101


# librosa, sounddevice and soundfile are optional audio extras. When
# voice_features, voice_cloner, emotion_detector and audio/capture imported
# them at module scope, a machine without them could not import SpeechEngine
# at all, and whole test files failed to collect, so the run reported errors
# for code that was not broken. Each check runs in a fresh interpreter with the
# three packages blocked, so it proves the point whether or not they happen to
# be installed here.
_BLOCK_OPTIONAL_AUDIO = (
    "import sys\n"
    "for _name in ('librosa', 'sounddevice', 'soundfile'):\n"
    "    sys.modules[_name] = None\n"
)


def _run_without_optional_audio(body: str) -> None:
    import subprocess
    import sys
    import textwrap

    repo_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(  # noqa: S603  # nosec B603
        [sys.executable, "-c", _BLOCK_OPTIONAL_AUDIO + textwrap.dedent(body)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr  # nosec B101


class TestImportableWithoutOptionalAudioExtras:
    """The speech package must import, and fail clearly, without the audio extras."""

    def test_speech_modules_import(self):
        _run_without_optional_audio(
            """
            import Agent_Guru.speech.engine
            import Agent_Guru.speech.biometric
            import Agent_Guru.speech.emotion
            import Agent_Guru.speech.tts.voice_cloner
            import Agent_Guru.speech.audio.capture
            """
        )

    def test_voice_features_report_the_missing_package(self):
        _run_without_optional_audio(
            """
            import asyncio
            import numpy as np
            from Agent_Guru.speech.biometric import VoiceFeatureExtractor
            from Agent_Guru.speech.exceptions import VoiceBiometricError

            extractor = VoiceFeatureExtractor()
            audio = np.sin(np.linspace(0, 2000, 16000)).astype(np.float32)
            try:
                asyncio.run(extractor.extract_features(audio, 16000))
            except VoiceBiometricError as exc:
                assert "librosa" in str(exc), exc
            else:
                raise AssertionError("extract_features succeeded without librosa")

            # Input errors are still reported as themselves, not as a missing
            # package, and empty audio keeps its definite liveness verdict.
            try:
                asyncio.run(extractor.extract_features(np.zeros(0, np.float32), 16000))
            except VoiceBiometricError as exc:
                assert "empty" in str(exc), exc
            assert extractor.detect_liveness(np.zeros(0, np.float32), 16000) == (False, 0.0)
            # Liveness without librosa must fail closed.
            assert extractor.detect_liveness(audio, 16000)[0] is False
            """
        )

    def test_emotion_detection_does_not_fake_a_result(self):
        # extract_acoustic_features swallows its own failures into default
        # features. A missing librosa must not be swallowed with them, or
        # every utterance would come back as a confident-looking reading.
        _run_without_optional_audio(
            """
            import numpy as np
            from Agent_Guru.speech.emotion import EmotionDetector
            from Agent_Guru.speech.exceptions import EmotionDetectionError

            audio = np.sin(np.linspace(0, 2000, 16000)).astype(np.float32)
            try:
                EmotionDetector().detect_emotion(audio, 16000)
            except EmotionDetectionError as exc:
                assert "librosa" in str(exc), exc
            else:
                raise AssertionError("detect_emotion returned a result without librosa")
            """
        )

    def test_audio_capture_reports_the_missing_package(self):
        _run_without_optional_audio(
            """
            from Agent_Guru.speech.audio.capture import FileCapture, MicrophoneCapture
            from Agent_Guru.speech.exceptions import AudioInputError

            for call in (
                lambda: FileCapture.get_file_info("missing.wav"),
                lambda: MicrophoneCapture().capture(duration=0.1),
            ):
                try:
                    call()
                except AudioInputError as exc:
                    assert "sound" in str(exc), exc
                else:
                    raise AssertionError("capture succeeded without its backend")
            assert MicrophoneCapture.list_devices() == []
            """
        )
