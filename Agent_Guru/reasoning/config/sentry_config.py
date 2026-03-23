"""Sentry error tracking configuration."""

import os
from typing import Any, Optional

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration


class SentryConfig:
    """Configuration for Sentry error tracking."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        environment: str = "development",
        release: Optional[str] = None,
        traces_sample_rate: float = 0.1,
        profiles_sample_rate: float = 0.1,
        send_default_pii: bool = False,
        attach_stacktrace: bool = True,
        max_breadcrumbs: int = 50,
        debug: bool = False,
    ):
        """
        Initialize Sentry configuration.

        Args:
            dsn: Sentry DSN (Data Source Name)
            environment: Environment name (development, staging, production)
            release: Release version
            traces_sample_rate: Sampling rate for performance traces (0.0-1.0)
            profiles_sample_rate: Sampling rate for profiling (0.0-1.0)
            send_default_pii: Whether to send personally identifiable information
            attach_stacktrace: Whether to attach stack traces to messages
            max_breadcrumbs: Maximum number of breadcrumbs to keep
            debug: Enable debug mode
        """
        self.dsn = dsn or os.getenv("SENTRY_DSN")
        self.environment = environment
        self.release = release or os.getenv("SENTRY_RELEASE", "0.1.0")
        self.traces_sample_rate = traces_sample_rate
        self.profiles_sample_rate = profiles_sample_rate
        self.send_default_pii = send_default_pii
        self.attach_stacktrace = attach_stacktrace
        self.max_breadcrumbs = max_breadcrumbs
        self.debug = debug


def configure_sentry(config: SentryConfig) -> None:
    """
    Configure Sentry error tracking.

    Args:
        config: Sentry configuration
    """
    if not config.dsn:
        # Sentry not configured, skip initialization
        return

    # Configure logging integration
    logging_integration = LoggingIntegration(
        level=None,  # Capture all log levels
        event_level=None,  # Don't send logs as events by default
    )

    # Configure asyncio integration
    asyncio_integration = AsyncioIntegration()

    # Initialize Sentry SDK
    sentry_sdk.init(
        dsn=config.dsn,
        environment=config.environment,
        release=config.release,
        traces_sample_rate=config.traces_sample_rate,
        profiles_sample_rate=config.profiles_sample_rate,
        send_default_pii=config.send_default_pii,
        attach_stacktrace=config.attach_stacktrace,
        max_breadcrumbs=config.max_breadcrumbs,
        debug=config.debug,
        integrations=[
            logging_integration,
            asyncio_integration,
        ],
        before_send=before_send_filter,
        before_breadcrumb=before_breadcrumb_filter,
    )


def before_send_filter(event: dict[str, Any], hint: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Filter and modify events before sending to Sentry.

    Args:
        event: Event dictionary
        hint: Hint dictionary with additional context

    Returns:
        Modified event or None to drop the event
    """
    # Add custom tags
    if "tags" not in event:
        event["tags"] = {}

    event["tags"]["component"] = "reasoning_engine"

    # Filter out sensitive information
    if "request" in event:
        # Remove sensitive headers
        if "headers" in event["request"]:
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                event["request"]["headers"].pop(header, None)

    # Group similar errors
    if "exception" in event and "values" in event["exception"]:
        for exception in event["exception"]["values"]:
            if exception.get("type") == "TimeoutError":
                # Group all timeout errors together
                event["fingerprint"] = ["timeout-error"]

    return event


def before_breadcrumb_filter(crumb: dict[str, Any], hint: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Filter and modify breadcrumbs before adding to event.

    Args:
        crumb: Breadcrumb dictionary
        hint: Hint dictionary with additional context

    Returns:
        Modified breadcrumb or None to drop it
    """
    # Filter out noisy breadcrumbs
    if crumb.get("category") == "query" and crumb.get("message", "").startswith("SELECT"):
        # Skip SELECT queries to reduce noise
        return None

    return crumb


class SentryContextManager:
    """Manager for Sentry context and error capture."""

    @staticmethod
    def set_user_context(
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Set user context for error tracking.

        Args:
            user_id: User ID
            username: Username
            email: User email
            **kwargs: Additional user attributes
        """
        user_data = {}
        if user_id:
            user_data["id"] = user_id
        if username:
            user_data["username"] = username
        if email:
            user_data["email"] = email
        user_data.update(kwargs)

        sentry_sdk.set_user(user_data)

    @staticmethod
    def set_conversation_context(
        conversation_id: str,
        turn_id: Optional[str] = None,
        intent_type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Set conversation context for error tracking.

        Args:
            conversation_id: Conversation ID
            turn_id: Turn ID
            intent_type: Detected intent type
            **kwargs: Additional context
        """
        with sentry_sdk.configure_scope() as scope:
            scope.set_context("conversation", {
                "conversation_id": conversation_id,
                "turn_id": turn_id,
                "intent_type": intent_type,
                **kwargs,
            })

    @staticmethod
    def set_input_context(
        input_text: str,
        input_source: str,
        **kwargs: Any,
    ) -> None:
        """
        Set input context for error tracking.

        Args:
            input_text: User input text (will be truncated)
            input_source: Input source (voice, text, etc.)
            **kwargs: Additional context
        """
        # Truncate input to avoid sending too much data
        truncated_input = input_text[:200] + "..." if len(input_text) > 200 else input_text

        with sentry_sdk.configure_scope() as scope:
            scope.set_context("input", {
                "text": truncated_input,
                "source": input_source,
                **kwargs,
            })

    @staticmethod
    def add_breadcrumb(
        message: str,
        category: str = "default",
        level: str = "info",
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Add a breadcrumb for error context.

        Args:
            message: Breadcrumb message
            category: Breadcrumb category
            level: Breadcrumb level (debug, info, warning, error)
            data: Additional breadcrumb data
        """
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {},
        )

    @staticmethod
    def capture_exception(
        error: Exception,
        level: str = "error",
        tags: Optional[dict[str, str]] = None,
        extras: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Capture an exception and send to Sentry.

        Args:
            error: Exception to capture
            level: Error level (debug, info, warning, error, fatal)
            tags: Additional tags
            extras: Additional extra data

        Returns:
            Event ID
        """
        with sentry_sdk.push_scope() as scope:
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)

            if extras:
                for key, value in extras.items():
                    scope.set_extra(key, value)

            scope.level = level

            return sentry_sdk.capture_exception(error)

    @staticmethod
    def capture_message(
        message: str,
        level: str = "info",
        tags: Optional[dict[str, str]] = None,
        extras: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Capture a message and send to Sentry.

        Args:
            message: Message to capture
            level: Message level (debug, info, warning, error, fatal)
            tags: Additional tags
            extras: Additional extra data

        Returns:
            Event ID
        """
        with sentry_sdk.push_scope() as scope:
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)

            if extras:
                for key, value in extras.items():
                    scope.set_extra(key, value)

            scope.level = level

            return sentry_sdk.capture_message(message)

    @staticmethod
    def clear_context() -> None:
        """Clear all Sentry context."""
        sentry_sdk.set_user(None)
        with sentry_sdk.configure_scope() as scope:
            scope.clear()


# Global Sentry context manager
sentry_context = SentryContextManager()
