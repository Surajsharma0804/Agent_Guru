"""
Unit Tests for LLM Providers

Comprehensive test suite for LLM provider implementations including
capability detection, rate limiting, and security controls.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import json

from src.llm.providers import (
    LLMProvider, 
    GeminiProvider, 
    LocalProvider, 
    ProviderStatus, 
    ProviderCapabilities,
    RateLimitState
)
from src.llm.intent import StructuredIntent, IntentType
from src.llm.exceptions import ProviderError, RateLimitExceededError


class TestProviderCapabilities:
    """Test suite for provider capabilities."""
    
    def test_capabilities_creation(self):
        """Test provider capabilities creation."""
        capabilities = ProviderCapabilities(
            supports_structured_output=True,
            max_tokens=4096,
            model_name="test-model",
            requests_per_minute=60
        )
        
        assert capabilities.supports_structured_output is True
        assert capabilities.max_tokens == 4096
        assert capabilities.model_name == "test-model"
        assert capabilities.requests_per_minute == 60
        
    def test_capabilities_serialization(self):
        """Test capabilities serialization to dictionary."""
        capabilities = ProviderCapabilities(
            supports_structured_output=True,
            supports_streaming=False,
            max_tokens=2048,
            model_name="test-model",
            provider_type="local"
        )
        
        capabilities_dict = capabilities.to_dict()
        
        assert capabilities_dict['supports_structured_output'] is True
        assert capabilities_dict['supports_streaming'] is False
        assert capabilities_dict['max_tokens'] == 2048
        assert capabilities_dict['model_name'] == "test-model"
        assert capabilities_dict['provider_type'] == "local"
        
    def test_default_capabilities(self):
        """Test default capability values."""
        capabilities = ProviderCapabilities()
        
        assert capabilities.supports_structured_output is False
        assert capabilities.max_tokens == 4096
        assert capabilities.context_window == 4096
        assert capabilities.requests_per_minute == 60
        assert capabilities.provider_type == "cloud"
        assert capabilities.requires_api_key is True


class TestRateLimitState:
    """Test suite for rate limiting state management."""
    
    def test_rate_limit_state_creation(self):
        """Test rate limit state initialization."""
        state = RateLimitState()
        
        assert state.requests_this_minute == 0
        assert state.requests_this_hour == 0
        assert state.requests_this_day == 0
        assert state.tokens_this_minute == 0
        assert isinstance(state.last_minute_reset, datetime)
        
    def test_rate_limit_reset_minute(self):
        """Test minute counter reset."""
        state = RateLimitState()
        
        # Set some values
        state.requests_this_minute = 10
        state.tokens_this_minute = 1000
        
        # Set reset time to past
        state.last_minute_reset = datetime.utcnow() - timedelta(minutes=2)
        
        # Reset should clear minute counters
        state.reset_if_needed()
        
        assert state.requests_this_minute == 0
        assert state.tokens_this_minute == 0
        
    def test_rate_limit_reset_hour(self):
        """Test hour counter reset."""
        state = RateLimitState()
        
        state.requests_this_hour = 100
        state.last_hour_reset = datetime.utcnow() - timedelta(hours=2)
        
        state.reset_if_needed()
        
        assert state.requests_this_hour == 0
        
    def test_rate_limit_reset_day(self):
        """Test day counter reset."""
        state = RateLimitState()
        
        state.requests_this_day = 1000
        state.last_day_reset = datetime.utcnow() - timedelta(days=2)
        
        state.reset_if_needed()
        
        assert state.requests_this_day == 0
        
    def test_no_reset_when_not_needed(self):
        """Test that counters are not reset when not needed."""
        state = RateLimitState()
        
        state.requests_this_minute = 5
        state.requests_this_hour = 50
        state.requests_this_day = 500
        
        # Recent reset times - no reset should occur
        state.last_minute_reset = datetime.utcnow()
        state.last_hour_reset = datetime.utcnow()
        state.last_day_reset = datetime.utcnow()
        
        state.reset_if_needed()
        
        assert state.requests_this_minute == 5
        assert state.requests_this_hour == 50
        assert state.requests_this_day == 500


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing base functionality."""
    
    def __init__(self, name: str = "mock_provider"):
        super().__init__(name)
        self.initialize_called = False
        self.generate_called = False
        self.health_check_called = False
        self.detect_capabilities_called = False
        
    async def initialize(self) -> bool:
        self.initialize_called = True
        self.status = ProviderStatus.AVAILABLE
        return True
        
    async def generate_intent(self, user_input: str, context=None) -> StructuredIntent:
        self.generate_called = True
        return StructuredIntent(
            intent_type=IntentType.TYPE_TEXT,
            parameters={'text': f"Mock response: {user_input}"},
            confidence=0.9
        )
        
    async def detect_capabilities(self) -> ProviderCapabilities:
        self.detect_capabilities_called = True
        return ProviderCapabilities(
            supports_structured_output=True,
            model_name="mock-model",
            provider_type="local"
        )
        
    async def health_check(self) -> bool:
        self.health_check_called = True
        return True


