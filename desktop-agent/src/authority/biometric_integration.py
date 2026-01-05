"""
Biometric Integration for Authority State Machine

This module provides the integration layer between the Authority State Machine
and biometric providers, enabling seamless biometric verification within the
authority workflow.

Security Features:
- Confidence threshold validation
- Provider selection and fallback
- Comprehensive audit logging
- Error handling and recovery
- Thread-safe operations
"""

import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import structlog

from src.authority.state import (
    AuthorityStateMachine,
    BiometricFactor,
    BiometricVerification,
    AuthorityConfiguration
)
from src.biometric.providers import (
    BiometricProviderManager,
    BiometricProviderConfig,
    BiometricProviderType,
    BiometricResult,
    BiometricProviderNotAvailableError,
    BiometricVerificationTimeoutError,
    create_biometric_provider_manager
)

logger = structlog.get_logger(__name__)


@dataclass
class BiometricIntegrationConfig:
    """Configuration for biometric integration."""
    # Provider preferences
    preferred_face_provider: Optional[BiometricProviderType] = BiometricProviderType.WINDOWS_HELLO
    preferred_fingerprint_provider: Optional[BiometricProviderType] = BiometricProviderType.WINDOWS_HELLO
    fallback_to_mock: bool = True  # For testing/development
    
    # Verification settings
    max_verification_attempts: int = 3
    verification_timeout_seconds: int = 30
    retry_delay_seconds: float = 1.0
    
    # Confidence thresholds (can override provider defaults)
    face_confidence_override: Optional[float] = None
    fingerprint_confidence_override: Optional[float] = None
    
    # Integration behavior
    auto_retry_on_failure: bool = True
    log_biometric_events: bool = True


class BiometricIntegrationError(Exception):
    """Base exception for biometric integration errors."""
    pass


