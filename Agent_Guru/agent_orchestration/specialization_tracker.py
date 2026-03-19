"""
Specialization Tracker for Agent Orchestration System.

Tracks and updates agent specialization based on task success patterns using
exponential moving average for specialization scores.

Performance Characteristics:
- Time Complexity: O(1) per specialization update
- Space Complexity: O(n) where n = number of agents
- Update Latency: <1ms per operation

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

from typing import Dict, List
from Agent_Guru.agent_orchestration.storage import AgentStorage
from Agent_Guru.agent_orchestration.models import Agent


class SpecializationTracker:
    """
    Tracks and updates agent specialization based on performance.
    
    Uses exponential moving average (EMA) for specialization scores to:
    - Emphasize recent performance over historical
    - Smooth out noise from individual task outcomes
    - Enable continuous learning and adaptation
    
    Specialization Score Range: 0.0 - 1.0
    - 0.0: No specialization (never succeeded)
    - 0.5: Neutral (default for new task types)
    - 1.0: Perfect specialization (always succeeds)
    
    Score Update Formula:
        new_score = (1 - α) * old_score + α * reward
        where α = learning_rate, reward = 1.0 (success) or 0.0 (failure)
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
    """
    
    def __init__(
        self,
        storage: AgentStorage,
        learning_rate: float = 0.1,
        min_specialization_threshold: float = 0.3,
        high_specialization_threshold: float = 0.8,
    ):
        """
        Initialize specialization tracker.
        
        Args:
            storage: Agent storage backend for persistence
            learning_rate: Learning rate for EMA updates (0.0-1.0)
                Higher values = faster adaptation to recent performance
                Lower values = more stable, less reactive to noise
            min_specialization_threshold: Minimum score to maintain specialization
                Scores below this are removed to prevent clutter
            high_specialization_threshold: Score for high specialization marking
                Agents above this are considered domain experts
        
        Raises:
            ValueError: If parameters are out of valid ranges
        
        Time Complexity: O(1)
        """
        # Validate parameters
        if not 0.0 < learning_rate <= 1.0:
            raise ValueError(
                f"learning_rate must be in (0.0, 1.0], got {learning_rate}"
            )
        
        if not 0.0 <= min_specialization_threshold <= 1.0:
            raise ValueError(
                f"min_specialization_threshold must be in [0.0, 1.0], "
                f"got {min_specialization_threshold}"
            )
        
        if not 0.0 <= high_specialization_threshold <= 1.0:
            raise ValueError(
                f"high_specialization_threshold must be in [0.0, 1.0], "
                f"got {high_specialization_threshold}"
            )
        
        if min_specialization_threshold >= high_specialization_threshold:
            raise ValueError(
                f"min_specialization_threshold ({min_specialization_threshold}) "
                f"must be less than high_specialization_threshold "
                f"({high_specialization_threshold})"
            )
        
        self.storage = storage
        self.learning_rate = learning_rate
        self.min_threshold = min_specialization_threshold
        self.high_threshold = high_specialization_threshold
    
    async def update_specialization(
        self,
        agent_id: str,
        task_type: str,
        success: bool,
    ) -> Dict[str, float]:
        """
        Update agent specialization based on task outcome.
        
        Uses exponential moving average to update specialization score:
        - Success: Increases score toward 1.0
        - Failure: Decreases score toward 0.0
        - Removes specialization if score falls below minimum threshold
        
        Args:
            agent_id: Agent identifier
            task_type: Type of task completed
            success: Whether task succeeded
        
        Returns:
            Updated specialization scores for agent
        
        Time Complexity: O(1)
        Performance Target: <1ms
        
        Validates: Requirements 2.1, 2.2, 2.3
        """
        # Get agent
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return {}
        
        # Get current specialization score (default 0.5 for new task types)
        current_score = agent.specializations.get(task_type, 0.5)
        
        # Calculate reward (1.0 for success, 0.0 for failure)
        reward = 1.0 if success else 0.0
        
        # Update score using exponential moving average
        # new_score = (1 - α) * old_score + α * reward
        new_score = (1 - self.learning_rate) * current_score + self.learning_rate * reward
        
        # Update or remove specialization based on threshold
        if new_score >= self.min_threshold:
            agent.specializations[task_type] = new_score
        else:
            # Remove specialization if below threshold
            if task_type in agent.specializations:
                del agent.specializations[task_type]
        
        # Store updated agent
        await self.storage.update_agent(agent)
        
        return agent.specializations
    
    async def get_specialization_score(
        self,
        agent_id: str,
        task_type: str,
    ) -> float:
        """
        Get agent's specialization score for task type.
        
        Args:
            agent_id: Agent identifier
            task_type: Task type to query
        
        Returns:
            Specialization score (0.0-1.0), or 0.0 if no specialization
        
        Time Complexity: O(1)
        Performance Target: <1ms
        
        Validates: Requirement 2.5
        """
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return 0.0
        
        return agent.specializations.get(task_type, 0.0)
    
    async def is_highly_specialized(
        self,
        agent_id: str,
        task_type: str,
    ) -> bool:
        """
        Check if agent is highly specialized in task type.
        
        An agent is considered highly specialized if their score exceeds
        the high specialization threshold, indicating consistent success
        and domain expertise.
        
        Args:
            agent_id: Agent identifier
            task_type: Task type to check
        
        Returns:
            True if agent is highly specialized, False otherwise
        
        Time Complexity: O(1)
        Performance Target: <1ms
        
        Validates: Requirement 2.4
        """
        score = await self.get_specialization_score(agent_id, task_type)
        return score >= self.high_threshold
    
    async def get_top_specialists(
        self,
        task_type: str,
        limit: int = 5,
    ) -> List[Agent]:
        """
        Get top specialist agents for task type.
        
        Returns agents sorted by specialization score in descending order.
        Only includes agents with active specialization in the task type.
        
        Args:
            task_type: Task type to query
            limit: Maximum number of specialists to return
        
        Returns:
            List of top specialist agents (up to limit)
        
        Time Complexity: O(n log n) where n = number of active agents
        Performance Target: <10ms for 1000 agents
        
        Validates: Requirement 2.5
        """
        # Get all active agents
        all_agents = await self.storage.get_active_agents()
        
        # Filter agents with specialization in task type
        specialists = [
            (agent, agent.specializations.get(task_type, 0.0))
            for agent in all_agents
            if task_type in agent.specializations
        ]
        
        # Sort by specialization score descending
        specialists.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N agents
        return [agent for agent, score in specialists[:limit]]
    
    async def get_agent_specializations(
        self,
        agent_id: str,
    ) -> Dict[str, float]:
        """
        Get all specializations for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Dictionary mapping task types to specialization scores
        
        Time Complexity: O(1)
        """
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return {}
        
        return agent.specializations.copy()
    
    async def get_specialization_count(
        self,
        agent_id: str,
    ) -> int:
        """
        Get number of specializations for an agent.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Number of task types agent is specialized in
        
        Time Complexity: O(1)
        """
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return 0
        
        return len(agent.specializations)
    
    async def remove_specialization(
        self,
        agent_id: str,
        task_type: str,
    ) -> bool:
        """
        Manually remove a specialization from an agent.
        
        Useful for forcing re-learning or handling edge cases.
        
        Args:
            agent_id: Agent identifier
            task_type: Task type to remove
        
        Returns:
            True if specialization was removed, False if it didn't exist
        
        Time Complexity: O(1)
        """
        agent = await self.storage.get_agent(agent_id)
        if not agent:
            return False
        
        if task_type in agent.specializations:
            del agent.specializations[task_type]
            await self.storage.update_agent(agent)
            return True
        
        return False
