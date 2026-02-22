"""
Tests for API authentication.

This module tests JWT authentication and rate limiting.
"""

import pytest
import time
from fastapi import HTTPException

from Agent_Guru.reasoning.api.auth import (
    create_access_token,
    verify_token,
    RateLimiter,
    get_rate_limiter,
)


class TestJWTTokens:
    """Tests for JWT token creation and verification."""
    
    def test_create_token(self):
        """Test token creation."""
        token = create_access_token("user_123")
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_valid_token(self):
        """Test verifying a valid token."""
        token = create_access_token("user_123")
        token_data = verify_token(token)
        
        assert token_data.user_id == "user_123"
        assert token_data.exp > 0
        assert token_data.iat > 0
    
    def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            verify_token("invalid_token")
        
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail
    
    def test_token_contains_user_id(self):
        """Test that token contains user ID."""
        user_id = "test_user_456"
        token = create_access_token(user_id)
        token_data = verify_token(token)
        
        assert token_data.user_id == user_id


class TestRateLimiter:
    """Tests for rate limiter."""
    
    def test_within_limit(self):
        """Test requests within rate limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # Make 10 requests (within limit)
        for i in range(10):
            assert limiter.check_rate_limit("user_123") is True
    
    def test_exceeds_limit(self):
        """Test requests exceeding rate limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # Make 5 requests (within limit)
        for i in range(5):
            assert limiter.check_rate_limit("user_123") is True
        
        # 6th request should be blocked
        assert limiter.check_rate_limit("user_123") is False
    
    def test_different_users_independent(self):
        """Test that different users have independent limits."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # User 1 makes 5 requests
        for i in range(5):
            assert limiter.check_rate_limit("user_1") is True
        
        # User 2 should still be able to make requests
        assert limiter.check_rate_limit("user_2") is True
    
    def test_window_reset(self):
        """Test that rate limit resets after window."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        
        # Make 2 requests
        assert limiter.check_rate_limit("user_123") is True
        assert limiter.check_rate_limit("user_123") is True
        
        # 3rd request should be blocked
        assert limiter.check_rate_limit("user_123") is False
        
        # Wait for window to reset
        time.sleep(1.1)
        
        # Should be able to make requests again
        assert limiter.check_rate_limit("user_123") is True
    
    def test_get_remaining_requests(self):
        """Test getting remaining requests."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # Initially should have 10 remaining
        assert limiter.get_remaining_requests("user_123") == 10
        
        # After 3 requests, should have 7 remaining
        for i in range(3):
            limiter.check_rate_limit("user_123")
        
        assert limiter.get_remaining_requests("user_123") == 7
    
    def test_cleanup_old_entries(self):
        """Test cleanup of old entries."""
        limiter = RateLimiter(max_requests=10, window_seconds=1)
        
        # Make requests for multiple users
        limiter.check_rate_limit("user_1")
        limiter.check_rate_limit("user_2")
        limiter.check_rate_limit("user_3")
        
        # Wait for entries to expire
        time.sleep(1.1)
        
        # Trigger cleanup
        limiter._cleanup_old_entries(time.time())
        
        # Old entries should be removed
        assert len(limiter._requests) == 0


class TestGlobalRateLimiter:
    """Tests for global rate limiter instance."""
    
    def test_get_rate_limiter(self):
        """Test getting global rate limiter."""
        limiter = get_rate_limiter()
        
        assert isinstance(limiter, RateLimiter)
        assert limiter.max_requests > 0
        assert limiter.window_seconds > 0
