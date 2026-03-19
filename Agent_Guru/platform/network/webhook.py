"""
Module: agent_guru.platform.network.webhook
Purpose: Webhook registration, signature verification, and event routing
Author: Agent Guru Team
Date: 2026-02-26

Performance Requirements:
- Time Complexity: O(1) for webhook lookup and routing
- Space Complexity: O(n) where n is number of registered webhooks
- Latency: <10ms for signature verification (95th percentile)
- Throughput: 1000+ webhook events/second

Design Decisions:
- Use HMAC-SHA256 for signature verification (industry standard)
- Async handlers for non-blocking event processing
- Thread-safe handler registration (concurrent access)
- Structured logging for all webhook events (audit trail)
"""

import asyncio
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Awaitable
from enum import Enum
import json

# Configure structured logging
logger = logging.getLogger(__name__)


class SignatureAlgorithm(str, Enum):
    """Signature algorithms for webhook verification."""
    
    HMAC_SHA256 = "hmac-sha256"
    HMAC_SHA512 = "hmac-sha512"


@dataclass
class WebhookConfig:
    """Configuration for webhook handling.
    
    Attributes:
        signature_algorithm: Algorithm for signature verification
        signature_header: HTTP header containing signature
        timestamp_header: HTTP header containing timestamp
        timestamp_tolerance: Maximum age of webhook in seconds (300s = 5 minutes)
        require_signature: Whether signature verification is required
        require_timestamp: Whether timestamp validation is required
    """
    
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256
    signature_header: str = "X-Webhook-Signature"
    timestamp_header: str = "X-Webhook-Timestamp"
    timestamp_tolerance: float = 300.0  # 5 minutes
    require_signature: bool = True
    require_timestamp: bool = True


@dataclass
class WebhookEvent:
    """Webhook event data.
    
    Attributes:
        event_id: Unique event identifier
        event_type: Event type (e.g., "user.created", "payment.completed")
        timestamp: Event timestamp
        payload: Event payload data
        headers: HTTP headers from webhook request
        signature: Signature from webhook request (if present)
        verified: Whether signature was verified successfully
    """
    
    event_id: str
    event_type: str
    timestamp: datetime
    payload: Dict[str, Any]
    headers: Dict[str, str]
    signature: Optional[str] = None
    verified: bool = False


@dataclass
class WebhookHandler:
    """Webhook handler registration.
    
    Attributes:
        endpoint: Webhook endpoint path (e.g., "/webhooks/github")
        handler: Async handler function
        secret_key: Secret key for signature verification
        config: Webhook configuration
        event_types: List of event types to handle (empty = all types)
        created_at: Handler registration timestamp
        last_triggered: Last time handler was triggered
        trigger_count: Number of times handler was triggered
    """
    
    endpoint: str
    handler: Callable[[WebhookEvent], Awaitable[None]]
    secret_key: Optional[str]
    config: WebhookConfig
    event_types: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0


# Exception hierarchy

class WebhookError(Exception):
    """Base exception for webhook operations."""
    pass


class SignatureVerificationError(WebhookError):
    """Raised when signature verification fails."""
    pass


class TimestampValidationError(WebhookError):
    """Raised when timestamp validation fails."""
    pass


class HandlerNotFoundError(WebhookError):
    """Raised when no handler found for endpoint."""
    pass


