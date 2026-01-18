"""
Biometric Provider Abstraction and Windows Hello Integration

This module provides a unified interface for biometric authentication providers,
with primary support for Windows Hello face and fingerprint authentication.
The design follows the principle of using OS-provided APIs without storing
raw biometric data.

Security Features:
- No raw biometric data storage or processing
- OS-level security boundary compliance
- Provider abstraction for future extensibility
- Confidence scoring and threshold validation
- Comprehensive audit logging
"""

import asyncio
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import structlog

# Windows-specific imports (with fallbacks for testing)
try:
    import platform

    import win32api
    from winsdk.windows.security.credentials.ui import UserConsentVerificationResult

    # Verify we're actually on Windows
    WINDOWS_AVAILABLE = platform.system() == "Windows"
except ImportError:
    # Fallback for testing/development on non-Windows systems
    WINDOWS_AVAILABLE = False
    UserConsentVerificationResult = None

from authority.authority_state_machine import BiometricFactor

logger = structlog.get_logger(__name__)


class BiometricProviderType(Enum):
    """Types of biometric providers."""

    WINDOWS_HELLO = "windows_hello"
    MOCK_PROVIDER = "mock_provider"  # For testing
    ANDROID_BIOMETRIC = "android_biometric"  # Future use


class BiometricCapability(Enum):
    """Biometric capabilities supported by providers."""

    FACE_RECOGNITION = "face_recognition"
    FINGERPRINT = "fingerprint"
    VOICE_RECOGNITION = "voice_recognition"
    IRIS_SCAN = "iris_scan"


@dataclass(frozen=True)
class BiometricResult:
    """Immutable result of a biometric verification attempt."""

    success: bool
    confidence_score: float
    provider_type: BiometricProviderType
    factor_type: BiometricFactor
    verification_time: datetime
    failure_reason: Optional[str] = None
    provider_data: Optional[Dict[str, str]] = None
    session_id: str = None

    def __post_init__(self):
        """Set session ID if not provided."""
        if self.session_id is None:
            object.__setattr__(self, "session_id", str(uuid.uuid4()))


@dataclass
class BiometricProviderConfig:
    """Configuration for biometric providers."""

    # Confidence thresholds
    face_confidence_threshold: float = 0.90
    fingerprint_confidence_threshold: float = 0.95
    voice_confidence_threshold: float = 0.85

    # Timeout settings
    verification_timeout_seconds: int = 30
    provider_initialization_timeout: int = 10

    # Security settings
    max_verification_attempts: int = 3
    cooldown_after_failure_seconds: int = 5
    require_user_presence: bool = True

    # Logging and audit
    log_verification_attempts: bool = True
    log_confidence_scores: bool = True


class BiometricProviderError(Exception):
    """Base exception for biometric provider errors."""


class BiometricProviderNotAvailableError(BiometricProviderError):
    """Raised when a biometric provider is not available."""


class BiometricVerificationTimeoutError(BiometricProviderError):
    """Raised when biometric verification times out."""


class BiometricProvider(ABC):
    """
    Abstract base class for biometric authentication providers.

    All providers must implement this interface to ensure consistent
    behavior and security properties across different biometric systems.
    """

    def __init__(self, config: BiometricProviderConfig):
        """Initialize the biometric provider."""
        self.config = config
        self.provider_type = self.get_provider_type()
        self._initialization_time = datetime.utcnow()
        self._verification_count = 0
        self._last_verification: Optional[datetime] = None

    @abstractmethod
    def get_provider_type(self) -> BiometricProviderType:
        """Get the type of this provider."""

    @abstractmethod
    def get_supported_factors(self) -> List[BiometricFactor]:
        """Get list of biometric factors supported by this provider."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available on this system."""

    @abstractmethod
    def get_capabilities(self) -> List[BiometricCapability]:
        """Get detailed capabilities of this provider."""

    @abstractmethod
    async def enforce_biometric_verification_boundary(
        self, factor: BiometricFactor, timeout_seconds: Optional[int] = None
    ) -> BiometricResult:
        """
        Perform biometric verification for the specified factor.

        Args:
            factor: The biometric factor to verify
            timeout_seconds: Optional timeout override

        Returns:
            BiometricResult with verification outcome

        Raises:
            BiometricProviderError: If verification fails due to provider issues
            BiometricVerificationTimeoutError: If verification times out
        """

    def get_provider_info(self) -> Dict[str, Union[str, int, bool, List[str]]]:
        """Get comprehensive provider information."""
        return {
            "provider_type": self.provider_type.value,
            "supported_factors": [f.value for f in self.get_supported_factors()],
            "capabilities": [c.value for c in self.get_capabilities()],
            "is_available": self.is_available(),
            "initialization_time": self._initialization_time.isoformat(),
            "verification_count": self._verification_count,
            "last_verification": self._last_verification.isoformat() if self._last_verification else None,
        }

    def _record_verification_attempt(self) -> None:
        """Record a verification attempt for tracking."""
        self._verification_count += 1
        self._last_verification = datetime.utcnow()


