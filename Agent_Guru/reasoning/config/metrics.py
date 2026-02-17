"""Prometheus metrics collection for the reasoning engine."""

from typing import Dict, Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class MetricsCollector:
    """Centralized metrics collector for the reasoning engine."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.
        
        Args:
            registry: Optional custom registry (uses default if None)
        """
        self.registry = registry or CollectorRegistry()
        
        # Latency histograms for each pipeline stage
        self.latency_histograms: Dict[str, Histogram] = {}
        pipeline_stages = [
            "input_normalization",
            "intent_detection",
            "reasoning",
            "tool_selection",
            "safety_validation",
            "execution",
            "response_generation",
        ]
        
        for stage in pipeline_stages:
            self.latency_histograms[stage] = Histogram(
                f"reasoning_engine_{stage}_duration_seconds",
                f"Time spent in {stage} stage",
                buckets=(0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
                registry=self.registry,
            )
        
        # Counter metrics
        self.requests_total = Counter(
            "reasoning_engine_requests_total",
            "Total number of requests processed",
            ["status"],  # success, error
            registry=self.registry,
        )
        
        self.errors_total = Counter(
            "reasoning_engine_errors_total",
            "Total number of errors by type",
            ["error_type"],
            registry=self.registry,
        )
        
        self.timeouts_total = Counter(
            "reasoning_engine_timeouts_total",
            "Total number of timeouts by stage",
            ["stage"],
            registry=self.registry,
        )
        
        self.fallbacks_total = Counter(
            "reasoning_engine_fallbacks_total",
            "Total number of fallback activations",
            ["fallback_type"],  # llm_fallback, tool_fallback, etc.
            registry=self.registry,
        )
        
        self.intents_detected = Counter(
            "reasoning_engine_intents_detected_total",
            "Total intents detected by type",
            ["intent_type"],
            registry=self.registry,
        )
        
        self.actions_executed = Counter(
            "reasoning_engine_actions_executed_total",
            "Total actions executed",
            ["tool_id", "status"],  # success, failure
            registry=self.registry,
        )
        
        self.safety_blocks = Counter(
            "reasoning_engine_safety_blocks_total",
            "Total actions blocked by safety gate",
            ["reason"],  # permission_denied, sensitive_action, etc.
            registry=self.registry,
        )
        
        # Gauge metrics
        self.active_conversations = Gauge(
            "reasoning_engine_active_conversations",
            "Number of active conversations",
            registry=self.registry,
        )
        
        self.queue_depth = Gauge(
            "reasoning_engine_queue_depth",
            "Number of requests in queue",
            ["queue_type"],  # sync, async
            registry=self.registry,
        )
        
        self.memory_usage_bytes = Gauge(
            "reasoning_engine_memory_usage_bytes",
            "Memory usage in bytes",
            registry=self.registry,
        )
        
        self.cpu_usage_percent = Gauge(
            "reasoning_engine_cpu_usage_percent",
            "CPU usage percentage",
            registry=self.registry,
        )
        
        self.llm_tokens_used = Counter(
            "reasoning_engine_llm_tokens_used_total",
            "Total LLM tokens used",
            ["backend"],  # local, cloud
            registry=self.registry,
        )
        
        self.cache_hits = Counter(
            "reasoning_engine_cache_hits_total",
            "Total cache hits",
            ["cache_type"],  # intent, prompt, etc.
            registry=self.registry,
        )
        
        self.cache_misses = Counter(
            "reasoning_engine_cache_misses_total",
            "Total cache misses",
            ["cache_type"],
            registry=self.registry,
        )
    
    def record_stage_latency(self, stage: str, duration: float) -> None:
        """
        Record latency for a pipeline stage.
        
        Args:
            stage: Pipeline stage name
            duration: Duration in seconds
        """
        if stage in self.latency_histograms:
            self.latency_histograms[stage].observe(duration)
    
    def increment_requests(self, status: str = "success") -> None:
        """
        Increment request counter.
        
        Args:
            status: Request status (success, error)
        """
        self.requests_total.labels(status=status).inc()
    
    def increment_errors(self, error_type: str) -> None:
        """
        Increment error counter.
        
        Args:
            error_type: Type of error
        """
        self.errors_total.labels(error_type=error_type).inc()
    
    def increment_timeouts(self, stage: str) -> None:
        """
        Increment timeout counter.
        
        Args:
            stage: Stage that timed out
        """
        self.timeouts_total.labels(stage=stage).inc()
    
    def increment_fallbacks(self, fallback_type: str) -> None:
        """
        Increment fallback counter.
        
        Args:
            fallback_type: Type of fallback activated
        """
        self.fallbacks_total.labels(fallback_type=fallback_type).inc()
    
    def record_intent(self, intent_type: str) -> None:
        """
        Record detected intent.
        
        Args:
            intent_type: Type of intent detected
        """
        self.intents_detected.labels(intent_type=intent_type).inc()
    
    def record_action(self, tool_id: str, status: str) -> None:
        """
        Record action execution.
        
        Args:
            tool_id: ID of tool executed
            status: Execution status (success, failure)
        """
        self.actions_executed.labels(tool_id=tool_id, status=status).inc()
    
    def record_safety_block(self, reason: str) -> None:
        """
        Record safety gate block.
        
        Args:
            reason: Reason for blocking
        """
        self.safety_blocks.labels(reason=reason).inc()
    
    def set_active_conversations(self, count: int) -> None:
        """
        Set active conversations gauge.
        
        Args:
            count: Number of active conversations
        """
        self.active_conversations.set(count)
    
    def set_queue_depth(self, queue_type: str, depth: int) -> None:
        """
        Set queue depth gauge.
        
        Args:
            queue_type: Type of queue (sync, async)
            depth: Queue depth
        """
        self.queue_depth.labels(queue_type=queue_type).set(depth)
    
    def set_memory_usage(self, bytes_used: int) -> None:
        """
        Set memory usage gauge.
        
        Args:
            bytes_used: Memory usage in bytes
        """
        self.memory_usage_bytes.set(bytes_used)
    
    def set_cpu_usage(self, percent: float) -> None:
        """
        Set CPU usage gauge.
        
        Args:
            percent: CPU usage percentage
        """
        self.cpu_usage_percent.set(percent)
    
    def record_llm_tokens(self, backend: str, tokens: int) -> None:
        """
        Record LLM token usage.
        
        Args:
            backend: LLM backend (local, cloud)
            tokens: Number of tokens used
        """
        self.llm_tokens_used.labels(backend=backend).inc(tokens)
    
    def record_cache_hit(self, cache_type: str) -> None:
        """
        Record cache hit.
        
        Args:
            cache_type: Type of cache
        """
        self.cache_hits.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str) -> None:
        """
        Record cache miss.
        
        Args:
            cache_type: Type of cache
        """
        self.cache_misses.labels(cache_type=cache_type).inc()
    
    def generate_metrics(self) -> bytes:
        """
        Generate metrics in Prometheus format.
        
        Returns:
            Metrics data in Prometheus text format
        """
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        """
        Get content type for metrics endpoint.
        
        Returns:
            Content type string
        """
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector() -> None:
    """Reset the global metrics collector (useful for testing)."""
    global _metrics_collector
    _metrics_collector = None
