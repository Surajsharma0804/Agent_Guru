"""
Onboarding flow for the Guru Deployment System.

Guides new users through complete AGENT_GURU setup:
1. Welcome
2. Profile setup
3. Biometric enrollment
4. LLM configuration
5. Permission granting
6. Completion

Supports interrupted onboarding (saves progress, resumes on next launch).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger(__name__)


class OnboardingStep(str, Enum):
    """Steps in the onboarding flow."""

    WELCOME = "welcome"
    PROFILE = "profile"
    BIOMETRIC = "biometric"
    LLM_CONFIG = "llm_config"
    PERMISSIONS = "permissions"
    COMPLETE = "complete"


_STEP_ORDER: List[OnboardingStep] = [
    OnboardingStep.WELCOME,
    OnboardingStep.PROFILE,
    OnboardingStep.BIOMETRIC,
    OnboardingStep.LLM_CONFIG,
    OnboardingStep.PERMISSIONS,
    OnboardingStep.COMPLETE,
]


class UserProfile(BaseModel):
    """User profile collected during onboarding."""

    name: str = Field(..., min_length=1, max_length=100)
    gender: str = Field(..., pattern=r"^(male|female|other|prefer_not_to_say)$")
    age: int = Field(..., ge=13, le=120)
    date_of_birth: str = Field(..., description="ISO date string YYYY-MM-DD")

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"Invalid date_of_birth: {v}") from exc
        return v


class LLMConfig(BaseModel):
    """LLM configuration collected during onboarding."""

    provider: str = Field(..., pattern=r"^(ollama|openai|gemini|anthropic|deepseek)$")
    api_key: Optional[str] = Field(None, description="API key for cloud providers")
    model_name: Optional[str] = None
    ollama_url: Optional[str] = Field(None, description="Ollama server URL for local mode")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: Optional[str], info: Any) -> Optional[str]:
        # Cloud providers require an API key
        if v is not None and len(v.strip()) == 0:
            raise ValueError("api_key must not be empty if provided")
        return v


class OnboardingState(BaseModel):
    """Persistent onboarding state saved between sessions."""

    completed: bool = False
    current_step: OnboardingStep = OnboardingStep.WELCOME
    profile: Optional[UserProfile] = None
    llm_config: Optional[LLMConfig] = None
    biometric_enrolled: bool = False
    permissions_granted: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class OnboardingManager:
    """
    Manages the onboarding flow with persistent state.

    Supports:
    - Automatic launch on first run
    - Interrupted onboarding resume
    - Step validation before advancing
    - Back navigation
    """

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._state_path = state_path or Path(".guru/onboarding_state.json")
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_completed(self) -> bool:
        """Return True if onboarding has been completed."""
        return self._state.completed

    def needs_onboarding(self) -> bool:
        """Return True if onboarding should be launched."""
        return not self._state.completed

    def get_current_step(self) -> OnboardingStep:
        """Return the current onboarding step."""
        return self._state.current_step

    def get_state(self) -> OnboardingState:
        """Return a copy of the current onboarding state."""
        return self._state.model_copy(deep=True)

    def start_onboarding(self) -> OnboardingState:
        """
        Start or resume onboarding.

        If already completed, resets to allow re-running from settings.
        """
        if not self._state.started_at:
            self._state.started_at = datetime.now(timezone.utc).isoformat()
        self._save_state()
        logger.info("onboarding_started", step=self._state.current_step.value)
        return self.get_state()

    def reset_onboarding(self) -> None:
        """Reset onboarding to allow re-running from settings."""
        self._state = OnboardingState()
        self._save_state()
        logger.info("onboarding_reset")

    def complete_step(
        self,
        step: OnboardingStep,
        data: Optional[Dict[str, Any]] = None,
    ) -> OnboardingState:
        """
        Complete a step and advance to the next.

        Args:
            step: The step being completed.
            data: Step-specific data (profile, llm_config, etc.).

        Returns:
            Updated onboarding state.

        Raises:
            ValueError: If step data is invalid or step is out of order.
        """
        if step != self._state.current_step:
            raise ValueError(
                f"Expected step '{self._state.current_step.value}', "
                f"got '{step.value}'"
            )

        self._apply_step_data(step, data or {})
        next_step = self._next_step(step)

        if next_step is None:
            # All steps complete
            self._state.current_step = OnboardingStep.COMPLETE
            self._state.completed = True
            self._state.completed_at = datetime.now(timezone.utc).isoformat()
            logger.info("onboarding_completed")
        else:
            self._state.current_step = next_step
            logger.info("onboarding_step_completed", step=step.value,
                        next_step=next_step.value)

        self._save_state()
        return self.get_state()

    def go_back(self) -> OnboardingState:
        """Navigate to the previous step."""
        current_idx = _STEP_ORDER.index(self._state.current_step)
        if current_idx > 0:
            self._state.current_step = _STEP_ORDER[current_idx - 1]
            self._save_state()
            logger.info("onboarding_back", step=self._state.current_step.value)
        return self.get_state()

    def skip_step(self, step: OnboardingStep) -> OnboardingState:
        """
        Skip an optional step (e.g., biometric enrollment).

        Only BIOMETRIC step is skippable.
        """
        _skippable = {OnboardingStep.BIOMETRIC}
        if step not in _skippable:
            raise ValueError(f"Step '{step.value}' is not skippable")
        if step != self._state.current_step:
            raise ValueError(f"Cannot skip step '{step.value}' — not the current step")

        next_step = self._next_step(step)
        self._state.current_step = next_step or OnboardingStep.COMPLETE
        self._save_state()
        logger.info("onboarding_step_skipped", step=step.value)
        return self.get_state()

    def get_progress(self) -> Dict[str, Any]:
        """Return progress info: current step index and total steps."""
        current_idx = _STEP_ORDER.index(self._state.current_step)
        return {
            "current_step": self._state.current_step.value,
            "step_index": current_idx,
            "total_steps": len(_STEP_ORDER),
            "percent": round(current_idx / len(_STEP_ORDER) * 100),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_step_data(self, step: OnboardingStep, data: Dict[str, Any]) -> None:
        """Validate and apply step-specific data to state."""
        if step == OnboardingStep.PROFILE:
            self._state.profile = UserProfile(**data)
        elif step == OnboardingStep.LLM_CONFIG:
            self._state.llm_config = LLMConfig(**data)
        elif step == OnboardingStep.BIOMETRIC:
            self._state.biometric_enrolled = bool(data.get("enrolled", False))
        elif step == OnboardingStep.PERMISSIONS:
            self._state.permissions_granted = list(data.get("granted", []))

    @staticmethod
    def _next_step(step: OnboardingStep) -> Optional[OnboardingStep]:
        """Return the next step after the given step, or None if last."""
        idx = _STEP_ORDER.index(step)
        if idx + 1 < len(_STEP_ORDER):
            return _STEP_ORDER[idx + 1]
        return None

    def _load_state(self) -> OnboardingState:
        if self._state_path.exists():
            try:
                raw = json.loads(self._state_path.read_text())
                return OnboardingState(**raw)
            except Exception as exc:
                logger.warning("onboarding_state_load_error", error=str(exc))
        return OnboardingState()

    def _save_state(self) -> None:
        self._state_path.write_text(
            self._state.model_dump_json(indent=2)
        )
