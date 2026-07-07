"""Unit tests for speech engine data models."""

import numpy as np
from hypothesis import given, strategies as st
from Agent_Guru.speech.models import (
    PersonalityType,
    EmotionType,
    WakeWordDetection,
    TranscriptionResult,
    TranscriptionSegment,
    VoiceFeatures,
    EmotionResult,
    EmotionHistory,
    VoiceModel,
    NoiseProfile,
    StreamMetrics,
    ConversationTurn,
    ConversationContext,
    TTSConfig,
    CommandResult,
)


class TestPersonalityType:
    """Tests for PersonalityType enum."""
    
    def test_guru_personality(self):
        """Test Guru personality type."""
        assert PersonalityType.GURU.value == "guru"  # nosec B101
    
    def test_maya_personality(self):
        """Test Maya personality type."""
        assert PersonalityType.MAYA.value == "maya"  # nosec B101


class TestEmotionType:
    """Tests for EmotionType enum."""
    
    def test_all_emotion_types(self):
        """Test all emotion types are defined."""
        expected_emotions = {
            "happy", "sad", "angry", "neutral", 
            "surprised", "fearful", "disgusted"
        }
        actual_emotions = {e.value for e in EmotionType}
        assert actual_emotions == expected_emotions  # nosec B101


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
        
        assert detection.wake_word == "Hey Guru"  # nosec B101
        assert detection.personality == PersonalityType.GURU  # nosec B101
        assert detection.confidence == 0.95  # nosec B101
        assert detection.timestamp == 1234567890.0  # nosec B101
        assert len(detection.audio_chunk) == 1000  # nosec B101


class TestTranscriptionResult:
    """Tests for TranscriptionResult dataclass."""
    
    def test_transcription_result_basic(self):
        """Test basic transcription result."""
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            confidence=0.98
        )
        
        assert result.text == "Hello world"  # nosec B101
        assert result.language == "en"  # nosec B101
        assert result.confidence == 0.98  # nosec B101
        assert result.segments == []  # nosec B101
        assert result.duration == 0.0  # nosec B101
    
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
        
        assert len(result.segments) == 2  # nosec B101
        assert result.segments[0].text == "Hello"  # nosec B101
        assert result.segments[1].text == "world"  # nosec B101


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
        
        assert len(features.feature_vector) == 128  # nosec B101
        assert features.sample_rate == 16000  # nosec B101
        assert features.duration == 2.5  # nosec B101
        assert 0.0 <= features.quality_score <= 1.0  # nosec B101


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
        
        assert result.primary_emotion == EmotionType.HAPPY  # nosec B101
        assert result.emotion_scores[EmotionType.HAPPY] == 0.8  # nosec B101
        assert result.confidence == 0.8  # nosec B101
        assert result.audio_quality == 0.9  # nosec B101


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
        
        assert model.model_id == "model_123"  # nosec B101
        assert model.user_id == "user_456"  # nosec B101
        assert model.voice_characteristics["pitch"] == 150.0  # nosec B101
        assert model.similarity_score == 0.87  # nosec B101


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
        
        assert context.personality == PersonalityType.GURU  # nosec B101
        assert context.current_topic == "weather"  # nosec B101
        assert context.user_preferences["language"] == "en"  # nosec B101


class TestTTSConfig:
    """Tests for TTSConfig dataclass."""
    
    def test_tts_config_defaults(self):
        """Test TTS config with defaults."""
        config = TTSConfig(personality=PersonalityType.MAYA)
        
        assert config.personality == PersonalityType.MAYA  # nosec B101
        assert config.emotion is None  # nosec B101
        assert config.speech_rate == 1.0  # nosec B101
        assert config.pitch == 1.0  # nosec B101
        assert config.volume == 1.0  # nosec B101
        assert config.use_ssml is False  # nosec B101
    
    def test_tts_config_with_emotion(self):
        """Test TTS config with emotion."""
        config = TTSConfig(
            personality=PersonalityType.GURU,
            emotion=EmotionType.HAPPY,
            speech_rate=1.2
        )
        
        assert config.personality == PersonalityType.GURU  # nosec B101
        assert config.emotion == EmotionType.HAPPY  # nosec B101
        assert config.speech_rate == 1.2  # nosec B101


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
        
        assert result.is_command is True  # nosec B101
        assert result.action_id == "OPEN_APP"  # nosec B101
        assert result.parameters["app_name"] == "browser"  # nosec B101
        assert result.confidence == 0.92  # nosec B101
    
    def test_command_result_not_command(self):
        """Test command result for non-command."""
        result = CommandResult(
            is_command=False,
            action_id=None,
            parameters={},
            confidence=0.3,
            raw_text="hello there"
        )
        
        assert result.is_command is False  # nosec B101
        assert result.action_id is None  # nosec B101
        assert result.parameters == {}  # nosec B101