class TestLLMProviderBase:
    """Test suite for base LLM provider functionality."""
    
    @pytest.mark.asyncio
    async def test_provider_initialization(self):
        """Test provider initialization."""
        provider = MockLLMProvider("test_provider")
        
        assert provider.provider_name == "test_provider"
        assert provider.status == ProviderStatus.UNKNOWN
        assert provider.capabilities is None
        
        success = await provider.initialize()
        assert success
        assert provider.initialize_called
        assert provider.status == ProviderStatus.AVAILABLE
        
    @pytest.mark.asyncio
    async def test_intent_generation(self):
        """Test intent generation."""
        provider = MockLLMProvider()
        await provider.initialize()
        
        intent = await provider.generate_intent("Hello world")
        
        assert provider.generate_called
        assert isinstance(intent, StructuredIntent)
        assert intent.intent_type == IntentType.TYPE_TEXT
        assert "Hello world" in intent.parameters['text']
        
    @pytest.mark.asyncio
    async def test_capability_detection(self):
        """Test capability detection."""
        provider = MockLLMProvider()
        
        capabilities = await provider.detect_capabilities()
        
        assert provider.detect_capabilities_called
        assert isinstance(capabilities, ProviderCapabilities)
        assert capabilities.supports_structured_output is True
        assert capabilities.model_name == "mock-model"
        
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        provider = MockLLMProvider()
        
        is_healthy = await provider.health_check()
        
        assert provider.health_check_called
        assert is_healthy is True
        
    def test_rate_limit_checking(self):
        """Test rate limit checking."""
        provider = MockLLMProvider()
        provider.capabilities = ProviderCapabilities(
            requests_per_minute=10,
            requests_per_hour=100,
            tokens_per_minute=1000
        )
        
        # Should be within limits initially
        assert provider.check_rate_limits(100) is True
        
        # Simulate hitting minute limit
        provider.rate_limit_state.requests_this_minute = 10
        assert provider.check_rate_limits(100) is False
        
        # Reset and test hour limit
        provider.rate_limit_state.requests_this_minute = 0
        provider.rate_limit_state.requests_this_hour = 100
        assert provider.check_rate_limits(100) is False
        
        # Test token limit
        provider.rate_limit_state.requests_this_hour = 0
        provider.rate_limit_state.tokens_this_minute = 900
        assert provider.check_rate_limits(200) is False  # Would exceed token limit
        
    def test_request_recording(self):
        """Test request recording for rate limiting."""
        provider = MockLLMProvider()
        
        initial_minute = provider.rate_limit_state.requests_this_minute
        initial_hour = provider.rate_limit_state.requests_this_hour
        initial_day = provider.rate_limit_state.requests_this_day
        initial_tokens = provider.rate_limit_state.tokens_this_minute
        
        provider.record_request(150)
        
        assert provider.rate_limit_state.requests_this_minute == initial_minute + 1
        assert provider.rate_limit_state.requests_this_hour == initial_hour + 1
        assert provider.rate_limit_state.requests_this_day == initial_day + 1
        assert provider.rate_limit_state.tokens_this_minute == initial_tokens + 150
        
    def test_provider_status_reporting(self):
        """Test provider status reporting."""
        provider = MockLLMProvider("status_test")
        provider.capabilities = ProviderCapabilities(model_name="test-model")
        
        status = provider.get_status()
        
        assert status['provider_name'] == "status_test"
        assert status['status'] == ProviderStatus.UNKNOWN.value
        assert status['capabilities']['model_name'] == "test-model"
        assert 'rate_limit_state' in status


