"""
Guru Speech Engine - Custom speech recognition system with Whisper, noise reduction, and command detection.

This package provides a complete audio processing pipeline:
1. Audio Capture: Real-time microphone input or file-based audio
2. Noise Reduction: Pre-processing using noisereduce library
3. Speech Transcription: faster-whisper with int8 quantization
4. Command Interpretation: Pattern matching to map transcriptions to agent actions
"""

import logging
import asyncio
from typing import Optional

from .models import TranscriptionResult, CommandResult
from .noise import NoiseCleaner
from .speech import WhisperTranscriber
from .commands import CommandInterpreter
from .capture import MicrophoneCapture, FileCapture
from .exceptions import GuruSpeechError, AudioCaptureError, ModelLoadError, TranscriptionError
from .wake_word import WakeWordDetector, WakeWordEvent, WakeWordError
from .vad import VoiceActivityDetector, VADResult, VADError
from .tts import TextToSpeech, TTSConfig, TTSError
from .metrics import PerformanceMonitor, get_monitor, reset_monitor
from .biometric import VoiceBiometricAuthenticator, VoiceProfile, AuthenticationResult, BiometricError
from .streaming import StreamingTranscriber, StreamingConfig, AudioStreamIterator, stream_transcribe, StreamingError

__version__ = "0.1.0"
__author__ = "Guru Team"

# Configure logging
logger = logging.getLogger("guru_speech")


