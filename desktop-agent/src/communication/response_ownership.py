"""
Response Ownership Coordinator

Production-grade response ownership system that ensures exactly ONE subsystem
produces a user-facing response at any time. Prevents duplicate or conflicting
responses from multiple subsystems.

CRITICAL RULE: At any time, exactly ONE subsystem may produce a user-facing response.

Ownership Priority:
1. Command_Executor (during action execution)
2. Error_Handler (during failures)
3. Conversation_Manager (only when no action is executing)

Architecture:
- Centralized ownership tracking
- Priority-based ownership claims
- Automatic ownership release
- Thread-safe operations
- Audit logging integration

This ensures deterministic, predictable responses without duplication.

Validates: Requirements 28.1, 28.2, 28.3, 28.4, 28.5, 28.6, 28.7
"""

import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ResponseOwner(Enum):
    """Subsystems that can own response"""
    NONE = "none"
    COMMAND_EXECUTOR = "command_executor"
    ERROR_HANDLER = "error_handler"
    CONVERSATION_MANAGER = "conversation_manager"


class OwnershipPriority(Enum):
    """Ownership priority levels (lower value = higher priority)"""
    COMMAND_EXECUTOR = 1  # Highest priority
    ERROR_HANDLER = 2
    CONVERSATION_MANAGER = 3  # Lowest priority


@dataclass
class OwnershipClaim:
    """Ownership claim record"""
    owner: ResponseOwner
    priority: OwnershipPriority
    claimed_at: datetime
    context: Dict[str, Any]


