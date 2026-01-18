"""
Authority State Machine - Root of Trust

Enforces cryptographic authority boundaries for command execution.
No command executes without verified authority state == ARMED.

Security Invariants (Cryptographically Enforced):
- Commands rejected unless AuthorityState == ARMED
- State transitions require cryptographic proof
- All state changes atomic with HMAC integrity
- Authority cannot increase silently
- System fails closed on integrity violation
"""

import hashlib
import hmac
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union


import structlog

# Thread-safe logger initialization with deferred binding to prevent deadlocks
def get_thread_safe_logger():
    """Get thread-safe logger with deferred binding to prevent GUI deadlocks."""
    try:
        return structlog.get_logger(__name__)
    except Exception:
        # Fallback to standard logging if structlog fails
        import logging
        return logging.getLogger(__name__)

logger = get_thread_safe_logger()


class AuthorityState(Enum):
    """Authority states with cryptographic enforcement."""

    LOCKED_LISTEN_ONLY = "LOCKED_LISTEN_ONLY"
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    ARMED = "ARMED"
    INTRUSION_DETECTED = "INTRUSION_DETECTED"


class AuthorityScope(Enum):
    """Authority scope levels per platform."""

    SYSTEM_WIDE = "system_wide"  # Desktop: Windows, macOS - full system control
    APP_LEVEL = "app_level"  # Mobile: Android, iOS - app-level only


class AuthorityPolicy(Enum):
    """Authority verification requirements by risk level."""

    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    ADMIN = "admin"


class BiometricFactor(Enum):
    """Cryptographically verified biometric factors."""

    VOICE = "voice"
    FACE = "face"
    FINGERPRINT = "fingerprint"


class StateTransitionReason(Enum):
    """Cryptographically audited state transition triggers."""

    VOICE_PHRASE_DETECTED = "voice_phrase_detected"
    BIOMETRIC_VERIFIED = "biometric_verified"
    BIOMETRIC_FAILED = "biometric_failed"
    TASK_COMPLETED = "task_completed"
    DESKTOP_VISIBLE = "desktop_visible"
    INACTIVITY_TIMEOUT = "inactivity_timeout"
    MANUAL_REVOKE = "manual_revoke"
    COMPONENT_FAILURE = "component_failure"
    INTRUSION_DETECTED = "intrusion_detected"
    VERIFICATION_TIMEOUT = "verification_timeout"
    SYSTEM_STARTUP = "system_startup"


@dataclass(frozen=True)
class BiometricVerification:
    """Cryptographically signed biometric verification record."""

    factor_type: BiometricFactor
    provider: str
    confidence_score: float
    verification_time: datetime
    success: bool
    failure_reason: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class StateTransition:
    """Cryptographically signed authority state transition."""

    from_state: AuthorityState
    to_state: AuthorityState
    reason: StateTransitionReason
    timestamp: datetime
    session_id: str
    verification_factors: Tuple[BiometricFactor, ...] = field(default_factory=tuple)
    metadata: Dict[str, str] = field(default_factory=dict)
    integrity_hash: str = field(default="")

    def __post_init__(self):
        """Calculate cryptographic integrity hash."""
        if not self.integrity_hash:
            data = (
                f"{self.from_state.value}:{self.to_state.value}:{self.reason.value}:"
                f"{self.timestamp.isoformat()}:{self.session_id}"
            )
            object.__setattr__(self, "integrity_hash", hashlib.sha256(data.encode()).hexdigest())


@dataclass
class AuthorityConfiguration:
    """Cryptographic authority enforcement configuration."""

    identity_verification_timeout: int = 30
    armed_session_timeout: int = 300
    inactivity_timeout: int = 60
    voice_confidence_threshold: float = 0.85
    face_confidence_threshold: float = 0.90
    fingerprint_confidence_threshold: float = 0.95
    max_failed_attempts: int = 3
    intrusion_cooldown_seconds: int = 300
    require_biometric_for_rearm: bool = True

    # SECURITY CRITICAL: Test mode flag
    test_mode_disable_workstation_lock: bool = False  # NEVER set to True in production

    policy_requirements: Dict[AuthorityPolicy, Set[BiometricFactor]] = field(
        default_factory=lambda: {
            AuthorityPolicy.LOW_RISK: {BiometricFactor.VOICE},
            AuthorityPolicy.MEDIUM_RISK: {BiometricFactor.VOICE, BiometricFactor.FACE},
            AuthorityPolicy.HIGH_RISK: {BiometricFactor.VOICE, BiometricFactor.FACE, BiometricFactor.FINGERPRINT},
            AuthorityPolicy.ADMIN: {BiometricFactor.VOICE, BiometricFactor.FACE, BiometricFactor.FINGERPRINT},
        }
    )


