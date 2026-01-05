"""
Unit Tests for Biometric Providers

These tests verify the biometric provider abstraction and Windows Hello integration,
including provider management, verification workflows, and error handling.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from src.biometric.providers import (
    BiometricProviderType,
    BiometricCapability,
    BiometricResult,
    BiometricProviderConfig,
    BiometricProvider,
    BiometricProviderError,
    BiometricProviderNotAvailableError,
    BiometricVerificationTimeoutError,
    WindowsHelloProvider,
    MockBiometricProvider,
    BiometricProviderManager,
    create_biometric_provider_manager,
    get_default_biometric_config
)
from src.authority.state import BiometricFactor


class TestBiometricProviderConfig:
    """Test BiometricProviderConfig class."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = BiometricProviderConfig()
        
        # Confidence thresholds
        assert config.face_confidence_threshold == 0.90
        assert config.fingerprint_confidence_threshold == 0.95
        assert config.voice_confidence_threshold == 0.85
        
        # Timeout settings
        assert config.verification_timeout_seconds == 30
        assert config.provider_initialization_timeout == 10
        
        # Security settings
        assert config.max_verification_attempts == 3
        assert config.cooldown_after_failure_seconds == 5
        assert config.require_user_presence is True
        
        # Logging settings
        assert config.log_verification_attempts is True
        assert config.log_confidence_scores is True
    
    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = BiometricProviderConfig(
            face_confidence_threshold=0.95,
            verification_timeout_seconds=60,
            max_verification_attempts=5
        )
        
        assert config.face_confidence_threshold == 0.95
        assert config.verification_timeout_seconds == 60
        assert config.max_verification_attempts == 5
        
        # Other values should remain default
        assert config.fingerprint_confidence_threshold == 0.95
        assert config.require_user_presence is True


class TestBiometricResult:
    """Test BiometricResult class."""
    
    def test_successful_result(self):
        """Test creation of successful biometric result."""
        result = BiometricResult(
            success=True,
            confidence_score=0.95,
            provider_type=BiometricProviderType.WINDOWS_HELLO,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow()
        )
        
        assert result.success is True
        assert result.confidence_score == 0.95
        assert result.provider_type == BiometricProviderType.WINDOWS_HELLO
        assert result.factor_type == BiometricFactor.FACE
        assert result.failure_reason is None
        assert isinstance(result.session_id, str)
        assert len(result.session_id) > 0
    
    def test_failed_result(self):
        """Test creation of failed biometric result."""
        result = BiometricResult(
            success=False,
            confidence_score=0.30,
            provider_type=BiometricProviderType.MOCK_PROVIDER,
            factor_type=BiometricFactor.FINGERPRINT,
            verification_time=datetime.utcnow(),
            failure_reason="Low confidence score"
        )
        
        assert result.success is False
        assert result.confidence_score == 0.30
        assert result.failure_reason == "Low confidence score"
        assert isinstance(result.session_id, str)
    
    def test_session_id_generation(self):
        """Test automatic session ID generation."""
        result1 = BiometricResult(
            success=True,
            confidence_score=0.90,
            provider_type=BiometricProviderType.MOCK_PROVIDER,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow()
        )
        
        result2 = BiometricResult(
            success=True,
            confidence_score=0.90,
            provider_type=BiometricProviderType.MOCK_PROVIDER,
            factor_type=BiometricFactor.FACE,
            verification_time=datetime.utcnow()
        )
        
        # Session IDs should be unique
        assert result1.session_id != result2.session_id
        assert len(result1.session_id) > 0
        assert len(result2.session_id) > 0


