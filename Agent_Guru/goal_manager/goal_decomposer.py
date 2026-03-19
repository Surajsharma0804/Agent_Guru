"""
Goal Decomposer - LLM-powered goal decomposition.

Decomposes high-level goals into actionable sub-goals using LLM Runtime.

Time Complexity: O(1) per decomposition (LLM call dominates)
Space Complexity: O(n) where n is number of sub-goals generated

Performance Targets:
- LLM response time: <5s (95th percentile)
- Sub-goal generation: 3-7 sub-goals per goal
- Retry attempts: Max 3 with exponential backoff

Author: Agent_Guru Team
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any

from Agent_Guru.goal_manager.models import Goal, GoalStatus
from Agent_Guru.goal_manager.exceptions import DecompositionError
from Agent_Guru.goal_manager.logging_config import get_logger

# Initialize structured logger
logger = get_logger(__name__)


class GoalDecomposer:
    """
    Decomposes high-level goals into actionable sub-goals using LLM.
    
    Uses LLM Runtime to analyze goals and generate sub-goals with:
    - Context from Memory System (similar past goals)
    - Structured prompts for consistent output
    - Retry logic with exponential backoff
    - Quality validation (3-7 sub-goals, meaningful descriptions)
    
    Example:
        >>> decomposer = GoalDecomposer(llm_runtime, memory_system)
        >>> parent_goal = Goal(description="Build user authentication")
        >>> sub_goals = await decomposer.decompose(parent_goal)
        >>> print(f"Generated {len(sub_goals)} sub-goals")
    """
    
    def __init__(self, llm_runtime: Any, memory_system: Any):
        """
        Initialize with LLM Runtime and Memory System.
        
        Args:
            llm_runtime: LLM Runtime instance with generate() method
            memory_system: Memory System instance with query_similar() method
        """
        self.llm_runtime = llm_runtime
        self.memory_system = memory_system
    
    async def decompose(self, goal: Goal) -> List[Goal]:
        """
        Decompose goal into sub-goals.
        
        Process:
        1. Query Memory System for relevant context
        2. Build structured decomposition prompt
        3. Call LLM with retry logic (exponential backoff)
        4. Parse JSON response into Goal objects
        5. Validate sub-goals meet quality criteria
        
        Args:
            goal: Goal to decompose
            
        Returns:
            List of sub-goals (3-7 goals typically)
            
        Raises:
            DecompositionError: If LLM fails after retries or returns invalid response
        """
        # Get relevant context from memory
        context = await self._get_context(goal)
        
        # Build decomposition prompt
        prompt = self._build_prompt(goal, context)
        
        # Call LLM with retry logic
        response = await self._call_llm_with_retry(prompt)
        
        # Parse response into sub-goals
        sub_goals = self._parse_response(response, goal)
        
        # Validate sub-goals
        self._validate_subgoals(sub_goals)
        
        return sub_goals
    
    async def _get_context(self, goal: Goal) -> Dict[str, Any]:
        """
        Get relevant context from Memory System.
        
        Queries for similar past goals to provide context for decomposition.
        
        Args:
            goal: Goal to get context for
            
        Returns:
            Dictionary with similar_goals and metadata
        """
        try:
            # Query memory for similar past goals
            similar_goals = await self.memory_system.query_similar(
                query=goal.description,
                limit=5,
                metadata_filter={"type": "goal"}
            )
            
            return {
                "similar_goals": [g.content for g in similar_goals],
                "metadata": goal.metadata
            }
        except Exception:
            # If memory query fails, continue with empty context
            return {
                "similar_goals": [],
                "metadata": goal.metadata
            }
    
    def _build_prompt(self, goal: Goal, context: Dict[str, Any]) -> str:
        """
        Build decomposition prompt for LLM.
        
        Creates a structured prompt that:
        - Explains the task clearly
        - Provides goal description and context
        - Specifies output format (JSON array)
        - Sets quality criteria (3-7 sub-goals, specific, actionable)
        
        Args:
            goal: Goal to decompose
            context: Context from Memory System
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are an expert at breaking down high-level goals into actionable sub-goals.

Goal: {goal.description}

Context:
{json.dumps(context, indent=2)}

Please decompose this goal into 3-7 specific, actionable sub-goals. Each sub-goal should:
1. Be more specific than the parent goal
2. Be independently executable
3. Contribute to achieving the parent goal
4. Be testable (clear success criteria)

Return your response as a JSON array of objects with this structure:
[
  {{
    "description": "Sub-goal description",
    "rationale": "Why this sub-goal is needed",
    "estimated_complexity": "low|medium|high"
  }}
]

