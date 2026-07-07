"""Unit tests for speech engine exceptions."""

from Agent_Guru.speech.exceptions import (
    GuruSpeechError,
    AudioInputError,
    AudioProcessingError,
    WakeWordDetectionError,
    TranscriptionError,
    VoiceBiometricError,
    EmotionDetectionError,
    TTSError,
    VoiceCloningError,
    CommandParsingError,
    ContextManagementError,
    StreamingError,
    ModelLoadError,
    ConfigurationError,
)


class TestGuruSpeechError:
    """Tests for base GuruSpeechError exception."""
    
    def test_base_exception_message(self):
        """Test base exception with message."""
        error = GuruSpeechError("Test error message")
        assert str(error) == "Test error message"  # nosec B101
    
    def test_base_exception_inheritance(self):
        """Test base exception inherits from Exception."""
        error = GuruSpeechError("Test")
        assert isinstance(error, Exception)  # nosec B101


class TestComponentExceptions:
    """Tests for component-specific exceptions."""
    
    def test_audio_input_error(self):
        """Test AudioInputError formatting."""
        error = AudioInputError("Microphone not found")
        assert str(error) == "Microphone not found"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_audio_processing_error(self):
        """Test AudioProcessingError formatting."""
        error = AudioProcessingError("Failed to reduce noise")
        assert str(error) == "Failed to reduce noise"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_wake_word_detection_error(self):
        """Test WakeWordDetectionError formatting."""
        error = WakeWordDetectionError("Wake word model not loaded")
        assert str(error) == "Wake word model not loaded"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_transcription_error(self):
        """Test TranscriptionError formatting."""
        error = TranscriptionError("STT model failed")
        assert str(error) == "STT model failed"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_voice_biometric_error(self):
        """Test VoiceBiometricError formatting."""
        error = VoiceBiometricError("Voice verification failed")
        assert str(error) == "Voice verification failed"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_emotion_detection_error(self):
        """Test EmotionDetectionError formatting."""
        error = EmotionDetectionError("Emotion model not available")
        assert str(error) == "Emotion model not available"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_tts_error(self):
        """Test TTSError formatting."""
        error = TTSError("TTS synthesis failed")
        assert str(error) == "TTS synthesis failed"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_voice_cloning_error(self):
        """Test VoiceCloningError formatting."""
        error = VoiceCloningError("Voice cloning training failed")
        assert str(error) == "Voice cloning training failed"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_command_parsing_error(self):
        """Test CommandParsingError formatting."""
        error = CommandParsingError("Command not recognized")
        assert str(error) == "Command not recognized"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_context_management_error(self):
        """Test ContextManagementError formatting."""
        error = ContextManagementError("Context resolution failed")
        assert str(error) == "Context resolution failed"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_streaming_error(self):
        """Test StreamingError formatting."""
        error = StreamingError("Audio stream interrupted")
        assert str(error) == "Audio stream interrupted"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_model_load_error(self):
        """Test ModelLoadError formatting."""
        error = ModelLoadError("Failed to load Whisper model")
        assert str(error) == "Failed to load Whisper model"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101
    
    def test_configuration_error(self):
        """Test ConfigurationError formatting."""
        error = ConfigurationError("Invalid sample rate")
        assert str(error) == "Invalid sample rate"  # nosec B101
        assert isinstance(error, GuruSpeechError)  # nosec B101


class TestExceptionChaining:
    """Tests for exception chaining."""
    
    def test_exception_chaining_with_cause(self):
        """Test exception chaining with __cause__."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise TranscriptionError("Transcription failed") from e
        except TranscriptionError as error:
            assert str(error) == "Transcription failed"  # nosec B101
            assert isinstance(error.__cause__, ValueError)  # nosec B101
            assert str(error.__cause__) == "Original error"  # nosec B101
    
    def test_exception_chaining_preserves_context(self):
        """Test exception chaining preserves context."""
        try:
            try:
                raise IOError("File not found")
            except IOError as e:
                raise ModelLoadError("Model file missing") from e
        except ModelLoadError as error:
            assert str(error) == "Model file missing"  # nosec B101
            assert isinstance(error.__context__, IOError)  # nosec B101
    
    def test_nested_exception_hierarchy(self):
        """Test nested exception hierarchy."""
        try:
            try:
                raise AudioInputError("Mic error")
            except AudioInputError as e:
                raise AudioProcessingError("Processing failed") from e
        except AudioProcessingError as error:
            assert isinstance(error, GuruSpeechError)  # nosec B101
            assert isinstance(error.__cause__, GuruSpeechError)  # nosec B101
            assert isinstance(error.__cause__, AudioInputError)  # nosec B101


class TestExceptionFormatting:
    """Tests for exception message formatting."""
    
    def test_exception_with_formatted_message(self):
        """Test exception with formatted message."""
        device_id = 42
        error = AudioInputError(f"Device {device_id} not available")
        assert str(error) == "Device 42 not available"  # nosec B101
    
    def test_exception_with_multiline_message(self):
        """Test exception with multiline message."""
        error = ConfigurationError(
            "Invalid configuration:\n"
            "- sample_rate must be positive\n"
            "- channels must be 1 or 2"
        )
        assert "Invalid configuration:" in str(error)  # nosec B101
        assert "sample_rate must be positive" in str(error)  # nosec B101
    
    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        error = GuruSpeechError("")
        assert str(error) == ""  # nosec B101
    
    def test_exception_repr(self):
        """Test exception repr."""
        error = TTSError("Synthesis failed")
        repr_str = repr(error)
        assert "TTSError" in repr_str  # nosec B101
        assert "Synthesis failed" in repr_str  # nosec B101
