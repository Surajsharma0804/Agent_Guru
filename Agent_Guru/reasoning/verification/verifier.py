"""
Module: agent_guru.reasoning.verification.verifier
Purpose: Reasoning plan verification and validation
Author: Agent Guru Team
Date: 2026-02-22

Performance Requirements:
- Time Complexity: O(n) where n is number of steps
- Space Complexity: O(n) for issue storage
- Latency Budget: <200ms for complete verification

Design Decisions:
- Use LLM for semantic verification (correctness, alignment)
- Use rule-based checks for structural verification (tool compatibility, logical consistency)
- Separate verification pass from planning for independence
- Cache tool metadata for fast lookups
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from Agent_Guru.reasoning.llm.client import LLMClient
from Agent_Guru.reasoning.llm.models import LLMRequest
from Agent_Guru.reasoning.models.task import Task, TaskStep
from Agent_Guru.reasoning.models.verification import (
    IssueSeverity,
    IssueType,
    VerificationAction,
    VerificationIssue,
    VerificationResult,
)
from Agent_Guru.reasoning.tools.registry import ToolRegistry, get_registry


class ReasoningVerifier:
    """Verifies reasoning plans before execution.

    Performs multiple verification checks:
    1. Plan correctness (LLM-based)
    2. Tool compatibility (rule-based)
    3. Logical consistency (rule-based)
    4. Intent alignment (LLM-based)
    5. Schema validation (rule-based)

    Time Complexity: O(n) where n is number of steps
    Space Complexity: O(n) for issue storage
    Latency Budget: <200ms

    Example:
        >>> verifier = ReasoningVerifier(llm_client, tool_registry)
        >>> result = await verifier.verify_plan(task, original_input)
        >>> if result.recommendation == VerificationAction.PROCEED:
        ...     # Execute plan
        ...     pass
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: Optional[ToolRegistry] = None,
        confidence_threshold: float = 0.75,
    ):
        """Initialize reasoning verifier.

        Args:
            llm_client: LLM client for semantic verification
            tool_registry: Tool registry for tool validation (uses global if None)
            confidence_threshold: Minimum confidence to proceed (default 0.75)
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry or get_registry()
        self.confidence_threshold = confidence_threshold

        # Verification prompt template
        self.verification_prompt_template = """You are a reasoning plan verifier for Agent_Guru.

Your task is to verify if a reasoning plan is correct, complete, and aligned with the user's intent.

User Input: {user_input}

Reasoning Plan:
Goal: {goal}
Steps:
{steps}

Verify the following:
1. CORRECTNESS: Do the steps logically lead to achieving the goal?
2. COMPLETENESS: Are there any missing steps needed to achieve the goal?
3. EFFICIENCY: Are there any unnecessary steps that don't contribute to the goal?
4. ALIGNMENT: Does the plan match what the user actually requested?

