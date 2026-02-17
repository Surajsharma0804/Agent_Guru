"""Data models for the speech engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import numpy as np


class PersonalityType(Enum):
    """AI personality types."""
    GURU = "guru"  # Male personality
    MAYA = "maya"  # Female personality


class EmotionType(Enum):
    """Emotion types detected from voice."""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    SURPRISED = "surprised"
    FEARFUL = "fearful"
    DISGUSTED = "disgusted"


@dataclass
class WakeWordDetection:
    """Wake word detection result."""
    wake_word: str
    personality: PersonalityType
    confidence: float
    timestamp: float
    audio_chunk: np.ndarray


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text."""
    text: str
    start_time: float
    end_time: float
    speaker_id: Optional[int] = None
    confidence: float = 1.0


@dataclass
class TranscriptionResult:
    """Speech-to-text transcription result."""
    text: str
    language: str
    confidence: float
    segments: List[TranscriptionSegment] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class VoiceFeatures:
    """Voice biometric features."""
    feature_vector: np.ndarray
    sample_rate: int
    duration: float
    quality_score: float  # 0.0 to 1.0


@dataclass
class EmotionResult:
    """Emotion detection result."""
    primary_emotion: EmotionType
    emotion_scores: Dict[EmotionType, float]
    confidence: float
    timestamp: float
    audio_quality: float


@dataclass
class EmotionHistory:
    """Emotion history over time."""
    emotions: List[EmotionResult]
    dominant_emotion: EmotionType
    emotion_transitions: List[tuple[EmotionType, EmotionType, float]]


@dataclass
class VoiceModel:
    """Voice cloning model."""
    model_id: str
    user_id: str
    voice_characteristics: Dict[str, float]
    training_duration_seconds: float
    similarity_score: float
    created_at: float
    updated_at: float


@dataclass
class NoiseProfile:
    """Noise profile for adaptive cancellation."""
    noise_type: str
    noise_level: float
    snr: float
    frequency_profile: np.ndarray


@dataclass
class StreamMetrics:
    """Streaming audio metrics."""
    latency_ms: float
    jitter_ms: float
    packet_loss_percent: float
    buffer_size: int
    buffer_underruns: int = 0
    buffer_overruns: int = 0


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    speaker: str
    text: str
    timestamp: float
    emotion: Optional[EmotionType] = None


@dataclass
class ConversationContext:
    """Conversation context state."""
    personality: PersonalityType
    turns: List[ConversationTurn]
    current_topic: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class TTSConfig:
    """Text-to-speech configuration."""
    personality: PersonalityType
    emotion: Optional[EmotionType] = None
    speech_rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    use_ssml: bool = False


@dataclass
class CommandResult:
    """Command interpretation result."""
    is_command: bool
    action_id: Optional[str]
    parameters: Dict[str, Any]
    confidence: float
    raw_text: str
