"""
API security utilities for input validation and sanitization.

This module implements comprehensive input validation and sanitization
to prevent injection attacks and ensure data integrity.

Security Features:
    - Schema validation for all inputs
    - SQL injection prevention
    - XSS prevention
    - Command injection prevention
    - Request size limits
    - Content security policies

Performance Characteristics:
    - Time Complexity: O(n) where n is input size
    - Space Complexity: O(1)

Design Principles:
    - Validate all inputs
    - Sanitize untrusted data
    - Fail securely
    - Log security events

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import html
import re
from typing import Any, Optional

import structlog
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field, validator

logger = structlog.get_logger(__name__)

# Security configuration
MAX_REQUEST_SIZE = 10 * 1024  # 10KB
MAX_STRING_LENGTH = 1000
MAX_ARRAY_LENGTH = 100
MAX_OBJECT_DEPTH = 5

# Dangerous patterns for injection prevention
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
    r"(--|;|\/\*|\*\/)",
    r"(\bOR\b.*=.*)",
    r"(\bAND\b.*=.*)",
    r"('|\")",
]

COMMAND_INJECTION_PATTERNS = [
    r"[;&|`$()]",
    r"(\.\./)",
    r"(~\/)",
]

XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe",
    r"<object",
    r"<embed",
]


class SecurityValidator:
    """Validator for security checks.

    Time Complexity: O(n) where n is input size
    Space Complexity: O(1)

    Features:
        - SQL injection detection
        - XSS detection
        - Command injection detection
        - Size limit enforcement
        - Depth limit enforcement
    """

    @staticmethod
    def validate_string(
        value: str,
        field_name: str,
        max_length: int = MAX_STRING_LENGTH,
        allow_html: bool = False,
    ) -> str:
        """Validate and sanitize string input.

        Time Complexity: O(n) where n is string length

        Args:
            value: Input string
            field_name: Field name for error messages
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML (default: False)

        Returns:
            Sanitized string

        Raises:
            HTTPException: If validation fails

        Example:
            >>> validator = SecurityValidator()
            >>> clean = validator.validate_string("user input", "text")
        """
        # Check length
        if len(value) > max_length:
            logger.warning(
                "input_too_long",
                field=field_name,
                length=len(value),
                max_length=max_length,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} exceeds maximum length of {max_length}",
            )

        # Check for SQL injection
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(
                    "sql_injection_attempt",
                    field=field_name,
                    pattern=pattern,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid characters in {field_name}",
                )

        # Check for command injection
        for pattern in COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, value):
                logger.warning(
                    "command_injection_attempt",
                    field=field_name,
                    pattern=pattern,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid characters in {field_name}",
                )

        # Check for XSS
        if not allow_html:
            for pattern in XSS_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    logger.warning(
                        "xss_attempt",
                        field=field_name,
                        pattern=pattern,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid content in {field_name}",
                    )

            # HTML escape if not allowing HTML
            value = html.escape(value)

        return value

    @staticmethod
    def validate_dict(
        value: dict[str, Any],
        field_name: str,
        max_depth: int = MAX_OBJECT_DEPTH,
        current_depth: int = 0,
    ) -> dict[str, Any]:
        """Validate dictionary depth and size.

        Time Complexity: O(n) where n is number of keys

        Args:
            value: Input dictionary
            field_name: Field name for error messages
            max_depth: Maximum nesting depth
            current_depth: Current depth (for recursion)

        Returns:
            Validated dictionary

        Raises:
            HTTPException: If validation fails
        """
        if current_depth >= max_depth:
            logger.warning(
                "object_too_deep",
                field=field_name,
                depth=current_depth,
                max_depth=max_depth,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} exceeds maximum nesting depth of {max_depth}",
            )

        # Recursively validate nested dicts
        for key, val in value.items():
            if isinstance(val, dict):
                value[key] = SecurityValidator.validate_dict(
                    val,
                    f"{field_name}.{key}",
                    max_depth,
                    current_depth + 1,
                )
            elif isinstance(val, str):
                value[key] = SecurityValidator.validate_string(
                    val,
                    f"{field_name}.{key}",
                )

        return value

    @staticmethod
    def validate_array(
        value: list,
        field_name: str,
        max_length: int = MAX_ARRAY_LENGTH,
    ) -> list:
        """Validate array length.

        Time Complexity: O(n) where n is array length

        Args:
            value: Input array
            field_name: Field name for error messages
            max_length: Maximum allowed length

        Returns:
            Validated array

        Raises:
            HTTPException: If validation fails
        """
        if len(value) > max_length:
            logger.warning(
                "array_too_long",
                field=field_name,
                length=len(value),
                max_length=max_length,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} exceeds maximum length of {max_length}",
            )

        # Validate array elements
        for i, item in enumerate(value):
            if isinstance(item, str):
                value[i] = SecurityValidator.validate_string(
                    item,
                    f"{field_name}[{i}]",
                )
            elif isinstance(item, dict):
                value[i] = SecurityValidator.validate_dict(
                    item,
                    f"{field_name}[{i}]",
                )

        return value


async def validate_request_size(request: Request) -> None:
    """Middleware to validate request size.

    Time Complexity: O(1)

    Args:
        request: FastAPI request

    Raises:
        HTTPException: If request too large

    Example:
        >>> @app.middleware("http")
        >>> async def check_request_size(request: Request, call_next):
        >>>     await validate_request_size(request)
        >>>     return await call_next(request)
    """
    content_length = request.headers.get("content-length")

    if content_length:
        content_length = int(content_length)
        if content_length > MAX_REQUEST_SIZE:
            logger.warning(
                "request_too_large",
                size=content_length,
                max_size=MAX_REQUEST_SIZE,
                path=request.url.path,
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Request size {content_length} exceeds maximum of {MAX_REQUEST_SIZE} bytes",
            )


class SecureProcessRequest(BaseModel):
    """Secure process request with validation.

    Attributes:
        text: User input text (validated and sanitized)
        user_id: User identifier (validated)
        source: Input source (validated)
        metadata: Optional metadata (validated)
    """

    text: str = Field(..., max_length=MAX_STRING_LENGTH)
    user_id: str = Field(..., max_length=100)
    source: str = Field(..., max_length=50)
    metadata: Optional[dict[str, Any]] = None

    @validator("text")
    def validate_text(cls, v):
        """Validate and sanitize text input."""
        return SecurityValidator.validate_string(v, "text")

    @validator("user_id")
    def validate_user_id(cls, v):
        """Validate user_id format."""
        # Only allow alphanumeric and underscore
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("user_id contains invalid characters")
        return v

    @validator("source")
    def validate_source(cls, v):
        """Validate source value."""
        allowed_sources = ["text", "voice", "system_event"]
        if v not in allowed_sources:
            raise ValueError(f"source must be one of {allowed_sources}")
        return v

    @validator("metadata")
    def validate_metadata(cls, v):
        """Validate metadata structure."""
        if v is not None:
            return SecurityValidator.validate_dict(v, "metadata")
        return v


# Content Security Policy headers
CSP_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def add_security_headers(response):
    """Add security headers to response.

    Args:
        response: FastAPI response

    Returns:
        Response with security headers

    Example:
        >>> @app.middleware("http")
        >>> async def add_headers(request: Request, call_next):
        >>>     response = await call_next(request)
        >>>     return add_security_headers(response)
    """
    for header, value in CSP_HEADERS.items():
        response.headers[header] = value
    return response
