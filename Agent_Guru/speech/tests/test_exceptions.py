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
        assert str(error) == "Test error message"
    
    def test_base_exception_inheritance(self):
        """Test base exception inherits from Exception."""
        error = GuruSpeechError("Test")
        assert isinstance(error, Exception)


class TestComponentExceptions:
    """Tests for component-specific exceptions."""
    
    def test_audio_input_error(self):
        """Test AudioInputError formatting."""
        error = AudioInputError("Microphone not found")
        assert str(error) == "Microphone not found"
        assert isinstance(error, GuruSpeechError)
    
    def test_audio_processing_error(self):
        """Test AudioProcessingError formatting."""
        error = AudioProcessingError("Failed to reduce noise")
        assert str(error) == "Failed to reduce noise"
        assert isinstance(error, GuruSpeechError)
    
    def test_wake_word_detection_error(self):
        """Test WakeWordDetectionError formatting."""
        error = WakeWordDetectionError("Wake word model not loaded")
        assert str(error) == "Wake word model not loaded"
        assert isinstance(error, GuruSpeechError)
    
    def test_transcription_error(self):
        """Test TranscriptionError formatting."""
        error = TranscriptionError("STT model failed")
        assert str(error) == "STT model failed"
        assert isinstance(error, GuruSpeechError)
    
    def test_voice_biometric_error(self):
        """Test VoiceBiometricError formatting."""
        error = VoiceBiometricError("Voice verification failed")
        assert str(error) == "Voice verification failed"
        assert isinstance(error, GuruSpeechError)
    
    def test_emotion_detection_error(self):
        """Test EmotionDetectionError formatting."""
        error = EmotionDetectionError("Emotion model not available")
        assert str(error) == "Emotion model not available"
        assert isinstance(error, GuruSpeechError)
    
    def test_tts_error(self):
        """Test TTSError formatting."""
        error = TTSError("TTS synthesis failed")
        assert str(error) == "TTS synthesis failed"
        assert isinstance(error, GuruSpeechError)
    
    def test_voice_cloning_error(self):
        """Test VoiceCloningError formatting."""
        error = VoiceCloningError("Voice cloning training failed")
        assert str(error) == "Voice cloning training failed"
        assert isinstance(error, GuruSpeechError)
    
    def test_command_parsing_error(self):
        """Test CommandParsingError formatting."""
        error = CommandParsingError("Command not recognized")
        assert str(error) == "Command not recognized"
        assert isinstance(error, GuruSpeechError)
    
    def test_context_management_error(self):
        """Test ContextManagementError formatting."""
        error = ContextManagementError("Context resolution failed")
        assert str(error) == "Context resolution failed"
        assert isinstance(error, GuruSpeechError)
    
    def test_streaming_error(self):
        """Test StreamingError formatting."""
        error = StreamingError("Audio stream interrupted")
        assert str(error) == "Audio stream interrupted"
        assert isinstance(error, GuruSpeechError)
    
    def test_model_load_error(self):
        """Test ModelLoadError formatting."""
        error = ModelLoadError("Failed to load Whisper model")
        assert str(error) == "Failed to load Whisper model"
        assert isinstance(error, GuruSpeechError)
    
    def test_configuration_error(self):
        """Test ConfigurationError formatting."""
        error = ConfigurationError("Invalid sample rate")
        assert str(error) == "Invalid sample rate"
        assert isinstance(error, GuruSpeechError)


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
            assert str(error) == "Transcription failed"
            assert isinstance(error.__cause__, ValueError)
            assert str(error.__cause__) == "Original error"
    
    def test_exception_chaining_preserves_context(self):
        """Test exception chaining preserves context."""
        try:
            try:
                raise IOError("File not found")
            except IOError:
                raise ModelLoadError("Model file missing")
        except ModelLoadError as error:
            assert str(error) == "Model file missing"
            assert isinstance(error.__context__, IOError)
    
    def test_nested_exception_hierarchy(self):
        """Test nested exception hierarchy."""
        try:
            try:
                raise AudioInputError("Mic error")
            except AudioInputError as e:
                raise AudioProcessingError("Processing failed") from e
        except AudioProcessingError as error:
            assert isinstance(error, GuruSpeechError)
            assert isinstance(error.__cause__, GuruSpeechError)
            assert isinstance(error.__cause__, AudioInputError)


class TestExceptionFormatting:
    """Tests for exception message formatting."""
    
    def test_exception_with_formatted_message(self):
        """Test exception with formatted message."""
        device_id = 42
        error = AudioInputError(f"Device {device_id} not available")
        assert str(error) == "Device 42 not available"
    
    def test_exception_with_multiline_message(self):
        """Test exception with multiline message."""
        error = ConfigurationError(
            "Invalid configuration:\n"
            "- sample_rate must be positive\n"
            "- channels must be 1 or 2"
        )
        assert "Invalid configuration:" in str(error)
        assert "sample_rate must be positive" in str(error)
    
    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        error = GuruSpeechError("")
        assert str(error) == ""
    
    def test_exception_repr(self):
        """Test exception repr."""
        error = TTSError("Synthesis failed")
        repr_str = repr(error)
        assert "TTSError" in repr_str
        assert "Synthesis failed" in repr_str
