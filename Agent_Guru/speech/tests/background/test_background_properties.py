"""
Property-based tests for Background Service Manager.

Property 27: State Transition Latency

Validates: Requirements 1.5.11
"""

import time
from hypothesis import given, strategies as st, settings

from Agent_Guru.speech.background_service import (
    BackgroundServiceManager,
    ServiceState
)


class TestBackgroundServiceProperties:
    """Property-based tests for Background Service Manager."""
    
    # ========================================================================
    # PROPERTY 27: STATE TRANSITION LATENCY
    # ========================================================================
    
    @given(
        num_transitions=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_27_wake_transition_latency(self, num_transitions: int):
        """
        Property 27: State Transition Latency
        
        For any number of wake transitions, each should complete within 500ms.
        
        Validates: Requirements 1.5.11
        """
        service = BackgroundServiceManager()
        service.start()
        
        try:
            for _ in range(num_transitions):
                # Transition to wake
                start_time = time.time()
                service.handle_wake_word_detected()
                elapsed = time.time() - start_time
                
                # PROPERTY ASSERTION: Transition must be <500ms
                assert elapsed < 0.5, f"Wake transition took {elapsed:.3f}s (target: <0.5s)"
                
                # Return to sleep for next iteration
                service._transition_to_sleep()
        finally:
            service.stop()
    
    # ========================================================================
    # PROPERTY: CONSISTENCY
    # ========================================================================
    
    @given(
        num_cycles=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_sleep_wake_cycle_consistency(self, num_cycles: int):
        """
        Property: Sleep/Wake Cycle Consistency
        
        For any number of sleep/wake cycles, state should be consistent.
        """
        service = BackgroundServiceManager()
        service.start()
        
        try:
            for _ in range(num_cycles):
                # Should start in sleep
                assert service.get_state() == ServiceState.SLEEP
                
                # Transition to wake
                service.handle_wake_word_detected()
                assert service.get_state() == ServiceState.WAKE
                
                # Return to sleep
                service._transition_to_sleep()
                assert service.get_state() == ServiceState.SLEEP
        finally:
            service.stop()
    
    # ========================================================================
    # PROPERTY: ROBUSTNESS
    # ========================================================================
    
    @given(
        num_errors=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_error_recovery(self, num_errors: int):
        """
        Property: Error Recovery
        
        For any number of errors, service should recover to sleep mode.
        """
        service = BackgroundServiceManager()
        service.start()
        
        try:
            for i in range(num_errors):
                # Transition to wake
                service.handle_wake_word_detected()
                
                # Handle error
                service.handle_error(Exception(f"Test error {i}"))
                
                # PROPERTY ASSERTION: Should recover to sleep
                assert service.get_state() == ServiceState.SLEEP
        finally:
            service.stop()
    
    # ========================================================================
    # PROPERTY: METRICS ACCURACY
    # ========================================================================
    
    @given(
        num_wake_words=st.integers(min_value=0, max_value=50),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_wake_word_count_accuracy(self, num_wake_words: int):
        """
        Property: Metrics Accuracy
        
        For any number of wake word detections, count should be accurate.
        """
        service = BackgroundServiceManager()
        service.start()
        
        try:
            for _ in range(num_wake_words):
                service.handle_wake_word_detected()
                # Return to sleep for next detection
                service._transition_to_sleep()
            
            metrics = service.get_metrics()
            
            # PROPERTY ASSERTION: Count should match
            assert metrics.wake_word_detections == num_wake_words
        finally:
            service.stop()
    
    @given(
        num_commands=st.integers(min_value=0, max_value=50),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_command_count_accuracy(self, num_commands: int):
        """
        Property: Metrics Accuracy
        
        For any number of commands, count should be accurate.
        """
        service = BackgroundServiceManager()
        service.start()
        service.handle_wake_word_detected()
        
        try:
            for i in range(num_commands):
                service.handle_command_received(f"command {i}")
            
            metrics = service.get_metrics()
            
            # PROPERTY ASSERTION: Count should match
            assert metrics.commands_processed == num_commands
        finally:
            service.stop()
    
    # ========================================================================
    # PROPERTY: STATE TRANSITION COUNTING
    # ========================================================================
    
    @given(
        num_transitions=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_state_transition_counting(self, num_transitions: int):
        """
        Property: State Transition Counting
        
        For any number of transitions, count should be accurate.
        """
        service = BackgroundServiceManager()
        service.start()  # 1 transition (STOPPED -> SLEEP)
        
        try:
            for _ in range(num_transitions):
                service.handle_wake_word_detected()  # SLEEP -> WAKE
                service._transition_to_sleep()  # WAKE -> SLEEP
            
            metrics = service.get_metrics()
            
            # PROPERTY ASSERTION: Count should match
            # 1 (start) + num_transitions * 2 (wake + sleep)
            expected = 1 + (num_transitions * 2)
            assert metrics.state_transitions == expected
        finally:
            service.stop()
    
    # ========================================================================
    # PROPERTY: UPTIME ACCURACY
    # ========================================================================
    
    @given(
        sleep_seconds=st.floats(min_value=0.1, max_value=0.5),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_uptime_accuracy(self, sleep_seconds: float):
        """
        Property: Uptime Accuracy
        
        For any sleep duration, uptime should be accurate.
        """
        service = BackgroundServiceManager()
        service.start()
        
        try:
            time.sleep(sleep_seconds)
            
            metrics = service.get_metrics()
            
            # PROPERTY ASSERTION: Uptime should be approximately correct
            assert metrics.uptime_seconds >= sleep_seconds
            assert metrics.uptime_seconds < sleep_seconds + 0.5  # Allow 500ms tolerance
        finally:
            service.stop()
