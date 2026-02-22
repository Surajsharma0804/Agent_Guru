"""
Tone and personality adaptation for conversation strategy.

This module implements:
- Personality dimension definitions
- User preference learning for tone
- Context-based adaptation
- Response templates per tone type

Requirements: 19.4, 26.2, 26.3
"""

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Optional


class PersonalityDimension(Enum):
    """Personality dimensions for tone adaptation."""

    # Professional ↔ Casual
    FORMALITY = "formality"  # 0.0 = casual, 1.0 = professional

    # Formal ↔ Friendly
    WARMTH = "warmth"  # 0.0 = formal, 1.0 = friendly

    # Concise ↔ Verbose
    VERBOSITY = "verbosity"  # 0.0 = concise, 1.0 = verbose


@dataclass
class ToneProfile:
    """User's tone preferences."""

    formality: float  # 0.0 to 1.0
    warmth: float  # 0.0 to 1.0
    verbosity: float  # 0.0 to 1.0

    def __post_init__(self):
        """Validate tone values."""
        self.formality = max(0.0, min(1.0, self.formality))
        self.warmth = max(0.0, min(1.0, self.warmth))
        self.verbosity = max(0.0, min(1.0, self.verbosity))


@dataclass
class ContextualFactors:
    """Contextual factors affecting tone."""

    time_of_day: Optional[datetime] = None
    is_work_hours: bool = False
    battery_level: Optional[float] = None
    user_stress_level: Optional[float] = None
    conversation_length: int = 0


class ToneAdapter:
    """Adapts response tone based on user preferences and context."""

    # Default tone profile (balanced)
    DEFAULT_PROFILE = ToneProfile(formality=0.5, warmth=0.6, verbosity=0.5)

    # Work hours definition
    WORK_START = time(9, 0)
    WORK_END = time(17, 0)

    def __init__(self):
        """Initialize tone adapter."""
        self.user_profiles: dict[str, ToneProfile] = {}

    def get_tone_profile(
        self, user_id: str, context: Optional[ContextualFactors] = None
    ) -> ToneProfile:
        """
        Get tone profile for user with contextual adjustments.

        Args:
            user_id: User identifier
            context: Contextual factors

        Returns:
            Adjusted tone profile
        """
        # Get base profile
        base_profile = self.user_profiles.get(user_id, self.DEFAULT_PROFILE)

        # Apply contextual adjustments if provided
        if context:
            return self._apply_context(base_profile, context)

        return base_profile

    def learn_preference(
        self, user_id: str, dimension: PersonalityDimension, value: float, weight: float = 0.1
    ) -> None:
        """
        Learn user's tone preference using exponential moving average.

        Args:
            user_id: User identifier
            dimension: Personality dimension to update
            value: New observed value (0.0 to 1.0)
            weight: Learning rate (0.0 to 1.0)
        """
        # Get current profile
        current = self.user_profiles.get(user_id, self.DEFAULT_PROFILE)

        # Update dimension using exponential moving average
        if dimension == PersonalityDimension.FORMALITY:
            new_formality = (1 - weight) * current.formality + weight * value
            self.user_profiles[user_id] = ToneProfile(
                formality=new_formality, warmth=current.warmth, verbosity=current.verbosity
            )
        elif dimension == PersonalityDimension.WARMTH:
            new_warmth = (1 - weight) * current.warmth + weight * value
            self.user_profiles[user_id] = ToneProfile(
                formality=current.formality, warmth=new_warmth, verbosity=current.verbosity
            )
        elif dimension == PersonalityDimension.VERBOSITY:
            new_verbosity = (1 - weight) * current.verbosity + weight * value
            self.user_profiles[user_id] = ToneProfile(
                formality=current.formality, warmth=current.warmth, verbosity=new_verbosity
            )

    def set_profile(self, user_id: str, profile: ToneProfile) -> None:
        """
        Set user's tone profile directly.

        Args:
            user_id: User identifier
            profile: Tone profile to set
        """
        self.user_profiles[user_id] = profile

    def _apply_context(self, base_profile: ToneProfile, context: ContextualFactors) -> ToneProfile:
        """
        Apply contextual adjustments to tone profile.

        Args:
            base_profile: Base tone profile
            context: Contextual factors

        Returns:
            Adjusted tone profile
        """
        formality = base_profile.formality
        warmth = base_profile.warmth
        verbosity = base_profile.verbosity

        # Work hours: increase formality, decrease warmth
        if context.is_work_hours:
            formality = min(1.0, formality + 0.2)
            warmth = max(0.0, warmth - 0.1)

        # Low battery: decrease verbosity (be concise)
        if context.battery_level is not None and context.battery_level < 0.2:
            verbosity = max(0.0, verbosity - 0.3)

        # High stress: increase warmth, decrease verbosity
        if context.user_stress_level is not None and context.user_stress_level > 0.7:
            warmth = min(1.0, warmth + 0.2)
            verbosity = max(0.0, verbosity - 0.2)

        # Long conversation: decrease verbosity
        if context.conversation_length > 10:
            verbosity = max(0.0, verbosity - 0.1)

        # Time of day adjustments
        if context.time_of_day:
            hour = context.time_of_day.hour

            # Early morning (5-8): more formal, less verbose
            if 5 <= hour < 8:
                formality = min(1.0, formality + 0.1)
                verbosity = max(0.0, verbosity - 0.1)

            # Late night (22-24): more casual, warmer
            elif 22 <= hour < 24:
                formality = max(0.0, formality - 0.1)
                warmth = min(1.0, warmth + 0.1)

        return ToneProfile(formality=formality, warmth=warmth, verbosity=verbosity)

    def adapt_response(self, response: str, tone_profile: ToneProfile) -> str:
        """
        Adapt response text to match tone profile.

        Args:
            response: Original response text
            tone_profile: Target tone profile

        Returns:
            Adapted response text
        """
        # Apply formality adjustments
        if tone_profile.formality > 0.7:
            response = self._make_formal(response)
        elif tone_profile.formality < 0.3:
            response = self._make_casual(response)

        # Apply warmth adjustments
        if tone_profile.warmth > 0.7:
            response = self._make_friendly(response)
        elif tone_profile.warmth < 0.3:
            response = self._make_neutral(response)

        # Apply verbosity adjustments
        if tone_profile.verbosity > 0.7:
            response = self._make_verbose(response)
        elif tone_profile.verbosity < 0.3:
            response = self._make_concise(response)

        return response

    def _make_formal(self, text: str) -> str:
        """Make text more formal."""
        # Replace casual contractions
        replacements = {
            "I'll": "I will",
            "you'll": "you will",
            "can't": "cannot",
            "won't": "will not",
            "don't": "do not",
            "doesn't": "does not",
            "isn't": "is not",
            "aren't": "are not",
        }

        for casual, formal in replacements.items():
            text = text.replace(casual, formal)

        return text

    def _make_casual(self, text: str) -> str:
        """Make text more casual."""
        # Replace formal phrases
        replacements = {
            "I will": "I'll",
            "you will": "you'll",
            "cannot": "can't",
            "will not": "won't",
            "do not": "don't",
            "does not": "doesn't",
            "is not": "isn't",
            "are not": "aren't",
        }

        for formal, casual in replacements.items():
            text = text.replace(formal, casual)

        return text

    def _make_friendly(self, text: str) -> str:
        """Make text more friendly."""
        # Add friendly phrases
        if not any(text.startswith(prefix) for prefix in ["Sure", "Great", "Happy to"]):
            text = f"Happy to help! {text}"

        return text

    def _make_neutral(self, text: str) -> str:
        """Make text more neutral."""
        # Remove overly friendly phrases
        friendly_phrases = [
            "Happy to help! ",
            "Great! ",
            "Awesome! ",
            "Sure thing! ",
        ]

        for phrase in friendly_phrases:
            text = text.replace(phrase, "")

        return text

    def _make_verbose(self, text: str) -> str:
        """Make text more verbose."""
        # Add explanatory phrases
        if "." in text and not text.endswith("Let me know if you need anything else."):
            text = f"{text} Let me know if you need anything else."

        return text

    def _make_concise(self, text: str) -> str:
        """Make text more concise."""
        # Remove unnecessary phrases
        verbose_phrases = [
            "Let me know if you need anything else.",
            "Feel free to ask if you have questions.",
            "I'm here to help.",
        ]

        for phrase in verbose_phrases:
            text = text.replace(phrase, "").strip()

        return text

    @staticmethod
    def is_work_hours(current_time: datetime) -> bool:
        """
        Determine if current time is work hours.

        Args:
            current_time: Current datetime

        Returns:
            True if work hours
        """
        # Weekend check
        if current_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Time check
        current = current_time.time()
        return ToneAdapter.WORK_START <= current <= ToneAdapter.WORK_END


