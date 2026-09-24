"""Module: Agent_Guru.avatar.models
Purpose: Production-grade data models for the Avatar and Emotion Engine.

Implements the full Cowen & Keltner (2017) 27-emotion taxonomy, Russell's
circumplex model (valence/arousal), FACS Action Units, and Pydantic-validated
state objects for thread-safe avatar state management.

References:
    - Cowen & Keltner (2017) PNAS: 27 distinct emotion categories
    - Russell (1980): Circumplex model of affect (valence/arousal)
    - Ekman FACS: Facial Action Coding System (AU1-AU46)

Requirements: Req 5 (Avatar State Management), Req 11 (Python Implementation)

"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

try:
    from pydantic import Field, field_validator

    _PYDANTIC_V2 = True
except ImportError:
    # Fallback: use dataclasses if pydantic not installed
    Field = None  # type: ignore[assignment]
    _PYDANTIC_V2 = False


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PersonalityType(Enum):
    """Supported avatar personalities."""

    GURU = "guru"
    MAYA = "maya"


# ---------------------------------------------------------------------------
# Cowen & Keltner (2017) - 27 distinct emotion categories
# ---------------------------------------------------------------------------

EMOTION_CATEGORIES_27: list[str] = [
    "admiration",
    "adoration",
    "aesthetic_appreciation",
    "amusement",
    "anger",
    "anxiety",
    "awe",
    "awkwardness",
    "boredom",
    "calmness",
    "confusion",
    "craving",
    "disgust",
    "empathic_pain",
    "entrancement",
    "excitement",
    "fear",
    "horror",
    "interest",
    "joy",
    "nostalgia",
    "relief",
    "romance",
    "sadness",
    "satisfaction",
    "surprise",
    "triumph",
]

# Legacy 7-emotion set (Ekman) - kept for backward compatibility
EMOTION_CATEGORIES_7: list[str] = [
    "happy",
    "sad",
    "angry",
    "fear",
    "surprise",
    "disgust",
    "neutral",
]

# Full set used by the system (27 + neutral + legacy aliases)
EMOTION_CATEGORIES: list[str] = [*EMOTION_CATEGORIES_27, "neutral", "happy"]

# Mapping from legacy 7-emotion labels to 27-emotion equivalents
LEGACY_EMOTION_MAP: dict[str, str] = {
    "happy": "joy",
    "sad": "sadness",
    "angry": "anger",
    "fear": "fear",
    "surprise": "surprise",
    "disgust": "disgust",
    "neutral": "neutral",
}

# Valence/arousal coordinates for each emotion (Russell's circumplex model)
# valence: -1.0 (negative) to +1.0 (positive)
# arousal: -1.0 (calm) to +1.0 (excited)
EMOTION_VALENCE_AROUSAL: dict[str, tuple[float, float]] = {
    "admiration": (0.7, 0.3),
    "adoration": (0.9, 0.4),
    "aesthetic_appreciation": (0.6, 0.2),
    "amusement": (0.8, 0.5),
    "anger": (-0.7, 0.8),
    "anxiety": (-0.6, 0.7),
    "awe": (0.5, 0.6),
    "awkwardness": (-0.3, 0.3),
    "boredom": (-0.2, -0.5),
    "calmness": (0.4, -0.7),
    "confusion": (-0.2, 0.2),
    "craving": (0.2, 0.5),
    "disgust": (-0.8, 0.3),
    "empathic_pain": (-0.5, 0.2),
    "entrancement": (0.5, 0.4),
    "excitement": (0.8, 0.9),
    "fear": (-0.8, 0.8),
    "horror": (-0.9, 0.8),
    "interest": (0.4, 0.4),
    "joy": (0.9, 0.7),
    "nostalgia": (0.3, -0.1),
    "relief": (0.6, -0.3),
    "romance": (0.8, 0.4),
    "sadness": (-0.7, -0.4),
    "satisfaction": (0.7, -0.1),
    "surprise": (0.1, 0.7),
    "triumph": (0.8, 0.6),
    "neutral": (0.0, 0.0),
    "happy": (0.9, 0.7),  # alias for joy
}

# FACS Action Units relevant to facial expression rendering
# AU number → description
FACS_ACTION_UNITS: dict[int, str] = {
    1: "Inner Brow Raise",
    2: "Outer Brow Raise",
    4: "Brow Lowerer",
    5: "Upper Lid Raiser",
    6: "Cheek Raiser",
    7: "Lid Tightener",
    9: "Nose Wrinkler",
    10: "Upper Lip Raiser",
    12: "Lip Corner Puller",
    13: "Cheek Puffer",
    14: "Dimpler",
    15: "Lip Corner Depressor",
    16: "Lower Lip Depressor",
    17: "Chin Raiser",
    18: "Lip Puckerer",
    20: "Lip Stretcher",
    22: "Lip Funneler",
    23: "Lip Tightener",
    24: "Lip Pressor",
    25: "Lips Part",
    26: "Jaw Drop",
    27: "Mouth Stretch",
    28: "Lip Suck",
    43: "Eyes Closed",
    45: "Blink",
    46: "Wink",
}

# Emotion → FACS AU activations (AU_number → intensity 0.0-1.0)
EMOTION_FACS_MAP: dict[str, dict[int, float]] = {
    "joy": {6: 0.8, 12: 0.9, 25: 0.3},
    "happy": {6: 0.8, 12: 0.9, 25: 0.3},
    "sadness": {1: 0.7, 4: 0.5, 15: 0.6, 17: 0.4},
    "anger": {4: 0.9, 7: 0.7, 23: 0.6, 24: 0.5},
    "fear": {1: 0.8, 2: 0.7, 4: 0.5, 5: 0.8, 20: 0.6, 26: 0.5},
    "disgust": {9: 0.8, 15: 0.5, 16: 0.4, 17: 0.3},
    "surprise": {1: 0.7, 2: 0.8, 5: 0.9, 26: 0.7, 27: 0.5},
    "amusement": {6: 0.6, 12: 0.7, 14: 0.4},
    "admiration": {2: 0.4, 5: 0.3, 12: 0.4},
    "adoration": {6: 0.7, 12: 0.8, 1: 0.3},
    "awe": {1: 0.5, 2: 0.5, 5: 0.6, 26: 0.4},
    "anxiety": {1: 0.5, 4: 0.4, 7: 0.4, 20: 0.3},
    "excitement": {1: 0.4, 2: 0.4, 5: 0.5, 12: 0.6, 25: 0.5},
    "horror": {1: 0.9, 2: 0.9, 4: 0.6, 5: 0.9, 20: 0.8, 26: 0.8},
    "triumph": {6: 0.7, 12: 0.8, 2: 0.3},
    "calmness": {},
    "boredom": {4: 0.2, 15: 0.2},
    "confusion": {4: 0.4, 1: 0.3, 17: 0.2},
    "nostalgia": {1: 0.3, 12: 0.3, 15: 0.2},
    "relief": {6: 0.4, 12: 0.3},
    "satisfaction": {6: 0.5, 12: 0.5},
    "romance": {6: 0.5, 12: 0.4, 18: 0.3},
    "craving": {18: 0.5, 25: 0.3},
    "interest": {2: 0.3, 5: 0.3},
    "entrancement": {5: 0.5, 2: 0.3, 26: 0.2},
    "empathic_pain": {1: 0.6, 4: 0.4, 15: 0.4},
    "awkwardness": {4: 0.3, 15: 0.2, 17: 0.2},
    "neutral": {},
}

# MediaPipe Face Mesh landmark indices for mouth region (468-point model)
MOUTH_LANDMARK_INDICES: list[int] = [
    # Upper lip outer
    61,
    185,
    40,
    39,
    37,
    0,
    267,
    269,
    270,
    409,
    # Lower lip outer
    146,
    91,
    181,
    84,
    17,
    314,
    405,
    321,
    375,
    291,
    # Upper lip inner
    78,
    191,
    80,
    81,
    82,
    13,
    312,
    311,
    310,
    415,
    # Lower lip inner
    95,
    88,
    178,
    87,
    14,
    317,
    402,
    318,
    324,
    308,
]

# Phoneme → viseme index mapping (Preston Blair's 10-viseme set extended to 15)
PHONEME_VISEME_MAP: dict[str, int] = {
    # Silence
    "": 0,
    "sil": 0,
    # P, B, M - lips together
    "p": 1,
    "b": 1,
    "m": 1,
    # F, V - upper teeth on lower lip
    "f": 2,
    "v": 2,
    # TH - tongue between teeth
    "th": 3,
    "dh": 3,
    # T, D, S, Z, N, L - tongue tip up
    "t": 4,
    "d": 4,
    "s": 4,
    "z": 4,
    "n": 4,
    "l": 4,
    # SH, ZH, CH, JH - tongue back
    "sh": 5,
    "zh": 5,
    "ch": 5,
    "jh": 5,
    # K, G, NG - back of tongue
    "k": 6,
    "g": 6,
    "ng": 6,
    # R - rounded
    "r": 7,
    "er": 7,
    # W, OO - rounded lips
    "w": 8,
    "uw": 8,
    "ow": 8,
    # AH, AA - open mouth
    "ah": 9,
    "aa": 9,
    "ae": 9,
    # EH, EY - mid open
    "eh": 10,
    "ey": 10,
    "ay": 10,
    # IH, IY - smile
    "ih": 11,
    "iy": 11,
    # AO, AW - rounded open
    "ao": 12,
    "aw": 12,
    # OY - rounded mid
    "oy": 13,
    # HH - open
    "hh": 14,
}

# Viseme → mouth_open_ratio and lip_spread (0.0-1.0)
VISEME_MOUTH_PARAMS: dict[int, tuple[float, float]] = {
    0: (0.00, 0.00),  # silence
    1: (0.00, 0.10),  # P/B/M
    2: (0.05, 0.20),  # F/V
    3: (0.10, 0.15),  # TH
    4: (0.15, 0.30),  # T/D/S
    5: (0.20, 0.25),  # SH/CH
    6: (0.20, 0.20),  # K/G
    7: (0.25, 0.40),  # R
    8: (0.30, 0.10),  # W/OO
    9: (0.60, 0.50),  # AH/AA
    10: (0.40, 0.60),  # EH/EY
    11: (0.20, 0.80),  # IH/IY
    12: (0.50, 0.20),  # AO/AW
    13: (0.35, 0.15),  # OY
    14: (0.45, 0.45),  # HH
}


# ---------------------------------------------------------------------------
# Pydantic data models
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel as _PydanticBase
    from pydantic import Field, field_validator

    class EmotionState(_PydanticBase):
        """Detected or expressed emotion at a point in time.

        Supports the full 27-emotion Cowen & Keltner taxonomy plus neutral.

        Attributes:
            emotion: Emotion category name.
            confidence: Detection confidence in [0.0, 1.0].
            timestamp: Unix timestamp of detection.
            valence: Affective valence in [-1.0, 1.0] (Russell's circumplex).
            arousal: Affective arousal in [-1.0, 1.0] (Russell's circumplex).
            action_units: FACS AU activations {au_number: intensity}.

        """

        emotion: str = Field(default="neutral", description="Emotion category")
        confidence: float = Field(default=1.0, ge=0.0, le=1.0)
        timestamp: float = Field(default_factory=time.time)
        valence: float = Field(default=0.0, ge=-1.0, le=1.0)
        arousal: float = Field(default=0.0, ge=-1.0, le=1.0)
        action_units: dict[int, float] = Field(default_factory=dict)

        @field_validator("emotion")
        @classmethod
        def validate_emotion(cls, v: str) -> str:
            if v not in EMOTION_CATEGORIES:
                msg = f"Invalid emotion '{v}'. Must be one of: {EMOTION_CATEGORIES}"
                raise ValueError(msg)
            return v

        @field_validator("action_units")
        @classmethod
        def validate_aus(cls, v: dict[int, float]) -> dict[int, float]:
            for au, intensity in v.items():
                if not 0.0 <= intensity <= 1.0:
                    msg = f"AU {au} intensity {intensity} out of [0,1]"
                    raise ValueError(msg)
            return v

        model_config = {"frozen": False}

        @classmethod
        def neutral(cls) -> EmotionState:
            """Return a neutral emotion state."""
            return cls(emotion="neutral", confidence=1.0, valence=0.0, arousal=0.0)

        @classmethod
        def from_emotion_name(cls, emotion: str, confidence: float = 0.8) -> EmotionState:
            """Create an EmotionState with auto-populated valence/arousal/AUs."""
            # Normalize legacy names
            emotion = LEGACY_EMOTION_MAP.get(emotion, emotion)
            if emotion not in EMOTION_CATEGORIES:
                emotion = "neutral"
            valence, arousal = EMOTION_VALENCE_AROUSAL.get(emotion, (0.0, 0.0))
            aus = {k: v * confidence for k, v in EMOTION_FACS_MAP.get(emotion, {}).items()}
            return cls(
                emotion=emotion,
                confidence=confidence,
                valence=valence,
                arousal=arousal,
                action_units=aus,
            )

    class LipSyncState(_PydanticBase):
        """Lip sync landmark data for a point in time.

        Attributes:
            landmarks: List of (x, y) normalized coordinates in [0.0, 1.0].
            timestamp: Unix timestamp of this state.
            audio_position: Current position in audio stream (seconds).
            mouth_open_ratio: Mouth openness in [0.0, 1.0].
            lip_spread: Horizontal lip spread in [0.0, 1.0].
            viseme_index: Current viseme index (0-14).
            phoneme: Current phoneme string.

        """

        landmarks: list[tuple[float, float]] = Field(default_factory=list)
        timestamp: float = Field(default_factory=time.time)
        audio_position: float = Field(default=0.0, ge=0.0)
        mouth_open_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
        lip_spread: float = Field(default=0.0, ge=0.0, le=1.0)
        viseme_index: int = Field(default=0, ge=0, le=14)
        phoneme: str = Field(default="")

        model_config = {"frozen": False}

        @classmethod
        def neutral(cls) -> LipSyncState:
            """Return a neutral (closed mouth) lip sync state."""
            return cls(
                landmarks=_build_neutral_landmarks(),
                mouth_open_ratio=0.0,
                lip_spread=0.0,
                viseme_index=0,
                phoneme="",
            )

    class PersonalityProfile(_PydanticBase):
        """Personality trait configuration for an avatar.

        All trait values must be in [0.0, 1.0].

        Attributes:
            name: Personality identifier (e.g. "guru", "maya").
            friendliness: How warm and approachable the avatar is.
            formality: How formal/professional the avatar is.
            expressiveness: How intensely emotions are expressed.
            responsiveness: How quickly the avatar reacts to user state.
            humor: Tendency to use humor in interactions.
            empathy: Sensitivity to user emotional state.
            behavior_rules: List of rule dicts for behavior patterns.

        """

        name: str = Field(default="default")
        friendliness: float = Field(default=0.5, ge=0.0, le=1.0)
        formality: float = Field(default=0.5, ge=0.0, le=1.0)
        expressiveness: float = Field(default=0.5, ge=0.0, le=1.0)
        responsiveness: float = Field(default=0.5, ge=0.0, le=1.0)
        humor: float = Field(default=0.5, ge=0.0, le=1.0)
        empathy: float = Field(default=0.5, ge=0.0, le=1.0)
        behavior_rules: list[dict[str, Any]] = Field(default_factory=list)

        model_config = {"frozen": False}

        def to_dict(self) -> dict[str, Any]:
            return self.model_dump()

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> PersonalityProfile:
            return cls(**{k: v for k, v in data.items() if k in cls.model_fields})

    class AvatarState(_PydanticBase):
        """Unified avatar state shared across all components.

        Attributes:
            personality_type: Active personality (GURU or MAYA).
            emotion: Current emotion state.
            lip_sync: Current lip sync state.
            personality: Active personality profile.
            rendering_params: Arbitrary rendering parameters.

        """

        personality_type: PersonalityType = Field(default=PersonalityType.GURU)
        emotion: EmotionState = Field(default_factory=EmotionState)
        lip_sync: LipSyncState = Field(default_factory=LipSyncState)
        personality: PersonalityProfile = Field(default_factory=PersonalityProfile)
        rendering_params: dict[str, Any] = Field(default_factory=dict)

        model_config = {"frozen": False}

        def to_dict(self) -> dict[str, Any]:
            """Serialize state to a plain dictionary."""
            return {
                "personality_type": self.personality_type.value,
                "emotion": self.emotion.model_dump(),
                "lip_sync": {
                    "landmarks": self.lip_sync.landmarks,
                    "timestamp": self.lip_sync.timestamp,
                    "audio_position": self.lip_sync.audio_position,
                    "mouth_open_ratio": self.lip_sync.mouth_open_ratio,
                    "lip_spread": self.lip_sync.lip_spread,
                    "viseme_index": self.lip_sync.viseme_index,
                    "phoneme": self.lip_sync.phoneme,
                },
                "personality": self.personality.to_dict(),
                "rendering_params": self.rendering_params,
            }

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> AvatarState:
            """Deserialize and validate state from a dictionary."""
            personality_type = PersonalityType(data["personality_type"])
            em = data["emotion"]
            emotion = EmotionState(**em)
            ls = data["lip_sync"]
            lip_sync = LipSyncState(
                landmarks=[tuple(p) for p in ls.get("landmarks", [])],  # type: ignore[misc]
                timestamp=float(ls.get("timestamp", time.time())),
                audio_position=float(ls.get("audio_position", 0.0)),
                mouth_open_ratio=float(ls.get("mouth_open_ratio", 0.0)),
                lip_spread=float(ls.get("lip_spread", 0.0)),
                viseme_index=int(ls.get("viseme_index", 0)),
                phoneme=str(ls.get("phoneme", "")),
            )
            personality = PersonalityProfile.from_dict(data["personality"])
            return cls(
                personality_type=personality_type,
                emotion=emotion,
                lip_sync=lip_sync,
                personality=personality,
                rendering_params=data.get("rendering_params", {}),
            )

except ImportError:
    # Fallback dataclass implementation when pydantic is not installed
    import dataclasses

    @dataclasses.dataclass
    class EmotionState:  # type: ignore[no-redef]
        emotion: str = "neutral"
        confidence: float = 1.0
        timestamp: float = dataclasses.field(default_factory=time.time)
        valence: float = 0.0
        arousal: float = 0.0
        action_units: dict[int, float] = dataclasses.field(default_factory=dict)

        def __post_init__(self) -> None:
            if self.emotion not in EMOTION_CATEGORIES:
                msg = f"Invalid emotion '{self.emotion}'"
                raise ValueError(msg)
            if not 0.0 <= self.confidence <= 1.0:
                msg = f"Confidence {self.confidence} out of [0,1]"
                raise ValueError(msg)

        @classmethod
        def neutral(cls) -> EmotionState:
            return cls(emotion="neutral", confidence=1.0)

        @classmethod
        def from_emotion_name(cls, emotion: str, confidence: float = 0.8) -> EmotionState:
            emotion = LEGACY_EMOTION_MAP.get(emotion, emotion)
            if emotion not in EMOTION_CATEGORIES:
                emotion = "neutral"
            valence, arousal = EMOTION_VALENCE_AROUSAL.get(emotion, (0.0, 0.0))
            aus = {k: v * confidence for k, v in EMOTION_FACS_MAP.get(emotion, {}).items()}
            return cls(
                emotion=emotion,
                confidence=confidence,
                valence=valence,
                arousal=arousal,
                action_units=aus,
            )

        def model_dump(self) -> dict[str, Any]:
            return dataclasses.asdict(self)

    @dataclasses.dataclass
    class LipSyncState:  # type: ignore[no-redef]
        landmarks: list[tuple[float, float]] = dataclasses.field(default_factory=list)
        timestamp: float = dataclasses.field(default_factory=time.time)
        audio_position: float = 0.0
        mouth_open_ratio: float = 0.0
        lip_spread: float = 0.0
        viseme_index: int = 0
        phoneme: str = ""

        @classmethod
        def neutral(cls) -> LipSyncState:
            return cls(landmarks=_build_neutral_landmarks(), mouth_open_ratio=0.0)

    @dataclasses.dataclass
    class PersonalityProfile:  # type: ignore[no-redef]
        name: str = "default"
        friendliness: float = 0.5
        formality: float = 0.5
        expressiveness: float = 0.5
        responsiveness: float = 0.5
        humor: float = 0.5
        empathy: float = 0.5
        behavior_rules: list[dict[str, Any]] = dataclasses.field(default_factory=list)

        def __post_init__(self) -> None:
            for trait in (
                "friendliness",
                "formality",
                "expressiveness",
                "responsiveness",
                "humor",
                "empathy",
            ):
                val = getattr(self, trait)
                if not 0.0 <= val <= 1.0:
                    msg = f"Trait '{trait}' value {val} out of [0,1]"
                    raise ValueError(msg)

        def to_dict(self) -> dict[str, Any]:
            return dataclasses.asdict(self)

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> PersonalityProfile:
            fields = {f.name for f in dataclasses.fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in fields})

    @dataclasses.dataclass
    class AvatarState:  # type: ignore[no-redef]
        personality_type: PersonalityType = PersonalityType.GURU
        emotion: EmotionState = dataclasses.field(default_factory=EmotionState)
        lip_sync: LipSyncState = dataclasses.field(default_factory=LipSyncState)
        personality: PersonalityProfile = dataclasses.field(default_factory=PersonalityProfile)
        rendering_params: dict[str, Any] = dataclasses.field(default_factory=dict)

        def to_dict(self) -> dict[str, Any]:
            return {
                "personality_type": self.personality_type.value,
                "emotion": self.emotion.model_dump(),
                "lip_sync": dataclasses.asdict(self.lip_sync),
                "personality": self.personality.to_dict(),
                "rendering_params": self.rendering_params,
            }

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> AvatarState:
            personality_type = PersonalityType(data["personality_type"])
            emotion = EmotionState(**data["emotion"])
            ls = data["lip_sync"]
            lip_sync = LipSyncState(
                landmarks=[tuple(p) for p in ls.get("landmarks", [])],  # type: ignore[misc]
                timestamp=float(ls.get("timestamp", time.time())),
                audio_position=float(ls.get("audio_position", 0.0)),
                mouth_open_ratio=float(ls.get("mouth_open_ratio", 0.0)),
                lip_spread=float(ls.get("lip_spread", 0.0)),
                viseme_index=int(ls.get("viseme_index", 0)),
                phoneme=str(ls.get("phoneme", "")),
            )
            personality = PersonalityProfile.from_dict(data["personality"])
            return cls(
                personality_type=personality_type,
                emotion=emotion,
                lip_sync=lip_sync,
                personality=personality,
                rendering_params=data.get("rendering_params", {}),
            )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _build_neutral_landmarks() -> list[tuple[float, float]]:
    """Build normalized neutral mouth landmark positions."""
    # 40 landmarks for the full mouth region (upper + lower lip, inner + outer)
    landmarks = []
    # Upper lip outer (10 points, y=0.63)
    for i in range(10):
        x = 0.40 + i * 0.02
        landmarks.append((x, 0.63))
    # Lower lip outer (10 points, y=0.67)
    for i in range(10):
        x = 0.40 + i * 0.02
        landmarks.append((x, 0.67))
    # Upper lip inner (10 points, y=0.645)
    for i in range(10):
        x = 0.41 + i * 0.018
        landmarks.append((x, 0.645))
    # Lower lip inner (10 points, y=0.655)
    for i in range(10):
        x = 0.41 + i * 0.018
        landmarks.append((x, 0.655))
    return landmarks


def normalize_emotion(emotion: str) -> str:
    """Normalize a legacy or variant emotion name to the canonical 27-emotion set."""
    emotion = emotion.lower().strip().replace(" ", "_")
    if emotion in EMOTION_CATEGORIES:
        return emotion
    return LEGACY_EMOTION_MAP.get(emotion, "neutral")
