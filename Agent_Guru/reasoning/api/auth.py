"""
API authentication and authorization.

This module implements JWT-based authentication with RBAC and API key management.

Performance Characteristics:
    - Time Complexity: O(1) for token validation
    - Space Complexity: O(n) where n is number of active tokens

Design Principles:
    - Secure JWT tokens with HS256
    - Role-based access control (RBAC)
    - API key management
    - Rate limiting per user/API key
    - Token expiration and refresh
    - Stateless authentication

Security Features:
    - JWT authentication
    - API key authentication
    - Role-based permissions
    - Per-user rate limiting
    - Per-API key rate limiting
    - Token expiration
    - Secure secret management

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import BaseModel

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds

# Security schemes
security = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class Role(str, Enum):
    """User roles for RBAC.

    Roles:
        ADMIN: Full access to all resources
        USER: Standard user access
        SERVICE: Service account access (for integrations)
        READONLY: Read-only access
    """

    ADMIN = "admin"
    USER = "user"
    SERVICE = "service"
    READONLY = "readonly"


class Permission(str, Enum):
    """Permissions for fine-grained access control.

    Permissions:
        PROCESS_REQUEST: Process user requests
        READ_CONVERSATION: Read conversation history
        WRITE_CONVERSATION: Modify conversation history
        READ_TASK: Read task status
        CANCEL_TASK: Cancel running tasks
        READ_STATS: Read system statistics
        MANAGE_USERS: Manage user accounts
        MANAGE_API_KEYS: Manage API keys
    """

    PROCESS_REQUEST = "process:request"
    READ_CONVERSATION = "read:conversation"
    WRITE_CONVERSATION = "write:conversation"
    READ_TASK = "read:task"
    CANCEL_TASK = "cancel:task"
    READ_STATS = "read:stats"
    MANAGE_USERS = "manage:users"
    MANAGE_API_KEYS = "manage:api_keys"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {
        Permission.PROCESS_REQUEST,
        Permission.READ_CONVERSATION,
        Permission.WRITE_CONVERSATION,
        Permission.READ_TASK,
        Permission.CANCEL_TASK,
        Permission.READ_STATS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_API_KEYS,
    },
    Role.USER: {
        Permission.PROCESS_REQUEST,
        Permission.READ_CONVERSATION,
        Permission.WRITE_CONVERSATION,
        Permission.READ_TASK,
        Permission.CANCEL_TASK,
    },
    Role.SERVICE: {
        Permission.PROCESS_REQUEST,
        Permission.READ_CONVERSATION,
        Permission.READ_TASK,
        Permission.READ_STATS,
    },
    Role.READONLY: {
        Permission.READ_CONVERSATION,
        Permission.READ_TASK,
        Permission.READ_STATS,
    },
}


class TokenData(BaseModel):
    """JWT token data.

    Attributes:
        user_id: User identifier
        role: User role for RBAC
        exp: Expiration timestamp
        iat: Issued at timestamp
    """

    user_id: str
    role: Role
    exp: int
    iat: int


class APIKey(BaseModel):
    """API key data.

    Attributes:
        key_id: API key identifier
        key_hash: Hashed API key
        user_id: Owner user ID
        role: Role for this API key
        name: Human-readable name
        created_at: Creation timestamp
        expires_at: Optional expiration timestamp
        last_used: Last usage timestamp
        is_active: Whether key is active
    """

    key_id: str
    key_hash: str
    user_id: str
    role: Role
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True


class APIKeyManager:
    """Manager for API keys.

    Time Complexity:
        - generate_key: O(1)
        - validate_key: O(1)
        - revoke_key: O(1)

    Space Complexity: O(n) where n is number of API keys

    Features:
        - Secure key generation
        - Key hashing for storage
        - Key validation
        - Key revocation
        - Expiration handling
    """

    def __init__(self) -> None:
        """Initialize API key manager."""
        self._keys: dict[str, APIKey] = {}  # key_id -> APIKey
        self._key_hash_to_id: dict[str, str] = {}  # key_hash -> key_id

    def generate_key(
        self,
        user_id: str,
        role: Role,
        name: str,
        expires_in_days: Optional[int] = None,
    ) -> tuple[str, APIKey]:
        """Generate new API key.

        Time Complexity: O(1)

        Args:
            user_id: Owner user ID
            role: Role for this key
            name: Human-readable name
            expires_in_days: Optional expiration in days

        Returns:
            Tuple of (raw_key, api_key_object)

        Example:
            >>> manager = APIKeyManager()
            >>> raw_key, api_key = manager.generate_key(
            ...     "user_123",
            ...     Role.USER,
            ...     "My API Key",
            ...     expires_in_days=90,
            ... )
            >>> print(f"Key: {raw_key}")
            >>> print(f"Key ID: {api_key.key_id}")
        """
        # Generate secure random key
        raw_key = secrets.token_urlsafe(32)

        # Hash key for storage
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Generate key ID
        key_id = f"key_{secrets.token_urlsafe(16)}"

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create API key object
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            role=role,
            name=name,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True,
        )

        # Store key
        self._keys[key_id] = api_key
        self._key_hash_to_id[key_hash] = key_id

        return raw_key, api_key

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate API key and return key data.

        Time Complexity: O(1)

        Args:
            raw_key: Raw API key string

        Returns:
            API key object if valid, None otherwise

        Example:
            >>> api_key = manager.validate_key(raw_key)
            >>> if api_key:
            ...     print(f"Valid key for user: {api_key.user_id}")
        """
        # Hash key
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # Look up key
        key_id = self._key_hash_to_id.get(key_hash)
        if not key_id:
            return None

        api_key = self._keys.get(key_id)
        if not api_key:
            return None

        # Check if active
        if not api_key.is_active:
            return None

        # Check expiration
        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            return None

        # Update last used
        api_key.last_used = datetime.utcnow()

        return api_key

    def revoke_key(self, key_id: str) -> bool:
        """Revoke API key.

        Time Complexity: O(1)

        Args:
            key_id: API key identifier

        Returns:
            True if revoked, False if not found

        Example:
            >>> manager.revoke_key("key_abc123")
        """
        api_key = self._keys.get(key_id)
        if not api_key:
            return False

        api_key.is_active = False
        return True

    def list_keys(self, user_id: str) -> list[APIKey]:
        """List API keys for user.

        Time Complexity: O(n) where n is number of keys

        Args:
            user_id: User identifier

        Returns:
            List of API keys
        """
        return [
            key
            for key in self._keys.values()
            if key.user_id == user_id
        ]

    def get_key(self, key_id: str) -> Optional[APIKey]:
        """Get API key by ID.

        Time Complexity: O(1)

        Args:
            key_id: API key identifier

        Returns:
            API key if found, None otherwise
        """
        return self._keys.get(key_id)


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
        self._requests: dict[str, list[float]] = {}  # user_id -> [timestamps]
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


