"""Typed exceptions for the Agent Guru SDK."""

from __future__ import annotations


class AgentGuruSDKError(Exception):
    """Base SDK error."""


class InvalidParameterError(AgentGuruSDKError):
    """Raised when a parameter fails validation."""

    def __init__(self, param: str, message: str) -> None:
        self.param = param
        super().__init__(f"Invalid parameter '{param}': {message}")


class RateLimitError(AgentGuruSDKError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: float = 0.0) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.1f}s")


class ProviderUnavailableError(AgentGuruSDKError):
    """Raised when a provider is unavailable."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Provider '{provider}' is unavailable")
