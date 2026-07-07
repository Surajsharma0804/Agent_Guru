"""LLM Reasoning Core.

Implements reasoning plan generation with:
- ReasoningPlan and ReasoningStep data structures
- LLM-based plan generation with streaming support
- JSON schema validation with retry logic
- Step limit enforcement (max 5 steps)
- Conversation context integration

Performance Target: <2s end-to-end reasoning (95th percentile)
"""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from Agent_Guru.reasoning.llm.models import LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.prompts import ConversationContext, ReasoningPrompts

@dataclass
class ReasoningStep:
    """Single step in a reasoning plan."""

    step_id: int
    description: str
    tool_id: str
    parameters: dict[str, Any]
    estimated_duration_seconds: float
    requires_confirmation: bool = False
    depends_on: list[int] = field(default_factory=list)  # For parallel execution

    def __post_init__(self):
        """Validate step fields."""
        if self.step_id < 1:
            msg = f"step_id must be >= 1, got {self.step_id}"
            raise ValueError(msg)
        if not self.description:
            msg = "description cannot be empty"
            raise ValueError(msg)
        if not self.tool_id:
            msg = "tool_id cannot be empty"
            raise ValueError(msg)
        if self.estimated_duration_seconds <= 0:
            msg = f"estimated_duration_seconds must be positive, got {self.estimated_duration_seconds}"
            raise ValueError(
                msg,
            )
        # Validate depends_on references
        for dep_id in self.depends_on:
            if dep_id >= self.step_id:
                msg = f"Step {self.step_id} cannot depend on step {dep_id} (must be earlier step)"
                raise ValueError(
                    msg,
                )

@dataclass
class ReasoningPlan:
    """Complete reasoning plan with multiple steps."""

    goal: str
    steps: list[ReasoningStep]
    reasoning: str
    confidence: float
    requires_confirmation: bool = False
    estimated_duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def __post_init__(self):
        """Validate plan fields."""
        if not self.goal:
            msg = "goal cannot be empty"
            raise ValueError(msg)
        if not self.steps:
            msg = "steps cannot be empty"
            raise ValueError(msg)
        if len(self.steps) > 5:
            msg = f"Maximum 5 steps allowed, got {len(self.steps)}"
            raise ValueError(msg)
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"confidence must be 0.0-1.0, got {self.confidence}"
            raise ValueError(msg)
        if not self.reasoning:
            msg = "reasoning cannot be empty"
            raise ValueError(msg)

        # Calculate total estimated duration if not provided
        if self.estimated_duration_seconds == 0.0:
            self.estimated_duration_seconds = sum(
                step.estimated_duration_seconds for step in self.steps
            )

        # Check if any step requires confirmation
        if not self.requires_confirmation:
            self.requires_confirmation = any(step.requires_confirmation for step in self.steps)

