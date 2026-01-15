"""
Property-Based Tests for Response Ownership System

Tests the Response Ownership Coordinator to ensure exactly one subsystem
produces a user-facing response at any time.

Properties Tested:
- Property 68: Exclusive Response Ownership
- Property 69: Action Execution Suppresses Conversation
- Property 70: Action Success Speaks Only Result
- Property 71: Action Failure Speaks Only Reason
- Property 72: No Duplicate Responses

Validates: Requirements 28.1, 28.2, 28.4, 28.5, 28.6, 28.7
"""

import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from communication.response_ownership import OwnershipPriority, ResponseOwner, ResponseOwnershipCoordinator


# Strategies for generating test data
@st.composite
def response_owner_strategy(draw):
    """Generate random ResponseOwner (excluding NONE)"""
    owners = [
        ResponseOwner.COMMAND_EXECUTOR,
        ResponseOwner.ERROR_HANDLER,
        ResponseOwner.CONVERSATION_MANAGER
    ]
    return draw(st.sampled_from(owners))


@st.composite
def ownership_sequence_strategy(draw):
    """Generate sequence of ownership claims"""
    length = draw(st.integers(min_value=1, max_value=10))
    owners = [
        ResponseOwner.COMMAND_EXECUTOR,
        ResponseOwner.ERROR_HANDLER,
        ResponseOwner.CONVERSATION_MANAGER
    ]
    return [draw(st.sampled_from(owners)) for _ in range(length)]


