"""Data models for the speech engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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
    speaker_id: int | None = None
    confidence: float = 1.0


@dataclass
class TranscriptionResult:
    """Speech-to-text transcription result."""

    text: str
    language: str
    confidence: float
    segments: list[TranscriptionSegment] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class VoiceFeatures:
    """Voice biometric features extracted for the security system.

    This dataclass is the API contract between the speech engine (feature
    extraction) and guru-security-cryptography (authentication).  The speech
    engine populates every field; the security system consumes them to make
    authentication decisions.

    Attributes:
        feature_vector: Numerical representation of voice characteristics
            (MFCC, pitch, spectral, energy features).
        sample_rate: Sample rate of the source audio in Hz.
        duration: Duration of the source audio in seconds.
        quality_score: Overall audio quality estimate in [0.0, 1.0].
            Higher values indicate better quality for authentication.
        liveness_score: Anti-spoofing confidence in [0.0, 1.0].
            Higher values indicate the audio is more likely from a live speaker.
        is_live: True when liveness_score meets the liveness threshold
            (>= 0.55).  The BiometricAuthenticator MUST reject authentication
            when this field is False.

    """

    feature_vector: np.ndarray
    sample_rate: int
    duration: float
    quality_score: float  # 0.0 to 1.0
    liveness_score: float = 0.0  # 0.0 to 1.0 – populated by VoiceFeatureExtractor
    is_live: bool = False  # True when liveness_score >= 0.55


@dataclass
class EmotionResult:
    """Emotion detection result."""

    primary_emotion: EmotionType
    emotion_scores: dict[EmotionType, float]
    confidence: float
    timestamp: float
    audio_quality: float


@dataclass
class EmotionHistory:
    """Emotion history over time."""

    emotions: list[EmotionResult]
    dominant_emotion: EmotionType
    emotion_transitions: list[tuple[EmotionType, EmotionType, float]]


@dataclass
class VoiceModel:
    """Voice cloning model."""

    model_id: str
    user_id: str
    voice_characteristics: dict[str, float]
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
    emotion: EmotionType | None = None


@dataclass
class ConversationContext:
    """Conversation context state."""

    personality: PersonalityType
    turns: list[ConversationTurn]
    current_topic: str | None = None
    user_preferences: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class TTSConfig:
    """Text-to-speech configuration."""

    personality: PersonalityType
    emotion: EmotionType | None = None
    speech_rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    use_ssml: bool = False


@dataclass
class CommandResult:
    """Command interpretation result."""

    is_command: bool
    action_id: str | None
    parameters: dict[str, Any]
    confidence: float
    raw_text: str
