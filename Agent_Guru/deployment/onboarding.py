"""Onboarding flow for the Guru Deployment System.

Guides new users through complete AGENT_GURU setup:
1. Welcome
2. Profile setup
3. Biometric enrollment
4. LLM configuration
5. Permission granting
6. Completion

Supports interrupted onboarding (saves progress, resumes on next launch).

SECURITY (Round 13): the on-disk state file is plaintext JSON (it also
holds a user profile and progress flags, none of which are secret), but
LLM_CONFIG.api_key is a real cloud-provider credential (OpenAI, Anthropic,
Gemini, DeepSeek). It is never written to that file -- see
OnboardingManager._save_state() / _load_state() for how it is instead
persisted encrypted-at-rest via KeyStore and transparently restored into
memory.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from Agent_Guru.security.crypto.errors import KeyNotFoundError
from Agent_Guru.security.crypto.key_store import KeyStore

logger = structlog.get_logger(__name__)


class OnboardingStep(str, Enum):
    """Steps in the onboarding flow."""

    WELCOME = "welcome"
    PROFILE = "profile"
    BIOMETRIC = "biometric"
    LLM_CONFIG = "llm_config"
    PERMISSIONS = "permissions"
    COMPLETE = "complete"


_STEP_ORDER: list[OnboardingStep] = [
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
            msg = f"Invalid date_of_birth: {v}"
            raise ValueError(msg) from exc
        return v


class LLMConfig(BaseModel):
    """LLM configuration collected during onboarding."""

    provider: str = Field(..., pattern=r"^(ollama|openai|gemini|anthropic|deepseek)$")
    api_key: str | None = Field(None, description="API key for cloud providers")
    model_name: str | None = None
    ollama_url: str | None = Field(None, description="Ollama server URL for local mode")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None, info: Any) -> str | None:
        # Cloud providers require an API key
        if v is not None and len(v.strip()) == 0:
            msg = "api_key must not be empty if provided"
            raise ValueError(msg)
        return v


class OnboardingState(BaseModel):
    """Persistent onboarding state saved between sessions."""

    completed: bool = False
    current_step: OnboardingStep = OnboardingStep.WELCOME
    profile: UserProfile | None = None
    llm_config: LLMConfig | None = None
    biometric_enrolled: bool = False
    permissions_granted: list[str] = Field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None


class OnboardingManager:
    """Manages the onboarding flow with persistent state.

    Supports:
    - Automatic launch on first run
    - Interrupted onboarding resume
    - Step validation before advancing
    - Back navigation
    """

    def __init__(self, state_path: Path | None = None, key_store: KeyStore | None = None) -> None:
        self._state_path = state_path or Path(".guru/onboarding_state.json")
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        # Dependency injection, matching IdentityManager's convention
        # (security/crypto/identity.py) -- callers that already run a
        # GuruSecuritySystem should inject its shared KeyStore instance so
        # LLM credentials land in the same encrypted store (and, once one
        # exists, behind the same master password) as every other secret.
        # Falling back to a private KeyStore keeps this class usable
        # standalone; it uses master_password="" because that is the
        # existing codebase-wide default (see SecurityConfig.master_password
        # in security/security_system.py) -- not a weaker choice made here,
        # but not a solved secrets story either. See _save_state().
        self._key_store = key_store or KeyStore(
            storage_path=str(self._state_path.parent / "onboarding_secrets.db"),
            master_password="",  # nosec B106
        )
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
        """Start or resume onboarding.

        If already completed, resets to allow re-running from settings.
        """
        if not self._state.started_at:
            self._state.started_at = datetime.now(UTC).isoformat()
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
        data: dict[str, Any] | None = None,
    ) -> OnboardingState:
        """Complete a step and advance to the next.

        Args:
            step: The step being completed.
            data: Step-specific data (profile, llm_config, etc.).

        Returns:
            Updated onboarding state.

        Raises:
            ValueError: If step data is invalid or step is out of order.

        """
        if step != self._state.current_step:
            msg = f"Expected step '{self._state.current_step.value}', got '{step.value}'"
            raise ValueError(
                msg,
            )

        self._apply_step_data(step, data or {})
        next_step = self._next_step(step)

        if next_step is None:
            # All steps complete
            self._state.current_step = OnboardingStep.COMPLETE
            self._state.completed = True
            self._state.completed_at = datetime.now(UTC).isoformat()
            logger.info("onboarding_completed")
        else:
            self._state.current_step = next_step
            logger.info("onboarding_step_completed", step=step.value, next_step=next_step.value)

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
        """Skip an optional step (e.g., biometric enrollment).

        Only BIOMETRIC step is skippable.
        """
        _skippable = {OnboardingStep.BIOMETRIC}
        if step not in _skippable:
            msg = f"Step '{step.value}' is not skippable"
            raise ValueError(msg)
        if step != self._state.current_step:
            msg = f"Cannot skip step '{step.value}' - not the current step"
            raise ValueError(msg)

        next_step = self._next_step(step)
        self._state.current_step = next_step or OnboardingStep.COMPLETE
        self._save_state()
        logger.info("onboarding_step_skipped", step=step.value)
        return self.get_state()

    def get_progress(self) -> dict[str, Any]:
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

    def _apply_step_data(self, step: OnboardingStep, data: dict[str, Any]) -> None:
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
    def _next_step(step: OnboardingStep) -> OnboardingStep | None:
        """Return the next step after the given step, or None if last."""
        idx = _STEP_ORDER.index(step)
        if idx + 1 < len(_STEP_ORDER):
            return _STEP_ORDER[idx + 1]
        return None

    def _load_state(self) -> OnboardingState:
        if self._state_path.exists():
            try:
                raw = json.loads(self._state_path.read_text())
                state = OnboardingState(**raw)
            except Exception as exc:
                logger.exception("onboarding_state_load_error", error=str(exc))
                return OnboardingState()

            # Restore the LLM API key from the encrypted KeyStore. The
            # on-disk JSON never carries a real key (see _save_state()), so
            # a config loaded with api_key already None needs it filled
            # back in from where it actually lives. If the file predates
            # this fix, or the field was already populated some other way,
            # leave it untouched rather than clobbering a legitimate value.
            if state.llm_config is not None and state.llm_config.api_key is None:
                key_id = self._llm_api_key_id(state.llm_config.provider)
                try:
                    real_key = self._key_store.retrieve_key(key_id)
                except KeyNotFoundError:
                    # Expected for providers with no credential (e.g. a
                    # local ollama server) -- api_key legitimately stays None.
                    pass
                else:
                    state.llm_config.api_key = real_key.decode("utf-8")
            return state
        return OnboardingState()

    def _save_state(self) -> None:
        """Persist onboarding state to disk.

        BUG FIX (Round 13): this previously wrote
        self._state.model_dump_json() directly to the state file, which
        meant LLM_CONFIG.api_key -- a real OpenAI/Anthropic/Gemini/DeepSeek
        credential -- sat in plaintext JSON on disk indefinitely, readable
        by anything that could `cat` the file (any process running as the
        user, a backup tool, a support bundle, etc.), with zero encryption
        at rest. Fixed by extracting the real key into the same
        AES-256-GCM encrypted KeyStore the rest of the security system
        uses (keyed per-provider so switching providers doesn't clobber a
        previously stored one), and writing only a redacted copy (api_key
        blanked to None, which is already a valid value per LLMConfig) to
        the plaintext file. _load_state() transparently restores the real
        key into memory on the next load.

        This does not by itself make the key unreadable to a sufficiently
        privileged local attacker -- KeyStore's confidentiality depends on
        its master_password, and this codebase has no master-password
        sourcing mechanism anywhere yet (see the __init__ docstring note
        and SecurityConfig.master_password's own "" default in
        security/security_system.py). It does remove the most casual
        exposure path (a plain read of the state file no longer reveals
        the key), which is a genuine improvement over the prior behavior,
        not a claim of complete secrecy.
        """
        state_to_persist = self._state.model_copy(deep=True)

        if state_to_persist.llm_config is not None and state_to_persist.llm_config.api_key:
            key_id = self._llm_api_key_id(state_to_persist.llm_config.provider)
            self._key_store.store_key(
                key_id,
                state_to_persist.llm_config.api_key.encode("utf-8"),
            )
            state_to_persist.llm_config.api_key = None

        self._state_path.write_text(state_to_persist.model_dump_json(indent=2))

    @staticmethod
    def _llm_api_key_id(provider: str) -> str:
        """Return the KeyStore key_id under which a provider's API key lives."""
        return f"onboarding:llm_api_key:{provider}"