Sub-goals:"""
        
        return prompt
    
    async def _call_llm_with_retry(
        self,
        prompt: str,
        max_retries: int = 3
    ) -> str:
        """
        Call LLM with exponential backoff retry.
        
        Retry strategy:
        - Attempt 1: Immediate
        - Attempt 2: Wait 1s (2^0)
        - Attempt 3: Wait 2s (2^1)
        - Attempt 4: Wait 4s (2^2)
        
        Args:
            prompt: Prompt to send to LLM
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            LLM response string
            
        Raises:
            DecompositionError: If all retries fail
        """
        for attempt in range(max_retries):
            try:
                response = await self.llm_runtime.generate(
                    prompt=prompt,
                    max_tokens=2000,
                    temperature=0.7
                )
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        "llm_decomposition_failed",
                        goal_id=None,  # Not available in this context
                        operation="decompose",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    raise DecompositionError(
                        f"LLM failed after {max_retries} attempts: {e}"
                    )
                
                # Log retry attempt
                logger.warning(
                    "llm_decomposition_retry",
                    operation="decompose",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay_seconds=2 ** attempt,
                    error=str(e)
                )
                
                # Exponential backoff: 2^attempt seconds
                delay = 2 ** attempt
                await asyncio.sleep(delay)
        
        # Should never reach here, but for type safety
        raise DecompositionError("Unexpected error in retry logic")
    
    def _parse_response(self, response: str, parent_goal: Goal) -> List[Goal]:
        """
        Parse LLM response into Goal objects.
        
        Extracts JSON array from response and creates Goal objects with:
        - Unique IDs
        - Parent reference
        - Metadata from LLM response
        - Same priority as parent
        
        Args:
            response: LLM response string
            parent_goal: Parent goal for reference
            
        Returns:
            List of Goal objects
            
        Raises:
            DecompositionError: If response cannot be parsed
        """
        try:
            # Extract JSON from response (find first [ to last ])
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error(
                    "llm_response_parse_failed",
                    goal_id=parent_goal.id,
                    operation="parse_response",
                    error="No JSON array found in LLM response",
                    response_preview=response[:200] if len(response) > 200 else response
                )
                raise DecompositionError("No JSON array found in LLM response")
            
            json_str = response[json_start:json_end]
            sub_goals_data = json.loads(json_str)
            
            # Create Goal objects
            sub_goals = []
            for data in sub_goals_data:
                sub_goal = Goal(
                    id=str(uuid.uuid4()),
                    description=data["description"],
                    status=GoalStatus.PENDING,
                    priority=parent_goal.priority,
                    progress=0.0,
                    created_at=datetime.now(),
                    started_at=None,
                    completed_at=None,
                    parent_id=parent_goal.id,
                    sub_goal_ids=[],
                    dependency_ids=[],
                    metadata={
                        "rationale": data.get("rationale", ""),
                        "estimated_complexity": data.get("estimated_complexity", "medium"),
                        "generated_by": "llm_decomposer"
                    },
                    error_message=None
                )
                sub_goals.append(sub_goal)
            
            return sub_goals
        
        except json.JSONDecodeError as e:
            logger.error(
                "llm_response_json_decode_failed",
                goal_id=parent_goal.id,
                operation="parse_response",
                error=str(e),
                error_type="JSONDecodeError"
            )
            raise DecompositionError(f"Failed to parse JSON from LLM response: {e}")
        except KeyError as e:
            logger.error(
                "llm_response_missing_field",
                goal_id=parent_goal.id,
                operation="parse_response",
                error=str(e),
                error_type="KeyError"
            )
            raise DecompositionError(f"Missing required field in LLM response: {e}")
        except Exception as e:
            logger.error(
                "llm_response_parse_error",
                goal_id=parent_goal.id,
                operation="parse_response",
                error=str(e),
                error_type=type(e).__name__
            )
            raise DecompositionError(f"Failed to parse LLM response: {e}")
    
    def _validate_subgoals(self, sub_goals: List[Goal]) -> None:
        """
        Validate sub-goals meet quality criteria.
        
        Quality criteria:
        - At least 1 sub-goal generated
        - At most 10 sub-goals (to prevent over-decomposition)
        - Each description is at least 10 characters
        - Recommended: 3-7 sub-goals for optimal granularity
        
        Args:
            sub_goals: List of sub-goals to validate
            
        Raises:
            DecompositionError: If validation fails
        """
        if not sub_goals:
            logger.error(
                "subgoal_validation_failed",
                operation="validate",
                error="No sub-goals generated"
            )
            raise DecompositionError("No sub-goals generated")
        
        if len(sub_goals) > 10:
            logger.error(
                "subgoal_validation_failed",
                operation="validate",
                error=f"Too many sub-goals: {len(sub_goals)}",
                count=len(sub_goals),
                max_allowed=10
            )
            raise DecompositionError(
                f"Too many sub-goals generated ({len(sub_goals)}), maximum is 10"
            )
        
        for sub_goal in sub_goals:
            if len(sub_goal.description) < 10:
                logger.error(
                    "subgoal_validation_failed",
                    operation="validate",
                    error="Sub-goal description too short",
                    description=sub_goal.description,
                    length=len(sub_goal.description),
                    min_length=10
                )
                raise DecompositionError(
                    f"Sub-goal description too short: '{sub_goal.description}' "
                    f"(minimum 10 characters)"
                )

