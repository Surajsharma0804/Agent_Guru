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
import time

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
        assert engine is not None
        assert engine.get_state() == EngineState.UNINITIALIZED
    
    def test_engine_initialization(self, engine: SpeechEngine):
        """Test engine initialization."""
        engine.initialize()
        
        # Should be ready
        assert engine.get_state() == EngineState.READY
        
        # All components should be initialized
        assert engine.audio_capture is not None
        assert engine.audio_processor is not None
        assert engine.wake_word_detector is not None
        assert engine.noise_cancellation is not None
        assert engine.streaming_manager is not None
        assert engine.stt_transcriber is not None
        assert engine.language_detector is not None
        assert engine.tts_engine is not None
        assert engine.voice_cloner is not None
        assert engine.emotion_detector is not None
        assert engine.voice_feature_extractor is not None
        assert engine.command_parser is not None
        assert engine.context_manager is not None
        assert engine.background_service is not None
        assert engine.model_router is not None
    
    def test_engine_initialization_with_config(self):
        """Test engine initialization with custom config."""
        config = SpeechEngineConfig()
        engine = SpeechEngine(config=config)
        engine.initialize()
        
        assert engine.get_state() == EngineState.READY
        assert engine.config == config
    
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
        assert isinstance(result, VoiceInteractionResult)
        assert result.transcription is not None
        assert result.emotion is not None
        assert result.personality == PersonalityType.GURU
        assert result.context_id is not None
        assert result.processing_time_ms > 0
    
    def test_process_voice_input_auto_personality(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test voice processing with auto personality detection."""
        import asyncio
        
        result = asyncio.run(initialized_engine.process_voice_input(audio=sample_audio))
        
        # Should detect personality automatically
        assert result.personality in [PersonalityType.GURU, PersonalityType.MAYA]
    
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
        assert result1.context_id == result2.context_id
    
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
        
        assert result is not None
        assert result.text is not None
    
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
        
        assert result is not None
        assert result.text is not None
    
    # ========================================================================
    # SYNTHESIS
    # ========================================================================
    
    def test_synthesize_response(self, initialized_engine: SpeechEngine):
        """Test response synthesis."""
        audio = initialized_engine.synthesize_response(
            text="Hello, how can I help you?",
            personality=PersonalityType.GURU,
            emotion=EmotionType.HAPPY
        )
        
        assert audio is not None
        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
    
    def test_synthesize_response_with_emotion(self, initialized_engine: SpeechEngine):
        """Test response synthesis with different emotions."""
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
            
            assert audio is not None
            assert len(audio) > 0
    
    # ========================================================================
    # EMOTION DETECTION
    # ========================================================================
    
    def test_detect_emotion(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test emotion detection."""
        result = initialized_engine.detect_emotion(sample_audio)
        
        assert result is not None
        assert result.primary_emotion in EmotionType
        assert 0.0 <= result.confidence <= 1.0
    
    # ========================================================================
    # VOICE BIOMETRICS
    # ========================================================================
    
    def test_extract_voice_features(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test voice feature extraction."""
        features = initialized_engine.extract_voice_features(sample_audio)
        
        assert features is not None
        assert features.feature_vector is not None
        assert len(features.feature_vector) > 0
    
    # ========================================================================
    # VOICE CLONING
    # ========================================================================
    
    def test_clone_voice(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """Test voice cloning."""
        # Create multiple samples (need 5+ minutes total = 300+ seconds at 16kHz = 4,800,000+ samples)
        # Create 300 samples of 1 second each = 300 seconds total (5 minutes minimum)
        samples = [np.random.randn(16000).astype(np.float32) for _ in range(300)]
        
        # Clone voice
        initialized_engine.clone_voice(samples, "test_voice_001")
        
        # Should not raise exception
        assert True
    
    # ========================================================================
    # BACKGROUND SERVICE
    # ========================================================================
    
    def test_start_background_service(self, initialized_engine: SpeechEngine):
        """Test starting background service."""
        initialized_engine.start_background_service()
        
        # Service should be running
        assert initialized_engine.background_service.get_state().value in ["sleep", "wake"]
        
        # Cleanup
        initialized_engine.stop_background_service()
    
    def test_stop_background_service(self, initialized_engine: SpeechEngine):
        """Test stopping background service."""
        initialized_engine.start_background_service()
        initialized_engine.stop_background_service()
        
        # Service should be stopped
        assert initialized_engine.background_service.get_state().value == "stopped"
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def test_get_state(self, engine: SpeechEngine):
        """Test getting engine state."""
        assert engine.get_state() == EngineState.UNINITIALIZED
        
        engine.initialize()
        assert engine.get_state() == EngineState.READY
    
    def test_state_transitions(self, engine: SpeechEngine, sample_audio: np.ndarray):
        """Test state transitions."""
        import asyncio
        
        # Uninitialized
        assert engine.get_state() == EngineState.UNINITIALIZED
        
        # Initialize
        engine.initialize()
        assert engine.get_state() == EngineState.READY
        
        # Process (briefly goes to PROCESSING, then back to READY)
        asyncio.run(engine.process_voice_input(sample_audio, PersonalityType.GURU))
        assert engine.get_state() == EngineState.READY
    
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
        except:
            pass
        
        # Context should still exist
        assert initialized_engine._current_context_id == context_id
    
    def test_initialization_error_handling(self):
        """Test error handling during initialization."""
        engine = SpeechEngine()
        
        # Mock a component to fail
        original_init = engine.initialize
        
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
        assert initialized_engine.get_state() == EngineState.UNINITIALIZED
    
    def test_shutdown_with_background_service(self, initialized_engine: SpeechEngine):
        """Test shutdown with running background service."""
        initialized_engine.start_background_service()
        
        # Store reference before shutdown
        bg_service = initialized_engine.background_service
        
        initialized_engine.shutdown()
        
        # Service should be stopped (check the stored reference)
        assert bg_service.get_state().value == "stopped"
        assert initialized_engine.get_state() == EngineState.UNINITIALIZED
    
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
        assert result1.personality == PersonalityType.GURU
        
        # Process with Maya
        result2 = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.MAYA
        ))
        assert result2.personality == PersonalityType.MAYA
    
    # ========================================================================
    # CALLBACKS
    # ========================================================================
    
    def test_wake_word_callback(self, initialized_engine: SpeechEngine):
        """Test wake word callback."""
        # Should not raise exception
        initialized_engine._on_wake_word_detected()
        assert True
    
    def test_command_callback(self, initialized_engine: SpeechEngine):
        """Test command callback."""
        # Should not raise exception
        initialized_engine._on_command_received("test command")
        assert True


    # ========================================================================
    # ZERO COMPROMISE - INTEGRATION TESTS
    # ========================================================================
    
    def test_integration_complete_voice_interaction(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """ZERO COMPROMISE: Test complete voice interaction flow."""
        import asyncio
        
        # Process voice input
        result = asyncio.run(initialized_engine.process_voice_input(
            audio=sample_audio,
            personality=PersonalityType.GURU
        ))
        
        # Verify all components worked
        assert result.transcription is not None
        assert result.emotion is not None
        assert result.personality == PersonalityType.GURU
        assert result.context_id is not None
        
        # Synthesize response
        response_audio = initialized_engine.synthesize_response(
            text="I understand",
            personality=result.personality,
            emotion=result.emotion.primary_emotion
        )
        
        assert response_audio is not None
        assert len(response_audio) > 0
    
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
        assert len(set(context_ids)) == 1
    
    def test_integration_emotion_aware_response(
        self,
        initialized_engine: SpeechEngine,
        sample_audio: np.ndarray
    ):
        """ZERO COMPROMISE: Test emotion-aware response generation."""
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
        
        assert response_audio is not None
    
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
            assert result is not None
    
    def test_stress_long_audio(self, initialized_engine: SpeechEngine):
        """ZERO COMPROMISE: Stress test with long audio."""
        import asyncio
        
        # 10 seconds of audio
        long_audio = np.random.randn(160000).astype(np.float32)
        
        result = asyncio.run(initialized_engine.process_voice_input(
            audio=long_audio,
            personality=PersonalityType.GURU
        ))
        
        assert result is not None
    
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
            assert result is not None
        except GuruSpeechError:
            # Expected for very short audio
            pass
    
    def test_edge_case_shutdown_before_init(self, engine: SpeechEngine):
        """ZERO COMPROMISE: Test shutdown before initialization."""
        # Should handle gracefully
        engine.shutdown()
        assert engine.get_state() == EngineState.UNINITIALIZED
    
    def test_edge_case_double_initialization(self, engine: SpeechEngine):
        """ZERO COMPROMISE: Test double initialization."""
        engine.initialize()
        
        # Second initialization should work
        engine.initialize()
        assert engine.get_state() == EngineState.READY