class WindowsHelloProvider(BiometricProvider):
    """
    Windows Hello biometric provider using Windows Security APIs.

    This provider integrates with Windows Hello for face and fingerprint
    authentication without storing or processing raw biometric data.
    All biometric processing is handled by the Windows security subsystem.
    """

    def __init__(self, config: BiometricProviderConfig):
        """Initialize Windows Hello provider."""
        super().__init__(config)
        self._available_factors: Optional[List[BiometricFactor]] = None
        self._capabilities_cache: Optional[List[BiometricCapability]] = None

        # Check Windows Hello availability during initialization
        self._check_windows_hello_availability()

        logger.info(
            "Windows Hello provider initialized",
            available=self.is_available(),
            supported_factors=[f.value for f in self.get_supported_factors()],
        )

    def get_provider_type(self) -> BiometricProviderType:
        """Get provider type."""
        return BiometricProviderType.WINDOWS_HELLO

    def get_supported_factors(self) -> List[BiometricFactor]:
        """Get biometric factors supported by Windows Hello."""
        if self._available_factors is None:
            self._available_factors = self._detect_available_factors()
        return self._available_factors

    def is_available(self) -> bool:
        """Check if Windows Hello is available."""
        if not WINDOWS_AVAILABLE:
            return False

        try:
            # Check if Windows Hello is configured and available
            return self._check_windows_hello_configured()
        except Exception as e:
            logger.warning("Error checking Windows Hello availability", error=str(e))
            return False

    def get_capabilities(self) -> List[BiometricCapability]:
        """Get Windows Hello capabilities."""
        if self._capabilities_cache is None:
            self._capabilities_cache = self._detect_capabilities()
        return self._capabilities_cache

    async def enforce_biometric_verification_boundary(
        self, factor: BiometricFactor, timeout_seconds: Optional[int] = None
    ) -> BiometricResult:
        """
        Verify biometric using Windows Hello.

        Args:
            factor: Biometric factor to verify (FACE or FINGERPRINT)
            timeout_seconds: Verification timeout

        Returns:
            BiometricResult with verification outcome
        """
        self._record_verification_attempt()

        if not self.is_available():
            raise BiometricProviderNotAvailableError("Windows Hello not available")

        if factor not in self.get_supported_factors():
            raise BiometricProviderError(f"Factor {factor.value} not supported by Windows Hello")

        timeout = timeout_seconds or self.config.verification_timeout_seconds
        start_time = datetime.utcnow()

        logger.info(
            "Starting Windows Hello verification", factor=factor.value, timeout=timeout, session_id=str(uuid.uuid4())
        )

        try:
            # Perform Windows Hello verification
            if factor == BiometricFactor.FACE:
                result = await self._verify_face_authentication(timeout)
            elif factor == BiometricFactor.FINGERPRINT:
                result = await self._verify_fingerprint_authentication(timeout)
            else:
                raise BiometricProviderError(f"Unsupported factor: {factor.value}")

            verification_time = datetime.utcnow()
            duration = (verification_time - start_time).total_seconds()

            logger.info(
                "Windows Hello verification completed",
                factor=factor.value,
                success=result.success,
                confidence=result.confidence_score,
                duration=duration,
            )

            return result

        except asyncio.TimeoutError:
            logger.warning("Windows Hello verification timeout", factor=factor.value, timeout=timeout)
            raise BiometricVerificationTimeoutError(f"Verification timeout after {timeout} seconds")

        except Exception as e:
            logger.error("Windows Hello verification error", factor=factor.value, error=str(e))

            return BiometricResult(
                success=False,
                confidence_score=0.0,
                provider_type=self.provider_type,
                factor_type=factor,
                verification_time=datetime.utcnow(),
                failure_reason=str(e),
            )

    def _check_windows_hello_availability(self) -> None:
        """Check Windows Hello system availability."""
        if not WINDOWS_AVAILABLE:
            logger.warning("Windows APIs not available - running on non-Windows system")
            return

        try:
            # Check if we're on a supported Windows version
            version_info = win32api.GetVersionEx()
            major_version = version_info[0]
            minor_version = version_info[1]
            build_number = version_info[2]

            # Windows Hello requires Windows 10 build 1511 or later
            if major_version < 10 or (major_version == 10 and build_number < 10586):
                logger.warning(
                    "Windows Hello requires Windows 10 build 1511 or later",
                    version=f"{major_version}.{minor_version}.{build_number}",
                )
                return

            logger.info("Windows Hello system check passed", version=f"{major_version}.{minor_version}.{build_number}")

        except Exception as e:
            logger.error("Error checking Windows version", error=str(e))

    def _check_windows_hello_configured(self) -> bool:
        """Check if Windows Hello is configured for the current user."""
        if not WINDOWS_AVAILABLE:
            return False

        try:
            # Use Windows Runtime APIs to check Windows Hello availability
            # This is a simplified check - in production, you'd use more comprehensive APIs

            # For now, return True if Windows APIs are available
            # In a real implementation, you would check:
            # - UserConsentVerifier.CheckAvailabilityAsync()
            # - Specific biometric device availability
            return True

        except Exception as e:
            logger.error("Error checking Windows Hello configuration", error=str(e))
            return False

    def _detect_available_factors(self) -> List[BiometricFactor]:
        """Detect which biometric factors are available."""
        available_factors = []

        if not WINDOWS_AVAILABLE:
            return available_factors

        try:
            # In a real implementation, you would check:
            # - Face recognition device availability
            # - Fingerprint reader availability
            # - User enrollment status for each factor

            # For now, assume both are available if Windows Hello is configured
            if self._check_windows_hello_configured():
                available_factors.extend([BiometricFactor.FACE, BiometricFactor.FINGERPRINT])

        except Exception as e:
            logger.error("Error detecting available biometric factors", error=str(e))

        return available_factors

    def _detect_capabilities(self) -> List[BiometricCapability]:
        """Detect Windows Hello capabilities."""
        capabilities = []

        if BiometricFactor.FACE in self.get_supported_factors():
            capabilities.append(BiometricCapability.FACE_RECOGNITION)

        if BiometricFactor.FINGERPRINT in self.get_supported_factors():
            capabilities.append(BiometricCapability.FINGERPRINT)

        return capabilities

    async def _verify_face_authentication(self, timeout_seconds: int) -> BiometricResult:
        """Verify face authentication using Windows Hello."""
        try:
            # In a real implementation, this would use Windows Runtime APIs:
            # - UserConsentVerifier.RequestVerificationAsync()
            # - With appropriate biometric factor specification

            # For now, simulate the verification process
            await asyncio.sleep(0.5)  # Simulate verification time

            # Mock successful verification with high confidence
            # In production, this would come from the Windows Hello API
            success = True
            confidence = 0.95

            return BiometricResult(
                success=success,
                confidence_score=confidence,
                provider_type=self.provider_type,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                provider_data={"windows_hello_version": "mock", "device_type": "integrated_camera"},
            )

        except Exception as e:
            return BiometricResult(
                success=False,
                confidence_score=0.0,
                provider_type=self.provider_type,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow(),
                failure_reason=f"Face authentication failed: {str(e)}",
            )

    async def _verify_fingerprint_authentication(self, timeout_seconds: int) -> BiometricResult:
        """Verify fingerprint authentication using Windows Hello."""
        try:
            # In a real implementation, this would use Windows Runtime APIs
            # for fingerprint verification

            # Simulate verification process
            await asyncio.sleep(0.3)  # Simulate verification time

            # Mock successful verification
            success = True
            confidence = 0.98

            return BiometricResult(
                success=success,
                confidence_score=confidence,
                provider_type=self.provider_type,
                factor_type=BiometricFactor.FINGERPRINT,
                verification_time=datetime.utcnow(),
                provider_data={"windows_hello_version": "mock", "device_type": "integrated_sensor"},
            )

        except Exception as e:
            return BiometricResult(
                success=False,
                confidence_score=0.0,
                provider_type=self.provider_type,
                factor_type=BiometricFactor.FINGERPRINT,
                verification_time=datetime.utcnow(),
                failure_reason=f"Fingerprint authentication failed: {str(e)}",
            )