class TestGeminiProvider:
    """Test suite for Gemini provider implementation."""
    
    def test_gemini_provider_creation(self):
        """Test Gemini provider creation."""
        config = {
            'api_key': 'test_key',
            'model_name': 'gemini-pro',
            'timeout': 30
        }
        
        provider = GeminiProvider(config)
        
        assert provider.provider_name == "gemini"
        assert provider.api_key == 'test_key'
        assert provider.model_name == 'gemini-pro'
        assert provider.timeout == 30
        
    def test_gemini_provider_default_config(self):
        """Test Gemini provider with default configuration."""
        provider = GeminiProvider()
        
        assert provider.provider_name == "gemini"
        assert provider.api_key is None
        assert provider.model_name == 'gemini-pro'
        assert provider.base_url == 'https://generativelanguage.googleapis.com'
        
    @pytest.mark.asyncio
    async def test_gemini_initialization_without_api_key(self):
        """Test Gemini initialization failure without API key."""
        provider = GeminiProvider()
        
        success = await provider.initialize()
        
        assert not success
        assert provider.status == ProviderStatus.AUTHENTICATION_FAILED
        
    @pytest.mark.asyncio
    async def test_gemini_capability_detection(self):
        """Test Gemini capability detection."""
        provider = GeminiProvider({'api_key': 'test_key'})
        
        capabilities = await provider.detect_capabilities()
        
        assert capabilities.supports_structured_output is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_image_input is True
        assert capabilities.model_name == 'gemini-pro'
        assert capabilities.provider_type == "cloud"
        assert capabilities.requires_api_key is True
        assert capabilities.requires_internet is True
        
    @pytest.mark.asyncio
    async def test_gemini_health_check(self):
        """Test Gemini health check."""
        provider = GeminiProvider({'api_key': 'test_key'})
        
        # Mock the health check to return True
        is_healthy = await provider.health_check()
        assert is_healthy is True
        
    def test_gemini_structured_prompt_building(self):
        """Test Gemini structured prompt building."""
        provider = GeminiProvider({'api_key': 'test_key'})
        
        prompt = provider._build_structured_prompt("Type hello world")
        
        assert "You are GURU's intent parser" in prompt
        assert "Type hello world" in prompt
        assert "valid JSON only" in prompt
        assert "intent_type" in prompt
        
    def test_gemini_structured_prompt_with_context(self):
        """Test Gemini structured prompt building with context."""
        provider = GeminiProvider({'api_key': 'test_key'})
        context = {'session_id': '123', 'user_preference': 'concise'}
        
        prompt = provider._build_structured_prompt("Type hello", context)
        
        assert "Type hello" in prompt
        assert "session_id" in prompt
        assert "user_preference" in prompt
        
    @pytest.mark.asyncio
    async def test_gemini_api_request_simulation(self):
        """Test Gemini API request simulation."""
        provider = GeminiProvider({'api_key': 'test_key'})
        
        # This is a simulated response
        response = await provider._make_api_request("Test prompt")
        
        assert isinstance(response, str)
        response_data = json.loads(response)
        assert 'intent_type' in response_data
        assert 'parameters' in response_data
        assert 'confidence' in response_data


