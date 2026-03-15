"""
Agent_Guru.avatar — Production Avatar and Emotion Engine

Provides dual AI personalities (Guru and Maya) with:
  - Real-time emotion recognition (27-emotion Cowen & Keltner taxonomy)
  - Lip synchronization with speech audio (MediaPipe + phoneme-to-viseme)
  - FACS-based personality-driven behavior
  - Interactive rendering (OpenCV / PyQt / headless)
  - Performance monitoring (psutil)
  - Speech and vision system integration

Quick start::

    from Agent_Guru.avatar import GuruAvatarSystem
    from Agent_Guru.avatar.models import PersonalityType

    system = GuruAvatarSystem(render_backend="headless")
    system.initialize()
    system.set_personality(PersonalityType.MAYA)
    frame = system.render_frame()
    system.stop()
"""

from Agent_Guru.avatar.avatar_system import GuruAvatarSystem
from Agent_Guru.avatar.models import (
    EMOTION_CATEGORIES,
    EMOTION_CATEGORIES_27,
    AvatarState,
    EmotionState,
    LipSyncState,
    PersonalityProfile,
    PersonalityType,
    normalize_emotion,
)

__all__ = [
    "GuruAvatarSystem",
    "AvatarState",
    "EmotionState",
    "LipSyncState",
    "PersonalityProfile",
    "PersonalityType",
    "EMOTION_CATEGORIES",
    "EMOTION_CATEGORIES_27",
    "normalize_emotion",
]
