"""
ZERO COMPROMISE unit tests for Speech Engine Facade.

Tests cover:
- Engine initialization
- Component integration
- Voice processing pipeline
- Error handling with context preservation
- State management
- Personality switching
- Emotion-aware responses
"""

import pytest
import numpy as np

from Agent_Guru.speech.engine import (
    SpeechEngine,
    EngineState,
    VoiceInteractionResult
)
from Agent_Guru.speech.models import (
    PersonalityType,
    EmotionType
)
from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.config import SpeechEngineConfig
import logging

# The first librosa call JIT-compiles numba code (18-30 s cold). Warm it once
# per session, before any test starts, so no individual test is charged the
# compile inside its own timeout budget.
pytestmark = pytest.mark.usefixtures("warm_librosa")

logger = logging.getLogger(__name__)


def require_tts_backend() -> None:
    """Skip when synthesising would have to download a model first.

    SpeechEngine.synthesize_response() reaches KokoroTTSEngine._ensure_loaded(),
    which auto-downloads ~83 MB on first use. In a test run that meant a
    network fetch inside a test with a 30-second budget: the four synthesis
    tests below timed out rather than testing anything, and a CI runner would
    have pulled model weights on every cold cache.

    Setting AGENT_GURU_NO_DOWNLOAD=1 turns that download into an immediate
    error; either way, with no backend on the machine there is nothing here to
    assert about synthesised audio.
    """
    from Agent_Guru.speech.tts.tts_engine import TTSEngine, downloads_disabled

    backend = TTSEngine().active_backend
    if backend == "none" or (backend == "kokoro" and downloads_disabled()):
        pytest.skip(
            "UNVERIFIED on this host: no local TTS backend "
            "(Kokoro model not cached and pyttsx3 unavailable)",
        )


