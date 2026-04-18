"""
Module: Agent_Guru.avatar.state_manager
Purpose: Thread-safe central state management for the Avatar system.

Requirements: Req 5 (Avatar State Management)
"""

from __future__ import annotations

import logging
import threading

from Agent_Guru.avatar.models import (
    AvatarState,
    EmotionState,
    LipSyncState,
    PersonalityProfile,
    PersonalityType,
)

logger = logging.getLogger("guruvision.avatar.state_manager")


class StateManager:
    """Thread-safe central state store for the avatar system.

    All reads and writes are protected by a reentrant lock so that
    concurrent component threads never observe a partially-updated state.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = AvatarState()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_state(self) -> AvatarState:
        """Return a shallow copy of the current state (thread-safe)."""
        with self._lock:
            # Return a new AvatarState referencing the same sub-objects.
            # Sub-objects are replaced atomically on update, so this is safe.
            return AvatarState(
                personality_type=self._state.personality_type,
                emotion=self._state.emotion,
                lip_sync=self._state.lip_sync,
                personality=self._state.personality,
                rendering_params=dict(self._state.rendering_params),
            )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def update_emotion(self, emotion: EmotionState) -> bool:
        """Replace the emotion state after validation.

        Returns:
            True on success, False if validation fails.
        """
        try:
            # Validate by constructing — raises on bad values
            validated = EmotionState(
                emotion=emotion.emotion,
                confidence=emotion.confidence,
                timestamp=emotion.timestamp,
                valence=getattr(emotion, "valence", 0.0),
                arousal=getattr(emotion, "arousal", 0.0),
                action_units=getattr(emotion, "action_units", {}),
            )
        except (ValueError, Exception) as exc:
            logger.error("update_emotion rejected: %s", exc)
            return False

        with self._lock:
            self._state.emotion = validated
        return True

    def update_lip_sync(self, lip_sync: LipSyncState) -> bool:
        """Replace the lip sync state after validation.

        Returns:
            True on success, False if validation fails.
        """
        try:
            ratio = lip_sync.mouth_open_ratio
        except AttributeError as e:
            logger.error("update_lip_sync rejected: missing mouth_open_ratio: %s", e)
            return False

        if not 0.0 <= ratio <= 1.0:
            logger.error(
                "update_lip_sync rejected: mouth_open_ratio %s out of [0,1]", ratio
            )
            return False

        with self._lock:
            self._state.lip_sync = lip_sync
        return True

    def update_personality(self, personality: PersonalityProfile) -> bool:
        """Replace the personality profile after validation.

        Returns:
            True on success, False if validation fails.
        """
        try:
            _ = PersonalityProfile(
                name=personality.name,
                friendliness=personality.friendliness,
                formality=personality.formality,
                expressiveness=personality.expressiveness,
                responsiveness=personality.responsiveness,
                humor=personality.humor,
                empathy=personality.empathy,
            )
        except ValueError as exc:
            logger.error("update_personality rejected: %s", exc)
            return False

        with self._lock:
            self._state.personality = personality
        return True

    def switch_personality(self, personality_type: PersonalityType) -> bool:
        """Switch the active personality type.

        Returns:
            True always (switching type is always valid).
        """
        with self._lock:
            self._state.personality_type = personality_type
        logger.info("Personality switched to %s", personality_type.value)
        return True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(self) -> dict:
        """Serialize current state to a plain dictionary."""
        with self._lock:
            return self._state.to_dict()

    def deserialize(self, data: dict) -> bool:
        """Deserialize and validate state from a dictionary.

        Returns:
            True on success, False if validation fails.
        """
        try:
            new_state = AvatarState.from_dict(data)
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("deserialize failed: %s", exc)
            return False

        with self._lock:
            self._state = new_state
        return True
