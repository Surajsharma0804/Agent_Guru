"""Module: Agent_Guru.avatar.personality.engine
Purpose: Apply personality traits to avatar emotion expression and behavior.

Requirements: Req 3 (Dual Personality Engine)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from Agent_Guru.avatar.models import (
    EMOTION_CATEGORIES,
    AvatarState,
    EmotionState,
    PersonalityProfile,
    PersonalityType,
)

logger = logging.getLogger("guruvision.avatar.personality")

# Default profiles embedded so the engine works without config files
_DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "guru": {
        "name": "guru",
        "friendliness": 0.7,
        "formality": 0.8,
        "expressiveness": 0.6,
        "responsiveness": 0.75,
        "humor": 0.4,
        "empathy": 0.65,
        "behavior_rules": [
            {"trigger": "user_emotion:sadness", "response": "neutral", "intensity": 0.6},
            {"trigger": "user_emotion:joy", "response": "joy", "intensity": 0.7},
            {"trigger": "user_emotion:happy", "response": "joy", "intensity": 0.7},
            {"trigger": "greeting", "response": "joy", "intensity": 0.6},
        ],
    },
    "maya": {
        "name": "maya",
        "friendliness": 0.95,
        "formality": 0.3,
        "expressiveness": 0.9,
        "responsiveness": 0.9,
        "humor": 0.75,
        "empathy": 0.95,
        "behavior_rules": [
            {"trigger": "user_emotion:sadness", "response": "sadness", "intensity": 0.7},
            {"trigger": "user_emotion:joy", "response": "joy", "intensity": 0.95},
            {"trigger": "user_emotion:happy", "response": "joy", "intensity": 0.95},
            {"trigger": "greeting", "response": "joy", "intensity": 0.9},
        ],
    },
}


class PersonalityEngine:
    """Apply personality traits to emotion expression and behavior.

    Args:
        profile_path: Optional path to a JSON personality config file.
            When None, the built-in default for the requested personality
            is used.

    """

    def __init__(self, profile_path: str | None = None) -> None:
        self._profile_path = profile_path
        self._profiles: dict[str, PersonalityProfile] = {}
        self._behavior_rules: dict[str, list[dict[str, Any]]] = {}
        self._load_defaults()
        if profile_path:
            self._load_from_file(profile_path)

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def load_profile(self, profile_path: str) -> PersonalityProfile:
        """Load and validate a personality profile from a JSON file.

        Args:
            profile_path: Path to the JSON config file.

        Returns:
            Validated :class:`PersonalityProfile`.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If required traits are missing or out of range.

        """
        from Agent_Guru.utils.path_utils import safe_path as _safe_path

        resolved = _safe_path(
            Path(profile_path).resolve().parent,
            Path(profile_path).resolve().name,
        )
        if not resolved.exists():
            msg = f"Personality profile not found: {profile_path}"
            raise FileNotFoundError(msg)

        with resolved.open() as fh:
            data = json.load(fh)

        profile = PersonalityProfile.from_dict(data)
        self._profiles[profile.name] = profile
        self._behavior_rules[profile.name] = data.get("behavior_rules", [])
        logger.info("Loaded personality profile '%s' from %s", profile.name, profile_path)
        return profile

    def get_profile(self, personality_type: PersonalityType) -> PersonalityProfile:
        """Return the profile for the given personality type."""
        name = personality_type.value
        if name not in self._profiles:
            logger.warning("Profile '%s' not loaded - using default", name)
            self._load_defaults()
        return self._profiles.get(name, PersonalityProfile())

    # ------------------------------------------------------------------
    # Emotion modulation
    # ------------------------------------------------------------------

    def modulate_emotion(
        self,
        emotion: EmotionState,
        personality: PersonalityProfile,
    ) -> EmotionState:
        """Apply personality traits to emotion intensity.

        High expressiveness amplifies confidence; high formality dampens
        extreme negative emotions.

        Args:
            emotion: Raw detected emotion.
            personality: Active personality profile.

        Returns:
            Modulated :class:`EmotionState` with adjusted confidence.

        """
        intensity = emotion.confidence
        # Expressiveness scales intensity
        intensity *= 0.5 + personality.expressiveness * 0.5
        # Formality dampens extreme negative emotions
        if emotion.emotion in ("anger", "fear", "disgust", "horror", "anxiety"):
            intensity *= 1.0 - personality.formality * 0.3

        return EmotionState(
            emotion=emotion.emotion,
            confidence=float(np.clip(intensity, 0.0, 1.0)),
            timestamp=emotion.timestamp,
        )

    def generate_response_emotion(
        self,
        user_emotion: EmotionState,
        personality: PersonalityProfile,
    ) -> EmotionState:
        """Generate an avatar emotional response to the user's emotion.

        High friendliness mirrors positive emotions; high empathy mirrors
        negative emotions.

        Args:
            user_emotion: Detected user emotion.
            personality: Active personality profile.

        Returns:
            Avatar response :class:`EmotionState`.

        """
        rules = self._behavior_rules.get(personality.name, [])
        trigger_key = f"user_emotion:{user_emotion.emotion}"

        for rule in rules:
            if rule.get("trigger") == trigger_key:
                response_emotion = rule.get("response", "neutral")
                base_intensity = float(rule.get("intensity", 0.5))
                # Scale by responsiveness
                intensity = base_intensity * personality.responsiveness
                return EmotionState(
                    emotion=response_emotion
                    if response_emotion in EMOTION_CATEGORIES
                    else "neutral",
                    confidence=float(np.clip(intensity, 0.0, 1.0)),
                    timestamp=time.time(),
                )

        # Default: mirror positive, stay neutral for negative
        if user_emotion.emotion in ("joy", "happy", "amusement", "excitement", "triumph"):
            return EmotionState(
                emotion="joy",
                confidence=float(
                    np.clip(user_emotion.confidence * personality.friendliness, 0.0, 1.0),
                ),
                timestamp=time.time(),
            )
        return EmotionState(emotion="neutral", confidence=0.8, timestamp=time.time())

    def apply_behavior_rules(self, state: AvatarState) -> AvatarState:
        """Apply rule-based behavior patterns to the avatar state.

        Args:
            state: Current avatar state.

        Returns:
            Updated :class:`AvatarState` with behavior-adjusted emotion.

        """
        modulated = self.modulate_emotion(state.emotion, state.personality)
        return AvatarState(
            personality_type=state.personality_type,
            emotion=modulated,
            lip_sync=state.lip_sync,
            personality=state.personality,
            rendering_params=state.rendering_params,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_defaults(self) -> None:
        for name, data in _DEFAULT_PROFILES.items():
            try:
                profile = PersonalityProfile.from_dict(data)
                self._profiles[name] = profile
                self._behavior_rules[name] = data.get("behavior_rules", [])
            except ValueError as exc:
                logger.exception("Failed to load default profile '%s': %s", name, exc)

    def _load_from_file(self, profile_path: str) -> None:
        try:
            self.load_profile(profile_path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            logger.exception(
                "Could not load profile from '%s': %s - using defaults",
                profile_path,
                exc,
            )