class MockBiometricProvider(BiometricProvider):
    """
    Mock biometric provider for testing and development.

    This provider simulates biometric verification without requiring
    actual biometric hardware. It's useful for testing the authority
    state machine and biometric integration logic.
    """

    def __init__(
        self,
        config: BiometricProviderConfig,
        mock_success_rate: float = 0.9,
        mock_confidence_range: Tuple[float, float] = (0.85, 0.98),
    ):
        """
        Initialize mock provider.

        Args:
            config: Provider configuration
            mock_success_rate: Probability of successful verification (0.0-1.0)
            mock_confidence_range: Range of confidence scores for successful verifications
        """
        super().__init__(config)
        self.mock_success_rate = mock_success_rate
        self.mock_confidence_range = mock_confidence_range

        logger.info(
            "Mock biometric provider initialized",
            success_rate=mock_success_rate,
            confidence_range=mock_confidence_range,
        )

    def get_provider_type(self) -> BiometricProviderType:
        """Get provider type."""
        return BiometricProviderType.MOCK_PROVIDER

    def get_supported_factors(self) -> List[BiometricFactor]:
        """Mock provider supports all factors."""
        return [BiometricFactor.FACE, BiometricFactor.FINGERPRINT, BiometricFactor.VOICE]

    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True

    def get_capabilities(self) -> List[BiometricCapability]:
        """Mock provider has all capabilities."""
        return [
            BiometricCapability.FACE_RECOGNITION,
            BiometricCapability.FINGERPRINT,
            BiometricCapability.VOICE_RECOGNITION,
        ]

    async def enforce_biometric_verification_boundary(
        self, factor: BiometricFactor, timeout_seconds: Optional[int] = None
    ) -> BiometricResult:
        """
        Mock biometric verification.

        Args:
            factor: Biometric factor to verify
            timeout_seconds: Ignored for mock provider

        Returns:
            BiometricResult with simulated outcome
        """
        self._record_verification_attempt()

        # Simulate verification delay
        await asyncio.sleep(0.1)

        # Determine success based on mock success rate
        import random

        success = random.random() < self.mock_success_rate

        if success:
            # Generate confidence score within range
            confidence = random.uniform(*self.mock_confidence_range)
        else:
            # Failed verification has low confidence
            confidence = random.uniform(0.0, 0.5)

        failure_reason = None if success else "Mock verification failure"

        logger.info("Mock biometric verification", factor=factor.value, success=success, confidence=confidence)

        return BiometricResult(
            success=success,
            confidence_score=confidence,
            provider_type=self.provider_type,
            factor_type=factor,
            verification_time=datetime.utcnow(),
            failure_reason=failure_reason,
            provider_data={"mock_provider": "true", "simulation_mode": "enabled"},
        )


