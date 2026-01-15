"""
Enhanced LLM Adapter - Production-Grade LLM System with Timeout and Caching

Extends the base LLM adapter with:
- 10-second timeout with template fallback
- Response caching for performance
- Comprehensive error handling
- Audit logging integration

SECURITY INVARIANTS:
- LLMs are advisory only, never authoritative
- All outputs are structured intents
- Timeouts prevent blocking operations
- Cache does not bypass security checks
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .adapter import AdapterConfiguration, LLMAdapter
from .intent import StructuredIntent
from .response_cache import ResponseCache
from .safety import SafeResponse
from .template_responses import TemplateResponseSystem


@dataclass
class EnhancedAdapterConfiguration(AdapterConfiguration):
    """Enhanced adapter configuration with timeout and caching."""

    # Timeout settings
    default_timeout_seconds: float = 10.0
    enable_timeout_fallback: bool = True

    # Caching settings
    enable_response_cache: bool = True
    cache_max_size: int = 1000
    cache_ttl_seconds: int = 3600  # 1 hour

    # Template fallback settings
    use_template_on_timeout: bool = True
    log_timeout_events: bool = True


class EnhancedLLMAdapter(LLMAdapter):
    """
    Enhanced LLM adapter with timeout and caching support.

    Features:
    - 10-second timeout with automatic fallback
    - Response caching for improved performance
    - Template responses for timeout scenarios
    - Comprehensive statistics and monitoring
    - Audit logging integration

    CRITICAL: Maintains all security invariants from base adapter.
    """

    def __init__(self, config: Optional[EnhancedAdapterConfiguration] = None):
        """
        Initialize enhanced LLM adapter.

        Args:
            config: Enhanced adapter configuration
        """
        # Initialize base adapter
        enhanced_config = config or EnhancedAdapterConfiguration()
        super().__init__(enhanced_config)

        # Store enhanced config
        self.enhanced_config = enhanced_config

        # Initialize caching system
        if self.enhanced_config.enable_response_cache:
            self.cache = ResponseCache(
                max_size=self.enhanced_config.cache_max_size,
                default_ttl_seconds=self.enhanced_config.cache_ttl_seconds,
                enable_statistics=True,
            )
            self.logger.info("Response caching enabled")
        else:
            self.cache = None
            self.logger.info("Response caching disabled")

        # Initialize template response system
        if self.enhanced_config.use_template_on_timeout:
            self.template_system = TemplateResponseSystem()
            self.logger.info("Template fallback enabled")
        else:
            self.template_system = None
            self.logger.info("Template fallback disabled")

        # Timeout statistics
        self.timeout_count = 0
        self.fallback_count = 0

        self.logger.info(
            "Enhanced LLM Adapter initialized "
            f"(timeout={self.enhanced_config.default_timeout_seconds}s, "
            f"cache={self.enhanced_config.enable_response_cache})"
        )

    async def generate_intent_with_timeout(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        preferred_provider: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> SafeResponse:
        """
        Generate structured intent with timeout and caching support.

        This method extends the base generate_intent with:
        - Automatic timeout after specified duration
        - Template fallback on timeout
        - Response caching for performance
        - Comprehensive error handling

        Args:
            user_input: User's natural language input
            context: Optional context information
            preferred_provider: Optional preferred provider name
            timeout_seconds: Optional custom timeout (default: 10s)

        Returns:
            SafeResponse: Safe, validated response with structured intent
        """
        start_time = datetime.utcnow()
        timeout = timeout_seconds or self.enhanced_config.default_timeout_seconds

        # Check cache first
        if self.cache:
            cached_response = self.cache.get(prompt=user_input, context=context, model=preferred_provider)

            if cached_response:
                self.logger.debug("Cache hit - returning cached response")

                # Parse cached response into SafeResponse
                try:
                    intent = self.intent_validator.validate_raw_response(cached_response)
                    return SafeResponse(
                        success=True,
                        safe_intent=intent,
                        original_filtered=cached_response,
                        processing_time_ms=self._get_processing_time(start_time),
                        metadata={"cache_hit": True},
                    )
                except Exception as e:
                    self.logger.warning(f"Cached response validation failed: {e}")
                    # Continue to generate new response

        # Attempt generation with timeout
        try:
            # Create task for generation
            generation_task = asyncio.create_task(
                self.generate_intent(user_input=user_input, context=context, preferred_provider=preferred_provider)
            )

            # Wait with timeout
            response = await asyncio.wait_for(generation_task, timeout=timeout)

            # Cache successful response
            if self.cache and response.success and response.original_filtered:
                self.cache.put(
                    prompt=user_input, response=response.original_filtered, context=context, model=preferred_provider
                )

            return response

        except asyncio.TimeoutError:
            # Timeout occurred - use fallback
            self.timeout_count += 1

            if self.enhanced_config.log_timeout_events:
                self.logger.warning(
                    f"LLM request timeout after {timeout}s " f"(provider={preferred_provider or self.current_provider})"
                )

            # Cancel the generation task
            if not generation_task.done():
                generation_task.cancel()
                try:
                    await generation_task
                except asyncio.CancelledError:
                    pass

            # Use template fallback if enabled
            if self.enhanced_config.enable_timeout_fallback and self.template_system:
                return self._generate_timeout_fallback(
                    user_input=user_input, context=context, elapsed_seconds=timeout, start_time=start_time
                )
            else:
                # Return timeout error
                return SafeResponse(
                    success=False,
                    error_message=f"LLM request timeout after {timeout} seconds",
                    processing_time_ms=self._get_processing_time(start_time),
                    metadata={"timeout": True},
                )

        except Exception as e:
            self.logger.error(f"Enhanced intent generation failed: {e}")
            return SafeResponse(
                success=False,
                error_message=f"Intent generation failed: {str(e)}",
                processing_time_ms=self._get_processing_time(start_time),
            )

    def _generate_timeout_fallback(
        self, user_input: str, context: Optional[Dict[str, Any]], elapsed_seconds: float, start_time: datetime
    ) -> SafeResponse:
        """
        Generate fallback response for timeout scenario.

        Args:
            user_input: Original user input
            context: Optional context
            elapsed_seconds: Time elapsed before timeout
            start_time: Request start time

        Returns:
            SafeResponse: Fallback response
        """
        self.fallback_count += 1

        # Get template response
        template_response = self.template_system.get_timeout_response(elapsed_seconds=elapsed_seconds, context=context)

        # Create fallback intent
        # Note: This is a conversational response, not an action intent
        fallback_intent = StructuredIntent(
            intent_type="conversation_response",
            parameters={"text": template_response},
            confidence=0.5,  # Low confidence for fallback
            context="Template fallback due to LLM timeout",
        )

        self.logger.info(f"Using template fallback: '{template_response}' " f"(timeout={elapsed_seconds}s)")

        return SafeResponse(
            success=True,
            safe_intent=fallback_intent,
            original_filtered=template_response,
            processing_time_ms=self._get_processing_time(start_time),
            metadata={"fallback_used": True, "timeout_seconds": elapsed_seconds, "fallback_type": "template"},
        )

    def get_cache_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics.

        Returns:
            Optional[Dict[str, Any]]: Cache statistics or None if caching disabled
        """
        if self.cache:
            return self.cache.get_statistics()
        return None

    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive enhanced adapter statistics.

        Returns:
            Dict[str, Any]: Enhanced statistics including base stats, cache, and timeout info
        """
        base_stats = self.get_adapter_statistics()

        enhanced_stats = {
            **base_stats,
            "timeout_statistics": {
                "timeout_count": self.timeout_count,
                "fallback_count": self.fallback_count,
                "timeout_rate": self.timeout_count / max(self.total_requests, 1),
                "fallback_rate": self.fallback_count / max(self.total_requests, 1),
            },
        }

        # Add cache statistics if available
        if self.cache:
            enhanced_stats["cache_statistics"] = self.get_cache_statistics()

        return enhanced_stats

    def invalidate_cache(
        self, prompt: Optional[str] = None, context: Optional[Dict[str, Any]] = None, model: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            prompt: Optional specific prompt to invalidate
            context: Optional context
            model: Optional model name

        Returns:
            int: Number of entries invalidated
        """
        if self.cache:
            return self.cache.invalidate(prompt, context, model)
        return 0

    async def cleanup_cache(self) -> int:
        """
        Clean up expired cache entries.

        Returns:
            int: Number of entries removed
        """
        if self.cache:
            return self.cache.cleanup_expired()
        return 0

    async def shutdown(self):
        """Shutdown enhanced adapter and cleanup resources."""
        self.logger.info("Shutting down Enhanced LLM Adapter...")

        # Cleanup cache
        if self.cache:
            expired_count = await self.cleanup_cache()
            self.logger.info(f"Cleaned up {expired_count} expired cache entries")

        # Shutdown base adapter
        await super().shutdown()

        self.logger.info("Enhanced LLM Adapter shutdown complete")