# Global instances
_rate_limiter = RateLimiter()
_api_key_manager = APIKeyManager()


def check_permission(role: Role, permission: Permission) -> bool:
    """Check if role has permission.

    Time Complexity: O(1)

    Args:
        role: User role
        permission: Required permission

    Returns:
        True if role has permission, False otherwise

    Example:
        >>> if check_permission(Role.USER, Permission.PROCESS_REQUEST):
        ...     # User can process requests
        ...     pass
    """
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_permission(permission: Permission):
    """Decorator to require permission for endpoint.

    Args:
        permission: Required permission

    Returns:
        Decorator function

    Example:
        >>> @app.get("/admin")
        >>> @require_permission(Permission.MANAGE_USERS)
        >>> async def admin_endpoint(user_id: str = Depends(get_current_user)):
        ...     return {"message": "Admin access granted"}
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get user from kwargs (injected by get_current_user)
            user_data = kwargs.get("user_data")
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check permission
            if not check_permission(user_data["role"], permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def create_access_token(user_id: str, role: Role = Role.USER) -> str:
    """Create JWT access token.

    Time Complexity: O(1)

    Args:
        user_id: User identifier
        role: User role (default: USER)

    Returns:
        JWT token string

    Example:
        >>> token = create_access_token("user_123", Role.ADMIN)
        >>> print(token)
    """
    now = datetime.utcnow()
    exp = now + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "user_id": user_id,
        "role": role.value,
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
        >>> print(data.user_id, data.role)
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # Convert role string to Role enum
        payload["role"] = Role(payload["role"])
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
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    api_key: Optional[str] = Security(api_key_header),
) -> dict[str, any]:
    """Get current user from JWT token or API key.

    Time Complexity: O(1)

    Args:
        credentials: HTTP authorization credentials (JWT)
        api_key: API key from header

    Returns:
        User data dict with user_id and role

    Raises:
        HTTPException: If authentication fails or rate limit exceeded

    Example:
        >>> @app.get("/protected")
        >>> async def protected_route(user_data: Dict = Depends(get_current_user)):
        >>>     return {"user_id": user_data["user_id"], "role": user_data["role"]}
    """
    user_id: str
    role: Role

    # Try API key authentication first
    if api_key:
        api_key_data = _api_key_manager.validate_key(api_key)
        if not api_key_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        user_id = api_key_data.user_id
        role = api_key_data.role

        # Check rate limit for API key
        rate_limit_key = f"apikey_{api_key_data.key_id}"
        if not _rate_limiter.check_rate_limit(rate_limit_key):
            remaining = _rate_limiter.get_remaining_requests(rate_limit_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for API key. Remaining: {remaining}",
                headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
            )

    # Try JWT authentication
    elif credentials:
        token_data = verify_token(credentials.credentials)
        user_id = token_data.user_id
        role = token_data.role

        # Check rate limit for user
        if not _rate_limiter.check_rate_limit(user_id):
            remaining = _rate_limiter.get_remaining_requests(user_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Remaining: {remaining}",
                headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (JWT token or API key)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": user_id,
        "role": role,
    }


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance.

    Returns:
        Rate limiter instance
    """
    return _rate_limiter


def get_api_key_manager() -> APIKeyManager:
    """Get global API key manager instance.

    Returns:
        API key manager instance
    """
    return _api_key_manager
