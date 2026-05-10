"""Prompt Evolution System for Self-Improvement Engine.

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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
    """Evolves prompts based on performance tracking.

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

    def __init__(
        self,
        pool: "ConnectionPool",
        min_update_interval_seconds: float = 3600.0,  # 1 hour default
        rollback_cooldown_seconds: float = 7200.0,  # 2 hours default
        oscillation_window_seconds: float = 86400.0,  # 24 hours default
    ) -> None:
        """Initialize prompt evolution system.

        Args:
            pool: ConnectionPool for database access
            min_update_interval_seconds: Minimum time between prompt updates (default: 1 hour)
            rollback_cooldown_seconds: Cooldown period after rollback (default: 2 hours)
            oscillation_window_seconds: Time window for oscillation detection (default: 24 hours)

        Raises:
            RuntimeError: If prompts table doesn't exist

        """
        self.pool = pool
        self.min_update_interval = min_update_interval_seconds
        self.rollback_cooldown = rollback_cooldown_seconds
        self.oscillation_window = oscillation_window_seconds
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema for prompts.

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
            """,
            )

            if not cursor.fetchone():
                msg = "Prompts table not found. Call DatabaseSchema.create_schema() first."
                raise RuntimeError(
                    msg,
                )

    def register_prompt(
        self,
        prompt_type: str,
        content: str,
        version: int = 1,
        force: bool = False,
    ) -> str:
        """Register a new prompt version.

        Args:
            prompt_type: Type of prompt (e.g., "task_analysis", "tool_selection")
            content: The prompt text
            version: Version number (default: 1)
            force: If True, bypass rate limiting (default: False)

        Returns:
            Prompt ID of the registered prompt

        Raises:
            ValueError: If prompt_type is empty or content is empty
            RuntimeError: If rate limit prevents update (unless force=True)

        """
        if not prompt_type:
            msg = "prompt_type cannot be empty"
            raise ValueError(msg)
        if not content:
            msg = "content cannot be empty"
            raise ValueError(msg)

        # Check rate limiting (unless forced)
        if not force:
            can_update, reason = self.can_update_prompt(prompt_type, "register")
            if not can_update:
                msg = f"Rate limit prevents update: {reason}"
                raise RuntimeError(msg)

        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Get previous active version
            cursor.execute(
                """
                SELECT version
                FROM prompts
                WHERE prompt_type = ? AND is_active = 1
            """,
                (prompt_type,),
            )
            prev_row = cursor.fetchone()
            previous_version = prev_row[0] if prev_row else None

            # Generate prompt ID
            prompt_id = f"{prompt_type}_v{version}_{datetime.now(tz=UTC).timestamp()}"
            now = datetime.now(tz=UTC).isoformat()

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

        # Record update for rate limiting
        self._record_prompt_update(prompt_type, "register", previous_version, version)

        return prompt_id

    def record_prompt_outcome(
        self,
        prompt_id: str,
        success: bool,
        hallucination_detected: bool,
    ) -> None:
        """Record outcome of using a prompt.

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
                msg = f"Prompt '{prompt_id}' not found"
                raise ValueError(msg)

            total, success_count, failure_count, halluc_count = row

            # Update stats
            new_total = total + 1
            new_success_count = success_count + (1 if success else 0)
            new_failure_count = failure_count + (0 if success else 1)
            new_halluc_count = halluc_count + (1 if hallucination_detected else 0)
            new_success_rate = new_success_count / new_total if new_total > 0 else 0.0

            now = datetime.now(tz=UTC).isoformat()

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
        """Get the currently active prompt for a type.

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
        """Get a specific prompt version by ID.

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
        """Get version history for a prompt type.

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
                    ),
                )

            return versions

    def get_prompt_count(self) -> int:
        """Get total number of prompt versions.

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
        """Get all registered prompt types.

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
            """,
            )

            return [row[0] for row in cursor.fetchall()]

    def identify_weak_prompts(
        self,
        min_uses: int = 10,
        max_success_rate: float = 0.7,
    ) -> list[PromptVersion]:
        """Identify prompts with poor performance.

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
                    ),
                )

            return weak_prompts

    def get_prompt_weaknesses(self, prompt_id: str) -> dict[str, float]:
        """Analyze specific weaknesses of a prompt.

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
            msg = f"Prompt '{prompt_id}' not found"
            raise ValueError(msg)

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
        self,
        prompt_type: str,
        version1: int,
        version2: int,
    ) -> dict[str, float]:
        """Compare performance between two prompt versions.

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
                msg = f"Version {version1} of prompt type '{prompt_type}' not found"
                raise ValueError(msg)

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
                msg = f"Version {version2} of prompt type '{prompt_type}' not found"
                raise ValueError(msg)

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
        self,
        prompt_id: str,
        min_uses: int = 20,
        min_failure_rate: float = 0.3,
    ) -> bool:
        """Determine if a prompt should be replaced due to poor performance.

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

        return failure_rate >= min_failure_rate or hallucination_rate >= 0.2  # noqa: PLR2004 - Threshold value


    def generate_improved_prompt(
        self,
        prompt_id: str,
        llm_callable: Callable[[str], str] | None = None,
    ) -> str:
        """Generate improved prompt using LLM meta-prompting.

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
            msg = f"Prompt '{prompt_id}' not found"
            raise ValueError(msg)

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
                msg = f"LLM generation failed: {e}"
                raise RuntimeError(msg) from e

        # Otherwise return meta-prompt for manual use
        return meta_prompt

    def _build_meta_prompt(self, prompt: PromptVersion, weaknesses: dict[str, float]) -> str:
        """Build meta-prompt for LLM to improve original prompt.

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
        if hallucination_rate > 0.15:  # noqa: PLR2004 - Threshold value

            primary_issue = "hallucinations (fabricated information)"
        elif failure_rate > 0.4:  # noqa: PLR2004 - Threshold value

            primary_issue = "task failures"
        elif success_rate < 0.6:  # noqa: PLR2004 - Threshold value

            primary_issue = "low success rate"

        return f"""You are a prompt engineering expert. Your task is to improve the following prompt based on performance analysis.

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

    def validate_improved_prompt(
        self,
        original_prompt_id: str,
        improved_prompt_text: str,
        validation_callable: Callable[[str, str], tuple[bool, bool]],
        min_validation_tasks: int = 5,
    ) -> tuple[bool, dict[str, float]]:
        """Validate improved prompt on similar tasks before adoption.

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
            msg = f"Prompt '{original_prompt_id}' not found"
            raise ValueError(msg)

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
                    improved_prompt_text,
                    validation_context,
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
                msg = f"Validation failed on task {i}: {e}"
                raise RuntimeError(msg) from e

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

    def rollback_prompt(
        self,
        prompt_type: str,
        target_version: int | None = None,
        force: bool = False,
    ) -> str:
        """Rollback to a previous prompt version due to degraded performance.

        Deactivates the current active prompt and activates a previous version.
        If target_version is not specified, rolls back to the previous version.

        Time Complexity: O(1) - constant database operations
        Space Complexity: O(1)

        Args:
            prompt_type: Type of prompt to rollback
            target_version: Specific version to rollback to (None = previous version)
            force: If True, bypass rate limiting and oscillation checks (default: False)

        Returns:
            prompt_id of the activated version

        Raises:
            ValueError: If prompt_type doesn't exist or target_version not found
            RuntimeError: If oscillation detected (unless force=True)

        Example:
            >>> # Current version is 3, rollback to version 2
            >>> prompt_id = system.rollback_prompt("task_analysis", target_version=2)
            >>> active = system.get_active_prompt("task_analysis")
            >>> assert active.version == 2

        """
        conn = self.pool.acquire()
        cursor = conn.connection.cursor()

        try:
            # Get current active version
            cursor.execute(
                """
                SELECT prompt_id, version
                FROM prompts
                WHERE prompt_type = ? AND is_active = 1
                """,
                (prompt_type,),
            )
            current = cursor.fetchone()

            if not current:
                msg = f"No active prompt found for type '{prompt_type}'"
                raise ValueError(msg)

            current_id, current_version = current

            # Determine target version
            if target_version is None:
                # Rollback to previous version
                target_version = current_version - 1

            if target_version < 1:
                msg = f"Cannot rollback to version {target_version} (minimum is 1)"
                raise ValueError(msg)

            # Check oscillation (unless forced)
            if not force:
                can_switch, reason = self.can_switch_to_version(prompt_type, target_version)
                if not can_switch:
                    msg = f"Oscillation prevention: {reason}"
                    raise RuntimeError(msg)

            # Get target version
            cursor.execute(
                """
                SELECT prompt_id
                FROM prompts
                WHERE prompt_type = ? AND version = ?
                """,
                (prompt_type, target_version),
            )
            target = cursor.fetchone()

            if not target:
                msg = f"Version {target_version} not found for prompt type '{prompt_type}'"
                raise ValueError(
                    msg,
                )

            target_id = target[0]

            # Deactivate current version
            cursor.execute(
                """
                UPDATE prompts
                SET is_active = 0
                WHERE prompt_id = ?
                """,
                (current_id,),
            )

            # Activate target version
            cursor.execute(
                """
                UPDATE prompts
                SET is_active = 1
                WHERE prompt_id = ?
                """,
                (target_id,),
            )

            conn.connection.commit()

            # Record rollback for rate limiting
            self._record_prompt_update(prompt_type, "rollback", current_version, target_version)

            return target_id

        finally:
            self.pool.release(conn)

    def detect_performance_degradation(
        self,
        prompt_type: str,
        degradation_threshold: float = 0.15,
    ) -> tuple[bool, dict[str, float]]:
        """Detect if prompt performance has degraded significantly.

        Compares current active prompt performance to previous version performance.
        Used to trigger automatic rollback when performance drops.

        Time Complexity: O(1) - constant database operations
        Space Complexity: O(1)

        Args:
            prompt_type: Type of prompt to check
            degradation_threshold: Minimum degradation to trigger alert (0.15 = 15%)

        Returns:
            Tuple of (is_degraded: bool, metrics: dict) where metrics contains:
            - current_success_rate: Success rate of current version
            - previous_success_rate: Success rate of previous version
            - degradation: Absolute degradation amount
            - current_hallucination_rate: Hallucination rate of current version

        Example:
            >>> is_degraded, metrics = system.detect_performance_degradation(
            ...     "task_analysis",
            ...     degradation_threshold=0.15
            ... )
            >>> if is_degraded:
            ...     # Automatic rollback
            ...     system.rollback_prompt("task_analysis")

        """
        # Get current active prompt
        current = self.get_active_prompt(prompt_type)
        if not current or current.total_uses < 10:  # noqa: PLR2004 - Threshold

            # Not enough data
            return False, {}

        # Get previous version
        history = self.get_prompt_history(prompt_type, limit=2)
        if len(history) < 2:  # noqa: PLR2004 - Small integer threshold

            # No previous version to compare
            return False, {}

        previous = history[1]  # Second in history (first is current)
        if previous.total_uses < 10:  # noqa: PLR2004 - Threshold

            # Not enough data in previous version
            return False, {}

        # Calculate degradation
        degradation = previous.success_rate - current.success_rate
        current_hallucination_rate = (
            current.hallucination_count / current.total_uses if current.total_uses > 0 else 0.0
        )

        metrics = {
            "current_success_rate": round(current.success_rate, 2),
            "previous_success_rate": round(previous.success_rate, 2),
            "degradation": round(degradation, 2),
            "current_hallucination_rate": round(current_hallucination_rate, 2),
        }

        is_degraded = degradation >= degradation_threshold

        return is_degraded, metrics

    def ab_test_prompts(
        self,
        prompt_type: str,
        candidate_prompt_text: str,
        test_callable: Callable[[str, str], tuple[bool, bool]],
        num_tests: int = 20,
        traffic_split: float = 0.5,
    ) -> dict[str, Any]:
        """A/B test a candidate prompt against the current active prompt.

        Runs parallel testing of candidate vs active prompt to determine
        which performs better before full adoption.

        Time Complexity: O(n) where n is num_tests
        Space Complexity: O(n)

        Args:
            prompt_type: Type of prompt to test
            candidate_prompt_text: Text of candidate prompt to test
            test_callable: Function that takes (prompt_text, task_context)
                          and returns (success: bool, hallucination: bool)
            num_tests: Total number of test tasks to run
            traffic_split: Fraction of traffic to send to candidate (0.0-1.0)

        Returns:
            Dictionary with A/B test results:
            - candidate_success_rate: Success rate of candidate prompt
            - active_success_rate: Success rate of active prompt
            - candidate_hallucination_rate: Hallucination rate of candidate
            - active_hallucination_rate: Hallucination rate of active
            - improvement: Absolute improvement (candidate - active)
            - statistical_significance: Whether difference is significant
            - recommendation: "adopt" or "reject"

        Raises:
            ValueError: If prompt_type doesn't have an active prompt
            RuntimeError: If test_callable fails

        Example:
            >>> def test_task(prompt: str, context: str) -> tuple[bool, bool]:
            ...     result = run_task_with_prompt(prompt, context)
            ...     return result.success, result.hallucination_detected
            >>>
            >>> results = system.ab_test_prompts(
            ...     "task_analysis",
            ...     "Candidate prompt text",
            ...     test_task,
            ...     num_tests=50,
            ...     traffic_split=0.5
            ... )
            >>> if results["recommendation"] == "adopt":
            ...     system.register_prompt("task_analysis", "Candidate prompt text")

        """
        active = self.get_active_prompt(prompt_type)
        if not active:
            msg = f"No active prompt found for type '{prompt_type}'"
            raise ValueError(msg)

        # Determine test allocation
        candidate_tests = int(num_tests * traffic_split)
        active_tests = num_tests - candidate_tests

        # Run tests
        candidate_successes = 0
        candidate_hallucinations = 0
        active_successes = 0
        active_hallucinations = 0

        try:
            # Test candidate prompt
            for i in range(candidate_tests):
                test_context = f"ab_test_candidate_{i}"
                success, hallucination = test_callable(candidate_prompt_text, test_context)
                if success:
                    candidate_successes += 1
                if hallucination:
                    candidate_hallucinations += 1

            # Test active prompt
            for i in range(active_tests):
                test_context = f"ab_test_active_{i}"
                success, hallucination = test_callable(active.content, test_context)
                if success:
                    active_successes += 1
                if hallucination:
                    active_hallucinations += 1

        except Exception as e:
            msg = f"A/B test failed: {e}"
            raise RuntimeError(msg) from e

        # Calculate metrics
        candidate_success_rate = (
            candidate_successes / candidate_tests if candidate_tests > 0 else 0.0
        )
        active_success_rate = active_successes / active_tests if active_tests > 0 else 0.0
        candidate_hallucination_rate = (
            candidate_hallucinations / candidate_tests if candidate_tests > 0 else 0.0
        )
        active_hallucination_rate = (
            active_hallucinations / active_tests if active_tests > 0 else 0.0
        )

        improvement = candidate_success_rate - active_success_rate

        # Simple statistical significance test (chi-square would be better)
        # For now, require at least 10% improvement with sufficient sample size
        statistical_significance = abs(improvement) >= 0.10 and num_tests >= 20  # noqa: PLR2004 - Threshold


        # Recommendation
        recommendation = "adopt" if improvement > 0 and statistical_significance else "reject"

        return {
            "candidate_success_rate": round(candidate_success_rate, 2),
            "active_success_rate": round(active_success_rate, 2),
            "candidate_hallucination_rate": round(candidate_hallucination_rate, 2),
            "active_hallucination_rate": round(active_hallucination_rate, 2),
            "improvement": round(improvement, 2),
            "statistical_significance": statistical_significance,
            "recommendation": recommendation,
            "num_tests": num_tests,
            "candidate_tests": candidate_tests,
            "active_tests": active_tests,
        }

    def _record_prompt_update(
        self,
        prompt_type: str,
        update_type: str,
        previous_version: int | None,
        new_version: int,
    ) -> None:
        """Record a prompt update for rate limiting tracking.

        Args:
            prompt_type: Type of prompt updated
            update_type: Type of update ('register', 'rollback', 'replace')
            previous_version: Previous version number (None for first registration)
            new_version: New version number

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            update_id = f"update_{prompt_type}_{datetime.now(tz=UTC).timestamp()}"
            now = datetime.now(tz=UTC).isoformat()

            cursor.execute(
                """
                INSERT INTO prompt_updates (
                    update_id, prompt_type, update_type,
                    previous_version, new_version, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    update_id,
                    prompt_type,
                    update_type,
                    previous_version,
                    new_version,
                    now,
                ),
            )

            conn.commit()

    def _get_last_update_time(self, prompt_type: str) -> datetime | None:
        """Get timestamp of last update for a prompt type.

        Args:
            prompt_type: Type of prompt to check

        Returns:
            Datetime of last update or None if never updated

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT timestamp
                FROM prompt_updates
                WHERE prompt_type = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                (prompt_type,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return datetime.fromisoformat(row[0])

    def _get_last_rollback_time(self, prompt_type: str) -> datetime | None:
        """Get timestamp of last rollback for a prompt type.

        Args:
            prompt_type: Type of prompt to check

        Returns:
            Datetime of last rollback or None if never rolled back

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT timestamp
                FROM prompt_updates
                WHERE prompt_type = ? AND update_type = 'rollback'
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                (prompt_type,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return datetime.fromisoformat(row[0])

    def _check_oscillation(self, prompt_type: str, target_version: int) -> tuple[bool, list[int]]:
        """Check if switching to target version would cause oscillation.

        Detects rapid back-and-forth changes between versions within
        the oscillation window. Oscillation is defined as switching
        to a version that was active recently AND there's a pattern
        of version switching.

        Args:
            prompt_type: Type of prompt to check
            target_version: Version we want to switch to

        Returns:
            Tuple of (is_oscillating, recent_versions) where:
            - is_oscillating: True if oscillation detected
            - recent_versions: List of recent version numbers

        """
        with self.pool.connection() as conn:
            cursor = conn.cursor()

            # Get recent updates within oscillation window
            cutoff_time = datetime.now(tz=UTC).timestamp() - self.oscillation_window
            cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()

            cursor.execute(
                """
                SELECT new_version
                FROM prompt_updates
                WHERE prompt_type = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """,
                (prompt_type, cutoff_iso),
            )

            recent_versions = [row[0] for row in cursor.fetchall()]

            # No oscillation if not enough history
            if len(recent_versions) < 2:  # noqa: PLR2004 - Small integer threshold

                return False, recent_versions

            # Oscillation detected if:
            # 1. Target version appears in recent history (last 4 updates)
            # 2. The target version appears at least twice in recent history
            # This catches back-and-forth switching patterns
            last_four = recent_versions[:4] if len(recent_versions) >= 4 else recent_versions  # noqa: PLR2004 - Small integer threshold

            target_count_in_recent = recent_versions.count(target_version)

            # True oscillation: switching back to a recently used version
            is_oscillating = target_version in last_four and target_count_in_recent >= 1

            return is_oscillating, recent_versions

    def can_update_prompt(
        self,
        prompt_type: str,
        update_type: str = "register",
    ) -> tuple[bool, str]:
        """Check if a prompt can be updated based on rate limiting rules.

        Enforces:
        1. Cooldown period after rollback (rollback_cooldown) - checked first
        2. Minimum time between updates (min_update_interval)
        3. Oscillation prevention (oscillation_window)

        Time Complexity: O(1) - constant database queries
        Space Complexity: O(1)

        Args:
            prompt_type: Type of prompt to update
            update_type: Type of update ('register', 'rollback', 'replace')

        Returns:
            Tuple of (can_update: bool, reason: str) where:
            - can_update: True if update is allowed
            - reason: Explanation if update is blocked

        Example:
            >>> can_update, reason = system.can_update_prompt("task_analysis")
            >>> if not can_update:
            ...     print(f"Update blocked: {reason}")
            >>> else:
            ...     system.register_prompt("task_analysis", "New prompt text")

        """
        now = datetime.now(tz=UTC)

        # Check rollback cooldown FIRST (highest priority)
        if update_type != "rollback":
            last_rollback = self._get_last_rollback_time(prompt_type)
            if last_rollback:
                time_since_rollback = (now - last_rollback).total_seconds()
                if time_since_rollback < self.rollback_cooldown:
                    remaining = self.rollback_cooldown - time_since_rollback
                    return (
                        False,
                        f"Rollback cooldown: {remaining:.0f}s remaining before new updates allowed",
                    )

        # Check minimum update interval
        last_update = self._get_last_update_time(prompt_type)
        if last_update:
            time_since_update = (now - last_update).total_seconds()
            if time_since_update < self.min_update_interval:
                remaining = self.min_update_interval - time_since_update
                return (
                    False,
                    f"Rate limit: {remaining:.0f}s remaining until next update allowed",
                )

        return True, "Update allowed"

    def can_switch_to_version(self, prompt_type: str, target_version: int) -> tuple[bool, str]:
        """Check if switching to a specific version would cause oscillation.

        Args:
            prompt_type: Type of prompt
            target_version: Version to switch to

        Returns:
            Tuple of (can_switch: bool, reason: str)

        Example:
            >>> can_switch, reason = system.can_switch_to_version("task_analysis", 2)
            >>> if not can_switch:
            ...     print(f"Switch blocked: {reason}")

        """
        is_oscillating, recent_versions = self._check_oscillation(prompt_type, target_version)

        if is_oscillating:
            return (
                False,
                f"Oscillation detected: version {target_version} was recently active. "
                f"Recent versions: {recent_versions[:5]}",
            )

        return True, "Switch allowed"

    def get_rate_limit_status(self, prompt_type: str) -> dict[str, Any]:
        """Get current rate limiting status for a prompt type.

        Args:
            prompt_type: Type of prompt to check

        Returns:
            Dictionary with rate limit status:
            - can_update: Whether update is currently allowed
            - last_update: Timestamp of last update (or None)
            - time_since_update: Seconds since last update (or None)
            - time_until_next_update: Seconds until next update allowed (or 0)
            - last_rollback: Timestamp of last rollback (or None)
            - time_since_rollback: Seconds since last rollback (or None)
            - rollback_cooldown_remaining: Seconds remaining in cooldown (or 0)
            - recent_versions: List of recent version numbers

        Example:
            >>> status = system.get_rate_limit_status("task_analysis")
            >>> print(f"Can update: {status['can_update']}")
            >>> print(f"Time until next update: {status['time_until_next_update']}s")

        """
        now = datetime.now(tz=UTC)

        last_update = self._get_last_update_time(prompt_type)
        last_rollback = self._get_last_rollback_time(prompt_type)

        time_since_update = (now - last_update).total_seconds() if last_update else None
        time_since_rollback = (now - last_rollback).total_seconds() if last_rollback else None

        time_until_next_update = 0.0
        if time_since_update is not None:
            time_until_next_update = max(0.0, self.min_update_interval - time_since_update)

        rollback_cooldown_remaining = 0.0
        if time_since_rollback is not None:
            rollback_cooldown_remaining = max(0.0, self.rollback_cooldown - time_since_rollback)

        can_update, _ = self.can_update_prompt(prompt_type)

        _, recent_versions = self._check_oscillation(prompt_type, 0)

        return {
            "can_update": can_update,
            "last_update": last_update.isoformat() if last_update else None,
            "time_since_update": time_since_update,
            "time_until_next_update": time_until_next_update,
            "last_rollback": last_rollback.isoformat() if last_rollback else None,
            "time_since_rollback": time_since_rollback,
            "rollback_cooldown_remaining": rollback_cooldown_remaining,
            "recent_versions": recent_versions[:10],  # Last 10 versions
        }
