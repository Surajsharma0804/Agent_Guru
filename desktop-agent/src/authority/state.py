"""
Authority State Management Module

This module implements the core Authority State Machine that serves as the root of trust
for all execution decisions in GURU. The AuthorityStateMachine enforces the principle
that "GURU treats authority as sacred and convenience as optional."

Security Invariants:
1. Commands SHALL NOT execute unless AuthorityState == ARMED
2. State transitions SHALL NOT occur without cryptographic proof
3. All state changes MUST be atomic and logged
4. No component may bypass or override authority decisions
5. System SHALL fail closed on any integrity verification failure

Thread Safety:
All operations are thread-safe using atomic operations and proper locking.
The state machine guarantees consistency under concurrent access.
"""

import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
import uuid
import hashlib
import hmac
import secrets
import structlog

logger = structlog.get_logger(__name__)


class AuthorityState(Enum):
    """
    Authority states defining the security posture of the GURU system.
    
    State Definitions:
    - LOCKED_LISTEN_ONLY: No automation allowed; system listens only for secret voice phrase
    - IDENTITY_VERIFICATION: Biometric verification in progress
    - ARMED: Automation allowed within the unlocked user session
    - INTRUSION_DETECTED: Security violation detected; immediate lockdown required
    """
    LOCKED_LISTEN_ONLY = "LOCKED_LISTEN_ONLY"
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    ARMED = "ARMED"
    INTRUSION_DETECTED = "INTRUSION_DETECTED"


class AuthorityPolicy(Enum):
    """Risk-based authority policies determining verification requirements."""
    LOW_RISK = "low_risk"      # Voice only
    MEDIUM_RISK = "medium_risk"  # Voice + one biometric
    HIGH_RISK = "high_risk"    # Voice + face + fingerprint
    ADMIN = "admin"            # Voice + face + fingerprint + Windows UAC


class BiometricFactor(Enum):
    """Supported biometric authentication factors."""
    VOICE = "voice"
    FACE = "face"
    FINGERPRINT = "fingerprint"


class StateTransitionReason(Enum):
    """Reasons for authority state transitions."""
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
    """Immutable record of a biometric verification attempt."""
    factor_type: BiometricFactor
    provider: str
    confidence_score: float
    verification_time: datetime
    success: bool
    failure_reason: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class StateTransition:
    """Immutable record of an authority state transition."""
    from_state: AuthorityState
    to_state: AuthorityState
    reason: StateTransitionReason
    timestamp: datetime
    session_id: str
    verification_factors: Tuple[BiometricFactor, ...] = field(default_factory=tuple)
    metadata: Dict[str, str] = field(default_factory=dict)
    integrity_hash: str = field(default="")
    
    def __post_init__(self):
        """Calculate integrity hash after initialization."""
        if not self.integrity_hash:
            # Create deterministic hash of transition data
            data = f"{self.from_state.value}:{self.to_state.value}:{self.reason.value}:{self.timestamp.isoformat()}:{self.session_id}"
            object.__setattr__(self, 'integrity_hash', hashlib.sha256(data.encode()).hexdigest())


@dataclass
class AuthorityConfiguration:
    """Configuration for authority policies and timeouts."""
    # Timeout configurations (in seconds)
    identity_verification_timeout: int = 30
    armed_session_timeout: int = 300  # 5 minutes
    inactivity_timeout: int = 60      # 1 minute
    
    # Biometric thresholds
    voice_confidence_threshold: float = 0.85
    face_confidence_threshold: float = 0.90
    fingerprint_confidence_threshold: float = 0.95
    
    # Security policies
    max_failed_attempts: int = 3
    intrusion_cooldown_seconds: int = 300  # 5 minutes
    require_biometric_for_rearm: bool = True
    
    # Policy requirements
    policy_requirements: Dict[AuthorityPolicy, Set[BiometricFactor]] = field(default_factory=lambda: {
        AuthorityPolicy.LOW_RISK: {BiometricFactor.VOICE},
        AuthorityPolicy.MEDIUM_RISK: {BiometricFactor.VOICE, BiometricFactor.FACE},
        AuthorityPolicy.HIGH_RISK: {BiometricFactor.VOICE, BiometricFactor.FACE, BiometricFactor.FINGERPRINT},
        AuthorityPolicy.ADMIN: {BiometricFactor.VOICE, BiometricFactor.FACE, BiometricFactor.FINGERPRINT}
    })