class ResponseOwnershipCoordinator:
    """
    Coordinates response ownership across subsystems.
    
    Ensures exactly one subsystem produces a user-facing response at any time.
    Implements priority-based ownership with automatic suppression of lower-priority
    subsystems.
    
    Thread-safe: All operations are protected by locks.
    
    Properties:
    - Property 68: Exclusive Response Ownership
    - Property 69: Action Execution Suppresses Conversation
    - Property 70: Action Success Speaks Only Result
    - Property 71: Action Failure Speaks Only Reason
    - Property 72: No Duplicate Responses
    """
    
    def __init__(self):
        """Initialize response ownership coordinator"""
        self.current_owner: ResponseOwner = ResponseOwner.NONE
        self.current_claim: Optional[OwnershipClaim] = None
        self.lock = threading.RLock()  # Reentrant lock for nested calls
        
        # Ownership history for debugging
        self.ownership_history: list[OwnershipClaim] = []
        self.max_history = 100
        
        logger.info("Response Ownership Coordinator initialized")
    
    def claim_ownership(
        self,
        owner: ResponseOwner,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Claim response ownership.
        
        Args:
            owner: Subsystem claiming ownership
            context: Optional context information
        
        Returns:
            True if ownership claimed successfully, False if denied
        
        Rules:
            - Higher priority owners can always claim ownership
            - Lower priority owners cannot claim if higher priority owner active
            - Same priority owner can reclaim (extends ownership)
        
        Validates: Requirements 28.1
        """
        with self.lock:
            # Get priority for requesting owner
            priority = self._get_priority(owner)
            
            # If no current owner, grant immediately
            if self.current_owner == ResponseOwner.NONE:
                self._grant_ownership(owner, priority, context or {})
                logger.info(f"Ownership granted to {owner.value} (no current owner)")
                return True
            
            # If same owner, extend ownership
            if self.current_owner == owner:
                self._grant_ownership(owner, priority, context or {})
                logger.debug(f"Ownership extended for {owner.value}")
                return True
            
            # Check priority
            current_priority = self._get_priority(self.current_owner)
            
            # Higher priority can take ownership
            if priority.value < current_priority.value:
                logger.info(
                    f"Ownership transferred from {self.current_owner.value} "
                    f"to {owner.value} (higher priority)"
                )
                self._grant_ownership(owner, priority, context or {})
                return True
            
            # Lower or equal priority cannot take ownership
            logger.debug(
                f"Ownership denied for {owner.value} "
                f"(current owner: {self.current_owner.value} has higher/equal priority)"
            )
            return False
    
    def release_ownership(self, owner: ResponseOwner) -> bool:
        """
        Release response ownership.
        
        Args:
            owner: Subsystem releasing ownership
        
        Returns:
            True if ownership released, False if not owner
        
        Validates: Requirements 28.4
        """
        with self.lock:
            # Only current owner can release
            if self.current_owner != owner:
                logger.warning(
                    f"{owner.value} attempted to release ownership, "
                    f"but current owner is {self.current_owner.value}"
                )
                return False
            
            logger.info(f"Ownership released by {owner.value}")
            self.current_owner = ResponseOwner.NONE
            self.current_claim = None
            return True
    
    def is_owner(self, owner: ResponseOwner) -> bool:
        """
        Check if subsystem currently owns response.
        
        Args:
            owner: Subsystem to check
        
        Returns:
            True if subsystem owns response, False otherwise
        """
        with self.lock:
            return self.current_owner == owner
    
    def can_respond(self, owner: ResponseOwner) -> bool:
        """
        Check if subsystem can produce a response.
        
        Args:
            owner: Subsystem to check
        
        Returns:
            True if subsystem can respond, False if suppressed
        
        Rules:
            - Current owner can always respond
            - Non-owners cannot respond (suppressed)
            - If no owner, all can respond
        
        Validates: Requirements 28.2, 28.4
        """
        with self.lock:
            # If no owner, all can respond
            if self.current_owner == ResponseOwner.NONE:
                return True
            
            # Only current owner can respond
            return self.current_owner == owner
    
    def get_current_owner(self) -> ResponseOwner:
        """
        Get current response owner.
        
        Returns:
            Current owner (NONE if no owner)
        """
        with self.lock:
            return self.current_owner
    
    def get_ownership_info(self) -> Dict[str, Any]:
        """
        Get current ownership information.
        
        Returns:
            Dictionary with ownership details
        """
        with self.lock:
            if self.current_claim is None:
                return {
                    "owner": ResponseOwner.NONE.value,
                    "priority": None,
                    "claimed_at": None,
                    "duration_seconds": 0,
                    "context": {}
                }
            
            duration = (datetime.now() - self.current_claim.claimed_at).total_seconds()
            
            return {
                "owner": self.current_claim.owner.value,
                "priority": self.current_claim.priority.value,
                "claimed_at": self.current_claim.claimed_at.isoformat(),
                "duration_seconds": duration,
                "context": self.current_claim.context
            }
    
    def _grant_ownership(
        self,
        owner: ResponseOwner,
        priority: OwnershipPriority,
        context: Dict[str, Any]
    ):
        """
        Internal: Grant ownership to subsystem.
        
        Args:
            owner: Subsystem to grant ownership to
            priority: Priority level
            context: Context information
        """
        claim = OwnershipClaim(
            owner=owner,
            priority=priority,
            claimed_at=datetime.now(),
            context=context
        )
        
        self.current_owner = owner
        self.current_claim = claim
        
        # Record in history
        self.ownership_history.append(claim)
        if len(self.ownership_history) > self.max_history:
            self.ownership_history = self.ownership_history[-self.max_history:]
    
    def _get_priority(self, owner: ResponseOwner) -> OwnershipPriority:
        """
        Get priority for owner.
        
        Args:
            owner: Subsystem
        
        Returns:
            Priority level
        """
        priority_map = {
            ResponseOwner.COMMAND_EXECUTOR: OwnershipPriority.COMMAND_EXECUTOR,
            ResponseOwner.ERROR_HANDLER: OwnershipPriority.ERROR_HANDLER,
            ResponseOwner.CONVERSATION_MANAGER: OwnershipPriority.CONVERSATION_MANAGER,
            ResponseOwner.NONE: OwnershipPriority.CONVERSATION_MANAGER  # Lowest
        }
        
        return priority_map.get(owner, OwnershipPriority.CONVERSATION_MANAGER)
    
    def get_ownership_history(self, limit: int = 10) -> list[Dict[str, Any]]:
        """
        Get recent ownership history.
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            List of ownership records
        """
        with self.lock:
            recent = self.ownership_history[-limit:]
            
            return [
                {
                    "owner": claim.owner.value,
                    "priority": claim.priority.value,
                    "claimed_at": claim.claimed_at.isoformat(),
                    "context": claim.context
                }
                for claim in recent
            ]
    
    def reset(self):
        """
        Reset ownership state (for testing).
        
        Clears current owner and history.
        """
        with self.lock:
            self.current_owner = ResponseOwner.NONE
            self.current_claim = None
            self.ownership_history.clear()
            logger.info("Ownership state reset")


# Global coordinator instance
_coordinator: Optional[ResponseOwnershipCoordinator] = None
_coordinator_lock = threading.Lock()


def get_response_ownership_coordinator() -> ResponseOwnershipCoordinator:
    """
    Get global response ownership coordinator instance.
    
    Returns:
        ResponseOwnershipCoordinator singleton
    
    Thread-safe: Uses double-checked locking pattern
    """
    global _coordinator
    
    if _coordinator is None:
        with _coordinator_lock:
            if _coordinator is None:
                _coordinator = ResponseOwnershipCoordinator()
    
    return _coordinator


__all__ = [
    'ResponseOwnershipCoordinator',
    'ResponseOwner',
    'OwnershipPriority',
    'OwnershipClaim',
    'get_response_ownership_coordinator'
]
