"""Multi-platform onboarding wizard.

Thin facade over OnboardingManager that adds platform-specific
step sequences and UI integration hooks.

Desktop steps (Windows/macOS/Linux):
  1. Welcome
  2. Profile setup
  3. Biometric enrollment (face, voice, fingerprint)
  4. LLM configuration (Ollama local OR cloud API key)
  5. Permission granting (microphone, camera, accessibility)
  6. Background service setup (auto-start on boot)
  7. Test voice interaction
  8. Complete

Mobile steps (Android/iOS):
  1. Welcome
  2. Profile setup
  3. Biometric enrollment
  4. API configuration (required — OpenAI/Gemini/DeepSeek/Anthropic)
  5. Permission granting (microphone, camera, accessibility, background)
  6. Background service setup
  7. Test voice interaction
  8. Complete
"""

from __future__ import annotations

import logging
import platform
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from Agent_Guru.deployment.onboarding import (
    LLMConfig,
    OnboardingManager,
    OnboardingState,
    OnboardingStep,
    UserProfile,
)

logger = logging.getLogger(__name__)

_PLATFORM = platform.system().lower()
_IS_MOBILE = _PLATFORM in ("android", "ios")
_IS_DESKTOP = not _IS_MOBILE


class OnboardingWizard:
    """Multi-platform onboarding wizard.

    Wraps OnboardingManager to provide a step-by-step guided setup
    experience with platform-specific flows and UI callbacks.

    Example:
        >>> wizard = OnboardingWizard()
        >>> if wizard.needs_onboarding():
        ...     wizard.run()

    Platform:
        - Desktop: Supports local Ollama + cloud API options
        - Mobile: Cloud API only (required)
    """

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._manager = OnboardingManager(state_path=state_path)
        self._on_step_change: Optional[Callable[[OnboardingStep], None]] = None
        self._on_complete: Optional[Callable[[OnboardingState], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def needs_onboarding(self) -> bool:
        """Return True if onboarding has not been completed."""
        return self._manager.needs_onboarding()

    def run(self) -> OnboardingState:
        """Run the full onboarding wizard.

        Starts or resumes onboarding from the current step.
        Calls registered callbacks on step changes and completion.

        Returns:
            Final OnboardingState after completion.
        """
        state = self._manager.start_onboarding()
        logger.info("Onboarding started at step: %s (platform=%s)",
                    state.current_step.value, _PLATFORM)
        return state

    def complete_step(
        self,
        step: OnboardingStep,
        data: Optional[Dict[str, Any]] = None,
    ) -> OnboardingState:
        """Complete a step and advance to the next.

        Args:
            step: The step being completed.
            data: Step-specific data dict.

        Returns:
            Updated OnboardingState.
        """
        state = self._manager.complete_step(step, data)

        if self._on_step_change:
            self._on_step_change(state.current_step)

        if state.completed and self._on_complete:
            self._on_complete(state)
            logger.info("Onboarding completed")

        return state

    def skip_biometric(self) -> OnboardingState:
        """Skip the optional biometric enrollment step."""
        return self._manager.skip_step(OnboardingStep.BIOMETRIC)

    def go_back(self) -> OnboardingState:
        """Navigate to the previous step."""
        return self._manager.go_back()

    def get_progress(self) -> Dict[str, Any]:
        """Return progress info: step index, total steps, percent."""
        return self._manager.get_progress()

    def get_state(self) -> OnboardingState:
        """Return current onboarding state."""
        return self._manager.get_state()

    def reset(self) -> None:
        """Reset onboarding (e.g., from settings)."""
        self._manager.reset_onboarding()
        logger.info("Onboarding reset")

    # ------------------------------------------------------------------
    # Platform helpers
    # ------------------------------------------------------------------

    @property
    def is_desktop(self) -> bool:
        """True if running on a desktop platform."""
        return _IS_DESKTOP

    @property
    def is_mobile(self) -> bool:
        """True if running on a mobile platform."""
        return _IS_MOBILE

    @property
    def platform(self) -> str:
        """Current platform identifier."""
        return _PLATFORM

    def get_llm_options(self) -> Dict[str, Any]:
        """Return available LLM options for the current platform.

        Desktop: Ollama (local, recommended) + cloud APIs
        Mobile: Cloud APIs only (required)
        """
        cloud_providers = ["openai", "gemini", "anthropic", "deepseek"]
        if _IS_DESKTOP:
            return {
                "recommended": "ollama",
                "providers": ["ollama"] + cloud_providers,
                "ollama_note": "Free, private, offline — recommended for desktop",
            }
        return {
            "recommended": "openai",
            "providers": cloud_providers,
            "note": "Cloud API required on mobile (user-owned API key)",
        }

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_step_change(self, callback: Callable[[OnboardingStep], None]) -> None:
        """Register callback invoked when the current step changes."""
        self._on_step_change = callback

    def on_complete(self, callback: Callable[[OnboardingState], None]) -> None:
        """Register callback invoked when onboarding completes."""
        self._on_complete = callback