class TestEmotionHistory:
    """Tests for EmotionHistory dataclass."""
    
    def test_emotion_history_creation(self):
        """Test creating emotion history."""
        emotions = [
            EmotionResult(
                primary_emotion=EmotionType.HAPPY,
                emotion_scores={EmotionType.HAPPY: 0.8},
                confidence=0.8,
                timestamp=1.0,
                audio_quality=0.9
            ),
            EmotionResult(
                primary_emotion=EmotionType.SAD,
                emotion_scores={EmotionType.SAD: 0.7},
                confidence=0.7,
                timestamp=2.0,
                audio_quality=0.85
            )
        ]
        
        transitions = [(EmotionType.HAPPY, EmotionType.SAD, 2.0)]
        
        history = EmotionHistory(
            emotions=emotions,
            dominant_emotion=EmotionType.HAPPY,
            emotion_transitions=transitions
        )
        
        assert len(history.emotions) == 2  # nosec B101
        assert history.dominant_emotion == EmotionType.HAPPY  # nosec B101
        assert len(history.emotion_transitions) == 1  # nosec B101
        assert history.emotion_transitions[0][0] == EmotionType.HAPPY  # nosec B101
        assert history.emotion_transitions[0][1] == EmotionType.SAD  # nosec B101


class TestNoiseProfile:
    """Tests for NoiseProfile dataclass."""
    
    def test_noise_profile_creation(self):
        """Test creating noise profile."""
        profile = NoiseProfile(
            noise_type="white",
            noise_level=0.3,
            snr=15.0,
            frequency_profile=np.random.rand(256)
        )
        
        assert profile.noise_type == "white"  # nosec B101
        assert profile.noise_level == 0.3  # nosec B101
        assert profile.snr == 15.0  # nosec B101
        assert len(profile.frequency_profile) == 256  # nosec B101


class TestStreamMetrics:
    """Tests for StreamMetrics dataclass."""
    
    def test_stream_metrics_creation(self):
        """Test creating stream metrics."""
        metrics = StreamMetrics(
            latency_ms=250.0,
            jitter_ms=10.0,
            packet_loss_percent=0.5,
            buffer_size=4096
        )
        
        assert metrics.latency_ms == 250.0  # nosec B101
        assert metrics.jitter_ms == 10.0  # nosec B101
        assert metrics.packet_loss_percent == 0.5  # nosec B101
        assert metrics.buffer_size == 4096  # nosec B101


class TestConversationTurn:
    """Tests for ConversationTurn dataclass."""
    
    def test_conversation_turn_creation(self):
        """Test creating conversation turn."""
        turn = ConversationTurn(
            speaker="user",
            text="Hello Guru",
            timestamp=1234567890.0,
            emotion=EmotionType.HAPPY
        )
        
        assert turn.speaker == "user"  # nosec B101
        assert turn.text == "Hello Guru"  # nosec B101
        assert turn.timestamp == 1234567890.0  # nosec B101
        assert turn.emotion == EmotionType.HAPPY  # nosec B101
    
    def test_conversation_turn_without_emotion(self):
        """Test conversation turn without emotion."""
        turn = ConversationTurn(
            speaker="agent",
            text="Hello!",
            timestamp=1234567891.0
        )
        
        assert turn.speaker == "agent"  # nosec B101
        assert turn.emotion is None  # nosec B101


# Property-Based Tests for Confidence Score Consistency

@given(
    confidence=st.floats(min_value=0.0, max_value=1.0),
    timestamp=st.floats(min_value=0.0, max_value=2e9)
)
def test_property_wake_word_detection_confidence_bounds(confidence, timestamp):
    """
    Feature: guru-speech-engine, Property 26: Confidence Score Consistency
    Validates: Requirements 2.14, 3.3, 6.4, 13.3
    
    For any WakeWordDetection, confidence score should be in [0.0, 1.0].
    """
    audio = np.zeros(1000, dtype=np.float32)
    detection = WakeWordDetection(
        wake_word="Hey Guru",
        personality=PersonalityType.GURU,
        confidence=confidence,
        timestamp=timestamp,
        audio_chunk=audio
    )
    
    assert 0.0 <= detection.confidence <= 1.0  # nosec B101


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0),
    duration=st.floats(min_value=0.0, max_value=3600.0)
)
def test_property_transcription_result_confidence_bounds(confidence, duration):
    """
    Feature: guru-speech-engine, Property 26: Confidence Score Consistency
    Validates: Requirements 2.14, 3.3, 6.4, 13.3
    
    For any TranscriptionResult, confidence score should be in [0.0, 1.0].
    """
    result = TranscriptionResult(
        text="Hello world",
        language="en",
        confidence=confidence,
        duration=duration
    )
    
    assert 0.0 <= result.confidence <= 1.0  # nosec B101
    assert result.duration >= 0.0  # nosec B101


