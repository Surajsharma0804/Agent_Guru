"""Main Speech Engine Facade - ZERO COMPROMISE IMPLEMENTATION.

This module provides the main facade for the speech engine, integrating all components:
- Wake word detection (dual personality)
- Speech-to-text transcription
- Emotion detection from voice
- Voice biometric authentication
- Command recognition and parsing
- Text-to-speech synthesis with emotion
- Voice cloning
- Conversation context management
- Background service management
- Battery optimization
"""

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

import numpy as np

from Agent_Guru.speech.agent_orchestration_client import AgentOrchestrationClient

# Component imports
from Agent_Guru.speech.audio.capture import AudioCapture, MicrophoneCapture
from Agent_Guru.speech.audio.noise_cancellation import AdvancedNoiseCancellation
from Agent_Guru.speech.audio.processor import AudioProcessor
from Agent_Guru.speech.audio.streaming import StreamConfig, StreamingAudioManager
from Agent_Guru.speech.audio.wake_word import WakeWordDetector
from Agent_Guru.speech.background_service import BackgroundServiceManager
from Agent_Guru.speech.biometric.voice_features import VoiceFeatureExtractor
from Agent_Guru.speech.commands.command_parser import CommandParser
from Agent_Guru.speech.config import SpeechEngineConfig
from Agent_Guru.speech.context.context_manager import ConversationContextManager
from Agent_Guru.speech.emotion.emotion_detector import EmotionDetector
from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.goal_manager_client import GoalManagerClient
from Agent_Guru.speech.memory_client import MemoryClient
from Agent_Guru.speech.model_router_client import ModelRouterClient
from Agent_Guru.speech.models import (
    CommandResult,
    EmotionResult,
    EmotionType,
    PersonalityType,
    TranscriptionResult,
    VoiceFeatures,
)
from Agent_Guru.speech.stt.language_detector import LanguageDetector
from Agent_Guru.speech.stt.whisper_stt import WhisperTranscriber
from Agent_Guru.speech.tts.tts_engine import CoquiTTSEngine as TTSEngine
from Agent_Guru.speech.tts.voice_cloner import VoiceCloner