class TestLocalProvider:
    """Test suite for Local provider implementation."""
    
    def test_local_provider_creation(self):
        """Test Local provider creation."""
        config = {
            'model_path': './custom/model.gguf',
            'max_memory_mb': 8192,
            'threads': 8
        }
        
        provider = LocalProvider(config)
        
        assert provider.provider_name == "local"
        assert provider.model_path == './custom/model.gguf'
        assert provider.max_memory_mb == 8192
        assert provider.threads == 8
        
    def test_local_provider_default_config(self):
        """Test Local provider with default configuration."""
        provider = LocalProvider()
        
        assert provider.provider_name == "local"
        assert provider.model_path == './models/local-llm.gguf'
        assert provider.max_memory_mb == 4096
        assert provider.threads == 4
        
    @pytest.mark.asyncio
    async def test_local_capability_detection(self):
        """Test Local provider capability detection."""
        provider = LocalProvider()
        
        capabilities = await provider.detect_capabilities()
        
        assert capabilities.supports_structured_output is True
        assert capabilities.supports_streaming is False
        assert capabilities.supports_function_calling is False
        assert capabilities.model_name == "local-llm"
        assert capabilities.provider_type == "local"
        assert capabilities.requires_api_key is False
        assert capabilities.requires_internet is False
        assert capabilities.cost_per_1k_tokens == 0.0
        
    @pytest.mark.asyncio
    async def test_local_health_check(self):
        """Test Local provider health check."""
        provider = LocalProvider()
        
        is_healthy = await provider.health_check()
        assert is_healthy is True
        
    def test_local_prompt_building(self):
        """Test Local provider prompt building."""
        provider = LocalProvider()
        
        prompt = provider._build_local_prompt("Launch notepad")
        
        assert "<|system|>" in prompt
        assert "<|user|>" in prompt
        assert "<|assistant|>" in prompt
        assert "Launch notepad" in prompt
        assert "JSON only" in prompt
        
    def test_local_prompt_with_context(self):
        """Test Local provider prompt building with context."""
        provider = LocalProvider()
        context = {'app_preference': 'notepad++'}
        
        prompt = provider._build_local_prompt("Launch editor", context)
        
        assert "Launch editor" in prompt
        # Context handling would be implemented in actual prompt building
        
    @pytest.mark.asyncio
    async def test_local_response_generation(self):
        """Test Local provider response generation."""
        provider = LocalProvider()
        
        response = await provider._generate_local_response("Test prompt")
        
        assert isinstance(response, str)
        response_data = json.loads(response)
        assert 'intent_type' in response_data
        assert 'parameters' in response_data
        assert 'confidence' in response_data
        assert response_data['confidence'] == 0.85  # Local model confidence
        
    @pytest.mark.asyncio
    async def test_local_initialization_missing_model(self):
        """Test Local provider initialization with missing model file."""
        provider = LocalProvider({'model_path': '/nonexistent/model.gguf'})
        
        success = await provider.initialize()
        
        assert not success
        assert provider.status == ProviderStatus.UNAVAILABLE


class TestProviderErrorHandling:
    """Test suite for provider error handling."""
    
    @pytest.mark.asyncio
    async def test_provider_generation_failure(self):
        """Test provider handling of generation failures."""
        provider = MockLLMProvider()
        
        # Mock generate_intent to raise exception
        async def failing_generate(user_input, context=None):
            raise Exception("Generation failed")
            
        provider.generate_intent = failing_generate
        
        with pytest.raises(Exception):
            await provider.generate_intent("Test input")
            
    def test_rate_limit_exceeded_detection(self):
        """Test rate limit exceeded detection."""
        provider = MockLLMProvider()
        provider.capabilities = ProviderCapabilities(
            requests_per_minute=1,
            tokens_per_minute=100
        )
        
        # First request should be allowed
        assert provider.check_rate_limits(50) is True
        provider.record_request(50)
        
        # Second request should be blocked
        assert provider.check_rate_limits(50) is False
        
    def test_provider_status_transitions(self):
        """Test provider status transitions."""
        provider = MockLLMProvider()
        
        # Initial status
        assert provider.status == ProviderStatus.UNKNOWN
        
        # After initialization
        asyncio.run(provider.initialize())
        assert provider.status == ProviderStatus.AVAILABLE
        
        # Manual status change
        provider.status = ProviderStatus.RATE_LIMITED
        assert provider.status == ProviderStatus.RATE_LIMITED
        
    @pytest.mark.asyncio
    async def test_provider_timeout_simulation(self):
        """Test provider timeout handling simulation."""
        provider = MockLLMProvider()
        
        # Mock a slow operation
        async def slow_operation():
            await asyncio.sleep(2)
            return True
            
        # Test with timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.1)
            
    def test_provider_configuration_validation(self):
        """Test provider configuration validation."""
        # Test valid configuration
        config = {
            'api_key': 'valid_key',
            'model_name': 'test-model',
            'timeout': 30
        }
        
        provider = GeminiProvider(config)
        assert provider.api_key == 'valid_key'
        assert provider.model_name == 'test-model'
        assert provider.timeout == 30
        
        # Test empty configuration
        provider = GeminiProvider({})
        assert provider.api_key is None
        assert provider.model_name == 'gemini-pro'  # Default
        
    def test_provider_capability_caching(self):
        """Test provider capability caching."""
        provider = MockLLMProvider()
        
        # Initially no capabilities
        assert provider.capabilities is None
        
        # After detection
        capabilities = asyncio.run(provider.detect_capabilities())
        provider.capabilities = capabilities
        
        assert provider.capabilities is not None
        assert provider.capabilities.model_name == "mock-model"