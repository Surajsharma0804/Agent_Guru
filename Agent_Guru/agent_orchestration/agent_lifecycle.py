"""
Agent Lifecycle Manager for Agent Orchestration System.

Manages agent creation, retirement, and lifecycle transitions with strict
enforcement of constraints:
- No pre-defined role names (researcher, coder, planner, etc.)
- Unique agent identifiers
- Performance-based retirement
- Complete evolution event tracking

Time Complexity:
- create_agent: O(1)
- retire_agent: O(1)
- get_active_agents: O(n) where n is active agents

Space Complexity: O(1) per operation (storage handles persistence)

Performance Targets:
- Agent creation: <10ms
- Agent retirement: <5ms
- Active agent retrieval: <10ms

Author: Agent Guru Team
Date: 2024
Version: 1.0.0

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4, 5.5
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from Agent_Guru.agent_orchestration.models import Agent, AgentStatus
from Agent_Guru.agent_orchestration.storage import AgentStorage


class AgentLifecycleManager:
    """
    Manages agent creation, retirement, and lifecycle transitions.
    
    Enforces critical constraints:
    - No pre-defined role names (researcher, coder, planner, etc.)
    - Unique agent identifiers (UUID)
    - Performance-based retirement decisions
    - Complete evolution event tracking for GitHub sync
    
    Design Decisions:
    - Forbidden role names enforced at creation time
    - Evolution events recorded for all lifecycle changes
    - Agent status transitions follow defined state machine
    - Storage layer handles persistence and querying
    
    Performance Characteristics:
    - Time Complexity: O(1) for create/retire operations
    - Space Complexity: O(1) per operation
    - Memory: <1KB per agent (excluding history)
    
    Example:
        >>> storage = AgentStorage("agents.db")
        >>> manager = AgentLifecycleManager(storage)
        >>> agent = await manager.create_agent(
        ...     task_requirements={"task_type": "analysis"},
        ...     initial_capabilities={"data_analysis": 0.5}
        ... )
        >>> print(f"Created agent: {agent.id}")
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4, 5.5
    """
    
    # Forbidden role names that violate the dynamic agent principle
    # These represent static roles, not task-specific capabilities
    FORBIDDEN_ROLE_NAMES = {
        "researcher",
        "coder",
        "planner",
        "writer",
        "analyst",
        "reviewer",
        "tester",
        "designer",
        "architect",
        "developer",
        "engineer",
        "programmer",
        "debugger",
        "optimizer",
        "documenter",
    }
    
    def __init__(self, storage: AgentStorage):
        """
        Initialize agent lifecycle manager.
        
        Args:
            storage: Storage backend for agent persistence
        
        Time Complexity: O(1)
        """
        self.storage = storage
    
    async def create_agent(
        self,
        task_requirements: Dict[str, Any],
        initial_capabilities: Dict[str, float],
    ) -> Agent:
        """
        Create new agent based on task requirements.
        
        Creates a new agent with unique identifier and initial capabilities.
        Validates that capabilities do not contain forbidden role names.
        Records creation event for evolution tracking.
        
        Args:
            task_requirements: Requirements that triggered agent creation
            initial_capabilities: Initial capability set (capability -> proficiency)
        
        Returns:
            Created agent with ACTIVE status
        
        Raises:
            ValueError: If capabilities contain forbidden role names
        
        Time Complexity: O(1)
        Performance Target: <10ms
        
        Example:
            >>> agent = await manager.create_agent(
            ...     task_requirements={"task_type": "data_analysis"},
            ...     initial_capabilities={"statistical_analysis": 0.6}
            ... )
        
        Validates: Requirements 1.1, 1.2, 1.3, 1.4
        """
        # Validate no forbidden role names (Requirement 1.3)
        self._validate_no_forbidden_names(initial_capabilities)
        
        # Create agent with unique identifier (Requirement 1.2)
        agent = Agent(
            id=str(uuid4()),
            status=AgentStatus.CREATED,
            capabilities=initial_capabilities,
            specializations={},  # Empty initially, built through experience
            performance_history=[],
            created_at=datetime.now(),
            last_active=datetime.now(),
            total_tasks=0,
            successful_tasks=0,
            metadata={
                "created_for_task": task_requirements,
                "creation_reason": "no_suitable_agent",
            },
        )
        
        # Store agent (Requirement 1.1)
        await self.storage.store_agent(agent)
        
        # Record creation event (Requirement 1.4)
        await self._record_evolution_event(
            event_type="creation",
            agent_ids=[agent.id],
            reason="task_requirements",
            details={
                "task_requirements": task_requirements,
                "initial_capabilities": initial_capabilities,
            },
        )
        
        # Transition to active status
        agent.status = AgentStatus.ACTIVE
        await self.storage.update_agent(agent)
        
        return agent
    
    async def retire_agent(
        self,
        agent_id: str,
        reason: str,
    ) -> None:
        """
        Retire agent due to underperformance or redundancy.
        
        Transitions agent through RETIRING -> RETIRED states.
        Records retirement event with final performance metrics.
        Performance history is preserved in storage for analysis.
        
        Args:
            agent_id: Agent identifier to retire
            reason: Retirement reason (e.g., "underperformance", "merged", "redundant")
        
        Time Complexity: O(1)
        Performance Target: <5ms
        
        Example:
            >>> await manager.retire_agent(
            ...     agent_id="agent-123",
            ...     reason="underperformance"
            ... )
        
        Validates: Requirements 5.1, 5.2, 5.3, 5.4
        """
        # Get agent
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return
        
        # Transition to retiring (Requirement 5.1)
        agent.status = AgentStatus.RETIRING
        await self.storage.update_agent(agent)
        
        # Calculate final metrics
        success_rate = agent.success_rate
        
        # Record retirement event (Requirement 5.3)
        await self._record_evolution_event(
            event_type="retirement",
            agent_ids=[agent_id],
            reason=reason,
            details={
                "total_tasks": agent.total_tasks,
                "successful_tasks": agent.successful_tasks,
                "success_rate": success_rate,
                "final_specializations": agent.specializations,
                "final_capabilities": agent.capabilities,
            },
        )
        
        # Transition to retired (Requirement 5.1)
        agent.status = AgentStatus.RETIRED
        await self.storage.update_agent(agent)
        
        # Note: Performance history is NOT deleted (Requirement 5.4)
        # It remains in storage for analysis and learning
    
    async def get_active_agents(self) -> List[Agent]:
        """
        Get all active agents.
        
        Returns:
            List of agents with ACTIVE status
        
        Time Complexity: O(n) where n is active agents
        Performance Target: <10ms
        
        Example:
            >>> agents = await manager.get_active_agents()
            >>> print(f"Active agents: {len(agents)}")
        
        Validates: Requirements 1.1, 1.2
        """
        return await self.storage.get_active_agents()
    
    async def _record_evolution_event(
        self,
        event_type: str,
        agent_ids: List[str],
        reason: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Record evolution event for GitHub sync and analysis.
        
        Evolution events track all significant changes in agent population:
        - creation: New agent created
        - merge: Agents merged into one
        - split: Agent split into multiple
        - retirement: Agent retired
        
        Args:
            event_type: Type of evolution event
            agent_ids: Agent IDs involved in event
            reason: Reason for event
            details: Additional event details
        
        Time Complexity: O(1)
        
        Validates: Requirements 1.4, 3.5, 4.4, 5.3
        """
        event = {
            "id": str(uuid4()),
            "event_type": event_type,
            "agent_ids": agent_ids,
            "reason": reason,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
        
        await self.storage.store_evolution_event(event)
    
    def _validate_no_forbidden_names(
        self,
        capabilities: Dict[str, float],
    ) -> None:
        """
        Validate that capabilities do not contain forbidden role names.
        
        Forbidden names represent static roles (researcher, coder, planner)
        which violate the dynamic agent principle. Agents should have
        task-specific capabilities, not pre-defined roles.
        
        Args:
            capabilities: Capability dictionary to validate
        
        Raises:
            ValueError: If any capability name is a forbidden role name
        
        Time Complexity: O(n) where n is number of capabilities
        
        Example:
            >>> # Valid - task-specific capabilities
            >>> manager._validate_no_forbidden_names({
            ...     "data_analysis": 0.7,
            ...     "statistical_modeling": 0.6
            ... })
            
            >>> # Invalid - forbidden role name
            >>> manager._validate_no_forbidden_names({
            ...     "researcher": 0.8  # Raises ValueError
            ... })
        
        Validates: Requirement 1.3
        """
        for capability_name in capabilities.keys():
            # Check if capability name is a forbidden role
            if capability_name.lower() in self.FORBIDDEN_ROLE_NAMES:
                raise ValueError(
                    f"Forbidden role name '{capability_name}' in capabilities. "
                    f"Use task-specific capability names instead. "
                    f"For example, instead of 'researcher', use 'data_analysis', "
                    f"'literature_review', or 'hypothesis_testing'."
                )