class EngineState(Enum):
    """Speech engine state."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass
class VoiceInteractionResult:
    """Result of a complete voice interaction."""

    transcription: TranscriptionResult
    emotion: EmotionResult
    command: CommandResult | None
    response_text: str | None
    response_audio: np.ndarray | None
    personality: PersonalityType
    context_id: str
    processing_time_ms: float


class SpeechEngine:
    """Main Speech Engine Facade - ZERO COMPROMISE.

    Integrates all speech components into a unified interface:
    - Wake word detection (Guru/Maya)
    - Speech-to-text with multi-language support
    - Emotion detection from voice
    - Voice biometric authentication
    - Command recognition
    - Text-to-speech with emotion
    - Voice cloning
    - Conversation context
    - Background service with battery optimization

    Pipeline: capture → process → wake word → STT → emotion → interpret → context → TTS
    """

    def __init__(self, config: SpeechEngineConfig | None = None) -> None:
        """Initialize Speech Engine.

        Args:
            config: Speech engine configuration (uses defaults if None)

        """
        self.config = config or SpeechEngineConfig()
        self._state = EngineState.UNINITIALIZED
        self._state_lock = threading.Lock()

        self.audio_capture: AudioCapture | None = None
        self.audio_processor: AudioProcessor | None = None
        self.wake_word_detector: WakeWordDetector | None = None
        self.noise_cancellation: AdvancedNoiseCancellation | None = None
        self.streaming_manager: StreamingAudioManager | None = None
        self.stt_transcriber: WhisperTranscriber | None = None
        self.language_detector: LanguageDetector | None = None
        self.tts_engine: TTSEngine | None = None
        self.voice_cloner: VoiceCloner | None = None
        self.emotion_detector: EmotionDetector | None = None
        self.voice_feature_extractor: VoiceFeatureExtractor | None = None
        self.command_parser: CommandParser | None = None
        self.context_manager: ConversationContextManager | None = None
        self.background_service: BackgroundServiceManager | None = None
        self.model_router: ModelRouterClient | None = None
        self.agent_orchestration: AgentOrchestrationClient | None = None
        self.memory_client: MemoryClient | None = None
        self.goal_manager_client: GoalManagerClient | None = None

        # Current state
        self._current_personality: PersonalityType | None = None
        self._current_context_id: str | None = None

        # Logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def initialize(self) -> None:
        """Initialize all speech engine components.

        Raises:
            GuruSpeechError: If initialization fails

        """
        with self._state_lock:
            if self._state == EngineState.INITIALIZING:
                return
            self._state = EngineState.INITIALIZING
        try:
            self.logger.info("Initializing Speech Engine...")

            # Initialize audio components
            self.audio_capture = MicrophoneCapture(
                sample_rate=self.config.audio.sample_rate,
                channels=self.config.audio.channels,
            )
            self.audio_processor = AudioProcessor(
                config=self.config.audio_processing,
                sample_rate=self.config.audio.sample_rate,
            )
            self.wake_word_detector = WakeWordDetector()
            self.noise_cancellation = AdvancedNoiseCancellation()

            # Create StreamConfig from our config
            stream_config = StreamConfig()
            stream_config.sample_rate = self.config.audio.sample_rate
            stream_config.channels = self.config.audio.channels
            stream_config.chunk_duration_ms = self.config.streaming.chunk_duration_ms
            stream_config.buffer_size_ms = 500  # Default buffer size
            stream_config.max_latency_ms = self.config.streaming.max_latency_ms
            self.streaming_manager = StreamingAudioManager(config=stream_config)

            # Initialize STT components
            self.stt_transcriber = WhisperTranscriber(model_size=self.config.stt.model_size)
            self.language_detector = LanguageDetector()

            # Initialize TTS components
            self.tts_engine = TTSEngine()
            self.voice_cloner = VoiceCloner()

            # Initialize emotion and biometric components
            self.emotion_detector = EmotionDetector()
            self.voice_feature_extractor = VoiceFeatureExtractor()

            # Initialize command and context components
            self.command_parser = CommandParser()
            self.context_manager = ConversationContextManager()

            # Initialize background service
            self.background_service = BackgroundServiceManager(
                wake_word_callback=self._on_wake_word_detected,
                command_callback=self._on_command_received,
            )

            # Initialize model router
            self.model_router = ModelRouterClient()

            # Initialize integration clients (no external systems required at init)
            self.agent_orchestration = AgentOrchestrationClient()
            self.memory_client = MemoryClient()
            self.goal_manager_client = GoalManagerClient()

            with self._state_lock:
                self._state = EngineState.READY
            self.logger.info("Speech Engine initialized successfully")

        except Exception as e:
            with self._state_lock:
                self._state = EngineState.ERROR
            self.logger.exception("Failed to initialize Speech Engine: %s", e)
            msg = f"Initialization failed: {e}"
            raise GuruSpeechError(msg) from e

    async def process_voice_input(
        self,
        audio: np.ndarray,
        personality: PersonalityType | None = None,
    ) -> VoiceInteractionResult:
        """Process voice input through complete pipeline.

        Pipeline: process → STT → emotion → command → context

        Args:
            audio: Input audio data
            personality: Personality to use (auto-detected if None)

        Returns:
            VoiceInteractionResult with complete interaction data

        Raises:
            GuruSpeechError: If processing fails

        """
        import time

        start_time = time.time()

        try:
            with self._state_lock:
                self._state = EngineState.PROCESSING

            # Step 1: Audio processing
            if self.audio_processor is None:
                msg = "Audio processor not initialized"
                raise RuntimeError(msg)
            if self.noise_cancellation is None:
                msg = "Noise cancellation not initialized"
                raise RuntimeError(msg)

            processed_audio = await self.audio_processor.process_chunk(audio)
            processed_audio = await self.noise_cancellation.reduce_noise(processed_audio)

            # Step 2: Detect personality from wake word if not provided
            if personality is None:
                # Wake word detector has async detect() method
                if self.wake_word_detector is None:
                    personality = PersonalityType.GURU  # Default when not initialized
                else:
                    try:
                        wake_word_result = await self.wake_word_detector.detect(processed_audio)
                        if wake_word_result:
                            personality = wake_word_result.personality
                        else:
                            personality = PersonalityType.GURU  # Default
                    except Exception:
                        personality = PersonalityType.GURU  # Default on error

            self._current_personality = personality

            # Step 3: Speech-to-text transcription
            transcription = self.transcribe_with_personality(processed_audio, personality)

            # Step 4: Emotion detection
            emotion = self.detect_emotion(processed_audio)

            # Step 5: Command recognition
            command = None
            if transcription.text:
                if self.command_parser is None:
                    msg = "Command parser not initialized"
                    raise RuntimeError(msg)
                command = self.command_parser.interpret(transcription.text)

            # Step 5a: Route command to agent orchestration
            if command and command.is_command and self.agent_orchestration:
                try:
                    await self.agent_orchestration.route_command(command)
                except Exception:
                    self.logger.exception("Agent orchestration routing failed")

            # Step 6: Context management
            if self.context_manager is None:
                msg = "Context manager not initialized"
                raise RuntimeError(msg)

            if self._current_context_id is None:
                context_id, _ = self.context_manager.create_context(
                    user_id="default_user",
                    personality=personality,
                )
                self._current_context_id = context_id

            self.context_manager.add_turn(
                context_id=self._current_context_id,
                speaker="user",
                text=transcription.text,
                emotion=emotion.primary_emotion,
            )

            # Step 6a: Store emotion state and conversation turn in memory
            if self.memory_client:
                try:
                    await self.memory_client.store_emotion_state(
                        user_id="default_user",
                        emotion=emotion.primary_emotion,
                        timestamp=datetime.now(tz=UTC),
                        confidence=emotion.confidence,
                    )
                    await self.memory_client.store_conversation_turn(
                        user_id="default_user",
                        speaker="user",
                        text=transcription.text,
                        emotion=emotion.primary_emotion,
                        personality=personality.value,
                    )
                except Exception:
                    self.logger.exception("Memory storage failed")

            # Step 7: Generate response (placeholder - would integrate with LLM)
            response_text = None
            response_audio = None

            processing_time = (time.time() - start_time) * 1000

            with self._state_lock:
                self._state = EngineState.READY

            return VoiceInteractionResult(
                transcription=transcription,
                emotion=emotion,
                command=command,
                response_text=response_text,
                response_audio=response_audio,
                personality=personality,
                context_id=self._current_context_id,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            with self._state_lock:
                self._state = EngineState.ERROR
            self.logger.exception("Voice processing failed: %s", e)

            # Preserve context even on error
            if self._current_context_id and self.context_manager is not None:
                try:
                    self.context_manager.add_turn(
                        context_id=self._current_context_id,
                        speaker="system",
                        text=f"Error: {e!s}",
                        emotion=EmotionType.NEUTRAL,
                    )
                except Exception:
                    self.logger.exception("Failed to record error turn in context")

            msg = f"Voice processing failed: {e}"
            raise GuruSpeechError(msg) from e

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
    ) -> "TranscriptionResult":
        """Transcribe audio to text (alias for transcribe_with_personality).

        This is the primary entry point used by the IntegrationOrchestrator.

        Args:
            audio_data: Audio as float32 numpy array.
            sample_rate: Sample rate in Hz (default 16000).

        Returns:
            TranscriptionResult with text, language, confidence.

        """
        return self.transcribe_with_personality(audio_data, PersonalityType.GURU)

    def transcribe_with_personality(
        self,
        audio: np.ndarray,
        personality: PersonalityType,
    ) -> TranscriptionResult:
        """Transcribe audio with personality-specific settings.

        Args:
            audio: Audio data to transcribe
            personality: Personality type

        Returns:
            TranscriptionResult with transcription

        """
        if self.stt_transcriber is None:
            msg = "STT transcriber not initialized"
            raise RuntimeError(msg)

        # Transcribe with automatic language detection (Whisper handles this)
        result = self.stt_transcriber.transcribe(
            audio,
            self.config.audio.sample_rate,
            language=self.config.stt.language,  # force "en" to stop Hindi misdetection
        )

        self.logger.info(
            "Transcribed with %s personality: %s... (language: %s)",
            personality.value,
            result.text[:50] if result.text else "(empty)",
            result.language,
        )

        return result

    def synthesize_to_array(
        self,
        text: str,
        personality: "PersonalityType",
        emotion: "EmotionType | None" = None,
    ) -> "tuple[np.ndarray, int]":
        """Synthesize speech and return (audio_array, sample_rate).

        This is the primary TTS entry point used by the IntegrationOrchestrator.

        Args:
            text: Text to synthesize.
            personality: Guru or Maya personality.
            emotion: Optional emotion (defaults to NEUTRAL).

        Returns:
            Tuple of (float32 numpy array in [-1, 1], sample_rate_hz).

        """
        if self.tts_engine is None:
            msg = "TTS engine not initialized"
            raise RuntimeError(msg)
        return self.tts_engine.synthesize_to_array(text, personality, emotion)

    def synthesize_response(
        self,
        text: str,
        personality: PersonalityType,
        emotion: EmotionType | None = None,
    ) -> np.ndarray:
        """Synthesize speech response with personality and emotion.

        Args:
            text: Text to synthesize
            personality: Personality type (Guru/Maya)
            emotion: Emotion to express (defaults to NEUTRAL if None)

        Returns:
            Audio data as numpy array

        """
        # Default to NEUTRAL if emotion is None
        if emotion is None:
            emotion = EmotionType.NEUTRAL

        if self.tts_engine is None:
            msg = "TTS engine not initialized"
            raise RuntimeError(msg)

        # Synthesize speech with personality and emotion
        audio, _ = self.tts_engine.synthesize_to_array(
            text=text,
            personality=personality,
            emotion=emotion,
        )

        self.logger.info(
            "Synthesized response with %s personality and %s emotion",
            personality.value,
            emotion.value,
        )

        return audio

    def extract_voice_features(self, audio: np.ndarray) -> VoiceFeatures:
        """Extract voice biometric features.

        FOR SECURITY SYSTEM USE ONLY.  This method is the integration point
        between the speech engine and guru-security-cryptography.  Callers
        outside the security system MUST NOT use this method to make
        authentication decisions – all authentication logic lives in
        ``BiometricAuthenticator`` (Agent_Guru/security/).

        The returned :class:`~Agent_Guru.speech.models.VoiceFeatures` object
        includes ``liveness_score`` and ``is_live`` fields that the
        ``BiometricAuthenticator`` MUST check before accepting an
        authentication attempt.

        Args:
            audio: Raw audio data as a float32 numpy array.

        Returns:
            :class:`~Agent_Guru.speech.models.VoiceFeatures` containing the
            feature vector, quality score, liveness score, and liveness flag.
            Pass this object directly to
            ``BiometricAuthenticator.authenticate_voice()``.

        Raises:
            RuntimeError: If the voice feature extractor has not been
                initialised (call :meth:`initialize` first).
            :class:`~Agent_Guru.speech.exceptions.VoiceBiometricError`:
                If feature extraction fails.

        """
        if self.voice_feature_extractor is None:
            msg = "Voice feature extractor not initialized"
            raise RuntimeError(msg)

        import asyncio
        import concurrent.futures

        coro = self.voice_feature_extractor.extract_features(audio, self.config.audio.sample_rate)

        try:
            # Check if we're inside a running event loop
            try:
                asyncio.get_running_loop()
                is_running = True
            except RuntimeError:
                # RuntimeError("no running event loop") is the expected signal
                is_running = False

            if is_running:
                # Called from inside an async context — run in a separate thread
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    result: VoiceFeatures = future.result(timeout=10)
            else:
                result = asyncio.run(coro)
        except concurrent.futures.TimeoutError as exc:
            msg = "Voice feature extraction timed out after 10s"
            raise RuntimeError(msg) from exc

        return result

    def detect_emotion(self, audio: np.ndarray) -> EmotionResult:
        """Detect emotion from voice.

        Args:
            audio: Audio data

        Returns:
            EmotionResult with detected emotions

        """
        if self.emotion_detector is None:
            msg = "Emotion detector not initialized"
            raise RuntimeError(msg)

        return self.emotion_detector.detect_emotion(audio, self.config.audio.sample_rate)

    def clone_voice(self, audio_samples: list[np.ndarray], voice_id: str) -> None:
        """Clone voice from audio samples.

        Args:
            audio_samples: List of audio samples (5+ minutes total)
            voice_id: Unique identifier for cloned voice

        """
        if self.voice_cloner is None:
            msg = "Voice cloner not initialized"
            raise RuntimeError(msg)

        self.voice_cloner.enroll_voice(audio_samples, voice_id)
        self.logger.info("Voice cloned successfully: %s", voice_id)

    def start_background_service(self) -> None:
        """Start always-on background service."""
        if self.background_service:
            self.background_service.start()
            self.logger.info("Background service started")

    def stop_background_service(self) -> None:
        """Stop background service."""
        if self.background_service:
            self.background_service.stop()
            self.logger.info("Background service stopped")

    def get_state(self) -> EngineState:
        """Get current engine state."""
        with self._state_lock:
            return self._state

    def _on_wake_word_detected(self) -> None:
        """Callback when wake word is detected."""
        self.logger.info("Wake word detected callback")

    def _on_command_received(self, command: str) -> None:
        """Callback when command is received."""
        self.logger.info("Command received callback: %s", command)

    def shutdown(self) -> None:
        """Shutdown speech engine and cleanup resources."""
        self.logger.info("Shutting down Speech Engine...")

        try:
            # Stop background service
            if self.background_service:
                self.background_service.stop()

            # Cleanup components
            # AudioCapture doesn't need explicit stop - it's synchronous
            if self.audio_capture:
                pass  # No stop method needed

            # Clear component references
            self.audio_capture = None
            self.audio_processor = None
            self.wake_word_detector = None
            self.noise_cancellation = None
            self.streaming_manager = None
            self.stt_transcriber = None
            self.language_detector = None
            self.tts_engine = None
            self.voice_cloner = None
            self.emotion_detector = None
            self.voice_feature_extractor = None
            self.command_parser = None
            self.context_manager = None
            self.background_service = None
            self.model_router = None
            self.agent_orchestration = None
            self.memory_client = None
            self.goal_manager_client = None

            self.logger.info("Speech Engine shutdown complete")

        except Exception as e:
            self.logger.exception("Error during shutdown: %s", e)
        finally:
            # ALWAYS set state to UNINITIALIZED, even on error
            with self._state_lock:
                self._state = EngineState.UNINITIALIZED