class ResponseTemplateSelector:
    """Selects appropriate response templates based on tone."""

    # Templates by tone type
    TEMPLATES = {
        "success_formal": [
            "I have completed {action} successfully.",
            "The {action} has been completed as requested.",
        ],
        "success_casual": [
            "Done! I've {action}.",
            "All set! {action} is complete.",
        ],
        "success_friendly": [
            "Great! I've {action} for you.",
            "Happy to help! {action} is done.",
        ],
        "error_formal": [
            "I was unable to complete {action}. {reason}",
            "The {action} could not be completed. {reason}",
        ],
        "error_casual": [
            "Couldn't {action}. {reason}",
            "Sorry, {action} didn't work. {reason}",
        ],
        "error_friendly": [
            "Oops! I couldn't {action}. {reason}",
            "Sorry about that! {action} didn't work. {reason}",
        ],
    }

    @staticmethod
    def select_template(template_type: str, tone_profile: ToneProfile) -> str:
        """
        Select appropriate template based on tone profile.

        Args:
            template_type: Type of template ("success" or "error")
            tone_profile: User's tone profile

        Returns:
            Selected template string
        """
        # Determine tone category
        if tone_profile.formality > 0.7:
            tone_key = f"{template_type}_formal"
        elif tone_profile.warmth > 0.7:
            tone_key = f"{template_type}_friendly"
        else:
            tone_key = f"{template_type}_casual"

        # Get templates for this category
        templates = ResponseTemplateSelector.TEMPLATES.get(tone_key, [])

        if not templates:
            # Fallback to casual
            tone_key = f"{template_type}_casual"
            templates = ResponseTemplateSelector.TEMPLATES.get(tone_key, [])

        # Return first template (could be randomized)
        return templates[0] if templates else "{action}"
