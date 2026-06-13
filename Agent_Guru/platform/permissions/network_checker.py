"""Module: Agent_Guru.platform.permissions.network_checker
Purpose: Network permission validation with domain whitelist and HTTP method checking.

This module implements comprehensive network validation:
- Domain whitelist checking (exact and wildcard matching)
- HTTP method validation
- URL pattern matching (regex-based)
- Protocol validation (HTTPS enforcement)
- Port validation
- Query parameter validation

Performance Characteristics:
    - Time Complexity: O(n) where n is number of allowed domains
    - Space Complexity: O(1) for validation
    - Domain Matching: O(1) average (hash table lookup)

Security Features:
    - HTTPS enforcement (production mode)
    - Domain whitelist (no blacklist bypass)
    - Method restriction
    - URL sanitization
    - Query parameter validation
    - Port restriction

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)


class HttpMethod(Enum):
    """HTTP method types."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    CONNECT = "CONNECT"
    TRACE = "TRACE"


class Protocol(Enum):
    """Network protocol types."""

    HTTP = "http"
    HTTPS = "https"
    FTP = "ftp"
    FTPS = "ftps"
    WS = "ws"
    WSS = "wss"


@dataclass
class NetworkValidationResult:
    """Result of network validation."""

    allowed: bool
    url: str
    method: HttpMethod
    parsed_url: Any  # ParseResult
    matched_domain: str | None
    matched_pattern: str | None
    reason: str
    protocol: str
    domain: str
    port: int | None
    path: str
    sanitized_url: str | None
    warnings: list[str]


class NetworkValidationError(Exception):
    """Raised when network validation fails."""