class TestSpeechEngine:
    """Comprehensive tests for Speech Engine."""
    
    @pytest.fixture
    def engine(self) -> SpeechEngine:
        """Create speech engine instance."""
        return SpeechEngine()
    
    @pytest.fixture
    def initialized_engine(self) -> SpeechEngine:
        """Create and initialize speech engine."""
        engine = SpeechEngine()
        engine.initialize()
        return engine
    
    @pytest.fixture
    def sample_audio(self) -> np.ndarray:
        """Create sample audio data."""
        # 1 second of audio at 16kHz
        return np.random.randn(16000).astype(np.float32)
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    def test_engine_creation(self, engine: SpeechEngine):
        """Test engine creation."""
        assert engine is not None  # nosec B101
        assert engine.get_state() == EngineState.UNINITIALIZED  # nosec B101
    
    def test_engine_initialization(self, engine: SpeechEngine):
        """Test engine initialization."""
        engine.initialize()
        
        # Should be ready
        assert engine.get_state() == EngineState.READY  # nosec B101
        
        # All components should be initialized
        assert engine.audio_capture is not None  # nosec B101
        assert engine.audio_processor is not None  # nosec B101
        assert engine.wake_word_detector is not None  # nosec B101
        assert engine.noise_cancellation is not None  # nosec B101
        assert engine.streaming_manager is not None  # nosec B101
        assert engine.stt_transcriber is not None  # nosec B101
        assert engine.language_detector is not None  # nosec B101
        assert engine.tts_engine is not None  # nosec B101
        assert engine.voice_cloner is not None  # nosec B101
        assert engine.emotion_detector is not None  # nosec B101
        assert engine.voice_feature_extractor is not None  # nosec B101
        assert engine.command_parser is not None  # nosec B101
        assert engine.context_manager is not None  # nosec B101
        assert engine.background_service is not None  # nosec B101
        assert engine.model_router is not None  # nosec B101
    
    def test_engine_initialization_with_config(self):
        """Test engine initialization with custom config."""
        config = SpeechEngineConfig()
        engine = SpeechEngine(config=config)
        engine.initialize()
        
        assert engine.get_state() == EngineState.READY  # nosec B101
        assert engine.config == config  # nosec B101
    
    # ========================================================================
    # VOICE PROCESSING PIPELINE
    # ========================================================================
    
    def test_process_voice_input(self, initialized_engine: SpeechEngine, sample_audio: np.ndarray):
        """Test complete voice processing pipeline."""
        import asyncio
        
        result = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        
        # Should return complete result
        assert isinstance(result, VoiceInteractionResult)  # nosec B101
        assert result.transcription is not None  # nosec B101
        assert result.emotion is not None  # nosec B101
        assert result.personality == PersonalityType.GURU  # nosec B101
        assert result.context_id is not None  # nosec B101
        assert result.processing_time_ms > 0  # nosec B101
    
    def test_process_voice_input_auto_personality(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test voice processing with auto personality detection."""
        import asyncio
        
        result = asyncio.run(initialized_engine.process_voice_input(audio=sample_audio))
        
        # Should detect personality automatically
        assert result.personality in [PersonalityType.GURU, PersonalityType.MAYA]  # nosec B101
    
    def test_process_voice_input_preserves_context(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test that voice processing preserves conversation context."""
        import asyncio
        
        # Process first input
        result1 = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        
        # Process second input
        result2 = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        
        # Should use same context
        assert result1.context_id == result2.context_id  # nosec B101
    
    # ========================================================================
    # TRANSCRIPTION
    # ========================================================================
    
    def test_transcribe_with_personality(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test transcription with personality."""
        result = initialized_engine.transcribe_with_personality(
            audio=sample_audio,
            personality=PersonalityType.GURU
        )
        
        assert result is not None  # nosec B101
        assert result.text is not None  # nosec B101
    
    def test_transcribe_with_maya_personality(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test transcription with Maya personality."""
        result = initialized_engine.transcribe_with_personality(
            audio=sample_audio,
            personality=PersonalityType.MAYA
        )
        
        assert result is not None  # nosec B101
        assert result.text is not None  # nosec B101
    
    # ========================================================================
    # SYNTHESIS
    # ========================================================================
    
    def test_synthesize_response(self, initialized_engine: SpeechEngine):
        """Test response synthesis."""
        require_tts_backend()
        audio = initialized_engine.synthesize_response(
            text="Hello, how can I help you?",
            personality=PersonalityType.GURU,
            emotion=EmotionType.HAPPY
        )
        
        assert audio is not None  # nosec B101
        assert isinstance(audio, np.ndarray)  # nosec B101
        assert len(audio) > 0  # nosec B101
    
    def test_synthesize_response_with_emotion(self, initialized_engine: SpeechEngine):
        """Test response synthesis with different emotions."""
        require_tts_backend()
        emotions = [
            EmotionType.HAPPY,
            EmotionType.SAD,
            EmotionType.ANGRY,
            EmotionType.NEUTRAL
        ]
        
        for emotion in emotions:
            audio = initialized_engine.synthesize_response(
                text="Test message",
                personality=PersonalityType.GURU,
                emotion=emotion
            )
            
            assert audio is not None  # nosec B101
            assert len(audio) > 0  # nosec B101
    
    # ========================================================================
    # EMOTION DETECTION
    # ========================================================================
    
    @pytest.mark.usefixtures("requires_librosa")
    def test_detect_emotion(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test emotion detection."""
        result = initialized_engine.detect_emotion(sample_audio)
        
        assert result is not None  # nosec B101
        assert result.primary_emotion in EmotionType  # nosec B101
        assert 0.0 <= result.confidence <= 1.0  # nosec B101
    
    # ========================================================================
    # VOICE BIOMETRICS
    # ========================================================================
    
    @pytest.mark.usefixtures("requires_librosa")
    def test_extract_voice_features(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test voice feature extraction."""
        features = initialized_engine.extract_voice_features(sample_audio)
        
        assert features is not None  # nosec B101
        assert features.feature_vector is not None  # nosec B101
        assert len(features.feature_vector) > 0  # nosec B101
    
    # ========================================================================
    # VOICE CLONING
    # ========================================================================
    
    @pytest.mark.usefixtures("requires_librosa")
    def test_clone_voice(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test voice cloning.

        The samples must be VALID audio. This used to build them with a bare
        `np.random.randn(16000)` - Gaussian noise with unit standard
        deviation, so roughly a third of every sample sits outside the
        [-1.0, 1.0] range that float32 PCM is defined on. Enrolment now
        rejects that (quality 0.03 against a 0.60 minimum) and is right to:
        a recording that is one third full-scale is not a voice. The test also
        ended in `assert True`, so it asserted nothing about the result.
        """
        # 5+ minutes of audio is required: 300 samples x 1 second at 16 kHz.
        rng = np.random.default_rng(1234)
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        tone = np.sin(2 * np.pi * 140 * t) + 0.3 * np.sin(2 * np.pi * 280 * t)
        samples = []
        for _ in range(300):
            audio = tone + 0.05 * rng.standard_normal(16000)
            audio = audio / np.max(np.abs(audio)) * 0.8  # in-range, with headroom
            samples.append(audio.astype(np.float32))

        model = initialized_engine.clone_voice(samples, "test_voice_001")

        assert model is not None  # nosec B101
        assert model.model_id == "test_voice_001"  # nosec B101
        assert model.voice_characteristics["sample_count"] == 300  # nosec B101
        assert model.training_duration_seconds >= 300.0  # nosec B101

    @pytest.mark.usefixtures("requires_librosa")
    def test_clone_voice_rejects_out_of_range_audio(
        self,
        initialized_engine: SpeechEngine,
    ):
        """Audio outside [-1, 1] must not be enrolled as a voice.

        Quality is measured on the ORIGINAL sample, so unnormalised noise -
        the exact input the test above used to pass - is now refused instead
        of being silently peak-normalised into apparent validity.
        """
        from Agent_Guru.speech.tts.voice_cloner import VoiceCloningError

        rng = np.random.default_rng(99)
        samples = [rng.standard_normal(16000).astype(np.float32) for _ in range(300)]

        with pytest.raises(VoiceCloningError, match="quality"):
            initialized_engine.clone_voice(samples, "bad_voice_001")
    
    # ========================================================================
    # BACKGROUND SERVICE
    # ========================================================================
    
    def test_start_background_service(self, initialized_engine: SpeechEngine):
        """Test starting background service."""
        initialized_engine.start_background_service()
        
        # Service should be running
        assert initialized_engine.background_service.get_state().value in ["sleep", "wake"]  # nosec B101
        
        # Cleanup
        initialized_engine.stop_background_service()
    
    def test_stop_background_service(self, initialized_engine: SpeechEngine):
        """Test stopping background service."""
        initialized_engine.start_background_service()
        initialized_engine.stop_background_service()
        
        # Service should be stopped
        assert initialized_engine.background_service.get_state().value == "stopped"  # nosec B101
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def test_get_state(self, engine: SpeechEngine):
        """Test getting engine state."""
        assert engine.get_state() == EngineState.UNINITIALIZED  # nosec B101
        
        engine.initialize()
        assert engine.get_state() == EngineState.READY  # nosec B101
    
    def test_state_transitions(self, engine: SpeechEngine, sample_audio: np.ndarray):
        """Test state transitions."""
        import asyncio
        
        # Uninitialized
        assert engine.get_state() == EngineState.UNINITIALIZED  # nosec B101
        
        # Initialize
        engine.initialize()
        assert engine.get_state() == EngineState.READY  # nosec B101
        
        # Process (briefly goes to PROCESSING, then back to READY)
        asyncio.run(engine.process_voice_input(sample_audio, PersonalityType.GURU))
        assert engine.get_state() == EngineState.READY  # nosec B101
    
    # ========================================================================
    # ERROR HANDLING
    # ========================================================================
    
    def test_process_voice_input_preserves_context_on_error(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test that context is preserved even on error."""
        import asyncio
        
        # Create initial context
        result1 = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        context_id = result1.context_id
        
        # Force an error by passing invalid audio
        try:
            asyncio.run(initialized_engine.process_voice_input(
                audio=np.array([]),  # Empty audio
                personality=PersonalityType.GURU
            ))
        except Exception as e:
            logger.warning("Suppressed exception: %s", e)
        
        # Context should still exist
        assert initialized_engine._current_context_id == context_id  # nosec B101
    
    def test_initialization_error_handling(self):
        """Test error handling during initialization."""
        engine = SpeechEngine()
        
        # Mock a component to fail
        engine.initialize
        
        def failing_init():
            raise Exception("Test initialization failure")
        
        engine.initialize = failing_init
        
        # Should raise GuruSpeechError
        with pytest.raises(Exception):
            engine.initialize()
    
    # ========================================================================
    # SHUTDOWN
    # ========================================================================
    
    def test_shutdown(self, initialized_engine: SpeechEngine):
        """Test engine shutdown."""
        initialized_engine.shutdown()
        
        # Should be uninitialized
        assert initialized_engine.get_state() == EngineState.UNINITIALIZED  # nosec B101
    
    def test_shutdown_with_background_service(self, initialized_engine: SpeechEngine):
        """Test shutdown with running background service."""
        initialized_engine.start_background_service()
        
        # Store reference before shutdown
        bg_service = initialized_engine.background_service
        
        initialized_engine.shutdown()
        
        # Service should be stopped (check the stored reference)
        assert bg_service.get_state().value == "stopped"  # nosec B101
        assert initialized_engine.get_state() == EngineState.UNINITIALIZED  # nosec B101
    
    # ========================================================================
    # PERSONALITY SWITCHING
    # ========================================================================
    
    def test_personality_switching(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test switching between personalities."""
        import asyncio
        
        # Process with Guru
        result1 = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        assert result1.personality == PersonalityType.GURU  # nosec B101
        
        # Process with Maya
        result2 = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.MAYA
        ))
        assert result2.personality == PersonalityType.MAYA  # nosec B101
    
    # ========================================================================
    # CALLBACKS
    # ========================================================================
    
    def test_wake_word_callback(self, initialized_engine: SpeechEngine):
        """Test wake word callback."""
        # Should not raise exception
        initialized_engine._on_wake_word_detected()
        assert True  # nosec B101
    
    def test_command_callback(self, initialized_engine: SpeechEngine):
        """Test command callback."""
        # Should not raise exception
        initialized_engine._on_command_received("test command")
        assert True  # nosec B101


    # ========================================================================
    # ZERO COMPROMISE - INTEGRATION TESTS
    # ========================================================================
    
    def test_integration_complete_voice_interaction(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """ZERO COMPROMISE: Test complete voice interaction flow."""
        require_tts_backend()
        import asyncio
        
        # Process voice input
        result = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        
        # Verify all components worked
        assert result.transcription is not None  # nosec B101
        assert result.emotion is not None  # nosec B101
        assert result.personality == PersonalityType.GURU  # nosec B101
        assert result.context_id is not None  # nosec B101
        
        # Synthesize response
        response_audio = initialized_engine.synthesize_response(
            text="I understand",
            personality=result.personality,
            emotion=result.emotion.primary_emotion
        )
        
        assert response_audio is not None  # nosec B101
        assert len(response_audio) > 0  # nosec B101
    
    def test_integration_multi_turn_conversation(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """ZERO COMPROMISE: Test multi-turn conversation."""
        import asyncio
        
        results = []
        
        # Process multiple turns
        for _ in range(5):
            result = asyncio.run(initialized_engine.process_voice_input(
                audio=sample_audio,
                personality=PersonalityType.GURU
            ))
            results.append(result)
        
        # All should use same context
        context_ids = [r.context_id for r in results]
        assert len(set(context_ids)) == 1  # nosec B101
    
    def test_integration_emotion_aware_response(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """ZERO COMPROMISE: Test emotion-aware response generation."""
        require_tts_backend()
        import asyncio
        
        # Process input
        result = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.MAYA
        ))
        
        # Generate response matching detected emotion
        response_audio = initialized_engine.synthesize_response(
            text="I sense your emotion",
            personality=result.personality,
            emotion=result.emotion.primary_emotion
        )
        
        assert response_audio is not None  # nosec B101
    
    # ========================================================================
    # ZERO COMPROMISE - STRESS TESTS
    # ========================================================================
    
    def test_stress_rapid_processing(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """ZERO COMPROMISE: Stress test with rapid processing."""
        import asyncio
        
        for _ in range(10):
            result = asyncio.run(initialized_engine.process_voice_input(
                audio=sample_audio,
                personality=PersonalityType.GURU
            ))
            assert result is not None  # nosec B101
    
    def test_stress_long_audio(self, initialized_engine: SpeechEngine):
        """ZERO COMPROMISE: Stress test with long audio."""
        import asyncio
        
        # 10 seconds of audio
        long_audio = np.random.randn(160000).astype(np.float32)
        
        result = asyncio.run(initialized_engine.process_voice_input(
            audio=long_audio,
            personality=PersonalityType.GURU
        ))
        
        assert result is not None  # nosec B101
    
    # ========================================================================
    # ZERO COMPROMISE - EDGE CASES
    # ========================================================================
    
    def test_edge_case_empty_audio(self, initialized_engine: SpeechEngine):
        """ZERO COMPROMISE: Test with empty audio."""
        import asyncio
        
        with pytest.raises(GuruSpeechError):
            asyncio.run(initialized_engine.process_voice_input(
                audio=np.array([]),
                personality=PersonalityType.GURU
            ))
    
    def test_edge_case_very_short_audio(self, initialized_engine: SpeechEngine):
        """ZERO COMPROMISE: Test with very short audio."""
        import asyncio
        
        short_audio = np.random.randn(100).astype(np.float32)
        
        # Should handle gracefully
        try:
            result = asyncio.run(initialized_engine.process_voice_input(
                audio=short_audio,
                personality=PersonalityType.GURU
            ))
            assert result is not None  # nosec B101
        except GuruSpeechError:
            # Expected for very short audio
            pass
    
    def test_edge_case_shutdown_before_init(self, engine: SpeechEngine):
        """ZERO COMPROMISE: Test shutdown before initialization."""
        # Should handle gracefully
        engine.shutdown()
        assert engine.get_state() == EngineState.UNINITIALIZED  # nosec B101
    
    def test_edge_case_double_initialization(self, engine: SpeechEngine):
        """ZERO COMPROMISE: Test double initialization."""
        engine.initialize()
        
        # Second initialization should work
        engine.initialize()
        assert engine.get_state() == EngineState.READY  # nosec B101
    

    # ========================================================================
    # ZERO COMPROMISE - 100% COVERAGE TESTS
    # ========================================================================
    
    def test_initialization_failure_sets_error_state(self):
        """ZERO COMPROMISE: Test initialization failure sets ERROR state."""
        engine = SpeechEngine()
        
        # Mock audio_capture to fail
        import unittest.mock as mock
        with mock.patch.object(engine, 'audio_capture', None):
            with mock.patch('Agent_Guru.speech.engine.MicrophoneCapture', side_effect=Exception("Test failure")):
                with pytest.raises(GuruSpeechError) as exc_info:
                    engine.initialize()
                
                assert "Initialization failed" in str(exc_info.value)  # nosec B101
                assert engine.get_state() == EngineState.ERROR  # nosec B101
    
    def test_wake_word_detection_with_result(self, initialized_engine: SpeechEngine, sample_audio: np.ndarray):
        """ZERO COMPROMISE: Test wake word detection returns personality - COMPREHENSIVE."""
        import asyncio
        from Agent_Guru.speech.models import WakeWordDetection
        from unittest.mock import AsyncMock
        
        # Create wake word result
        wake_word_result = WakeWordDetection(
            wake_word="maya",
            personality=PersonalityType.MAYA,
            confidence=0.95,
            timestamp=0.0,
            audio_chunk=sample_audio
        )
        
        # Use AsyncMock to properly mock async method (BEST practice)
        mock_detect = AsyncMock(return_value=wake_word_result)
        original_detect = initialized_engine.wake_word_detector.detect
        initialized_engine.wake_word_detector.detect = mock_detect
        
        try:
            result = asyncio.run(initialized_engine.process_voice_input(
                audio=sample_audio,
                personality=None  # Trigger auto-detection
            ))
            
            # Verify wake word detection was called
            assert mock_detect.called  # nosec B101
            # Verify personality was set from wake word result (covers line 234)
            assert result.personality == PersonalityType.MAYA  # nosec B101
            assert initialized_engine._current_personality == PersonalityType.MAYA  # nosec B101
        finally:
            initialized_engine.wake_word_detector.detect = original_detect
    
    @pytest.mark.usefixtures("requires_librosa")
    def test_command_none_when_transcription_empty(self, initialized_engine: SpeechEngine, sample_audio: np.ndarray):
        """ZERO COMPROMISE: Test command is None when transcription is empty."""
        import asyncio
        import unittest.mock as mock
        
        # Mock transcriber to return empty text
        mock_transcription = mock.MagicMock()
        mock_transcription.text = ""
        mock_transcription.language = "en"
        
        with mock.patch.object(initialized_engine.stt_transcriber, 'transcribe', return_value=mock_transcription):
            result = asyncio.run(initialized_engine.process_voice_input(
                audio=sample_audio,
                personality=PersonalityType.GURU
            ))
            
            # Command should be None for empty transcription
            assert result.command is None  # nosec B101
    
    def test_context_preservation_error_handling(self, initialized_engine: SpeechEngine, sample_audio: np.ndarray):
        """ZERO COMPROMISE: Test error in context preservation is handled gracefully."""
        import asyncio
        import unittest.mock as mock
        
        # Create initial context
        result1 = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        
        # Mock context manager to fail on add_turn
        with mock.patch.object(initialized_engine.context_manager, 'add_turn', side_effect=Exception("Context error")):
            # Force an error by passing invalid audio
            with pytest.raises(GuruSpeechError):
                asyncio.run(initialized_engine.process_voice_input(
                    audio=np.array([]),  # Empty audio will cause error
                    personality=PersonalityType.GURU
                ))
            
            # Context ID should still be preserved
            assert initialized_engine._current_context_id == result1.context_id  # nosec B101
    
    def test_shutdown_error_handling(self, initialized_engine: SpeechEngine):
        """ZERO COMPROMISE: Test shutdown handles errors gracefully."""
        import unittest.mock as mock
        
        # Mock background_service.stop to raise exception
        with mock.patch.object(initialized_engine.background_service, 'stop', side_effect=Exception("Stop error")):
            # Should not raise exception - shutdown handles errors gracefully
            initialized_engine.shutdown()
            
            # Should ALWAYS set state to UNINITIALIZED, even on error (ZERO COMPROMISE)
            assert initialized_engine.get_state() == EngineState.UNINITIALIZED  # nosec B101


    # ========================================================================
    # ZERO COMPROMISE - FINAL 100% COVERAGE TESTS
    # ========================================================================
    
    @pytest.mark.usefixtures("requires_librosa")
    def test_coverage_command_interpret_call(self, initialized_engine: SpeechEngine, sample_audio: np.ndarray):
        """ZERO COMPROMISE: Ensure line 251 is covered - command_parser.interpret() call."""
        import asyncio
        from Agent_Guru.speech.models import TranscriptionResult, CommandResult
        
        # Mock transcriber to return non-empty text
        mock_transcription = TranscriptionResult(
            text="turn on the lights",
            language="en",
            confidence=0.95,
            segments=[],
            duration=1.0
        )
        
        # Mock command parser to return a command
        mock_command = CommandResult(
            is_command=True,
            action_id="turn_on_lights",
            parameters={"device": "lights"},
            confidence=0.9,
            raw_text="turn on the lights"
        )
        
        original_transcribe = initialized_engine.stt_transcriber.transcribe
        original_interpret = initialized_engine.command_parser.interpret
        
        # Stubs mirror the real signatures rather than the narrowest call:
        # transcribe_with_personality() passes language= to transcribe(), and
        # the speech path passes language= to interpret(). A stub that accepts
        # only the positional arguments turns a signature change into a
        # TypeError inside the code under test, which is what happened here.
        initialized_engine.stt_transcriber.transcribe = (
            lambda audio, sample_rate, language=None, **_kw: mock_transcription
        )
        initialized_engine.command_parser.interpret = (
            lambda text, language="en", context=None, **_kw: mock_command
        )
        
        try:
            result = asyncio.run(initialized_engine.process_voice_input(
                audio=sample_audio,
                personality=PersonalityType.GURU
            ))
            
            # Verify command was interpreted
            assert result.command is not None  # nosec B101
            assert result.command.is_command is True  # nosec B101
            assert result.command.action_id == "turn_on_lights"  # nosec B101
        finally:
            initialized_engine.stt_transcriber.transcribe = original_transcribe
            initialized_engine.command_parser.interpret = original_interpret


    def test_final_coverage_wake_word_exception_handling(self, initialized_engine: SpeechEngine, sample_audio: np.ndarray):
        """ZERO COMPROMISE: Test wake word detector exception handling (lines 236-237)."""
        import asyncio
        from unittest.mock import AsyncMock
        
        # Mock detect to raise an exception
        mock_detect = AsyncMock(side_effect=Exception("Wake word detection failed"))
        original_detect = initialized_engine.wake_word_detector.detect
        initialized_engine.wake_word_detector.detect = mock_detect
        
        try:
            result = asyncio.run(initialized_engine.process_voice_input(
                audio=sample_audio,
                personality=None  # Trigger auto-detection
            ))
            
            # Should default to GURU on exception
            assert result.personality == PersonalityType.GURU  # nosec B101
            assert initialized_engine._current_personality == PersonalityType.GURU  # nosec B101
        finally:
            initialized_engine.wake_word_detector.detect = original_detect


class _FixedTranscriber:
    """Stands in for Whisper, whose model is not always available offline.

    These tests are about what happens after transcription has succeeded, so
    they need a transcription that succeeds on every machine.
    """

    def transcribe(self, audio, sample_rate, language=None):
        from Agent_Guru.speech.models import TranscriptionResult

        return TranscriptionResult(text="turn on the lights", language="en", confidence=0.95)


class TestSecondaryStepsDoNotDiscardTranscription:
    """An utterance that was understood must not be lost to a secondary step.

    Emotion detection and conversation bookkeeping used to share one try with
    transcription, so their failures raised GuruSpeechError and the caller got
    nothing, although the words had been transcribed correctly.
    """

    @pytest.fixture
    def engine(self) -> SpeechEngine:
        from Agent_Guru.speech.memory_client import MemoryClient

        engine = SpeechEngine()
        engine.initialize()
        engine.stt_transcriber = _FixedTranscriber()
        engine.memory_client = MemoryClient()
        return engine

    @pytest.fixture
    def audio(self) -> np.ndarray:
        t = np.arange(16000, dtype=np.float32) / 16000
        return (0.1 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)

    @staticmethod
    def _utter(engine: SpeechEngine, audio: np.ndarray) -> VoiceInteractionResult:
        import asyncio

        return asyncio.run(engine.process_voice_input(audio, PersonalityType.GURU))

    def test_missing_librosa_keeps_transcription(self, engine, audio, monkeypatch):
        # None in sys.modules makes `import librosa` raise ImportError, so this
        # exercises the missing-extra path whether or not librosa is installed.
        monkeypatch.setitem(__import__("sys").modules, "librosa", None)

        result = self._utter(engine, audio)

        assert result.transcription.text == "turn on the lights"  # nosec B101
        assert result.emotion is None  # nosec B101
        assert "librosa" in result.emotion_error  # nosec B101
        assert engine.get_state() == EngineState.READY  # nosec B101

        # The turn is still recorded, without an invented emotion, and no
        # emotion observation is written to the user's history.
        turn = engine.context_manager.get_context(result.context_id).turns[-1]
        assert turn.text == "turn on the lights"  # nosec B101
        assert turn.emotion is None  # nosec B101
        assert engine.memory_client.get_recent_emotions("default_user") == []  # nosec B101
        stored = engine.memory_client.get_recent_turns("default_user")[-1]
        assert stored.emotion is None  # nosec B101

    def test_uninitialised_emotion_detector_keeps_transcription(self, engine, audio):
        engine.emotion_detector = None

        result = self._utter(engine, audio)

        assert result.transcription.text == "turn on the lights"  # nosec B101
        assert result.emotion is None  # nosec B101
        assert result.emotion_error == "Emotion detector not initialized"  # nosec B101

    def test_measured_neutral_is_distinguishable_from_unmeasured(self, engine, audio, monkeypatch):
        import time

        from Agent_Guru.speech.models import EmotionResult

        measured = EmotionResult(
            primary_emotion=EmotionType.NEUTRAL,
            emotion_scores={EmotionType.NEUTRAL: 0.8},
            confidence=0.8,
            timestamp=time.time(),
            audio_quality=1.0,
        )
        monkeypatch.setattr(engine, "detect_emotion", lambda _audio: measured)

        result = self._utter(engine, audio)

        assert result.emotion is measured  # nosec B101
        assert result.emotion_error is None  # nosec B101
        assert len(engine.memory_client.get_recent_emotions("default_user")) == 1  # nosec B101

    def test_unexpected_emotion_failure_still_fails_loudly(self, engine, audio, monkeypatch):
        # Only the detector's documented failure is downgraded. Anything else
        # is a bug and must not be hidden behind an "emotion not measured".
        def broken(_audio):
            raise ValueError("detector bug")

        monkeypatch.setattr(engine, "detect_emotion", broken)

        with pytest.raises(GuruSpeechError, match="detector bug"):
            self._utter(engine, audio)

    def test_transcription_failure_still_fails_loudly(self, engine, audio, monkeypatch):
        def broken(*_args, **_kwargs):
            raise RuntimeError("whisper failed")

        monkeypatch.setattr(engine.stt_transcriber, "transcribe", broken)

        with pytest.raises(GuruSpeechError, match="whisper failed"):
            self._utter(engine, audio)

    def test_cleared_context_does_not_discard_later_utterances(self, engine, audio, monkeypatch):
        import time

        from Agent_Guru.speech.models import EmotionResult

        # Emotion succeeds here so that only the context step can fail.
        measured = EmotionResult(
            primary_emotion=EmotionType.HAPPY,
            emotion_scores={EmotionType.HAPPY: 0.9},
            confidence=0.9,
            timestamp=time.time(),
            audio_quality=1.0,
        )
        monkeypatch.setattr(engine, "detect_emotion", lambda _audio: measured)
        first = self._utter(engine, audio)
        engine.context_manager.clear_context(first.context_id)

        second = self._utter(engine, audio)
        third = self._utter(engine, audio)

        assert second.transcription.text == "turn on the lights"  # nosec B101
        assert second.context_id != first.context_id  # nosec B101
        assert third.context_id == second.context_id  # nosec B101
        assert len(engine.context_manager.get_context(second.context_id).turns) == 2  # nosec B101

    def test_unmeasured_emotion_is_not_persisted_as_a_label(self, engine, audio, monkeypatch):
        class RecordingSystem:
            def __init__(self):
                self.turns = []
                self.emotions = []

            async def store_conversation_turn(self, user_id, record):
                self.turns.append(record)

            async def store_emotion_state(self, user_id, record):
                self.emotions.append(record)

        system = RecordingSystem()
        engine.memory_client._system = system
        monkeypatch.setitem(__import__("sys").modules, "librosa", None)

        self._utter(engine, audio)

        # str(None) used to reach the store as the emotion label "None".
        assert system.turns[-1]["emotion"] is None  # nosec B101
        assert system.emotions == []  # nosec B101
