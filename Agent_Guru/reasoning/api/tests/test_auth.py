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
        
        assert isinstance(token, str)  # nosec B101
        assert len(token) > 0  # nosec B101
    
    def test_verify_valid_token(self):
        """Test verifying a valid token."""
        token = create_access_token("user_123")
        token_data = verify_token(token)
        
        assert token_data.user_id == "user_123"  # nosec B101
        assert token_data.exp > 0  # nosec B101
        assert token_data.iat > 0  # nosec B101
    
    def test_verify_invalid_token(self):
        """Test verifying an invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            verify_token("invalid_token")
        
        assert exc_info.value.status_code == 401  # nosec B101
        assert "Invalid token" in exc_info.value.detail  # nosec B101
    
    def test_token_contains_user_id(self):
        """Test that token contains user ID."""
        user_id = "test_user_456"
        token = create_access_token(user_id)
        token_data = verify_token(token)
        
        assert token_data.user_id == user_id  # nosec B101


class TestJWTTokenRejection:
    """Every way a token can be rejected must produce 401, never 500.

    verify_token() used to handle only ExpiredSignatureError. Every other
    failure - a forged signature above all - escaped the function raw, which
    FastAPI turns into a 500 Internal Server Error rather than an
    authentication failure. These tests pin each rejection path.
    """

    @staticmethod
    def _assert_rejected(token):
        with pytest.raises(HTTPException) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401  # nosec B101
        return exc_info.value

    def test_forged_signature_is_rejected(self):
        """A token signed with the WRONG key must not authenticate anyone."""
        import jwt as pyjwt

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM

        forged = pyjwt.encode(
            {
                "user_id": "attacker",
                "role": "admin",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            "not-the-server-secret",
            algorithm=JWT_ALGORITHM,
        )

        self._assert_rejected(forged)

    def test_unsigned_alg_none_token_is_rejected(self):
        """The classic algorithm-confusion attack must not be accepted."""
        import jwt as pyjwt

        unsigned = pyjwt.encode(
            {
                "user_id": "attacker",
                "role": "admin",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            key="",
            algorithm="none",
        )

        self._assert_rejected(unsigned)

    def test_tampered_payload_is_rejected(self):
        """Flipping a byte of a genuine token must invalidate it."""
        token = create_access_token("user_123")
        header, payload, signature = token.split(".")
        # Corrupt the payload segment while keeping the structure valid.
        tampered = f"{header}.{payload[:-2]}XY.{signature}"

        self._assert_rejected(tampered)

    @pytest.mark.parametrize(
        "token",
        ["", "   ", "not.a.jwt", "onlyonesegment", "a.b", "a.b.c.d"],
    )
    def test_malformed_tokens_are_rejected(self, token):
        self._assert_rejected(token)

    def test_unknown_role_claim_is_rejected(self):
        """A correctly signed token whose role this build cannot parse."""
        import jwt as pyjwt

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM, JWT_SECRET

        token = pyjwt.encode(
            {
                "user_id": "user_123",
                "role": "superuser-that-does-not-exist",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )

        self._assert_rejected(token)

    def test_missing_claims_are_rejected(self):
        """A correctly signed token that is missing required claims."""
        import jwt as pyjwt

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM, JWT_SECRET

        token = pyjwt.encode({"user_id": "user_123"}, JWT_SECRET, algorithm=JWT_ALGORITHM)

        self._assert_rejected(token)

    def test_rejection_detail_does_not_leak_the_reason(self):
        """Saying WHICH check failed is an oracle for refining a forgery."""
        import jwt as pyjwt

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM

        forged = pyjwt.encode(
            {
                "user_id": "attacker",
                "role": "admin",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            "not-the-server-secret",
            algorithm=JWT_ALGORITHM,
        )

        forged_detail = self._assert_rejected(forged).detail
        malformed_detail = self._assert_rejected("not.a.jwt").detail

        assert forged_detail == malformed_detail == "Invalid token"  # nosec B101

    def test_expired_token_is_still_distinguished(self):
        """Expiry is safe to report - it tells an attacker nothing useful."""
        import jwt as pyjwt

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM, JWT_SECRET

        expired = pyjwt.encode(
            {
                "user_id": "user_123",
                "role": "user",
                "exp": int(time.time()) - 10,
                "iat": int(time.time()) - 3600,
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )

        assert "expired" in self._assert_rejected(expired).detail.lower()  # nosec B101


class TestRateLimiter:
    """Tests for rate limiter."""
    
    def test_within_limit(self):
        """Test requests within rate limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # Make 10 requests (within limit)
        for i in range(10):
            assert limiter.check_rate_limit("user_123") is True  # nosec B101
    
    def test_exceeds_limit(self):
        """Test requests exceeding rate limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # Make 5 requests (within limit)
        for i in range(5):
            assert limiter.check_rate_limit("user_123") is True  # nosec B101
        
        # 6th request should be blocked
        assert limiter.check_rate_limit("user_123") is False  # nosec B101
    
    def test_different_users_independent(self):
        """Test that different users have independent limits."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # User 1 makes 5 requests
        for i in range(5):
            assert limiter.check_rate_limit("user_1") is True  # nosec B101
        
        # User 2 should still be able to make requests
        assert limiter.check_rate_limit("user_2") is True  # nosec B101
    
    def test_window_reset(self):
        """Test that rate limit resets after window."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        
        # Make 2 requests
        assert limiter.check_rate_limit("user_123") is True  # nosec B101
        assert limiter.check_rate_limit("user_123") is True  # nosec B101
        
        # 3rd request should be blocked
        assert limiter.check_rate_limit("user_123") is False  # nosec B101
        
        # Wait for window to reset
        time.sleep(1.1)
        
        # Should be able to make requests again
        assert limiter.check_rate_limit("user_123") is True  # nosec B101
    
    def test_get_remaining_requests(self):
        """Test getting remaining requests."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # Initially should have 10 remaining
        assert limiter.get_remaining_requests("user_123") == 10  # nosec B101
        
        # After 3 requests, should have 7 remaining
        for i in range(3):
            limiter.check_rate_limit("user_123")
        
        assert limiter.get_remaining_requests("user_123") == 7  # nosec B101
    
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
        assert len(limiter._requests) == 0  # nosec B101


class TestGlobalRateLimiter:
    """Tests for global rate limiter instance."""
    
    def test_get_rate_limiter(self):
        """Test getting global rate limiter."""
        limiter = get_rate_limiter()
        
        assert isinstance(limiter, RateLimiter)  # nosec B101
        assert limiter.max_requests > 0  # nosec B101
        assert limiter.window_seconds > 0  # nosec B101