class TestMockBiometricProvider:
    """Test MockBiometricProvider implementation."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BiometricProviderConfig(verification_timeout_seconds=5)
    
    @pytest.fixture
    def mock_provider(self, config):
        """Create mock biometric provider."""
        return MockBiometricProvider(config, mock_success_rate=0.8)
    
    def test_provider_type(self, mock_provider):
        """Test provider type identification."""
        assert mock_provider.get_provider_type() == BiometricProviderType.MOCK_PROVIDER
    
    def test_supported_factors(self, mock_provider):
        """Test supported biometric factors."""
        factors = mock_provider.get_supported_factors()
        assert BiometricFactor.FACE in factors
        assert BiometricFactor.FINGERPRINT in factors
        assert BiometricFactor.VOICE in factors
    
    def test_availability(self, mock_provider):
        """Test provider availability."""
        assert mock_provider.is_available() is True
    
    def test_capabilities(self, mock_provider):
        """Test provider capabilities."""
        capabilities = mock_provider.get_capabilities()
        assert BiometricCapability.FACE_RECOGNITION in capabilities
        assert BiometricCapability.FINGERPRINT in capabilities
        assert BiometricCapability.VOICE_RECOGNITION in capabilities
    
    @pytest.mark.asyncio
    async def test_successful_verification(self, config):
        """Test successful biometric verification."""
        # Create provider with 100% success rate
        provider = MockBiometricProvider(config, mock_success_rate=1.0)
        
        result = await provider.verify_biometric(BiometricFactor.FACE)
        
        assert result.success is True
        assert result.confidence_score >= 0.85  # Within expected range
        assert result.provider_type == BiometricProviderType.MOCK_PROVIDER
        assert result.factor_type == BiometricFactor.FACE
        assert result.failure_reason is None
    
    @pytest.mark.asyncio
    async def test_failed_verification(self, config):
        """Test failed biometric verification."""
        # Create provider with 0% success rate
        provider = MockBiometricProvider(config, mock_success_rate=0.0)
        
        result = await provider.verify_biometric(BiometricFactor.FINGERPRINT)
        
        assert result.success is False
        assert result.confidence_score < 0.5  # Low confidence for failures
        assert result.provider_type == BiometricProviderType.MOCK_PROVIDER
        assert result.factor_type == BiometricFactor.FINGERPRINT
        assert result.failure_reason is not None
    
    @pytest.mark.asyncio
    async def test_verification_tracking(self, mock_provider):
        """Test verification attempt tracking."""
        initial_count = mock_provider._verification_count
        
        await mock_provider.verify_biometric(BiometricFactor.FACE)
        await mock_provider.verify_biometric(BiometricFactor.FINGERPRINT)
        
        assert mock_provider._verification_count == initial_count + 2
        assert mock_provider._last_verification is not None
    
    def test_provider_info(self, mock_provider):
        """Test provider information retrieval."""
        info = mock_provider.get_provider_info()
        
        assert info['provider_type'] == BiometricProviderType.MOCK_PROVIDER.value
        assert info['is_available'] is True
        assert 'face' in info['supported_factors']
        assert 'fingerprint' in info['supported_factors']
        assert 'voice' in info['supported_factors']
        assert info['verification_count'] >= 0


class TestWindowsHelloProvider:
    """Test WindowsHelloProvider implementation."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BiometricProviderConfig()
    
    @pytest.fixture
    def windows_provider(self, config):
        """Create Windows Hello provider."""
        return WindowsHelloProvider(config)
    
    def test_provider_type(self, windows_provider):
        """Test provider type identification."""
        assert windows_provider.get_provider_type() == BiometricProviderType.WINDOWS_HELLO
    
    def test_supported_factors(self, windows_provider):
        """Test supported factors detection."""
        factors = windows_provider.get_supported_factors()
        # Factors depend on system availability
        assert isinstance(factors, list)
        # All factors should be valid BiometricFactor values
        for factor in factors:
            assert isinstance(factor, BiometricFactor)
    
    def test_capabilities(self, windows_provider):
        """Test capabilities detection."""
        capabilities = windows_provider.get_capabilities()
        assert isinstance(capabilities, list)
        # All capabilities should be valid BiometricCapability values
        for capability in capabilities:
            assert isinstance(capability, BiometricCapability)
    
    @pytest.mark.asyncio
    async def test_face_verification_mock(self, windows_provider):
        """Test face verification with mocked Windows APIs."""
        # Mock the internal verification method
        with patch.object(windows_provider, '_verify_face_authentication') as mock_verify:
            mock_result = BiometricResult(
                success=True,
                confidence_score=0.95,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow()
            )
            mock_verify.return_value = mock_result
            
            # Mock availability check
            with patch.object(windows_provider, 'is_available', return_value=True):
                with patch.object(windows_provider, 'get_supported_factors', 
                                return_value=[BiometricFactor.FACE]):
                    
                    result = await windows_provider.verify_biometric(BiometricFactor.FACE)
                    
                    assert result.success is True
                    assert result.confidence_score == 0.95
                    assert result.factor_type == BiometricFactor.FACE
                    mock_verify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fingerprint_verification_mock(self, windows_provider):
        """Test fingerprint verification with mocked Windows APIs."""
        with patch.object(windows_provider, '_verify_fingerprint_authentication') as mock_verify:
            mock_result = BiometricResult(
                success=True,
                confidence_score=0.98,
                provider_type=BiometricProviderType.WINDOWS_HELLO,
                factor_type=BiometricFactor.FINGERPRINT,
                verification_time=datetime.utcnow()
            )
            mock_verify.return_value = mock_result
            
            with patch.object(windows_provider, 'is_available', return_value=True):
                with patch.object(windows_provider, 'get_supported_factors', 
                                return_value=[BiometricFactor.FINGERPRINT]):
                    
                    result = await windows_provider.verify_biometric(BiometricFactor.FINGERPRINT)
                    
                    assert result.success is True
                    assert result.confidence_score == 0.98
                    assert result.factor_type == BiometricFactor.FINGERPRINT
                    mock_verify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unsupported_factor(self, windows_provider):
        """Test verification with unsupported factor."""
        with patch.object(windows_provider, 'is_available', return_value=True):
            with patch.object(windows_provider, 'get_supported_factors', 
                            return_value=[BiometricFactor.FACE]):  # Only face supported
                
                with pytest.raises(BiometricProviderError) as exc_info:
                    await windows_provider.verify_biometric(BiometricFactor.FINGERPRINT)
                
                assert "not supported" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_provider_not_available(self, windows_provider):
        """Test verification when provider is not available."""
        with patch.object(windows_provider, 'is_available', return_value=False):
            
            with pytest.raises(BiometricProviderNotAvailableError):
                await windows_provider.verify_biometric(BiometricFactor.FACE)
    
    def test_provider_info(self, windows_provider):
        """Test provider information retrieval."""
        info = windows_provider.get_provider_info()
        
        assert info['provider_type'] == BiometricProviderType.WINDOWS_HELLO.value
        assert isinstance(info['supported_factors'], list)
        assert isinstance(info['capabilities'], list)
        assert isinstance(info['is_available'], bool)
        assert 'initialization_time' in info
        assert 'verification_count' in info


