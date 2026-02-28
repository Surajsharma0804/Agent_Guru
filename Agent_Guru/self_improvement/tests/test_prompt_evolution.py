"""
Tests for Prompt Evolution System.

Coverage Target: >80% (enforced by CI/CD)
"""

import gc
import os
import tempfile
from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from Agent_Guru.self_improvement.connection_pool import ConnectionPool
from Agent_Guru.self_improvement.database_schema import DatabaseSchema
from Agent_Guru.self_improvement.prompt_evolution import (
    PromptEvolutionSystem,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        # Create schema using static method
        DatabaseSchema.create_schema(str(db_path))
        yield str(db_path)


@pytest.fixture
def pool(temp_db):
    """Create connection pool."""
    pool = ConnectionPool(temp_db, min_size=1, max_size=5)
    yield pool
    # Cleanup: close all connections
    pool.close_all()


@pytest.fixture
def system(pool):
    """Create PromptEvolutionSystem instance."""
    return PromptEvolutionSystem(pool)


class TestPromptEvolutionSystemInitialization:
    """Tests for PromptEvolutionSystem initialization."""

    def test_initialization(self, system):
        """Test system initialization."""
        assert system is not None
        assert system.pool is not None

    def test_initialization_without_schema_fails(self):
        """Test initialization fails without schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            pool = ConnectionPool(str(db_path), min_size=1, max_size=5)

            with pytest.raises(RuntimeError, match="Prompts table not found"):
                PromptEvolutionSystem(pool)

            pool.close_all()


class TestPromptRegistration:
    """Tests for prompt registration."""

    def test_register_prompt(self, system):
        """Test registering a new prompt."""
        prompt_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Analyze the following task carefully...",
            version=1,
        )

        assert prompt_id is not None
        assert "task_analysis_v1" in prompt_id

        # Verify it's stored
        prompt = system.get_active_prompt("task_analysis")
        assert prompt is not None
        assert prompt.prompt_type == "task_analysis"
        assert prompt.version == 1
        assert prompt.is_active is True

    def test_register_prompt_with_empty_type_fails(self, system):
        """Test registering prompt with empty type fails."""
        with pytest.raises(ValueError, match="prompt_type cannot be empty"):
            system.register_prompt(
                prompt_type="",
                content="Some text",
            )

    def test_register_prompt_with_empty_content_fails(self, system):
        """Test registering prompt with empty content fails."""
        with pytest.raises(ValueError, match="content cannot be empty"):
            system.register_prompt(
                prompt_type="task_analysis",
                content="",
            )

    def test_register_multiple_versions_deactivates_previous(self, system):
        """Test registering new version deactivates previous."""
        # Register version 1
        v1_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Version 1 text",
            version=1,
        )

        # Register version 2
        v2_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Version 2 text",
            version=2,
        )

        # Version 2 should be active
        active = system.get_active_prompt("task_analysis")
        assert active is not None
        assert active.prompt_id == v2_id
        assert active.version == 2

        # Version 1 should be inactive
        v1 = system.get_prompt_version(v1_id)
        assert v1 is not None
        assert v1.is_active is False


class TestPromptOutcomeRecording:
    """Tests for recording prompt outcomes."""

    def test_record_successful_outcome(self, system):
        """Test recording successful outcome."""
        prompt_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Analyze task...",
        )

        system.record_prompt_outcome(
            prompt_id=prompt_id,
            success=True,
            hallucination_detected=False,
        )

        prompt = system.get_prompt_version(prompt_id)
        assert prompt is not None
        assert prompt.total_uses == 1
        assert prompt.success_count == 1
        assert prompt.failure_count == 0
        assert prompt.hallucination_count == 0
        assert prompt.success_rate == 1.0

    def test_record_failed_outcome(self, system):
        """Test recording failed outcome."""
        prompt_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Analyze task...",
        )

        system.record_prompt_outcome(
            prompt_id=prompt_id,
            success=False,
            hallucination_detected=False,
        )

        prompt = system.get_prompt_version(prompt_id)
        assert prompt is not None
        assert prompt.total_uses == 1
        assert prompt.success_count == 0
        assert prompt.failure_count == 1
        assert prompt.success_rate == 0.0

    def test_record_outcome_with_hallucination(self, system):
        """Test recording outcome with hallucination."""
        prompt_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Analyze task...",
        )

        system.record_prompt_outcome(
            prompt_id=prompt_id,
            success=False,
            hallucination_detected=True,
        )

        prompt = system.get_prompt_version(prompt_id)
        assert prompt is not None
        assert prompt.hallucination_count == 1
        assert prompt.failure_count == 1

    def test_record_multiple_outcomes_updates_stats(self, system):
        """Test recording multiple outcomes updates statistics."""
        prompt_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Analyze task...",
        )

        # Record 3 successes and 1 failure
        system.record_prompt_outcome(prompt_id, True, False)
        system.record_prompt_outcome(prompt_id, True, False)
        system.record_prompt_outcome(prompt_id, True, False)
        system.record_prompt_outcome(prompt_id, False, False)

        prompt = system.get_prompt_version(prompt_id)
        assert prompt is not None
        assert prompt.total_uses == 4
        assert prompt.success_count == 3
        assert prompt.failure_count == 1
        assert prompt.success_rate == 0.75

    def test_record_outcome_for_nonexistent_prompt_fails(self, system):
        """Test recording outcome for nonexistent prompt fails."""
        with pytest.raises(ValueError, match="Prompt .* not found"):
            system.record_prompt_outcome(
                prompt_id="nonexistent",
                success=True,
                hallucination_detected=False,
            )


class TestPromptRetrieval:
    """Tests for prompt retrieval."""

    def test_get_active_prompt(self, system):
        """Test getting active prompt."""
        prompt_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Analyze task...",
        )

        active = system.get_active_prompt("task_analysis")
        assert active is not None
        assert active.prompt_id == prompt_id
        assert active.is_active is True

    def test_get_active_prompt_nonexistent_returns_none(self, system):
        """Test getting nonexistent active prompt returns None."""
        active = system.get_active_prompt("nonexistent")
        assert active is None

    def test_get_prompt_version(self, system):
        """Test getting specific prompt version."""
        prompt_id = system.register_prompt(
            prompt_type="task_analysis",
            content="Analyze task...",
        )

        prompt = system.get_prompt_version(prompt_id)
        assert prompt is not None
        assert prompt.prompt_id == prompt_id

    def test_get_prompt_version_nonexistent_returns_none(self, system):
        """Test getting nonexistent version returns None."""
        prompt = system.get_prompt_version("nonexistent")
        assert prompt is None

    def test_get_prompt_history(self, system):
        """Test getting prompt version history."""
        # Register 3 versions
        system.register_prompt("task_analysis", "Version 1", 1)
        system.register_prompt("task_analysis", "Version 2", 2)
        system.register_prompt("task_analysis", "Version 3", 3)

        history = system.get_prompt_history("task_analysis")
        assert len(history) == 3
        # Should be newest first
        assert history[0].version == 3
        assert history[1].version == 2
        assert history[2].version == 1

    def test_get_prompt_history_with_limit(self, system):
        """Test getting prompt history with limit."""
        # Register 5 versions
        for i in range(1, 6):
            system.register_prompt("task_analysis", f"Version {i}", i)

        history = system.get_prompt_history("task_analysis", limit=3)
        assert len(history) == 3
        assert history[0].version == 5
        assert history[1].version == 4
        assert history[2].version == 3

    def test_get_prompt_count(self, system):
        """Test getting total prompt count."""
        assert system.get_prompt_count() == 0

        system.register_prompt("type1", "Text 1")
        assert system.get_prompt_count() == 1

        system.register_prompt("type2", "Text 2")
        assert system.get_prompt_count() == 2

    def test_get_all_prompt_types(self, system):
        """Test getting all prompt types."""
        assert system.get_all_prompt_types() == []

        system.register_prompt("task_analysis", "Text 1")
        system.register_prompt("tool_selection", "Text 2")
        system.register_prompt("reasoning", "Text 3")

        types = system.get_all_prompt_types()
        assert len(types) == 3
        assert "task_analysis" in types
        assert "tool_selection" in types
        assert "reasoning" in types


class TestPromptVersionManagement:
    """Tests for prompt version management."""

    def test_version_tracking(self, system):
        """Test version numbers are tracked correctly."""
        v1 = system.register_prompt("task_analysis", "V1", 1)
        v2 = system.register_prompt("task_analysis", "V2", 2)
        v3 = system.register_prompt("task_analysis", "V3", 3)

        p1 = system.get_prompt_version(v1)
        p2 = system.get_prompt_version(v2)
        p3 = system.get_prompt_version(v3)

        assert p1.version == 1
        assert p2.version == 2
        assert p3.version == 3

    def test_only_latest_version_is_active(self, system):
        """Test only the latest version is active."""
        v1 = system.register_prompt("task_analysis", "V1", 1)
        v2 = system.register_prompt("task_analysis", "V2", 2)
        v3 = system.register_prompt("task_analysis", "V3", 3)

        p1 = system.get_prompt_version(v1)
        p2 = system.get_prompt_version(v2)
        p3 = system.get_prompt_version(v3)

        assert p1.is_active is False
        assert p2.is_active is False
        assert p3.is_active is True

    def test_different_prompt_types_independent(self, system):
        """Test different prompt types are independent."""
        v1 = system.register_prompt("task_analysis", "Text 1")
        v2 = system.register_prompt("tool_selection", "Text 2")

        p1 = system.get_active_prompt("task_analysis")
        p2 = system.get_active_prompt("tool_selection")

        assert p1 is not None
        assert p2 is not None
        assert p1.prompt_id == v1
        assert p2.prompt_id == v2
        assert p1.is_active is True
        assert p2.is_active is True


class TestPromptPerformanceTracking:
    """Tests for prompt performance tracking."""

    def test_success_rate_calculation(self, system):
        """Test success rate is calculated correctly."""
        prompt_id = system.register_prompt("task_analysis", "Text")

        # 7 successes, 3 failures = 70% success rate
        for _ in range(7):
            system.record_prompt_outcome(prompt_id, True, False)
        for _ in range(3):
            system.record_prompt_outcome(prompt_id, False, False)

        prompt = system.get_prompt_version(prompt_id)
        assert prompt is not None
        assert prompt.success_rate == 0.7

    def test_hallucination_tracking(self, system):
        """Test hallucination count is tracked."""
        prompt_id = system.register_prompt("task_analysis", "Text")

        system.record_prompt_outcome(prompt_id, False, True)
        system.record_prompt_outcome(prompt_id, False, True)
        system.record_prompt_outcome(prompt_id, True, False)

        prompt = system.get_prompt_version(prompt_id)
        assert prompt is not None
        assert prompt.hallucination_count == 2
        assert prompt.total_uses == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



class TestPromptWeaknessIdentification:
    """Tests for prompt weakness identification."""

    def test_identify_weak_prompts(self, system):
        """Test identifying weak prompts."""
        # Register prompts with different performance
        good_prompt = system.register_prompt("type1", "Good prompt")
        weak_prompt = system.register_prompt("type2", "Weak prompt")

        # Record good performance for first prompt
        for _ in range(15):
            system.record_prompt_outcome(good_prompt, True, False)

        # Record poor performance for second prompt
        for _ in range(10):
            system.record_prompt_outcome(weak_prompt, False, False)
        for _ in range(5):
            system.record_prompt_outcome(weak_prompt, True, False)

        # Identify weak prompts
        weak_prompts = system.identify_weak_prompts(min_uses=10, max_success_rate=0.7)

        assert len(weak_prompts) == 1
        assert weak_prompts[0].prompt_id == weak_prompt
        assert weak_prompts[0].success_rate < 0.7

    def test_identify_weak_prompts_empty(self, system):
        """Test identifying weak prompts when none exist."""
        # Register prompt with good performance
        prompt_id = system.register_prompt("type1", "Good prompt")

        for _ in range(15):
            system.record_prompt_outcome(prompt_id, True, False)

        weak_prompts = system.identify_weak_prompts(min_uses=10, max_success_rate=0.7)
        assert len(weak_prompts) == 0

    def test_identify_weak_prompts_insufficient_data(self, system):
        """Test that prompts with insufficient data are not identified as weak."""
        prompt_id = system.register_prompt("type1", "Prompt")

        # Only 5 uses (below min_uses=10)
        for _ in range(5):
            system.record_prompt_outcome(prompt_id, False, False)

        weak_prompts = system.identify_weak_prompts(min_uses=10, max_success_rate=0.7)
        assert len(weak_prompts) == 0

    def test_get_prompt_weaknesses(self, system):
        """Test analyzing specific prompt weaknesses."""
        prompt_id = system.register_prompt("type1", "Prompt")

        # Record mixed outcomes
        for _ in range(7):
            system.record_prompt_outcome(prompt_id, True, False)
        for _ in range(2):
            system.record_prompt_outcome(prompt_id, False, True)  # Failures with hallucinations
        for _ in range(1):
            system.record_prompt_outcome(prompt_id, False, False)  # Failure without hallucination

        weaknesses = system.get_prompt_weaknesses(prompt_id)

        assert weaknesses["failure_rate"] == 0.3  # 3 failures out of 10
        assert weaknesses["hallucination_rate"] == 0.2  # 2 hallucinations out of 10
        assert weaknesses["success_rate"] == 0.7  # 7 successes out of 10
        assert weaknesses["total_uses"] == 10
        assert weaknesses["failure_count"] == 3
        assert weaknesses["hallucination_count"] == 2

    def test_get_prompt_weaknesses_nonexistent(self, system):
        """Test getting weaknesses for nonexistent prompt fails."""
        with pytest.raises(ValueError, match="Prompt .* not found"):
            system.get_prompt_weaknesses("nonexistent")

    def test_compare_prompt_versions(self, system):
        """Test comparing two prompt versions."""
        # Register version 1
        v1_id = system.register_prompt("type1", "Version 1", version=1)

        # Record poor performance for v1
        for _ in range(6):
            system.record_prompt_outcome(v1_id, True, False)
        for _ in range(4):
            system.record_prompt_outcome(v1_id, False, True)

        # Register version 2
        v2_id = system.register_prompt("type1", "Version 2", version=2)

        # Record better performance for v2
        for _ in range(9):
            system.record_prompt_outcome(v2_id, True, False)
        for _ in range(1):
            system.record_prompt_outcome(v2_id, False, False)

        comparison = system.compare_prompt_versions("type1", 1, 2)

        assert comparison["version1_success_rate"] == 0.6
        assert comparison["version2_success_rate"] == 0.9
        assert comparison["success_rate_diff"] == 0.3
        assert comparison["version1_hallucination_rate"] == 0.4
        assert comparison["version2_hallucination_rate"] == 0.0
        assert comparison["hallucination_diff"] == -0.4
        assert comparison["improvement_percentage"] == 50.0  # 50% improvement

    def test_compare_prompt_versions_nonexistent_v1(self, system):
        """Test comparing versions when v1 doesn't exist."""
        system.register_prompt("type1", "Version 2", version=2)

        with pytest.raises(ValueError, match="Version 1 .* not found"):
            system.compare_prompt_versions("type1", 1, 2)

    def test_compare_prompt_versions_nonexistent_v2(self, system):
        """Test comparing versions when v2 doesn't exist."""
        system.register_prompt("type1", "Version 1", version=1)

        with pytest.raises(ValueError, match="Version 2 .* not found"):
            system.compare_prompt_versions("type1", 1, 2)

    def test_should_replace_prompt_high_failure_rate(self, system):
        """Test that prompts with high failure rate should be replaced."""
        prompt_id = system.register_prompt("type1", "Prompt")

        # Record high failure rate (70%)
        for _ in range(7):
            system.record_prompt_outcome(prompt_id, False, False)
        for _ in range(3):
            system.record_prompt_outcome(prompt_id, True, False)

        # Add more to reach min_uses=20
        for _ in range(7):
            system.record_prompt_outcome(prompt_id, False, False)
        for _ in range(3):
            system.record_prompt_outcome(prompt_id, True, False)

        assert system.should_replace_prompt(prompt_id, min_uses=20, min_failure_rate=0.3)

    def test_should_replace_prompt_high_hallucination_rate(self, system):
        """Test that prompts with high hallucination rate should be replaced."""
        prompt_id = system.register_prompt("type1", "Prompt")

        # Record high hallucination rate (25%)
        for _ in range(15):
            system.record_prompt_outcome(prompt_id, True, False)
        for _ in range(5):
            system.record_prompt_outcome(prompt_id, False, True)

        # Hallucination rate is 25% (>20% threshold)
        assert system.should_replace_prompt(prompt_id, min_uses=20, min_failure_rate=0.3)

    def test_should_replace_prompt_good_performance(self, system):
        """Test that prompts with good performance should not be replaced."""
        prompt_id = system.register_prompt("type1", "Prompt")

        # Record good performance
        for _ in range(18):
            system.record_prompt_outcome(prompt_id, True, False)
        for _ in range(2):
            system.record_prompt_outcome(prompt_id, False, False)

        assert not system.should_replace_prompt(prompt_id, min_uses=20, min_failure_rate=0.3)

    def test_should_replace_prompt_insufficient_data(self, system):
        """Test that prompts with insufficient data should not be replaced."""
        prompt_id = system.register_prompt("type1", "Prompt")

        # Only 10 uses (below min_uses=20)
        for _ in range(10):
            system.record_prompt_outcome(prompt_id, False, False)

        assert not system.should_replace_prompt(prompt_id, min_uses=20, min_failure_rate=0.3)

    def test_should_replace_prompt_nonexistent(self, system):
        """Test that nonexistent prompts return False."""
        assert not system.should_replace_prompt("nonexistent")



class TestPromptImprovement:
    """Tests for prompt improvement generation."""

    def test_generate_improved_prompt_without_llm(self, system):
        """Test generating meta-prompt without LLM callable."""
        prompt_id = system.register_prompt("type1", "Original prompt text")

        # Record some failures to create weaknesses
        for _ in range(7):
            system.record_prompt_outcome(prompt_id, False, False)
        for _ in range(3):
            system.record_prompt_outcome(prompt_id, True, False)

        # Generate meta-prompt (no LLM callable)
        meta_prompt = system.generate_improved_prompt(prompt_id)

        # Verify meta-prompt contains key elements
        assert "Original prompt text" in meta_prompt
        assert "PERFORMANCE ANALYSIS" in meta_prompt
        assert "Success Rate" in meta_prompt
        assert "Failure Rate" in meta_prompt
        assert "IMPROVEMENT GUIDELINES" in meta_prompt
        assert "IMPROVED PROMPT:" in meta_prompt

    def test_generate_improved_prompt_with_llm(self, system):
        """Test generating improved prompt with LLM callable."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record failures
        for _ in range(10):
            system.record_prompt_outcome(prompt_id, False, False)

        # Mock LLM callable
        def mock_llm(prompt: str) -> str:
            return "Improved prompt based on analysis"

        # Generate improved prompt
        improved = system.generate_improved_prompt(prompt_id, mock_llm)

        assert improved == "Improved prompt based on analysis"

    def test_generate_improved_prompt_llm_failure(self, system):
        """Test handling of LLM generation failure."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record failures
        for _ in range(10):
            system.record_prompt_outcome(prompt_id, False, False)

        # Mock LLM that raises exception
        def failing_llm(prompt: str) -> str:
            raise Exception("LLM API error")

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="LLM generation failed"):
            system.generate_improved_prompt(prompt_id, failing_llm)

    def test_generate_improved_prompt_nonexistent(self, system):
        """Test generating improved prompt for nonexistent prompt fails."""
        with pytest.raises(ValueError, match="Prompt .* not found"):
            system.generate_improved_prompt("nonexistent")

    def test_generate_improved_prompt_high_hallucination(self, system):
        """Test meta-prompt focuses on hallucinations when rate is high."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record high hallucination rate (50%)
        for _ in range(10):
            system.record_prompt_outcome(prompt_id, False, True)
        for _ in range(10):
            system.record_prompt_outcome(prompt_id, True, False)

        meta_prompt = system.generate_improved_prompt(prompt_id)

        # Should identify hallucinations as primary issue
        assert "hallucinations" in meta_prompt.lower()
        assert "fabricat" in meta_prompt.lower()

    def test_generate_improved_prompt_high_failure(self, system):
        """Test meta-prompt focuses on failures when rate is high."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record high failure rate (80%)
        for _ in range(16):
            system.record_prompt_outcome(prompt_id, False, False)
        for _ in range(4):
            system.record_prompt_outcome(prompt_id, True, False)

        meta_prompt = system.generate_improved_prompt(prompt_id)

        # Should identify task failures as primary issue
        assert "task failures" in meta_prompt.lower()

    def test_generate_improved_prompt_low_success(self, system):
        """Test meta-prompt focuses on low success rate."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record low success rate (40%)
        for _ in range(12):
            system.record_prompt_outcome(prompt_id, False, False)
        for _ in range(8):
            system.record_prompt_outcome(prompt_id, True, False)

        meta_prompt = system.generate_improved_prompt(prompt_id)

        # Should identify low success rate as issue
        assert "success rate" in meta_prompt.lower()

    def test_generate_improved_prompt_strips_whitespace(self, system):
        """Test that improved prompt strips leading/trailing whitespace."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record failures
        for _ in range(10):
            system.record_prompt_outcome(prompt_id, False, False)

        # Mock LLM that returns prompt with whitespace
        def mock_llm(prompt: str) -> str:
            return "  \n  Improved prompt  \n  "

        improved = system.generate_improved_prompt(prompt_id, mock_llm)

        assert improved == "Improved prompt"
        assert not improved.startswith(" ")
        assert not improved.endswith(" ")

    def test_meta_prompt_includes_all_metrics(self, system):
        """Test that meta-prompt includes all performance metrics."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record mixed outcomes
        for _ in range(7):
            system.record_prompt_outcome(prompt_id, True, False)
        for _ in range(2):
            system.record_prompt_outcome(prompt_id, False, True)
        for _ in range(1):
            system.record_prompt_outcome(prompt_id, False, False)

        meta_prompt = system.generate_improved_prompt(prompt_id)

        # Verify all metrics are included
        assert "Total Uses: 10" in meta_prompt
        assert "Success Rate:" in meta_prompt
        assert "Failure Rate:" in meta_prompt
        assert "Hallucination Rate:" in meta_prompt
        assert "Prompt Type: type1" in meta_prompt
        assert "Version: 1" in meta_prompt

    def test_meta_prompt_includes_improvement_guidelines(self, system):
        """Test that meta-prompt includes comprehensive improvement guidelines."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Record failures
        for _ in range(10):
            system.record_prompt_outcome(prompt_id, False, False)

        meta_prompt = system.generate_improved_prompt(prompt_id)

        # Verify guidelines are included
        assert "IMPROVEMENT GUIDELINES" in meta_prompt
        assert "hallucination rate is high" in meta_prompt
        assert "failure rate is high" in meta_prompt
        assert "success rate is low" in meta_prompt
        assert "REQUIREMENTS" in meta_prompt
        assert "OUTPUT FORMAT" in meta_prompt



