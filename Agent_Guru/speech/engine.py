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
from typing import Any

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
from Agent_Guru.speech.context.context_manager import (
    ContextNotFoundError,
    ConversationContextManager,
)
from Agent_Guru.speech.emotion.emotion_detector import EmotionDetector
from Agent_Guru.speech.exceptions import EmotionDetectionError, GuruSpeechError
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
    # None means emotion could not be measured for this utterance, and
    # emotion_error says why. It is deliberately not a NEUTRAL placeholder:
    # a caller must be able to tell "calm, and we measured that" from "we
    # could not tell", or it would comfort or reassure the user on the
    # strength of a reading that was never taken.
    emotion: EmotionResult | None
    command: CommandResult | None
    response_text: str | None
    response_audio: np.ndarray | None
    personality: PersonalityType
    context_id: str | None
    processing_time_ms: float

    # BUG FIX: the pipeline used to route a recognised command and then
    # discard the routing result, logging any failure and returning a result
    # indistinguishable from success. The user would hear a normal reply
    # while the action never happened. These fields let the caller tell the
    # user the truth ("I could not do that") instead of silently pretending.
    #
    # command_executed is None when the utterance was not a command at all,
    # True when it was routed and succeeded, False when it failed or was
    # dropped; command_error then carries the reason.
    command_executed: bool | None = None
    command_error: str | None = None

    # Emotion used to be detected inside the same try as transcription, so a
    # detector failure (librosa not installed, detector not initialised)
    # raised GuruSpeechError and threw away a transcription that had already
    # succeeded: the user was understood perfectly and got nothing back
    # because Guru could not tell how they felt. Emotion is a secondary
    # signal, so like command routing above it is now reported, not fatal.
    emotion_error: str | None = None


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
            processed_audio = await self._preprocess_audio(audio)

            # Step 2: Detect personality from wake word if not provided
            personality = await self._resolve_personality(processed_audio, personality)
            self._current_personality = personality

            # Step 3-4: Transcription + emotion
            transcription = self.transcribe_with_personality(processed_audio, personality)
            emotion, emotion_error = self._detect_turn_emotion(processed_audio)

            # Step 5: Command recognition + routing
            command, command_executed, command_error = await self._process_command(
                transcription,
            )

            # Step 6: Context management + memory
            await self._update_context(transcription, emotion, personality)

            processing_time = (time.time() - start_time) * 1000

            with self._state_lock:
                self._state = EngineState.READY

            return VoiceInteractionResult(
                transcription=transcription,
                emotion=emotion,
                command=command,
                response_text=None,
                response_audio=None,
                personality=personality,
                context_id=self._current_context_id,
                processing_time_ms=processing_time,
                command_executed=command_executed,
                command_error=command_error,
                emotion_error=emotion_error,
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

    # ------------------------------------------------------------------
    # process_voice_input helpers (extracted for complexity reduction)
    # ------------------------------------------------------------------

    async def _preprocess_audio(self, audio: np.ndarray) -> np.ndarray:
        """Preprocess audio through processor and noise cancellation."""
        if self.audio_processor is None:
            msg = "Audio processor not initialized"
            raise RuntimeError(msg)
        if self.noise_cancellation is None:
            msg = "Noise cancellation not initialized"
            raise RuntimeError(msg)
        processed = await self.audio_processor.process_chunk(audio)
        return await self.noise_cancellation.reduce_noise(processed)

    async def _resolve_personality(
        self, audio: np.ndarray, personality: PersonalityType | None,
    ) -> PersonalityType:
        """Resolve personality from wake word detection if not provided."""
        if personality is not None:
            return personality
        if self.wake_word_detector is None:
            return PersonalityType.GURU
        try:
            wake_word_result = await self.wake_word_detector.detect(audio)
            if wake_word_result:
                return wake_word_result.personality
        except Exception:
            # Non-critical: fall back to the default personality. Logged at
            # debug rather than swallowed outright, so a wake-word detector
            # that is failing on EVERY utterance is visible instead of just
            # quietly making every interaction sound like GURU.
            self.logger.debug("Wake-word detection failed; defaulting to GURU", exc_info=True)
        return PersonalityType.GURU

    def _detect_turn_emotion(
        self, audio: np.ndarray,
    ) -> tuple[EmotionResult | None, str | None]:
        """Detect emotion for one utterance, reporting failure instead of raising.

        Returns:
            (emotion, emotion_error). Exactly one of the two is None.

        """
        # Checked here rather than by catching detect_emotion()'s RuntimeError,
        # so that only this known condition is downgraded and any other
        # RuntimeError from the detector still fails the turn loudly.
        if self.emotion_detector is None:
            self.logger.warning("Emotion detector not initialized - emotion not measured")
            return None, "Emotion detector not initialized"
        try:
            return self.detect_emotion(audio), None
        except EmotionDetectionError as exc:
            self.logger.warning("Emotion not measured for this utterance: %s", exc)
            return None, str(exc)

    async def _process_command(
        self, transcription: Any,
    ) -> tuple[Any, bool | None, str | None]:
        """Parse a command and route it, reporting whether it actually ran.

        Returns:
            (command, command_executed, command_error). command_executed is
            None when the utterance was not a command, True on successful
            execution, False when execution failed or was dropped.

        """
        if not transcription.text:
            return None, None, None
        if self.command_parser is None:
            msg = "Command parser not initialized"
            raise RuntimeError(msg)

        # Pass the transcription's language through. CommandParser stores
        # patterns keyed by (action_id, language) precisely so a command can
        # have a different pattern set per language -- but this, the only
        # call site on the live speech path, omitted the argument, so the
        # parameter always defaulted to "en" and every non-English pattern
        # set was unreachable no matter what was registered.
        #
        # Behaviour is unchanged today: transcribe_with_personality() forces
        # the STT language from config (currently "en"), so this resolves to
        # "en" exactly as before. What changes is that relaxing that forcing
        # now actually reaches the matching patterns instead of silently
        # continuing to match English ones.
        command = self.command_parser.interpret(
            transcription.text,
            language=transcription.language or "en",
        )
        if not (command and command.is_command):
            return command, None, None

        # BUG FIX: a recognised command with no orchestration attached used to
        # be dropped in silence -- the `and self.agent_orchestration` guard
        # simply skipped routing and returned as though all was well.
        if not self.agent_orchestration:
            self.logger.warning(
                "Command %s recognised but no orchestration is attached - not executed",
                getattr(command, "action_id", None),
            )
            return command, False, "No orchestration attached - command not executed"

        # Routing failures stay non-fatal (one failed tool must not kill the
        # whole voice turn) but are now REPORTED rather than swallowed.
        try:
            routing = await self.agent_orchestration.route_command(command)
        except Exception as exc:
            self.logger.exception("Agent orchestration routing failed")
            return command, False, f"Command routing failed: {exc}"

        success = getattr(routing, "success", None)
        if success is None:
            # Unexpected return shape: do not claim success we cannot verify.
            return command, False, "Command routing returned no status"
        if success:
            return command, True, None
        return command, False, getattr(routing, "error", None) or "Command execution failed"

    async def _update_context(
        self,
        transcription: Any,
        emotion: EmotionResult | None,
        personality: PersonalityType,
    ) -> None:
        """Update conversation context and store to memory."""
        turn_emotion = emotion.primary_emotion if emotion is not None else None
        try:
            self._add_user_turn(transcription.text, turn_emotion, personality)
        except ContextNotFoundError:
            # context_manager.clear_context() is public, and clearing the
            # current conversation left this engine holding a dead id. Every
            # later utterance then raised here and was discarded after it had
            # been transcribed, for good, until the process restarted. The
            # conversation was ended on purpose, so continue in a new one.
            self.logger.warning(
                "Conversation context %s no longer exists - starting a new one",
                self._current_context_id,
            )
            self._current_context_id = None
            self._add_user_turn(transcription.text, turn_emotion, personality)

        if self.memory_client:
            try:
                # No emotion state is stored for an unmeasured utterance: a
                # stand-in value would enter the user's emotion history as
                # if it had been observed.
                if emotion is not None:
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
                    emotion=turn_emotion,
                    personality=personality.value,
                )
            except Exception:
                self.logger.exception("Memory storage failed")

    def _add_user_turn(
        self,
        text: str,
        emotion: EmotionType | None,
        personality: PersonalityType,
    ) -> None:
        """Record a user turn, creating the conversation context if there is none."""
        if self.context_manager is None:
            msg = "Context manager not initialized"
            raise RuntimeError(msg)
        if self._current_context_id is None:
            context_id, _ = self.context_manager.create_context(
                user_id="default_user", personality=personality,
            )
            self._current_context_id = context_id
        self.context_manager.add_turn(
            context_id=self._current_context_id,
            speaker="user",
            text=text,
            emotion=emotion,
        )

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
        authentication decisions - all authentication logic lives in
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
                # Called from inside an async context - run in a separate thread.
                #
                # BUG FIX (voice/vision/avatar audit): this previously used
                # `with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:`.
                # ThreadPoolExecutor.__exit__ calls shutdown(wait=True), which
                # blocks until the submitted task actually finishes - even
                # after future.result(timeout=10) has already raised
                # TimeoutError. Verified concretely with a standalone repro:
                # future.result(timeout=0.5) against a 3-second task raised
                # TimeoutError at the correct t=0.5s, but the `with` block's
                # __exit__ did not let that exception escape to the caller
                # until t=3.0s (the full task duration). So the documented
                # "times out after 10s" guarantee was false: a genuinely
                # hung extraction (this method feeds
                # BiometricAuthenticator.authenticate_voice(), which MUST
                # be able to bound how long it waits) would block the
                # caller for however long the runaway task actually took -
                # potentially forever - not 10 seconds.
                #
                # Fix: don't use the pool as a context manager. Shut it down
                # with wait=False so the caller's timeout is honored
                # immediately; the orphaned worker thread finishes (or is
                # abandoned) on its own without blocking this call.
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                try:
                    future = pool.submit(asyncio.run, coro)
                    result: VoiceFeatures = future.result(timeout=10)
                finally:
                    pool.shutdown(wait=False)
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

    def clone_voice(self, audio_samples: list[np.ndarray], voice_id: str) -> Any:
        """Clone voice from audio samples.

        Args:
            audio_samples: List of audio samples (5+ minutes total). Samples
                must be valid float PCM in [-1.0, 1.0]; enrolment rejects
                audio whose measured quality is below the cloner's minimum.
            voice_id: Unique identifier for cloned voice

        Returns:
            The enrolled VoiceModel. The model used to be built by
            enroll_voice() and then DISCARDED here - the caller got None and
            had no way to read the enrolment's quality score, sample count or
            training duration without going back to the cloner.

        Raises:
            RuntimeError: If the voice cloner is not initialised.
            VoiceCloningError: If the audio is insufficient or too low quality.

        """
        if self.voice_cloner is None:
            msg = "Voice cloner not initialized"
            raise RuntimeError(msg)

        model = self.voice_cloner.enroll_voice(audio_samples, voice_id)
        self.logger.info("Voice cloned successfully: %s", voice_id)
        return model

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

        # BUG FIX: stopping the background service used to happen inside the
        # same try/except that also cleared every component reference. If
        # background_service.stop() raised, the exception jumped straight to
        # `except` and NONE of the `self.X = None` assignments below it ever
        # ran -- leaving every other component (audio capture, STT/TTS
        # engines, wake word detector, ...) still referenced by this engine
        # even though `_state` was unconditionally reset to UNINITIALIZED by
        # the `finally` block. A caller trusting get_state() == UNINITIALIZED
        # to mean "safe to initialize() again" would then have a fresh
        # initialize() construct a second generation of every component
        # (new AudioCapture grabbing the same microphone, a new
        # BackgroundServiceManager) while the first generation -- including
        # a background service that never actually stopped -- stayed alive
        # and reachable from nowhere, a resource/thread leak and a source of
        # duplicate audio-device contention. Isolating the one call that can
        # actually raise, and moving the reference-clearing into `finally`,
        # ensures shutdown() always fully releases every component
        # regardless of what any single one of them does.
        try:
            if self.background_service:
                self.background_service.stop()
        except Exception as e:
            self.logger.exception("Error stopping background service during shutdown: %s", e)
        finally:
            # Clear component references -- always, even if a component's
            # own stop() raised above.
            # AudioCapture doesn't need explicit stop - it's synchronous
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

            # ALWAYS set state to UNINITIALIZED, even on error
            with self._state_lock:
                self._state = EngineState.UNINITIALIZED

        self.logger.info("Speech Engine shutdown complete")
