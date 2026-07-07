"""
ZERO COMPROMISE unit tests for Model Router Client.

Tests cover:
- STT model selection (local/cloud)
- TTS model selection (local/cloud)
- Fallback to local models (<1 second)
- Network state handling
- Battery-aware selection
- Performance tracking
- Model caching
- User preferences (local-only, cloud-only)
"""

import pytest
import time

from Agent_Guru.speech.model_router_client import (
    ModelRouterClient,
    ModelType,
    ModelLocation,
    CloudProvider,
    NetworkState
)


class TestModelRouterClient:
    """Comprehensive tests for Model Router Client."""
    
    @pytest.fixture
    def client(self) -> ModelRouterClient:
        """Create model router client instance."""
        return ModelRouterClient()
    
    # ========================================================================
    # STT MODEL SELECTION
    # ========================================================================
    
    def test_select_stt_model_online_good(self, client: ModelRouterClient):
        """Test STT model selection with good online connection."""
        client.set_network_state(NetworkState.ONLINE_GOOD)
        
        model = client.select_stt_model(language="en")
        
        # Should select cloud model for better accuracy
        assert model.location == ModelLocation.CLOUD  # nosec B101
        assert model.provider is not None  # nosec B101
        assert model.estimated_accuracy > 0.9  # nosec B101
    
    def test_select_stt_model_offline(self, client: ModelRouterClient):
        """Test STT model selection when offline."""
        client.set_network_state(NetworkState.OFFLINE)
        
        model = client.select_stt_model(language="en")
        
        # Should select local model
        assert model.location == ModelLocation.LOCAL  # nosec B101
        assert model.provider is None  # nosec B101
        assert model.estimated_cost == 0.0  # nosec B101
    
    def test_select_stt_model_poor_connection(self, client: ModelRouterClient):
        """Test STT model selection with poor connection."""
        client.set_network_state(NetworkState.ONLINE_POOR)
        
        model = client.select_stt_model(language="en")
        
        # Should prefer local model with poor connection
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    def test_select_stt_model_low_battery(self, client: ModelRouterClient):
        """Test STT model selection with low battery."""
        client.set_network_state(NetworkState.ONLINE_GOOD)
        client.set_battery_state(low=True)
        
        model = client.select_stt_model(language="en")
        
        # Should prefer local model to save battery
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    def test_select_stt_model_prefer_local(self):
        """Test STT model selection with local preference."""
        client = ModelRouterClient(prefer_local=True)
        client.set_network_state(NetworkState.ONLINE_GOOD)
        
        model = client.select_stt_model(language="en")
        
        # Should always use local model
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    def test_select_stt_model_prefer_cloud(self):
        """Test STT model selection with cloud preference."""
        client = ModelRouterClient(prefer_cloud=True)
        client.set_network_state(NetworkState.ONLINE_GOOD)
        
        model = client.select_stt_model(language="en")
        
        # Should use cloud model
        assert model.location == ModelLocation.CLOUD  # nosec B101
    
    def test_select_stt_model_prefer_cloud_offline(self):
        """Test STT model selection with cloud preference but offline."""
        client = ModelRouterClient(prefer_cloud=True)
        client.set_network_state(NetworkState.OFFLINE)
        
        model = client.select_stt_model(language="en")
        
        # Should fallback to local when offline
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    # ========================================================================
    # TTS MODEL SELECTION
    # ========================================================================
    
    def test_select_tts_model_online_good(self, client: ModelRouterClient):
        """Test TTS model selection with good online connection."""
        client.set_network_state(NetworkState.ONLINE_GOOD)
        
        model = client.select_tts_model(language="en", gender="male")
        
        # Should select cloud model for better quality
        assert model.location == ModelLocation.CLOUD  # nosec B101
        assert model.provider is not None  # nosec B101
        assert model.estimated_accuracy > 0.9  # nosec B101
    
    def test_select_tts_model_offline(self, client: ModelRouterClient):
        """Test TTS model selection when offline."""
        client.set_network_state(NetworkState.OFFLINE)
        
        model = client.select_tts_model(language="en", gender="female")
        
        # Should select local model
        assert model.location == ModelLocation.LOCAL  # nosec B101
        assert model.provider is None  # nosec B101
        assert model.estimated_cost == 0.0  # nosec B101
    
    def test_select_tts_model_poor_connection(self, client: ModelRouterClient):
        """Test TTS model selection with poor connection."""
        client.set_network_state(NetworkState.ONLINE_POOR)
        
        model = client.select_tts_model(language="en", gender="male")
        
        # Should prefer local model
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    def test_select_tts_model_low_battery(self, client: ModelRouterClient):
        """Test TTS model selection with low battery."""
        client.set_network_state(NetworkState.ONLINE_GOOD)
        client.set_battery_state(low=True)
        
        model = client.select_tts_model(language="en", gender="female")
        
        # Should prefer local model to save battery
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    # ========================================================================
    # FALLBACK TO LOCAL
    # ========================================================================
    
    def test_fallback_to_local_stt(self, client: ModelRouterClient):
        """Test fallback to local STT model."""
        start_time = time.time()
        
        model = client.fallback_to_local(ModelType.STT, language="en")
        
        elapsed = time.time() - start_time
        
        # Should complete within 1 second
        assert elapsed < 1.0  # nosec B101
        assert model.location == ModelLocation.LOCAL  # nosec B101
        assert model.provider is None  # nosec B101
    
    def test_fallback_to_local_tts(self, client: ModelRouterClient):
        """Test fallback to local TTS model."""
        start_time = time.time()
        
        model = client.fallback_to_local(ModelType.TTS, language="en", gender="male")
        
        elapsed = time.time() - start_time
        
        # Should complete within 1 second
        assert elapsed < 1.0  # nosec B101
        assert model.location == ModelLocation.LOCAL  # nosec B101
        assert model.provider is None  # nosec B101
    
    def test_fallback_latency_requirement(self, client: ModelRouterClient):
        """Test that fallback meets <1 second requirement."""
        # Test multiple times to ensure consistency
        for _ in range(10):
            start_time = time.time()
            model = client.fallback_to_local(ModelType.STT, language="en")
            elapsed = time.time() - start_time
            
            assert elapsed < 1.0, f"Fallback took {elapsed:.3f}s, must be <1s"  # nosec B101
    
    # ========================================================================
    # PERFORMANCE TRACKING
    # ========================================================================
    
    def test_track_performance(self, client: ModelRouterClient):
        """Test performance tracking."""
        model_id = "test-model"
        
        client.track_performance(
            model_id=model_id,
            accuracy=0.95,
            latency_ms=200.0,
            cost=0.01,
            success=True
        )
        
        metrics = client.get_performance_metrics(model_id)
        
        assert metrics is not None  # nosec B101
        assert metrics.model_id == model_id  # nosec B101
        assert metrics.accuracy == 0.95  # nosec B101
        assert metrics.latency_ms == 200.0  # nosec B101
        assert metrics.cost_per_request == 0.01  # nosec B101
        assert metrics.success_rate == 1.0  # nosec B101
        assert metrics.total_requests == 1  # nosec B101
    
    def test_track_performance_running_average(self, client: ModelRouterClient):
        """Test performance tracking with running averages."""
        model_id = "test-model"
        
        # Track multiple requests
        client.track_performance(model_id, accuracy=0.90, latency_ms=100.0, cost=0.01, success=True)
        client.track_performance(model_id, accuracy=0.95, latency_ms=200.0, cost=0.02, success=True)
        client.track_performance(model_id, accuracy=0.92, latency_ms=150.0, cost=0.015, success=False)
        
        metrics = client.get_performance_metrics(model_id)
        
        assert metrics is not None  # nosec B101
        assert metrics.total_requests == 3  # nosec B101
        # Check running averages
        assert 0.90 <= metrics.accuracy <= 0.95  # nosec B101
        assert 100.0 <= metrics.latency_ms <= 200.0  # nosec B101
        assert 0.01 <= metrics.cost_per_request <= 0.02  # nosec B101
        assert 0.6 <= metrics.success_rate <= 0.7  # 2/3 success  # nosec B101
    
    def test_get_performance_metrics_not_tracked(self, client: ModelRouterClient):
        """Test getting metrics for untracked model."""
        metrics = client.get_performance_metrics("unknown-model")
        
        assert metrics is None  # nosec B101
    
    # ========================================================================
    # MODEL CACHING
    # ========================================================================
    
    def test_cache_result(self, client: ModelRouterClient):
        """Test caching model results."""
        key = "hello world"
        result = {"audio": "data"}
        
        client.cache_result(key, result)
        cached = client.get_cached_result(key)
        
        assert cached == result  # nosec B101
    
    def test_get_cached_result_not_found(self, client: ModelRouterClient):
        """Test getting non-existent cached result."""
        cached = client.get_cached_result("nonexistent")
        
        assert cached is None  # nosec B101
    
    def test_clear_cache(self, client: ModelRouterClient):
        """Test clearing cache."""
        client.cache_result("key1", "value1")
        client.cache_result("key2", "value2")
        
        client.clear_cache()
        
        assert client.get_cached_result("key1") is None  # nosec B101
        assert client.get_cached_result("key2") is None  # nosec B101
    
    def test_caching_disabled(self):
        """Test that caching can be disabled."""
        client = ModelRouterClient(enable_caching=False)
        
        client.cache_result("key", "value")
        cached = client.get_cached_result("key")
        
        assert cached is None  # nosec B101
    
    # ========================================================================
    # NETWORK STATE
    # ========================================================================
    
    def test_set_network_state(self, client: ModelRouterClient):
        """Test setting network state."""
        client.set_network_state(NetworkState.OFFLINE)
        
        model = client.select_stt_model()
        assert model.location == ModelLocation.LOCAL  # nosec B101
        
        client.set_network_state(NetworkState.ONLINE_GOOD)
        model = client.select_stt_model()
        assert model.location == ModelLocation.CLOUD  # nosec B101
    
    def test_network_state_via_context(self, client: ModelRouterClient):
        """Test setting network state via context."""
        context = {"network_state": NetworkState.OFFLINE}
        
        model = client.select_stt_model(context=context)
        
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    # ========================================================================
    # BATTERY STATE
    # ========================================================================
    
    def test_set_battery_state(self, client: ModelRouterClient):
        """Test setting battery state."""
        client.set_network_state(NetworkState.ONLINE_GOOD)
        client.set_battery_state(low=False)
        
        model = client.select_stt_model()
        assert model.location == ModelLocation.CLOUD  # nosec B101
        
        client.set_battery_state(low=True)
        model = client.select_stt_model()
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    def test_battery_state_via_context(self, client: ModelRouterClient):
        """Test setting battery state via context."""
        client.set_network_state(NetworkState.ONLINE_GOOD)
        context = {"battery_low": True}
        
        model = client.select_stt_model(context=context)
        
        assert model.location == ModelLocation.LOCAL  # nosec B101
    
    # ========================================================================
    # MODEL INFO VALIDATION
    # ========================================================================
    
    def test_model_info_has_required_fields(self, client: ModelRouterClient):
        """Test that ModelInfo has all required fields."""
        model = client.select_stt_model()
        
        assert hasattr(model, 'model_id')  # nosec B101
        assert hasattr(model, 'location')  # nosec B101
        assert hasattr(model, 'provider')  # nosec B101
        assert hasattr(model, 'estimated_latency_ms')  # nosec B101
        assert hasattr(model, 'estimated_accuracy')  # nosec B101
        assert hasattr(model, 'estimated_cost')  # nosec B101
    
    def test_local_model_has_zero_cost(self, client: ModelRouterClient):
        """Test that local models have zero cost."""
        client.set_network_state(NetworkState.OFFLINE)
        
        stt_model = client.select_stt_model()
        tts_model = client.select_tts_model(gender="male")
        
        assert stt_model.estimated_cost == 0.0  # nosec B101
        assert tts_model.estimated_cost == 0.0  # nosec B101
    
    def test_cloud_model_has_provider(self, client: ModelRouterClient):
        """Test that cloud models have provider."""
        client.set_network_state(NetworkState.ONLINE_GOOD)
        
        model = client.select_stt_model()
        
        if model.location == ModelLocation.CLOUD:
            assert model.provider is not None  # nosec B101
            assert model.provider in CloudProvider  # nosec B101
    
    # ========================================================================
    # EDGE CASES
    # ========================================================================
    
    def test_multiple_model_selections(self, client: ModelRouterClient):
        """Test multiple model selections."""
        for _ in range(100):
            stt_model = client.select_stt_model()
            tts_model = client.select_tts_model(gender="male")
            
            assert stt_model is not None  # nosec B101
            assert tts_model is not None  # nosec B101
    
    def test_rapid_network_state_changes(self, client: ModelRouterClient):
        """Test rapid network state changes."""
        states = [
            NetworkState.ONLINE_GOOD,
            NetworkState.OFFLINE,
            NetworkState.ONLINE_POOR,
            NetworkState.ONLINE_GOOD,
        ]
        
        for state in states * 10:
            client.set_network_state(state)
            model = client.select_stt_model()
            assert model is not None  # nosec B101
    
    def test_concurrent_like_selections(self, client: ModelRouterClient):
        """Test concurrent-like model selections."""
        results = []
        
        for i in range(100):
            if i % 2 == 0:
                model = client.select_stt_model()
            else:
                model = client.select_tts_model(gender="female")
            results.append(model)
        
        # All selections should succeed
        assert len(results) == 100  # nosec B101
        assert all(r is not None for r in results)  # nosec B101
