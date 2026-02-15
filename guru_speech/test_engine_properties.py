"""
Property-based tests for GuruSpeechEngine module.

This module contains property tests that verify universal correctness properties
of the main engine facade and pipeline orchestration.
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from .exceptions import (
    GuruSpeechError,
    AudioCaptureError,
    ModelLoadError,
    TranscriptionError,
    CommandInterpretationError
)
from .models import TranscriptionResult, TranscriptionSegment


# Strategy for generating error messages
error_messages = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")),
    min_size=5,
    max_size=100
).filter(lambda x: x.strip() and len(x.strip()) > 0)

# Strategy for generating exception types
exception_types = st.sampled_from([
    ValueError,
    RuntimeError,
    IOError,
    OSError,
    Exception
])

# Strategy for generating file paths
file_paths = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/_.-"),
    min_size=5,
    max_size=50
).filter(lambda x: x.strip() and len(x.strip()) > 0 and not x.startswith("/"))


@settings(max_examples=100, deadline=None)
@given(
    error_message=error_messages,
    exception_type=exception_types,
    file_path=file_paths
)
def test_error_context_preservation_file_transcription(
    error_message,
    exception_type,
    file_path
):
    """
    Feature: guru-speech-engine, Property 5: Error Context Preservation
    
    For any component failure during audio processing, the Guru_Speech_Engine 
    should return an error that includes the original error message and 
    identifies which component failed.
    
    **Validates: Requirements 10.1, 10.4**
    
    This property verifies that:
    1. When any component in the pipeline fails with an error
    2. The GuruSpeechEngine catches and wraps the error
    3. The resulting error preserves the original error message
    4. The resulting error identifies which component failed
    5. The error chain is maintained (original_error is preserved)
    """
    # Create an original error with the generated message
    original_error = exception_type(error_message)
    
    # Test error preservation in file transcription pipeline
    # Patch at the module level where it's imported
    with patch('guru_speech.WhisperTranscriber') as mock_transcriber_class:
        mock_transcriber = Mock()
        mock_transcriber_class.return_value = mock_transcriber
        
        with patch('guru_speech.FileCapture') as mock_file_capture:
            # Simulate AudioCaptureError from FileCapture
            mock_instance = Mock()
            mock_instance.capture.side_effect = AudioCaptureError(
                error_message,
                original_error=original_error
            )
            mock_file_capture.return_value = mock_instance
            
            # Import after patching
            from . import GuruSpeechEngine
            
            # Create engine (this should succeed with mocked transcriber)
            engine = GuruSpeechEngine()
            
            # Attempt transcription - should raise error
            with pytest.raises(GuruSpeechError) as exc_info:
                engine.transcribe_file(file_path)
            
            # Verify error context preservation
            error = exc_info.value
            
            # The error should be an AudioCaptureError (subclass of GuruSpeechError)
            assert isinstance(error, AudioCaptureError)
            
            # The component should be identified
            assert error.component == "AudioCapture"
            
            # The original error should be preserved
            assert error.original_error is not None
            assert error.original_error == original_error
            
            # The error message should contain context
            error_str = str(error)
            assert "AudioCapture" in error_str


@settings(max_examples=100, deadline=None)
@given(
    error_message=error_messages,
    exception_type=exception_types
)
def test_error_context_preservation_transcription(error_message, exception_type):
    """
    Feature: guru-speech-engine, Property 5: Error Context Preservation
    
    Verify that transcription errors preserve context.
    
    **Validates: Requirements 10.1, 10.4**
    """
    # Create an original error
    original_error = exception_type(error_message)
    
    # Mock the transcriber to raise an error
    with patch('guru_speech.WhisperTranscriber') as mock_transcriber_class:
        mock_transcriber = Mock()
        mock_transcriber.transcribe.side_effect = TranscriptionError(
            error_message,
            original_error=original_error
        )
        mock_transcriber_class.return_value = mock_transcriber
        
        # Import after patching
        from . import GuruSpeechEngine
        
        # Create engine
        engine = GuruSpeechEngine()
        
        # Mock file capture to return valid audio
        with patch('guru_speech.FileCapture') as mock_file_capture:
            mock_capture_instance = Mock()
            mock_capture_instance.capture.return_value = (
                np.zeros(16000, dtype=np.float32),
                16000
            )
            mock_file_capture.return_value = mock_capture_instance
            
            # Attempt transcription - should raise error
            with pytest.raises(GuruSpeechError) as exc_info:
                engine.transcribe_file("test.wav")
            
            # Verify error context preservation
            error = exc_info.value
            
            # The error should be a TranscriptionError (subclass of GuruSpeechError)
            assert isinstance(error, TranscriptionError)
            
            # The component should be identified
            assert error.component == "Transcription"
            
            # The original error should be preserved
            assert error.original_error is not None
            assert error.original_error == original_error
            
            # The error message should contain context
            error_str = str(error)
            assert "Transcription" in error_str


@settings(max_examples=100, deadline=None)
@given(
    error_message=error_messages,
    exception_type=exception_types
)
def test_error_context_preservation_command_interpretation(error_message, exception_type):
    """
    Feature: guru-speech-engine, Property 5: Error Context Preservation
    
    Verify that command interpretation errors preserve context.
    
    **Validates: Requirements 10.1, 10.4**
    """
    # Create an original error
    original_error = exception_type(error_message)
    
    # Create a valid transcription result
    transcription = TranscriptionResult(
        text="test command",
        language="en",
        confidence=0.9,
        segments=[],
        duration=1.0
    )
    
    # Mock the transcriber
    with patch('guru_speech.WhisperTranscriber') as mock_transcriber_class:
        mock_transcriber = Mock()
        mock_transcriber_class.return_value = mock_transcriber
        
        # Import after patching
        from . import GuruSpeechEngine
        
        engine = GuruSpeechEngine()
        
        with patch.object(engine.command_interpreter, 'interpret') as mock_interpret:
            mock_interpret.side_effect = original_error
            
            # Attempt command interpretation - should raise error
            with pytest.raises(GuruSpeechError) as exc_info:
                engine.interpret_command(transcription)
            
            # Verify error context preservation
            error = exc_info.value
            
            # The error should be a GuruSpeechError
            assert isinstance(error, GuruSpeechError)
            
            # The component should be identified
            assert error.component == "GuruSpeechEngine"
            
            # The original error should be preserved
            assert error.original_error is not None
            assert error.original_error == original_error
            
            # The error message should contain context
            error_str = str(error)
            assert "GuruSpeechEngine" in error_str


@settings(max_examples=100, deadline=None)
@given(
    error_message=error_messages,
    exception_type=exception_types,
    duration=st.floats(min_value=0.1, max_value=10.0)
)
def test_error_context_preservation_microphone_capture(
    error_message,
    exception_type,
    duration
):
    """
    Feature: guru-speech-engine, Property 5: Error Context Preservation
    
    Verify that microphone capture errors preserve context.
    
    **Validates: Requirements 10.1, 10.4**
    """
    # Create an original error
    original_error = exception_type(error_message)
    
    # Mock WhisperTranscriber first to avoid loading the model
    with patch('guru_speech.WhisperTranscriber') as mock_transcriber_class:
        mock_transcriber = Mock()
        mock_transcriber_class.return_value = mock_transcriber
        
        # Mock the microphone capture to raise an error
        with patch('guru_speech.MicrophoneCapture') as mock_mic_capture:
            mock_instance = Mock()
            mock_instance.capture.side_effect = AudioCaptureError(
                error_message,
                original_error=original_error
            )
            mock_mic_capture.return_value = mock_instance
            
            # Import after patching
            from . import GuruSpeechEngine
            
            # Create engine
            engine = GuruSpeechEngine()
            
            # Attempt microphone transcription - should raise error
            with pytest.raises(GuruSpeechError) as exc_info:
                engine.transcribe_microphone(duration=duration)
            
            # Verify error context preservation
            error = exc_info.value
            
            # The error should be an AudioCaptureError (subclass of GuruSpeechError)
            assert isinstance(error, AudioCaptureError)
            
            # The component should be identified
            assert error.component == "AudioCapture"
            
            # The original error should be preserved
            assert error.original_error is not None
            assert error.original_error == original_error
            
            # The error message should contain context
            error_str = str(error)
            assert "AudioCapture" in error_str


@settings(max_examples=100, deadline=None)
@given(
    error_message=error_messages,
    exception_type=exception_types
)
def test_error_context_preservation_noise_reduction(error_message, exception_type):
    """
    Feature: guru-speech-engine, Property 5: Error Context Preservation
    
    Verify that noise reduction errors preserve context.
    
    **Validates: Requirements 10.1, 10.4**
    """
    # Create an original error
    original_error = exception_type(error_message)
    
    # Mock WhisperTranscriber first to avoid loading the model
    with patch('guru_speech.WhisperTranscriber') as mock_transcriber_class:
        mock_transcriber = Mock()
        mock_transcriber_class.return_value = mock_transcriber
        
        # Mock the noise cleaner to raise an error
        with patch('guru_speech.NoiseCleaner') as mock_noise_cleaner_class:
            mock_noise_cleaner = Mock()
            mock_noise_cleaner.clean.side_effect = original_error
            mock_noise_cleaner_class.return_value = mock_noise_cleaner
            
            # Import after patching
            from . import GuruSpeechEngine
            
            # Create engine with noise reduction enabled
            engine = GuruSpeechEngine(enable_noise_reduction=True)
            
            # Mock file capture to return valid audio
            with patch('guru_speech.FileCapture') as mock_file_capture:
                mock_capture_instance = Mock()
                mock_capture_instance.capture.return_value = (
                    np.zeros(16000, dtype=np.float32),
                    16000
                )
                mock_file_capture.return_value = mock_capture_instance
                
                # Attempt transcription - should raise error
                with pytest.raises(GuruSpeechError) as exc_info:
                    engine.transcribe_file("test.wav")
                
                # Verify error context preservation
                error = exc_info.value
                
                # The error should be a GuruSpeechError
                assert isinstance(error, GuruSpeechError)
                
                # The component should be identified (GuruSpeechEngine wraps it)
                assert error.component == "GuruSpeechEngine"
                
                # The original error should be preserved
                assert error.original_error is not None
                assert error.original_error == original_error
                
                # The error message should contain context
                error_str = str(error)
                assert "GuruSpeechEngine" in error_str


@settings(max_examples=100, deadline=None)
@given(
    num_requests=st.integers(min_value=2, max_value=10),
    file_paths=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/_.-"),
            min_size=5,
            max_size=50
        ).filter(lambda x: x.strip() and len(x.strip()) > 0 and not x.startswith("/")),
        min_size=2,
        max_size=10
    )
)
def test_model_reuse_across_requests(num_requests, file_paths):
    """
    Feature: guru-speech-engine, Property 6: Model Reuse Across Requests
    
    For any sequence of transcription requests to the same GuruSpeechEngine instance,
    the Whisper model should be loaded exactly once and reused for all subsequent requests.
    
    **Validates: Requirements 11.3**
    
    This property verifies that:
    1. When a GuruSpeechEngine instance is created, the model is loaded once
    2. When multiple transcription requests are made to the same instance
    3. The model is NOT reloaded for each request
    4. The same model instance is reused across all requests
    5. This holds regardless of the number of requests or input sources
    """
    # Ensure we have enough file paths for the number of requests
    if len(file_paths) < num_requests:
        file_paths = file_paths * ((num_requests // len(file_paths)) + 1)
    file_paths = file_paths[:num_requests]
    
    # Track model instantiation count
    model_instantiation_count = 0
    original_whisper_model = None
    
    def mock_whisper_model_init(*args, **kwargs):
        nonlocal model_instantiation_count, original_whisper_model
        model_instantiation_count += 1
        
        # Create a mock model instance
        mock_model = MagicMock()
        
        # Mock the transcribe method to return valid results
        def mock_transcribe(audio, beam_size=5, language=None):
            # Create mock segment
            mock_segment = MagicMock()
            mock_segment.text = "test transcription"
            mock_segment.start = 0.0
            mock_segment.end = 1.0
            mock_segment.avg_logprob = -0.5
            
            # Create mock info
            mock_info = MagicMock()
            mock_info.language = language or "en"
            
            return iter([mock_segment]), mock_info
        
        mock_model.transcribe = mock_transcribe
        original_whisper_model = mock_model
        return mock_model
    
    # Patch WhisperModel at the module level where it's imported
    with patch('guru_speech.speech.WhisperModel', side_effect=mock_whisper_model_init):
        # Import after patching
        from . import GuruSpeechEngine
        
        # Create a single engine instance
        engine = GuruSpeechEngine()
        
        # Verify model was loaded exactly once during initialization
        assert model_instantiation_count == 1, \
            f"Model should be loaded once during initialization, but was loaded {model_instantiation_count} times"
        
        # Store the initial model instance
        initial_model = engine.transcriber.model
        assert initial_model is not None, "Model should be loaded after initialization"
        assert initial_model is original_whisper_model, "Model should be the one we created"
        
        # Mock file capture to return valid audio for each request
        with patch('guru_speech.FileCapture') as mock_file_capture_class:
            def create_mock_capture(file_path):
                mock_capture = Mock()
                # Return different audio data for each file to simulate real usage
                audio_length = 16000 + (hash(file_path) % 16000)
                mock_capture.capture.return_value = (
                    np.random.randn(audio_length).astype(np.float32) * 0.1,
                    16000
                )
                return mock_capture
            
            mock_file_capture_class.side_effect = create_mock_capture
            
            # Make multiple transcription requests
            for i in range(num_requests):
                result = engine.transcribe_file(file_paths[i])
                
                # Verify the result is valid
                assert result.text is not None
                assert result.language is not None
                assert 0.0 <= result.confidence <= 1.0
                assert result.duration >= 0.0
                
                # Verify model was NOT reloaded
                assert model_instantiation_count == 1, \
                    f"Model should not be reloaded on request {i+1}, but instantiation count is {model_instantiation_count}"
                
                # Verify the same model instance is still being used
                assert engine.transcriber.model is initial_model, \
                    f"Model instance should remain the same across requests, but changed on request {i+1}"
        
        # Final verification: model was loaded exactly once for all requests
        assert model_instantiation_count == 1, \
            f"Model should be loaded exactly once for {num_requests} requests, but was loaded {model_instantiation_count} times"
