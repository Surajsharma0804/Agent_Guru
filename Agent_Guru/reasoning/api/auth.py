"""
API authentication and authorization.

This module implements JWT-based authentication with rate limiting per user.

Performance Characteristics:
    - Time Complexity: O(1) for token validation
    - Space Complexity: O(n) where n is number of active tokens

Design Principles:
    - Secure JWT tokens with HS256
    - Rate limiting per user
    - Token expiration and refresh
    - Stateless authentication

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds

# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """JWT token data.
    
    Attributes:
        user_id: User identifier
        exp: Expiration timestamp
        iat: Issued at timestamp
    """
    
    user_id: str
    exp: int
    iat: int


class RateLimiter:
    """Rate limiter for API requests.
    
    Time Complexity:
        - check_rate_limit: O(1)
        - cleanup: O(n) where n is number of users
    
    Space Complexity: O(n) where n is number of active users
    
    Features:
        - Per-user rate limiting
        - Sliding window algorithm
        - Automatic cleanup of old entries
    """
    
    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW,
    ) -> None:
        """Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Window size in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list[float]] = {}  # user_id -> [timestamps]
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit.
        
        Time Complexity: O(1) amortized
        
        Args:
            user_id: User identifier
        
        Returns:
            True if within rate limit, False otherwise
        """
        now = time.time()
        
        # Periodic cleanup
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(now)
        
        # Get user's request history
        if user_id not in self._requests:
            self._requests[user_id] = []
        
        requests = self._requests[user_id]
        
        # Remove requests outside window
        cutoff = now - self.window_seconds
        requests[:] = [ts for ts in requests if ts > cutoff]
        
        # Check if within limit
        if len(requests) >= self.max_requests:
            return False
        
        # Add current request
        requests.append(now)
        return True
    
    def get_remaining_requests(self, user_id: str) -> int:
        """Get remaining requests for user.
        
        Args:
            user_id: User identifier
        
        Returns:
            Number of remaining requests
        """
        if user_id not in self._requests:
            return self.max_requests
        
        now = time.time()
        cutoff = now - self.window_seconds
        requests = self._requests[user_id]
        
        # Count requests in window
        active_requests = sum(1 for ts in requests if ts > cutoff)
        return max(0, self.max_requests - active_requests)
    
    def _cleanup_old_entries(self, now: float) -> None:
        """Clean up old entries to prevent memory growth.
        
        Time Complexity: O(n) where n is number of users
        
        Args:
            now: Current timestamp
        """
        cutoff = now - self.window_seconds
        
        # Remove users with no recent requests
        users_to_remove = [
            user_id
            for user_id, requests in self._requests.items()
            if not requests or max(requests) < cutoff
        ]
        
        for user_id in users_to_remove:
            del self._requests[user_id]
        
        self._last_cleanup = now


# Global rate limiter instance
_rate_limiter = RateLimiter()


def create_access_token(user_id: str) -> str:
    """Create JWT access token.
    
    Time Complexity: O(1)
    
    Args:
        user_id: User identifier
    
    Returns:
        JWT token string
    
    Example:
        >>> token = create_access_token("user_123")
        >>> print(token)
    """
    now = datetime.utcnow()
    exp = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    payload = {
        "user_id": user_id,
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token: str) -> TokenData:
    """Verify JWT token and extract data.
    
    Time Complexity: O(1)
    
    Args:
        token: JWT token string
    
    Returns:
        Token data
    
    Raises:
        HTTPException: If token is invalid or expired
    
    Example:
        >>> data = verify_token(token)
        >>> print(data.user_id)
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenData(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Get current user from JWT token.
    
    Time Complexity: O(1)
    
    Args:
        credentials: HTTP authorization credentials
    
    Returns:
        User ID
    
    Raises:
        HTTPException: If token is invalid or rate limit exceeded
    
    Example:
        >>> @app.get("/protected")
        >>> async def protected_route(user_id: str = Depends(get_current_user)):
        >>>     return {"user_id": user_id}
    """
    # Verify token
    token_data = verify_token(credentials.credentials)
    user_id = token_data.user_id
    
    # Check rate limit
    if not _rate_limiter.check_rate_limit(user_id):
        remaining = _rate_limiter.get_remaining_requests(user_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again later. Remaining: {remaining}",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )
    
    return user_id


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance.
    
    Returns:
        Rate limiter instance
    """
    return _rate_limiter