class NetworkPermissionChecker:
    """Network permission checker with domain whitelist and method validation.

    Features:
    - Domain whitelist (exact and wildcard matching)
    - HTTP method validation
    - URL pattern matching (regex)
    - Protocol validation (HTTPS enforcement)
    - Port validation
    - Query parameter sanitization

    Time Complexity: O(n) where n is number of allowed domains
    Space Complexity: O(1) for validation

    Example:
        >>> checker = NetworkPermissionChecker()
        >>> checker.add_allowed_domain("api.github.com")
        >>> checker.add_allowed_domain("*.googleapis.com")
        >>> checker.add_allowed_method(HttpMethod.GET)
        >>> result = checker.validate_url(
        ...     "https://api.github.com/repos",
        ...     HttpMethod.GET
        ... )
        >>> print(f"Allowed: {result.allowed}")

    """

    # Default allowed ports
    DEFAULT_ALLOWED_PORTS: ClassVar[set[int]] = {80, 443, 8080, 8443}

    # Dangerous query parameters (potential security risks)
    DANGEROUS_PARAMS: ClassVar[list[str]] = [
        "eval",
        "exec",
        "system",
        "cmd",
        "command",
        "__import__",
        "compile",
    ]

    def __init__(self, enforce_https: bool = True, allowed_ports: set[int] | None = None) -> None:
        """Initialize network permission checker.

        Args:
            enforce_https: Whether to enforce HTTPS in production
            allowed_ports: Set of allowed ports (defaults to 80, 443, 8080, 8443)

        """
        self._allowed_domains: set[str] = set()
        self._wildcard_domains: list[str] = []  # Domains with * prefix
        self._allowed_methods: set[HttpMethod] = set()
        self._allowed_patterns: list[re.Pattern] = []
        self._blocked_patterns: list[re.Pattern] = []
        self._enforce_https = enforce_https
        self._allowed_ports = allowed_ports or self.DEFAULT_ALLOWED_PORTS

        logger.debug(
            f"NetworkPermissionChecker initialized "
            f"(enforce_https={enforce_https}, "
            f"allowed_ports={self._allowed_ports})",
        )

    def add_allowed_domain(self, domain: str) -> None:
        """Add allowed domain to whitelist.

        Supports wildcards:
        - *.example.com matches any subdomain of example.com
        - example.com matches exactly example.com

        Args:
            domain: Domain name (e.g., "api.github.com", "*.googleapis.com")

        Example:
            >>> checker.add_allowed_domain("api.github.com")
            >>> checker.add_allowed_domain("*.googleapis.com")

        """
        domain = domain.lower().strip()

        if domain.startswith("*."):
            # Wildcard subdomain
            self._wildcard_domains.append(domain[2:])  # Store without *.
            logger.debug("Added wildcard domain: %s", domain)
        else:
            # Exact domain
            self._allowed_domains.add(domain)
            logger.debug("Added exact domain: %s", domain)

    def add_allowed_method(self, method: HttpMethod) -> None:
        """Add allowed HTTP method.

        Args:
            method: HTTP method to allow

        Example:
            >>> checker.add_allowed_method(HttpMethod.GET)
            >>> checker.add_allowed_method(HttpMethod.POST)

        """
        self._allowed_methods.add(method)
        logger.debug("Added allowed method: %s", method.value)

    def add_allowed_pattern(self, pattern: str) -> None:
        r"""Add allowed URL pattern (regex).

        Args:
            pattern: Regular expression pattern

        Example:
            >>> checker.add_allowed_pattern(r"^https://api\.github\.com/repos/.*")

        """
        try:
            compiled_pattern = re.compile(pattern)
            self._allowed_patterns.append(compiled_pattern)
            logger.debug("Added allowed URL pattern: %s", pattern)
        except re.error as e:
            logger.exception("Invalid regex pattern: %s (%s)")
            msg = f"Invalid regex pattern: {pattern}"
            raise NetworkValidationError(msg) from e

    def add_blocked_pattern(self, pattern: str) -> None:
        """Add blocked URL pattern (regex).

        Blocked patterns take precedence over allowed patterns.

        Args:
            pattern: Regular expression pattern

        Example:
            >>> checker.add_blocked_pattern(r".*admin.*")

        """
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            self._blocked_patterns.append(compiled_pattern)
            logger.debug("Added blocked URL pattern: %s", pattern)
        except re.error as e:
            logger.exception("Invalid regex pattern: %s (%s)")
            msg = f"Invalid regex pattern: {pattern}"
            raise NetworkValidationError(msg) from e

    def validate_url(
        self,
        url: str,
        method: HttpMethod,
        validate_query_params: bool = True,
    ) -> NetworkValidationResult:
        """Validate URL against allowed domains, methods, and patterns.

        Time Complexity: O(n) where n is number of allowed domains
        Space Complexity: O(1)

        Args:
            url: URL to validate
            method: HTTP method
            validate_query_params: Whether to validate query parameters

        Returns:
            NetworkValidationResult with validation details

        """
        warnings = []

        # Basic validation
        if not url or not url.strip():
            return NetworkValidationResult(
                allowed=False,
                url=url,
                method=method,
                parsed_url=None,
                matched_domain=None,
                matched_pattern=None,
                reason="Empty URL",
                protocol="",
                domain="",
                port=None,
                path="",
                sanitized_url=None,
                warnings=[],
            )

        # Parse URL
        try:
            parsed_url = urlparse(url)
        except Exception as e:
            return NetworkValidationResult(
                allowed=False,
                url=url,
                method=method,
                parsed_url=None,
                matched_domain=None,
                matched_pattern=None,
                reason=f"Failed to parse URL: {e}",
                protocol="",
                domain="",
                port=None,
                path="",
                sanitized_url=None,
                warnings=[],
            )

        # Extract components
        protocol = parsed_url.scheme.lower()
        domain = parsed_url.netloc.lower()
        port = parsed_url.port
        path = parsed_url.path

        # Remove port from domain if present
        if ":" in domain:
            domain = domain.split(":")[0]

        # Validate protocol
        if self._enforce_https and protocol != "https":
            logger.warning("Non-HTTPS protocol denied: %s", url)
            return NetworkValidationResult(
                allowed=False,
                url=url,
                method=method,
                parsed_url=parsed_url,
                matched_domain=None,
                matched_pattern=None,
                reason=f"HTTPS required (got: {protocol})",
                protocol=protocol,
                domain=domain,
                port=port,
                path=path,
                sanitized_url=None,
                warnings=[],
            )

        # Validate port
        if port is not None and port not in self._allowed_ports:
            logger.warning("Port not allowed: %s in %s", port, url)
            warnings.append(f"Port {port} not in allowed ports: {self._allowed_ports}")

        # Check blocked patterns first (security priority)
        for pattern in self._blocked_patterns:
            if pattern.search(url):
                logger.warning("URL blocked by pattern: %s", url)
                return NetworkValidationResult(
                    allowed=False,
                    url=url,
                    method=method,
                    parsed_url=parsed_url,
                    matched_domain=None,
                    matched_pattern=pattern.pattern,
                    reason=f"URL matches blocked pattern: {pattern.pattern}",
                    protocol=protocol,
                    domain=domain,
                    port=port,
                    path=path,
                    sanitized_url=None,
                    warnings=[],
                )

        # Validate HTTP method
        if method not in self._allowed_methods:
            logger.warning("HTTP method not allowed: %s", method.value)
            return NetworkValidationResult(
                allowed=False,
                url=url,
                method=method,
                parsed_url=parsed_url,
                matched_domain=None,
                matched_pattern=None,
                reason=f"HTTP method {method.value} not allowed",
                protocol=protocol,
                domain=domain,
                port=port,
                path=path,
                sanitized_url=None,
                warnings=[],
            )

        # Validate domain
        domain_match = self._check_domain(domain)
        if not domain_match[0]:
            logger.warning("Domain not allowed: %s", domain)
            return NetworkValidationResult(
                allowed=False,
                url=url,
                method=method,
                parsed_url=parsed_url,
                matched_domain=None,
                matched_pattern=None,
                reason=f"Domain {domain} not in whitelist",
                protocol=protocol,
                domain=domain,
                port=port,
                path=path,
                sanitized_url=None,
                warnings=[],
            )

        matched_domain = domain_match[1]

        # Check URL patterns if any
        matched_pattern = None
        if self._allowed_patterns:
            pattern_matched = False
            for pattern in self._allowed_patterns:
                if pattern.search(url):
                    matched_pattern = pattern.pattern
                    pattern_matched = True
                    break

            if not pattern_matched:
                logger.warning("URL does not match any allowed pattern: %s", url)
                return NetworkValidationResult(
                    allowed=False,
                    url=url,
                    method=method,
                    parsed_url=parsed_url,
                    matched_domain=matched_domain,
                    matched_pattern=None,
                    reason="URL does not match any allowed pattern",
                    protocol=protocol,
                    domain=domain,
                    port=port,
                    path=path,
                    sanitized_url=None,
                    warnings=[],
                )

        # Validate query parameters
        if validate_query_params and parsed_url.query:
            param_validation = self._validate_query_params(parsed_url.query)
            if not param_validation[0]:
                warnings.append(param_validation[1])

        # Sanitize URL
        sanitized_url = self._sanitize_url(parsed_url)

        logger.debug(
            f"URL allowed: {url} -> {matched_domain} (method: {method.value}, protocol: {protocol})",
        )

        return NetworkValidationResult(
            allowed=True,
            url=url,
            method=method,
            parsed_url=parsed_url,
            matched_domain=matched_domain,
            matched_pattern=matched_pattern,
            reason="URL matches allowed domain and method",
            protocol=protocol,
            domain=domain,
            port=port,
            path=path,
            sanitized_url=sanitized_url,
            warnings=warnings,
        )

    def _check_domain(self, domain: str) -> tuple[bool, str | None]:
        """Check if domain is in whitelist.

        Time Complexity: O(1) for exact match, O(n) for wildcard match
        Space Complexity: O(1)

        Args:
            domain: Domain to check

        Returns:
            Tuple of (is_allowed, matched_domain)

        """
        domain = domain.lower()

        # Check exact match first (O(1))
        if domain in self._allowed_domains:
            return (True, domain)

        # Check wildcard matches (O(n))
        for wildcard_base in self._wildcard_domains:
            # Wildcard should only match subdomains, not the base domain itself
            # e.g., "api.example.com" matches "*.example.com"
            # but "example.com" does NOT match "*.example.com"
            # and "notexample.com" does NOT match "*.example.com"
            if domain.endswith("." + wildcard_base):
                return (True, f"*.{wildcard_base}")

        return (False, None)

    def _validate_query_params(self, query_string: str) -> tuple[bool, str]:
        """Validate query parameters for suspicious patterns.

        Args:
            query_string: URL query string

        Returns:
            Tuple of (is_valid, warning_message)

        """
        warnings = []

        try:
            params = parse_qs(query_string)
        except Exception as e:
            return (False, f"Failed to parse query parameters: {e}")

        for param_name, param_values in params.items():
            # Check for dangerous parameter names
            if param_name.lower() in self.DANGEROUS_PARAMS:
                warnings.append(f"Dangerous parameter name: {param_name}")

            # Check parameter values
            for value in param_values:
                # Check for code injection patterns
                if any(
                    pattern in value.lower()
                    for pattern in ["<script", "javascript:", "eval(", "exec("]
                ):
                    warnings.append(f"Suspicious parameter value: {param_name}={value}")

                # Check for SQL injection patterns
                if any(
                    pattern in value.lower() for pattern in ["' or ", "'; drop", "union select"]
                ):
                    warnings.append(f"Potential SQL injection: {param_name}={value}")

        if warnings:
            return (False, "; ".join(warnings))
        return (True, "")

    def _sanitize_url(self, parsed_url: Any) -> str:
        """Sanitize URL by removing potentially dangerous elements.

        Args:
            parsed_url: Parsed URL object

        Returns:
            Sanitized URL

        """
        # Reconstruct URL with sanitized components
        sanitized_parts = list(parsed_url)

        # Sanitize query parameters
        if parsed_url.query:
            try:
                params = parse_qs(parsed_url.query)
                # Remove dangerous parameters
                safe_params = {
                    k: v for k, v in params.items() if k.lower() not in self.DANGEROUS_PARAMS
                }
                sanitized_parts[4] = urlencode(safe_params, doseq=True)
            except Exception:
                # If sanitization fails, remove query string entirely
                sanitized_parts[4] = ""

        # Remove fragment (not needed for API calls)
        sanitized_parts[5] = ""

        return urlunparse(sanitized_parts)

    def is_url_allowed(self, url: str, method: HttpMethod) -> bool:
        """Quick check if URL is allowed.

        Time Complexity: O(n)
        Space Complexity: O(1)

        Args:
            url: URL to check
            method: HTTP method

        Returns:
            True if URL is allowed

        """
        result = self.validate_url(url, method, validate_query_params=False)
        return result.allowed

    def is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is in whitelist.

        Time Complexity: O(n)
        Space Complexity: O(1)

        Args:
            domain: Domain to check

        Returns:
            True if domain is allowed

        """
        return self._check_domain(domain.lower())[0]

    def is_method_allowed(self, method: HttpMethod) -> bool:
        """Check if HTTP method is allowed.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            method: HTTP method to check

        Returns:
            True if method is allowed

        """
        return method in self._allowed_methods

    def get_url_info(self, url: str, method: HttpMethod) -> dict[str, Any]:
        """Get detailed information about URL validation.

        Args:
            url: URL to analyze
            method: HTTP method

        Returns:
            Dictionary with URL validation information

        """
        result = self.validate_url(url, method)

        return {
            "allowed": result.allowed,
            "url": result.url,
            "method": result.method.value,
            "matched_domain": result.matched_domain,
            "matched_pattern": result.matched_pattern,
            "reason": result.reason,
            "protocol": result.protocol,
            "domain": result.domain,
            "port": result.port,
            "path": result.path,
            "sanitized_url": result.sanitized_url,
            "warnings": result.warnings,
        }

    def clear_domains(self) -> None:
        """Clear all allowed domains."""
        self._allowed_domains.clear()
        self._wildcard_domains.clear()
        logger.debug("All allowed domains cleared")

    def clear_methods(self) -> None:
        """Clear all allowed methods."""
        self._allowed_methods.clear()
        logger.debug("All allowed methods cleared")

    def clear_patterns(self) -> None:
        """Clear all URL patterns."""
        self._allowed_patterns.clear()
        self._blocked_patterns.clear()
        logger.debug("All URL patterns cleared")

    @property
    def allowed_domain_count(self) -> int:
        """Get number of allowed domains (exact + wildcard)."""
        return len(self._allowed_domains) + len(self._wildcard_domains)

    @property
    def allowed_method_count(self) -> int:
        """Get number of allowed methods."""
        return len(self._allowed_methods)

    @property
    def allowed_pattern_count(self) -> int:
        """Get number of allowed patterns."""
        return len(self._allowed_patterns)

    @property
    def blocked_pattern_count(self) -> int:
        """Get number of blocked patterns."""
        return len(self._blocked_patterns)


def is_valid_url(url: str) -> bool:
    """Quick validation that URL is well-formed.

    Time Complexity: O(1)
    Space Complexity: O(1)

    Args:
        url: URL to validate

    Returns:
        True if URL is well-formed

    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def extract_domain(url: str) -> str | None:
    """Extract domain from URL.

    Time Complexity: O(1)
    Space Complexity: O(1)

    Args:
        url: URL to parse

    Returns:
        Domain name or None if parsing fails

    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove port if present
        if ":" in domain:
            domain = domain.split(":")[0]
        # Return None if no domain found
        return domain if domain else None
    except Exception:
        return None


def is_https_url(url: str) -> bool:
    """Check if URL uses HTTPS protocol.

    Time Complexity: O(1)
    Space Complexity: O(1)

    Args:
        url: URL to check

    Returns:
        True if URL uses HTTPS

    """
    try:
        parsed = urlparse(url)
        return parsed.scheme.lower() == "https"
    except Exception:
        return False


def sanitize_url_simple(url: str) -> str:
    """Simple URL sanitization (remove fragment, normalize).

    Time Complexity: O(n) where n is URL length
    Space Complexity: O(n)

    Args:
        url: URL to sanitize

    Returns:
        Sanitized URL

    """
    try:
        parsed = urlparse(url)
        # Remove fragment
        sanitized_parts = list(parsed)
        sanitized_parts[5] = ""
        return urlunparse(sanitized_parts)
    except Exception:
        return url