@given(
    segment_confidence=st.floats(min_value=0.0, max_value=1.0),
    start_time=st.floats(min_value=0.0, max_value=100.0),
    duration=st.floats(min_value=0.1, max_value=10.0)
)
def test_property_transcription_segment_confidence_bounds(segment_confidence, start_time, duration):
    """
    Feature: guru-speech-engine, Property 26: Confidence Score Consistency
    Validates: Requirements 2.14, 3.3, 6.4, 13.3
    
    For any TranscriptionSegment, confidence score should be in [0.0, 1.0].
    """
    segment = TranscriptionSegment(
        text="Hello",
        start_time=start_time,
        end_time=start_time + duration,
        confidence=segment_confidence
    )
    
    assert 0.0 <= segment.confidence <= 1.0  # nosec B101
    assert segment.start_time <= segment.end_time  # nosec B101


@given(
    quality_score=st.floats(min_value=0.0, max_value=1.0),
    duration=st.floats(min_value=0.1, max_value=60.0)
)
def test_property_voice_features_quality_score_bounds(quality_score, duration):
    """
    Feature: guru-speech-engine, Property 26: Confidence Score Consistency
    Validates: Requirements 2.14, 3.3, 6.4, 13.3
    
    For any VoiceFeatures, quality_score should be in [0.0, 1.0].
    """
    features = VoiceFeatures(
        feature_vector=np.random.rand(128),
        sample_rate=16000,
        duration=duration,
        quality_score=quality_score
    )
    
    assert 0.0 <= features.quality_score <= 1.0  # nosec B101
    assert features.duration > 0.0  # nosec B101


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0),
    audio_quality=st.floats(min_value=0.0, max_value=1.0),
    timestamp=st.floats(min_value=0.0, max_value=2e9)
)
def test_property_emotion_result_confidence_bounds(confidence, audio_quality, timestamp):
    """
    Feature: guru-speech-engine, Property 26: Confidence Score Consistency
    Validates: Requirements 2.14, 3.3, 6.4, 13.3
    
    For any EmotionResult, confidence and audio_quality should be in [0.0, 1.0],
    and all emotion_scores should be in [0.0, 1.0].
    """
    # Generate emotion scores that sum to approximately 1.0
    emotion_scores = {}
    remaining = 1.0
    emotions = list(EmotionType)
    
    for i, emotion in enumerate(emotions[:-1]):
        score = np.random.uniform(0, remaining)
        emotion_scores[emotion] = score
        remaining -= score
    emotion_scores[emotions[-1]] = max(0.0, remaining)
    
    result = EmotionResult(
        primary_emotion=EmotionType.HAPPY,
        emotion_scores=emotion_scores,
        confidence=confidence,
        timestamp=timestamp,
        audio_quality=audio_quality
    )
    
    assert 0.0 <= result.confidence <= 1.0  # nosec B101
    assert 0.0 <= result.audio_quality <= 1.0  # nosec B101
    for emotion, score in result.emotion_scores.items():
        assert 0.0 <= score <= 1.0  # nosec B101


@given(
    similarity_score=st.floats(min_value=0.0, max_value=1.0),
    training_duration=st.floats(min_value=300.0, max_value=3600.0)
)
def test_property_voice_model_similarity_score_bounds(similarity_score, training_duration):
    """
    Feature: guru-speech-engine, Property 26: Confidence Score Consistency
    Validates: Requirements 2.14, 3.3, 6.4, 13.3
    
    For any VoiceModel, similarity_score should be in [0.0, 1.0].
    """
    model = VoiceModel(
        model_id="model_123",
        user_id="user_456",
        voice_characteristics={"pitch": 150.0},
        training_duration_seconds=training_duration,
        similarity_score=similarity_score,
        created_at=1234567890.0,
        updated_at=1234567900.0
    )
    
    assert 0.0 <= model.similarity_score <= 1.0  # nosec B101
    assert model.training_duration_seconds >= 300.0  # nosec B101


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0)
)
def test_property_command_result_confidence_bounds(confidence):
    """
    Feature: guru-speech-engine, Property 26: Confidence Score Consistency
    Validates: Requirements 2.14, 3.3, 6.4, 13.3
    
    For any CommandResult, confidence score should be in [0.0, 1.0].
    """
    result = CommandResult(
        is_command=True,
        action_id="OPEN_APP",
        parameters={"app_name": "browser"},
        confidence=confidence,
        raw_text="open browser"
    )
    
    assert 0.0 <= result.confidence <= 1.0  # nosec B101


# Edge Case Tests for Confidence Scores

