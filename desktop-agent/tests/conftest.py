"""
Test Configuration for GURU Personal Assistant

This module provides test-specific configurations and fixtures that enable
testing without triggering production security mechanisms like workstation locking.

⚠️  SECURITY WARNING: Test configurations disable critical security features
and must NEVER be used in production environments.
"""

import pytest
from src.authority.state import AuthorityConfiguration


@pytest.fixture
def test_authority_config():
    """
    Test-only authority configuration that disables workstation locking.
    
    ⚠️  SECURITY WARNING: This configuration disables workstation locking which is
    a critical security feature. It exists solely for unit testing purposes.
    
    NEVER use this configuration in production code.
    """
    config = AuthorityConfiguration()
    
    # SECURITY CRITICAL: Enable test mode to disable workstation locking
    config.test_mode_disable_workstation_lock = True
    
    # Reduce timeouts for faster testing
    config.identity_verification_timeout = 5
    config.armed_session_timeout = 30
    config.inactivity_timeout = 10
    config.intrusion_cooldown_seconds = 5
    
    return config


@pytest.fixture
def production_authority_config():
    """
    Production authority configuration with all security features enabled.
    
    This configuration enforces workstation locking and should be used to test
    that the security enforcement is working correctly.
    """
    return AuthorityConfiguration()  # Default production configuration


def create_test_authority_config(**overrides):
    """
    Factory function to create test authority configuration with custom overrides.
    
    ⚠️  SECURITY WARNING: This always enables test mode to disable workstation locking.
    
    Args:
        **overrides: Configuration parameters to override
        
    Returns:
        AuthorityConfiguration with test mode enabled and custom overrides
    """
    config = AuthorityConfiguration()
    
    # SECURITY CRITICAL: Always enable test mode
    config.test_mode_disable_workstation_lock = True
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            raise ValueError(f"Invalid configuration parameter: {key}")
    
    return config