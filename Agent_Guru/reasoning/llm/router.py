"""
Hybrid LLM Router

Intelligently routes requests between local and cloud LLM providers based on:
- Task complexity (simple → local, complex → cloud)
- Provider availability and health
- Automatic fallback on timeout or error
- Performance tracking and metrics

Performance Target: <50ms routing decision overhead
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from Agent_Guru.reasoning.llm.models import LLMRequest, LLMResponse
from Agent_Guru.reasoning.llm.providers.base import BaseLLMProvider


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
            raise ValueError(f"score must be 0.0-1.0, got {self.score}")


@dataclass
class RoutingMetrics:
    """Metrics for routing decisions."""

    total_requests: int = 0
    local_requests: int = 0
    cloud_requests: int = 0
    fallback_requests: int = 0
    local_latency_ms: list[float] = field(default_factory=list)
    cloud_latency_ms: list[float] = field(default_factory=list)
    local_errors: int = 0
    cloud_errors: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    def record_request(
        self, decision: RoutingDecision, latency_ms: float, error: bool = False
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

        self.last_updated = datetime.now()

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
            "last_updated": self.last_updated.isoformat(),
        }


class HybridLLMRouter:
    """
    Hybrid LLM router for intelligent provider selection.

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
        local_provider: Optional[BaseLLMProvider] = None,
        cloud_provider: Optional[BaseLLMProvider] = None,
        complexity_threshold: float = 0.5,
        enable_fallback: bool = True,
    ):
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
            raise ValueError("At least one provider (local or cloud) must be provided")

        self.local_provider = local_provider
        self.cloud_provider = cloud_provider
        self.complexity_threshold = complexity_threshold
        self.enable_fallback = enable_fallback
        self.metrics = RoutingMetrics()

    def calculate_complexity(
        self,
        request: LLMRequest,
        intent_type: Optional[str] = None,
        entity_count: int = 0,
        step_count: int = 1,
    ) -> ComplexityScore:
        """
        Calculate task complexity score.

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
        """
        Make routing decision based on complexity and availability.

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
            raise RuntimeError("No LLM providers available")

        # Simple task → prefer local
        if complexity.score < self.complexity_threshold:
            if local_available and self.local_provider:
                return RoutingDecision.LOCAL
            elif cloud_available and self.cloud_provider:
                return RoutingDecision.FALLBACK  # Fallback to cloud
            else:
                raise RuntimeError("No suitable provider available for simple task")

        # Complex task → prefer cloud
        else:
            if cloud_available and self.cloud_provider:
                return RoutingDecision.CLOUD
            elif local_available and self.local_provider:
                return RoutingDecision.FALLBACK  # Fallback to local
            else:
                raise RuntimeError("No suitable provider available for complex task")

    async def generate(
        self,
        request: LLMRequest,
        intent_type: Optional[str] = None,
        entity_count: int = 0,
        step_count: int = 1,
    ) -> LLMResponse:
        """
        Generate response with intelligent routing.

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
                else:
                    raise RuntimeError("Local provider not available")

            elif decision == RoutingDecision.CLOUD:
                if self.cloud_provider is not None:
                    response = await self.cloud_provider.generate(request)
                    routing_latency_ms = (time.perf_counter() - start_time) * 1000
                    self.metrics.record_request(decision, routing_latency_ms, error=False)
                    return response
                else:
                    raise RuntimeError("Cloud provider not available")

            elif decision == RoutingDecision.FALLBACK:
                # Fallback already determined by routing logic
                if complexity.score < self.complexity_threshold:
                    # Simple task, fallback to cloud
                    if self.cloud_provider is not None:
                        response = await self.cloud_provider.generate(request)
                    else:
                        raise RuntimeError("Cloud provider not available")
                else:
                    # Complex task, fallback to local
                    if self.local_provider is not None:
                        response = await self.local_provider.generate(request)
                    else:
                        raise RuntimeError("Local provider not available")

                routing_latency_ms = (time.perf_counter() - start_time) * 1000
                self.metrics.record_request(
                    RoutingDecision.FALLBACK, routing_latency_ms, error=False
                )
                return response

        except Exception as primary_error:
            # Record error
            routing_latency_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record_request(decision, routing_latency_ms, error=True)

            # Try fallback if enabled
            if self.enable_fallback:
                try:
                    if decision == RoutingDecision.LOCAL and self.cloud_provider:
                        # Fallback to cloud
                        response = await self.cloud_provider.generate(request)
                        self.metrics.record_request(
                            RoutingDecision.FALLBACK, routing_latency_ms, error=False
                        )
                        return response

                    elif decision == RoutingDecision.CLOUD and self.local_provider:
                        # Fallback to local
                        response = await self.local_provider.generate(request)
                        self.metrics.record_request(
                            RoutingDecision.FALLBACK, routing_latency_ms, error=False
                        )
                        return response

                except Exception as fallback_error:
                    # Both providers failed
                    raise RuntimeError(
                        f"Primary provider failed: {primary_error}. "
                        f"Fallback provider failed: {fallback_error}"
                    ) from fallback_error

            # No fallback, raise original error
            raise primary_error

    def get_metrics(self) -> dict[str, Any]:
        """Get routing metrics and statistics."""
        return self.metrics.get_stats()

    def reset_metrics(self) -> None:
        """Reset routing metrics."""
        self.metrics = RoutingMetrics()
