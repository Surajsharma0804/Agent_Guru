"""
Tests for parallel execution engine.

Coverage Target: 80%+
"""

import time

import pytest

from Agent_Guru.reasoning.execution.parallel_executor import (
    ParallelExecutionController,
    ParallelExecutor,
    StepExecution,
)


class TestStepExecution:
    """Tests for StepExecution data model."""

    def test_initialization(self):
        """Test StepExecution initialization."""

        def mock_func(params):
            return "result"

        step = StepExecution(
            step_id="step1",
            tool_function=mock_func,
            parameters={"param1": "value1"},
            depends_on=["step0"],
            timeout=5.0,
        )

        assert step.step_id == "step1"  # nosec B101
        assert step.tool_function == mock_func  # nosec B101
        assert step.parameters == {"param1": "value1"}  # nosec B101
        assert step.depends_on == ["step0"]  # nosec B101
        assert step.timeout == 5.0  # nosec B101


class TestParallelExecutor:
    """Tests for ParallelExecutor."""

    @pytest.mark.asyncio
    async def test_execute_single_step(self):
        """Test executing a single step."""

        def mock_func(params):
            return {"result": "success"}

        executor = ParallelExecutor()
        steps = [
            StepExecution(
                step_id="step1",
                tool_function=mock_func,
                parameters={},
                depends_on=[],
            )
        ]

        result = await executor.execute_parallel(steps)

        assert result.success is True  # nosec B101
        assert len(result.step_results) == 1  # nosec B101
        assert result.step_results["step1"].success is True  # nosec B101
        assert result.step_results["step1"].result_data == {"result": "success"}  # nosec B101
        assert result.parallel_batches == 1  # nosec B101
        assert result.failed_steps == []  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_independent_steps_parallel(self):
        """Test executing independent steps in parallel."""
        execution_order = []

        def make_func(step_id):
            def func(params):
                execution_order.append(step_id)
                time.sleep(0.1)  # Simulate work
                return {"step": step_id}

            return func

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", make_func("step1"), {}, []),
            StepExecution("step2", make_func("step2"), {}, []),
            StepExecution("step3", make_func("step3"), {}, []),
        ]

        start_time = time.perf_counter()
        result = await executor.execute_parallel(steps)
        elapsed = time.perf_counter() - start_time

        assert result.success is True  # nosec B101
        assert len(result.step_results) == 3  # nosec B101
        assert result.parallel_batches == 1  # All in one batch  # nosec B101
        # Should take ~0.1s (parallel) not ~0.3s (sequential)
        assert elapsed < 0.25  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_dependent_steps_sequential(self):
        """Test executing dependent steps sequentially."""
        execution_order = []

        def make_func(step_id):
            def func(params):
                execution_order.append(step_id)
                return {"step": step_id}

            return func

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", make_func("step1"), {}, []),
            StepExecution("step2", make_func("step2"), {}, ["step1"]),
            StepExecution("step3", make_func("step3"), {}, ["step2"]),
        ]

        result = await executor.execute_parallel(steps)

        assert result.success is True  # nosec B101
        assert len(result.step_results) == 3  # nosec B101
        assert result.parallel_batches == 3  # Three sequential batches  # nosec B101
        # Verify execution order
        assert execution_order == ["step1", "step2", "step3"]  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_mixed_dependencies(self):
        """Test executing steps with mixed dependencies."""

        def mock_func(params):
            return {"result": "success"}

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", mock_func, {}, []),
            StepExecution("step2", mock_func, {}, []),
            StepExecution("step3", mock_func, {}, ["step1", "step2"]),
            StepExecution("step4", mock_func, {}, ["step1"]),
        ]

        result = await executor.execute_parallel(steps)

        assert result.success is True  # nosec B101
        assert len(result.step_results) == 4  # nosec B101
        assert result.parallel_batches == 2  # Batch 1: step1,step2; Batch 2: step3,step4  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_failure_fail_fast(self):
        """Test execution with failure and fail_fast=True."""

        def success_func(params):
            return {"result": "success"}

        def failure_func(params):
            raise ValueError("Test error")

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", failure_func, {}, []),
            StepExecution("step2", success_func, {}, []),
            StepExecution("step3", success_func, {}, ["step1"]),
        ]

        result = await executor.execute_parallel(steps, fail_fast=True)

        assert result.success is False  # nosec B101
        assert "step1" in result.failed_steps  # nosec B101
        # step3 should not execute due to fail_fast
        assert "step3" not in result.step_results or not result.step_results["step3"].success  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_failure_continue(self):
        """Test execution with failure and fail_fast=False."""

        def success_func(params):
            return {"result": "success"}

        def failure_func(params):
            raise ValueError("Test error")

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", failure_func, {}, []),
            StepExecution("step2", success_func, {}, []),
        ]

        result = await executor.execute_parallel(steps, fail_fast=False)

        assert result.success is False  # nosec B101
        assert "step1" in result.failed_steps  # nosec B101
        assert result.step_results["step1"].success is False  # nosec B101
        assert result.step_results["step2"].success is True  # nosec B101

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test execution with timeout."""

        def slow_func(params):
            time.sleep(2.0)
            return {"result": "success"}

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", slow_func, {}, [], timeout=0.5),
        ]

        result = await executor.execute_parallel(steps)

        assert result.success is False  # nosec B101
        assert "step1" in result.failed_steps  # nosec B101
        assert result.step_results["step1"].error["error_code"] == "TIMEOUT"  # nosec B101

    def test_build_execution_batches_independent(self):
        """Test building batches for independent steps."""

        def mock_func(params):
            return {}

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", mock_func, {}, []),
            StepExecution("step2", mock_func, {}, []),
            StepExecution("step3", mock_func, {}, []),
        ]

        batches = executor._build_execution_batches(steps)

        assert len(batches) == 1  # nosec B101
        assert len(batches[0]) == 3  # nosec B101

    def test_build_execution_batches_sequential(self):
        """Test building batches for sequential steps."""

        def mock_func(params):
            return {}

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", mock_func, {}, []),
            StepExecution("step2", mock_func, {}, ["step1"]),
            StepExecution("step3", mock_func, {}, ["step2"]),
        ]

        batches = executor._build_execution_batches(steps)

        assert len(batches) == 3  # nosec B101
        assert len(batches[0]) == 1  # nosec B101
        assert batches[0][0].step_id == "step1"  # nosec B101
        assert batches[1][0].step_id == "step2"  # nosec B101
        assert batches[2][0].step_id == "step3"  # nosec B101

    def test_build_execution_batches_diamond(self):
        """Test building batches for diamond dependency pattern."""

        def mock_func(params):
            return {}

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", mock_func, {}, []),
            StepExecution("step2", mock_func, {}, ["step1"]),
            StepExecution("step3", mock_func, {}, ["step1"]),
            StepExecution("step4", mock_func, {}, ["step2", "step3"]),
        ]

        batches = executor._build_execution_batches(steps)

        assert len(batches) == 3  # nosec B101
        assert len(batches[0]) == 1  # step1  # nosec B101
        assert len(batches[1]) == 2  # step2, step3  # nosec B101
        assert len(batches[2]) == 1  # step4  # nosec B101

    def test_detect_independent_steps(self):
        """Test detecting independent steps."""

        def mock_func(params):
            return {}

        executor = ParallelExecutor()
        steps = [
            StepExecution("step1", mock_func, {}, []),
            StepExecution("step2", mock_func, {}, []),
            StepExecution("step3", mock_func, {}, ["step1", "step2"]),
        ]

        batches = executor.detect_independent_steps(steps)

        assert len(batches) == 2  # nosec B101
        assert set(batches[0]) == {"step1", "step2"}  # nosec B101
        assert batches[1] == ["step3"]  # nosec B101


class TestParallelExecutionController:
    """Tests for ParallelExecutionController."""

    @pytest.mark.asyncio
    async def test_execute(self):
        """Test executing through controller."""

        def mock_func(params):
            return {"result": "success"}

        controller = ParallelExecutionController()
        steps = [
            StepExecution("step1", mock_func, {}, []),
            StepExecution("step2", mock_func, {}, []),
        ]

        result = await controller.execute(steps)

        assert result.success is True  # nosec B101
        assert len(result.step_results) == 2  # nosec B101

    def test_analyze_dependencies(self):
        """Test dependency analysis."""

        def mock_func(params):
            return {}

        controller = ParallelExecutionController()
        steps = [
            StepExecution("step1", mock_func, {}, []),
            StepExecution("step2", mock_func, {}, []),
            StepExecution("step3", mock_func, {}, ["step1", "step2"]),
        ]

        analysis = controller.analyze_dependencies(steps)

        assert analysis["total_steps"] == 3  # nosec B101
        assert analysis["parallel_batches"] == 2  # nosec B101
        assert analysis["max_parallelism"] == 2  # nosec B101
        assert len(analysis["batches"]) == 2  # nosec B101


class TestParallelExecutionResult:
    """Tests for ParallelExecutionResult."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from Agent_Guru.reasoning.execution.executor import ExecutionResult

        result = ExecutionResult(
            success=True,
            result_data={"output": "test"},
            execution_time=1.0,
            action_id="step1",
        )

        from Agent_Guru.reasoning.execution.parallel_executor import ParallelExecutionResult

        parallel_result = ParallelExecutionResult(
            success=True,
            step_results={"step1": result},
            total_time=1.5,
            parallel_batches=1,
            failed_steps=[],
        )

        result_dict = parallel_result.to_dict()

        assert result_dict["success"] is True  # nosec B101
        assert "step1" in result_dict["step_results"]  # nosec B101
        assert result_dict["total_time"] == 1.5  # nosec B101
        assert result_dict["parallel_batches"] == 1  # nosec B101
        assert result_dict["failed_steps"] == []  # nosec B101