class TestPromptValidation:
    """Tests for prompt validation before adoption."""

    def test_validate_improved_prompt_better_performance(self, system):
        """Test validation when improved prompt performs better."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Mock validation callable - improved performs better
        def mock_validate(prompt: str, context: str) -> tuple[bool, bool]:
            if "Improved" in prompt:
                return (True, False)  # Success, no hallucination
            else:
                return (False, False)  # Failure

        should_adopt, metrics = system.validate_improved_prompt(
            prompt_id, "Improved prompt", mock_validate, min_validation_tasks=5
        )

        assert should_adopt is True
        assert metrics["improved_success_rate"] == 1.0
        assert metrics["original_success_rate"] == 0.0
        assert metrics["improvement"] == 1.0
        assert metrics["validation_tasks"] == 5

    def test_validate_improved_prompt_worse_performance(self, system):
        """Test validation when improved prompt performs worse."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Mock validation callable - improved performs worse
        def mock_validate(prompt: str, context: str) -> tuple[bool, bool]:
            if "Improved" in prompt:
                return (False, False)  # Failure
            else:
                return (True, False)  # Success

        should_adopt, metrics = system.validate_improved_prompt(
            prompt_id, "Improved prompt", mock_validate, min_validation_tasks=5
        )

        assert should_adopt is False
        assert metrics["improved_success_rate"] == 0.0
        assert metrics["original_success_rate"] == 1.0
        assert metrics["improvement"] == -1.0

    def test_validate_improved_prompt_high_hallucination(self, system):
        """Test validation rejects prompts with high hallucination rate."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Mock validation callable - improved has high hallucinations
        def mock_validate(prompt: str, context: str) -> tuple[bool, bool]:
            if "Improved" in prompt:
                return (True, True)  # Success but hallucination
            else:
                return (True, False)  # Success, no hallucination

        should_adopt, metrics = system.validate_improved_prompt(
            prompt_id, "Improved prompt", mock_validate, min_validation_tasks=5
        )

        # Should reject due to high hallucination rate
        assert should_adopt is False
        assert metrics["improved_hallucination_rate"] == 1.0

    def test_validate_improved_prompt_nonexistent(self, system):
        """Test validation fails for nonexistent prompt."""

        def mock_validate(prompt: str, context: str) -> tuple[bool, bool]:
            return (True, False)

        with pytest.raises(ValueError, match="Prompt .* not found"):
            system.validate_improved_prompt(
                "nonexistent", "Improved prompt", mock_validate
            )

    def test_validate_improved_prompt_validation_failure(self, system):
        """Test handling of validation callable failure."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Mock validation callable that raises exception
        def failing_validate(prompt: str, context: str) -> tuple[bool, bool]:
            raise Exception("Validation error")

        with pytest.raises(RuntimeError, match="Validation failed on task"):
            system.validate_improved_prompt(
                prompt_id, "Improved prompt", failing_validate
            )

    def test_validate_improved_prompt_marginal_improvement(self, system):
        """Test validation with marginal improvement."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        call_count = [0]

        # Mock validation callable - marginal improvement
        def mock_validate(prompt: str, context: str) -> tuple[bool, bool]:
            call_count[0] += 1
            if "Improved" in prompt:
                # 60% success rate
                return (call_count[0] % 5 < 3, False)
            else:
                # 40% success rate
                return (call_count[0] % 5 < 2, False)

        should_adopt, metrics = system.validate_improved_prompt(
            prompt_id, "Improved prompt", mock_validate, min_validation_tasks=10
        )

        # Should adopt even with marginal improvement
        assert should_adopt is True
        assert metrics["improvement"] > 0.0

    def test_validate_improved_prompt_equal_performance(self, system):
        """Test validation when performance is equal."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        # Mock validation callable - equal performance
        def mock_validate(prompt: str, context: str) -> tuple[bool, bool]:
            return (True, False)  # Both succeed equally

        should_adopt, metrics = system.validate_improved_prompt(
            prompt_id, "Improved prompt", mock_validate, min_validation_tasks=5
        )

        # Should not adopt if no improvement
        assert should_adopt is False
        assert metrics["improvement"] == 0.0

    def test_validate_improved_prompt_metrics_rounded(self, system):
        """Test that validation metrics are rounded to 2 decimals."""
        prompt_id = system.register_prompt("type1", "Original prompt")

        call_count = [0]

        # Mock validation callable - creates non-round numbers
        def mock_validate(prompt: str, context: str) -> tuple[bool, bool]:
            call_count[0] += 1
            if "Improved" in prompt:
                return (call_count[0] % 3 == 0, False)  # 33.33% success
            else:
                return (call_count[0] % 4 == 0, False)  # 25% success

        should_adopt, metrics = system.validate_improved_prompt(
            prompt_id, "Improved prompt", mock_validate, min_validation_tasks=12
        )

        # Check all metrics are rounded
        assert isinstance(metrics["improved_success_rate"], float)
        assert isinstance(metrics["original_success_rate"], float)
        assert isinstance(metrics["improvement"], float)
        # Verify rounding (should have at most 2 decimal places)
        assert len(str(metrics["improved_success_rate"]).split(".")[-1]) <= 2


