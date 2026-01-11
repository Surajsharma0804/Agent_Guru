"""
LLM Adapter - Multi-Provider Abstraction Layer

Central coordination system for all LLM providers with comprehensive security controls,
provider registration, capability detection, and safety enforcement.

CRITICAL SECURITY INVARIANT: LLMs are advisory only, never authoritative.
All LLM outputs are structured intents that must pass authority gates.
"""

from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
from threading import Lock
import json

from .providers import LLMProvider, GeminiProvider, LocalProvider, ProviderStatus, ProviderCapabilities
from .intent import StructuredIntent, IntentValidator
from .safety import LLMSafetyEngine, SafeResponse
from .exceptions import (
    LLMAdapterError,
    ProviderError,
    ProviderRegistrationError,
    CapabilityDetectionError,
    IsolationBreachError
)


class ProviderPriority(Enum):
    """Provider priority levels for fallback ordering."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"
    DISABLED = "disabled"


@dataclass
class ProviderRegistration:
    """Provider registration information."""
    
    provider: LLMProvider
    priority: ProviderPriority
    enabled: bool = True
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    average_latency_ms: float = 0.0
    
    def get_success_rate(self) -> float:
        """Calculate provider success rate."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
        
    def is_healthy(self) -> bool:
        """Check if provider is considered healthy."""
        return (
            self.enabled and 
            self.consecutive_failures < 5 and
            self.get_success_rate() > 0.8
        )


@dataclass
class AdapterConfiguration:
    """LLM Adapter configuration."""
    
    # Provider settings
    default_provider: str = "local"
    fallback_enabled: bool = True
    max_fallback_attempts: int = 3
    
    # Health monitoring
    health_check_interval_minutes: int = 5
    max_consecutive_failures: int = 5
    
    # Rate limiting
    global_rate_limit_per_minute: int = 100
    global_rate_limit_per_hour: int = 1000
    
    # Safety settings
    safety_enabled: bool = True
    content_filtering_enabled: bool = True
    
    # Timeout settings
    request_timeout_seconds: int = 30
    initialization_timeout_seconds: int = 60
    
    # Logging
    log_all_requests: bool = True
    log_safety_violations: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'default_provider': self.default_provider,
            'fallback_enabled': self.fallback_enabled,
            'max_fallback_attempts': self.max_fallback_attempts,
            'health_check_interval_minutes': self.health_check_interval_minutes,
            'max_consecutive_failures': self.max_consecutive_failures,
            'global_rate_limit_per_minute': self.global_rate_limit_per_minute,
            'global_rate_limit_per_hour': self.global_rate_limit_per_hour,
            'safety_enabled': self.safety_enabled,
            'content_filtering_enabled': self.content_filtering_enabled,
            'request_timeout_seconds': self.request_timeout_seconds,
            'initialization_timeout_seconds': self.initialization_timeout_seconds,
            'log_all_requests': self.log_all_requests,
            'log_safety_violations': self.log_safety_violations
        }