class BiometricAuthority:
    """
    Biometric Authority integration layer.
    
    This class provides a high-level interface for biometric verification
    within the GURU authority system, handling provider management,
    verification workflows, and integration with the Authority State Machine.
    """
    
    def __init__(self, 
                 authority_config: Optional[AuthorityConfiguration] = None,
                 biometric_config: Optional[BiometricProviderConfig] = None,
                 integration_config: Optional[BiometricIntegrationConfig] = None):
        """
        Initialize biometric authority integration.
        
        Args:
            authority_config: Authority state machine configuration
            biometric_config: Biometric provider configuration
            integration_config: Integration-specific configuration
        """
        self.authority_config = authority_config or AuthorityConfiguration()
        self.biometric_config = biometric_config or BiometricProviderConfig()
        self.integration_config = integration_config or BiometricIntegrationConfig()
        
        # Initialize biometric provider manager
        self.provider_manager = create_biometric_provider_manager(self.biometric_config)
        
        # Thread safety
        self._verification_lock = threading.Lock()
        self._verification_history: List[BiometricResult] = []
        
        logger.info("Biometric Authority integration initialized",
                   available_providers=len(self.provider_manager.get_available_providers()),
                   integration_config=self.integration_config.__dict__)
    
    def get_available_factors(self) -> List[BiometricFactor]:
        """
        Get list of biometric factors available on this system.
        
        Returns:
            List of available biometric factors
        """
        available_factors = set()
        
        for provider_type in self.provider_manager.get_available_providers():
            provider = self.provider_manager.get_provider(provider_type)
            if provider and provider.is_available():
                available_factors.update(provider.get_supported_factors())
        
        return list(available_factors)
    
    def is_factor_available(self, factor: BiometricFactor) -> bool:
        """
        Check if a specific biometric factor is available.
        
        Args:
            factor: Biometric factor to check
            
        Returns:
            True if factor is available
        """
        return factor in self.get_available_factors()
    
    async def verify_biometric_for_authority(self, 
                                           authority_machine: AuthorityStateMachine,
                                           factor: BiometricFactor) -> bool:
        """
        Perform biometric verification and update authority state machine.
        
        Args:
            authority_machine: Authority state machine instance
            factor: Biometric factor to verify
            
        Returns:
            True if verification successful and authority updated
        """
        with self._verification_lock:
            if not self.is_factor_available(factor):
                logger.warning("Biometric factor not available",
                             factor=factor.value,
                             available_factors=[f.value for f in self.get_available_factors()])
                return False
            
            try:
                # Get preferred provider for this factor
                preferred_provider = self._get_preferred_provider(factor)
                
                # Perform biometric verification
                result = await self.provider_manager.verify_biometric(
                    factor=factor,
                    preferred_provider=preferred_provider,
                    timeout_seconds=self.integration_config.verification_timeout_seconds
                )
                
                # Record verification attempt
                self._verification_history.append(result)
                
                # Check confidence threshold
                confidence_threshold = self._get_confidence_threshold(factor)
                confidence_met = result.confidence_score >= confidence_threshold
                
                if self.integration_config.log_biometric_events:
                    logger.info("Biometric verification completed",
                               factor=factor.value,
                               provider=result.provider_type.value,
                               success=result.success,
                               confidence=result.confidence_score,
                               threshold=confidence_threshold,
                               confidence_met=confidence_met,
                               session_id=result.session_id)
                
                # Update authority state machine if verification successful
                if result.success and confidence_met:
                    # Convert to authority verification format
                    auth_verification = BiometricVerification(
                        factor_type=factor,
                        provider=result.provider_type.value,
                        confidence_score=result.confidence_score,
                        verification_time=result.verification_time,
                        success=True,
                        session_id=result.session_id
                    )
                    
                    # Update authority state machine
                    return authority_machine.verify_biometric_factor(
                        factor=factor,
                        provider=result.provider_type.value,
                        confidence=result.confidence_score,
                        success=True
                    )
                else:
                    # Handle verification failure
                    failure_reason = result.failure_reason or "Confidence threshold not met"
                    
                    auth_verification = BiometricVerification(
                        factor_type=factor,
                        provider=result.provider_type.value,
                        confidence_score=result.confidence_score,
                        verification_time=result.verification_time,
                        success=False,
                        failure_reason=failure_reason,
                        session_id=result.session_id
                    )
                    
                    # Update authority state machine with failure
                    return authority_machine.verify_biometric_factor(
                        factor=factor,
                        provider=result.provider_type.value,
                        confidence=result.confidence_score,
                        success=False,
                        failure_reason=failure_reason
                    )
                
            except BiometricProviderNotAvailableError as e:
                logger.error("Biometric provider not available",
                           factor=factor.value,
                           error=str(e))
                return False
                
            except BiometricVerificationTimeoutError as e:
                logger.warning("Biometric verification timeout",
                             factor=factor.value,
                             timeout=self.integration_config.verification_timeout_seconds,
                             error=str(e))
                return False
                
            except Exception as e:
                logger.error("Biometric verification error",
                           factor=factor.value,
                           error=str(e))
                return False
    
    async def verify_multiple_factors(self,
                                    authority_machine: AuthorityStateMachine,
                                    factors: List[BiometricFactor],
                                    require_all: bool = True) -> Tuple[bool, List[BiometricFactor]]:
        """
        Verify multiple biometric factors.
        
        Args:
            authority_machine: Authority state machine instance
            factors: List of biometric factors to verify
            require_all: If True, all factors must succeed; if False, any factor success is sufficient
            
        Returns:
            Tuple of (overall_success, list_of_successful_factors)
        """
        successful_factors = []
        
        for factor in factors:
            try:
                success = await self.verify_biometric_for_authority(authority_machine, factor)
                if success:
                    successful_factors.append(factor)
                    
                    # If we don't require all factors and one succeeded, we can stop
                    if not require_all:
                        break
                        
            except Exception as e:
                logger.error("Error verifying biometric factor",
                           factor=factor.value,
                           error=str(e))
                
                # If we require all factors and one failed, overall failure
                if require_all:
                    break
        
        # Determine overall success
        if require_all:
            overall_success = len(successful_factors) == len(factors)
        else:
            overall_success = len(successful_factors) > 0
        
        logger.info("Multiple factor verification completed",
                   requested_factors=[f.value for f in factors],
                   successful_factors=[f.value for f in successful_factors],
                   require_all=require_all,
                   overall_success=overall_success)
        
        return overall_success, successful_factors
    
    def get_verification_history(self, limit: Optional[int] = None) -> List[BiometricResult]:
        """
        Get history of biometric verification attempts.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of biometric verification results, most recent first
        """
        with self._verification_lock:
            history = list(reversed(self._verification_history))
            if limit:
                history = history[:limit]
            return history
    
    def get_system_status(self) -> Dict[str, any]:
        """
        Get comprehensive biometric system status.
        
        Returns:
            Dictionary with system status information
        """
        provider_info = self.provider_manager.get_system_info()
        
        return {
            'available_factors': [f.value for f in self.get_available_factors()],
            'provider_info': provider_info,
            'verification_history_count': len(self._verification_history),
            'integration_config': {
                'preferred_face_provider': self.integration_config.preferred_face_provider.value if self.integration_config.preferred_face_provider else None,
                'preferred_fingerprint_provider': self.integration_config.preferred_fingerprint_provider.value if self.integration_config.preferred_fingerprint_provider else None,
                'fallback_to_mock': self.integration_config.fallback_to_mock,
                'max_verification_attempts': self.integration_config.max_verification_attempts,
                'verification_timeout_seconds': self.integration_config.verification_timeout_seconds
            },
            'confidence_thresholds': {
                'face': self._get_confidence_threshold(BiometricFactor.FACE),
                'fingerprint': self._get_confidence_threshold(BiometricFactor.FINGERPRINT),
                'voice': self._get_confidence_threshold(BiometricFactor.VOICE)
            }
        }
    
    def _get_preferred_provider(self, factor: BiometricFactor) -> Optional[BiometricProviderType]:
        """Get preferred provider for a biometric factor."""
        if factor == BiometricFactor.FACE:
            return self.integration_config.preferred_face_provider
        elif factor == BiometricFactor.FINGERPRINT:
            return self.integration_config.preferred_fingerprint_provider
        else:
            return None  # Use best available
    
    def _get_confidence_threshold(self, factor: BiometricFactor) -> float:
        """Get confidence threshold for a biometric factor."""
        # Check for integration config overrides first
        if factor == BiometricFactor.FACE and self.integration_config.face_confidence_override:
            return self.integration_config.face_confidence_override
        elif factor == BiometricFactor.FINGERPRINT and self.integration_config.fingerprint_confidence_override:
            return self.integration_config.fingerprint_confidence_override
        
        # Fall back to authority config thresholds
        if factor == BiometricFactor.FACE:
            return self.authority_config.face_confidence_threshold
        elif factor == BiometricFactor.FINGERPRINT:
            return self.authority_config.fingerprint_confidence_threshold
        elif factor == BiometricFactor.VOICE:
            return self.authority_config.voice_confidence_threshold
        else:
            return 0.85  # Default threshold


# Factory function for easy integration

def create_biometric_authority(authority_config: Optional[AuthorityConfiguration] = None,
                             biometric_config: Optional[BiometricProviderConfig] = None,
                             integration_config: Optional[BiometricIntegrationConfig] = None) -> BiometricAuthority:
    """
    Factory function to create a BiometricAuthority instance.
    
    Args:
        authority_config: Authority configuration
        biometric_config: Biometric provider configuration  
        integration_config: Integration configuration
        
    Returns:
        Configured BiometricAuthority instance
    """
    return BiometricAuthority(authority_config, biometric_config, integration_config)


# Export public interface
__all__ = [
    'BiometricIntegrationConfig',
    'BiometricIntegrationError',
    'BiometricAuthority',
    'create_biometric_authority'
]