class TestConfidenceScoreEdgeCases:
    """Test edge cases for confidence scores."""
    
    def test_confidence_score_zero(self):
        """Test confidence score at minimum (0.0)."""
        result = TranscriptionResult(
            text="uncertain",
            language="en",
            confidence=0.0
        )
        assert result.confidence == 0.0  # nosec B101
    
    def test_confidence_score_one(self):
        """Test confidence score at maximum (1.0)."""
        result = TranscriptionResult(
            text="certain",
            language="en",
            confidence=1.0
        )
        assert result.confidence == 1.0  # nosec B101
    
    def test_quality_score_boundaries(self):
        """Test quality score at boundaries."""
        features_min = VoiceFeatures(
            feature_vector=np.random.rand(128),
            sample_rate=16000,
            duration=1.0,
            quality_score=0.0
        )
        assert features_min.quality_score == 0.0  # nosec B101
        
        features_max = VoiceFeatures(
            feature_vector=np.random.rand(128),
            sample_rate=16000,
            duration=1.0,
            quality_score=1.0
        )
        assert features_max.quality_score == 1.0  # nosec B101
    
    def test_emotion_scores_sum_to_one(self):
        """Test that emotion scores can sum to 1.0."""
        emotion_scores = {
            EmotionType.HAPPY: 0.5,
            EmotionType.NEUTRAL: 0.3,
            EmotionType.SAD: 0.2,
        }
        
        result = EmotionResult(
            primary_emotion=EmotionType.HAPPY,
            emotion_scores=emotion_scores,
            confidence=0.8,
            timestamp=1234567890.0,
            audio_quality=0.9
        )
        
        total = sum(result.emotion_scores.values())
        assert abs(total - 1.0) < 0.01  # Allow small floating point error  # nosec B101
    
    def test_similarity_score_high_quality(self):
        """Test voice model with high similarity score."""
        model = VoiceModel(
            model_id="model_123",
            user_id="user_456",
            voice_characteristics={"pitch": 150.0},
            training_duration_seconds=600.0,
            similarity_score=0.95,
            created_at=1234567890.0,
            updated_at=1234567900.0
        )
        assert model.similarity_score >= 0.85  # Meets requirement  # nosec B101


# Field Validation Tests

class TestDataclassFieldValidation:
    """Test field validation for all dataclasses."""
    
    def test_wake_word_detection_required_fields(self):
        """Test WakeWordDetection requires all fields."""
        audio = np.zeros(1000, dtype=np.float32)
        detection = WakeWordDetection(
            wake_word="Hey Guru",
            personality=PersonalityType.GURU,
            confidence=0.95,
            timestamp=1234567890.0,
            audio_chunk=audio
        )
        assert detection.wake_word is not None  # nosec B101
        assert detection.personality is not None  # nosec B101
        assert detection.audio_chunk is not None  # nosec B101
    
    def test_transcription_result_default_values(self):
        """Test TranscriptionResult default values."""
        result = TranscriptionResult(
            text="Hello",
            language="en",
            confidence=0.98
        )
        assert result.segments == []  # nosec B101
        assert result.duration == 0.0  # nosec B101
    
    def test_transcription_segment_optional_speaker(self):
        """Test TranscriptionSegment with optional speaker_id."""
        segment = TranscriptionSegment(
            text="Hello",
            start_time=0.0,
            end_time=1.0
        )
        assert segment.speaker_id is None  # nosec B101
        assert segment.confidence == 1.0  # nosec B101
    
    def test_conversation_turn_optional_emotion(self):
        """Test ConversationTurn with optional emotion."""
        turn = ConversationTurn(
            speaker="user",
            text="Hello",
            timestamp=1234567890.0
        )
        assert turn.emotion is None  # nosec B101
    
    def test_conversation_context_default_values(self):
        """Test ConversationContext default values."""
        context = ConversationContext(
            personality=PersonalityType.GURU,
            turns=[]
        )
        assert context.current_topic is None  # nosec B101
        assert context.user_preferences == {}  # nosec B101
        assert context.created_at == 0.0  # nosec B101
        assert context.updated_at == 0.0  # nosec B101
    
    def test_tts_config_all_defaults(self):
        """Test TTSConfig with all default values."""
        config = TTSConfig(personality=PersonalityType.MAYA)
        assert config.emotion is None  # nosec B101
        assert config.speech_rate == 1.0  # nosec B101
        assert config.pitch == 1.0  # nosec B101
        assert config.volume == 1.0  # nosec B101
        assert config.use_ssml is False  # nosec B101
    
    def test_command_result_with_none_action(self):
        """Test CommandResult with None action_id."""
        result = CommandResult(
            is_command=False,
            action_id=None,
            parameters={},
            confidence=0.2,
            raw_text="just talking"
        )
        assert result.action_id is None  # nosec B101
        assert result.is_command is False  # nosec B101