class LLMAdapter:
    """
    Multi-provider LLM abstraction layer with comprehensive security controls.
    
    Features:
    - Provider registration and discovery
    - Automatic failover and load balancing
    - Comprehensive safety and content filtering
    - Rate limiting and health monitoring
    - Audit logging and security enforcement
    
    SECURITY GUARANTEE: LLMs can only produce structured intents, never execute actions.
    """
    
    def __init__(self, config: Optional[AdapterConfiguration] = None):
        self.config = config or AdapterConfiguration()
        self.logger = logging.getLogger("llm.adapter")
        
        # Provider management
        self.providers: Dict[str, ProviderRegistration] = {}
        self.current_provider: Optional[str] = None
        self._provider_lock = Lock()
        
        # Safety and validation
        self.safety_engine = LLMSafetyEngine()
        self.intent_validator = IntentValidator()
        
        # Rate limiting
        self.global_requests_this_minute = 0
        self.global_requests_this_hour = 0
        self.last_minute_reset = datetime.utcnow()
        self.last_hour_reset = datetime.utcnow()
        self._rate_limit_lock = Lock()
        
        # Health monitoring
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.safety_violations = 0
        
        self.logger.info("LLM Adapter initialized with security-first configuration")
        
    async def initialize(self) -> bool:
        """
        Initialize the LLM adapter and register default providers.
        
        Returns:
            bool: True if initialization successful
        """
        
        try:
            self.logger.info("Initializing LLM Adapter...")
            
            # Register default providers (failures are acceptable)
            await self._register_default_providers()
            
            # Start health monitoring
            if self.config.health_check_interval_minutes > 0:
                self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
                
            # Set current provider (may be None if no providers available)
            await self._select_best_provider()
            
            provider_count = len(self.providers)
            if provider_count > 0:
                self.logger.info(f"LLM Adapter initialized successfully with {provider_count} providers")
            else:
                self.logger.warning("LLM Adapter initialized with no available providers - providers can be registered later")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM Adapter: {e}")
            return False
            
    async def shutdown(self):
        """Shutdown the LLM adapter and cleanup resources."""
        
        self.logger.info("Shutting down LLM Adapter...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel health monitoring
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
                
        # Shutdown providers
        for registration in self.providers.values():
            try:
                if hasattr(registration.provider, 'shutdown'):
                    await registration.provider.shutdown()
            except Exception as e:
                self.logger.warning(f"Error shutting down provider {registration.provider.provider_name}: {e}")
                
        self.logger.info("LLM Adapter shutdown complete")
        
    async def register_provider(
        self, 
        provider: LLMProvider, 
        priority: ProviderPriority = ProviderPriority.SECONDARY
    ) -> bool:
        """
        Register a new LLM provider.
        
        Args:
            provider: LLM provider instance
            priority: Provider priority level
            
        Returns:
            bool: True if registration successful
        """
        
        try:
            with self._provider_lock:
                # Check if provider already registered
                if provider.provider_name in self.providers:
                    raise ProviderRegistrationError(
                        f"Provider {provider.provider_name} already registered",
                        provider_name=provider.provider_name,
                        registration_phase="duplicate_check"
                    )
                    
                # Initialize provider
                self.logger.info(f"Initializing provider: {provider.provider_name}")
                
                initialization_successful = await asyncio.wait_for(
                    provider.initialize(),
                    timeout=self.config.initialization_timeout_seconds
                )
                
                if not initialization_successful:
                    raise ProviderRegistrationError(
                        f"Provider {provider.provider_name} initialization failed",
                        provider_name=provider.provider_name,
                        registration_phase="initialization"
                    )
                    
                # Detect capabilities
                try:
                    capabilities = await provider.detect_capabilities()
                    provider.capabilities = capabilities
                except Exception as e:
                    raise CapabilityDetectionError(
                        f"Failed to detect capabilities for {provider.provider_name}: {str(e)}",
                        provider_name=provider.provider_name,
                        capability_type="all"
                    )
                    
                # Create registration
                registration = ProviderRegistration(
                    provider=provider,
                    priority=priority,
                    last_health_check=datetime.utcnow()
                )
                
                # Register provider
                self.providers[provider.provider_name] = registration
                
                self.logger.info(
                    f"Successfully registered provider: {provider.provider_name} "
                    f"(priority: {priority.value}, capabilities: {len(capabilities.to_dict())} features)"
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to register provider {provider.provider_name}: {e}")
            return False
            
    async def unregister_provider(self, provider_name: str) -> bool:
        """
        Unregister an LLM provider.
        
        Args:
            provider_name: Name of provider to unregister
            
        Returns:
            bool: True if unregistration successful
        """
        
        try:
            with self._provider_lock:
                if provider_name not in self.providers:
                    self.logger.warning(f"Provider {provider_name} not found for unregistration")
                    return False
                    
                registration = self.providers[provider_name]
                
                # Shutdown provider if it has shutdown method
                if hasattr(registration.provider, 'shutdown'):
                    await registration.provider.shutdown()
                    
                # Remove from registry
                del self.providers[provider_name]
                
                # Update current provider if needed
                if self.current_provider == provider_name:
                    await self._select_best_provider()
                    
                self.logger.info(f"Successfully unregistered provider: {provider_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to unregister provider {provider_name}: {e}")
            return False
            
    async def generate_intent(
        self, 
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        preferred_provider: Optional[str] = None
    ) -> SafeResponse:
        """
        Generate structured intent from user input with comprehensive safety controls.
        
        CRITICAL: This method enforces the security invariant that LLMs are advisory only.
        
        Args:
            user_input: User's natural language input
            context: Optional context information
            preferred_provider: Optional preferred provider name
            
        Returns:
            SafeResponse: Safe, validated response with structured intent
        """
        
        start_time = datetime.utcnow()
        self.total_requests += 1
        
        # Check global rate limits
        if not self._check_global_rate_limits():
            self.failed_requests += 1
            return SafeResponse(
                success=False,
                error_message="Global rate limit exceeded",
                processing_time_ms=self._get_processing_time(start_time)
            )
            
        # Input validation
        if not user_input or not user_input.strip():
            self.failed_requests += 1
            return SafeResponse(
                success=False,
                error_message="Empty user input provided",
                processing_time_ms=self._get_processing_time(start_time)
            )
            
        # Determine provider to use
        provider_name = preferred_provider or self.current_provider
        if not provider_name or provider_name not in self.providers:
            await self._select_best_provider()
            provider_name = self.current_provider
            
        if not provider_name:
            self.failed_requests += 1
            return SafeResponse(
                success=False,
                error_message="No available LLM providers",
                processing_time_ms=self._get_processing_time(start_time)
            )
            
        # Attempt generation with fallback
        attempts = 0
        max_attempts = self.config.max_fallback_attempts if self.config.fallback_enabled else 1
        
        while attempts < max_attempts:
            try:
                registration = self.providers[provider_name]
                provider = registration.provider
                
                self.logger.debug(f"Generating intent using provider: {provider_name}")
                
                # Generate raw response
                raw_response = await asyncio.wait_for(
                    provider.generate_intent(user_input, context),
                    timeout=self.config.request_timeout_seconds
                )
                
                # Convert to string if it's a StructuredIntent
                if isinstance(raw_response, StructuredIntent):
                    response_text = json.dumps(raw_response.to_dict())
                else:
                    response_text = str(raw_response)
                    
                # Process through safety engine
                if self.config.safety_enabled:
                    safe_response = self.safety_engine.process_llm_response(response_text, context)
                    
                    if not safe_response.success:
                        self.safety_violations += 1
                        if self.config.log_safety_violations:
                            self.logger.warning(
                                f"Safety violation detected from provider {provider_name}: "
                                f"{safe_response.error_message}"
                            )
                        self.failed_requests += 1
                        return safe_response
                else:
                    # Direct validation without safety engine
                    try:
                        intent = self.intent_validator.validate_raw_response(response_text)
                        safe_response = SafeResponse(
                            success=True,
                            safe_intent=intent,
                            original_filtered=response_text,
                            processing_time_ms=self._get_processing_time(start_time)
                        )
                    except Exception as e:
                        self.failed_requests += 1
                        return SafeResponse(
                            success=False,
                            error_message=f"Intent validation failed: {str(e)}",
                            processing_time_ms=self._get_processing_time(start_time)
                        )
                        
                # Update provider statistics
                registration.total_requests += 1
                registration.successful_requests += 1
                registration.consecutive_failures = 0
                
                # Update global statistics
                self.successful_requests += 1
                self._record_global_request()
                
                # Log successful request
                if self.config.log_all_requests:
                    self.logger.info(
                        f"Successfully generated intent using {provider_name} "
                        f"(processing time: {safe_response.processing_time_ms}ms)"
                    )
                    
                return safe_response
                
            except Exception as e:
                attempts += 1
                
                # Update provider failure statistics
                if provider_name in self.providers:
                    registration = self.providers[provider_name]
                    registration.total_requests += 1
                    registration.consecutive_failures += 1
                    
                self.logger.warning(
                    f"Provider {provider_name} failed (attempt {attempts}/{max_attempts}): {str(e)}"
                )
                
                # Try fallback provider if enabled
                if attempts < max_attempts and self.config.fallback_enabled:
                    provider_name = await self._get_fallback_provider(provider_name)
                    if not provider_name:
                        break
                        
        # All attempts failed
        self.failed_requests += 1
        return SafeResponse(
            success=False,
            error_message=f"All provider attempts failed after {attempts} tries",
            processing_time_ms=self._get_processing_time(start_time)
        )
        
    def get_provider_status(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive provider status information.
        
        Args:
            provider_name: Optional specific provider name
            
        Returns:
            Dict[str, Any]: Provider status information
        """
        
        if provider_name:
            if provider_name not in self.providers:
                return {'error': f'Provider {provider_name} not found'}
                
            registration = self.providers[provider_name]
            return {
                'provider_name': provider_name,
                'status': registration.provider.status.value,
                'priority': registration.priority.value,
                'enabled': registration.enabled,
                'healthy': registration.is_healthy(),
                'success_rate': registration.get_success_rate(),
                'total_requests': registration.total_requests,
                'successful_requests': registration.successful_requests,
                'consecutive_failures': registration.consecutive_failures,
                'average_latency_ms': registration.average_latency_ms,
                'last_health_check': registration.last_health_check.isoformat() if registration.last_health_check else None,
                'capabilities': registration.provider.capabilities.to_dict() if registration.provider.capabilities else None
            }
        else:
            # Return status for all providers
            return {
                'current_provider': self.current_provider,
                'total_providers': len(self.providers),
                'healthy_providers': sum(1 for r in self.providers.values() if r.is_healthy()),
                'providers': {
                    name: {
                        'status': reg.provider.status.value,
                        'priority': reg.priority.value,
                        'enabled': reg.enabled,
                        'healthy': reg.is_healthy(),
                        'success_rate': reg.get_success_rate()
                    }
                    for name, reg in self.providers.items()
                }
            }
            
    def get_adapter_statistics(self) -> Dict[str, Any]:
        """Get comprehensive adapter statistics."""
        
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'safety_violations': self.safety_violations,
            'success_rate': self.successful_requests / max(self.total_requests, 1),
            'safety_violation_rate': self.safety_violations / max(self.total_requests, 1),
            'global_rate_limits': {
                'requests_this_minute': self.global_requests_this_minute,
                'requests_this_hour': self.global_requests_this_hour,
                'minute_limit': self.config.global_rate_limit_per_minute,
                'hour_limit': self.config.global_rate_limit_per_hour
            },
            'safety_statistics': self.safety_engine.get_safety_statistics(),
            'configuration': self.config.to_dict()
        }
        
    async def _register_default_providers(self):
        """Register default LLM providers."""
        
        # Register local provider as primary (privacy-first)
        try:
            local_provider = LocalProvider()
            success = await self.register_provider(local_provider, ProviderPriority.PRIMARY)
            if not success:
                self.logger.info("Local provider not available - missing model file or configuration")
        except Exception as e:
            self.logger.info(f"Local provider not available: {e}")
        
        # Register Gemini as secondary (if configured)
        try:
            gemini_config = {
                'api_key': None,  # Would be loaded from environment/config
                'model_name': 'gemini-pro'
            }
            gemini_provider = GeminiProvider(gemini_config)
            success = await self.register_provider(gemini_provider, ProviderPriority.SECONDARY)
            if not success:
                self.logger.info("Gemini provider not available - missing API key or configuration")
        except Exception as e:
            self.logger.info(f"Gemini provider not available: {e}")
            
    async def _select_best_provider(self):
        """Select the best available provider based on health and priority."""
        
        best_provider = None
        best_priority = None
        
        for name, registration in self.providers.items():
            if not registration.is_healthy():
                continue
                
            if best_provider is None or registration.priority.value < best_priority.value:
                best_provider = name
                best_priority = registration.priority
                
        self.current_provider = best_provider
        
        if best_provider:
            self.logger.info(f"Selected provider: {best_provider}")
        else:
            self.logger.warning("No healthy providers available")
            
    async def _get_fallback_provider(self, failed_provider: str) -> Optional[str]:
        """Get next best provider for fallback."""
        
        for name, registration in self.providers.items():
            if name != failed_provider and registration.is_healthy():
                return name
                
        return None
        
    def _check_global_rate_limits(self) -> bool:
        """Check global rate limits."""
        
        with self._rate_limit_lock:
            now = datetime.utcnow()
            
            # Reset minute counter
            if now - self.last_minute_reset >= timedelta(minutes=1):
                self.global_requests_this_minute = 0
                self.last_minute_reset = now
                
            # Reset hour counter
            if now - self.last_hour_reset >= timedelta(hours=1):
                self.global_requests_this_hour = 0
                self.last_hour_reset = now
                
            # Check limits
            if self.global_requests_this_minute >= self.config.global_rate_limit_per_minute:
                return False
            if self.global_requests_this_hour >= self.config.global_rate_limit_per_hour:
                return False
                
            return True
            
    def _record_global_request(self):
        """Record a global request for rate limiting."""
        with self._rate_limit_lock:
            self.global_requests_this_minute += 1
            self.global_requests_this_hour += 1
            
    async def _health_monitor_loop(self):
        """Background health monitoring loop."""
        
        while not self._shutdown_event.is_set():
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.health_check_interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(60)  # Wait before retrying
                
    async def _perform_health_checks(self):
        """Perform health checks on all providers."""
        
        for name, registration in self.providers.items():
            try:
                is_healthy = await registration.provider.health_check()
                registration.last_health_check = datetime.utcnow()
                
                if not is_healthy:
                    registration.consecutive_failures += 1
                    self.logger.warning(f"Provider {name} failed health check")
                else:
                    registration.consecutive_failures = 0
                    
            except Exception as e:
                registration.consecutive_failures += 1
                self.logger.error(f"Health check failed for provider {name}: {e}")
                
        # Update current provider if needed
        if self.current_provider and not self.providers[self.current_provider].is_healthy():
            await self._select_best_provider()
            
    def _get_processing_time(self, start_time: datetime) -> int:
        """
        Calculate processing time in milliseconds with microsecond precision.
        
        For high-performance systems, processing may complete in microseconds.
        This method ensures accurate timing measurement for production monitoring.
        """
        delta = datetime.utcnow() - start_time
        total_microseconds = delta.total_seconds() * 1_000_000
        # Convert to milliseconds, ensuring minimum of 1ms for completed operations
        milliseconds = max(1, int(total_microseconds / 1000))
        return milliseconds