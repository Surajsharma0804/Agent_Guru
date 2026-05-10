"""Reasoning Pipeline with Knowledge Synthesis Integration.

This module implements the main reasoning pipeline that integrates Knowledge Query
Detection and Knowledge Synthesis. It routes knowledge queries directly to the
Knowledge Synthesizer, bypassing normal reasoning for faster response times.

Performance Characteristics:
    - Time Complexity: O(n) where n is input length
    - Space Complexity: O(1) for routing logic
    - Knowledge Query Detection: <50ms
    - Knowledge Synthesis: <1.5s
    - Total Latency: <1.6s for knowledge queries

Pipeline Flow:
    1. Input Normalization
    2. Memory Retrieval
    3. Knowledge Query Detection (NEW)
    4. If knowledge query:
       - Route to Knowledge Synthesizer
       - Generate response from KnowledgeAnswer
       - Track metrics
    5. Else:
       - Continue with normal reasoning pipeline

Design Principles:
    - Fast knowledge query detection (<50ms)
    - Direct routing to bypass normal reasoning
    - Comprehensive metrics tracking
    - Type-safe with Pydantic models
    - Error handling with fallback

Competitive Advantage:
    - Faster response for knowledge queries (<1.6s vs >2.5s normal pipeline)
    - Specialized knowledge synthesis
    - Better accuracy for personal knowledge questions
    - Comprehensive metrics for optimization

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from Agent_Guru.reasoning.knowledge.query_detector import KnowledgeQueryDetector
from Agent_Guru.reasoning.knowledge.synthesizer import KnowledgeSynthesizer
from Agent_Guru.reasoning.memory_retriever import MemoryRetriever
from Agent_Guru.reasoning.models.knowledge import KnowledgeAnswer


class PipelineStage(str, Enum):
    """Pipeline stages for tracking and metrics.

    Stages:
        INPUT_NORMALIZATION: Input validation and normalization
        MEMORY_RETRIEVAL: Semantic memory retrieval
        KNOWLEDGE_DETECTION: Knowledge query detection
        KNOWLEDGE_SYNTHESIS: Knowledge answer synthesis
        NORMAL_REASONING: Normal reasoning pipeline (not implemented yet)
        RESPONSE_GENERATION: Response generation
    """

    INPUT_NORMALIZATION = "input_normalization"
    MEMORY_RETRIEVAL = "memory_retrieval"
    KNOWLEDGE_DETECTION = "knowledge_detection"
    KNOWLEDGE_SYNTHESIS = "knowledge_synthesis"
    NORMAL_REASONING = "normal_reasoning"
    RESPONSE_GENERATION = "response_generation"


@dataclass
class PipelineMetrics:
    """Metrics for pipeline execution.

    Attributes:
        total_latency_ms: Total pipeline latency in milliseconds
        stage_latencies: Latency per stage in milliseconds
        knowledge_query_detected: Whether knowledge query was detected
        knowledge_query_type: Type of knowledge query (if detected)
        knowledge_confidence: Confidence score for knowledge answer
        error: Error message if pipeline failed
        timestamp: Timestamp of pipeline execution

    """

    total_latency_ms: float = 0.0
    stage_latencies: dict[str, float] = field(default_factory=dict)
    knowledge_query_detected: bool = False
    knowledge_query_type: str | None = None
    knowledge_confidence: float | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def add_stage_latency(self, stage: PipelineStage, latency_ms: float) -> None:
        """Add latency for a pipeline stage.

        Args:
            stage: Pipeline stage
            latency_ms: Latency in milliseconds

        """
        self.stage_latencies[stage.value] = latency_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for logging/storage.

        Returns:
            Dictionary representation of metrics

        """
        return {
            "total_latency_ms": self.total_latency_ms,
            "stage_latencies": self.stage_latencies,
            "knowledge_query_detected": self.knowledge_query_detected,
            "knowledge_query_type": self.knowledge_query_type,
            "knowledge_confidence": self.knowledge_confidence,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PipelineResult:
    """Result of pipeline execution.

    Attributes:
        response: Generated response text
        confidence: Confidence score (0.0-1.0)
        knowledge_answer: KnowledgeAnswer if knowledge query was detected
        metrics: Pipeline execution metrics
        success: Whether pipeline succeeded

    """

    response: str
    confidence: float
    knowledge_answer: KnowledgeAnswer | None = None
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
    success: bool = True


class ReasoningPipeline:
    """Main reasoning pipeline with knowledge synthesis integration.

    This class implements the complete reasoning pipeline including:
    - Input normalization
    - Memory retrieval
    - Knowledge query detection
    - Knowledge synthesis (for knowledge queries)
    - Normal reasoning (for other queries - not implemented yet)
    - Response generation

    Time Complexity:
        - process: O(n) where n is input length
        - Knowledge queries: <1.6s total latency
        - Normal queries: <2.5s total latency (when implemented)

    Space Complexity:
        - O(k) where k is retrieved memories (max 50)

    Attributes:
        memory_retriever: MemoryRetriever for semantic search
        knowledge_detector: KnowledgeQueryDetector for query detection
        knowledge_synthesizer: KnowledgeSynthesizer for answer synthesis
        enable_knowledge_synthesis: Whether to enable knowledge synthesis
        metrics_enabled: Whether to track metrics

    Example:
        >>> pipeline = ReasoningPipeline(memory_retriever)
        >>> result = pipeline.process("when did I last call John?", user_id="user_123")
        >>> print(result.response)
        >>> print(f"Latency: {result.metrics.total_latency_ms:.1f}ms")

    """

    def __init__(
        self,
        memory_retriever: MemoryRetriever,
        knowledge_synthesizer: KnowledgeSynthesizer | None = None,
        knowledge_detector: KnowledgeQueryDetector | None = None,
        enable_knowledge_synthesis: bool = True,
        metrics_enabled: bool = True,
    ) -> None:
        """Initialize ReasoningPipeline.

        Args:
            memory_retriever: MemoryRetriever instance
            knowledge_synthesizer: Optional KnowledgeSynthesizer instance
            knowledge_detector: Optional KnowledgeQueryDetector instance
            enable_knowledge_synthesis: Whether to enable knowledge synthesis
            metrics_enabled: Whether to track metrics

        Raises:
            ValueError: If memory_retriever is None

        """
        if memory_retriever is None:
            msg = "memory_retriever cannot be None"
            raise ValueError(msg)

        self.memory_retriever = memory_retriever
        self.enable_knowledge_synthesis = enable_knowledge_synthesis
        self.metrics_enabled = metrics_enabled

        # Initialize knowledge components if enabled
        if self.enable_knowledge_synthesis:
            self.knowledge_detector = knowledge_detector or KnowledgeQueryDetector()
            self.knowledge_synthesizer = knowledge_synthesizer or KnowledgeSynthesizer(
                memory_retriever=memory_retriever,
                use_llm_synthesis=False,  # Disable LLM by default for testing
            )
        else:
            self.knowledge_detector = None
            self.knowledge_synthesizer = None

    def process(self, user_input: str, user_id: str) -> PipelineResult:
        """Process user input through the reasoning pipeline.

        Time Complexity: O(n) where n is input length
        Latency Budget: <1.6s for knowledge queries, <2.5s for normal queries

        This is the main entry point for the reasoning pipeline. It orchestrates
        all pipeline stages and routes to appropriate handlers.

        Args:
            user_input: User input text
            user_id: User ID for data filtering

        Returns:
            PipelineResult with response and metrics

        Example:
            >>> pipeline = ReasoningPipeline(memory_retriever)
            >>> result = pipeline.process("when did I last call John?", "user_123")
            >>> print(result.response)

        """
        start_time = time.perf_counter()
        metrics = PipelineMetrics()

        try:
            # Stage 1: Input Normalization
            stage_start = time.perf_counter()
            normalized_input = self._normalize_input(user_input)
            metrics.add_stage_latency(
                PipelineStage.INPUT_NORMALIZATION,
                (time.perf_counter() - stage_start) * 1000,
            )

            # Stage 2: Memory Retrieval (always retrieve for context)
            stage_start = time.perf_counter()
            # Memory retrieval happens inside knowledge synthesis
            # For now, we skip this stage in the main pipeline
            metrics.add_stage_latency(
                PipelineStage.MEMORY_RETRIEVAL,
                (time.perf_counter() - stage_start) * 1000,
            )

            # Stage 3: Knowledge Query Detection
            if self.enable_knowledge_synthesis and self.knowledge_detector:
                stage_start = time.perf_counter()
                knowledge_query = self.knowledge_detector.detect_knowledge_query(normalized_input)
                metrics.add_stage_latency(
                    PipelineStage.KNOWLEDGE_DETECTION,
                    (time.perf_counter() - stage_start) * 1000,
                )

                # If knowledge query detected, route to knowledge synthesizer
                if knowledge_query is not None:
                    metrics.knowledge_query_detected = True
                    metrics.knowledge_query_type = knowledge_query.query_type.value

                    # Stage 4: Knowledge Synthesis
                    stage_start = time.perf_counter()
                    knowledge_answer = self.knowledge_synthesizer.synthesize_answer(
                        knowledge_query,
                        user_id,
                    )
                    metrics.add_stage_latency(
                        PipelineStage.KNOWLEDGE_SYNTHESIS,
                        (time.perf_counter() - stage_start) * 1000,
                    )

                    metrics.knowledge_confidence = knowledge_answer.confidence

                    # Stage 5: Response Generation (from KnowledgeAnswer)
                    stage_start = time.perf_counter()
                    response = self._generate_response_from_knowledge_answer(knowledge_answer)
                    metrics.add_stage_latency(
                        PipelineStage.RESPONSE_GENERATION,
                        (time.perf_counter() - stage_start) * 1000,
                    )

                    # Calculate total latency
                    metrics.total_latency_ms = (time.perf_counter() - start_time) * 1000

                    return PipelineResult(
                        response=response,
                        confidence=knowledge_answer.confidence,
                        knowledge_answer=knowledge_answer,
                        metrics=metrics,
                        success=True,
                    )

            # If not a knowledge query, route to normal reasoning pipeline
            # TODO: Implement normal reasoning pipeline in future tasks
            stage_start = time.perf_counter()
            response = self._fallback_response(normalized_input)
            metrics.add_stage_latency(
                PipelineStage.NORMAL_REASONING,
                (time.perf_counter() - stage_start) * 1000,
            )

            # Calculate total latency
            metrics.total_latency_ms = (time.perf_counter() - start_time) * 1000

            return PipelineResult(
                response=response,
                confidence=0.5,  # Low confidence for fallback
                metrics=metrics,
                success=True,
            )

        except Exception as e:
            # Handle errors gracefully
            metrics.error = str(e)
            metrics.total_latency_ms = (time.perf_counter() - start_time) * 1000

            return PipelineResult(
                response=f"I encountered an error processing your request: {e!s}",
                confidence=0.0,
                metrics=metrics,
                success=False,
            )

    def _normalize_input(self, user_input: str) -> str:
        """Normalize user input.

        Time Complexity: O(n) where n is input length
        Latency Budget: <30ms

        Args:
            user_input: Raw user input

        Returns:
            Normalized input text

        Raises:
            ValueError: If input is empty or invalid

        """
        if not user_input or not user_input.strip():
            msg = "Input cannot be empty"
            raise ValueError(msg)

        # Basic normalization
        normalized = user_input.strip()

        # Remove extra whitespace
        return " ".join(normalized.split())

    def _generate_response_from_knowledge_answer(self, knowledge_answer: KnowledgeAnswer) -> str:
        """Generate response text from KnowledgeAnswer.

        Time Complexity: O(1)
        Latency Budget: <10ms

        Args:
            knowledge_answer: KnowledgeAnswer from synthesis

        Returns:
            Response text

        """
        # For now, just return the summary
        # Future: Add rich formatting, suggestions, etc.
        return knowledge_answer.summary

    def _fallback_response(self, user_input: str) -> str:
        """Generate fallback response for non-knowledge queries.

        This is a placeholder until normal reasoning pipeline is implemented.

        Args:
            user_input: Normalized user input

        Returns:
            Fallback response text

        """
        return (
            "I understand you're asking about something, but I'm still learning "
            "how to handle this type of request. For now, I can answer questions "
            "about your past activities, patterns, and personal information. "
            "Try asking 'when did I last...', 'who do I... most', or 'what do I usually...'."
        )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of pipeline metrics.

        This method would aggregate metrics across multiple pipeline executions
        for monitoring and optimization.

        Returns:
            Dictionary of aggregated metrics

        Note:
            This is a placeholder for future metrics aggregation.

        """
        return {
            "knowledge_queries_processed": 0,
            "normal_queries_processed": 0,
            "average_latency_ms": 0.0,
            "average_confidence": 0.0,
            "error_rate": 0.0,
        }