class GuruSpeechEngine:
    """
    Main facade for the Guru Speech Engine.
    Coordinates audio capture, noise reduction, transcription, and command interpretation.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        compute_type: str = "int8",
        beam_size: int = 5,
        enable_noise_reduction: bool = True,
        noise_stationary: bool = True,
        noise_prop_decrease: float = 1.0,
        sample_rate: int = 16000
    ):
        """
        Initialize the speech engine.
        
        Args:
            model_path: Path to custom model weights (None for default Whisper small)
            compute_type: Compute type for faster-whisper ("int8", "float16", "float32")
            beam_size: Beam size for decoding (higher = more accurate but slower)
            enable_noise_reduction: Whether to apply noise reduction
            noise_stationary: Whether to use stationary noise reduction
            noise_prop_decrease: Proportion of noise to reduce (0.0 to 1.0)
            sample_rate: Sample rate for audio capture in Hz
        """
        logger.info("Initializing Guru Speech Engine")
        
        self.enable_noise_reduction = enable_noise_reduction
        self.sample_rate = sample_rate
        
        # Initialize performance monitor
        from .metrics import get_monitor
        self.metrics = get_monitor()
        
        try:
            # Initialize noise cleaner
            if enable_noise_reduction:
                logger.info("Initializing noise cleaner")
                self.noise_cleaner = NoiseCleaner(
                    stationary=noise_stationary,
                    prop_decrease=noise_prop_decrease
                )
            else:
                self.noise_cleaner = None
            
            # Initialize Whisper transcriber
            logger.info(f"Loading Whisper model (compute_type={compute_type}, beam_size={beam_size})")
            self.transcriber = WhisperTranscriber(
                model_size="small",
                model_path=model_path,
                compute_type=compute_type,
                beam_size=beam_size
            )
            
            # Initialize command interpreter
            logger.info("Initializing command interpreter")
            self.command_interpreter = CommandInterpreter()
            
            logger.info("Guru Speech Engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Guru Speech Engine: {e}")
            raise
    
    def transcribe_microphone(
        self,
        duration: Optional[float] = None,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Capture and transcribe audio from microphone.
        
        Args:
            duration: Recording duration in seconds (required for microphone)
            language: Force specific language (None for auto-detect)
            
        Returns:
            TranscriptionResult with text, language, and confidence
            
        Raises:
            GuruSpeechError: If capture or transcription fails
        """
        if duration is None:
            raise GuruSpeechError(
                message="Duration must be specified for microphone capture",
                component="GuruSpeechEngine"
            )
        
        logger.info(f"Starting microphone capture (duration={duration}s)")
        
        try:
            # Capture audio from microphone
            mic_capture = MicrophoneCapture(
                sample_rate=self.sample_rate,
                channels=1
            )
            audio_data, sample_rate = mic_capture.capture(duration=duration)
            
            logger.info(f"Captured {len(audio_data)} samples at {sample_rate}Hz")
            
            # Apply noise reduction if enabled
            if self.enable_noise_reduction and self.noise_cleaner:
                logger.info("Applying noise reduction")
                audio_data = self.noise_cleaner.clean(audio_data, sample_rate)
            
            # Transcribe audio
            logger.info("Transcribing audio")
            result = self.transcriber.transcribe(audio_data, sample_rate, language)
            
            logger.info(f"Transcription complete: '{result.text}' (language={result.language})")
            
            return result
            
        except AudioCaptureError:
            # Re-raise audio capture errors as-is
            raise
        except TranscriptionError:
            # Re-raise transcription errors as-is
            raise
        except GuruSpeechError:
            # Re-raise GuruSpeechError as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error during microphone transcription: {e}")
            raise GuruSpeechError(
                message=f"Failed to transcribe microphone input: {str(e)}",
                component="GuruSpeechEngine",
                original_error=e
            )
    
    def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio from file.
        
        Args:
            file_path: Path to audio file
            language: Force specific language (None for auto-detect)
            
        Returns:
            TranscriptionResult with text, language, and confidence
            
        Raises:
            GuruSpeechError: If file loading or transcription fails
        """
        logger.info(f"Transcribing file: {file_path}")
        
        try:
            # Load audio from file
            file_capture = FileCapture(file_path)
            audio_data, sample_rate = file_capture.capture()
            
            logger.info(f"Loaded {len(audio_data)} samples at {sample_rate}Hz")
            
            # Apply noise reduction if enabled
            if self.enable_noise_reduction and self.noise_cleaner:
                logger.info("Applying noise reduction")
                audio_data = self.noise_cleaner.clean(audio_data, sample_rate)
            
            # Transcribe audio
            logger.info("Transcribing audio")
            result = self.transcriber.transcribe(audio_data, sample_rate, language)
            
            logger.info(f"Transcription complete: '{result.text}' (language={result.language})")
            
            return result
            
        except AudioCaptureError:
            # Re-raise audio capture errors as-is
            raise
        except TranscriptionError:
            # Re-raise transcription errors as-is
            raise
        except GuruSpeechError:
            # Re-raise GuruSpeechError as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file transcription: {e}")
            raise GuruSpeechError(
                message=f"Failed to transcribe file '{file_path}': {str(e)}",
                component="GuruSpeechEngine",
                original_error=e
            )
    
    def interpret_command(
        self,
        transcription: TranscriptionResult
    ) -> CommandResult:
        """
        Interpret transcribed text as a command.
        
        Args:
            transcription: Result from transcription
            
        Returns:
            CommandResult with action_id and parameters
            
        Raises:
            GuruSpeechError: If command interpretation fails
        """
        logger.info(f"Interpreting command: '{transcription.text}'")
        
        try:
            result = self.command_interpreter.interpret(
                transcription.text,
                transcription.language
            )
            
            if result.is_command:
                logger.info(f"Command detected: {result.action_id} with parameters {result.parameters}")
            else:
                logger.info("No command detected, returning raw text")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to interpret command: {e}")
            raise GuruSpeechError(
                message=f"Failed to interpret command from text '{transcription.text}': {str(e)}",
                component="GuruSpeechEngine",
                original_error=e
            )
    
    def process_voice_command(
        self,
        duration: Optional[float] = None,
        source: str = "microphone",
        file_path: Optional[str] = None
    ) -> CommandResult:
        """
        End-to-end: capture audio, transcribe, and interpret command.
        
        Args:
            duration: Recording duration in seconds (required for microphone)
            source: Audio source ("microphone" or "file")
            file_path: Path to audio file (required if source="file")
            
        Returns:
            CommandResult ready for Guru Agent
            
        Raises:
            GuruSpeechError: If any step in the pipeline fails
        """
        logger.info(f"Processing voice command from {source}")
        
        try:
            # Step 1: Capture and transcribe audio
            if source == "microphone":
                transcription = self.transcribe_microphone(duration=duration)
            elif source == "file":
                if file_path is None:
                    raise GuruSpeechError(
                        message="file_path must be specified when source='file'",
                        component="GuruSpeechEngine"
                    )
                transcription = self.transcribe_file(file_path=file_path)
            else:
                raise GuruSpeechError(
                    message=f"Invalid source: {source}. Must be 'microphone' or 'file'",
                    component="GuruSpeechEngine"
                )
            
            # Step 2: Interpret command
            command_result = self.interpret_command(transcription)
            
            logger.info("Voice command processing complete")
            
            return command_result
            
        except GuruSpeechError:
            # Re-raise GuruSpeechError as-is (preserves context)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during voice command processing: {e}")
            raise GuruSpeechError(
                message=f"Failed to process voice command: {str(e)}",
                component="GuruSpeechEngine",
                original_error=e
            )


    async def transcribe_microphone_async(
        self,
        duration: Optional[float] = None,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Async version: Capture and transcribe audio from microphone.

        Args:
            duration: Recording duration in seconds (required for microphone)
            language: Force specific language (None for auto-detect)

        Returns:
            TranscriptionResult with text, language, and confidence

        Raises:
            GuruSpeechError: If capture or transcription fails
        """
        # Run the synchronous method in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.transcribe_microphone(duration=duration, language=language)
        )

    async def transcribe_file_async(
        self,
        file_path: str,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Async version: Transcribe audio from file.

        Args:
            file_path: Path to audio file
            language: Force specific language (None for auto-detect)

        Returns:
            TranscriptionResult with text, language, and confidence

        Raises:
            GuruSpeechError: If file loading or transcription fails
        """
        # Run the synchronous method in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.transcribe_file(file_path=file_path, language=language)
        )

    async def process_voice_command_async(
        self,
        duration: Optional[float] = None,
        source: str = "microphone",
        file_path: Optional[str] = None
    ) -> CommandResult:
        """
        Async version: End-to-end: capture audio, transcribe, and interpret command.

        Args:
            duration: Recording duration in seconds (required for microphone)
            source: Audio source ("microphone" or "file")
            file_path: Path to audio file (required if source="file")

        Returns:
            CommandResult ready for Guru Agent

        Raises:
            GuruSpeechError: If any step in the pipeline fails
        """
        # Run the synchronous method in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.process_voice_command(
                duration=duration,
                source=source,
                file_path=file_path
            )
        )



__all__ = [
    "__version__",
    "GuruSpeechEngine",
    "TranscriptionResult",
    "CommandResult",
    "GuruSpeechError",
    "AudioCaptureError",
    "ModelLoadError",
    "TranscriptionError",
]
