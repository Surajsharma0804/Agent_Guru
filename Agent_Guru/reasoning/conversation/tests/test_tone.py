"""
Tests for tone and personality adaptation.
"""

from datetime import datetime, timezone

import pytest

from Agent_Guru.reasoning.conversation.tone import (
    ContextualFactors,
    PersonalityDimension,
    ResponseTemplateSelector,
    ToneAdapter,
    ToneProfile,
)


class TestToneProfile:
    """Test tone profile."""

    def test_tone_profile_validation(self):
        """Test tone profile validates values."""
        profile = ToneProfile(formality=1.5, warmth=-0.5, verbosity=0.5)

        assert profile.formality == 1.0  # Clamped to max  # nosec B101
        assert profile.warmth == 0.0  # Clamped to min  # nosec B101
        assert profile.verbosity == 0.5  # nosec B101


class TestToneAdapter:
    """Test tone adapter."""

    def test_get_default_profile(self):
        """Test getting default profile for new user."""
        adapter = ToneAdapter()

        profile = adapter.get_tone_profile("user123")

        assert profile.formality == 0.5  # nosec B101
        assert profile.warmth == 0.6  # nosec B101
        assert profile.verbosity == 0.5  # nosec B101

    def test_learn_preference(self):
        """Test learning user preference."""
        adapter = ToneAdapter()

        # Learn formality preference
        adapter.learn_preference("user123", PersonalityDimension.FORMALITY, 0.8)

        profile = adapter.get_tone_profile("user123")

        # Should move towards 0.8
        assert profile.formality > 0.5  # nosec B101

    def test_context_work_hours(self):
        """Test context adjustment for work hours."""
        adapter = ToneAdapter()

        context = ContextualFactors(
            time_of_day=datetime(2024, 1, 1, 10, 0), is_work_hours=True  # Monday 10 AM
        )

        profile = adapter.get_tone_profile("user123", context)

        # Should be more formal during work hours
        assert profile.formality > ToneAdapter.DEFAULT_PROFILE.formality  # nosec B101

    def test_context_low_battery(self):
        """Test context adjustment for low battery."""
        adapter = ToneAdapter()

        context = ContextualFactors(battery_level=0.15)

        profile = adapter.get_tone_profile("user123", context)

        # Should be less verbose with low battery
        assert profile.verbosity < ToneAdapter.DEFAULT_PROFILE.verbosity  # nosec B101

    def test_adapt_response_formal(self):
        """Test adapting response to formal tone."""
        adapter = ToneAdapter()

        profile = ToneProfile(formality=0.9, warmth=0.3, verbosity=0.5)
        response = "I'll set a timer for you."

        adapted = adapter.adapt_response(response, profile)

        # Should expand contractions
        assert "I will" in adapted or "I'll" not in adapted  # nosec B101

    def test_adapt_response_casual(self):
        """Test adapting response to casual tone."""
        adapter = ToneAdapter()

        profile = ToneProfile(formality=0.2, warmth=0.5, verbosity=0.5)
        response = "I will set a timer for you."

        adapted = adapter.adapt_response(response, profile)

        # Should use contractions
        assert "I'll" in adapted or "I will" not in adapted  # nosec B101

    def test_is_work_hours(self):
        """Test work hours detection."""
        # Monday 10 AM
        work_time = datetime(2024, 1, 1, 10, 0)
        assert ToneAdapter.is_work_hours(work_time) is True  # nosec B101

        # Monday 8 PM
        evening_time = datetime(2024, 1, 1, 20, 0)
        assert ToneAdapter.is_work_hours(evening_time) is False  # nosec B101

        # Saturday 10 AM
        weekend_time = datetime(2024, 1, 6, 10, 0)
        assert ToneAdapter.is_work_hours(weekend_time) is False  # nosec B101


class TestResponseTemplateSelector:
    """Test response template selector."""

    def test_select_formal_template(self):
        """Test selecting formal template."""
        profile = ToneProfile(formality=0.9, warmth=0.3, verbosity=0.5)

        template = ResponseTemplateSelector.select_template("success", profile)

        assert "completed" in template.lower() or "successfully" in template.lower()  # nosec B101

    def test_select_casual_template(self):
        """Test selecting casual template."""
        profile = ToneProfile(formality=0.2, warmth=0.5, verbosity=0.5)

        template = ResponseTemplateSelector.select_template("success", profile)

        assert "done" in template.lower() or "set" in template.lower()  # nosec B101

    def test_select_friendly_template(self):
        """Test selecting friendly template."""
        profile = ToneProfile(formality=0.5, warmth=0.9, verbosity=0.5)

        template = ResponseTemplateSelector.select_template("success", profile)

        assert "great" in template.lower() or "happy" in template.lower()  # nosec B101


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