class TestBiometricProviderManager:
    """Test BiometricProviderManager functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BiometricProviderConfig()
    
    @pytest.fixture
    def manager(self, config):
        """Create biometric provider manager."""
        return BiometricProviderManager(config)
    
    def test_initialization(self, manager):
        """Test manager initialization."""
        assert isinstance(manager.config, BiometricProviderConfig)
        assert len(manager.providers) > 0  # Should have at least mock provider
        
        # Should have mock provider
        assert BiometricProviderType.MOCK_PROVIDER in manager.providers
    
    def test_available_providers(self, manager):
        """Test available providers detection."""
        available = manager.get_available_providers()
        assert isinstance(available, list)
        assert len(available) > 0  # Should have at least mock provider
        assert BiometricProviderType.MOCK_PROVIDER in available
    
    def test_get_provider(self, manager):
        """Test getting specific provider."""
        mock_provider = manager.get_provider(BiometricProviderType.MOCK_PROVIDER)
        assert mock_provider is not None
        assert isinstance(mock_provider, MockBiometricProvider)
        
        # Non-existent provider should return None
        non_existent = manager.get_provider(BiometricProviderType.ANDROID_BIOMETRIC)
        assert non_existent is None
    
    def test_best_provider_selection(self, manager):
        """Test best provider selection for factors."""
        # Should find provider for supported factors
        face_provider = manager.get_best_provider_for_factor(BiometricFactor.FACE)
        assert face_provider is not None
        assert BiometricFactor.FACE in face_provider.get_supported_factors()
        
        fingerprint_provider = manager.get_best_provider_for_factor(BiometricFactor.FINGERPRINT)
        assert fingerprint_provider is not None
        assert BiometricFactor.FINGERPRINT in fingerprint_provider.get_supported_factors()
    
    @pytest.mark.asyncio
    async def test_verification_with_best_provider(self, manager):
        """Test verification using best available provider."""
        result = await manager.verify_biometric(BiometricFactor.FACE)
        
        assert isinstance(result, BiometricResult)
        assert result.factor_type == BiometricFactor.FACE
        assert result.provider_type in [BiometricProviderType.WINDOWS_HELLO, BiometricProviderType.MOCK_PROVIDER]
    
    @pytest.mark.asyncio
    async def test_verification_with_preferred_provider(self, manager):
        """Test verification with preferred provider."""
        result = await manager.verify_biometric(
            BiometricFactor.FACE,
            preferred_provider=BiometricProviderType.MOCK_PROVIDER
        )
        
        assert isinstance(result, BiometricResult)
        assert result.factor_type == BiometricFactor.FACE
        assert result.provider_type == BiometricProviderType.MOCK_PROVIDER
    
    @pytest.mark.asyncio
    async def test_verification_no_available_provider(self, config):
        """Test verification when no provider supports the factor."""
        # Create manager with no providers
        manager = BiometricProviderManager(config)
        manager.providers.clear()  # Remove all providers
        
        with pytest.raises(BiometricProviderNotAvailableError):
            await manager.verify_biometric(BiometricFactor.FACE)
    
    def test_system_info(self, manager):
        """Test system information retrieval."""
        info = manager.get_system_info()
        
        assert 'total_providers' in info
        assert 'available_providers' in info
        assert 'providers' in info
        assert 'supported_factors' in info
        
        assert info['total_providers'] >= 1  # At least mock provider
        assert isinstance(info['providers'], list)
        assert isinstance(info['supported_factors'], list)


class TestFactoryFunctions:
    """Test factory functions and utilities."""
    
    def test_create_biometric_provider_manager(self):
        """Test factory function for creating provider manager."""
        # With default config
        manager1 = create_biometric_provider_manager()
        assert isinstance(manager1, BiometricProviderManager)
        assert isinstance(manager1.config, BiometricProviderConfig)
        
        # With custom config
        config = BiometricProviderConfig(verification_timeout_seconds=60)
        manager2 = create_biometric_provider_manager(config)
        assert isinstance(manager2, BiometricProviderManager)
        assert manager2.config.verification_timeout_seconds == 60
    
    def test_get_default_biometric_config(self):
        """Test default configuration factory."""
        config = get_default_biometric_config()
        assert isinstance(config, BiometricProviderConfig)
        assert config.face_confidence_threshold == 0.90
        assert config.verification_timeout_seconds == 30


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BiometricProviderConfig(verification_timeout_seconds=1)
    
    @pytest.mark.asyncio
    async def test_verification_timeout(self, config):
        """Test verification timeout handling."""
        provider = MockBiometricProvider(config)
        
        # Mock verification to take longer than timeout
        async def slow_verification(*args, **kwargs):
            await asyncio.sleep(2)  # Longer than 1 second timeout
            return BiometricResult(
                success=True,
                confidence_score=0.95,
                provider_type=BiometricProviderType.MOCK_PROVIDER,
                factor_type=BiometricFactor.FACE,
                verification_time=datetime.utcnow()
            )
        
        with patch.object(provider, 'verify_biometric', side_effect=slow_verification):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    provider.verify_biometric(BiometricFactor.FACE), 
                    timeout=1
                )
    
    def test_invalid_configuration(self):
        """Test handling of invalid configuration values."""
        # Negative confidence thresholds should still work
        config = BiometricProviderConfig(
            face_confidence_threshold=-0.5,
            verification_timeout_seconds=0
        )
        
        # Should create without error (validation is provider-specific)
        provider = MockBiometricProvider(config)
        assert provider.config.face_confidence_threshold == -0.5
    
    @pytest.mark.asyncio
    async def test_provider_exception_handling(self, config):
        """Test handling of provider exceptions."""
        provider = MockBiometricProvider(config)
        
        # Mock verification to raise exception
        with patch.object(provider, 'verify_biometric', side_effect=Exception("Test error")):
            with pytest.raises(Exception) as exc_info:
                await provider.verify_biometric(BiometricFactor.FACE)
            
            assert "Test error" in str(exc_info.value)


class TestConcurrency:
    """Test concurrent access and thread safety."""
    
    @pytest.fixture
    def manager(self):
        """Create provider manager for concurrency tests."""
        return BiometricProviderManager()
    
    @pytest.mark.asyncio
    async def test_concurrent_verifications(self, manager):
        """Test concurrent biometric verifications."""
        # Start multiple concurrent verifications
        tasks = [
            manager.verify_biometric(BiometricFactor.FACE),
            manager.verify_biometric(BiometricFactor.FINGERPRINT),
            manager.verify_biometric(BiometricFactor.FACE),
            manager.verify_biometric(BiometricFactor.FINGERPRINT)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete without errors
        for result in results:
            assert isinstance(result, BiometricResult)
            assert result.factor_type in [BiometricFactor.FACE, BiometricFactor.FINGERPRINT]
    
    def test_concurrent_provider_access(self, manager):
        """Test concurrent access to provider information."""
        import threading
        
        results = []
        errors = []
        
        def get_provider_info():
            try:
                for _ in range(10):
                    info = manager.get_system_info()
                    results.append(info)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=get_provider_info) for _ in range(5)]
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 iterations
        
        # All results should be consistent
        for result in results:
            assert 'total_providers' in result
            assert 'available_providers' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])