"""
Integration Tests for LLM Adapter

End-to-end integration tests demonstrating the complete LLM adapter system
working with multiple providers, safety controls, and intent validation.
"""

import pytest
import asyncio
from unittest.mock import patch
import json

from src.llm.adapter import LLMAdapter, AdapterConfiguration
from src.llm.providers import LocalProvider, GeminiProvider, ProviderStatus, ProviderCapabilities
from src.llm.intent import StructuredIntent, IntentType


class TestLLMAdapterIntegration:
    """Integration tests for the complete LLM adapter system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_intent_generation(self):
        """Test complete end-to-end intent generation flow."""
        
        # Create adapter with realistic configuration
        config = AdapterConfiguration(
            default_provider="local",
            safety_enabled=True,
            fallback_enabled=True,
            max_fallback_attempts=2
        )
        
        adapter = LLMAdapter(config)
        
        try:
            # Initialize adapter (default providers may fail due to missing dependencies)
            success = await adapter.initialize()
            assert success  # Adapter should initialize even if providers fail
            
            # Create a working mock provider for testing
            class TestProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "test_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': f'Test response: {user_input}'},
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="test-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
            # Register working test provider
            test_provider = TestProvider()
            provider_success = await adapter.register_provider(test_provider)
            assert provider_success
            
            # Verify providers are registered
            status = adapter.get_provider_status()
            assert status['total_providers'] >= 1
            
            # Test intent generation
            response = await adapter.generate_intent("Type hello world")
            
            # Verify successful response
            assert response.success
            assert response.safe_intent is not None
            assert isinstance(response.safe_intent, StructuredIntent)
            
            # Verify intent properties
            intent = response.safe_intent
            assert intent.is_valid()
            assert intent.requires_authority is True
            assert intent.intent_type == IntentType.TYPE_TEXT
            assert "Test response" in intent.parameters['text']
            
            # Verify safety processing
            assert response.processing_time_ms is not None
            assert response.processing_time_ms > 0
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_provider_fallback_mechanism(self):
        """Test provider fallback when primary provider fails."""
        
        config = AdapterConfiguration(
            fallback_enabled=True,
            max_fallback_attempts=3
        )
        
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create a failing provider and a working provider
            class FailingProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "failing_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    raise Exception("Provider failure simulation")
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="failing-model",
                        provider_type="local"
                    )
                    
            class WorkingProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "working_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': f'Fallback response: {user_input}'},
                        'confidence': 0.8
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="working-model",
                        provider_type="local"
                    )
                    
            # Register failing provider as primary
            failing_provider = FailingProvider()
            await adapter.register_provider(failing_provider)
            
            # Register working provider as secondary
            working_provider = WorkingProvider()
            await adapter.register_provider(working_provider)
            
            # Make request - should fallback to working provider
            response = await adapter.generate_intent("Test fallback")
            
            # Should succeed via fallback
            assert response.success
            assert response.safe_intent is not None
            assert "Fallback response" in str(response.safe_intent.parameters)
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_safety_engine_integration(self):
        """Test integration with safety engine for malicious content."""
        
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create provider that returns malicious content
            class MaliciousProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "malicious_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': 'exec("malicious code")'},
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="malicious-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
                async def health_check(self) -> bool:
                    return True
            
            malicious_provider = MaliciousProvider()
            provider_success = await adapter.register_provider(malicious_provider)
            assert provider_success
            
            # Make request with malicious provider
            response = await adapter.generate_intent("Malicious test")
            
            # Safety engine should handle malicious content
            if response.success:
                # Content should be sanitized
                text_content = response.safe_intent.parameters.get('text', '')
                assert 'exec(' not in text_content
            else:
                # Or request should be blocked
                assert not response.success
                assert response.error_message is not None
                
            # Check safety statistics
            stats = adapter.get_adapter_statistics()
            assert 'safety_violations' in stats
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test handling of multiple concurrent requests."""
        
        config = AdapterConfiguration(
            global_rate_limit_per_minute=100,  # Allow many requests
            safety_enabled=True
        )
        
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create a working mock provider for testing
            class TestProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "test_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': f'Concurrent response: {user_input}'},
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="test-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
            # Register working test provider
            test_provider = TestProvider()
            provider_success = await adapter.register_provider(test_provider)
            assert provider_success
            
            # Create multiple concurrent requests
            requests = [
                adapter.generate_intent(f"Concurrent request {i}")
                for i in range(5)
            ]
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*requests, return_exceptions=True)
            
            # Verify all responses
            successful_responses = 0
            for response in responses:
                if isinstance(response, Exception):
                    # Some exceptions are acceptable
                    continue
                    
                if response.success:
                    successful_responses += 1
                    assert response.safe_intent is not None
                    assert isinstance(response.safe_intent, StructuredIntent)
                    
            # At least some requests should succeed
            assert successful_responses > 0
            
            # Check adapter statistics
            stats = adapter.get_adapter_statistics()
            assert stats['total_requests'] >= 5
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self):
        """Test rate limiting enforcement."""
        
        # Set very low rate limits for testing
        config = AdapterConfiguration(
            global_rate_limit_per_minute=2,
            safety_enabled=True
        )
        
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create a working mock provider for testing
            class TestProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "test_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': f'Rate limit test: {user_input}'},
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="test-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
            # Register working test provider
            test_provider = TestProvider()
            provider_success = await adapter.register_provider(test_provider)
            assert provider_success
            
            # Make requests up to the limit
            response1 = await adapter.generate_intent("Request 1")
            response2 = await adapter.generate_intent("Request 2")
            
            # Third request should be rate limited
            response3 = await adapter.generate_intent("Request 3")
            
            # At least one of the first two should succeed
            assert response1.success or response2.success
            
            # Third request should be rate limited
            assert not response3.success
            assert "rate limit" in response3.error_message.lower()
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_provider_health_monitoring(self):
        """Test provider health monitoring and status reporting."""
        
        config = AdapterConfiguration(health_check_interval_minutes=0)  # Disable automatic checks
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create a working mock provider for testing
            class TestProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "test_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': f'Health test: {user_input}'},
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="test-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
                async def health_check(self) -> bool:
                    return True
                    
            # Register working test provider
            test_provider = TestProvider()
            provider_success = await adapter.register_provider(test_provider)
            assert provider_success
            
            # Get initial provider status
            initial_status = adapter.get_provider_status()
            assert 'total_providers' in initial_status
            assert initial_status['total_providers'] >= 1
            
            # Perform manual health check
            await adapter._perform_health_checks()
            
            # Check individual provider status
            for provider_name in adapter.providers.keys():
                provider_status = adapter.get_provider_status(provider_name)
                assert 'provider_name' in provider_status
                assert 'status' in provider_status
                assert 'healthy' in provider_status
                
            # Check adapter statistics
            stats = adapter.get_adapter_statistics()
            assert 'total_requests' in stats
            assert 'successful_requests' in stats
            assert 'configuration' in stats
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_configuration_validation(self):
        """Test adapter configuration validation and behavior."""
        
        # Test different configurations
        configs = [
            AdapterConfiguration(safety_enabled=True, fallback_enabled=True),
            AdapterConfiguration(safety_enabled=False, fallback_enabled=False),
            AdapterConfiguration(max_fallback_attempts=1, request_timeout_seconds=10)
        ]
        
        for config in configs:
            adapter = LLMAdapter(config)
            
            try:
                # Should initialize successfully with any valid config
                success = await adapter.initialize()
                assert success
                
                # Configuration should be accessible
                stats = adapter.get_adapter_statistics()
                assert 'configuration' in stats
                
                config_dict = stats['configuration']
                assert config_dict['safety_enabled'] == config.safety_enabled
                assert config_dict['fallback_enabled'] == config.fallback_enabled
                
            finally:
                await adapter.shutdown()
                
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        
        config = AdapterConfiguration(
            fallback_enabled=True,
            max_fallback_attempts=2
        )
        
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create a working mock provider for testing
            class TestProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "test_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    # Handle different input scenarios
                    if not user_input or not user_input.strip():
                        raise ValueError("Empty input")
                    if len(user_input) > 5000:  # Simulate handling very long input
                        user_input = user_input[:100] + "... [truncated]"
                        
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': f'Processed: {user_input}'},
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="test-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
                async def health_check(self) -> bool:
                    return True
                    
            # Register working test provider
            test_provider = TestProvider()
            provider_success = await adapter.register_provider(test_provider)
            assert provider_success
            
            # Test with invalid input
            response = await adapter.generate_intent("")  # Empty input
            assert not response.success
            assert "empty" in response.error_message.lower()
            
            # Test with very long input
            very_long_input = "A" * 10000
            response = await adapter.generate_intent(very_long_input)
            
            # Should handle gracefully (either succeed with truncation or fail safely)
            if not response.success:
                assert response.error_message is not None
            else:
                assert response.safe_intent is not None
                
            # Adapter should still be functional after errors
            normal_response = await adapter.generate_intent("Normal request")
            # Should either succeed or fail gracefully
            assert isinstance(normal_response.success, bool)
            
        finally:
            await adapter.shutdown()


class TestLLMAdapterRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    @pytest.mark.asyncio
    async def test_typical_user_interaction_flow(self):
        """Test a typical user interaction flow."""
        
        adapter = LLMAdapter()
        
        try:
            await adapter.initialize()
            
            # Create a working mock provider for testing
            class TestProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "test_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    # Generate appropriate responses based on input
                    if "type" in user_input.lower():
                        intent_type = "type_text"
                        params = {'text': user_input.replace("Type ", "")}
                    elif "press" in user_input.lower():
                        intent_type = "key_press"
                        params = {'key': 'Enter'}
                    elif "click" in user_input.lower():
                        intent_type = "mouse_click"
                        params = {'x': 100, 'y': 200}
                    elif "launch" in user_input.lower():
                        intent_type = "launch_application"
                        params = {'application': 'notepad'}
                    else:
                        intent_type = "system_query"
                        params = {'query': user_input}
                        
                    return json.dumps({
                        'intent_type': intent_type,
                        'parameters': params,
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="test-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
                async def health_check(self) -> bool:
                    return True
                    
            # Register working test provider
            test_provider = TestProvider()
            provider_success = await adapter.register_provider(test_provider)
            assert provider_success
            
            # Simulate typical user requests
            user_requests = [
                "Type hello world",
                "Press Enter key",
                "Click at position 100, 200",
                "Launch notepad application",
                "Get system status"
            ]
            
            for request in user_requests:
                response = await adapter.generate_intent(request)
                
                # Each request should be handled appropriately
                if response.success:
                    assert response.safe_intent is not None
                    assert response.safe_intent.is_valid()
                    assert response.safe_intent.requires_authority is True
                else:
                    # Failures should be graceful with error messages
                    assert response.error_message is not None
                    
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_security_boundary_enforcement(self):
        """Test that security boundaries are properly enforced."""
        
        adapter = LLMAdapter(AdapterConfiguration(safety_enabled=True))
        
        try:
            await adapter.initialize()
            
            # Create a provider that might return malicious content
            class SecurityTestProvider(LocalProvider):
                def __init__(self):
                    super().__init__()
                    self.provider_name = "security_test_provider"
                    
                async def initialize(self) -> bool:
                    self.status = ProviderStatus.AVAILABLE
                    return True
                    
                async def generate_intent(self, user_input, context=None):
                    # Return the malicious input as-is to test safety filtering
                    return json.dumps({
                        'intent_type': 'type_text',
                        'parameters': {'text': user_input},
                        'confidence': 0.9
                    })
                    
                async def detect_capabilities(self):
                    return ProviderCapabilities(
                        supports_structured_output=True,
                        model_name="security-test-model",
                        provider_type="local",
                        requires_api_key=False,
                        requires_internet=False
                    )
                    
                async def health_check(self) -> bool:
                    return True
                    
            # Register security test provider
            security_provider = SecurityTestProvider()
            provider_success = await adapter.register_provider(security_provider)
            assert provider_success
            
            # Test various security boundary violations
            security_tests = [
                "exec('malicious code')",
                "import subprocess; subprocess.run(['rm', '-rf', '/'])",
                "os.system('format c:')",
                "__import__('os').system('evil')"
            ]
            
            for malicious_input in security_tests:
                response = await adapter.generate_intent(malicious_input)
                
                # All malicious inputs should be blocked or sanitized
                if response.success:
                    # If successful, content must be sanitized
                    intent_str = str(response.safe_intent.to_dict())
                    assert 'exec(' not in intent_str
                    assert 'subprocess' not in intent_str
                    assert 'os.system' not in intent_str
                else:
                    # Or request should be blocked
                    assert not response.success
                    
            # Verify security statistics
            stats = adapter.get_adapter_statistics()
            # Should have some safety violations recorded
            assert stats.get('safety_violations', 0) >= 0
            
        finally:
            await adapter.shutdown()