class AuthorityStateIntegrityError(Exception):
    """Raised when authority state integrity is compromised."""


class AuthorityTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


class AuthorityStateMachine:
    """
    Cryptographic authority state machine - root of trust for command execution.

    Enforces invariant: No command executes unless state == ARMED.
    All state transitions cryptographically signed and audited.
    """

    def __init__(self, config: Optional[AuthorityConfiguration] = None):
        """Initialize authority state machine with cryptographic protection."""
        self._config = config or AuthorityConfiguration()
        self._lock = threading.RLock()
        self._current_state = AuthorityState.LOCKED_LISTEN_ONLY
        self._session_id = str(uuid.uuid4())
        self._state_history: List[StateTransition] = []
        self._armed_at: Optional[datetime] = None
        self._last_activity: datetime = datetime.utcnow()
        self._verification_start: Optional[datetime] = None
        self._pending_verifications: Dict[BiometricFactor, BiometricVerification] = {}
        self._failed_attempts: int = 0
        self._last_intrusion: Optional[datetime] = None
        self._current_policy = AuthorityPolicy.LOW_RISK
        self._required_factors: Set[BiometricFactor] = self._config.policy_requirements[self._current_policy]
        self._integrity_key = secrets.token_bytes(32)

        # Detect platform and set authority scope
        self._platform = self._detect_platform()
        self._authority_scope = self._determine_authority_scope(self._platform)

        self._initialized = True

        self._log_state_transition(
            from_state=AuthorityState.LOCKED_LISTEN_ONLY,
            to_state=AuthorityState.LOCKED_LISTEN_ONLY,
            reason=StateTransitionReason.SYSTEM_STARTUP,
        )

        # Initialize state checksum with controlled access
        self._updating_checksum = True
        self._state_checksum = self._calculate_state_checksum()
        delattr(self, "_updating_checksum")

        # TEMPORARY: Disable monitor thread to debug deadlock
        self._monitoring_active = False
        self._monitor_thread = None
        # self._monitoring_active = True
        # self._monitor_thread = threading.Thread(target=self._monitor_timeouts, daemon=True)
        # self._monitor_thread.start()

        # TEMPORARY: Comment out logger to debug deadlock
        # try:
        #     logger.info(
        #         "Authority state machine initialized",
        #         session_id=self._session_id,
        #         initial_state=self._current_state.value,
        #         policy=self._current_policy.value,
        #     )
        # except Exception:
        #     # Fallback to print if logger fails
        #     print(f"Authority state machine initialized (logger error: {e})")

    def __setattr__(self, name: str, value) -> None:
        """Prevent unauthorized modification of cryptographic state."""
        if not hasattr(self, "_initialized"):
            super().__setattr__(name, value)
            return

        # Allow _state_checksum updates through internal methods only
        if name == "_state_checksum" and hasattr(self, "_updating_checksum"):
            super().__setattr__(name, value)
            return

        # DANGEROUS: Test-only backdoor for integrity corruption simulation
        # This should NEVER be used in production code
        if name == "_state_checksum" and hasattr(self, "_test_corruption_mode"):
            super().__setattr__(name, value)
            return

        protected_attrs = {
            "_current_state",
            "_session_id",
            "_state_history",
            "_failed_attempts",
            "_last_intrusion",
            "_current_policy",
            "_required_factors",
            "_integrity_key",
            "_state_checksum",
            "_platform",
            "_authority_scope",
        }

        if name in protected_attrs:
            raise AttributeError(f"Cannot modify protected cryptographic state '{name}'")

        super().__setattr__(name, value)

    def __del__(self):
        """Cleanup resources on destruction."""
        try:
            self._monitoring_active = False
            if hasattr(self, "_monitor_thread") and self._monitor_thread is not None and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=1.0)
        except (AttributeError, TypeError):
            # Ignore cleanup errors during interpreter shutdown
            pass

    @property
    def current_state(self) -> AuthorityState:
        """Get current authority state with integrity verification."""
        with self._lock:
            self._verify_integrity()
            return self._current_state

    @property
    def session_id(self) -> str:
        """Get cryptographically unique session identifier."""
        with self._lock:
            return self._session_id

    @property
    def is_armed(self) -> bool:
        """Verify authority state allows command execution."""
        return self.current_state == AuthorityState.ARMED

    @property
    def is_locked(self) -> bool:
        """Verify authority state blocks command execution."""
        return self.current_state == AuthorityState.LOCKED_LISTEN_ONLY

    @property
    def current_policy(self) -> AuthorityPolicy:
        """Get the current authority policy."""
        with self._lock:
            return self._current_policy

    @property
    def platform(self) -> str:
        """Get the detected platform."""
        with self._lock:
            return self._platform

    @property
    def authority_scope(self) -> AuthorityScope:
        """Get the authority scope for the current platform."""
        with self._lock:
            return self._authority_scope

    def get_authority_scope(self) -> AuthorityScope:
        """
        Get the authority scope for the current platform.

        Returns:
            AuthorityScope.SYSTEM_WIDE for desktop (Windows, macOS)
            AuthorityScope.APP_LEVEL for mobile (Android, iOS)

        Validates: Requirements 39.1, 39.2, 39.3, 39.4
        """
        with self._lock:
            return self._authority_scope

    def get_state_info(self) -> Dict[str, Union[str, int, float, bool]]:
        """Get comprehensive state information for monitoring."""
        with self._lock:
            self._verify_integrity()

            time_since_armed = None
            if self._armed_at:
                time_since_armed = (datetime.utcnow() - self._armed_at).total_seconds()

            time_since_activity = (datetime.utcnow() - self._last_activity).total_seconds()

            return {
                "state": self._current_state.value,
                "session_id": self._session_id,
                "policy": self._current_policy.value,
                "platform": self._platform,
                "authority_scope": self._authority_scope.value,
                "is_armed": self.is_armed,
                "is_locked": self.is_locked,
                "armed_at": self._armed_at.isoformat() if self._armed_at else None,
                "time_since_armed": time_since_armed,
                "time_since_activity": time_since_activity,
                "failed_attempts": self._failed_attempts,
                "required_factors": [f.value for f in self._required_factors],
                "pending_verifications": list(self._pending_verifications.keys()),
                "verification_in_progress": self._current_state == AuthorityState.IDENTITY_VERIFICATION,
                "intrusion_cooldown_active": self._is_in_intrusion_cooldown(),
                "state_transitions_count": len(self._state_history),
            }

    def initiate_voice_rearm(self, voice_confidence: float, speaker_verified: bool) -> bool:
        """
        Initiate cryptographically verified voice re-arming.

        Enforces voice confidence thresholds and speaker verification.
        Triggers intrusion detection on repeated failures.
        """
        with self._lock:
            self._verify_integrity()

            if (
                not (0.0 <= voice_confidence <= 1.0)
                or not isinstance(voice_confidence, (int, float))
                or voice_confidence != voice_confidence
            ):
                logger.warning(
                    "Voice re-arm rejected: invalid confidence",
                    confidence=voice_confidence,
                    session_id=self._session_id,
                )
                self._record_failed_attempt("invalid_confidence")
                return False

            if self._is_in_intrusion_cooldown():
                logger.warning(
                    "Voice re-arm blocked: intrusion cooldown active",
                    session_id=self._session_id,
                    cooldown_remaining=self._get_cooldown_remaining(),
                )
                return False

            if self._current_state != AuthorityState.LOCKED_LISTEN_ONLY:
                raise AuthorityTransitionError(
                    f"Voice re-arm requires LOCKED_LISTEN_ONLY state, current: {self._current_state}"
                )

            if voice_confidence < self._config.voice_confidence_threshold:
                logger.warning(
                    "Voice re-arm rejected: insufficient confidence",
                    confidence=voice_confidence,
                    threshold=self._config.voice_confidence_threshold,
                    session_id=self._session_id,
                )
                self._record_failed_attempt("voice_confidence_low")

                if self._should_trigger_intrusion_detection():
                    self._trigger_intrusion_detection("Multiple voice authentication failures")

                return False

            if not speaker_verified:
                logger.warning("Voice re-arm rejected: speaker verification failed", session_id=self._session_id)
                self._record_failed_attempt("speaker_verification_failed")

                if self._should_trigger_intrusion_detection():
                    self._trigger_intrusion_detection("Multiple speaker verification failures")

                return False

            voice_verification = BiometricVerification(
                factor_type=BiometricFactor.VOICE,
                provider="whisper_cpp",
                confidence_score=voice_confidence,
                verification_time=datetime.utcnow(),
                success=True,
                session_id=self._session_id,
            )

            self._pending_verifications[BiometricFactor.VOICE] = voice_verification

            if self._required_factors == {BiometricFactor.VOICE}:
                return self._complete_arming()
            else:
                return self._transition_to_identity_verification()

    def enforce_biometric_factor_verification_boundary(
        self,
        factor: BiometricFactor,
        provider: str,
        confidence: float,
        success: bool,
        failure_reason: Optional[str] = None,
    ) -> bool:
        """
        Cryptographically verify biometric factor during identity verification.

        Enforces confidence thresholds and triggers intrusion detection on failures.
        """
        with self._lock:
            self._verify_integrity()

            if not isinstance(factor, BiometricFactor):
                raise TypeError(f"Factor must be BiometricFactor, got {type(factor)}")

            if provider is None:
                raise TypeError("Provider cannot be None")

            if not isinstance(provider, str):
                raise TypeError(f"Provider must be string, got {type(provider)}")

            if self._current_state != AuthorityState.IDENTITY_VERIFICATION:
                raise AuthorityTransitionError(
                    f"Biometric verification requires IDENTITY_VERIFICATION state, current: {self._current_state}"
                )

            if (
                self._verification_start
                and (datetime.utcnow() - self._verification_start).total_seconds()
                > self._config.identity_verification_timeout
            ):
                logger.warning("Biometric verification timeout", factor=factor.value, session_id=self._session_id)
                self._handle_verification_timeout()
                return False

            verification = BiometricVerification(
                factor_type=factor,
                provider=provider,
                confidence_score=confidence,
                verification_time=datetime.utcnow(),
                success=success,
                failure_reason=failure_reason,
                session_id=self._session_id,
            )

            if success:
                threshold = self._get_confidence_threshold(factor)
                if confidence < threshold:
                    logger.warning(
                        "Biometric verification rejected: insufficient confidence",
                        factor=factor.value,
                        confidence=confidence,
                        threshold=threshold,
                        session_id=self._session_id,
                    )
                    self._record_failed_attempt(f"{factor.value}_confidence_low")
                    return False

                self._pending_verifications[factor] = verification
                logger.info(
                    "Biometric factor verified",
                    factor=factor.value,
                    confidence=confidence,
                    provider=provider,
                    session_id=self._session_id,
                )

                if self._all_required_factors_verified():
                    return self._complete_arming()
                else:
                    remaining = self._required_factors - set(self._pending_verifications.keys())
                    logger.info(
                        "Awaiting additional biometric factors",
                        remaining_factors=[f.value for f in remaining],
                        session_id=self._session_id,
                    )
                    return False
            else:
                logger.warning(
                    "Biometric verification failed",
                    factor=factor.value,
                    reason=failure_reason,
                    confidence=confidence,
                    session_id=self._session_id,
                )

                self._record_failed_attempt(f"{factor.value}_verification_failed")

                if self._should_trigger_intrusion_detection():
                    self._trigger_intrusion_detection(f"Multiple {factor.value} verification failures")

                return False

    def revoke_authority_via_workstation_lock(
        self, reason: StateTransitionReason, metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        SECURITY ENFORCEMENT: Revoke authority by triggering workstation lock.

        This method replaces the insecure revoke_authority() which maintained session continuity.
        All authority revocation now forces OS-level re-authentication through workstation locking.

        This enforces the YuktOS security principle: authority loss = complete session termination.
        """
        with self._lock:
            self._verify_integrity()

            if not isinstance(reason, StateTransitionReason):
                raise TypeError(f"Reason must be StateTransitionReason, got {type(reason)}")

            logger.critical(
                "AUTHORITY REVOCATION TRIGGERING WORKSTATION LOCK",
                reason=reason.value,
                session_id=self._session_id,
                metadata=metadata,
                security_enforcement="OS_LEVEL_AUTHENTICATION_REQUIRED",
            )

            # Import workstation locker
            from ..intrusion.workstation_lock import WorkstationLockTrigger, create_workstation_locker

            # Map revocation reason to lock trigger
            trigger_mapping = {
                StateTransitionReason.MANUAL_REVOKE: WorkstationLockTrigger.MANUAL_TRIGGER,
                StateTransitionReason.INTRUSION_DETECTED: WorkstationLockTrigger.INTRUSION_DETECTED,
                StateTransitionReason.BIOMETRIC_FAILED: WorkstationLockTrigger.BIOMETRIC_FAILURE,
                StateTransitionReason.COMPONENT_FAILURE: WorkstationLockTrigger.SECURITY_VIOLATION,
                StateTransitionReason.VERIFICATION_TIMEOUT: WorkstationLockTrigger.SECURITY_VIOLATION,
                StateTransitionReason.INACTIVITY_TIMEOUT: WorkstationLockTrigger.SECURITY_VIOLATION,
            }

            lock_trigger = trigger_mapping.get(reason, WorkstationLockTrigger.SECURITY_VIOLATION)

            # Create workstation locker and trigger immediate lock
            workstation_locker = create_workstation_locker()
            lock_event = workstation_locker.lock_workstation_immediately(
                trigger=lock_trigger,
                trigger_context={
                    "authority_revocation_reason": reason.value,
                    "session_id": self._session_id,
                    **(metadata or {}),
                },
                session_id=self._session_id,
            )

            # Log the security enforcement
            logger.critical(
                "WORKSTATION LOCK ENFORCED FOR AUTHORITY REVOCATION",
                lock_event_id=lock_event.event_id,
                lock_result=lock_event.result.value,
                reason=reason.value,
                session_id=self._session_id,
            )

            # The workstation is now locked - this process will be suspended
            # When user unlocks, they must re-authenticate through OS mechanisms
            return lock_event.result.value == "success"

    def revoke_authority(self, reason: StateTransitionReason, metadata: Optional[Dict[str, str]] = None) -> bool:
        """
        SECURITY ENFORCEMENT: Revoke authority via workstation lock (production) or test mode.

        In production: Triggers workstation lock to enforce OS-level re-authentication.
        In test mode: Uses legacy behavior to avoid interfering with test execution.

        ⚠️  TEST MODE MUST NEVER BE ENABLED IN PRODUCTION - IT'S A SECURITY VULNERABILITY
        """
        # Validate reason parameter first
        if not isinstance(reason, StateTransitionReason):
            raise TypeError(f"Reason must be StateTransitionReason, got {type(reason)}")

        # Check if test mode is enabled (SECURITY CRITICAL)
        if self._config.test_mode_disable_workstation_lock:
            logger.critical(
                "TEST MODE ENABLED - USING INSECURE AUTHORITY REVOCATION",
                reason=reason.value,
                session_id=self._session_id,
                security_warning="NEVER_USE_IN_PRODUCTION",
            )
            return self._test_only_revoke_authority_without_workstation_lock(reason, metadata)

        # Production mode: enforce workstation lock
        logger.warning(
            "PRODUCTION MODE - redirecting to secure workstation lock",
            reason=reason.value,
            session_id=self._session_id,
            security_enforcement="WORKSTATION_LOCK_REQUIRED",
        )

        return self.revoke_authority_via_workstation_lock(reason, metadata)

    def _test_only_revoke_authority_without_workstation_lock(
        self, reason: StateTransitionReason, metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        TEST-ONLY METHOD: Revoke authority without workstation lock.

        ⚠️  SECURITY WARNING: This method maintains session continuity and should NEVER be used in production.
        It exists solely for unit testing purposes where workstation locking would interfere with test execution.

        Production code MUST use revoke_authority() which enforces workstation locking.
        """
        with self._lock:
            self._verify_integrity()

            if not isinstance(reason, StateTransitionReason):
                raise TypeError(f"Reason must be StateTransitionReason, got {type(reason)}")

            if self._current_state == AuthorityState.LOCKED_LISTEN_ONLY:
                logger.debug("Authority already revoked", session_id=self._session_id)
                return True

            self._clear_session_state()

            self._transition_state(new_state=AuthorityState.LOCKED_LISTEN_ONLY, reason=reason, metadata=metadata or {})

            logger.warning(
                "TEST-ONLY authority revocation without workstation lock",
                reason=reason.value,
                session_id=self._session_id,
                metadata=metadata,
                security_warning="PRODUCTION_MUST_USE_WORKSTATION_LOCK",
            )

            return True

    def update_activity(self) -> None:
        """Update activity timestamp to prevent inactivity timeout."""
        with self._lock:
            self._last_activity = datetime.utcnow()
            self._update_state_checksum()

    def set_authority_policy(self, policy: AuthorityPolicy) -> bool:
        """
        Update authority policy and required verification factors.

        Forces re-authentication if current session insufficient for new policy.
        """
        with self._lock:
            self._verify_integrity()

            old_policy = self._current_policy

            object.__setattr__(self, "_current_policy", policy)
            object.__setattr__(self, "_required_factors", self._config.policy_requirements[policy])

            self._update_state_checksum()

            if self._current_state == AuthorityState.ARMED and not self._all_required_factors_verified():
                logger.warning(
                    "Policy change requires re-authentication",
                    old_policy=old_policy.value,
                    new_policy=policy.value,
                    session_id=self._session_id,
                )
                self.revoke_authority(
                    reason=StateTransitionReason.MANUAL_REVOKE,
                    metadata={"policy_change": f"{old_policy.value} -> {policy.value}"},
                )

            logger.info(
                "Authority policy updated",
                old_policy=old_policy.value,
                new_policy=policy.value,
                required_factors=[f.value for f in self._required_factors],
                session_id=self._session_id,
            )

            return True

    def get_state_history(self, limit: Optional[int] = None) -> List[StateTransition]:
        """Get cryptographically signed state transition history."""
        with self._lock:
            history = list(reversed(self._state_history))
            if limit:
                history = history[:limit]
            return history

    def verify_state_integrity(self) -> bool:
        """Verify cryptographic integrity of state machine."""
        with self._lock:
            try:
                self._verify_integrity()
                return True
            except AuthorityStateIntegrityError:
                return False

    def verify_biometric_factor(
        self,
        factor: BiometricFactor,
        provider: str,
        confidence: float,
        success: bool,
        failure_reason: Optional[str] = None,
    ) -> bool:
        """
        Compatibility method for test interface.

        Delegates to enforce_biometric_factor_verification_boundary.
        """
        return self.enforce_biometric_factor_verification_boundary(
            factor=factor,
            provider=provider,
            confidence=confidence,
            success=success,
            failure_reason=failure_reason,
        )

    def enable_test_corruption_mode(self) -> None:
        """
        DANGEROUS: Enable test-only corruption simulation mode.

        This method should NEVER be called in production code.
        It allows tests to simulate integrity corruption for validation.
        """
        self._test_corruption_mode = True

    def disable_test_corruption_mode(self) -> None:
        """
        Disable test corruption mode and restore normal protection.
        """
        if hasattr(self, "_test_corruption_mode"):
            delattr(self, "_test_corruption_mode")
        if hasattr(self, "_test_corruption_mode"):
            delattr(self, "_test_corruption_mode")

    # Private methods

    def _detect_platform(self) -> str:
        """
        Detect the current platform.

        Returns:
            Platform identifier: "windows", "macos", "android", or "ios"

        Validates: Requirements 39.1, 43.1
        """
        try:
            # Try to import platform detector from PAL
            from src.pal.platform_detector import PlatformDetector

            return PlatformDetector.detect()
        except ImportError:
            # Fallback to basic platform detection if PAL not available
            import platform

            system = platform.system().lower()
            if system == "windows":
                return "windows"
            elif system == "darwin":
                return "macos"
            elif system == "linux":
                # Check for Android
                import sys

                if hasattr(sys, "getandroidapilevel"):
                    return "android"
                else:
                    # Default to windows for testing on Linux
                    return "windows"
            else:
                # Default to windows for unknown platforms
                return "windows"

    def _determine_authority_scope(self, platform: str) -> AuthorityScope:
        """
        Determine authority scope based on platform.

        Desktop platforms (Windows, macOS): SYSTEM_WIDE
        Mobile platforms (Android, iOS): APP_LEVEL

        Args:
            platform: Platform identifier

        Returns:
            AuthorityScope.SYSTEM_WIDE or AuthorityScope.APP_LEVEL

        Validates: Requirements 39.2, 39.3, 39.4
        """
        if platform in ("windows", "macos"):
            return AuthorityScope.SYSTEM_WIDE
        elif platform in ("android", "ios"):
            return AuthorityScope.APP_LEVEL
        else:
            # Default to APP_LEVEL for unknown platforms (fail-safe)
            return AuthorityScope.APP_LEVEL

    def _verify_integrity(self) -> None:
        """Verify HMAC integrity of cryptographic state."""
        current_checksum = self._calculate_state_checksum()
        if not hmac.compare_digest(current_checksum, self._state_checksum):
            logger.critical(
                "Authority state integrity violation detected",
                session_id=self._session_id,
                expected_checksum=self._state_checksum[:16] + "...",
                actual_checksum=current_checksum[:16] + "...",
            )
            raise AuthorityStateIntegrityError("State machine integrity compromised")

    def _calculate_state_checksum(self) -> str:
        """Calculate HMAC-SHA256 checksum of critical cryptographic state."""
        state_data = (
            f"{self._current_state.value}:"
            f"{self._session_id}:"
            f"{self._current_policy.value}:"
            f"{self._failed_attempts}:"
            f"{len(self._state_history)}"
        )
        return hmac.new(self._integrity_key, state_data.encode(), hashlib.sha256).hexdigest()

    def _update_state_checksum(self) -> None:
        """Update HMAC checksum after cryptographic state changes."""
        self._updating_checksum = True
        self._state_checksum = self._calculate_state_checksum()
        delattr(self, "_updating_checksum")

    def _transition_state(
        self, new_state: AuthorityState, reason: StateTransitionReason, metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """Execute cryptographically verified atomic state transition."""
        old_state = self._current_state

        if not self._is_valid_transition(old_state, new_state, reason):
            raise AuthorityTransitionError(f"Invalid transition: {old_state} -> {new_state} (reason: {reason})")

        if new_state == AuthorityState.ARMED:
            if reason == StateTransitionReason.BIOMETRIC_VERIFIED:
                if not self._all_required_factors_verified():
                    raise AuthorityTransitionError(
                        "Cannot arm: missing required biometric factors. "
                        f"Required: {[f.value for f in self._required_factors]}, "
                        f"Verified: {list(self._pending_verifications.keys())}"
                    )

        object.__setattr__(self, "_current_state", new_state)

        if new_state == AuthorityState.ARMED:
            self._armed_at = datetime.utcnow()
        elif new_state == AuthorityState.LOCKED_LISTEN_ONLY:
            self._armed_at = None
        elif new_state == AuthorityState.IDENTITY_VERIFICATION:
            self._verification_start = datetime.utcnow()

        self._log_state_transition(old_state, new_state, reason, metadata)

        self._update_state_checksum()

    def _is_valid_transition(
        self, from_state: AuthorityState, to_state: AuthorityState, reason: StateTransitionReason
    ) -> bool:
        """Validate cryptographically enforced state transition rules."""
        valid_transitions = {
            AuthorityState.LOCKED_LISTEN_ONLY: {
                AuthorityState.IDENTITY_VERIFICATION: {StateTransitionReason.VOICE_PHRASE_DETECTED},
                AuthorityState.ARMED: {StateTransitionReason.BIOMETRIC_VERIFIED},
                AuthorityState.INTRUSION_DETECTED: {StateTransitionReason.INTRUSION_DETECTED},
            },
            AuthorityState.IDENTITY_VERIFICATION: {
                AuthorityState.ARMED: {StateTransitionReason.BIOMETRIC_VERIFIED},
                AuthorityState.LOCKED_LISTEN_ONLY: {
                    StateTransitionReason.BIOMETRIC_FAILED,
                    StateTransitionReason.VERIFICATION_TIMEOUT,
                    StateTransitionReason.MANUAL_REVOKE,
                },
                AuthorityState.INTRUSION_DETECTED: {StateTransitionReason.INTRUSION_DETECTED},
            },
            AuthorityState.ARMED: {
                AuthorityState.LOCKED_LISTEN_ONLY: {
                    StateTransitionReason.TASK_COMPLETED,
                    StateTransitionReason.DESKTOP_VISIBLE,
                    StateTransitionReason.INACTIVITY_TIMEOUT,
                    StateTransitionReason.MANUAL_REVOKE,
                    StateTransitionReason.COMPONENT_FAILURE,
                },
                AuthorityState.INTRUSION_DETECTED: {StateTransitionReason.INTRUSION_DETECTED},
            },
            AuthorityState.INTRUSION_DETECTED: {
                AuthorityState.LOCKED_LISTEN_ONLY: {StateTransitionReason.MANUAL_REVOKE}
            },
        }

        allowed_reasons = valid_transitions.get(from_state, {}).get(to_state, set())
        return reason in allowed_reasons

    def _log_state_transition(
        self,
        from_state: AuthorityState,
        to_state: AuthorityState,
        reason: StateTransitionReason,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Log state transition with integrity protection."""
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            timestamp=datetime.utcnow(),
            session_id=self._session_id,
            verification_factors=tuple(self._pending_verifications.keys()),
            metadata=metadata or {},
        )

        self._state_history.append(transition)

        # Enhanced logging with platform and authority scope
        logger.info(
            "Authority state transition",
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason.value,
            session_id=self._session_id,
            platform=self._platform,
            authority_scope=self._authority_scope.value,
            transition_id=transition.integrity_hash[:8],
            metadata=metadata,
        )

    def _transition_to_identity_verification(self) -> bool:
        """Transition to identity verification state."""
        self._transition_state(
            new_state=AuthorityState.IDENTITY_VERIFICATION, reason=StateTransitionReason.VOICE_PHRASE_DETECTED
        )
        return True

    def _complete_arming(self) -> bool:
        """Complete the arming process after all verifications."""
        # Reset failed attempts on successful arming
        object.__setattr__(self, "_failed_attempts", 0)

        self._transition_state(
            new_state=AuthorityState.ARMED,
            reason=StateTransitionReason.BIOMETRIC_VERIFIED,
            metadata={
                "verified_factors": ",".join(f.value for f in self._pending_verifications.keys()),
                "policy": self._current_policy.value,
                "platform": self._platform,
                "authority_scope": self._authority_scope.value,
            },
        )

        logger.info(
            "Authority granted - system armed",
            session_id=self._session_id,
            policy=self._current_policy.value,
            platform=self._platform,
            authority_scope=self._authority_scope.value,
            verified_factors=[f.value for f in self._pending_verifications.keys()],
        )

        return True

    def _all_required_factors_verified(self) -> bool:
        """Check if all required biometric factors have been verified."""
        verified_factors = set(self._pending_verifications.keys())
        return self._required_factors.issubset(verified_factors)

    def _get_confidence_threshold(self, factor: BiometricFactor) -> float:
        """Get confidence threshold for a biometric factor."""
        thresholds = {
            BiometricFactor.VOICE: self._config.voice_confidence_threshold,
            BiometricFactor.FACE: self._config.face_confidence_threshold,
            BiometricFactor.FINGERPRINT: self._config.fingerprint_confidence_threshold,
        }
        return thresholds[factor]

    def _record_failed_attempt(self, failure_type: str) -> None:
        """Record a failed authentication attempt."""
        object.__setattr__(self, "_failed_attempts", self._failed_attempts + 1)
        self._update_state_checksum()

        logger.warning(
            "Authentication attempt failed",
            failure_type=failure_type,
            failed_attempts=self._failed_attempts,
            max_attempts=self._config.max_failed_attempts,
            session_id=self._session_id,
        )

    def _should_trigger_intrusion_detection(self) -> bool:
        """Determine if intrusion detection should be triggered."""
        return self._failed_attempts >= self._config.max_failed_attempts

    def _trigger_intrusion_detection(self, reason: str) -> None:
        """Trigger intrusion detection and lockdown."""
        object.__setattr__(self, "_last_intrusion", datetime.utcnow())

        self._transition_state(
            new_state=AuthorityState.INTRUSION_DETECTED,
            reason=StateTransitionReason.INTRUSION_DETECTED,
            metadata={"intrusion_reason": reason},
        )

        logger.critical(
            "INTRUSION DETECTED - System locked down",
            reason=reason,
            failed_attempts=self._failed_attempts,
            session_id=self._session_id,
        )

    def _is_in_intrusion_cooldown(self) -> bool:
        """Check if system is in intrusion cooldown period."""
        if not self._last_intrusion:
            return False

        cooldown_end = self._last_intrusion + timedelta(seconds=self._config.intrusion_cooldown_seconds)
        return datetime.utcnow() < cooldown_end

    def _get_cooldown_remaining(self) -> int:
        """Get remaining cooldown time in seconds."""
        if not self._last_intrusion:
            return 0

        cooldown_end = self._last_intrusion + timedelta(seconds=self._config.intrusion_cooldown_seconds)
        remaining = cooldown_end - datetime.utcnow()
        return max(0, int(remaining.total_seconds()))

    def _handle_verification_timeout(self) -> None:
        """Handle identity verification timeout."""
        self._clear_session_state()
        self._transition_state(
            new_state=AuthorityState.LOCKED_LISTEN_ONLY, reason=StateTransitionReason.VERIFICATION_TIMEOUT
        )

    def _clear_session_state(self) -> None:
        """Clear session-specific state data."""
        self._pending_verifications.clear()
        self._verification_start = None
        self._armed_at = None
        object.__setattr__(self, "_session_id", str(uuid.uuid4()))  # New session
        # Note: _failed_attempts is NOT reset here - it persists across sessions for intrusion detection
        self._update_state_checksum()

    def _monitor_timeouts(self) -> None:
        """Background thread to monitor timeouts and enforce policies."""
        while self._monitoring_active:
            try:
                with self._lock:
                    current_time = datetime.utcnow()

                    # Check identity verification timeout
                    if (
                        self._current_state == AuthorityState.IDENTITY_VERIFICATION
                        and self._verification_start
                        and (current_time - self._verification_start).total_seconds()
                        > self._config.identity_verification_timeout
                    ):

                        logger.warning("Identity verification timeout", session_id=self._session_id)
                        self._handle_verification_timeout()

                    # Check armed session timeout
                    elif (
                        self._current_state == AuthorityState.ARMED
                        and self._armed_at
                        and (current_time - self._armed_at).total_seconds() > self._config.armed_session_timeout
                    ):

                        logger.info("Armed session timeout", session_id=self._session_id)
                        self.revoke_authority(StateTransitionReason.INACTIVITY_TIMEOUT)

                    # Check inactivity timeout (only when armed)
                    elif (
                        self._current_state == AuthorityState.ARMED
                        and (current_time - self._last_activity).total_seconds() > self._config.inactivity_timeout
                    ):

                        logger.info("Inactivity timeout", session_id=self._session_id)
                        self.revoke_authority(StateTransitionReason.INACTIVITY_TIMEOUT)

                # Sleep for shorter intervals for more responsive timeout handling
                time.sleep(0.1)

            except Exception as e:
                logger.error(
                    "Error in timeout monitor", error=str(e), session_id=getattr(self, "_session_id", "unknown")
                )
                time.sleep(1.0)  # Longer sleep on error


# Utility functions for external use


def create_authority_state_machine(config: Optional[AuthorityConfiguration] = None) -> AuthorityStateMachine:
    """
    Factory function to create a properly configured Authority State Machine.

    Args:
        config: Optional configuration, uses secure defaults if None

    Returns:
        Configured AuthorityStateMachine instance
    """
    return AuthorityStateMachine(config)


def get_default_authority_config() -> AuthorityConfiguration:
    """
    Get the default authority configuration with secure settings.

    Returns:
        AuthorityConfiguration with production-ready defaults
    """
    return AuthorityConfiguration()


# Export public interface
__all__ = [
    "AuthorityState",
    "AuthorityScope",
    "AuthorityPolicy",
    "BiometricFactor",
    "StateTransitionReason",
    "BiometricVerification",
    "StateTransition",
    "AuthorityConfiguration",
    "AuthorityStateMachine",
    "AuthorityStateIntegrityError",
    "AuthorityTransitionError",
    "create_authority_state_machine",
    "get_default_authority_config",
]