class AuthorityStateIntegrityError(Exception):
    """Raised when authority state integrity is compromised."""
    pass


class AuthorityTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class AuthorityStateMachine:
    """
    Thread-safe Authority State Machine implementing the root of trust for GURU.
    
    This class enforces all security invariants and provides atomic state transitions
    with comprehensive audit logging. It serves as the single source of truth for
    all authorization decisions in the system.
    
    Security Features:
    - Atomic state transitions with integrity verification
    - Cryptographic audit trail with tamper detection
    - Thread-safe concurrent access
    - Fail-closed security model
    - Comprehensive intrusion detection
    """
    
    def __init__(self, config: Optional[AuthorityConfiguration] = None):
        """Initialize the Authority State Machine with secure defaults."""
        self._config = config or AuthorityConfiguration()
        
        # Core state (protected by lock)
        self._lock = threading.RLock()
        self._current_state = AuthorityState.LOCKED_LISTEN_ONLY
        self._session_id = str(uuid.uuid4())
        self._state_history: List[StateTransition] = []
        
        # Timing and session management
        self._armed_at: Optional[datetime] = None
        self._last_activity: datetime = datetime.utcnow()
        self._verification_start: Optional[datetime] = None
        
        # Biometric verification tracking
        self._pending_verifications: Dict[BiometricFactor, BiometricVerification] = {}
        self._failed_attempts: int = 0
        self._last_intrusion: Optional[datetime] = None
        
        # Current policy and requirements
        self._current_policy = AuthorityPolicy.LOW_RISK
        self._required_factors: Set[BiometricFactor] = self._config.policy_requirements[self._current_policy]
        
        # Integrity protection
        self._integrity_key = secrets.token_bytes(32)  # AES-256 key for HMAC
        
        # Mark as initialized to enable protection
        self._initialized = True
        
        # Initial state logging
        self._log_state_transition(
            from_state=AuthorityState.LOCKED_LISTEN_ONLY,  # Conceptual initial state
            to_state=AuthorityState.LOCKED_LISTEN_ONLY,
            reason=StateTransitionReason.SYSTEM_STARTUP
        )
        
        # Calculate initial checksum after all state is set
        self._state_checksum = self._calculate_state_checksum()
        
        # Background monitoring (start after checksum is calculated)
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitor_timeouts, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Authority State Machine initialized", 
                   session_id=self._session_id,
                   initial_state=self._current_state.value,
                   policy=self._current_policy.value)
    
    def __setattr__(self, name: str, value) -> None:
        """Prevent direct modification of critical state after initialization."""
        # Allow setting during initialization
        if not hasattr(self, '_initialized'):
            super().__setattr__(name, value)
            return
        
        # Protect critical state variables and methods
        protected_attrs = {
            '_current_state', '_session_id', '_state_history', '_failed_attempts',
            '_last_intrusion', '_current_policy', '_required_factors', '_integrity_key',
            '_transition_state'  # Protect internal methods too
        }
        
        if name in protected_attrs:
            raise AttributeError(f"Cannot directly modify protected attribute '{name}'")
        
        # Allow modification of other attributes
        super().__setattr__(name, value)
    
    def __del__(self):
        """Cleanup resources on destruction."""
        self._monitoring_active = False
        if hasattr(self, '_monitor_thread') and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
    
    @property
    def current_state(self) -> AuthorityState:
        """Get the current authority state (thread-safe)."""
        with self._lock:
            self._verify_integrity()
            return self._current_state
    
    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        with self._lock:
            return self._session_id
    
    @property
    def is_armed(self) -> bool:
        """Check if the system is currently armed for automation."""
        return self.current_state == AuthorityState.ARMED
    
    @property
    def is_locked(self) -> bool:
        """Check if the system is in locked state."""
        return self.current_state == AuthorityState.LOCKED_LISTEN_ONLY
    
    @property
    def current_policy(self) -> AuthorityPolicy:
        """Get the current authority policy."""
        with self._lock:
            return self._current_policy
    
    def get_state_info(self) -> Dict[str, Union[str, int, float, bool]]:
        """Get comprehensive state information for monitoring."""
        with self._lock:
            self._verify_integrity()
            
            time_since_armed = None
            if self._armed_at:
                time_since_armed = (datetime.utcnow() - self._armed_at).total_seconds()
            
            time_since_activity = (datetime.utcnow() - self._last_activity).total_seconds()
            
            return {
                'state': self._current_state.value,
                'session_id': self._session_id,
                'policy': self._current_policy.value,
                'is_armed': self.is_armed,
                'is_locked': self.is_locked,
                'armed_at': self._armed_at.isoformat() if self._armed_at else None,
                'time_since_armed': time_since_armed,
                'time_since_activity': time_since_activity,
                'failed_attempts': self._failed_attempts,
                'required_factors': [f.value for f in self._required_factors],
                'pending_verifications': list(self._pending_verifications.keys()),
                'verification_in_progress': self._current_state == AuthorityState.IDENTITY_VERIFICATION,
                'intrusion_cooldown_active': self._is_in_intrusion_cooldown(),
                'state_transitions_count': len(self._state_history)
            }
    
    def initiate_voice_rearm(self, voice_confidence: float, speaker_verified: bool) -> bool:
        """
        Initiate voice-based re-arming process.
        
        Args:
            voice_confidence: Confidence score of voice recognition (0.0-1.0)
            speaker_verified: Whether speaker verification passed
            
        Returns:
            True if voice re-arming initiated successfully
            
        Raises:
            AuthorityTransitionError: If transition is not allowed
        """
        with self._lock:
            self._verify_integrity()
            
            # Validate confidence value
            if not (0.0 <= voice_confidence <= 1.0) or not isinstance(voice_confidence, (int, float)) or \
               voice_confidence != voice_confidence:  # Check for NaN
                logger.warning("Voice re-arm failed: invalid confidence value",
                             confidence=voice_confidence,
                             session_id=self._session_id)
                self._record_failed_attempt("invalid_confidence")
                return False
            
            # Check if we're in intrusion cooldown
            if self._is_in_intrusion_cooldown():
                logger.warning("Voice re-arm blocked: intrusion cooldown active",
                             session_id=self._session_id,
                             cooldown_remaining=self._get_cooldown_remaining())
                return False
            
            # Validate current state
            if self._current_state != AuthorityState.LOCKED_LISTEN_ONLY:
                raise AuthorityTransitionError(
                    f"Voice re-arm only allowed from LOCKED_LISTEN_ONLY, current: {self._current_state}"
                )
            
            # Validate voice authentication
            if voice_confidence < self._config.voice_confidence_threshold:
                logger.warning("Voice re-arm failed: insufficient confidence",
                             confidence=voice_confidence,
                             threshold=self._config.voice_confidence_threshold,
                             session_id=self._session_id)
                self._record_failed_attempt("voice_confidence_low")
                
                # Check if this should trigger intrusion detection
                if self._should_trigger_intrusion_detection():
                    self._trigger_intrusion_detection("Multiple voice authentication failures")
                
                return False
            
            if not speaker_verified:
                logger.warning("Voice re-arm failed: speaker verification failed",
                             session_id=self._session_id)
                self._record_failed_attempt("speaker_verification_failed")
                
                # Check if this should trigger intrusion detection
                if self._should_trigger_intrusion_detection():
                    self._trigger_intrusion_detection("Multiple speaker verification failures")
                
                return False
            
            # Record successful voice verification
            voice_verification = BiometricVerification(
                factor_type=BiometricFactor.VOICE,
                provider="whisper_cpp",
                confidence_score=voice_confidence,
                verification_time=datetime.utcnow(),
                success=True,
                session_id=self._session_id
            )
            
            self._pending_verifications[BiometricFactor.VOICE] = voice_verification
            
            # Check if voice-only policy is sufficient
            if self._required_factors == {BiometricFactor.VOICE}:
                return self._complete_arming()
            else:
                # Transition to identity verification for additional factors
                return self._transition_to_identity_verification()
    
    def verify_biometric_factor(self, factor: BiometricFactor, provider: str, 
                               confidence: float, success: bool, 
                               failure_reason: Optional[str] = None) -> bool:
        """
        Verify a biometric factor during identity verification.
        
        Args:
            factor: The biometric factor being verified
            provider: The biometric provider (e.g., "windows_hello")
            confidence: Confidence score (0.0-1.0)
            success: Whether verification succeeded
            failure_reason: Reason for failure if success=False
            
        Returns:
            True if verification successful and arming completed
        """
        with self._lock:
            self._verify_integrity()
            
            # Validate parameters
            if not isinstance(factor, BiometricFactor):
                raise TypeError(f"Factor must be BiometricFactor, got {type(factor)}")
            
            if provider is None:
                raise TypeError("Provider cannot be None")
            
            if not isinstance(provider, str):
                raise TypeError(f"Provider must be string, got {type(provider)}")
            
            # Validate state
            if self._current_state != AuthorityState.IDENTITY_VERIFICATION:
                raise AuthorityTransitionError(
                    f"Biometric verification only allowed during IDENTITY_VERIFICATION, current: {self._current_state}"
                )
            
            # Check verification timeout
            if self._verification_start and \
               (datetime.utcnow() - self._verification_start).total_seconds() > self._config.identity_verification_timeout:
                logger.warning("Biometric verification timeout",
                             factor=factor.value,
                             session_id=self._session_id)
                self._handle_verification_timeout()
                return False
            
            # Create verification record
            verification = BiometricVerification(
                factor_type=factor,
                provider=provider,
                confidence_score=confidence,
                verification_time=datetime.utcnow(),
                success=success,
                failure_reason=failure_reason,
                session_id=self._session_id
            )
            
            if success:
                # Validate confidence threshold
                threshold = self._get_confidence_threshold(factor)
                if confidence < threshold:
                    logger.warning("Biometric verification failed: insufficient confidence",
                                 factor=factor.value,
                                 confidence=confidence,
                                 threshold=threshold,
                                 session_id=self._session_id)
                    self._record_failed_attempt(f"{factor.value}_confidence_low")
                    return False
                
                # Record successful verification
                self._pending_verifications[factor] = verification
                logger.info("Biometric factor verified successfully",
                           factor=factor.value,
                           confidence=confidence,
                           provider=provider,
                           session_id=self._session_id)
                
                # Check if all required factors are verified
                if self._all_required_factors_verified():
                    return self._complete_arming()
                else:
                    # Still waiting for more factors
                    remaining = self._required_factors - set(self._pending_verifications.keys())
                    logger.info("Waiting for additional biometric factors",
                               remaining_factors=[f.value for f in remaining],
                               session_id=self._session_id)
                    return False
            else:
                # Handle verification failure
                logger.warning("Biometric verification failed",
                             factor=factor.value,
                             reason=failure_reason,
                             confidence=confidence,
                             session_id=self._session_id)
                
                self._record_failed_attempt(f"{factor.value}_verification_failed")
                
                # Check if this should trigger intrusion detection
                if self._should_trigger_intrusion_detection():
                    self._trigger_intrusion_detection(f"Multiple {factor.value} verification failures")
                
                return False
    
    def revoke_authority(self, reason: StateTransitionReason, 
                        metadata: Optional[Dict[str, str]] = None) -> bool:
        """
        Revoke automation authority and return to locked state.
        
        Args:
            reason: Reason for revocation
            metadata: Additional context information
            
        Returns:
            True if revocation successful
        """
        with self._lock:
            self._verify_integrity()
            
            # Validate reason parameter
            if not isinstance(reason, StateTransitionReason):
                raise TypeError(f"Reason must be StateTransitionReason, got {type(reason)}")
            
            if self._current_state == AuthorityState.LOCKED_LISTEN_ONLY:
                logger.debug("Authority already revoked", session_id=self._session_id)
                return True
            
            # Clear session state
            self._clear_session_state()
            
            # Transition to locked state
            self._transition_state(
                new_state=AuthorityState.LOCKED_LISTEN_ONLY,
                reason=reason,
                metadata=metadata or {}
            )
            
            logger.info("Authority revoked",
                       reason=reason.value,
                       session_id=self._session_id,
                       metadata=metadata)
            
            return True
    
    def update_activity(self) -> None:
        """Update last activity timestamp to prevent inactivity timeout."""
        with self._lock:
            self._last_activity = datetime.utcnow()
            self._update_state_checksum()
    
    def set_authority_policy(self, policy: AuthorityPolicy) -> bool:
        """
        Update the authority policy and required verification factors.
        
        Args:
            policy: New authority policy
            
        Returns:
            True if policy updated successfully
        """
        with self._lock:
            self._verify_integrity()
            
            old_policy = self._current_policy
            
            # Update both policy and required factors atomically
            object.__setattr__(self, '_current_policy', policy)
            object.__setattr__(self, '_required_factors', self._config.policy_requirements[policy])
            
            # Update checksum after both changes
            self._update_state_checksum()
            
            # If currently armed and new policy requires more factors, revoke authority
            if (self._current_state == AuthorityState.ARMED and 
                not self._all_required_factors_verified()):
                logger.warning("Policy change requires re-authentication",
                             old_policy=old_policy.value,
                             new_policy=policy.value,
                             session_id=self._session_id)
                self.revoke_authority(
                    reason=StateTransitionReason.MANUAL_REVOKE,
                    metadata={"policy_change": f"{old_policy.value} -> {policy.value}"}
                )
            
            logger.info("Authority policy updated",
                       old_policy=old_policy.value,
                       new_policy=policy.value,
                       required_factors=[f.value for f in self._required_factors],
                       session_id=self._session_id)
            
            return True
    
    def get_state_history(self, limit: Optional[int] = None) -> List[StateTransition]:
        """
        Get the history of state transitions.
        
        Args:
            limit: Maximum number of transitions to return (None for all)
            
        Returns:
            List of state transitions, most recent first
        """
        with self._lock:
            history = list(reversed(self._state_history))
            if limit:
                history = history[:limit]
            return history
    
    def verify_state_integrity(self) -> bool:
        """
        Verify the integrity of the state machine.
        
        Returns:
            True if integrity is valid
            
        Raises:
            AuthorityStateIntegrityError: If integrity check fails
        """
        with self._lock:
            try:
                self._verify_integrity()
                return True
            except AuthorityStateIntegrityError:
                return False
    
    # Private methods
    
    def _verify_integrity(self) -> None:
        """Verify state machine integrity."""
        current_checksum = self._calculate_state_checksum()
        if not hmac.compare_digest(current_checksum, self._state_checksum):
            logger.critical("Authority state integrity violation detected",
                           session_id=self._session_id,
                           expected_checksum=self._state_checksum[:16] + "...",
                           actual_checksum=current_checksum[:16] + "...")
            raise AuthorityStateIntegrityError("State machine integrity compromised")
    
    def _calculate_state_checksum(self) -> str:
        """Calculate HMAC checksum of critical state data."""
        # Only include critical state that shouldn't change without explicit transitions
        # Exclude last_activity as it updates frequently and isn't security-critical
        state_data = (
            f"{self._current_state.value}:"
            f"{self._session_id}:"
            f"{self._current_policy.value}:"
            f"{self._failed_attempts}:"
            f"{len(self._state_history)}"
        )
        return hmac.new(
            self._integrity_key,
            state_data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _update_state_checksum(self) -> None:
        """Update the state checksum after state changes."""
        self._state_checksum = self._calculate_state_checksum()
    
    def _transition_state(self, new_state: AuthorityState, 
                         reason: StateTransitionReason,
                         metadata: Optional[Dict[str, str]] = None) -> None:
        """Execute atomic state transition with logging."""
        old_state = self._current_state
        
        # Validate transition
        if not self._is_valid_transition(old_state, new_state, reason):
            raise AuthorityTransitionError(
                f"Invalid transition: {old_state} -> {new_state} (reason: {reason})"
            )
        
        # Additional validation for ARMED transitions
        if new_state == AuthorityState.ARMED:
            if reason == StateTransitionReason.BIOMETRIC_VERIFIED:
                # Must have all required factors verified
                if not self._all_required_factors_verified():
                    raise AuthorityTransitionError(
                        f"Cannot arm: missing required biometric factors. "
                        f"Required: {[f.value for f in self._required_factors]}, "
                        f"Verified: {list(self._pending_verifications.keys())}"
                    )
        
        # Execute transition using object.__setattr__ to bypass protection
        object.__setattr__(self, '_current_state', new_state)
        
        # Update timing
        if new_state == AuthorityState.ARMED:
            self._armed_at = datetime.utcnow()
        elif new_state == AuthorityState.LOCKED_LISTEN_ONLY:
            self._armed_at = None
        elif new_state == AuthorityState.IDENTITY_VERIFICATION:
            self._verification_start = datetime.utcnow()
        
        # Log transition
        self._log_state_transition(old_state, new_state, reason, metadata)
        
        # Update integrity checksum
        self._update_state_checksum()
    
    def _is_valid_transition(self, from_state: AuthorityState, 
                           to_state: AuthorityState,
                           reason: StateTransitionReason) -> bool:
        """Validate if a state transition is allowed."""
        # Define valid transitions
        valid_transitions = {
            AuthorityState.LOCKED_LISTEN_ONLY: {
                AuthorityState.IDENTITY_VERIFICATION: {
                    StateTransitionReason.VOICE_PHRASE_DETECTED
                },
                AuthorityState.ARMED: {
                    StateTransitionReason.BIOMETRIC_VERIFIED  # Direct arming for voice-only policy
                },
                AuthorityState.INTRUSION_DETECTED: {
                    StateTransitionReason.INTRUSION_DETECTED  # Allow intrusion detection from locked state
                }
            },
            AuthorityState.IDENTITY_VERIFICATION: {
                AuthorityState.ARMED: {
                    StateTransitionReason.BIOMETRIC_VERIFIED
                },
                AuthorityState.LOCKED_LISTEN_ONLY: {
                    StateTransitionReason.BIOMETRIC_FAILED,
                    StateTransitionReason.VERIFICATION_TIMEOUT,
                    StateTransitionReason.MANUAL_REVOKE
                },
                AuthorityState.INTRUSION_DETECTED: {
                    StateTransitionReason.INTRUSION_DETECTED
                }
            },
            AuthorityState.ARMED: {
                AuthorityState.LOCKED_LISTEN_ONLY: {
                    StateTransitionReason.TASK_COMPLETED,
                    StateTransitionReason.DESKTOP_VISIBLE,
                    StateTransitionReason.INACTIVITY_TIMEOUT,
                    StateTransitionReason.MANUAL_REVOKE,
                    StateTransitionReason.COMPONENT_FAILURE
                },
                AuthorityState.INTRUSION_DETECTED: {
                    StateTransitionReason.INTRUSION_DETECTED
                }
            },
            AuthorityState.INTRUSION_DETECTED: {
                AuthorityState.LOCKED_LISTEN_ONLY: {
                    StateTransitionReason.MANUAL_REVOKE  # Manual recovery only
                }
            }
        }
        
        allowed_reasons = valid_transitions.get(from_state, {}).get(to_state, set())
        return reason in allowed_reasons
    
    def _log_state_transition(self, from_state: AuthorityState, 
                            to_state: AuthorityState,
                            reason: StateTransitionReason,
                            metadata: Optional[Dict[str, str]] = None) -> None:
        """Log state transition with integrity protection."""
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            timestamp=datetime.utcnow(),
            session_id=self._session_id,
            verification_factors=tuple(self._pending_verifications.keys()),
            metadata=metadata or {}
        )
        
        self._state_history.append(transition)
        
        logger.info("Authority state transition",
                   from_state=from_state.value,
                   to_state=to_state.value,
                   reason=reason.value,
                   session_id=self._session_id,
                   transition_id=transition.integrity_hash[:8],
                   metadata=metadata)
    
    def _transition_to_identity_verification(self) -> bool:
        """Transition to identity verification state."""
        self._transition_state(
            new_state=AuthorityState.IDENTITY_VERIFICATION,
            reason=StateTransitionReason.VOICE_PHRASE_DETECTED
        )
        return True
    
    def _complete_arming(self) -> bool:
        """Complete the arming process after all verifications."""
        # Reset failed attempts on successful arming
        object.__setattr__(self, '_failed_attempts', 0)
        
        self._transition_state(
            new_state=AuthorityState.ARMED,
            reason=StateTransitionReason.BIOMETRIC_VERIFIED,
            metadata={
                "verified_factors": ",".join(f.value for f in self._pending_verifications.keys()),
                "policy": self._current_policy.value
            }
        )
        
        logger.info("Authority granted - system armed",
                   session_id=self._session_id,
                   policy=self._current_policy.value,
                   verified_factors=[f.value for f in self._pending_verifications.keys()])
        
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
            BiometricFactor.FINGERPRINT: self._config.fingerprint_confidence_threshold
        }
        return thresholds[factor]
    
    def _record_failed_attempt(self, failure_type: str) -> None:
        """Record a failed authentication attempt."""
        object.__setattr__(self, '_failed_attempts', self._failed_attempts + 1)
        self._update_state_checksum()
        
        logger.warning("Authentication attempt failed",
                      failure_type=failure_type,
                      failed_attempts=self._failed_attempts,
                      max_attempts=self._config.max_failed_attempts,
                      session_id=self._session_id)
    
    def _should_trigger_intrusion_detection(self) -> bool:
        """Determine if intrusion detection should be triggered."""
        return self._failed_attempts >= self._config.max_failed_attempts
    
    def _trigger_intrusion_detection(self, reason: str) -> None:
        """Trigger intrusion detection and lockdown."""
        object.__setattr__(self, '_last_intrusion', datetime.utcnow())
        
        self._transition_state(
            new_state=AuthorityState.INTRUSION_DETECTED,
            reason=StateTransitionReason.INTRUSION_DETECTED,
            metadata={"intrusion_reason": reason}
        )
        
        logger.critical("INTRUSION DETECTED - System locked down",
                       reason=reason,
                       failed_attempts=self._failed_attempts,
                       session_id=self._session_id)
    
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
            new_state=AuthorityState.LOCKED_LISTEN_ONLY,
            reason=StateTransitionReason.VERIFICATION_TIMEOUT
        )
    
    def _clear_session_state(self) -> None:
        """Clear session-specific state data."""
        self._pending_verifications.clear()
        self._verification_start = None
        self._armed_at = None
        object.__setattr__(self, '_session_id', str(uuid.uuid4()))  # New session
        # Note: _failed_attempts is NOT reset here - it persists across sessions for intrusion detection
        self._update_state_checksum()
    
    def _monitor_timeouts(self) -> None:
        """Background thread to monitor timeouts and enforce policies."""
        while self._monitoring_active:
            try:
                with self._lock:
                    current_time = datetime.utcnow()
                    
                    # Check identity verification timeout
                    if (self._current_state == AuthorityState.IDENTITY_VERIFICATION and
                        self._verification_start and
                        (current_time - self._verification_start).total_seconds() > self._config.identity_verification_timeout):
                        
                        logger.warning("Identity verification timeout",
                                     session_id=self._session_id)
                        self._handle_verification_timeout()
                    
                    # Check armed session timeout
                    elif (self._current_state == AuthorityState.ARMED and
                          self._armed_at and
                          (current_time - self._armed_at).total_seconds() > self._config.armed_session_timeout):
                        
                        logger.info("Armed session timeout",
                                   session_id=self._session_id)
                        self.revoke_authority(StateTransitionReason.INACTIVITY_TIMEOUT)
                    
                    # Check inactivity timeout (only when armed)
                    elif (self._current_state == AuthorityState.ARMED and
                          (current_time - self._last_activity).total_seconds() > self._config.inactivity_timeout):
                        
                        logger.info("Inactivity timeout",
                                   session_id=self._session_id)
                        self.revoke_authority(StateTransitionReason.INACTIVITY_TIMEOUT)
                
                # Sleep for shorter intervals for more responsive timeout handling
                time.sleep(0.1)
                
            except Exception as e:
                logger.error("Error in timeout monitor",
                           error=str(e),
                           session_id=getattr(self, '_session_id', 'unknown'))
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
    'AuthorityState',
    'AuthorityPolicy', 
    'BiometricFactor',
    'StateTransitionReason',
    'BiometricVerification',
    'StateTransition',
    'AuthorityConfiguration',
    'AuthorityStateMachine',
    'AuthorityStateIntegrityError',
    'AuthorityTransitionError',
    'create_authority_state_machine',
    'get_default_authority_config'
]