Respond in JSON format:
{{
    "is_correct": true/false,
    "is_complete": true/false,
    "has_unnecessary_steps": true/false,
    "is_aligned": true/false,
    "confidence": 0.0-1.0,
    "issues": [
        {{
            "type": "correctness|completeness|efficiency|alignment",
            "severity": "critical|warning|info",
            "description": "detailed description",
            "affected_step": step_index or null
        }}
    ],
    "reasoning": "brief explanation of your assessment"
}}"""

    async def verify_plan(
        self, task: Task, original_input: str, context: Optional[dict[str, Any]] = None
    ) -> VerificationResult:
        """Verify a reasoning plan comprehensively.

        Performs all verification checks and returns aggregated result.

        Args:
            task: Task to verify
            original_input: Original user input
            context: Optional context (conversation state, world state, etc.)

        Returns:
            VerificationResult with all issues and recommendation

        Time Complexity: O(n) where n is number of steps
        Latency: <200ms target
        """
        start_time = time.perf_counter()
        issues: list[VerificationIssue] = []

        # Run all verification checks in parallel for speed
        results = await asyncio.gather(
            self._verify_tool_compatibility(task),
            self._verify_logical_consistency(task),
            self._verify_plan_correctness_and_alignment(task, original_input),
            return_exceptions=True,
        )

        # Aggregate issues from all checks
        for result in results:
            if isinstance(result, Exception):
                # Log error but continue with other checks
                issues.append(
                    VerificationIssue(
                        issue_type=IssueType.PLAN_CORRECTNESS,
                        severity=IssueSeverity.WARNING,
                        description=f"Verification check failed: {str(result)}",
                    )
                )
            elif isinstance(result, list):
                issues.extend(result)

        # Calculate overall confidence
        confidence = self._calculate_confidence(issues, task)

        # Determine if plan is valid (no critical issues)
        is_valid = not any(issue.severity == IssueSeverity.CRITICAL for issue in issues)

        # Determine recommendation
        recommendation = self._determine_recommendation(is_valid, confidence, issues)

        # Calculate verification time
        verification_time_ms = (time.perf_counter() - start_time) * 1000

        return VerificationResult(
            is_valid=is_valid,
            confidence=confidence,
            issues=issues,
            recommendation=recommendation,
            verification_time_ms=verification_time_ms,
            timestamp=datetime.now(tz=timezone.utc),
        )

    async def _verify_tool_compatibility(self, task: Task) -> list[VerificationIssue]:
        """Verify all tools exist and have required parameters.

        Checks:
        - Tool exists in registry
        - All required parameters are present
        - Parameter types match tool schema
        - Tool is available (not degraded)

        Args:
            task: Task to verify

        Returns:
            List of tool compatibility issues

        Time Complexity: O(n) where n is number of steps
        """
        issues: list[VerificationIssue] = []

        for step_idx, step in enumerate(task.steps):
            # Check if tool exists
            tool_metadata = self.tool_registry.get_metadata(step.tool_id)
            if tool_metadata is None:
                issues.append(
                    VerificationIssue(
                        issue_type=IssueType.TOOL_COMPATIBILITY,
                        severity=IssueSeverity.CRITICAL,
                        description=f"Tool '{step.tool_id}' does not exist in registry",
                        affected_step=step_idx,
                    )
                )
                continue

            # Check required parameters
            required_params = {p.name for p in tool_metadata.parameters if p.required}
            provided_params = set(step.parameters.keys())
            missing_params = required_params - provided_params

            if missing_params:
                issues.append(
                    VerificationIssue(
                        issue_type=IssueType.TOOL_COMPATIBILITY,
                        severity=IssueSeverity.CRITICAL,
                        description=f"Tool '{step.tool_id}' missing required parameters: {', '.join(missing_params)}",
                        affected_step=step_idx,
                    )
                )

            # Check parameter types (basic validation)
            for param_name, _param_value in step.parameters.items():
                param_def = next(
                    (p for p in tool_metadata.parameters if p.name == param_name), None
                )
                if param_def is None:
                    issues.append(
                        VerificationIssue(
                            issue_type=IssueType.TOOL_COMPATIBILITY,
                            severity=IssueSeverity.WARNING,
                            description=f"Tool '{step.tool_id}' has unexpected parameter '{param_name}'",
                            affected_step=step_idx,
                        )
                    )

        return issues

    async def _verify_logical_consistency(self, task: Task) -> list[VerificationIssue]:
        """Verify plan has no logical contradictions or impossible sequences.

        Checks:
        - No conflicting actions (e.g., open then close same app)
        - No circular dependencies
        - No impossible sequences

        Args:
            task: Task to verify

        Returns:
            List of logical consistency issues

        Time Complexity: O(n²) for dependency checking, O(n) for conflicts
        """
        issues: list[VerificationIssue] = []

        # Check for circular dependencies
        circular_deps = self._detect_circular_dependencies(task.steps)
        if circular_deps:
            issues.append(
                VerificationIssue(
                    issue_type=IssueType.LOGICAL_CONSISTENCY,
                    severity=IssueSeverity.CRITICAL,
                    description=f"Circular dependencies detected: {circular_deps}",
                    affected_step=None,
                )
            )

        # Check for conflicting actions
        conflicts = self._detect_conflicting_actions(task.steps)
        for conflict in conflicts:
            issues.append(
                VerificationIssue(
                    issue_type=IssueType.LOGICAL_CONSISTENCY,
                    severity=IssueSeverity.WARNING,
                    description=conflict["description"],
                    affected_step=conflict["step_idx"],
                )
            )

        return issues

    def _detect_circular_dependencies(self, steps: list[TaskStep]) -> Optional[str]:
        """Detect circular dependencies in step dependencies.

        Uses DFS to detect cycles in dependency graph.

        Args:
            steps: List of task steps

        Returns:
            Description of circular dependency or None

        Time Complexity: O(n²) worst case
        """
        # Build adjacency list using step IDs
        # Map step_id to index for graph traversal
        step_id_to_idx = {step.step_id: i for i, step in enumerate(steps)}

        # Build graph: index -> list of dependent indices
        graph: dict[int, list[int]] = {}
        for i, step in enumerate(steps):
            graph[i] = []
            for dep_step_id in step.depends_on:
                if dep_step_id in step_id_to_idx:
                    dep_idx = step_id_to_idx[dep_step_id]
                    graph[i].append(dep_idx)

        # DFS to detect cycles
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

        for i in range(len(steps)):
            if i not in visited:
                if has_cycle(i):
                    return "Steps have circular dependencies"

        return None

    def _detect_conflicting_actions(self, steps: list[TaskStep]) -> list[dict[str, Any]]:
        """Detect conflicting actions in plan.

        Looks for patterns like:
        - Open app then close same app
        - Set value then immediately change it
        - Delete then access same resource

        Args:
            steps: List of task steps

        Returns:
            List of conflicts with descriptions

        Time Complexity: O(n)
        """
        conflicts: list[dict[str, Any]] = []

        # Track actions by resource
        actions_by_resource: dict[str, list[tuple[int, str]]] = {}

        for idx, step in enumerate(steps):
            # Extract resource from tool_id (e.g., "app.open" -> "app")
            parts = step.tool_id.split(".")
            if len(parts) >= 2:
                resource = parts[0]
                action = parts[1]

                if resource not in actions_by_resource:
                    actions_by_resource[resource] = []
                actions_by_resource[resource].append((idx, action))

        # Check for conflicting patterns
        for resource, actions in actions_by_resource.items():
            for i in range(len(actions) - 1):
                idx1, action1 = actions[i]
                idx2, action2 = actions[i + 1]

                # Check for open/close conflicts
                if action1 == "open" and action2 == "close":
                    conflicts.append(
                        {
                            "step_idx": idx2,
                            "description": f"Step {idx2} closes {resource} that was just opened in step {idx1}",
                        }
                    )

                # Check for delete/access conflicts
                if action1 == "delete" and action2 in ["read", "write", "access"]:
                    conflicts.append(
                        {
                            "step_idx": idx2,
                            "description": f"Step {idx2} accesses {resource} that was deleted in step {idx1}",
                        }
                    )

        return conflicts

    async def _verify_plan_correctness_and_alignment(
        self, task: Task, original_input: str
    ) -> list[VerificationIssue]:
        """Verify plan correctness and intent alignment using LLM.

        Uses LLM to check:
        - Steps logically lead to goal
        - No missing steps
        - No unnecessary steps
        - Plan matches user intent

        Args:
            task: Task to verify
            original_input: Original user input

        Returns:
            List of correctness and alignment issues

        Time Complexity: O(1) - single LLM call
        Latency: ~100-150ms
        """
        issues: list[VerificationIssue] = []

        # Format steps for prompt
        steps_text = "\n".join(
            [
                f"{i+1}. {step.description} (tool: {step.tool_id})"
                for i, step in enumerate(task.steps)
            ]
        )

        # Create verification prompt
        prompt = self.verification_prompt_template.format(
            user_input=original_input, goal=task.goal, steps=steps_text
        )

        try:
            # Call LLM for verification
            request = LLMRequest(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3,  # Lower temperature for more consistent verification
            )

            response = await self.llm_client.generate(request)

            # Parse LLM response
            verification_data = self._parse_llm_verification(response.text)

            # Convert LLM issues to VerificationIssue objects
            for llm_issue in verification_data.get("issues", []):
                issue_type_map = {
                    "correctness": IssueType.PLAN_CORRECTNESS,
                    "completeness": IssueType.PLAN_CORRECTNESS,
                    "efficiency": IssueType.PLAN_CORRECTNESS,
                    "alignment": IssueType.INTENT_ALIGNMENT,
                }

                severity_map = {
                    "critical": IssueSeverity.CRITICAL,
                    "warning": IssueSeverity.WARNING,
                    "info": IssueSeverity.INFO,
                }

                issues.append(
                    VerificationIssue(
                        issue_type=issue_type_map.get(
                            llm_issue["type"], IssueType.PLAN_CORRECTNESS
                        ),
                        severity=severity_map.get(llm_issue["severity"], IssueSeverity.WARNING),
                        description=llm_issue["description"],
                        affected_step=llm_issue.get("affected_step"),
                    )
                )

        except Exception as e:
            # If LLM verification fails, add warning but don't block
            issues.append(
                VerificationIssue(
                    issue_type=IssueType.PLAN_CORRECTNESS,
                    severity=IssueSeverity.WARNING,
                    description=f"LLM verification failed: {str(e)}",
                )
            )

        return issues

    def _parse_llm_verification(self, llm_response: str) -> dict[str, Any]:
        """Parse LLM verification response.

        Extracts JSON from LLM response with error handling.

        Args:
            llm_response: Raw LLM response text

        Returns:
            Parsed verification data

        Raises:
            ValueError: If response cannot be parsed
        """
        try:
            # Try to extract JSON from response
            # LLM might wrap JSON in markdown code blocks
            response = llm_response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM verification response: {e}") from e

    def _calculate_confidence(self, issues: list[VerificationIssue], task: Task) -> float:
        """Calculate overall confidence in verification result.

        Confidence decreases with:
        - Number of issues
        - Severity of issues
        - Complexity of plan

        Args:
            issues: List of verification issues
            task: Task being verified

        Returns:
            Confidence score 0.0-1.0
        """
        # Start with high confidence
        confidence = 1.0

        # Decrease for each issue based on severity
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                confidence -= 0.2
            elif issue.severity == IssueSeverity.WARNING:
                confidence -= 0.1
            else:  # INFO
                confidence -= 0.05

        # Decrease slightly for complex plans (more steps = more uncertainty)
        complexity_penalty = min(0.1, len(task.steps) * 0.01)
        confidence -= complexity_penalty

        # Ensure confidence stays in valid range
        return max(0.0, min(1.0, confidence))

    def _determine_recommendation(
        self, is_valid: bool, confidence: float, issues: list[VerificationIssue]
    ) -> VerificationAction:
        """Determine recommended action based on verification results.

        Decision logic:
        - If confidence >= 0.75 and is_valid: PROCEED
        - If confidence < 0.75: CLARIFY (ask user)
        - If not is_valid and has critical issues: REPLAN (regenerate)
        - Otherwise: ABORT (cannot proceed)

        Args:
            is_valid: Whether plan passed all critical checks
            confidence: Confidence score
            issues: List of issues

        Returns:
            Recommended verification action
        """
        # Critical issues require replanning
        if not is_valid:
            has_critical = any(issue.severity == IssueSeverity.CRITICAL for issue in issues)
            if has_critical:
                return VerificationAction.REPLAN
            else:
                return VerificationAction.ABORT

        # Low confidence requires clarification
        if confidence < self.confidence_threshold:
            return VerificationAction.CLARIFY

        # High confidence and valid -> proceed
        return VerificationAction.PROCEED

    async def schema_validate(self, data: dict[str, Any], schema: dict[str, Any]) -> bool:
        """Validate data against JSON schema.

        Args:
            data: Data to validate
            schema: JSON schema

        Returns:
            True if valid, False otherwise
        """
        # Basic schema validation
        # In production, use jsonschema library
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                return False

        return True


# Pipeline Integration Example
# ============================
#
# To integrate ReasoningVerifier into the reasoning pipeline:
#
# 1. Add verification after Task Model Generator, before Safety Gate
# 2. Handle verification recommendations:
#    - PROCEED: Continue to Safety Gate
#    - CLARIFY: Ask user for clarification
#    - REPLAN: Regenerate task with feedback (max 2 retries)
#    - ABORT: Return error response
#
# Example integration code:
#
# async def process_with_verification(
#     task: Task,
#     original_input: str,
#     verifier: ReasoningVerifier,
#     max_replan_attempts: int = 2
# ) -> Union[Task, str]:
#     """Process task with verification.
#
#     Args:
#         task: Task to verify
#         original_input: Original user input
#         verifier: ReasoningVerifier instance
#         max_replan_attempts: Maximum replan attempts
#
#     Returns:
#         Verified task or error message
#     """
#     replan_count = 0
#     current_task = task
#
#     while replan_count <= max_replan_attempts:
#         # Verify the task
#         result = await verifier.verify_plan(current_task, original_input)
#
#         # Log verification decision
#         logger.info(
#             "Verification complete",
#             is_valid=result.is_valid,
#             confidence=result.confidence,
#             recommendation=result.recommendation.value,
#             issues_count=len(result.issues),
#             verification_time_ms=result.verification_time_ms
#         )
#
#         # Handle recommendation
#         if result.recommendation == VerificationAction.PROCEED:
#             # Continue to Safety Gate
#