class WebhookManager:
    """Webhook manager with signature verification and event routing.
    
    Time Complexity: O(1) for webhook lookup and routing
    Space Complexity: O(n) where n is number of registered webhooks
    
    Features:
    - Webhook registration with endpoint paths
    - HMAC-SHA256/SHA512 signature verification
    - Timestamp validation (prevent replay attacks)
    - Event type filtering
    - Async event handlers
    - Handler statistics tracking
    
    Example:
        >>> manager = WebhookManager()
        >>> 
        >>> # Register webhook handler
        >>> async def handle_github_event(event: WebhookEvent):
        ...     print(f"GitHub event: {event.event_type}")
        ...     print(f"Payload: {event.payload}")
        >>> 
        >>> manager.register_webhook(
        ...     endpoint="/webhooks/github",
        ...     handler=handle_github_event,
        ...     secret_key="github_webhook_secret",
        ...     event_types=["push", "pull_request"]
        ... )
        >>> 
        >>> # Process incoming webhook
        >>> event = await manager.process_webhook(
        ...     endpoint="/webhooks/github",
        ...     headers={"X-Webhook-Signature": "sha256=...", "X-Webhook-Timestamp": "1234567890"},
        ...     body=b'{"event": "push", "repository": "agent-guru"}',
        ... )
    """
    
    def __init__(self, default_config: Optional[WebhookConfig] = None) -> None:
        """Initialize webhook manager.
        
        Args:
            default_config: Default webhook configuration
        """
        self.default_config = default_config or WebhookConfig()
        self._handlers: Dict[str, WebhookHandler] = {}
        self._lock = asyncio.Lock()
        
        logger.info(
            "WebhookManager initialized",
            extra={
                "signature_algorithm": self.default_config.signature_algorithm.value,
                "require_signature": self.default_config.require_signature,
                "require_timestamp": self.default_config.require_timestamp,
                "timestamp_tolerance": self.default_config.timestamp_tolerance,
            }
        )
    
    def register_webhook(
        self,
        endpoint: str,
        handler: Callable[[WebhookEvent], Awaitable[None]],
        secret_key: Optional[str] = None,
        config: Optional[WebhookConfig] = None,
        event_types: Optional[List[str]] = None,
    ) -> None:
        """Register webhook handler for endpoint.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            endpoint: Webhook endpoint path (e.g., "/webhooks/github")
            handler: Async handler function
            secret_key: Secret key for signature verification
            config: Webhook configuration (uses default if None)
            event_types: List of event types to handle (empty = all types)
        
        Raises:
            ValueError: If endpoint already registered
        
        Example:
            >>> async def handle_event(event: WebhookEvent):
            ...     print(f"Event: {event.event_type}")
            >>> 
            >>> manager.register_webhook(
            ...     endpoint="/webhooks/stripe",
            ...     handler=handle_event,
            ...     secret_key="stripe_webhook_secret",
            ...     event_types=["payment.succeeded", "payment.failed"]
            ... )
        """
        # Normalize endpoint (ensure starts with /)
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        
        # Check if already registered
        if endpoint in self._handlers:
            raise ValueError(f"Webhook endpoint already registered: {endpoint}")
        
        # Create handler
        webhook_handler = WebhookHandler(
            endpoint=endpoint,
            handler=handler,
            secret_key=secret_key,
            config=config or self.default_config,
            event_types=event_types or [],
        )
        
        self._handlers[endpoint] = webhook_handler
        
        logger.info(
            "Webhook registered",
            extra={
                "endpoint": endpoint,
                "has_secret": secret_key is not None,
                "event_types": event_types or ["all"],
            }
        )
    
    def unregister_webhook(self, endpoint: str) -> bool:
        """Unregister webhook handler.
        
        Args:
            endpoint: Webhook endpoint path
        
        Returns:
            True if handler was unregistered, False if not found
        
        Example:
            >>> manager.unregister_webhook("/webhooks/github")
            True
        """
        # Normalize endpoint
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        
        if endpoint in self._handlers:
            del self._handlers[endpoint]
            logger.info(f"Webhook unregistered: {endpoint}")
            return True
        
        return False
    
    def get_registered_endpoints(self) -> List[str]:
        """Get list of registered webhook endpoints.
        
        Returns:
            List of endpoint paths
        
        Example:
            >>> endpoints = manager.get_registered_endpoints()
            >>> print(f"Registered: {endpoints}")
            ['webhooks/github', '/webhooks/stripe']
        """
        return list(self._handlers.keys())
    
    def get_handler_stats(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get statistics for webhook handler.
        
        Args:
            endpoint: Webhook endpoint path
        
        Returns:
            Handler statistics or None if not found
        
        Example:
            >>> stats = manager.get_handler_stats("/webhooks/github")
            >>> if stats:
            ...     print(f"Triggers: {stats['trigger_count']}")
            ...     print(f"Last triggered: {stats['last_triggered']}")
        """
        # Normalize endpoint
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        
        handler = self._handlers.get(endpoint)
        if handler is None:
            return None
        
        return {
            "endpoint": handler.endpoint,
            "event_types": handler.event_types or ["all"],
            "created_at": handler.created_at.isoformat(),
            "last_triggered": handler.last_triggered.isoformat() if handler.last_triggered else None,
            "trigger_count": handler.trigger_count,
        }
    
    def _verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret_key: str,
        algorithm: SignatureAlgorithm,
    ) -> bool:
        """Verify webhook signature.
        
        Time Complexity: O(n) where n is payload size
        Space Complexity: O(1)
        
        Args:
            payload: Webhook payload bytes
            signature: Signature from webhook request
            secret_key: Secret key for verification
            algorithm: Signature algorithm
        
        Returns:
            True if signature is valid, False otherwise
        """
        # Select hash algorithm
        if algorithm == SignatureAlgorithm.HMAC_SHA256:
            hash_func = hashlib.sha256
            prefix = "sha256="
        elif algorithm == SignatureAlgorithm.HMAC_SHA512:
            hash_func = hashlib.sha512
            prefix = "sha512="
        else:
            logger.error(f"Unsupported signature algorithm: {algorithm}")
            return False
        
        # Compute expected signature
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload,
            hash_func
        ).hexdigest()
        
        # Add prefix if not present in provided signature
        if not signature.startswith(prefix):
            signature = f"{prefix}{signature}"
        
        expected_with_prefix = f"{prefix}{expected_signature}"
        
        # Constant-time comparison (prevent timing attacks)
        return hmac.compare_digest(signature, expected_with_prefix)
    
    def _validate_timestamp(
        self,
        timestamp_str: str,
        tolerance: float,
    ) -> bool:
        """Validate webhook timestamp.
        
        Time Complexity: O(1)
        Space Complexity: O(1)
        
        Args:
            timestamp_str: Timestamp string (Unix timestamp)
            tolerance: Maximum age in seconds
        
        Returns:
            True if timestamp is valid, False otherwise
        """
        try:
            # Parse timestamp
            timestamp = float(timestamp_str)
            event_time = datetime.utcfromtimestamp(timestamp)
            current_time = datetime.utcnow()
            
            # Check if timestamp is within tolerance
            age = (current_time - event_time).total_seconds()
            
            if age < 0:
                logger.warning(f"Webhook timestamp is in the future: {timestamp_str}")
                return False
            
            if age > tolerance:
                logger.warning(
                    f"Webhook timestamp too old: {age:.1f}s (tolerance: {tolerance}s)"
                )
                return False
            
            return True
        
        except (ValueError, OSError) as e:
            logger.error(f"Invalid timestamp format: {timestamp_str} - {e}")
            return False
    
    async def process_webhook(
        self,
        endpoint: str,
        headers: Dict[str, str],
        body: bytes,
    ) -> WebhookEvent:
        """Process incoming webhook request.
        
        Time Complexity: O(n) where n is payload size (for signature verification)
        Space Complexity: O(n) where n is payload size
        
        Args:
            endpoint: Webhook endpoint path
            headers: HTTP headers from request
            body: Request body bytes
        
        Returns:
            Webhook event
        
        Raises:
            HandlerNotFoundError: If no handler registered for endpoint
            SignatureVerificationError: If signature verification fails
            TimestampValidationError: If timestamp validation fails
            WebhookError: If webhook processing fails
        
        Example:
            >>> event = await manager.process_webhook(
            ...     endpoint="/webhooks/github",
            ...     headers={
            ...         "X-Webhook-Signature": "sha256=abc123...",
            ...         "X-Webhook-Timestamp": "1234567890",
            ...         "X-GitHub-Event": "push",
            ...     },
            ...     body=b'{"repository": "agent-guru", "ref": "refs/heads/main"}',
            ... )
            >>> print(f"Event type: {event.event_type}")
            >>> print(f"Verified: {event.verified}")
        """
        start_time = time.perf_counter()
        
        # Normalize endpoint
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        
        # Find handler
        handler = self._handlers.get(endpoint)
        if handler is None:
            raise HandlerNotFoundError(f"No handler registered for endpoint: {endpoint}")
        
        # Parse payload
        try:
            payload = json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise WebhookError(f"Invalid JSON payload: {e}") from e
        
        # Extract event metadata
        event_id = payload.get("id", hashlib.sha256(body).hexdigest()[:16])
        event_type = payload.get("type") or payload.get("event") or "unknown"
        timestamp = datetime.utcnow()
        
        # Verify signature if required
        verified = False
        if handler.config.require_signature:
            signature = headers.get(handler.config.signature_header)
            if not signature:
                raise SignatureVerificationError(
                    f"Missing signature header: {handler.config.signature_header}"
                )
            
            if handler.secret_key is None:
                raise SignatureVerificationError(
                    f"No secret key configured for endpoint: {endpoint}"
                )
            
            verified = self._verify_signature(
                payload=body,
                signature=signature,
                secret_key=handler.secret_key,
                algorithm=handler.config.signature_algorithm,
            )
            
            if not verified:
                raise SignatureVerificationError(
                    f"Signature verification failed for endpoint: {endpoint}"
                )
        
        # Validate timestamp if required
        if handler.config.require_timestamp:
            timestamp_str = headers.get(handler.config.timestamp_header)
            if not timestamp_str:
                raise TimestampValidationError(
                    f"Missing timestamp header: {handler.config.timestamp_header}"
                )
            
            if not self._validate_timestamp(timestamp_str, handler.config.timestamp_tolerance):
                raise TimestampValidationError(
                    f"Timestamp validation failed for endpoint: {endpoint}"
                )
        
        # Create event
        event = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
            headers=headers,
            signature=headers.get(handler.config.signature_header),
            verified=verified,
        )
        
        # Check event type filter
        if handler.event_types and event_type not in handler.event_types:
            logger.debug(
                f"Event type '{event_type}' not in handler filter: {handler.event_types}"
            )
            return event
        
        # Update handler statistics
        async with self._lock:
            handler.last_triggered = datetime.utcnow()
            handler.trigger_count += 1
        
        # Route to handler (async, non-blocking)
        try:
            await handler.handler(event)
            
            processing_time = time.perf_counter() - start_time
            
            logger.info(
                "Webhook processed successfully",
                extra={
                    "endpoint": endpoint,
                    "event_id": event_id,
                    "event_type": event_type,
                    "verified": verified,
                    "processing_time": processing_time,
                }
            )
        
        except Exception as e:
            logger.error(
                "Webhook handler failed",
                extra={
                    "endpoint": endpoint,
                    "event_id": event_id,
                    "event_type": event_type,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise WebhookError(f"Handler failed for endpoint {endpoint}: {e}") from e
        
        return event
    
    async def close(self) -> None:
        """Close webhook manager and cleanup resources.
        
        Example:
            >>> await manager.close()
        """
        self._handlers.clear()
        logger.info("WebhookManager closed")
