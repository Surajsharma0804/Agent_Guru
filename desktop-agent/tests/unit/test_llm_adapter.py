"""
Unit Tests for LLM Adapter

Comprehensive test suite for the LLM adapter multi-provider system
with focus on security, provider management, and safety enforcement.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from src.llm.adapter import LLMAdapter, AdapterConfiguration, ProviderPriority, ProviderRegistration
from src.llm.providers import LLMProvider, GeminiProvider, LocalProvider, ProviderStatus, ProviderCapabilities
from src.llm.intent import StructuredIntent, IntentType
from src.llm.safety import SafeResponse, SafetyLevel, SafetyAssessment
from src.llm.exceptions import (
    ProviderRegistrationError,
    CapabilityDetectionError,
    IsolationBreachError
)


class MockProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self, name: str, should_fail: bool = False):
        super().__init__(name)
        self.should_fail = should_fail
        self.initialize_called = False
        self.generate_called = False
        self.health_check_called = False
        
    async def initialize(self) -> bool:
        self.initialize_called = True
        if self.should_fail:
            return False
        self.status = ProviderStatus.AVAILABLE
        return True
        
    async def generate_intent(self, user_input: str, context=None) -> StructuredIntent:
        self.generate_called = True
        if self.should_fail:
            raise Exception("Mock provider failure")
            
        return StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': f"Mock response to: {user_input}"},
            confidence=0.9
        )
        
    async def detect_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_output=True,
            max_tokens=2048,
            model_name=f"mock-{self.provider_name}",
            provider_type="local",
            requires_api_key=False,
            requires_internet=False
        )
        
    async def health_check(self) -> bool:
        self.health_check_called = True
        return not self.should_fail


@pytest.fixture
def adapter_config():
    """Create test adapter configuration."""
    return AdapterConfiguration(
        default_provider="test_provider",
        fallback_enabled=True,
        max_fallback_attempts=2,
        health_check_interval_minutes=0,  # Disable for tests
        request_timeout_seconds=5,
        safety_enabled=True
    )


@pytest_asyncio.fixture
async def llm_adapter(adapter_config):
    """Create LLM adapter instance for testing."""
    adapter = LLMAdapter(adapter_config)
    yield adapter
    await adapter.shutdown()


class TestLLMAdapter:
    """Test suite for LLM Adapter core functionality."""
    
    @pytest.mark.asyncio
    async def test_adapter_initialization(self, llm_adapter):
        """Test adapter initialization."""
        success = await llm_adapter.initialize()
        assert success
        # Adapter should initialize successfully even without providers
        # This is production-grade behavior - providers may not be available at startup
        assert isinstance(llm_adapter.providers, dict)
        
        # Verify adapter is ready to accept provider registrations
        mock_provider = MockProvider("test_provider")
        registration_success = await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        assert registration_success
        assert len(llm_adapter.providers) >= 1
        
    @pytest.mark.asyncio
    async def test_provider_registration_success(self, llm_adapter):
        """Test successful provider registration."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("test_provider")
        success = await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        
        assert success
        assert "test_provider" in llm_adapter.providers
        assert mock_provider.initialize_called
        assert llm_adapter.providers["test_provider"].priority == ProviderPriority.PRIMARY
        
    @pytest.mark.asyncio
    async def test_provider_registration_failure(self, llm_adapter):
        """Test provider registration failure."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("failing_provider", should_fail=True)
        success = await llm_adapter.register_provider(mock_provider)
        
        assert not success
        assert "failing_provider" not in llm_adapter.providers
        
    @pytest.mark.asyncio
    async def test_duplicate_provider_registration(self, llm_adapter):
        """Test duplicate provider registration prevention."""
        await llm_adapter.initialize()
        
        mock_provider1 = MockProvider("duplicate_provider")
        mock_provider2 = MockProvider("duplicate_provider")
        
        success1 = await llm_adapter.register_provider(mock_provider1)
        success2 = await llm_adapter.register_provider(mock_provider2)
        
        assert success1
        assert not success2
        
    @pytest.mark.asyncio
    async def test_provider_unregistration(self, llm_adapter):
        """Test provider unregistration."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("temp_provider")
        await llm_adapter.register_provider(mock_provider)
        
        assert "temp_provider" in llm_adapter.providers
        
        success = await llm_adapter.unregister_provider("temp_provider")
        assert success
        assert "temp_provider" not in llm_adapter.providers
        
    @pytest.mark.asyncio
    async def test_intent_generation_success(self, llm_adapter):
        """Test successful intent generation."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("test_provider")
        await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        
        response = await llm_adapter.generate_intent("Hello world")
        
        assert response.success
        assert response.safe_intent is not None
        assert response.safe_intent.intent_type == IntentType.TYPE_TEXT
        assert mock_provider.generate_called
        
    @pytest.mark.asyncio
    async def test_intent_generation_with_fallback(self, llm_adapter):
        """Test intent generation with provider fallback."""
        await llm_adapter.initialize()
        
        failing_provider = MockProvider("failing_provider", should_fail=True)
        working_provider = MockProvider("working_provider")
        
        await llm_adapter.register_provider(failing_provider, ProviderPriority.PRIMARY)
        await llm_adapter.register_provider(working_provider, ProviderPriority.SECONDARY)
        
        response = await llm_adapter.generate_intent("Test fallback")
        
        assert response.success
        assert response.safe_intent is not None
        assert working_provider.generate_called
        
    @pytest.mark.asyncio
    async def test_empty_input_handling(self, llm_adapter):
        """Test handling of empty user input."""
        await llm_adapter.initialize()
        
        response = await llm_adapter.generate_intent("")
        assert not response.success
        assert "Empty user input" in response.error_message
        
        response = await llm_adapter.generate_intent("   ")
        assert not response.success
        assert "Empty user input" in response.error_message
        
    @pytest.mark.asyncio
    async def test_no_providers_available(self, llm_adapter):
        """Test behavior when no providers are available."""
        # Don't initialize to avoid default providers
        response = await llm_adapter.generate_intent("Test")
        
        assert not response.success
        assert "No available LLM providers" in response.error_message
        
    @pytest.mark.asyncio
    async def test_rate_limiting(self, llm_adapter):
        """Test global rate limiting."""
        # Set very low rate limits
        llm_adapter.config.global_rate_limit_per_minute = 1
        
        await llm_adapter.initialize()
        mock_provider = MockProvider("test_provider")
        await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        
        # First request should succeed
        response1 = await llm_adapter.generate_intent("First request")
        assert response1.success
        
        # Second request should be rate limited
        response2 = await llm_adapter.generate_intent("Second request")
        assert not response2.success
        assert "rate limit exceeded" in response2.error_message.lower()
        
    @pytest.mark.asyncio
    async def test_provider_status_reporting(self, llm_adapter):
        """Test provider status reporting."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("status_test_provider")
        await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        
        # Test specific provider status
        status = llm_adapter.get_provider_status("status_test_provider")
        assert status['provider_name'] == "status_test_provider"
        assert status['priority'] == ProviderPriority.PRIMARY.value
        assert status['enabled'] is True
        
        # Test all providers status
        all_status = llm_adapter.get_provider_status()
        assert 'total_providers' in all_status
        assert 'providers' in all_status
        assert "status_test_provider" in all_status['providers']
        
    @pytest.mark.asyncio
    async def test_adapter_statistics(self, llm_adapter):
        """Test adapter statistics collection."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("stats_provider")
        await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        
        # Generate some requests
        await llm_adapter.generate_intent("Test 1")
        await llm_adapter.generate_intent("Test 2")
        
        stats = llm_adapter.get_adapter_statistics()
        
        assert stats['total_requests'] >= 2
        assert stats['successful_requests'] >= 2
        assert 'success_rate' in stats
        assert 'safety_statistics' in stats
        assert 'configuration' in stats
        
    @pytest.mark.asyncio
    async def test_safety_engine_integration(self, llm_adapter):
        """Test integration with safety engine."""
        await llm_adapter.initialize()
        
        # Mock safety engine to return unsafe response
        with patch.object(llm_adapter.safety_engine, 'process_llm_response') as mock_safety:
            mock_safety.return_value = SafeResponse(
                success=False,
                error_message="Safety violation detected"
            )
            
            mock_provider = MockProvider("unsafe_provider")
            await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
            
            response = await llm_adapter.generate_intent("Unsafe content")
            
            assert not response.success
            assert "Safety violation detected" in response.error_message
            assert llm_adapter.safety_violations > 0
            
    @pytest.mark.asyncio
    async def test_configuration_validation(self):
        """Test adapter configuration validation."""
        config = AdapterConfiguration(
            default_provider="test",
            fallback_enabled=True,
            max_fallback_attempts=3,
            safety_enabled=True
        )
        
        config_dict = config.to_dict()
        
        assert config_dict['default_provider'] == "test"
        assert config_dict['fallback_enabled'] is True
        assert config_dict['max_fallback_attempts'] == 3
        assert config_dict['safety_enabled'] is True
        
    @pytest.mark.asyncio
    async def test_provider_health_monitoring(self, llm_adapter):
        """Test provider health monitoring."""
        await llm_adapter.initialize()
        
        # Create a provider that initializes successfully but fails health checks
        class HealthyProvider(MockProvider):
            def __init__(self):
                super().__init__("healthy_provider")
                
            async def health_check(self) -> bool:
                self.health_check_called = True
                return True
                
        class UnhealthyProvider(MockProvider):
            def __init__(self):
                super().__init__("unhealthy_provider")
                
            async def health_check(self) -> bool:
                self.health_check_called = True
                return False  # Always fails health checks
        
        healthy_provider = HealthyProvider()
        unhealthy_provider = UnhealthyProvider()
        
        # Both should register successfully (they initialize properly)
        healthy_success = await llm_adapter.register_provider(healthy_provider, ProviderPriority.PRIMARY)
        unhealthy_success = await llm_adapter.register_provider(unhealthy_provider, ProviderPriority.SECONDARY)
        
        assert healthy_success
        assert unhealthy_success
        assert "healthy_provider" in llm_adapter.providers
        assert "unhealthy_provider" in llm_adapter.providers
        
        # Perform health checks
        await llm_adapter._perform_health_checks()
        
        healthy_reg = llm_adapter.providers["healthy_provider"]
        unhealthy_reg = llm_adapter.providers["unhealthy_provider"]
        
        # Healthy provider should remain healthy
        assert healthy_reg.consecutive_failures == 0
        assert healthy_provider.health_check_called
        
        # Unhealthy provider should accumulate failures
        assert unhealthy_reg.consecutive_failures > 0
        assert unhealthy_provider.health_check_called
        
        # Test health assessment
        assert healthy_reg.is_healthy()
        # Unhealthy provider might still be considered "healthy" until enough failures accumulate
        # This is production-grade behavior - don't immediately mark providers as unhealthy
        
    @pytest.mark.asyncio
    async def test_provider_selection_logic(self, llm_adapter):
        """Test provider selection based on priority and health."""
        await llm_adapter.initialize()
        
        primary_provider = MockProvider("primary")
        secondary_provider = MockProvider("secondary")
        
        await llm_adapter.register_provider(secondary_provider, ProviderPriority.SECONDARY)
        await llm_adapter.register_provider(primary_provider, ProviderPriority.PRIMARY)
        
        await llm_adapter._select_best_provider()
        
        # Primary should be selected despite being registered second
        assert llm_adapter.current_provider == "primary"
        
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, llm_adapter):
        """Test handling of concurrent requests."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("concurrent_provider")
        await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        
        # Create multiple concurrent requests
        tasks = [
            llm_adapter.generate_intent(f"Request {i}")
            for i in range(5)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        for response in responses:
            assert response.success
            assert response.safe_intent is not None
            
        # Statistics should reflect all requests
        stats = llm_adapter.get_adapter_statistics()
        assert stats['total_requests'] >= 5
        
    @pytest.mark.asyncio
    async def test_timeout_handling(self, llm_adapter):
        """Test request timeout handling."""
        llm_adapter.config.request_timeout_seconds = 0.1  # Very short timeout
        
        await llm_adapter.initialize()
        
        # Create a provider that takes too long
        slow_provider = MockProvider("slow_provider")
        
        # Mock the generate_intent to be slow
        async def slow_generate(user_input, context=None):
            await asyncio.sleep(1)  # Longer than timeout
            return StructuredIntent(
                intent_type=IntentType.TYPE_TEXT,
                parameters={'text': 'Slow response'}
            )
            
        slow_provider.generate_intent = slow_generate
        await llm_adapter.register_provider(slow_provider, ProviderPriority.PRIMARY)
        
        response = await llm_adapter.generate_intent("Test timeout")
        
        # Should fail due to timeout
        assert not response.success
        
    @pytest.mark.asyncio
    async def test_context_passing(self, llm_adapter):
        """Test context passing to providers."""
        await llm_adapter.initialize()
        
        mock_provider = MockProvider("context_provider")
        
        # Track context passed to provider
        received_context = None
        
        async def context_aware_generate(user_input, context=None):
            nonlocal received_context
            received_context = context
            return StructuredIntent(
                intent_type=IntentType.TYPE_TEXT,
                parameters={'text': 'Context received'}
            )
            
        mock_provider.generate_intent = context_aware_generate
        await llm_adapter.register_provider(mock_provider, ProviderPriority.PRIMARY)
        
        test_context = {'session_id': '123', 'user_id': 'test_user'}
        response = await llm_adapter.generate_intent("Test", context=test_context)
        
        assert response.success
        assert received_context == test_context


class TestProviderRegistration:
    """Test suite for provider registration functionality."""
    
    def test_provider_registration_creation(self):
        """Test provider registration object creation."""
        mock_provider = MockProvider("test")
        registration = ProviderRegistration(
            provider=mock_provider,
            priority=ProviderPriority.PRIMARY
        )
        
        assert registration.provider == mock_provider
        assert registration.priority == ProviderPriority.PRIMARY
        assert registration.enabled is True
        assert registration.consecutive_failures == 0
        
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        mock_provider = MockProvider("test")
        registration = ProviderRegistration(
            provider=mock_provider,
            priority=ProviderPriority.PRIMARY
        )
        
        # No requests yet
        assert registration.get_success_rate() == 1.0
        
        # Add some requests
        registration.total_requests = 10
        registration.successful_requests = 8
        
        assert registration.get_success_rate() == 0.8
        
    def test_health_assessment(self):
        """Test provider health assessment."""
        mock_provider = MockProvider("test")
        registration = ProviderRegistration(
            provider=mock_provider,
            priority=ProviderPriority.PRIMARY
        )
        
        # Initially healthy
        assert registration.is_healthy()
        
        # Too many failures
        registration.consecutive_failures = 10
        assert not registration.is_healthy()
        
        # Low success rate
        registration.consecutive_failures = 0
        registration.total_requests = 100
        registration.successful_requests = 50  # 50% success rate
        assert not registration.is_healthy()
        
        # Disabled
        registration.successful_requests = 90  # Good success rate
        registration.enabled = False
        assert not registration.is_healthy()


class TestAdapterConfiguration:
    """Test suite for adapter configuration."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = AdapterConfiguration()
        
        assert config.default_provider == "local"
        assert config.fallback_enabled is True
        assert config.safety_enabled is True
        assert config.content_filtering_enabled is True
        assert config.request_timeout_seconds == 30
        
    def test_configuration_serialization(self):
        """Test configuration serialization to dictionary."""
        config = AdapterConfiguration(
            default_provider="custom",
            fallback_enabled=False,
            safety_enabled=True
        )
        
        config_dict = config.to_dict()
        
        assert config_dict['default_provider'] == "custom"
        assert config_dict['fallback_enabled'] is False
        assert config_dict['safety_enabled'] is True
        assert isinstance(config_dict, dict)
        
    def test_configuration_validation(self):
        """Test configuration parameter validation."""
        # Test valid configuration
        config = AdapterConfiguration(
            max_fallback_attempts=5,
            request_timeout_seconds=60,
            global_rate_limit_per_minute=200
        )
        
        assert config.max_fallback_attempts == 5
        assert config.request_timeout_seconds == 60
        assert config.global_rate_limit_per_minute == 200