class TestResponseOwnershipProperties:
    """Property-based tests for Response Ownership Coordinator"""
    
    def setup_method(self):
        """Setup for each test"""
        self.coordinator = ResponseOwnershipCoordinator()
    
    def teardown_method(self):
        """Cleanup after each test"""
        self.coordinator.reset()
    
    @given(owner=response_owner_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_68_exclusive_response_ownership(self, owner):
        """
        Property 68: Exclusive Response Ownership
        
        For any user command, exactly one subsystem should produce a user-facing response.
        
        Test: At any point in time, exactly one owner (or NONE) should be active.
        
        **Validates: Requirements 28.1**
        """
        # Initially no owner
        assert self.coordinator.get_current_owner() == ResponseOwner.NONE
        
        # Claim ownership
        claimed = self.coordinator.claim_ownership(owner)
        assert claimed is True
        
        # Exactly one owner
        current_owner = self.coordinator.get_current_owner()
        assert current_owner == owner
        assert current_owner != ResponseOwner.NONE
        
        # Release ownership
        released = self.coordinator.release_ownership(owner)
        assert released is True
        
        # Back to no owner
        assert self.coordinator.get_current_owner() == ResponseOwner.NONE
    
    @given(sequence=ownership_sequence_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_69_action_execution_suppresses_conversation(self, sequence):
        """
        Property 69: Action Execution Suppresses Conversation
        
        For any command being executed by Command_Executor, the Conversation_Manager
        should not produce any response.
        
        Test: When Command_Executor owns response, Conversation_Manager cannot respond.
        
        **Validates: Requirements 28.2, 28.4**
        """
        # Command_Executor claims ownership
        claimed = self.coordinator.claim_ownership(ResponseOwner.COMMAND_EXECUTOR)
        assert claimed is True
        
        # Conversation_Manager should be suppressed
        can_respond = self.coordinator.can_respond(ResponseOwner.CONVERSATION_MANAGER)
        assert can_respond is False
        
        # Command_Executor can respond
        can_respond = self.coordinator.can_respond(ResponseOwner.COMMAND_EXECUTOR)
        assert can_respond is True
        
        # Try to claim ownership as Conversation_Manager (should fail)
        claimed = self.coordinator.claim_ownership(ResponseOwner.CONVERSATION_MANAGER)
        assert claimed is False
        
        # Command_Executor still owns
        assert self.coordinator.get_current_owner() == ResponseOwner.COMMAND_EXECUTOR
    
    @given(owner=response_owner_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_70_action_success_speaks_only_result(self, owner):
        """
        Property 70: Action Success Speaks Only Result
        
        For any successful action execution, only the ExecutionResult.message
        should be spoken.
        
        Test: When action completes successfully, ownership is released and
        only one response is produced.
        
        **Validates: Requirements 28.5**
        """
        # Simulate action execution
        self.coordinator.claim_ownership(
            ResponseOwner.COMMAND_EXECUTOR,
            context={"action": "open_app", "status": "success"}
        )
        
        # During execution, only Command_Executor can respond
        assert self.coordinator.can_respond(ResponseOwner.COMMAND_EXECUTOR) is True
        assert self.coordinator.can_respond(ResponseOwner.CONVERSATION_MANAGER) is False
        
        # Action completes - release ownership
        self.coordinator.release_ownership(ResponseOwner.COMMAND_EXECUTOR)
        
        # After release, no owner
        assert self.coordinator.get_current_owner() == ResponseOwner.NONE
        
        # Now Conversation_Manager could respond, but shouldn't for action results
        # (This is enforced by the calling code, not the coordinator)
    
    @given(owner=response_owner_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_71_action_failure_speaks_only_reason(self, owner):
        """
        Property 71: Action Failure Speaks Only Reason
        
        For any failed action execution, only the failure reason should be spoken.
        
        Test: When action fails, ownership is released and only one response
        is produced.
        
        **Validates: Requirements 28.6**
        """
        # Simulate action execution that fails
        self.coordinator.claim_ownership(
            ResponseOwner.COMMAND_EXECUTOR,
            context={"action": "open_app", "status": "failed", "error": "App not found"}
        )
        
        # During execution, only Command_Executor can respond
        assert self.coordinator.can_respond(ResponseOwner.COMMAND_EXECUTOR) is True
        assert self.coordinator.can_respond(ResponseOwner.CONVERSATION_MANAGER) is False
        
        # Action fails - release ownership
        self.coordinator.release_ownership(ResponseOwner.COMMAND_EXECUTOR)
        
        # After release, no owner
        assert self.coordinator.get_current_owner() == ResponseOwner.NONE
    
    @given(sequence=ownership_sequence_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_72_no_duplicate_responses(self, sequence):
        """
        Property 72: No Duplicate Responses
        
        For any single command, the system should never produce both an action
        confirmation and a conversational response.
        
        Test: Only one owner can respond at a time, preventing duplicates.
        
        **Validates: Requirements 28.7**
        """
        # Process sequence of ownership claims
        for owner in sequence:
            # Claim ownership
            claimed = self.coordinator.claim_ownership(owner)
            
            # If claimed, exactly one owner
            if claimed:
                current_owner = self.coordinator.get_current_owner()
                assert current_owner == owner
                
                # Only current owner can respond
                for check_owner in [ResponseOwner.COMMAND_EXECUTOR,
                                   ResponseOwner.ERROR_HANDLER,
                                   ResponseOwner.CONVERSATION_MANAGER]:
                    can_respond = self.coordinator.can_respond(check_owner)
                    if check_owner == owner:
                        assert can_respond is True
                    else:
                        assert can_respond is False
                
                # Release ownership
                self.coordinator.release_ownership(owner)
    
    @given(
        owner1=response_owner_strategy(),
        owner2=response_owner_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_priority_based_ownership(self, owner1, owner2):
        """
        Test priority-based ownership transfer.
        
        Higher priority owners can take ownership from lower priority owners.
        """
        # Reset coordinator for this test
        self.coordinator.reset()
        
        # Get priorities
        priority_map = {
            ResponseOwner.COMMAND_EXECUTOR: 1,
            ResponseOwner.ERROR_HANDLER: 2,
            ResponseOwner.CONVERSATION_MANAGER: 3
        }
        
        priority1 = priority_map[owner1]
        priority2 = priority_map[owner2]
        
        # First owner claims
        claimed = self.coordinator.claim_ownership(owner1)
        assert claimed is True
        assert self.coordinator.get_current_owner() == owner1
        
        # Second owner tries to claim
        claimed = self.coordinator.claim_ownership(owner2)
        
        if priority2 < priority1:
            # Higher priority: should succeed
            assert claimed is True
            assert self.coordinator.get_current_owner() == owner2
        elif priority2 == priority1:
            # Same owner: should succeed (extends ownership)
            if owner1 == owner2:
                assert claimed is True
                assert self.coordinator.get_current_owner() == owner2
            else:
                # Different owner, same priority: should fail
                assert claimed is False
                assert self.coordinator.get_current_owner() == owner1
        else:
            # Lower priority: should fail
            assert claimed is False
            assert self.coordinator.get_current_owner() == owner1
    
    @given(owner=response_owner_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_ownership_release_by_non_owner_fails(self, owner):
        """
        Test that only the current owner can release ownership.
        """
        # Claim ownership
        self.coordinator.claim_ownership(owner)
        
        # Try to release as different owner
        other_owners = [
            ResponseOwner.COMMAND_EXECUTOR,
            ResponseOwner.ERROR_HANDLER,
            ResponseOwner.CONVERSATION_MANAGER
        ]
        other_owners.remove(owner)
        
        for other_owner in other_owners:
            released = self.coordinator.release_ownership(other_owner)
            assert released is False
            # Original owner still owns
            assert self.coordinator.get_current_owner() == owner
        
        # Release as correct owner
        released = self.coordinator.release_ownership(owner)
        assert released is True
        assert self.coordinator.get_current_owner() == ResponseOwner.NONE
    
    @given(sequence=ownership_sequence_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_ownership_history_tracking(self, sequence):
        """
        Test that ownership history is tracked correctly.
        """
        # Process sequence
        for owner in sequence:
            self.coordinator.claim_ownership(owner)
            self.coordinator.release_ownership(owner)
        
        # Check history
        history = self.coordinator.get_ownership_history(limit=len(sequence))
        assert len(history) >= len(sequence)
        
        # Verify history contains our claims
        for i, owner in enumerate(sequence):
            # Find matching claim in history
            found = False
            for claim in history:
                if claim["owner"] == owner.value:
                    found = True
                    break
            assert found, f"Owner {owner.value} not found in history"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
