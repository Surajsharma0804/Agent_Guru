"""Core Verifier System API.

Orchestrates all verification components with async parallel execution.
Integrates with LLM Runtime, Agent Orchestration, and Memory System.

Requirements: 8.1-8.5, 9.1-9.5, 10.1-10.5, 12.1-12.5
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any

from Agent_Guru.verifier.confidence_scorer import ConfidenceScorer
from Agent_Guru.verifier.feedback_generator import SelfCorrectionFeedbackGenerator
from Agent_Guru.verifier.hallucination_detector import HallucinationDetector
from Agent_Guru.verifier.loop_detector import LoopDetector
from Agent_Guru.verifier.models import (
    VerificationConfig,
    VerificationResult,
    VerificationStatus,
)
from Agent_Guru.verifier.output_validator import OutputValidator
from Agent_Guru.verifier.result_storage import VerificationResultStorage
from Agent_Guru.verifier.strategy_selector import VerificationStrategySelector
from Agent_Guru.verifier.tool_output_checker import ToolOutputChecker

logger = logging.getLogger(__name__)


class VerifierSystem:
    """Core verification system for Agent_Guru.

    Provides:
    - verify_llm_response: Verify LLM outputs before forwarding
    - verify_task_output: Verify task outputs before completion
    - verify_before_storage: Verify information before Memory System storage

    All methods are async and execute strategies in parallel for low latency.
    Target: 95th percentile latency < 200ms
    """

    def __init__(
        self,
        config: VerificationConfig | None = None,
        db_path: str = ":memory:",
    ) -> None:
        self.config = config or VerificationConfig()
        self._hallucination_detector = HallucinationDetector(
            confidence_threshold=self.config.hallucination_confidence_threshold
        )
        self._output_validator = OutputValidator()
        self._tool_checker = ToolOutputChecker()
        self._loop_detector = LoopDetector(
            threshold=self.config.loop_detection_threshold
        )
        self._confidence_scorer = ConfidenceScorer(
            min_threshold=self.config.min_confidence_threshold
        )
        self._strategy_selector = VerificationStrategySelector()
        self._feedback_generator = SelfCorrectionFeedbackGenerator()
        self._storage = VerificationResultStorage(db_path=db_path)

        # LRU cache for repeated verifications
        self._cache: OrderedDict[str, VerificationResult] = OrderedDict()
        self._cache_max_size = 256

        # Failure reporting for Self-Improvement Engine
        self._failure_reports: list[dict[str, Any]] = []

        # Priority-based concurrency control (task 14.2)
        # critical/high: unlimited slots; normal: up to 8 concurrent; low: up to 4 concurrent
        self._semaphore_normal = asyncio.Semaphore(8)
        self._semaphore_low = asyncio.Semaphore(4)

        # Priority numeric mapping (lower = higher priority)
        self._priority_map: dict[str, int] = {
            "critical": 0,
            "high": 1,
            "normal": 2,
            "low": 3,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def verify_llm_response(
        self,
        response: str,
        context: dict[str, Any] | None = None,
        expected_format: str | None = None,
        expected_facts: list[str] | None = None,
        session_id: str | None = None,
        priority: str = "normal",
    ) -> VerificationResult:
        """Verify an LLM response before forwarding to agent.

        Runs hallucination detection, output validation, loop detection,
        and confidence scoring in parallel.

        Args:
            response: The LLM response text
            context: Optional context for cross-reference validation
            expected_format: Optional format hint ("json", "xml", "markdown")
            expected_facts: Optional known facts for consistency checking
            session_id: Optional session ID for loop detection
            priority: Verification priority ("low", "normal", "high", "critical")

        Returns:
            VerificationResult
        """
        # Cache check — skip cache when session_id is provided (loop detector needs to accumulate state)
        use_cache = self.config.enable_caching and session_id is None
        cache_key = ""
        # Normalize response to string
        if response is None:
            response = ""
        elif not isinstance(response, str):
            response = str(response)
        if use_cache:
            cache_key = self._cache_key("llm", response, expected_format or "")
            if cache_key in self._cache:
                return self._cache[cache_key]

        # Priority-based concurrency control: throttle low/normal, pass-through critical/high
        slot = await self._acquire_priority_slot(priority)
        try:
            start = time.perf_counter()
            strategy = self._strategy_selector.select_for_llm_response(
                response, context, task_type=None
            )

            result = await self._run_verification(
                text=response,
                context=context,
                expected_format=expected_format,
                expected_facts=expected_facts,
                session_id=session_id,
                strategy=strategy,
                context_type="llm_response",
            )
        finally:
            if slot is not None:
                slot.release()

        result.latency_ms = (time.perf_counter() - start) * 1000

        # Cache result
        if use_cache and cache_key:
            self._cache_put(cache_key, result)

        # Store and report
        try:
            self._storage.store(result, context_type="llm_response")
        except Exception as e:
            logger.warning("Failed to store verification result (non-fatal): %s", e)
        if result.failed:
            self._record_failure(result, "llm_response")
            logger.info(
                "LLM response verification FAILED | confidence=%.3f | latency=%.1fms | issues=%s",
                result.confidence,
                result.latency_ms,
                result.feedback.issues[:3],
            )
        elif result.latency_ms > self.config.max_latency_ms:
            logger.warning(
                "High latency detected | context=llm_response | latency=%.1fms | threshold=%.1fms",
                result.latency_ms,
                self.config.max_latency_ms,
            )
        else:
            logger.debug(
                "LLM response verification %s | confidence=%.3f | latency=%.1fms",
                result.status.value,
                result.confidence,
                result.latency_ms,
            )

        return result

    async def verify_task_output(
        self,
        task_id: str,
        output: Any,
        expected_schema: dict[str, Any] | None = None,
        priority: str = "normal",
    ) -> VerificationResult:
        """Verify task output before marking task complete.

        Args:
            task_id: Unique task identifier
            output: The task output
            expected_schema: Optional expected output schema
            priority: Verification priority ("low", "normal", "high", "critical")

        Returns:
            VerificationResult
        """
        slot = await self._acquire_priority_slot(priority)
        try:
            start = time.perf_counter()
            strategy = self._strategy_selector.select_for_task_output(
                output, expected_schema
            )

            # Pass raw output for validation; use string form for hallucination/loop detection
            text = output if isinstance(output, str) else str(output)
            result = await self._run_verification(
                text=text,
                raw_output=output,
                expected_schema=expected_schema,
                strategy=strategy,
                context_type="task_output",
            )
        finally:
            if slot is not None:
                slot.release()

        result.latency_ms = (time.perf_counter() - start) * 1000
        result.metadata["task_id"] = task_id

        try:
            self._storage.store(result, context_type="task_output")
        except Exception as e:
            logger.warning("Failed to store task output result (non-fatal): %s", e)
        if result.failed:
            self._record_failure(result, "task_output")
            logger.info(
                "Task output verification FAILED | task_id=%s | confidence=%.3f | latency=%.1fms",
                task_id,
                result.confidence,
                result.latency_ms,
            )
        elif result.latency_ms > self.config.max_latency_ms:
            logger.warning(
                "High latency detected | context=task_output | task_id=%s | latency=%.1fms",
                task_id,
                result.latency_ms,
            )

        return result

    async def verify_before_storage(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> VerificationResult:
        """Verify information before storing in Memory System.

        Prevents hallucinated information from being persisted.

        Args:
            content: The content to verify
            metadata: Optional metadata about the content

        Returns:
            VerificationResult — storage should be blocked if result.failed
        """
        start = time.perf_counter()

        # For storage verification, focus on hallucination detection
        strategy = self._strategy_selector.select_for_llm_response(content)
        strategy.use_tool_checking = False
        strategy.use_loop_detection = False

        result = await self._run_verification(
            text=content,
            strategy=strategy,
            context_type="storage",
        )

        result.latency_ms = (time.perf_counter() - start) * 1000
        if metadata:
            result.metadata.update(metadata)

        try:
            self._storage.store(result, context_type="storage")
        except Exception as e:
            logger.warning("Failed to store pre-storage result (non-fatal): %s", e)
        return result

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration at runtime."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info("Config updated: %s = %s", key, value)

    def get_failure_reports(self) -> list[dict[str, Any]]:
        """Get failure reports for Self-Improvement Engine."""
        return list(self._failure_reports)

    def get_accuracy_metrics(self) -> dict[str, Any]:
        """Get accuracy metrics from stored results."""
        metrics = self._storage.compute_accuracy_metrics()
        return {
            "total": metrics.total_verifications,
            "false_positive_rate": metrics.false_positive_rate,
            "false_negative_rate": metrics.false_negative_rate,
            "accuracy": metrics.accuracy,
            "p95_latency_ms": self._storage.get_latency_percentile(95),
        }

    def register_tool_schema(self, tool_name: str, schema: dict[str, Any]) -> None:
        """Register expected output schema for a tool."""
        self._tool_checker.register_tool_schema(tool_name, schema)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_verification(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        expected_format: str | None = None,
        expected_facts: list[str] | None = None,
        expected_schema: dict[str, Any] | None = None,
        raw_output: Any = None,
        session_id: str | None = None,
        strategy: Any = None,
        context_type: str = "",
    ) -> VerificationResult:
        """Execute verification strategies in parallel with timeout and graceful degradation.

        If individual strategies fail or time out, they are skipped and the
        remaining strategies still produce a result (graceful degradation).
        """
        from Agent_Guru.verifier.strategy_selector import VerificationStrategy

        if strategy is None:
            strategy = VerificationStrategy()

        # Validate inputs — gracefully handle None/empty text
        if not isinstance(text, str):
            try:
                text = str(text)
            except Exception as e:
                text = ""


        # Build coroutines for parallel execution
        tasks: dict[str, Any] = {}
        loop = asyncio.get_running_loop()

        if strategy.use_hallucination_detection and self.config.enable_hallucination_detection:
            _text, _ctx, _facts = text, context, expected_facts
            tasks["hallucination"] = loop.run_in_executor(
                None,
                lambda: self._hallucination_detector.detect(_text, _ctx, _facts),
            )

        if strategy.use_output_validation and self.config.enable_output_validation:
            # Use raw_output if provided (e.g. dict/list), otherwise use text
            validate_target = raw_output if raw_output is not None else text
            _vt, _schema, _fmt = validate_target, expected_schema, expected_format
            tasks["validation"] = loop.run_in_executor(
                None,
                lambda: self._output_validator.validate(_vt, _schema, _fmt),
            )

        if strategy.use_loop_detection and self.config.enable_loop_detection and session_id:
            _sid, _text2 = session_id, text
            tasks["loop"] = loop.run_in_executor(
                None,
                lambda: self._loop_detector.record_state(_sid, _text2),
            )

        # Await all tasks in parallel with per-task timeout
        results: dict[str, Any] = {}
        if tasks:
            task_names = list(tasks.keys())
            task_coros = list(tasks.values())
            timeout_s = self.config.max_latency_ms / 1000.0

            try:
                completed = await asyncio.wait_for(
                    asyncio.gather(*task_coros, return_exceptions=True),
                    timeout=timeout_s,
                )
                for name, res in zip(task_names, completed):
                    if not isinstance(res, Exception):
                        results[name] = res
                    else:
                        logger.warning(
                            "Verification strategy '%s' failed (graceful degradation): %s",
                            name,
                            res,
                        )
            except asyncio.TimeoutError:
                logger.warning(
                    "Verification timed out after %.0fms — returning degraded result",
                    self.config.max_latency_ms,
                )

        hallucination = results.get("hallucination")
        validation = results.get("validation")
        loop_detection = results.get("loop")

        # Confidence scoring
        confidence_score = None
        if strategy.use_confidence_scoring and self.config.enable_confidence_scoring:
            confidence_score = self._confidence_scorer.compute(
                hallucination=hallucination,
                validation=validation,
                loop_detection=loop_detection,
            )

        # Feedback generation
        feedback = self._feedback_generator.generate(
            hallucination=hallucination,
            validation=validation,
            loop_detection=loop_detection,
        )

        # Determine overall status
        status = self._determine_status(
            hallucination=hallucination,
            validation=validation,
            loop_detection=loop_detection,
            confidence_score=confidence_score,
        )

        from Agent_Guru.verifier.models import (
            HallucinationDetectionResult,
            LoopDetectionResult,
            OutputValidationResult,
            ToolOutputCheckResult,
        )

        return VerificationResult(
            status=status,
            confidence=confidence_score.score if confidence_score else 1.0,
            hallucination=hallucination or HallucinationDetectionResult(),
            validation=validation or OutputValidationResult(),
            tool_check=ToolOutputCheckResult(),
            loop_detection=loop_detection or LoopDetectionResult(),
            confidence_score=confidence_score or self._confidence_scorer.compute(),
            feedback=feedback,
            metadata={"context_type": context_type},
        )

    def _determine_status(
        self,
        hallucination: Any,
        validation: Any,
        loop_detection: Any,
        confidence_score: Any,
    ) -> VerificationStatus:
        """Determine overall verification status."""
        # Hard failures
        if loop_detection and loop_detection.loop_detected:
            return VerificationStatus.FAILED

        if hallucination and hallucination.detected:
            return VerificationStatus.FAILED

        if validation and not validation.valid:
            # Minor violations → uncertain; major → failed
            if len(validation.violations) > 2:
                return VerificationStatus.FAILED
            return VerificationStatus.UNCERTAIN

        # Confidence-based
        if confidence_score:
            if confidence_score.score < 0.4:
                return VerificationStatus.FAILED
            elif confidence_score.score < self.config.min_confidence_threshold:
                return VerificationStatus.UNCERTAIN

        return VerificationStatus.PASSED

    def _cache_key(self, *parts: str) -> str:
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _cache_put(self, key: str, result: VerificationResult) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            self._cache[key] = result
            if len(self._cache) > self._cache_max_size:
                self._cache.popitem(last=False)

    async def _acquire_priority_slot(self, priority: str) -> asyncio.Semaphore | None:
        """Acquire a concurrency slot based on priority.

        - critical/high: no throttling (bypass semaphore)
        - normal: limited to 8 concurrent verifications
        - low: limited to 4 concurrent verifications

        Returns the semaphore that was acquired (caller must release), or None
        if no semaphore was needed (critical/high).
        """
        p = self._priority_map.get(priority, 2)
        if p <= 1:
            # critical or high — no throttling
            return None
        elif p == 2:
            await self._semaphore_normal.acquire()
            return self._semaphore_normal
        else:
            await self._semaphore_low.acquire()
            return self._semaphore_low

    def _record_failure(self, result: VerificationResult, context_type: str) -> None:
        """Record failure for Self-Improvement Engine reporting."""
        self._failure_reports.append(
            {
                "result_id": str(result.result_id),
                "context_type": context_type,
                "status": result.status.value,
                "confidence": result.confidence,
                "issues": result.feedback.issues,
                "timestamp": result.timestamp.isoformat(),
            }
        )
        # Keep last 1000 reports — use list slicing to avoid O(n) pop(0)
        if len(self._failure_reports) > 1000:
            self._failure_reports = self._failure_reports[-1000:]