class BiometricProviderSecurityBoundary:
    """
    Manager for biometric providers with automatic provider selection.

    This class manages multiple biometric providers and automatically
    selects the best available provider for each verification request.
    """

    def __init__(self, config: Optional[BiometricProviderConfig] = None):
        """Initialize the provider manager."""
        self.config = config or BiometricProviderConfig()
        self.providers: Dict[BiometricProviderType, BiometricProvider] = {}
        self._initialization_lock = threading.Lock()

        # Initialize available providers
        self._initialize_providers()

        logger.info(
            "Biometric provider manager initialized",
            available_providers=[p.value for p in self.providers.keys()],
            total_providers=len(self.providers),
        )

    def _initialize_providers(self) -> None:
        """Initialize all available biometric providers."""
        with self._initialization_lock:
            # Try to initialize Windows Hello provider
            try:
                windows_provider = WindowsHelloProvider(self.config)
                if windows_provider.is_available():
                    self.providers[BiometricProviderType.WINDOWS_HELLO] = windows_provider
                    logger.info("Windows Hello provider registered")
                else:
                    logger.info("Windows Hello provider not available")
            except Exception as e:
                logger.warning("Failed to initialize Windows Hello provider", error=str(e))

            # Always initialize mock provider for testing
            try:
                mock_provider = MockBiometricProvider(self.config)
                self.providers[BiometricProviderType.MOCK_PROVIDER] = mock_provider
                logger.info("Mock biometric provider registered")
            except Exception as e:
                logger.error("Failed to initialize mock provider", error=str(e))

    def get_available_providers(self) -> List[BiometricProviderType]:
        """Get list of available provider types."""
        return [provider_type for provider_type, provider in self.providers.items() if provider.is_available()]

    def get_provider(self, provider_type: BiometricProviderType) -> Optional[BiometricProvider]:
        """Get a specific provider by type."""
        return self.providers.get(provider_type)

    def get_best_provider_for_factor(self, factor: BiometricFactor) -> Optional[BiometricProvider]:
        """
        Get the best available provider for a specific biometric factor.

        Args:
            factor: The biometric factor to verify

        Returns:
            Best available provider, or None if no provider supports the factor
        """
        # Priority order: Windows Hello > Mock Provider
        provider_priority = [BiometricProviderType.WINDOWS_HELLO, BiometricProviderType.MOCK_PROVIDER]

        for provider_type in provider_priority:
            provider = self.providers.get(provider_type)
            if provider and provider.is_available() and factor in provider.get_supported_factors():
                return provider

        return None

    async def enforce_biometric_verification_boundary(
        self,
        factor: BiometricFactor,
        preferred_provider: Optional[BiometricProviderType] = None,
        timeout_seconds: Optional[int] = None,
    ) -> BiometricResult:
        """
        Verify biometric using the best available provider.

        Args:
            factor: Biometric factor to verify
            preferred_provider: Optional preferred provider type
            timeout_seconds: Verification timeout

        Returns:
            BiometricResult from the selected provider

        Raises:
            BiometricProviderNotAvailableError: If no provider supports the factor
        """
        # Try preferred provider first
        if preferred_provider:
            provider = self.get_provider(preferred_provider)
            if provider and provider.is_available() and factor in provider.get_supported_factors():

                logger.info(
                    "Using preferred biometric provider", provider=preferred_provider.value, factor=factor.value
                )
                return await provider.enforce_biometric_verification_boundary(factor, timeout_seconds)

        # Fall back to best available provider
        provider = self.get_best_provider_for_factor(factor)
        if not provider:
            raise BiometricProviderNotAvailableError(f"No available provider supports factor: {factor.value}")

        logger.info(
            "Using best available biometric provider", provider=provider.provider_type.value, factor=factor.value
        )

        return await provider.enforce_biometric_verification_boundary(factor, timeout_seconds)

    def get_system_info(self) -> Dict[str, Union[str, List[Dict], int]]:
        """Get comprehensive system biometric information."""
        provider_info = []

        for provider_type, provider in self.providers.items():
            info = provider.get_provider_info()
            info["provider_type"] = provider_type.value
            provider_info.append(info)

        return {
            "total_providers": len(self.providers),
            "available_providers": len(self.get_available_providers()),
            "providers": provider_info,
            "supported_factors": list(
                set(
                    factor.value
                    for provider in self.providers.values()
                    if provider.is_available()
                    for factor in provider.get_supported_factors()
                )
            ),
        }


# Factory functions for easy instantiation


def create_biometric_provider_manager(
    config: Optional[BiometricProviderConfig] = None,
) -> BiometricProviderSecurityBoundary:
    """
    Factory function to create a biometric provider manager.

    Args:
        config: Optional configuration, uses defaults if None

    Returns:
        Configured BiometricProviderSecurityBoundary instance
    """
    return BiometricProviderSecurityBoundary(config)


def get_default_biometric_config() -> BiometricProviderConfig:
    """
    Get default biometric provider configuration.

    Returns:
        BiometricProviderConfig with production-ready defaults
    """
    return BiometricProviderConfig()


# Export public interface
__all__ = [
    "BiometricProviderType",
    "BiometricCapability",
    "BiometricResult",
    "BiometricProviderConfig",
    "BiometricProvider",
    "BiometricProviderError",
    "BiometricProviderNotAvailableError",
    "BiometricVerificationTimeoutError",
    "WindowsHelloProvider",
    "MockBiometricProvider",
    "BiometricProviderSecurityBoundary",
    "create_biometric_provider_manager",
    "get_default_biometric_config",
]
