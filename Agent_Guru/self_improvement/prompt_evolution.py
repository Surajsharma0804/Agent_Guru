"""
Prompt Evolution System for Self-Improvement Engine.

Automatically refines prompts based on outcomes and validates improvements.
Implements version management and performance tracking for prompt evolution.

**Validates: Requirements 3.1-3.7**

Performance Requirements:
- Time Complexity: O(1) for prompt retrieval
- Space Complexity: O(n) where n is number of prompt versions
- Prompt Selection Latency: <5ms (95th percentile)

Author: Agent Guru Team
Date: 2026-02-28
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Agent_Guru.self_improvement.connection_pool import ConnectionPool


@dataclass
class PromptVersion:
    """A version of a prompt with performance tracking."""

    prompt_id: str
    prompt_type: str
    content: str
    version: int
    success_rate: float
    total_uses: int
    success_count: int
    failure_count: int
    hallucination_count: int
    created_at: datetime
    last_used: datetime | None = None
    is_active: bool = True


class PromptEvolutionSystem:
    """
    Evolves prompts based on performance tracking.

    Automatically identifies prompt weaknesses, generates improvements,
    validates them, and manages version history.

    Time Complexity: O(1) for prompt retrieval
    Space Complexity: O(n) where n is number of prompt versions

    Example:
        >>> system = PromptEvolutionSystem(pool)
        >>> system.register_prompt(
        ...     prompt_type="task_analysis",
        ...     prompt_text="Analyze the following task..."
        ... )
        >>> system.record_prompt_outcome("prompt_v1", True, False, 150.0)
        >>> best = system.get_active_prompt("task_analysis")
    """

    def __init__(self, pool: "ConnectionPool") -> None:
        """
        Initialize prompt evolution system.

        Args:
            pool: ConnectionPool for database access

        Raises:
            RuntimeError: If prompts table doesn't exist
        """
        self.pool = pool
        self._init_database()

    def _init_database(self) -> None:
        """
        Initialize database schema for prompts.

        Note: DatabaseSchema.create_schema() should be called first.
        This method only verifies the table exists.
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Verify prompts table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='prompts'
            """
            )

            if not cursor.fetchone():
                raise RuntimeError(
                    "Prompts table not found. " "Call DatabaseSchema.create_schema() first."
                )

    def register_prompt(
        self,
        prompt_type: str,
        content: str,
        version: int = 1,
    ) -> str:
        """
        Register a new prompt version.

        Args:
            prompt_type: Type of prompt (e.g., "task_analysis", "tool_selection")
            content: The prompt text
            version: Version number (default: 1)

        Returns:
            Prompt ID of the registered prompt

        Raises:
            ValueError: If prompt_type is empty or content is empty
        """
        if not prompt_type:
            raise ValueError("prompt_type cannot be empty")
        if not content:
            raise ValueError("content cannot be empty")

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Generate prompt ID
            prompt_id = f"{prompt_type}_v{version}_{datetime.now().timestamp()}"
            now = datetime.now().isoformat()

            # Deactivate previous versions of this prompt type
            cursor.execute(
                """
                UPDATE prompts
                SET is_active = 0
                WHERE prompt_type = ? AND is_active = 1
            """,
                (prompt_type,),
            )

            # Insert new prompt version
            cursor.execute(
                """
                INSERT INTO prompts (
                    prompt_id, prompt_type, content, version,
                    success_rate, total_uses, success_count, failure_count,
                    hallucination_count, created_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    prompt_id,
                    prompt_type,
                    content,
                    version,
                    0.0,
                    0,
                    0,
                    0,
                    0,
                    now,
                    1,
                ),
            )

            conn.commit()
            return prompt_id

    def record_prompt_outcome(
        self,
        prompt_id: str,
        success: bool,
        hallucination_detected: bool,
    ) -> None:
        """
        Record outcome of using a prompt.

        Time Complexity: O(1) - single database update

        Args:
            prompt_id: Prompt ID that was used
            success: Whether the task succeeded
            hallucination_detected: Whether hallucination was detected

        Raises:
            ValueError: If prompt_id doesn't exist
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Get current stats
            cursor.execute(
                """
                SELECT total_uses, success_count, failure_count,
                       hallucination_count
                FROM prompts
                WHERE prompt_id = ?
            """,
                (prompt_id,),
            )

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Prompt '{prompt_id}' not found")

            total, success_count, failure_count, halluc_count = row

            # Update stats
            new_total = total + 1
            new_success_count = success_count + (1 if success else 0)
            new_failure_count = failure_count + (0 if success else 1)
            new_halluc_count = halluc_count + (1 if hallucination_detected else 0)
            new_success_rate = new_success_count / new_total if new_total > 0 else 0.0

            now = datetime.now().isoformat()

            cursor.execute(
                """
                UPDATE prompts
                SET total_uses = ?,
                    success_count = ?,
                    failure_count = ?,
                    hallucination_count = ?,
                    success_rate = ?,
                    last_used = ?
                WHERE prompt_id = ?
            """,
                (
                    new_total,
                    new_success_count,
                    new_failure_count,
                    new_halluc_count,
                    new_success_rate,
                    now,
                    prompt_id,
                ),
            )

            conn.commit()

    def get_active_prompt(self, prompt_type: str) -> PromptVersion | None:
        """
        Get the currently active prompt for a type.

        Time Complexity: O(1) - indexed lookup

        Args:
            prompt_type: Type of prompt to retrieve

        Returns:
            Active prompt version or None if not found
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT prompt_id, prompt_type, content, version,
                       success_rate, total_uses, success_count, failure_count,
                       hallucination_count, created_at, last_used, is_active
                FROM prompts
                WHERE prompt_type = ? AND is_active = 1
            """,
                (prompt_type,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return PromptVersion(
                prompt_id=row[0],
                prompt_type=row[1],
                content=row[2],
                version=row[3],
                success_rate=row[4],
                total_uses=row[5],
                success_count=row[6],
                failure_count=row[7],
                hallucination_count=row[8],
                created_at=datetime.fromisoformat(row[9]),
                last_used=datetime.fromisoformat(row[10]) if row[10] else None,
                is_active=bool(row[11]),
            )

    def get_prompt_version(self, prompt_id: str) -> PromptVersion | None:
        """
        Get a specific prompt version by ID.

        Time Complexity: O(1) - indexed lookup

        Args:
            prompt_id: Prompt ID to retrieve

        Returns:
            Prompt version or None if not found
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT prompt_id, prompt_type, content, version,
                       success_rate, total_uses, success_count, failure_count,
                       hallucination_count, created_at, last_used, is_active
                FROM prompts
                WHERE prompt_id = ?
            """,
                (prompt_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return PromptVersion(
                prompt_id=row[0],
                prompt_type=row[1],
                content=row[2],
                version=row[3],
                success_rate=row[4],
                total_uses=row[5],
                success_count=row[6],
                failure_count=row[7],
                hallucination_count=row[8],
                created_at=datetime.fromisoformat(row[9]),
                last_used=datetime.fromisoformat(row[10]) if row[10] else None,
                is_active=bool(row[11]),
            )

    def get_prompt_history(self, prompt_type: str, limit: int = 10) -> list[PromptVersion]:
        """
        Get version history for a prompt type.

        Time Complexity: O(n) where n is number of versions (limited)

        Args:
            prompt_type: Type of prompt
            limit: Maximum number of versions to return

        Returns:
            List of prompt versions, newest first
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT prompt_id, prompt_type, content, version,
                       success_rate, total_uses, success_count, failure_count,
                       hallucination_count, created_at, last_used, is_active
                FROM prompts
                WHERE prompt_type = ?
                ORDER BY version DESC
                LIMIT ?
            """,
                (prompt_type, limit),
            )

            versions = []
            for row in cursor.fetchall():
                versions.append(
                    PromptVersion(
                        prompt_id=row[0],
                        prompt_type=row[1],
                        content=row[2],
                        version=row[3],
                        success_rate=row[4],
                        total_uses=row[5],
                        success_count=row[6],
                        failure_count=row[7],
                        hallucination_count=row[8],
                        created_at=datetime.fromisoformat(row[9]),
                        last_used=datetime.fromisoformat(row[10]) if row[10] else None,
                        is_active=bool(row[11]),
                    )
                )

            return versions

    def get_prompt_count(self) -> int:
        """
        Get total number of prompt versions.

        Time Complexity: O(1)

        Returns:
            Number of prompt versions
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM prompts")
            result = cursor.fetchone()
            return int(result[0]) if result else 0

    def get_all_prompt_types(self) -> list[str]:
        """
        Get all registered prompt types.

        Time Complexity: O(n) where n is number of unique types

        Returns:
            List of prompt types
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT DISTINCT prompt_type
                FROM prompts
                ORDER BY prompt_type
            """
            )

            return [row[0] for row in cursor.fetchall()]

    def identify_weak_prompts(
        self, min_uses: int = 10, max_success_rate: float = 0.7
    ) -> list[PromptVersion]:
        """
        Identify prompts with poor performance.

        Time Complexity: O(n) where n is number of prompts

        Args:
            min_uses: Minimum uses before considering a prompt weak
            max_success_rate: Maximum success rate to be considered weak

        Returns:
            List of weak prompt versions sorted by success rate (worst first)
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT prompt_id, prompt_type, content, version,
                       success_rate, total_uses, success_count, failure_count,
                       hallucination_count, created_at, last_used, is_active
                FROM prompts
                WHERE total_uses >= ? AND success_rate <= ?
                ORDER BY success_rate ASC, hallucination_count DESC
            """,
                (min_uses, max_success_rate),
            )

            weak_prompts = []
            for row in cursor.fetchall():
                weak_prompts.append(
                    PromptVersion(
                        prompt_id=row[0],
                        prompt_type=row[1],
                        content=row[2],
                        version=row[3],
                        success_rate=row[4],
                        total_uses=row[5],
                        success_count=row[6],
                        failure_count=row[7],
                        hallucination_count=row[8],
                        created_at=datetime.fromisoformat(row[9]),
                        last_used=datetime.fromisoformat(row[10]) if row[10] else None,
                        is_active=bool(row[11]),
                    )
                )

            return weak_prompts

    def get_prompt_weaknesses(self, prompt_id: str) -> dict[str, float]:
        """
        Analyze specific weaknesses of a prompt.

        Time Complexity: O(1) - single database query

        Args:
            prompt_id: Prompt ID to analyze

        Returns:
            Dictionary with weakness metrics:
            - failure_rate: Proportion of failures
            - hallucination_rate: Proportion with hallucinations
            - success_rate: Current success rate
            - total_uses: Total number of uses
            - failure_count: Number of failures
            - hallucination_count: Number of hallucinations

        Raises:
            ValueError: If prompt_id doesn't exist
        """
        prompt = self.get_prompt_version(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt '{prompt_id}' not found")

        failure_rate = prompt.failure_count / prompt.total_uses if prompt.total_uses > 0 else 0.0

        hallucination_rate = (
            prompt.hallucination_count / prompt.total_uses if prompt.total_uses > 0 else 0.0
        )

        return {
            "failure_rate": failure_rate,
            "hallucination_rate": hallucination_rate,
            "success_rate": prompt.success_rate,
            "total_uses": prompt.total_uses,
            "failure_count": prompt.failure_count,
            "hallucination_count": prompt.hallucination_count,
        }

    def compare_prompt_versions(
        self, prompt_type: str, version1: int, version2: int
    ) -> dict[str, float]:
        """
        Compare performance between two prompt versions.

        Time Complexity: O(1) - two database queries

        Args:
            prompt_type: Type of prompt
            version1: First version number
            version2: Second version number

        Returns:
            Dictionary with comparison metrics:
            - success_rate_diff: Difference in success rates (v2 - v1)
            - hallucination_diff: Difference in hallucination rates
            - improvement_percentage: Percentage improvement
            - version1_success_rate: Success rate of version 1
            - version2_success_rate: Success rate of version 2
            - version1_hallucination_rate: Hallucination rate of version 1
            - version2_hallucination_rate: Hallucination rate of version 2

        Raises:
            ValueError: If either version doesn't exist
        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Get version 1
            cursor.execute(
                """
                SELECT success_rate, total_uses, hallucination_count
                FROM prompts
                WHERE prompt_type = ? AND version = ?
            """,
                (prompt_type, version1),
            )
            row1 = cursor.fetchone()
            if not row1:
                raise ValueError(f"Version {version1} of prompt type '{prompt_type}' not found")

            # Get version 2
            cursor.execute(
                """
                SELECT success_rate, total_uses, hallucination_count
                FROM prompts
                WHERE prompt_type = ? AND version = ?
            """,
                (prompt_type, version2),
            )
            row2 = cursor.fetchone()
            if not row2:
                raise ValueError(f"Version {version2} of prompt type '{prompt_type}' not found")

            success_rate1, total_uses1, halluc_count1 = row1
            success_rate2, total_uses2, halluc_count2 = row2

            halluc_rate1 = halluc_count1 / total_uses1 if total_uses1 > 0 else 0.0
            halluc_rate2 = halluc_count2 / total_uses2 if total_uses2 > 0 else 0.0

            success_rate_diff = success_rate2 - success_rate1
            hallucination_diff = halluc_rate2 - halluc_rate1

            improvement_percentage = (
                (success_rate_diff / success_rate1 * 100) if success_rate1 > 0 else 0.0
            )

            return {
                "success_rate_diff": round(success_rate_diff, 2),
                "hallucination_diff": round(hallucination_diff, 2),
                "improvement_percentage": round(improvement_percentage, 2),
                "version1_success_rate": round(success_rate1, 2),
                "version2_success_rate": round(success_rate2, 2),
                "version1_hallucination_rate": round(halluc_rate1, 2),
                "version2_hallucination_rate": round(halluc_rate2, 2),
            }

    def should_replace_prompt(
        self, prompt_id: str, min_uses: int = 20, min_failure_rate: float = 0.3
    ) -> bool:
        """
        Determine if a prompt should be replaced due to poor performance.

        Time Complexity: O(1) - single database query

        Args:
            prompt_id: Prompt ID to evaluate
            min_uses: Minimum uses before considering replacement
            min_failure_rate: Minimum failure rate to trigger replacement

        Returns:
            True if prompt should be replaced, False otherwise
        """
        prompt = self.get_prompt_version(prompt_id)
        if not prompt:
            return False

        # Not enough data yet
        if prompt.total_uses < min_uses:
            return False

        failure_rate = prompt.failure_count / prompt.total_uses if prompt.total_uses > 0 else 0.0

        # High failure rate or high hallucination rate
        hallucination_rate = (
            prompt.hallucination_count / prompt.total_uses if prompt.total_uses > 0 else 0.0
        )

        return failure_rate >= min_failure_rate or hallucination_rate >= 0.2

    def generate_improved_prompt(
        self, prompt_id: str, llm_callable: Callable[[str], str] | None = None
    ) -> str:
        """
        Generate improved prompt using LLM meta-prompting.

        Uses weakness analysis to create a meta-prompt that asks an LLM
        to improve the original prompt based on identified issues.

        Time Complexity: O(1) for analysis + O(LLM) for generation

        Args:
            prompt_id: Prompt ID to improve
            llm_callable: Optional callable that takes prompt text and returns response
                         If None, returns the meta-prompt for manual use

        Returns:
            Improved prompt text (or meta-prompt if llm_callable is None)

        Raises:
            ValueError: If prompt_id doesn't exist
            RuntimeError: If LLM generation fails

        Example:
            >>> # Automatic improvement with LLM
            >>> def my_llm(prompt: str) -> str:
            ...     return openai.ChatCompletion.create(
            ...         model="gpt-4",
            ...         messages=[{"role": "user", "content": prompt}]
            ...     ).choices[0].message.content
            >>> improved = system.generate_improved_prompt("prompt_v1", my_llm)
            >>>
            >>> # Manual improvement (get meta-prompt)
            >>> meta_prompt = system.generate_improved_prompt("prompt_v1")
            >>> # Use meta_prompt with your LLM manually
        """
        # Get original prompt
        prompt = self.get_prompt_version(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt '{prompt_id}' not found")

        # Get weakness analysis
        weaknesses = self.get_prompt_weaknesses(prompt_id)

        # Build meta-prompt for LLM
        meta_prompt = self._build_meta_prompt(prompt, weaknesses)

        # If LLM callable provided, generate improvement
        if llm_callable:
            try:
                improved_prompt = llm_callable(meta_prompt)
                return improved_prompt.strip()
            except Exception as e:
                raise RuntimeError(f"LLM generation failed: {e}") from e

        # Otherwise return meta-prompt for manual use
        return meta_prompt

    def _build_meta_prompt(self, prompt: PromptVersion, weaknesses: dict[str, float]) -> str:
        """
        Build meta-prompt for LLM to improve original prompt.

        Args:
            prompt: Original prompt version
            weaknesses: Weakness metrics

        Returns:
            Meta-prompt text for LLM
        """
        failure_rate = weaknesses["failure_rate"]
        hallucination_rate = weaknesses["hallucination_rate"]
        success_rate = weaknesses["success_rate"]
        total_uses = weaknesses["total_uses"]

        # Identify primary weakness
        primary_issue = "general performance"
        if hallucination_rate > 0.15:
            primary_issue = "hallucinations (fabricated information)"
        elif failure_rate > 0.4:
            primary_issue = "task failures"
        elif success_rate < 0.6:
            primary_issue = "low success rate"

        meta_prompt = f"""You are a prompt engineering expert. Your task is to improve the following prompt based on performance analysis.

ORIGINAL PROMPT:
```
{prompt.content}
```

PERFORMANCE ANALYSIS:
- Prompt Type: {prompt.prompt_type}
- Version: {prompt.version}
- Total Uses: {total_uses}
- Success Rate: {success_rate:.1%}
- Failure Rate: {failure_rate:.1%}
- Hallucination Rate: {hallucination_rate:.1%}

PRIMARY ISSUE: {primary_issue}

IMPROVEMENT GUIDELINES:
1. If hallucination rate is high (>{hallucination_rate:.1%}):
   - Add explicit instructions to only use provided information
   - Add warnings against fabricating data
   - Request citations or sources for claims
   - Add verification steps

2. If failure rate is high (>{failure_rate:.1%}):
   - Clarify ambiguous instructions
   - Add step-by-step guidance
   - Include error handling instructions
   - Provide examples of correct behavior

3. If success rate is low (<{success_rate:.1%}):
   - Simplify complex instructions
   - Break down into smaller steps
   - Add context and background
   - Clarify expected output format

REQUIREMENTS:
- Maintain the core purpose of the original prompt
- Keep the improved prompt concise and clear
- Use specific, actionable language
- Avoid vague or ambiguous phrasing
- Test-driven: imagine edge cases the prompt should handle

OUTPUT FORMAT:
Provide ONLY the improved prompt text, without explanations or commentary.
The improved prompt should be ready to use directly.

IMPROVED PROMPT:"""

        return meta_prompt

    def validate_improved_prompt(
        self,
        original_prompt_id: str,
        improved_prompt_text: str,
        validation_callable: Callable[[str, str], tuple[bool, bool]],
        min_validation_tasks: int = 5,
    ) -> tuple[bool, dict[str, float]]:
        """
        Validate improved prompt on similar tasks before adoption.

        Tests the improved prompt against similar tasks to ensure it performs
        better than the original before registering it as a new version.

        Time Complexity: O(n) where n is min_validation_tasks

        Args:
            original_prompt_id: ID of original prompt to compare against
            improved_prompt_text: Text of improved prompt to validate
            validation_callable: Function that takes (prompt_text, task_context)
                                and returns (success: bool, hallucination: bool)
            min_validation_tasks: Minimum number of validation tasks to run

        Returns:
            Tuple of (should_adopt: bool, metrics: dict) where metrics contains:
            - improved_success_rate: Success rate of improved prompt
            - original_success_rate: Success rate of original prompt
            - improvement: Absolute improvement in success rate
            - improved_hallucination_rate: Hallucination rate of improved prompt
            - validation_tasks: Number of validation tasks run

        Raises:
            ValueError: If original_prompt_id doesn't exist
            RuntimeError: If validation_callable fails

        Example:
            >>> def validate_task(prompt: str, context: str) -> tuple[bool, bool]:
            ...     # Run task with prompt and return (success, hallucination)
            ...     result = run_task_with_prompt(prompt, context)
            ...     return result.success, result.hallucination_detected
            >>>
            >>> should_adopt, metrics = system.validate_improved_prompt(
            ...     "prompt_v1",
            ...     "Improved prompt text",
            ...     validate_task,
            ...     min_validation_tasks=10
            ... )
            >>> if should_adopt:
            ...     new_version = system.register_prompt(
            ...         prompt_type="task_analysis",
            ...         content="Improved prompt text",
            ...         version=2
            ...     )
        """
        # Get original prompt
        original = self.get_prompt_version(original_prompt_id)
        if not original:
            raise ValueError(f"Prompt '{original_prompt_id}' not found")

        # Run validation tasks
        improved_successes = 0
        improved_hallucinations = 0
        original_successes = 0
        original_hallucinations = 0

        for i in range(min_validation_tasks):
            # Create validation context (could be from historical tasks)
            validation_context = f"validation_task_{i}"

            try:
                # Test improved prompt
                success, hallucination = validation_callable(
                    improved_prompt_text, validation_context
                )
                if success:
                    improved_successes += 1
                if hallucination:
                    improved_hallucinations += 1

                # Test original prompt
                success, hallucination = validation_callable(original.content, validation_context)
                if success:
                    original_successes += 1
                if hallucination:
                    original_hallucinations += 1

            except Exception as e:
                raise RuntimeError(f"Validation failed on task {i}: {e}") from e

        # Calculate metrics
        improved_success_rate = improved_successes / min_validation_tasks
        original_success_rate = original_successes / min_validation_tasks
        improvement = improved_success_rate - original_success_rate
        improved_hallucination_rate = improved_hallucinations / min_validation_tasks

        metrics = {
            "improved_success_rate": round(improved_success_rate, 2),
            "original_success_rate": round(original_success_rate, 2),
            "improvement": round(improvement, 2),
            "improved_hallucination_rate": round(improved_hallucination_rate, 2),
            "validation_tasks": min_validation_tasks,
        }

        # Adoption criteria:
        # 1. Improved prompt must have better success rate
        # 2. Hallucination rate must not increase significantly (>10%)
        should_adopt = (
            improvement > 0.0
            and improved_hallucination_rate
            <= (original_hallucinations / min_validation_tasks) + 0.1
        )

        return should_adopt, metrics
