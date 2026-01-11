"""
Property-Based Tests for LLM Isolation

Tests the critical security invariant: LLMs are advisory only, never authoritative.
All LLM outputs must be structured intents that pass through authority gates.

**Property 8: LLM Isolation**
**Validates: Requirements 17.9**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.llm.adapter import LLMAdapter, AdapterConfiguration
from src.llm.providers import LLMProvider, ProviderStatus, ProviderCapabilities
from src.llm.intent import StructuredIntent, IntentType, IntentValidator
from src.llm.safety import LLMSafetyEngine, SafeResponse, SafetyLevel
from src.llm.exceptions import IsolationBreachError, SafetyViolationError


# Hypothesis strategies for generating test data
@st.composite
def valid_intent_data(draw):
    """Generate valid intent data for testing."""
    intent_type = draw(st.sampled_from([
        IntentType.TYPE_TEXT,
        IntentType.PRESS_KEY,
        IntentType.MOUSE_ACTION,
        IntentType.LAUNCH_APP,
        IntentType.GET_STATUS
    ]))
    
    if intent_type == IntentType.TYPE_TEXT:
        parameters = {'text': draw(st.text(min_size=1, max_size=1000))}
    elif intent_type == IntentType.PRESS_KEY:
        parameters = {'key': draw(st.sampled_from(['Enter', 'Escape', 'Tab', 'Space']))}
    elif intent_type == IntentType.MOUSE_ACTION:
        parameters = {
            'action': draw(st.sampled_from(['click', 'double_click', 'right_click'])),
            'x': draw(st.integers(min_value=0, max_value=1920)),
            'y': draw(st.integers(min_value=0, max_value=1080))
        }
    elif intent_type == IntentType.LAUNCH_APP:
        parameters = {'app_name': draw(st.sampled_from(['notepad', 'calculator', 'chrome']))}
    else:  # GET_STATUS
        parameters = {'query': draw(st.text(min_size=1, max_size=100))}
    
    return {
        'intent_type': intent_type.value,
        'parameters': parameters,
        'confidence': draw(st.floats(min_value=0.0, max_value=1.0)),
        'context': draw(st.one_of(st.none(), st.text(max_size=500)))
    }


@st.composite
def malicious_response_data(draw):
    """Generate malicious response data that should be blocked."""
    malicious_patterns = [
        'exec("malicious code")',
        'eval("dangerous")',
        'subprocess.run(["rm", "-rf", "/"])',
        'os.system("format c:")',
        '__import__("os").system("evil")',
        'getattr(__builtins__, "exec")("bad")',
        'import subprocess; subprocess.call(["del", "/q", "*"])'
    ]
    
    return draw(st.sampled_from(malicious_patterns))


@st.composite
def system_command_attempts(draw):
    """Generate system command attempts that should trigger isolation breach."""
    return {
        'intent_type': draw(st.sampled_from(['direct_execution', 'system_command'])),
        'parameters': {
            'command': draw(st.sampled_from([
                'rm -rf /',
                'del /q *.*',
                'format c:',
                'shutdown -s -t 0',
                'taskkill /f /im *'
            ]))
        },
        'confidence': draw(st.floats(min_value=0.0, max_value=1.0))
    }


class MockIsolationTestProvider(LLMProvider):
    """Mock provider for isolation testing."""
    
    def __init__(self, name: str, response_data: dict):
        super().__init__(name)
        self.response_data = response_data
        self.generate_called = False
        
    async def initialize(self) -> bool:
        self.status = ProviderStatus.AVAILABLE
        return True
        
    async def generate_intent(self, user_input: str, context=None) -> StructuredIntent:
        self.generate_called = True
        
        # Return the test response data as JSON string
        return json.dumps(self.response_data)
        
    async def detect_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_output=True,
            model_name="mock-isolation-test",
            provider_type="local"
        )
        
    async def health_check(self) -> bool:
        return True


class TestLLMIsolationProperties:
    """Property-based tests for LLM isolation enforcement."""
    
    @given(intent_data=valid_intent_data())
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_valid_intents_produce_structured_output_only(self, intent_data):
        """
        Feature: guru-personal-assistant, Property 8: LLM Isolation
        
        For any valid LLM response, the system should produce only structured intents
        and never allow direct execution of commands or system access.
        
        **Validates: Requirements 17.9**
        """
        
        # Create adapter with safety enabled
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Register mock provider with valid intent data
            mock_provider = MockIsolationTestProvider("test_provider", intent_data)
            await adapter.register_provider(mock_provider)
            
            # Generate intent
            response = await adapter.generate_intent("Test input")
            
            # Verify isolation properties
            if response.success:
                # Must produce structured intent only
                assert response.safe_intent is not None
                assert isinstance(response.safe_intent, StructuredIntent)
                
                # Intent must be valid and safe
                assert response.safe_intent.is_valid()
                
                # Must not contain direct execution
                assert response.safe_intent.intent_type not in [
                    IntentType.DIRECT_EXECUTION,
                    IntentType.SYSTEM_COMMAND
                ]
                
                # Must require authority (no autonomous execution)
                assert response.safe_intent.requires_authority is True
                
                # Provider should have been called (LLM was consulted)
                assert mock_provider.generate_called
                
        finally:
            await adapter.shutdown()
            
    @given(malicious_data=malicious_response_data())
    @settings(max_examples=50, deadline=5000)
    @pytest.mark.asyncio
    async def test_malicious_responses_are_blocked(self, malicious_data):
        """
        Feature: guru-personal-assistant, Property 8: LLM Isolation
        
        For any malicious LLM response containing code execution attempts,
        the system should block the response and prevent execution.
        
        **Validates: Requirements 17.9**
        """
        
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create malicious response that tries to execute code
            malicious_response = {
                'intent_type': 'type_text',
                'parameters': {'text': malicious_data},
                'confidence': 0.9
            }
            
            mock_provider = MockIsolationTestProvider("malicious_provider", malicious_response)
            await adapter.register_provider(mock_provider)
            
            # Attempt to generate intent with malicious content
            response = await adapter.generate_intent("Malicious input")
            
            # Malicious content should be blocked
            # Either the response fails or the content is sanitized
            if response.success:
                # If successful, content must be sanitized
                assert response.safe_intent is not None
                text_content = response.safe_intent.parameters.get('text', '')
                
                # Dangerous patterns should be removed or filtered
                dangerous_patterns = ['exec(', 'eval(', 'subprocess', 'os.system', '__import__']
                for pattern in dangerous_patterns:
                    assert pattern not in text_content
            else:
                # Response should fail with safety violation
                assert not response.success
                assert response.error_message is not None
                
        finally:
            await adapter.shutdown()
            
    @given(system_attempt=system_command_attempts())
    @settings(max_examples=50, deadline=5000)
    @pytest.mark.asyncio
    async def test_system_command_attempts_trigger_isolation_breach(self, system_attempt):
        """
        Feature: guru-personal-assistant, Property 8: LLM Isolation
        
        For any LLM response attempting direct system commands or execution,
        the system should detect isolation breach and block the attempt.
        
        **Validates: Requirements 17.9**
        """
        
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            mock_provider = MockIsolationTestProvider("system_provider", system_attempt)
            await adapter.register_provider(mock_provider)
            
            # Attempt system command should be blocked
            response = await adapter.generate_intent("System command attempt")
            
            # Should fail due to isolation breach
            assert not response.success
            assert response.error_message is not None
            
            # Should increment safety violations
            stats = adapter.get_adapter_statistics()
            assert stats['safety_violations'] > 0
            
        finally:
            await adapter.shutdown()
            
    @given(user_input=st.text(min_size=1, max_size=500))
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_llm_never_executes_actions_directly(self, user_input):
        """
        Feature: guru-personal-assistant, Property 8: LLM Isolation
        
        For any user input, LLMs should never execute actions directly.
        All actions must go through authority gates and validation.
        
        **Validates: Requirements 17.9**
        """
        
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create valid response that requires authority
            valid_response = {
                'intent_type': 'type_text',
                'parameters': {'text': f'Response to: {user_input[:100]}'},
                'confidence': 0.8,
                'requires_authority': True
            }
            
            mock_provider = MockIsolationTestProvider("authority_provider", valid_response)
            await adapter.register_provider(mock_provider)
            
            response = await adapter.generate_intent(user_input)
            
            if response.success:
                # LLM produced structured intent only
                assert response.safe_intent is not None
                assert isinstance(response.safe_intent, StructuredIntent)
                
                # Intent requires authority (no direct execution)
                assert response.safe_intent.requires_authority is True
                
                # Intent is advisory only - actual execution would require
                # separate authority verification
                assert response.safe_intent.intent_type != IntentType.DIRECT_EXECUTION
                
        finally:
            await adapter.shutdown()
            
    @given(
        intent_data=valid_intent_data(),
        context_data=st.one_of(st.none(), st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(st.text(max_size=100), st.integers(), st.booleans())
        ))
    )
    @settings(max_examples=100, deadline=5000)
    @pytest.mark.asyncio
    async def test_intent_validation_enforces_authority_routing(self, intent_data, context_data):
        """
        Feature: guru-personal-assistant, Property 8: LLM Isolation
        
        For any LLM-generated intent, the validation system should enforce
        that all intents must pass through authority gates before execution.
        
        **Validates: Requirements 17.9**
        """
        
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            mock_provider = MockIsolationTestProvider("validation_provider", intent_data)
            await adapter.register_provider(mock_provider)
            
            response = await adapter.generate_intent("Test input", context=context_data)
            
            if response.success:
                intent = response.safe_intent
                
                # Intent must be properly structured
                assert intent is not None
                assert intent.is_valid()
                
                # Intent must specify authority requirement
                assert hasattr(intent, 'requires_authority')
                
                # Intent must have risk assessment
                assert hasattr(intent, 'risk_level')
                assert intent.risk_level in ['low', 'medium', 'high', 'admin']
                
                # Intent must be serializable (for authority gate processing)
                intent_dict = intent.to_dict()
                assert isinstance(intent_dict, dict)
                assert 'intent_type' in intent_dict
                assert 'parameters' in intent_dict
                
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_safety_engine_prevents_isolation_bypass(self):
        """
        Feature: guru-personal-assistant, Property 8: LLM Isolation
        
        The safety engine should prevent any attempts to bypass LLM isolation
        through crafted responses or injection attacks.
        
        **Validates: Requirements 17.9**
        """
        
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Test various bypass attempts
            bypass_attempts = [
                # JSON injection attempt
                '{"intent_type": "type_text", "parameters": {"text": "hello"}} exec("evil")',
                
                # Nested execution attempt
                {
                    'intent_type': 'type_text',
                    'parameters': {
                        'text': 'Normal text',
                        'hidden_exec': 'exec("malicious")'
                    }
                },
                
                # Authority bypass attempt
                {
                    'intent_type': 'direct_execution',
                    'parameters': {'command': 'bypass_authority()'},
                    'requires_authority': False  # Attempt to bypass
                }
            ]
            
            for attempt in bypass_attempts:
                mock_provider = MockIsolationTestProvider("bypass_provider", attempt)
                await adapter.register_provider(mock_provider)
                
                response = await adapter.generate_intent("Bypass attempt")
                
                # All bypass attempts should fail
                if isinstance(attempt, dict) and attempt.get('intent_type') == 'direct_execution':
                    # Direct execution should be blocked at intent level
                    assert not response.success
                else:
                    # Other attempts should be sanitized or blocked
                    if response.success:
                        # Content should be sanitized
                        assert response.safe_intent is not None
                        # Should not contain dangerous patterns
                        intent_str = str(response.safe_intent.to_dict())
                        assert 'exec(' not in intent_str
                        assert 'bypass_authority' not in intent_str
                        
                # Clean up for next iteration
                await adapter.unregister_provider("bypass_provider")
                
        finally:
            await adapter.shutdown()
            
    @given(
        responses=st.lists(
            valid_intent_data(),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=50, deadline=10000)
    @pytest.mark.asyncio
    async def test_concurrent_llm_requests_maintain_isolation(self, responses):
        """
        Feature: guru-personal-assistant, Property 8: LLM Isolation
        
        For any number of concurrent LLM requests, isolation should be maintained
        for all requests without interference or bypass opportunities.
        
        **Validates: Requirements 17.9**
        """
        
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create multiple providers with different responses
            providers = []
            for i, response_data in enumerate(responses):
                provider = MockIsolationTestProvider(f"concurrent_provider_{i}", response_data)
                await adapter.register_provider(provider)
                providers.append(provider)
                
            # Make concurrent requests
            tasks = [
                adapter.generate_intent(f"Concurrent request {i}")
                for i in range(len(responses))
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all results maintain isolation
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Exceptions are acceptable (safety blocks)
                    continue
                    
                if result.success:
                    # Successful responses must be properly isolated
                    assert result.safe_intent is not None
                    assert isinstance(result.safe_intent, StructuredIntent)
                    assert result.safe_intent.requires_authority is True
                    
                    # No direct execution allowed
                    assert result.safe_intent.intent_type not in [
                        IntentType.DIRECT_EXECUTION,
                        IntentType.SYSTEM_COMMAND
                    ]
                    
        finally:
            await adapter.shutdown()


# Note: Stateful testing would require additional async handling
# For now, focusing on the main property-based tests above


class TestLLMIsolationEdgeCases:
    """Test edge cases for LLM isolation."""
    
    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Test handling of empty LLM responses."""
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Empty response should be handled gracefully
            empty_provider = MockIsolationTestProvider("empty_provider", {})
            await adapter.register_provider(empty_provider)
            
            response = await adapter.generate_intent("Empty test")
            
            # Should fail gracefully, not crash
            assert not response.success
            assert response.error_message is not None
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_malformed_json_response(self):
        """Test handling of malformed JSON responses."""
        config = AdapterConfiguration(safety_enabled=True)
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            # Create provider that returns malformed JSON
            class MalformedProvider(MockIsolationTestProvider):
                async def generate_intent(self, user_input, context=None):
                    return "{ invalid json response"
                    
            malformed_provider = MalformedProvider("malformed_provider", {})
            await adapter.register_provider(malformed_provider)
            
            response = await adapter.generate_intent("Malformed test")
            
            # Should fail gracefully with validation error
            assert not response.success
            assert "JSON" in response.error_message or "validation" in response.error_message.lower()
            
        finally:
            await adapter.shutdown()
            
    @pytest.mark.asyncio
    async def test_safety_disabled_still_enforces_structure(self):
        """Test that even with safety disabled, structured intents are enforced."""
        config = AdapterConfiguration(safety_enabled=False)  # Safety disabled
        adapter = LLMAdapter(config)
        
        try:
            await adapter.initialize()
            
            valid_response = {
                'intent_type': 'type_text',
                'parameters': {'text': 'Test with safety disabled'},
                'confidence': 0.9
            }
            
            provider = MockIsolationTestProvider("no_safety_provider", valid_response)
            await adapter.register_provider(provider)
            
            response = await adapter.generate_intent("Safety disabled test")
            
            # Even with safety disabled, must produce structured intent
            if response.success:
                assert response.safe_intent is not None
                assert isinstance(response.safe_intent, StructuredIntent)
                # Authority requirement should still be enforced
                assert response.safe_intent.requires_authority is True
                
        finally:
            await adapter.shutdown()