class TestPromptEvolutionProperties:
    """Property-based tests for prompt evolution system."""

    @given(
        success_count=st.integers(min_value=0, max_value=100),
        failure_count=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=10)  # Reduce examples for faster testing
    def test_property_success_rate_always_between_0_and_1(
        self, success_count, failure_count
    ):
        """Property: Success rate must always be between 0 and 1."""
        assume(success_count + failure_count > 0)  # Avoid division by zero

        # Create fresh system for each iteration with named temp file
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)  # Close file descriptor immediately

        try:
            DatabaseSchema.create_schema(db_path)
            pool = ConnectionPool(db_path, min_size=1, max_size=5)
            system = PromptEvolutionSystem(pool)

            prompt_id = system.register_prompt("type1", "Test prompt")

            # Record outcomes
            for _ in range(success_count):
                system.record_prompt_outcome(prompt_id, True, False)
            for _ in range(failure_count):
                system.record_prompt_outcome(prompt_id, False, False)

            prompt = system.get_prompt_version(prompt_id)
            assert prompt is not None
            assert 0.0 <= prompt.success_rate <= 1.0

            # Explicitly close pool before cleanup
            pool.close_all()
            del system
            del pool
            gc.collect()  # Force garbage collection
        finally:
            # Clean up temp file
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass  # Ignore if file is still locked or already deleted

    @given(
        iterations=st.integers(min_value=1, max_value=20),
        success_rate_increase=st.floats(min_value=0.05, max_value=0.3),
    )
    def test_property_prompt_quality_improves_over_iterations(
        self, iterations, success_rate_increase
    ):
        """Property: Prompt quality must improve over iterations."""
        # Create fresh system for each iteration
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            DatabaseSchema.create_schema(str(db_path))
            pool = ConnectionPool(str(db_path), min_size=1, max_size=5)
            system = PromptEvolutionSystem(pool)

            prompt_type = "task_analysis"
            current_success_rate = 0.5

            # Register initial prompt
            prompt_id = system.register_prompt(prompt_type, "Prompt v1", version=1)

            # Record initial performance
            for i in range(20):
                success = i < int(20 * current_success_rate)
                system.record_prompt_outcome(prompt_id, success, False)

            previous_rate = current_success_rate

            # Simulate iterations of improvement
            for iteration in range(2, iterations + 2):
                # Each iteration should improve
                current_success_rate = min(1.0, previous_rate + success_rate_increase)

                # Register new version
                new_prompt_id = system.register_prompt(
                    prompt_type, f"Prompt v{iteration}", version=iteration
                )

                # Record improved performance
                for i in range(20):
                    success = i < int(20 * current_success_rate)
                    system.record_prompt_outcome(new_prompt_id, success, False)

                # Verify improvement
                new_prompt = system.get_prompt_version(new_prompt_id)
                assert new_prompt is not None
                assert new_prompt.success_rate >= previous_rate

                previous_rate = current_success_rate

            pool.close_all()
            import time
            time.sleep(0.01)  # Small delay to ensure file handles are released

    @given(
        total_uses=st.integers(min_value=10, max_value=100),
        failure_rate=st.floats(min_value=0.3, max_value=0.9),
    )
    def test_property_weak_prompts_identified_correctly(
        self, total_uses, failure_rate
    ):
        """Property: Weak prompts must be identified when failure rate is high."""
        # Create fresh system for each iteration
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            DatabaseSchema.create_schema(str(db_path))
            pool = ConnectionPool(str(db_path), min_size=1, max_value=5)
            system = PromptEvolutionSystem(pool)

            prompt_id = system.register_prompt("type1", "Weak prompt")

            # Record outcomes with specified failure rate
            failures = int(total_uses * failure_rate)
            successes = total_uses - failures

            for _ in range(successes):
                system.record_prompt_outcome(prompt_id, True, False)
            for _ in range(failures):
                system.record_prompt_outcome(prompt_id, False, False)

            # Identify weak prompts
            weak_prompts = system.identify_weak_prompts(
                min_uses=10, max_success_rate=0.7
            )

            # Should be identified as weak if success rate <= 0.7
            prompt = system.get_prompt_version(prompt_id)
            if prompt and prompt.success_rate <= 0.7:
                assert any(p.prompt_id == prompt_id for p in weak_prompts)

            pool.close_all()
            import time
            time.sleep(0.01)  # Small delay to ensure file handles are released

    @given(
        v1_success=st.integers(min_value=0, max_value=20),
        v2_success=st.integers(min_value=0, max_value=20),
    )
    def test_property_version_comparison_is_consistent(
        self, v1_success, v2_success
    ):
        """Property: Version comparison must be mathematically consistent."""
        # Create fresh system for each iteration
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            DatabaseSchema.create_schema(str(db_path))
            pool = ConnectionPool(str(db_path), min_size=1, max_size=5)
            system = PromptEvolutionSystem(pool)

            prompt_type = "type1"

            # Register version 1
            v1_id = system.register_prompt(prompt_type, "V1", version=1)
            for i in range(20):
                system.record_prompt_outcome(v1_id, i < v1_success, False)

            # Register version 2
            v2_id = system.register_prompt(prompt_type, "V2", version=2)
            for i in range(20):
                system.record_prompt_outcome(v2_id, i < v2_success, False)

            # Compare versions
            comparison = system.compare_prompt_versions(prompt_type, 1, 2)

            # Verify mathematical consistency
            v1_rate = v1_success / 20
            v2_rate = v2_success / 20
            expected_diff = round(v2_rate - v1_rate, 2)

            assert comparison["success_rate_diff"] == expected_diff
            assert comparison["version1_success_rate"] == round(v1_rate, 2)
            assert comparison["version2_success_rate"] == round(v2_rate, 2)

            pool.close_all()
            import time
            time.sleep(0.01)  # Small delay to ensure file handles are released

    @given(
        prompt_text=st.text(min_size=10, max_size=200),
        total_uses=st.integers(min_value=5, max_value=50),
    )
    def test_property_prompt_registration_always_succeeds(
        self, prompt_text, total_uses
    ):
        """Property: Valid prompt registration must always succeed."""
        assume(len(prompt_text.strip()) > 0)  # Non-empty after strip

        # Create fresh system for each iteration
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            DatabaseSchema.create_schema(str(db_path))
            pool = ConnectionPool(str(db_path), min_size=1, max_size=5)
            system = PromptEvolutionSystem(pool)

            prompt_id = system.register_prompt("type1", prompt_text)

            # Verify registration
            prompt = system.get_prompt_version(prompt_id)
            assert prompt is not None
            assert prompt.content == prompt_text
            assert prompt.is_active is True

            # Record some outcomes
            for i in range(total_uses):
                system.record_prompt_outcome(prompt_id, i % 2 == 0, False)

            # Verify stats updated
            prompt = system.get_prompt_version(prompt_id)
            assert prompt is not None
            assert prompt.total_uses == total_uses

            pool.close_all()
            import time
            time.sleep(0.01)  # Small delay to ensure file handles are released

    @given(
        hallucination_rate=st.floats(min_value=0.2, max_value=0.8),
        total_uses=st.integers(min_value=20, max_value=50),
    )
    def test_property_high_hallucination_triggers_replacement(
        self, hallucination_rate, total_uses
    ):
        """Property: High hallucination rate must trigger replacement recommendation."""
        # Create fresh system for each iteration
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            DatabaseSchema.create_schema(str(db_path))
            pool = ConnectionPool(str(db_path), min_size=1, max_size=5)
            system = PromptEvolutionSystem(pool)

            prompt_id = system.register_prompt("type1", "Prompt")

            # Record outcomes with specified hallucination rate
            hallucinations = int(total_uses * hallucination_rate)

            for i in range(total_uses):
                success = i % 2 == 0
                hallucination = i < hallucinations
                system.record_prompt_outcome(prompt_id, success, hallucination)

            # Check replacement recommendation
            should_replace = system.should_replace_prompt(
                prompt_id, min_uses=20, min_failure_rate=0.3
            )

            # Should recommend replacement if hallucination rate >= 20%
            if hallucination_rate >= 0.2:
                assert should_replace is True

            pool.close_all()
            import time
            time.sleep(0.01)  # Small delay to ensure file handles are released