class ReasoningPlanGenerator:
    """Generates reasoning plans using LLM.

    Supports:
    - Single-step and multi-step plan generation
    - JSON schema validation with retry logic
    - Step limit enforcement (max 5 steps)
    - Streaming support for responsiveness
    - Conversation context integration
    """

    MAX_STEPS = 5
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 5.0

    def __init__(self, llm_provider: Any) -> None:
        """Initialize reasoning plan generator.

        Args:
            llm_provider: LLM provider instance (OpenAI, Anthropic, etc.)

        """
        self.llm_provider = llm_provider

    async def generate_plan(
        self,
        user_input: str,
        intent_type: str,
        entities: dict[str, Any],
        available_tools: list[str],
        context: ConversationContext | None = None,
    ) -> ReasoningPlan:
        """Generate reasoning plan for user request.

        Args:
            user_input: User's request
            intent_type: Detected intent type
            entities: Extracted entities
            available_tools: List of available tool names
            context: Optional conversation context

        Returns:
            ReasoningPlan with validated steps

        Raises:
            ValueError: If plan generation fails after max retries
            asyncio.TimeoutError: If generation exceeds timeout

        """
        # Determine if single-step or multi-step
        is_multi_step = self._is_multi_step_task(intent_type, entities)

        # Format prompt
        if is_multi_step:
            prompt = ReasoningPrompts.format_multi_step_prompt(
                user_input=user_input,
                intent_type=intent_type,
                entities=entities,
                available_tools=available_tools,
                context=context,
            )
        else:
            prompt = ReasoningPrompts.format_single_step_prompt(
                user_input=user_input,
                intent_type=intent_type,
                entities=entities,
                available_tools=available_tools,
                context=context,
            )

        # Add system prompt
        full_prompt = f"{ReasoningPrompts.SYSTEM_PROMPT}\n\n{prompt}"

        # Generate plan with retry logic
        for _attempt in range(self.MAX_RETRIES):
            try:
                # Call LLM with timeout — single wait_for here; _call_llm must NOT
                # add its own wait_for so the cancellation propagates cleanly.
                response = await asyncio.wait_for(
                    self._call_llm(full_prompt),
                    timeout=self.TIMEOUT_SECONDS,
                )

                # Parse and validate response
                plan = self._parse_response(response.text)

                # Enforce step limit
                if len(plan.steps) > self.MAX_STEPS:
                    msg = f"Plan has {len(plan.steps)} steps, maximum is {self.MAX_STEPS}"
                    raise ValueError(
                        msg,
                    )

                return plan

            except asyncio.CancelledError as e:
                # Outer wait_for cancelled the inner coroutine — treat as timeout
                msg = f"LLM plan generation timed out after {self.TIMEOUT_SECONDS}s"
                raise TimeoutError(
                    msg,
                ) from e
                # Retry with more explicit instructions
        msg = "Failed to generate plan"
        raise ValueError(msg)

    async def stream_plan(
        self,
        user_input: str,
        intent_type: str,
        entities: dict[str, Any],
        available_tools: list[str],
        context: ConversationContext | None = None,
    ) -> AsyncIterator[ReasoningStep]:
        """Stream reasoning plan generation step-by-step.

        Args:
            user_input: User's request
            intent_type: Detected intent type
            entities: Extracted entities
            available_tools: List of available tool names
            context: Optional conversation context

        Yields:
            ReasoningStep objects as they are generated

        """
        # For now, generate full plan and yield steps
        # TODO: Implement true streaming with LLM streaming API
        plan = await self.generate_plan(user_input, intent_type, entities, available_tools, context)

        for step in plan.steps:
            yield step
            await asyncio.sleep(0.1)  # Simulate streaming delay

    async def _call_llm(self, prompt: str) -> LLMResponse:
        """Call LLM provider with prompt.

        The caller (generate_plan) wraps this in asyncio.wait_for, so we do NOT
        add a second wait_for here — nested wait_for calls cause CancelledError
        to propagate incorrectly when the outer timeout fires.

        Args:
            prompt: Formatted prompt

        Returns:
            LLM response

        """
        request = LLMRequest(
            prompt=prompt,
            temperature=0.7,
            top_p=0.9,
            max_tokens=512,
            stop_sequences=["```"],
        )

        return await self.llm_provider.generate(request)

    def _parse_response(self, response_text: str) -> ReasoningPlan:
        """Parse LLM response into ReasoningPlan.

        Args:
            response_text: Raw LLM response

        Returns:
            Validated ReasoningPlan

        Raises:
            ValueError: If response is invalid
            json.JSONDecodeError: If response is not valid JSON

        """
        # Extract JSON from response (may be wrapped in markdown)
        json_text = self._extract_json(response_text)

        # Parse JSON
        data = json.loads(json_text)

        # Validate required fields
        if "goal" not in data:
            msg = "Missing required field: goal"
            raise ValueError(msg)
        if "steps" not in data:
            msg = "Missing required field: steps"
            raise ValueError(msg)
        if "reasoning" not in data:
            msg = "Missing required field: reasoning"
            raise ValueError(msg)
        if "confidence" not in data:
            msg = "Missing required field: confidence"
            raise ValueError(msg)

        # Parse steps
        steps = []
        for i, step_data in enumerate(data["steps"], 1):
            step = ReasoningStep(
                step_id=step_data.get("step_id", i),
                description=step_data["description"],
                tool_id=step_data["tool_id"],
                parameters=step_data.get("parameters", {}),
                estimated_duration_seconds=step_data.get("estimated_duration_seconds", 1.0),
                requires_confirmation=step_data.get("requires_confirmation", False),
                depends_on=step_data.get("depends_on", []),
            )
            steps.append(step)

        # Create plan
        return ReasoningPlan(
            goal=data["goal"],
            steps=steps,
            reasoning=data["reasoning"],
            confidence=data["confidence"],
        )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text (may be wrapped in markdown code blocks).

        Args:
            text: Text containing JSON

        Returns:
            Extracted JSON string

        """
        # Remove markdown code blocks if present
        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```

        text = text.removesuffix("```")  # Remove trailing ```

        return text.strip()

    def _is_multi_step_task(self, intent_type: str, entities: dict[str, Any]) -> bool:
        """Determine if task requires multiple steps.

        Args:
            intent_type: Intent type
            entities: Extracted entities

        Returns:
            True if multi-step task

        """
        # Simple heuristic: multi_step_task intent or multiple entities
        if intent_type == "multi_step_task":
            return True

        # Check for multiple distinct actions in entities
        action_indicators = ["and", "then", "after", "before"]
        return any(indicator in str(entities).lower() for indicator in action_indicators)

class ReasoningPlanValidator:
    """Validates reasoning plans before execution.

    Checks:
    - Tool references are valid
    - Required parameters are present
    - No circular dependencies
    - Duration within timeout limits
    """

    def __init__(self, tool_registry: dict[str, Any], max_duration_seconds: float = 30.0) -> None:
        """Initialize plan validator.

        Args:
            tool_registry: Dictionary of available tools {tool_id: tool_spec}
            max_duration_seconds: Maximum allowed plan duration

        """
        self.tool_registry = tool_registry
        self.max_duration_seconds = max_duration_seconds

    def validate(self, plan: ReasoningPlan) -> tuple[bool, str | None]:
        """Validate reasoning plan.

        Args:
            plan: Plan to validate

        Returns:
            Tuple of (is_valid, error_message)

        """
        # Check duration limit
        if plan.estimated_duration_seconds > self.max_duration_seconds:
            return (
                False,
                f"Plan duration {plan.estimated_duration_seconds}s exceeds limit {self.max_duration_seconds}s",
            )

        # Validate each step
        for step in plan.steps:
            # Check tool exists
            if step.tool_id not in self.tool_registry:
                return False, f"Unknown tool: {step.tool_id}"

            # Check required parameters
            tool_spec = self.tool_registry[step.tool_id]
            required_params = tool_spec.get("required_parameters", [])
            for param in required_params:
                if param not in step.parameters:
                    return False, f"Missing required parameter '{param}' for tool {step.tool_id}"

        # Check for circular dependencies
        if self._has_circular_dependencies(plan.steps):
            return False, "Plan contains circular dependencies"

        return True, None

    def _has_circular_dependencies(self, steps: list[ReasoningStep]) -> bool:
        """Check if steps have circular dependencies.

        Args:
            steps: List of reasoning steps

        Returns:
            True if circular dependencies exist

        """
        # Build dependency graph
        graph: dict[int, list[int]] = {}
        for step in steps:
            graph[step.step_id] = step.depends_on

        # Check for cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        return any(step.step_id not in visited and has_cycle(step.step_id) for step in steps)
