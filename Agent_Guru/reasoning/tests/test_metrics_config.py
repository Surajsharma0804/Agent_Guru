"""Comprehensive unit tests for metrics configuration - 100% coverage."""

import pytest
from prometheus_client import CollectorRegistry

from Agent_Guru.reasoning.config.metrics import (
    MetricsCollector,
    get_metrics_collector,
    reset_metrics_collector,
)


class TestMetricsCollector:
    """Test MetricsCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create a metrics collector with custom registry."""
        registry = CollectorRegistry()
        return MetricsCollector(registry=registry)
    
    def test_init_with_custom_registry(self):
        """Test initialization with custom registry."""
        registry = CollectorRegistry()
        collector = MetricsCollector(registry=registry)
        
        assert collector.registry == registry  # nosec B101
        assert len(collector.latency_histograms) == 7  # nosec B101
    
    def test_init_with_default_registry(self):
        """Test initialization with default registry."""
        collector = MetricsCollector()
        
        assert collector.registry is not None  # nosec B101
    
    def test_record_stage_latency(self, collector):
        """Test recording stage latency."""
        collector.record_stage_latency("intent_detection", 0.5)
        
        # Verify metric was recorded
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_intent_detection_duration_seconds" in metrics  # nosec B101
    
    def test_record_stage_latency_invalid_stage(self, collector):
        """Test recording latency for invalid stage."""
        # Should not raise error
        collector.record_stage_latency("invalid_stage", 0.5)
    
    def test_increment_requests(self, collector):
        """Test incrementing request counter."""
        collector.increment_requests("success")
        collector.increment_requests("error")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_requests_total" in metrics  # nosec B101
    
    def test_increment_errors(self, collector):
        """Test incrementing error counter."""
        collector.increment_errors("timeout")
        collector.increment_errors("validation_error")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_errors_total" in metrics  # nosec B101
    
    def test_increment_timeouts(self, collector):
        """Test incrementing timeout counter."""
        collector.increment_timeouts("reasoning")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_timeouts_total" in metrics  # nosec B101
    
    def test_increment_fallbacks(self, collector):
        """Test incrementing fallback counter."""
        collector.increment_fallbacks("llm_fallback")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_fallbacks_total" in metrics  # nosec B101
    
    def test_record_intent(self, collector):
        """Test recording detected intent."""
        collector.record_intent("set_timer")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_intents_detected_total" in metrics  # nosec B101
    
    def test_record_action(self, collector):
        """Test recording action execution."""
        collector.record_action("timer_tool", "success")
        collector.record_action("weather_tool", "failure")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_actions_executed_total" in metrics  # nosec B101
    
    def test_record_safety_block(self, collector):
        """Test recording safety block."""
        collector.record_safety_block("permission_denied")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_safety_blocks_total" in metrics  # nosec B101
    
    def test_set_active_conversations(self, collector):
        """Test setting active conversations gauge."""
        collector.set_active_conversations(42)
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_active_conversations" in metrics  # nosec B101
    
    def test_set_queue_depth(self, collector):
        """Test setting queue depth gauge."""
        collector.set_queue_depth("sync", 10)
        collector.set_queue_depth("async", 5)
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_queue_depth" in metrics  # nosec B101
    
    def test_set_memory_usage(self, collector):
        """Test setting memory usage gauge."""
        collector.set_memory_usage(1024 * 1024 * 100)  # 100MB
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_memory_usage_bytes" in metrics  # nosec B101
    
    def test_set_cpu_usage(self, collector):
        """Test setting CPU usage gauge."""
        collector.set_cpu_usage(45.5)
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_cpu_usage_percent" in metrics  # nosec B101
    
    def test_record_llm_tokens(self, collector):
        """Test recording LLM token usage."""
        collector.record_llm_tokens("local", 100)
        collector.record_llm_tokens("cloud", 500)
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_llm_tokens_used_total" in metrics  # nosec B101
    
    def test_record_cache_hit(self, collector):
        """Test recording cache hit."""
        collector.record_cache_hit("intent")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_cache_hits_total" in metrics  # nosec B101
    
    def test_record_cache_miss(self, collector):
        """Test recording cache miss."""
        collector.record_cache_miss("prompt")
        
        metrics = collector.generate_metrics()
        assert b"reasoning_engine_cache_misses_total" in metrics  # nosec B101
    
    def test_generate_metrics(self, collector):
        """Test generating metrics."""
        collector.increment_requests("success")
        metrics = collector.generate_metrics()
        
        assert isinstance(metrics, bytes)  # nosec B101
        assert len(metrics) > 0  # nosec B101
    
    def test_get_content_type(self, collector):
        """Test getting content type."""
        content_type = collector.get_content_type()
        
        assert "text/plain" in content_type  # nosec B101
    
    def test_all_pipeline_stages(self, collector):
        """Test all pipeline stages have histograms."""
        stages = [
            "input_normalization",
            "intent_detection",
            "reasoning",
            "tool_selection",
            "safety_validation",
            "execution",
            "response_generation",
        ]
        
        for stage in stages:
            assert stage in collector.latency_histograms  # nosec B101
            collector.record_stage_latency(stage, 0.1)


class TestGlobalMetricsCollector:
    """Test global metrics collector functions."""
    
    def test_get_metrics_collector_singleton(self):
        """Test getting global metrics collector returns singleton."""
        reset_metrics_collector()
        
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        
        assert collector1 is collector2  # nosec B101
    
    def test_reset_metrics_collector(self):
        """Test resetting global metrics collector."""
        collector1 = get_metrics_collector()
        reset_metrics_collector()
        collector2 = get_metrics_collector()
        
        assert collector1 is not collector2  # nosec B101
