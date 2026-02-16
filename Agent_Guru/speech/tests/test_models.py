"""Unit tests for speech engine data models."""

import pytest
import numpy as np
from Agent_Guru.speech.models import (
    PersonalityType,
    EmotionType,
    WakeWordDetection,
    TranscriptionResult,
    TranscriptionSegment,
    VoiceFeatures,
    EmotionResult,
    VoiceModel,
    ConversationContext,
    TTSConfig,
    CommandResult,
)


class TestPersonalityType:
    """Tests for PersonalityType enum."""
    
    def test_guru_personality(self):
        """Test Guru personality type."""
        assert PersonalityType.GURU.value == "guru"
    
    def test_maya_personality(self):
        """Test Maya personality type."""
        assert PersonalityType.MAYA.value == "maya"


class TestEmotionType:
    """Tests for EmotionType enum."""
    
    def test_all_emotion_types(self):
        """Test all emotion types are defined."""
        expected_emotions = {
            "happy", "sad", "angry", "neutral", 
            "surprised", "fearful", "disgusted"
        }
        actual_emotions = {e.value for e in EmotionType}
        assert actual_emotions == expected_emotions


class TestWakeWordDetection:
    """Tests for WakeWordDetection dataclass."""
    
    def test_wake_word_detection_creation(self):
        """Test creating a wake word detection result."""
        audio = np.zeros(1000, dtype=np.float32)
        detection = WakeWordDetection(
            wake_word="Hey Guru",
            personality=PersonalityType.GURU,
            confidence=0.95,
            timestamp=1234567890.0,
            audio_chunk=audio
        )
        
        assert detection.wake_word == "Hey Guru"
        assert detection.personality == PersonalityType.GURU
        assert detection.confidence == 0.95
        assert detection.timestamp == 1234567890.0
        assert len(detection.audio_chunk) == 1000


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""
    
    def test_transcription_result_basic(self):
        """Test basic transcription result."""
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            confidence=0.98
        )
        
        assert result.text == "Hello world"
        assert result.language == "en"
        assert result.confidence == 0.98
        assert result.segments == []
        assert result.duration == 0.0
    
    def test_transcription_result_with_segments(self):
        """Test transcription result with segments."""
        segments = [
            TranscriptionSegment(
                text="Hello",
                start_time=0.0,
                end_time=0.5,
                speaker_id=1,
                confidence=0.99
            ),
            TranscriptionSegment(
                text="world",
                start_time=0.5,
                end_time=1.0,
                speaker_id=1,
                confidence=0.97
            )
        ]
        
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            confidence=0.98,
            segments=segments,
            duration=1.0
        )
        
        assert len(result.segments) == 2
        assert result.segments[0].text == "Hello"
        assert result.segments[1].text == "world"


class TestVoiceFeatures:
    """Tests for VoiceFeatures dataclass."""
    
    def test_voice_features_creation(self):
        """Test creating voice features."""
        features = VoiceFeatures(
            feature_vector=np.random.rand(128),
            sample_rate=16000,
            duration=2.5,
            quality_score=0.85
        )
        
        assert len(features.feature_vector) == 128
        assert features.sample_rate == 16000
        assert features.duration == 2.5
        assert 0.0 <= features.quality_score <= 1.0


class TestEmotionResult:
    """Tests for EmotionResult dataclass."""
    
    def test_emotion_result_creation(self):
        """Test creating emotion result."""
        emotion_scores = {
            EmotionType.HAPPY: 0.8,
            EmotionType.NEUTRAL: 0.15,
            EmotionType.SAD: 0.05,
        }
        
        result = EmotionResult(
            primary_emotion=EmotionType.HAPPY,
            emotion_scores=emotion_scores,
            confidence=0.8,
            timestamp=1234567890.0,
            audio_quality=0.9
        )
        
        assert result.primary_emotion == EmotionType.HAPPY
        assert result.emotion_scores[EmotionType.HAPPY] == 0.8
        assert result.confidence == 0.8
        assert result.audio_quality == 0.9


class TestVoiceModel:
    """Tests for VoiceModel dataclass."""
    
    def test_voice_model_creation(self):
        """Test creating voice model."""
        model = VoiceModel(
            model_id="model_123",
            user_id="user_456",
            voice_characteristics={"pitch": 150.0, "rate": 1.2},
            training_duration_seconds=300.0,
            similarity_score=0.87,
            created_at=1234567890.0,
            updated_at=1234567900.0
        )
        
        assert model.model_id == "model_123"
        assert model.user_id == "user_456"
        assert model.voice_characteristics["pitch"] == 150.0
        assert model.similarity_score == 0.87


class TestConversationContext:
    """Tests for ConversationContext dataclass."""
    
    def test_conversation_context_creation(self):
        """Test creating conversation context."""
        context = ConversationContext(
            personality=PersonalityType.GURU,
            turns=[],
            current_topic="weather",
            user_preferences={"language": "en"}
        )
        
        assert context.personality == PersonalityType.GURU
        assert context.current_topic == "weather"
        assert context.user_preferences["language"] == "en"


class TestTTSConfig:
    """Tests for TTSConfig dataclass."""
    
    def test_tts_config_defaults(self):
        """Test TTS config with defaults."""
        config = TTSConfig(personality=PersonalityType.MAYA)
        
        assert config.personality == PersonalityType.MAYA
        assert config.emotion is None
        assert config.speech_rate == 1.0
        assert config.pitch == 1.0
        assert config.volume == 1.0
        assert config.use_ssml is False
    
    def test_tts_config_with_emotion(self):
        """Test TTS config with emotion."""
        config = TTSConfig(
            personality=PersonalityType.GURU,
            emotion=EmotionType.HAPPY,
            speech_rate=1.2
        )
        
        assert config.personality == PersonalityType.GURU
        assert config.emotion == EmotionType.HAPPY
        assert config.speech_rate == 1.2


class TestCommandResult:
    """Tests for CommandResult dataclass."""
    
    def test_command_result_is_command(self):
        """Test command result for valid command."""
        result = CommandResult(
            is_command=True,
            action_id="OPEN_APP",
            parameters={"app_name": "browser"},
            confidence=0.92,
            raw_text="open browser"
        )
        
        assert result.is_command is True
        assert result.action_id == "OPEN_APP"
        assert result.parameters["app_name"] == "browser"
        assert result.confidence == 0.92
    
    def test_command_result_not_command(self):
        """Test command result for non-command."""
        result = CommandResult(
            is_command=False,
            action_id=None,
            parameters={},
            confidence=0.3,
            raw_text="hello there"
        )
        
        assert result.is_command is False
        assert result.action_id is None
        assert result.parameters == {}
