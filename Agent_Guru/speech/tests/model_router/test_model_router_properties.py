"""
Property-based tests for Model Router Client.

Property 24: Model Router Fallback

Validates: Requirements 20.2, 20.3, 20.5
"""

import time
from hypothesis import given, strategies as st, settings

from Agent_Guru.speech.model_router_client import (
    ModelRouterClient,
    ModelType,
    ModelLocation,
    NetworkState
)


class TestModelRouterClientProperties:
    """Property-based tests for Model Router Client."""
    
    # ========================================================================
    # PROPERTY 24: MODEL ROUTER FALLBACK
    # ========================================================================
    
    @given(
        network_state=st.sampled_from([NetworkState.ONLINE_GOOD, NetworkState.ONLINE_POOR, NetworkState.OFFLINE]),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_24_network_state_model_selection(self, network_state: NetworkState):
        """
        Property 24: Model Router Fallback
        
        For any network state, model selection should use appropriate location.
        
        Validates: Requirements 20.2, 20.3
        """
        client = ModelRouterClient()
        client.set_network_state(network_state)
        
        model = client.select_stt_model()
        
        # PROPERTY ASSERTION: Network state determines model location
        if network_state == NetworkState.OFFLINE:
            assert model.location == ModelLocation.LOCAL
        elif network_state == NetworkState.ONLINE_POOR:
            assert model.location == ModelLocation.LOCAL
        elif network_state == NetworkState.ONLINE_GOOD:
            assert model.location == ModelLocation.CLOUD
    
    @given(
        model_type=st.sampled_from([ModelType.STT, ModelType.TTS]),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_24_fallback_latency(self, model_type: ModelType):
        """
        Property 24: Model Router Fallback
        
        For any model type, fallback to local must complete within 1 second.
        
        Validates: Requirements 20.5
        """
        client = ModelRouterClient()
        
        start_time = time.time()
        
        if model_type == ModelType.STT:
            model = client.fallback_to_local(model_type, language="en")
        else:
            model = client.fallback_to_local(model_type, language="en", gender="male")
        
        elapsed = time.time() - start_time
        
        # PROPERTY ASSERTION: Fallback must complete within 1 second
        assert elapsed < 1.0, f"Fallback took {elapsed:.3f}s, must be <1s"
        assert model.location == ModelLocation.LOCAL
    
    @given(
        battery_low=st.booleans(),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_24_battery_aware_selection(self, battery_low: bool):
        """
        Property 24: Model Router Fallback
        
        For any battery state, low battery should prefer local models.
        
        Validates: Requirements 20.2
        """
        client = ModelRouterClient()
        client.set_network_state(NetworkState.ONLINE_GOOD)
        client.set_battery_state(low=battery_low)
        
        model = client.select_stt_model()
        
        # PROPERTY ASSERTION: Low battery prefers local
        if battery_low:
            assert model.location == ModelLocation.LOCAL
        else:
            assert model.location == ModelLocation.CLOUD
    
    # ========================================================================
    # PROPERTY: CONSISTENCY
    # ========================================================================
    
    @given(
        network_state=st.sampled_from([NetworkState.ONLINE_GOOD, NetworkState.ONLINE_POOR, NetworkState.OFFLINE]),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_consistency(self, network_state: NetworkState):
        """
        Property: Consistency
        
        For any network state, multiple selections should give consistent results.
        """
        client = ModelRouterClient()
        client.set_network_state(network_state)
        
        # Select multiple times
        models = [client.select_stt_model() for _ in range(5)]
        
        # PROPERTY ASSERTION: All selections should be consistent
        for i in range(1, len(models)):
            assert models[i].location == models[0].location
            assert models[i].model_id == models[0].model_id
    
    # ========================================================================
    # PROPERTY: ROBUSTNESS
    # ========================================================================
    
    @given(
        language=st.text(min_size=2, max_size=5, alphabet=st.characters(whitelist_categories=('L',))),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_robustness_to_any_language(self, language: str):
        """
        Property: Robustness
        
        For any language code, model selection should handle gracefully.
        """
        client = ModelRouterClient()
        
        # Should not crash
        model = client.select_stt_model(language=language)
        
        # PROPERTY ASSERTION
        assert model is not None
        assert model.location in ModelLocation
    
    @given(
        prefer_local=st.booleans(),
        prefer_cloud=st.booleans(),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_user_preferences(self, prefer_local: bool, prefer_cloud: bool):
        """
        Property: User Preferences
        
        For any user preferences, model selection should respect them.
        """
        client = ModelRouterClient(prefer_local=prefer_local, prefer_cloud=prefer_cloud)
        client.set_network_state(NetworkState.ONLINE_GOOD)
        
        model = client.select_stt_model()
        
        # PROPERTY ASSERTION: Preferences are respected
        if prefer_local:
            assert model.location == ModelLocation.LOCAL
        elif prefer_cloud:
            assert model.location == ModelLocation.CLOUD
    
    # ========================================================================
    # PROPERTY: PERFORMANCE TRACKING
    # ========================================================================
    
    @given(
        accuracy=st.floats(min_value=0.0, max_value=1.0),
        latency_ms=st.floats(min_value=0.0, max_value=10000.0),
        cost=st.floats(min_value=0.0, max_value=1.0),
        success=st.booleans(),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_performance_tracking_bounds(
        self,
        accuracy: float,
        latency_ms: float,
        cost: float,
        success: bool
    ):
        """
        Property: Performance Tracking Bounds
        
        For any performance metrics, tracking should maintain valid bounds.
        """
        client = ModelRouterClient()
        model_id = "test-model"
        
        client.track_performance(model_id, accuracy, latency_ms, cost, success)
        
        metrics = client.get_performance_metrics(model_id)
        
        # PROPERTY ASSERTION: Metrics should be in valid ranges
        assert metrics is not None
        assert 0.0 <= metrics.accuracy <= 1.0
        assert metrics.latency_ms >= 0.0
        assert metrics.cost_per_request >= 0.0
        assert 0.0 <= metrics.success_rate <= 1.0
        assert metrics.total_requests >= 1
    
    @given(
        num_requests=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_performance_tracking_accumulation(self, num_requests: int):
        """
        Property: Performance Tracking Accumulation
        
        For any number of requests, tracking should accumulate correctly.
        """
        client = ModelRouterClient()
        model_id = "test-model"
        
        for i in range(num_requests):
            client.track_performance(
                model_id,
                accuracy=0.9,
                latency_ms=100.0,
                cost=0.01,
                success=True
            )
        
        metrics = client.get_performance_metrics(model_id)
        
        # PROPERTY ASSERTION: Total requests should match
        assert metrics is not None
        assert metrics.total_requests == num_requests
    
    # ========================================================================
    # PROPERTY: CACHING
    # ========================================================================
    
    @given(
        key=st.text(min_size=1, max_size=100),
        value=st.integers(),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_caching_retrieval(self, key: str, value: int):
        """
        Property: Caching Retrieval
        
        For any key-value pair, caching should store and retrieve correctly.
        """
        client = ModelRouterClient(enable_caching=True)
        
        client.cache_result(key, value)
        cached = client.get_cached_result(key)
        
        # PROPERTY ASSERTION: Cached value should match
        assert cached == value
    
    @given(
        num_entries=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_cache_clear(self, num_entries: int):
        """
        Property: Cache Clear
        
        For any number of cached entries, clear should remove all.
        """
        client = ModelRouterClient(enable_caching=True)
        
        # Cache multiple entries
        for i in range(num_entries):
            client.cache_result(f"key{i}", f"value{i}")
        
        # Clear cache
        client.clear_cache()
        
        # PROPERTY ASSERTION: All entries should be gone
        for i in range(num_entries):
            assert client.get_cached_result(f"key{i}") is None
    
    # ========================================================================
    # PROPERTY: FALLBACK RELIABILITY
    # ========================================================================
    
    @given(
        num_fallbacks=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_fallback_reliability(self, num_fallbacks: int):
        """
        Property: Fallback Reliability
        
        For any number of fallbacks, all should complete within 1 second.
        """
        client = ModelRouterClient()
        
        for _ in range(num_fallbacks):
            start_time = time.time()
            model = client.fallback_to_local(ModelType.STT, language="en")
            elapsed = time.time() - start_time
            
            # PROPERTY ASSERTION: Each fallback must be fast
            assert elapsed < 1.0
            assert model.location == ModelLocation.LOCAL
    
    # ========================================================================
    # PROPERTY: MODEL INFO VALIDITY
    # ========================================================================
    
    @given(
        network_state=st.sampled_from([NetworkState.ONLINE_GOOD, NetworkState.ONLINE_POOR, NetworkState.OFFLINE]),
        battery_low=st.booleans(),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_model_info_validity(self, network_state: NetworkState, battery_low: bool):
        """
        Property: Model Info Validity
        
        For any conditions, model info should be valid.
        """
        client = ModelRouterClient()
        client.set_network_state(network_state)
        client.set_battery_state(low=battery_low)
        
        stt_model = client.select_stt_model()
        tts_model = client.select_tts_model(gender="male")
        
        # PROPERTY ASSERTION: Model info should be valid
        for model in [stt_model, tts_model]:
            assert model.model_id is not None
            assert len(model.model_id) > 0
            assert model.location in ModelLocation
            assert model.estimated_latency_ms >= 0.0
            assert 0.0 <= model.estimated_accuracy <= 1.0
            assert model.estimated_cost >= 0.0
    
    # ========================================================================
    # PROPERTY: LOCAL MODEL COST
    # ========================================================================
    
    @given(
        model_type=st.sampled_from([ModelType.STT, ModelType.TTS]),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_local_model_zero_cost(self, model_type: ModelType):
        """
        Property: Local Model Cost
        
        For any model type, local models should have zero cost.
        """
        client = ModelRouterClient()
        client.set_network_state(NetworkState.OFFLINE)
        
        if model_type == ModelType.STT:
            model = client.select_stt_model()
        else:
            model = client.select_tts_model(gender="male")
        
        # PROPERTY ASSERTION: Local models are free
        assert model.location == ModelLocation.LOCAL
        assert model.estimated_cost == 0.0
    
    # ========================================================================
    # PROPERTY: DETERMINISM
    # ========================================================================
    
    @given(
        network_state=st.sampled_from([NetworkState.ONLINE_GOOD, NetworkState.ONLINE_POOR, NetworkState.OFFLINE]),
    )
    @settings(max_examples=300, deadline=None)
    def test_property_determinism(self, network_state: NetworkState):
        """
        Property: Determinism
        
        For any network state, selection should be deterministic.
        """
        client = ModelRouterClient()
        client.set_network_state(network_state)
        
        # Select 10 times
        models = [client.select_stt_model() for _ in range(10)]
        
        # PROPERTY ASSERTION: All selections should be identical
        for i in range(1, len(models)):
            assert models[i].model_id == models[0].model_id
            assert models[i].location == models[0].location
            assert models[i].provider == models[0].provider
