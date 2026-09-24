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

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM, get_jwt_secret

        token = pyjwt.encode(
            {
                "user_id": "user_123",
                "role": "superuser-that-does-not-exist",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            get_jwt_secret(),
            algorithm=JWT_ALGORITHM,
        )

        self._assert_rejected(token)

    def test_missing_claims_are_rejected(self):
        """A correctly signed token that is missing required claims."""
        import jwt as pyjwt

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM, get_jwt_secret

        token = pyjwt.encode(
            {"user_id": "user_123"}, get_jwt_secret(), algorithm=JWT_ALGORITHM,
        )

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

        from Agent_Guru.reasoning.api.auth import JWT_ALGORITHM, get_jwt_secret

        expired = pyjwt.encode(
            {
                "user_id": "user_123",
                "role": "user",
                "exp": int(time.time()) - 10,
                "iat": int(time.time()) - 3600,
            },
            get_jwt_secret(),
            algorithm=JWT_ALGORITHM,
        )

        assert "expired" in self._assert_rejected(expired).detail.lower()  # nosec B101


class TestJWTSecretConfiguration:
    """No JWT_SECRET must mean no authentication, never forgeable authentication.

    auth.py used to fall back to the public string
    "your-secret-key-change-in-production" when JWT_SECRET was unset, so any
    such deployment accepted tokens that anyone could mint for any user id and
    role, and nothing warned. These tests pin the refusal and its message.
    """

    PLACEHOLDER = "your-secret-key-change-in-production"  # nosec B105

    @staticmethod
    def _sign_admin_token(key):
        import jwt as pyjwt

        return pyjwt.encode(
            {
                "user_id": "attacker-chosen-id",
                "role": "admin",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
            },
            key,
            algorithm="HS256",
        )

    def test_unset_secret_does_not_accept_a_placeholder_forgery(self, monkeypatch):
        """The original bypass: no secret set, token signed with the placeholder."""
        monkeypatch.delenv("JWT_SECRET")
        forged = self._sign_admin_token(self.PLACEHOLDER)

        # RuntimeError and not HTTPException: a missing secret is a server
        # misconfiguration and must not be disguised as an ordinary bad token.
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            verify_token(forged)

    def test_unset_secret_refuses_to_sign(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET")

        with pytest.raises(RuntimeError, match="JWT_SECRET") as exc_info:
            create_access_token("user_123")

        # The message must say what to set, not just which variable is missing.
        assert "secrets.token_urlsafe" in str(exc_info.value)  # nosec B101

    def test_error_type_is_the_named_configuration_error(self, monkeypatch):
        from Agent_Guru.reasoning.api.auth import JWTSecretNotConfiguredError

        monkeypatch.delenv("JWT_SECRET")

        with pytest.raises(JWTSecretNotConfiguredError):
            create_access_token("user_123")

    def test_blank_secret_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "   ")

        with pytest.raises(RuntimeError, match="JWT_SECRET is not set"):
            verify_token(self._sign_admin_token("   "))

    def test_public_placeholder_set_explicitly_is_refused(self, monkeypatch):
        """Copying the old default into the environment is the same hole."""
        monkeypatch.setenv("JWT_SECRET", self.PLACEHOLDER)

        with pytest.raises(RuntimeError, match="public placeholder"):
            verify_token(self._sign_admin_token(self.PLACEHOLDER))

    def test_secret_shorter_than_hs256_minimum_is_refused(self, monkeypatch):
        from Agent_Guru.reasoning.api.auth import JWT_MIN_SECRET_BYTES

        monkeypatch.setenv("JWT_SECRET", "k" * (JWT_MIN_SECRET_BYTES - 1))

        with pytest.raises(RuntimeError, match=f"JWT_SECRET is {JWT_MIN_SECRET_BYTES - 1} bytes"):
            create_access_token("user_123")

    def test_secret_at_hs256_minimum_is_accepted(self, monkeypatch):
        from Agent_Guru.reasoning.api.auth import JWT_MIN_SECRET_BYTES

        monkeypatch.setenv("JWT_SECRET", "k" * JWT_MIN_SECRET_BYTES)

        assert verify_token(create_access_token("user_123")).user_id == "user_123"  # nosec B101

    def test_token_signed_with_the_configured_secret_is_accepted(self, jwt_secret):
        token_data = verify_token(self._sign_admin_token(jwt_secret))

        assert token_data.user_id == "attacker-chosen-id"  # nosec B101

    def test_server_refuses_to_start_without_secret(self, monkeypatch):
        """A deployment missing JWT_SECRET must fail at startup, not on first use."""
        from fastapi.testclient import TestClient

        from Agent_Guru.reasoning.api.app import create_app

        monkeypatch.delenv("JWT_SECRET")

        with pytest.raises(RuntimeError, match="JWT_SECRET"), TestClient(create_app()):
            pass

    def test_server_starts_with_secret(self):
        from fastapi.testclient import TestClient

        from Agent_Guru.reasoning.api.app import create_app

        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200  # nosec B101


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