class TestIntegration:
    """Integration tests for parallel execution."""

    @pytest.mark.asyncio
    async def test_complex_dependency_graph(self):
        """Test execution with complex dependency graph."""
        execution_log = []

        def make_func(step_id, duration=0.05):
            def func(params):
                execution_log.append(("start", step_id))
                time.sleep(duration)
                execution_log.append(("end", step_id))
                return {"step": step_id}

            return func

        controller = ParallelExecutionController()
        steps = [
            StepExecution("A", make_func("A"), {}, []),
            StepExecution("B", make_func("B"), {}, []),
            StepExecution("C", make_func("C"), {}, ["A"]),
            StepExecution("D", make_func("D"), {}, ["A"]),
            StepExecution("E", make_func("E"), {}, ["B"]),
            StepExecution("F", make_func("F"), {}, ["C", "D", "E"]),
        ]

        result = await controller.execute(steps)

        assert result.success is True  # nosec B101
        assert len(result.step_results) == 6  # nosec B101
        # Verify all steps completed
        for step_id in ["A", "B", "C", "D", "E", "F"]:
            assert result.step_results[step_id].success is True  # nosec B101

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self):
        """Test handling of partial failures."""

        def success_func(params):
            return {"result": "success"}

        def failure_func(params):
            raise ValueError("Intentional failure")

        controller = ParallelExecutionController()
        steps = [
            StepExecution("step1", success_func, {}, []),
            StepExecution("step2", failure_func, {}, []),
            StepExecution("step3", success_func, {}, []),
            StepExecution("step4", success_func, {}, ["step1", "step3"]),
        ]

        result = await controller.execute(steps, fail_fast=False)

        assert result.success is False  # nosec B101
        assert "step2" in result.failed_steps  # nosec B101
        # step1 and step3 should succeed
        assert result.step_results["step1"].success is True  # nosec B101
        assert result.step_results["step3"].success is True  # nosec B101
        # step4 should succeed (doesn't depend on step2)
        assert result.step_results["step4"].success is True  # nosec B101
