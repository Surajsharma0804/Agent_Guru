"""Hybrid LLM Router.

Intelligently routes requests between local and cloud LLM providers based on:
- Task complexity (simple → local, complex → cloud)
- Provider availability and health
- Automatic fallback on timeout or error
- Performance tracking and metrics

Performance Target: <50ms routing decision overhead
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from Agent_Guru.reasoning.llm.models import LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider


# Rolling window for latency samples. Bounded so a long-running session
# cannot grow these without limit.
MAX_LATENCY_SAMPLES = 1000


class RoutingDecision(str, Enum):
    """Routing decision types."""

    LOCAL = "local"  # Use local LLM
    CLOUD = "cloud"  # Use cloud LLM
    FALLBACK = "fallback"  # Fallback to alternative


@dataclass
class ComplexityScore:
    """Task complexity scoring."""

    score: float  # 0.0 (simple) to 1.0 (complex)
    factors: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""

    def __post_init__(self):
        """Validate score."""
        if not 0.0 <= self.score <= 1.0:
            msg = f"score must be 0.0-1.0, got {self.score}"
            raise ValueError(msg)


@dataclass
class RoutingMetrics:
    """Metrics for routing decisions."""

    total_requests: int = 0
    local_requests: int = 0
    cloud_requests: int = 0
    fallback_requests: int = 0
    # BUG FIX (memory): these were plain lists appended to on EVERY request
    # and never trimmed. In a companion designed to run continuously they
    # grow without bound -- one float per LLM call, forever. Bounded to the
    # most recent MAX_LATENCY_SAMPLES, which keeps the rolling average
    # representative (and more current) at fixed memory cost.
    local_latency_ms: deque[float] = field(
        default_factory=lambda: deque(maxlen=MAX_LATENCY_SAMPLES),
    )
    cloud_latency_ms: deque[float] = field(
        default_factory=lambda: deque(maxlen=MAX_LATENCY_SAMPLES),
    )
    # BUG FIX (observability): fallback had a counter but no latency and no
    # error tracking -- record_request() discarded both arguments for this
    # decision. Fallback is the path taken whenever the primary provider is
    # down, so how slow and how reliable it is was precisely the thing that
    # could not be seen.
    fallback_latency_ms: deque[float] = field(
        default_factory=lambda: deque(maxlen=MAX_LATENCY_SAMPLES),
    )
    local_errors: int = 0
    cloud_errors: int = 0
    fallback_errors: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def record_request(
        self,
        decision: RoutingDecision,
        latency_ms: float,
        error: bool = False,
    ) -> None:
        """Record a routing decision and its outcome."""
        self.total_requests += 1

        if decision == RoutingDecision.LOCAL:
            self.local_requests += 1
            self.local_latency_ms.append(latency_ms)
            if error:
                self.local_errors += 1
        elif decision == RoutingDecision.CLOUD:
            self.cloud_requests += 1
            self.cloud_latency_ms.append(latency_ms)
            if error:
                self.cloud_errors += 1
        elif decision == RoutingDecision.FALLBACK:
            self.fallback_requests += 1
            self.fallback_latency_ms.append(latency_ms)
            if error:
                self.fallback_errors += 1

        self.last_updated = datetime.now(tz=UTC)

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "total_requests": self.total_requests,
            "local_requests": self.local_requests,
            "cloud_requests": self.cloud_requests,
            "fallback_requests": self.fallback_requests,
            "local_percentage": (
                self.local_requests / self.total_requests * 100 if self.total_requests > 0 else 0.0
            ),
            "cloud_percentage": (
                self.cloud_requests / self.total_requests * 100 if self.total_requests > 0 else 0.0
            ),
            "local_avg_latency_ms": (
                sum(self.local_latency_ms) / len(self.local_latency_ms)
                if self.local_latency_ms
                else 0.0
            ),
            "cloud_avg_latency_ms": (
                sum(self.cloud_latency_ms) / len(self.cloud_latency_ms)
                if self.cloud_latency_ms
                else 0.0
            ),
            "local_error_rate": (
                self.local_errors / self.local_requests if self.local_requests > 0 else 0.0
            ),
            "cloud_error_rate": (
                self.cloud_errors / self.cloud_requests if self.cloud_requests > 0 else 0.0
            ),
            "fallback_percentage": (
                self.fallback_requests / self.total_requests * 100
                if self.total_requests > 0
                else 0.0
            ),
            "fallback_avg_latency_ms": (
                sum(self.fallback_latency_ms) / len(self.fallback_latency_ms)
                if self.fallback_latency_ms
                else 0.0
            ),
            "fallback_error_rate": (
                self.fallback_errors / self.fallback_requests
                if self.fallback_requests > 0
                else 0.0
            ),
            "last_updated": self.last_updated.isoformat(),
        }


class HybridLLMRouter:
    """Hybrid LLM router for intelligent provider selection.

    Routes requests between local and cloud providers based on:
    - Task complexity
    - Provider health and availability
    - Automatic fallback on errors

    Example:
        >>> router = HybridLLMRouter(local_provider, cloud_provider)
        >>> request = LLMRequest(prompt="Simple task")
        >>> response = await router.generate(request)

    """

    def __init__(
        self,
        local_provider: BaseLLMProvider | None = None,
        cloud_provider: BaseLLMProvider | None = None,
        complexity_threshold: float = 0.5,
        enable_fallback: bool = True,
    ) -> None:
        """Initialize hybrid router.

        Args:
            local_provider: Local LLM provider (e.g., llama.cpp)
            cloud_provider: Cloud LLM provider (e.g., OpenAI, Anthropic)
            complexity_threshold: Threshold for routing (0.0-1.0)
            enable_fallback: Enable automatic fallback on errors

        Raises:
            ValueError: If both providers are None

        """
        if local_provider is None and cloud_provider is None:
            msg = "At least one provider (local or cloud) must be provided"
            raise ValueError(msg)

        self.local_provider = local_provider
        self.cloud_provider = cloud_provider
        self.complexity_threshold = complexity_threshold
        self.enable_fallback = enable_fallback
        self.metrics = RoutingMetrics()

    def calculate_complexity(
        self,
        request: LLMRequest,
        intent_type: str | None = None,
        entity_count: int = 0,
        step_count: int = 1,
    ) -> ComplexityScore:
        """Calculate task complexity score.

        Complexity factors:
        - Prompt length (longer = more complex)
        - Entity count (more entities = more complex)
        - Step count (multi-step = more complex)
        - Intent type (some intents are inherently complex)

        Args:
            request: LLM request
            intent_type: Optional intent type
            entity_count: Number of entities in request
            step_count: Number of steps in task

        Returns:
            ComplexityScore with score 0.0-1.0

        """
        factors = {}

        # Factor 1: Prompt length (0.0-0.3)
        prompt_length = len(request.prompt)
        if prompt_length < 50:
            factors["prompt_length"] = 0.0
        elif prompt_length < 200:
            factors["prompt_length"] = 0.15
        else:
            factors["prompt_length"] = 0.3

        # Factor 2: Entity count (0.0-0.2)
        if entity_count == 0:
            factors["entity_count"] = 0.0
        elif entity_count <= 2:
            factors["entity_count"] = 0.1
        else:
            factors["entity_count"] = 0.2

        # Factor 3: Step count (0.0-0.3)
        if step_count == 1:
            factors["step_count"] = 0.0
        elif step_count <= 3:
            factors["step_count"] = 0.15
        else:
            factors["step_count"] = 0.3

        # Factor 4: Intent complexity (0.0-0.2)
        complex_intents = {
            "multi_step_task",
            "complex_query",
            "reasoning_required",
            "creative_generation",
        }
        if intent_type and intent_type in complex_intents:
            factors["intent_type"] = 0.2
        else:
            factors["intent_type"] = 0.0

        # Calculate total score
        total_score = sum(factors.values())

        # Generate reasoning
        reasoning = f"Complexity: {total_score:.2f} (prompt={factors['prompt_length']:.2f}, entities={factors['entity_count']:.2f}, steps={factors['step_count']:.2f}, intent={factors['intent_type']:.2f})"

        return ComplexityScore(score=total_score, factors=factors, reasoning=reasoning)

    def make_routing_decision(
        self,
        complexity: ComplexityScore,
        local_available: bool = True,
        cloud_available: bool = True,
    ) -> RoutingDecision:
        """Make routing decision based on complexity and availability.

        Routing logic:
        - Simple tasks (score < threshold) → local
        - Complex tasks (score >= threshold) → cloud
        - Fallback if preferred provider unavailable

        Args:
            complexity: Task complexity score
            local_available: Whether local provider is available
            cloud_available: Whether cloud provider is available

        Returns:
            RoutingDecision (LOCAL, CLOUD, or FALLBACK)

        """
        # Check availability
        if not local_available and not cloud_available:
            msg = "No LLM providers available"
            raise RuntimeError(msg)

        # Simple task → prefer local
        if complexity.score < self.complexity_threshold:
            if local_available and self.local_provider:
                return RoutingDecision.LOCAL
            if cloud_available and self.cloud_provider:
                return RoutingDecision.FALLBACK  # Fallback to cloud
            msg = "No suitable provider available for simple task"
            raise RuntimeError(msg)

        # Complex task → prefer cloud
        if cloud_available and self.cloud_provider:
            return RoutingDecision.CLOUD
        if local_available and self.local_provider:
            return RoutingDecision.FALLBACK  # Fallback to local
        msg = "No suitable provider available for complex task"
        raise RuntimeError(msg)

    async def generate(
        self,
        request: LLMRequest,
        intent_type: str | None = None,
        entity_count: int = 0,
        step_count: int = 1,
    ) -> LLMResponse:
        """Generate response with intelligent routing.

        Args:
            request: LLM request
            intent_type: Optional intent type for complexity scoring
            entity_count: Number of entities for complexity scoring
            step_count: Number of steps for complexity scoring

        Returns:
            LLM response

        Raises:
            RuntimeError: If all providers fail

        """
        start_time = time.perf_counter()

        # Calculate complexity
        complexity = self.calculate_complexity(request, intent_type, entity_count, step_count)

        # Check provider health
        local_available = self.local_provider is not None
        cloud_available = self.cloud_provider is not None

        # Make routing decision
        decision = self.make_routing_decision(complexity, local_available, cloud_available)

        # Try primary provider
        try:
            if decision == RoutingDecision.LOCAL:
                if self.local_provider is not None:
                    response = await self.local_provider.generate(request)
                    routing_latency_ms = (time.perf_counter() - start_time) * 1000
                    self.metrics.record_request(decision, routing_latency_ms, error=False)
                    return response
                msg = "Local provider not available"
                raise RuntimeError(msg)

            if decision == RoutingDecision.CLOUD:
                if self.cloud_provider is not None:
                    response = await self.cloud_provider.generate(request)
                    routing_latency_ms = (time.perf_counter() - start_time) * 1000
                    self.metrics.record_request(decision, routing_latency_ms, error=False)
                    return response
                msg = "Cloud provider not available"
                raise RuntimeError(msg)

            if decision == RoutingDecision.FALLBACK:
                # Fallback already determined by routing logic
                if complexity.score < self.complexity_threshold:
                    # Simple task, fallback to cloud
                    if self.cloud_provider is not None:
                        response = await self.cloud_provider.generate(request)
                    else:
                        msg = "Cloud provider not available"
                        raise RuntimeError(msg)
                # Complex task, fallback to local
                elif self.local_provider is not None:
                    response = await self.local_provider.generate(request)
                else:
                    msg = "Local provider not available"
                    raise RuntimeError(msg)

                routing_latency_ms = (time.perf_counter() - start_time) * 1000
                self.metrics.record_request(
                    RoutingDecision.FALLBACK,
                    routing_latency_ms,
                    error=False,
                )
                return response

            # Defensive: every RoutingDecision member is handled above, but
            # falling off the end would silently return None from a function
            # declared to return LLMResponse, surfacing as an AttributeError
            # far from the cause. Fail where the problem actually is.
            msg = f"Unhandled routing decision: {decision}"
            raise RuntimeError(msg)

        except Exception as primary_error:
            # Record error
            routing_latency_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record_request(decision, routing_latency_ms, error=True)

            # Try fallback if enabled
            if self.enable_fallback:
                try:
                    # BUG FIX: both fallback paths below used to record
                    # `routing_latency_ms`, which was measured at the moment
                    # the PRIMARY provider failed -- before the fallback call
                    # had even started. The fallback provider's own inference
                    # time was therefore excluded entirely, so every
                    # successful fallback was recorded as far faster than it
                    # really was, systematically biasing the routing metrics
                    # in favour of fallback. Latency is now measured after
                    # the fallback response actually arrives.
                    if decision == RoutingDecision.LOCAL and self.cloud_provider:
                        # Fallback to cloud
                        response = await self.cloud_provider.generate(request)
                        self.metrics.record_request(
                            RoutingDecision.FALLBACK,
                            (time.perf_counter() - start_time) * 1000,
                            error=False,
                        )
                        return response

                    if decision == RoutingDecision.CLOUD and self.local_provider:
                        # Fallback to local
                        response = await self.local_provider.generate(request)
                        self.metrics.record_request(
                            RoutingDecision.FALLBACK,
                            (time.perf_counter() - start_time) * 1000,
                            error=False,
                        )
                        return response

                except Exception as fallback_error:
                    # Both providers failed
                    msg = (
                        f"Primary provider failed: {primary_error}. "
                        f"Fallback provider failed: {fallback_error}"
                    )
                    raise RuntimeError(
                        msg,
                    ) from fallback_error

            # No fallback, raise original error
            raise

    def get_metrics(self) -> dict[str, Any]:
        """Get routing metrics and statistics."""
        return self.metrics.get_stats()

    def reset_metrics(self) -> None:
        """Reset routing metrics."""
        self.metrics = RoutingMetrics()
