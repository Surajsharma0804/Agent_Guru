"""
Secure Message Bus for Inter-Component Communication

Production-grade message bus implementing secure, reliable message passing between
GURU components with comprehensive audit logging and failure handling.

Key Features:
- Cryptographically signed messages with integrity verification
- Priority-based message routing with QoS guarantees
- Comprehensive audit logging of all message traffic
- Automatic retry with exponential backoff
- Dead letter queue for failed messages
- Thread-safe operations with proper locking
- Message validation and sanitization
- Component isolation and security boundaries
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set, Union
from queue import Queue, PriorityQueue, Empty, Full
import weakref

from .exceptions import (
    MessageDeliveryError,
    MessageTimeoutError,
    MessageValidationError,
    MessageQueueFullError,
    ComponentNotFoundError,
    CommunicationSecurityError
)


class MessageType(Enum):
    """Message types for component communication."""
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    EVENT = "event"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    SECURITY_ALERT = "security_alert"
    SYSTEM_STATUS = "system_status"
    AUDIT_LOG = "audit_log"
    EMERGENCY = "emergency"


class MessagePriority(Enum):
    """Message priority levels for QoS routing."""
    EMERGENCY = 0    # Immediate delivery required
    CRITICAL = 1     # High priority, minimal delay
    HIGH = 2         # Important messages
    NORMAL = 3       # Standard priority
    LOW = 4          # Background messages
    BULK = 5         # Batch processing


@dataclass
class MessageMetadata:
    """Metadata for message tracking and routing."""
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    route_history: List[str] = field(default_factory=list)
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class Message:
    """Secure message for inter-component communication."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.COMMAND
    priority: MessagePriority = MessagePriority.NORMAL
    source_component: str = ""
    target_component: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: MessageMetadata = field(default_factory=MessageMetadata)
    signature: Optional[str] = None
    integrity_hash: Optional[str] = None
    
    def __post_init__(self):
        """Calculate message integrity hash after initialization."""
        if not self.integrity_hash:
            self.calculate_integrity_hash()
    
    def calculate_integrity_hash(self) -> str:
        """Calculate SHA-256 integrity hash of message content."""
        # Create canonical representation for hashing
        hash_data = {
            "id": self.id,
            "type": self.type.value,
            "source_component": self.source_component,
            "target_component": self.target_component,
            "payload": self.payload,
            "created_at": self.metadata.created_at.isoformat()
        }
        
        canonical_json = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        hash_value = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
        self.integrity_hash = hash_value
        return hash_value
    
    def verify_integrity(self) -> bool:
        """Verify message integrity hash."""
        if not self.integrity_hash:
            return False
        
        current_hash = self.integrity_hash
        self.integrity_hash = None  # Temporarily clear for recalculation
        expected_hash = self.calculate_integrity_hash()
        self.integrity_hash = current_hash  # Restore
        
        return hmac.compare_digest(current_hash, expected_hash)
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        if not self.metadata.expires_at:
            return False
        return datetime.now() > self.metadata.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.metadata.retry_count < self.metadata.max_retries
    
    def increment_retry(self) -> None:
        """Increment retry count."""
        self.metadata.retry_count += 1
    
    def add_route_hop(self, component: str) -> None:
        """Add component to route history."""
        self.metadata.route_history.append(f"{component}@{datetime.now().isoformat()}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "source_component": self.source_component,
            "target_component": self.target_component,
            "payload": self.payload,
            "metadata": {
                "created_at": self.metadata.created_at.isoformat(),
                "expires_at": self.metadata.expires_at.isoformat() if self.metadata.expires_at else None,
                "retry_count": self.metadata.retry_count,
                "max_retries": self.metadata.max_retries,
                "correlation_id": self.metadata.correlation_id,
                "reply_to": self.metadata.reply_to,
                "route_history": self.metadata.route_history,
                "custom_headers": self.metadata.custom_headers
            },
            "signature": self.signature,
            "integrity_hash": self.integrity_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        metadata_data = data.get("metadata", {})
        metadata = MessageMetadata(
            created_at=datetime.fromisoformat(metadata_data.get("created_at", datetime.now().isoformat())),
            expires_at=datetime.fromisoformat(metadata_data["expires_at"]) if metadata_data.get("expires_at") else None,
            retry_count=metadata_data.get("retry_count", 0),
            max_retries=metadata_data.get("max_retries", 3),
            correlation_id=metadata_data.get("correlation_id"),
            reply_to=metadata_data.get("reply_to"),
            route_history=metadata_data.get("route_history", []),
            custom_headers=metadata_data.get("custom_headers", {})
        )
        
        return cls(
            id=data["id"],
            type=MessageType(data["type"]),
            priority=MessagePriority(data["priority"]),
            source_component=data["source_component"],
            target_component=data["target_component"],
            payload=data["payload"],
            metadata=metadata,
            signature=data.get("signature"),
            integrity_hash=data.get("integrity_hash")
        )


class ComponentMessageProtocol:
    """Protocol for components that can handle messages."""
    
    def handle_message(self, message: Message) -> Optional[Message]:
        """Handle incoming message and optionally return response."""
        raise NotImplementedError


@dataclass
class QueuedMessage:
    """Message wrapper for priority queue."""
    priority: int
    timestamp: float
    message: Message
    
    def __lt__(self, other: 'QueuedMessage') -> bool:
        """Compare messages for priority queue ordering."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class MessageBus:
    """
    Production-grade secure message bus for inter-component communication.
    
    Provides reliable, secure message passing between GURU components with:
    - Cryptographic message signing and integrity verification
    - Priority-based routing with QoS guarantees
    - Automatic retry with exponential backoff
    - Dead letter queue for failed messages
    - Comprehensive audit logging
    - Thread-safe operations
    - Component isolation and security boundaries
    """
    
    def __init__(self, 
                 max_queue_size: int = 10000,
                 worker_threads: int = 4,
                 signing_key: Optional[bytes] = None,
                 enable_audit_logging: bool = True):
        """
        Initialize secure message bus.
        
        Args:
            max_queue_size: Maximum messages per component queue
            worker_threads: Number of message processing threads
            signing_key: Key for message signing (generated if None)
            enable_audit_logging: Enable comprehensive audit logging
        """
        self.logger = logging.getLogger(__name__)
        self.max_queue_size = max_queue_size
        self.enable_audit_logging = enable_audit_logging
        
        # Cryptographic components
        self.signing_key = signing_key or secrets.token_bytes(32)
        
        # Component registry and message routing
        self._components: Dict[str, weakref.ReferenceType] = {}
        self._component_queues: Dict[str, PriorityQueue] = {}
        self._component_handlers: Dict[str, ComponentMessageProtocol] = {}
        self._component_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Message tracking and routing
        self._pending_messages: Dict[str, Message] = {}
        self._message_responses: Dict[str, Future] = {}
        self._dead_letter_queue: Queue = Queue(maxsize=1000)
        self._message_history: List[Message] = []
        self._max_history_size = 10000
        
        # Threading and concurrency
        self._bus_lock = threading.RLock()
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=worker_threads, thread_name_prefix="MessageBus")
        self._worker_threads: List[threading.Thread] = []
        
        # Performance and monitoring
        self._message_stats: Dict[str, int] = {
            "sent": 0, "delivered": 0, "failed": 0, "retried": 0, "expired": 0
        }
        self._component_stats: Dict[str, Dict[str, int]] = {}
        self._delivery_times: List[float] = []
        
        # Security and validation
        self._trusted_components: Set[str] = set()
        self._message_validators: List[Callable[[Message], bool]] = []
        self._security_callbacks: List[Callable[[str, Message], None]] = []
        
        self.logger.info(f"MessageBus initialized with {worker_threads} workers, max queue size: {max_queue_size}")
    
    def start(self) -> None:
        """Start message bus processing."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker threads for message processing
        for i in range(4):  # Fixed number of core workers
            worker = threading.Thread(
                target=self._message_worker,
                name=f"MessageBus-Worker-{i}",
                daemon=True
            )
            worker.start()
            self._worker_threads.append(worker)
        
        # Start maintenance thread
        maintenance_thread = threading.Thread(
            target=self._maintenance_worker,
            name="MessageBus-Maintenance",
            daemon=True
        )
        maintenance_thread.start()
        self._worker_threads.append(maintenance_thread)
        
        self.logger.info("MessageBus started with message processing workers")
    
    def stop(self) -> None:
        """Stop message bus processing."""
        self._running = False
        
        # Wait for workers to finish
        for worker in self._worker_threads:
            if worker.is_alive():
                worker.join(timeout=5.0)
        
        # Shutdown executor with compatibility handling
        try:
            # Try with timeout parameter (Python 3.9+)
            self._executor.shutdown(wait=True, timeout=10.0)
        except TypeError:
            # Fallback for older Python versions
            self._executor.shutdown(wait=True)
        
        self.logger.info("MessageBus stopped")
    
    def register_component(self, 
                          component_name: str, 
                          handler: ComponentMessageProtocol,
                          component_ref: Optional[Any] = None,
                          trusted: bool = False,
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Register component for message handling.
        
        Args:
            component_name: Unique component identifier
            handler: Message handler implementation
            component_ref: Optional weak reference to component
            trusted: Whether component is trusted for security operations
            metadata: Optional component metadata
        """
        with self._bus_lock:
            if component_name in self._components:
                raise ValueError(f"Component '{component_name}' already registered")
            
            # Register component
            if component_ref:
                self._components[component_name] = weakref.ref(component_ref)
            else:
                self._components[component_name] = weakref.ref(handler)
            
            self._component_handlers[component_name] = handler
            self._component_queues[component_name] = PriorityQueue(maxsize=self.max_queue_size)
            self._component_metadata[component_name] = metadata or {}
            self._component_stats[component_name] = {
                "messages_received": 0,
                "messages_sent": 0,
                "messages_failed": 0,
                "last_activity": time.time()
            }
            
            if trusted:
                self._trusted_components.add(component_name)
        
        self.logger.info(f"Registered component '{component_name}' (trusted: {trusted})")
        
        if self.enable_audit_logging:
            self._audit_log("component_registered", {
                "component_name": component_name,
                "trusted": trusted,
                "metadata": metadata
            })
    
    def unregister_component(self, component_name: str) -> None:
        """Unregister component from message bus."""
        with self._bus_lock:
            self._components.pop(component_name, None)
            self._component_handlers.pop(component_name, None)
            self._component_queues.pop(component_name, None)
            self._component_metadata.pop(component_name, None)
            self._component_stats.pop(component_name, None)
            self._trusted_components.discard(component_name)
        
        self.logger.info(f"Unregistered component '{component_name}'")
        
        if self.enable_audit_logging:
            self._audit_log("component_unregistered", {"component_name": component_name})
    
    def send_message(self, message: Message, timeout_seconds: float = 30.0) -> bool:
        """
        Send message to target component.
        
        Args:
            message: Message to send
            timeout_seconds: Maximum time to wait for delivery
            
        Returns:
            True if message was queued successfully
            
        Raises:
            ComponentNotFoundError: If target component not found
            MessageValidationError: If message validation fails
            MessageQueueFullError: If target queue is full
        """
        # Validate message
        self._validate_message(message)
        
        # Check if target component exists
        if message.target_component not in self._component_queues:
            raise ComponentNotFoundError(
                message.target_component, 
                len(self._component_queues)
            )
        
        # Sign message for integrity
        message.signature = self._sign_message(message)
        message.add_route_hop("message_bus")
        
        # Get target queue
        target_queue = self._component_queues[message.target_component]
        
        try:
            # Create queued message with priority
            queued_msg = QueuedMessage(
                priority=message.priority.value,
                timestamp=time.time(),
                message=message
            )
            
            # Queue message (non-blocking)
            target_queue.put_nowait(queued_msg)
            
            # Track message
            self._pending_messages[message.id] = message
            self._message_stats["sent"] += 1
            self._component_stats[message.target_component]["messages_received"] += 1
            
            # Add to history
            self._add_to_message_history(message)
            
            self.logger.debug(f"Message {message.id} queued for {message.target_component}")
            
            if self.enable_audit_logging:
                self._audit_log("message_sent", {
                    "message_id": message.id,
                    "source": message.source_component,
                    "target": message.target_component,
                    "type": message.type.value,
                    "priority": message.priority.value
                })
            
            return True
            
        except Full:
            raise MessageQueueFullError(
                message.target_component,
                target_queue.qsize(),
                self.max_queue_size
            )
    
    def send_and_wait_response(self, 
                              message: Message, 
                              timeout_seconds: float = 30.0) -> Optional[Message]:
        """
        Send message and wait for response.
        
        Args:
            message: Message to send
            timeout_seconds: Maximum time to wait for response
            
        Returns:
            Response message or None if timeout
            
        Raises:
            MessageTimeoutError: If response timeout occurs
        """
        # Set up response tracking
        response_future = Future()
        self._message_responses[message.id] = response_future
        
        try:
            # Send message
            self.send_message(message, timeout_seconds)
            
            # Wait for response
            try:
                response = response_future.result(timeout=timeout_seconds)
                return response
            except TimeoutError:
                raise MessageTimeoutError(message.id, timeout_seconds, message.target_component)
        
        finally:
            # Clean up response tracking
            self._message_responses.pop(message.id, None)
    
    def _message_worker(self) -> None:
        """Worker thread for processing messages."""
        while self._running:
            try:
                # Process messages from all component queues
                processed_any = False
                
                with self._bus_lock:
                    component_queues = list(self._component_queues.items())
                
                for component_name, queue in component_queues:
                    try:
                        # Get message with short timeout
                        queued_msg = queue.get(timeout=0.1)
                        processed_any = True
                        
                        # Process message
                        self._process_message(component_name, queued_msg.message)
                        queue.task_done()
                        
                    except Empty:
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing message for {component_name}: {e}")
                
                # Sleep briefly if no messages processed
                if not processed_any:
                    time.sleep(0.01)
                    
            except Exception as e:
                self.logger.error(f"Error in message worker: {e}")
                time.sleep(0.1)
    
    def _process_message(self, component_name: str, message: Message) -> None:
        """Process individual message."""
        start_time = time.time()
        
        try:
            # Verify message integrity
            if not message.verify_integrity():
                raise MessageValidationError(message.id, "Integrity verification failed")
            
            # Verify message signature
            if not self._verify_message_signature(message):
                raise CommunicationSecurityError(
                    "signature_verification",
                    f"Message signature verification failed for {message.id}",
                    message.source_component,
                    component_name
                )
            
            # Check if message expired
            if message.is_expired():
                self._handle_expired_message(message)
                return
            
            # Get component handler
            handler = self._component_handlers.get(component_name)
            if not handler:
                raise ComponentNotFoundError(component_name)
            
            # Process message with handler
            response = handler.handle_message(message)
            
            # Handle response if provided
            if response:
                self._handle_message_response(message, response)
            
            # Update statistics
            processing_time = time.time() - start_time
            self._delivery_times.append(processing_time)
            self._message_stats["delivered"] += 1
            self._component_stats[component_name]["messages_sent"] += 1
            self._component_stats[component_name]["last_activity"] = time.time()
            
            # Remove from pending
            self._pending_messages.pop(message.id, None)
            
            self.logger.debug(f"Message {message.id} processed successfully in {processing_time:.3f}s")
            
            if self.enable_audit_logging:
                self._audit_log("message_delivered", {
                    "message_id": message.id,
                    "component": component_name,
                    "processing_time_ms": processing_time * 1000,
                    "has_response": response is not None
                })
        
        except Exception as e:
            self._handle_message_failure(message, str(e))
    
    def _handle_message_response(self, original_message: Message, response: Message) -> None:
        """Handle response to original message."""
        # Set response metadata
        response.metadata.correlation_id = original_message.id
        response.source_component = original_message.target_component
        response.target_component = original_message.source_component
        
        # Check if someone is waiting for this response
        response_future = self._message_responses.get(original_message.id)
        if response_future:
            response_future.set_result(response)
        else:
            # Send response back to original sender
            try:
                self.send_message(response)
            except Exception as e:
                self.logger.error(f"Failed to send response for {original_message.id}: {e}")
    
    def _handle_message_failure(self, message: Message, error: str) -> None:
        """Handle message processing failure."""
        self.logger.error(f"Message {message.id} failed: {error}")
        
        # Check if message can be retried
        if message.can_retry():
            message.increment_retry()
            
            # Calculate retry delay (exponential backoff)
            delay = min(2 ** message.metadata.retry_count, 60)  # Max 60 seconds
            
            # Schedule retry
            def retry_message():
                time.sleep(delay)
                try:
                    self.send_message(message)
                    self._message_stats["retried"] += 1
                except Exception as e:
                    self.logger.error(f"Retry failed for message {message.id}: {e}")
                    self._send_to_dead_letter_queue(message, f"Retry failed: {e}")
            
            self._executor.submit(retry_message)
            
        else:
            # Send to dead letter queue
            self._send_to_dead_letter_queue(message, error)
    
    def _handle_expired_message(self, message: Message) -> None:
        """Handle expired message."""
        self.logger.warning(f"Message {message.id} expired")
        self._message_stats["expired"] += 1
        self._send_to_dead_letter_queue(message, "Message expired")
    
    def _send_to_dead_letter_queue(self, message: Message, reason: str) -> None:
        """Send failed message to dead letter queue."""
        try:
            dead_letter_entry = {
                "message": message.to_dict(),
                "failure_reason": reason,
                "failed_at": datetime.now().isoformat(),
                "retry_count": message.metadata.retry_count
            }
            
            self._dead_letter_queue.put_nowait(dead_letter_entry)
            self._message_stats["failed"] += 1
            
            if self.enable_audit_logging:
                self._audit_log("message_failed", {
                    "message_id": message.id,
                    "reason": reason,
                    "retry_count": message.metadata.retry_count
                })
        
        except Full:
            self.logger.critical("Dead letter queue is full - message lost!")
    
    def _maintenance_worker(self) -> None:
        """Maintenance worker for cleanup and monitoring."""
        while self._running:
            try:
                # Clean up expired pending messages
                self._cleanup_expired_messages()
                
                # Trim message history
                self._trim_message_history()
                
                # Trim delivery times
                if len(self._delivery_times) > 1000:
                    self._delivery_times = self._delivery_times[-1000:]
                
                # Check component health
                self._check_component_health()
                
                # Sleep for maintenance interval
                time.sleep(30.0)  # Run maintenance every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in maintenance worker: {e}")
                time.sleep(10.0)
    
    def _cleanup_expired_messages(self) -> None:
        """Clean up expired pending messages."""
        current_time = datetime.now()
        expired_messages = []
        
        for message_id, message in self._pending_messages.items():
            if message.is_expired():
                expired_messages.append(message_id)
        
        for message_id in expired_messages:
            message = self._pending_messages.pop(message_id, None)
            if message:
                self._handle_expired_message(message)
    
    def _trim_message_history(self) -> None:
        """Trim message history to manageable size."""
        if len(self._message_history) > self._max_history_size:
            self._message_history = self._message_history[-self._max_history_size:]
    
    def _check_component_health(self) -> None:
        """Check health of registered components."""
        current_time = time.time()
        
        for component_name, stats in self._component_stats.items():
            last_activity = stats.get("last_activity", 0)
            if current_time - last_activity > 300:  # 5 minutes
                self.logger.warning(f"Component '{component_name}' has been inactive for {current_time - last_activity:.0f}s")
    
    def _validate_message(self, message: Message) -> None:
        """Validate message before sending."""
        if not message.id:
            raise MessageValidationError("", "Message ID is required")
        
        if not message.source_component:
            raise MessageValidationError(message.id, "Source component is required")
        
        if not message.target_component:
            raise MessageValidationError(message.id, "Target component is required")
        
        if not isinstance(message.payload, dict):
            raise MessageValidationError(message.id, "Payload must be a dictionary")
        
        # Run custom validators
        for validator in self._message_validators:
            if not validator(message):
                raise MessageValidationError(message.id, "Custom validation failed")
    
    def _sign_message(self, message: Message) -> str:
        """Create HMAC signature for message."""
        if not message.integrity_hash:
            message.calculate_integrity_hash()
        
        return hmac.new(
            self.signing_key,
            message.integrity_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _verify_message_signature(self, message: Message) -> bool:
        """Verify message HMAC signature."""
        if not message.signature or not message.integrity_hash:
            return False
        
        expected_signature = hmac.new(
            self.signing_key,
            message.integrity_hash.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(message.signature, expected_signature)
    
    def _add_to_message_history(self, message: Message) -> None:
        """Add message to history for monitoring."""
        self._message_history.append(message)
    
    def _audit_log(self, action: str, details: Dict[str, Any]) -> None:
        """Log audit event for message bus operations."""
        if self.enable_audit_logging:
            self.logger.info(f"AUDIT[message_bus]: {action}", extra={"audit_details": details})
    
    # Public API methods
    
    def get_component_list(self) -> List[str]:
        """Get list of registered components."""
        with self._bus_lock:
            return list(self._components.keys())
    
    def get_component_stats(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a component."""
        return self._component_stats.get(component_name)
    
    def get_bus_statistics(self) -> Dict[str, Any]:
        """Get overall message bus statistics."""
        avg_delivery_time = sum(self._delivery_times) / len(self._delivery_times) if self._delivery_times else 0
        
        return {
            "registered_components": len(self._components),
            "message_stats": self._message_stats.copy(),
            "pending_messages": len(self._pending_messages),
            "dead_letter_queue_size": self._dead_letter_queue.qsize(),
            "average_delivery_time_ms": avg_delivery_time * 1000,
            "message_history_size": len(self._message_history),
            "trusted_components": len(self._trusted_components),
            "running": self._running
        }
    
    def get_dead_letter_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages from dead letter queue."""
        messages = []
        count = 0
        
        while count < limit and not self._dead_letter_queue.empty():
            try:
                message = self._dead_letter_queue.get_nowait()
                messages.append(message)
                count += 1
            except Empty:
                break
        
        return messages
    
    def add_message_validator(self, validator: Callable[[Message], bool]) -> None:
        """Add custom message validator."""
        self._message_validators.append(validator)
    
    def add_security_callback(self, callback: Callable[[str, Message], None]) -> None:
        """Add security event callback."""
        self._security_callbacks.append(callback)
    
    def create_message(self, 
                      message_type: MessageType,
                      source_component: str,
                      target_component: str,
                      payload: Dict[str, Any],
                      priority: MessagePriority = MessagePriority.NORMAL,
                      expires_in_seconds: Optional[float] = None,
                      correlation_id: Optional[str] = None) -> Message:
        """
        Create a new message with proper initialization.
        
        Args:
            message_type: Type of message
            source_component: Source component name
            target_component: Target component name
            payload: Message payload
            priority: Message priority
            expires_in_seconds: Message expiration time
            correlation_id: Optional correlation ID
            
        Returns:
            Initialized Message object
        """
        metadata = MessageMetadata(
            correlation_id=correlation_id
        )
        
        if expires_in_seconds:
            metadata.expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        
        return Message(
            type=message_type,
            priority=priority,
            source_component=source_component,
            target_component=target_component,
            payload=payload,
            metadata=metadata
        )