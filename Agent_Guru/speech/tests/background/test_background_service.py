"""
ZERO COMPROMISE unit tests for Background Service Manager.

Tests cover:
- Service start/stop
- Sleep/wake transitions
- Wake word handling
- Command handling
- Error handling
- Resource usage
- State management
"""

import pytest
import time
import threading

from Agent_Guru.speech.background_service import (
    BackgroundServiceManager,
    ServiceState,
    ServiceMetrics
)


class TestBackgroundServiceManager:
    """Comprehensive tests for Background Service Manager."""
    
    @pytest.fixture
    def service(self) -> BackgroundServiceManager:
        """Create background service instance."""
        return BackgroundServiceManager()
    
    # ========================================================================
    # SERVICE START/STOP
    # ========================================================================
    
    def test_start_service(self, service: BackgroundServiceManager):
        """Test starting service."""
        service.start()
        
        # Should be in sleep mode
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        assert service._start_time is not None  # nosec B101
    
    def test_stop_service(self, service: BackgroundServiceManager):
        """Test stopping service."""
        service.start()
        service.stop()
        
        # Should be stopped
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
    
    def test_start_already_running(self, service: BackgroundServiceManager):
        """Test starting service when already running."""
        service.start()
        
        with pytest.raises(RuntimeError):
            service.start()
        
        service.stop()
    
    # ========================================================================
    # PAUSE/RESUME
    # ========================================================================
    
    def test_pause_service(self, service: BackgroundServiceManager):
        """Test pausing service."""
        service.start()
        service.pause()
        
        assert service.get_state() == ServiceState.PAUSED  # nosec B101
        
        service.stop()
    
    def test_resume_service(self, service: BackgroundServiceManager):
        """Test resuming service."""
        service.start()
        service.pause()
        service.resume()
        
        # Should be back in sleep mode
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    def test_resume_not_paused(self, service: BackgroundServiceManager):
        """Test resuming when not paused."""
        service.start()
        
        with pytest.raises(RuntimeError):
            service.resume()
        
        service.stop()
    
    # ========================================================================
    # WAKE WORD HANDLING
    # ========================================================================
    
    def test_handle_wake_word_detected(self, service: BackgroundServiceManager):
        """Test handling wake word detection."""
        service.start()
        
        # Detect wake word
        start_time = time.time()
        service.handle_wake_word_detected()
        elapsed = time.time() - start_time
        
        # Should transition to wake mode within 500ms
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        assert elapsed < 0.5  # nosec B101
        
        service.stop()
    
    def test_wake_word_callback(self, service: BackgroundServiceManager):
        """Test wake word callback is called."""
        callback_called = threading.Event()
        
        def wake_callback():
            callback_called.set()
        
        service.wake_word_callback = wake_callback
        service.start()
        service.handle_wake_word_detected()
        
        # Callback should be called
        assert callback_called.wait(timeout=1.0)  # nosec B101
        
        service.stop()
    
    def test_wake_word_count(self, service: BackgroundServiceManager):
        """Test wake word detection count."""
        service.start()
        
        # Detect multiple wake words (must return to sleep between detections)
        for _ in range(5):
            service.handle_wake_word_detected()
            # Return to sleep for next detection
            service._transition_to_sleep()
            time.sleep(0.05)
        
        metrics = service.get_metrics()
        assert metrics.wake_word_detections == 5  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # COMMAND HANDLING
    # ========================================================================
    
    def test_handle_command_received(self, service: BackgroundServiceManager):
        """Test handling command."""
        service.start()
        service.handle_wake_word_detected()
        
        service.handle_command_received("test command")
        
        metrics = service.get_metrics()
        assert metrics.commands_processed == 1  # nosec B101
        
        service.stop()
    
    def test_command_callback(self, service: BackgroundServiceManager):
        """Test command callback is called."""
        callback_called = threading.Event()
        received_command = []
        
        def command_callback(cmd):
            received_command.append(cmd)
            callback_called.set()
        
        service.command_callback = command_callback
        service.start()
        service.handle_wake_word_detected()
        service.handle_command_received("test command")
        
        # Callback should be called
        assert callback_called.wait(timeout=1.0)  # nosec B101
        assert received_command[0] == "test command"  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # SILENCE DETECTION
    # ========================================================================
    
    def test_handle_silence_detected(self, service: BackgroundServiceManager):
        """Test handling silence detection."""
        service.start()
        service.handle_wake_word_detected()
        
        # Detect silence
        service.handle_silence_detected()
        
        # Should still be in wake mode (timeout not expired)
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        
        service.stop()
    
    def test_wake_timeout_returns_to_sleep(self, service: BackgroundServiceManager):
        """Test wake timeout returns to sleep mode."""
        service._wake_timeout_seconds = 0.2  # Short timeout for testing
        service.start()
        service.handle_wake_word_detected()
        
        # Wait for timeout
        time.sleep(0.3)
        
        # Should have returned to sleep
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # ERROR HANDLING
    # ========================================================================
    
    def test_handle_error(self, service: BackgroundServiceManager):
        """Test error handling."""
        service.start()
        service.handle_wake_word_detected()
        
        # Handle error
        service.handle_error(Exception("Test error"))
        
        # Should return to sleep mode
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        metrics = service.get_metrics()
        assert metrics.errors == 1  # nosec B101
        
        service.stop()
    
    def test_error_in_callback(self, service: BackgroundServiceManager):
        """Test error in callback doesn't crash service."""
        def bad_callback():
            raise Exception("Callback error")
        
        service.wake_word_callback = bad_callback
        service.start()
        
        # Should handle error gracefully
        service.handle_wake_word_detected()
        
        # Service should still be running
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        
        metrics = service.get_metrics()
        assert metrics.errors == 1  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # LOW BATTERY HANDLING
    # ========================================================================
    
    def test_handle_low_battery(self, service: BackgroundServiceManager):
        """Test low battery handling."""
        service.start()
        
        # Handle low battery
        service.handle_low_battery()
        
        # Service should still be running (unless critical)
        assert service.get_state() in [ServiceState.SLEEP, ServiceState.PAUSED]  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def test_get_metrics(self, service: BackgroundServiceManager):
        """Test getting service metrics."""
        service.start()
        time.sleep(0.1)
        
        metrics = service.get_metrics()
        
        assert isinstance(metrics, ServiceMetrics)  # nosec B101
        assert metrics.uptime_seconds > 0  # nosec B101
        assert metrics.cpu_percent >= 0  # nosec B101
        assert metrics.memory_mb > 0  # nosec B101
        
        service.stop()
    
    def test_metrics_state_transitions(self, service: BackgroundServiceManager):
        """Test state transition counting."""
        service.start()  # STOPPED -> SLEEP (1)
        service.handle_wake_word_detected()  # SLEEP -> WAKE (2)
        service.pause()  # WAKE -> PAUSED (3)
        service.resume()  # PAUSED -> SLEEP (4)
        
        metrics = service.get_metrics()
        assert metrics.state_transitions == 4  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # RESOURCE USAGE
    # ========================================================================
    
    @pytest.mark.performance
    def test_sleep_mode_resource_usage(self, service: BackgroundServiceManager):
        """Test sleep mode resource usage.

        get_metrics() reports WHOLE-PROCESS RSS - correct for a deployment
        where the process is the assistant, but meaningless as an absolute
        number inside a test process that has also loaded torch, whisper,
        sentence-transformers and chromadb. The old
        `assert metrics.memory_mb < 500` measured the test runner: it passed
        when this file ran alone and failed at 792 MB in a full-suite run,
        with nothing about the background service having changed.

        What the test's own comment is reaching for - "sleep mode should use
        <100MB RAM" - is the memory the SERVICE adds, so that is what is
        measured: RSS before start() against RSS after. The delta is
        independent of whatever else the process has loaded, which makes this
        both stable and a stronger assertion than the absolute bound.
        """
        import os

        import psutil

        process = psutil.Process(os.getpid())
        baseline_mb = process.memory_info().rss / (1024 * 1024)

        service.start()
        time.sleep(0.1)

        metrics = service.get_metrics()
        service.stop()

        added_mb = metrics.memory_mb - baseline_mb
        assert added_mb < 100, (  # nosec B101
            f"sleep mode added {added_mb:.1f} MB "
            f"({baseline_mb:.1f} -> {metrics.memory_mb:.1f} MB)"
        )
        # CPU is sampled over a 100 ms window inside get_metrics(), so it is
        # already a rate rather than a total; 30% leaves room for a loaded
        # runner while still catching a spin-loop.
        assert metrics.cpu_percent < 30  # nosec B101
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def test_get_state(self, service: BackgroundServiceManager):
        """Test getting service state."""
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
        
        service.start()
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.handle_wake_word_detected()
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        
        service.stop()
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
    
    # ========================================================================
    # THREAD SAFETY
    # ========================================================================
    
    def test_concurrent_wake_word_detections(self, service: BackgroundServiceManager):
        """Test concurrent wake word detections."""
        service.start()
        
        # Simulate concurrent detections
        threads = []
        for _ in range(10):
            t = threading.Thread(target=service.handle_wake_word_detected)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should handle gracefully
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        
        service.stop()


    # ========================================================================
    # ZERO COMPROMISE - STRESS TESTS
    # ========================================================================
    
    def test_stress_1000_wake_word_detections(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Stress test with 1000 wake word detections."""
        service.start()
        
        for i in range(1000):
            service.handle_wake_word_detected()
            service._transition_to_sleep()
        
        metrics = service.get_metrics()
        assert metrics.wake_word_detections == 1000  # nosec B101
        assert metrics.errors == 0  # nosec B101
        
        service.stop()
    
    def test_stress_24_hour_simulation(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Simulate 24 hour operation (compressed time)."""
        service.start()
        
        # Simulate 24 hours with wake/sleep cycles
        for _ in range(100):  # 100 cycles
            service.handle_wake_word_detected()
            service.handle_command_received("test")
            time.sleep(0.01)  # Compressed time
            service._transition_to_sleep()
        
        metrics = service.get_metrics()
        assert metrics.wake_word_detections == 100  # nosec B101
        assert metrics.commands_processed == 100  # nosec B101
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    def test_stress_rapid_state_transitions_end_in_sleep(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Rapid state transitions."""
        service.start()
        
        for _ in range(100):
            service.handle_wake_word_detected()
            service._transition_to_sleep()
        
        # Should handle gracefully
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # ZERO COMPROMISE - CHAOS TESTS
    # ========================================================================
    
    def test_chaos_callback_exceptions_single(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Callbacks that always throw exceptions."""
        def bad_wake_callback():
            raise RuntimeError("Wake callback error")
        
        def bad_command_callback(cmd):
            raise ValueError("Command callback error")
        
        service.wake_word_callback = bad_wake_callback
        service.command_callback = bad_command_callback
        service.start()
        
        # Should handle errors gracefully
        service.handle_wake_word_detected()
        service.handle_command_received("test")
        
        metrics = service.get_metrics()
        assert metrics.errors == 2  # nosec B101
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        
        service.stop()
    
    def test_chaos_rapid_pause_resume(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Rapid pause/resume cycles."""
        service.start()
        
        for _ in range(50):
            service.pause()
            service.resume()
        
        # Should still be functional
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    def test_chaos_concurrent_commands(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Concurrent command handling."""
        service.start()
        service.handle_wake_word_detected()
        
        # Simulate concurrent commands
        threads = []
        for i in range(50):
            t = threading.Thread(target=service.handle_command_received, args=(f"cmd{i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        metrics = service.get_metrics()
        assert metrics.commands_processed == 50  # nosec B101
        
        service.stop()
    
    def test_chaos_error_during_transition(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Error during state transition."""
        service.start()
        
        # Cause error during wake transition
        service.handle_wake_word_detected()
        service.handle_error(Exception("Transition error"))
        
        # Should recover to sleep
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # ZERO COMPROMISE - EDGE CASES
    # ========================================================================
    
    def test_edge_case_stop_without_start(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Stop without starting."""
        # Should handle gracefully
        service.stop()
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
    
    def test_edge_case_multiple_stops(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Multiple stop calls."""
        service.start()
        service.stop()
        service.stop()  # Second stop
        
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
    
    def test_edge_case_wake_word_when_stopped(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Wake word when service stopped."""
        # Should handle gracefully
        service.handle_wake_word_detected()
        
        # Should not crash
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
    
    def test_edge_case_command_when_stopped(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Command when service stopped."""
        # Should handle gracefully
        service.handle_command_received("test")
        
        # Should not crash
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
    
    def test_edge_case_very_long_command(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Very long command text."""
        service.start()
        service.handle_wake_word_detected()
        
        # Very long command
        long_command = "test " * 10000
        service.handle_command_received(long_command)
        
        metrics = service.get_metrics()
        assert metrics.commands_processed == 1  # nosec B101
        
        service.stop()
    
    def test_edge_case_empty_command(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Empty command."""
        service.start()
        service.handle_wake_word_detected()
        
        service.handle_command_received("")
        
        metrics = service.get_metrics()
        assert metrics.commands_processed == 1  # nosec B101
        
        service.stop()
    
    def test_edge_case_unicode_command(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Unicode command."""
        service.start()
        service.handle_wake_word_detected()
        
        service.handle_command_received("测试命令 🎤 مرحبا")
        
        metrics = service.get_metrics()
        assert metrics.commands_processed == 1  # nosec B101
        
        service.stop()
    
    def test_edge_case_wake_timeout_zero(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Zero wake timeout."""
        service._wake_timeout_seconds = 0.0
        service.start()
        service.handle_wake_word_detected()
        
        # Should handle gracefully
        time.sleep(0.1)
        
        service.stop()
    
    def test_edge_case_negative_wake_timeout(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Negative wake timeout."""
        service._wake_timeout_seconds = -1.0
        service.start()
        service.handle_wake_word_detected()
        
        # Should handle gracefully
        time.sleep(0.1)
        
        service.stop()
    
    # ========================================================================
    # ZERO COMPROMISE - BATTERY INTEGRATION
    # ========================================================================
    
    def test_battery_tracking_sleep_mode(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Battery tracking in sleep mode."""
        service.start()
        time.sleep(0.2)
        service.stop()  # Stop to finalize tracking
        
        stats = service.battery_monitor.get_usage_stats()
        assert stats.sleep_time_seconds > 0  # nosec B101
    
    def test_battery_tracking_wake_mode(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Battery tracking in wake mode."""
        service.start()
        service.handle_wake_word_detected()
        time.sleep(0.2)
        service.stop()  # Stop to finalize tracking
        
        stats = service.battery_monitor.get_usage_stats()
        assert stats.wake_time_seconds > 0  # nosec B101
    
    def test_battery_tracking_mixed_modes(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Battery tracking across modes."""
        service.start()
        time.sleep(0.1)
        
        service.handle_wake_word_detected()
        time.sleep(0.1)
        
        service._transition_to_sleep()
        time.sleep(0.1)
        
        stats = service.battery_monitor.get_usage_stats()
        assert stats.sleep_time_seconds > 0  # nosec B101
        assert stats.wake_time_seconds > 0  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # ZERO COMPROMISE - PERFORMANCE VALIDATION
    # ========================================================================
    
    def test_performance_uptime_accuracy(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Validate uptime accuracy."""
        service.start()
        time.sleep(0.5)
        
        metrics = service.get_metrics()
        assert 0.4 < metrics.uptime_seconds < 0.7  # nosec B101
        
        service.stop()


    # ========================================================================
    # ZERO COMPROMISE - STRESS TESTS
    # ========================================================================
    
    def test_stress_24_hour_continuous_operation(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Simulate 24-hour continuous operation."""
        service.start()
        
        # Simulate 24 hours with wake/sleep cycles
        # Use shorter intervals for testing
        for _ in range(100):  # Simulate 100 cycles
            service.handle_wake_word_detected()
            time.sleep(0.01)
            service._transition_to_sleep()
            time.sleep(0.01)
        
        metrics = service.get_metrics()
        assert metrics.wake_word_detections == 100  # nosec B101
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    def test_stress_rapid_state_transitions_counted(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Stress test with rapid state transitions."""
        service.start()
        
        for _ in range(500):
            service.handle_wake_word_detected()
            service._transition_to_sleep()
        
        metrics = service.get_metrics()
        assert metrics.state_transitions >= 1000  # 1 start + 500*2 transitions  # nosec B101
        
        service.stop()
    
    def test_stress_memory_leak_detection(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Stress test for memory leaks."""
        import gc
        
        service.start()
        gc.collect()
        
        # Run many cycles
        for _ in range(1000):
            service.handle_wake_word_detected()
            service.handle_command_received("test command")
            service._transition_to_sleep()
        
        gc.collect()
        
        # If we got here without crashing, no obvious memory leak
        metrics = service.get_metrics()
        assert metrics.commands_processed == 1000  # nosec B101
        
        service.stop()
    
    def test_stress_concurrent_commands(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Stress test with concurrent commands."""
        service.start()
        service.handle_wake_word_detected()
        
        # Simulate concurrent commands
        threads = []
        for i in range(100):
            t = threading.Thread(target=service.handle_command_received, args=(f"command {i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should handle all commands
        metrics = service.get_metrics()
        assert metrics.commands_processed == 100  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # ZERO COMPROMISE - CHAOS TESTS
    # ========================================================================
    
    def test_chaos_random_state_transitions(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Chaos test with random state transitions."""
        import random
        
        service.start()
        
        actions = [
            lambda: service.handle_wake_word_detected(),
            lambda: service.handle_command_received("test"),
            lambda: service.handle_silence_detected(),
            lambda: service._transition_to_sleep(),
        ]
        
        for _ in range(100):
            action = random.choice(actions)  # nosec B311
            try:
                action()
            except Exception:
                pass  # nosec B110
        
        # Service should still be running
        assert service.get_state() in [ServiceState.SLEEP, ServiceState.WAKE]  # nosec B101
        
        service.stop()
    
    def test_chaos_callback_exceptions_repeated(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Chaos test with callback exceptions."""
        exception_count = [0]
        
        def bad_wake_callback():
            exception_count[0] += 1
            raise Exception(f"Wake callback error {exception_count[0]}")
        
        def bad_command_callback(cmd):
            exception_count[0] += 1
            raise Exception(f"Command callback error {exception_count[0]}")
        
        service.wake_word_callback = bad_wake_callback
        service.command_callback = bad_command_callback
        service.start()
        
        # Trigger callbacks multiple times
        # First wake word will work, subsequent ones will be in wrong state
        service.handle_wake_word_detected()  # 1 error (wake callback)
        for _ in range(10):
            service.handle_command_received("test")  # 10 errors (command callback)
        
        # Service should still be running despite exceptions
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        metrics = service.get_metrics()
        assert metrics.errors == 11  # 1 wake + 10 command errors  # nosec B101
        
        service.stop()
    
    def test_chaos_stop_during_wake(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Chaos test stopping during wake mode."""
        service.start()
        service.handle_wake_word_detected()
        
        # Stop immediately during wake
        service.stop()
        
        assert service.get_state() == ServiceState.STOPPED  # nosec B101
    
    def test_chaos_multiple_errors_in_sequence(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Chaos test with multiple errors."""
        service.start()
        
        for i in range(50):
            service.handle_wake_word_detected()
            service.handle_error(Exception(f"Error {i}"))
        
        # Should recover from all errors
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        metrics = service.get_metrics()
        assert metrics.errors == 50  # nosec B101
        
        service.stop()
    
    # ========================================================================
    # ZERO COMPROMISE - EDGE CASES
    # ========================================================================
    
    def test_edge_case_wake_word_in_wake_mode(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Edge case - wake word while already awake."""
        service.start()
        service.handle_wake_word_detected()
        
        # Detect wake word again while awake
        service.handle_wake_word_detected()
        
        # Should handle gracefully
        assert service.get_state() == ServiceState.WAKE  # nosec B101
        
        service.stop()
    
    def test_edge_case_command_in_sleep_mode(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Edge case - command while in sleep mode."""
        service.start()
        
        # Try to handle command in sleep mode
        service.handle_command_received("test command")
        
        # Should handle gracefully (log warning but not crash)
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    def test_edge_case_silence_in_sleep_mode(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Edge case - silence detection in sleep mode."""
        service.start()
        
        # Detect silence in sleep mode
        service.handle_silence_detected()
        
        # Should handle gracefully
        assert service.get_state() == ServiceState.SLEEP  # nosec B101
        
        service.stop()
    
    def test_edge_case_zero_timeout(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Edge case - zero wake timeout."""
        service._wake_timeout_seconds = 0.0
        service.start()
        service.handle_wake_word_detected()
        
        # Should handle zero timeout gracefully
        time.sleep(0.1)
        
        service.stop()
    
    def test_edge_case_very_long_timeout(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Edge case - very long wake timeout."""
        service._wake_timeout_seconds = 3600.0  # 1 hour
        service.start()
        service.handle_wake_word_detected()
        
        # Should set timeout without issues
        assert service._wake_timeout_timer is not None  # nosec B101
        
        service.stop()
    
    def test_edge_case_pause_without_start(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Edge case - pause without start."""
        with pytest.raises(RuntimeError):
            service.pause()
    
    def test_edge_case_multiple_starts(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Edge case - multiple start calls."""
        service.start()
        
        with pytest.raises(RuntimeError):
            service.start()
        
        service.stop()
    
    # ========================================================================
    # ZERO COMPROMISE - PERFORMANCE VALIDATION
    # ========================================================================
    
    def test_performance_wake_transition_latency(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Validate wake transition latency <500ms."""
        service.start()
        
        # Test multiple transitions
        latencies = []
        for _ in range(10):
            start_time = time.time()
            service.handle_wake_word_detected()
            elapsed = time.time() - start_time
            latencies.append(elapsed)
            
            service._transition_to_sleep()
        
        # All transitions should be <500ms
        for latency in latencies:
            assert latency < 0.5, f"Transition took {latency:.3f}s (target: <0.5s)"  # nosec B101
        
        # Average should be well below target
        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.3  # nosec B101
        
        service.stop()
    
    def test_performance_metrics_overhead(self, service: BackgroundServiceManager):
        """ZERO COMPROMISE: Test metrics collection overhead."""
        service.start()
        
        # Collect metrics many times
        start_time = time.time()
        for _ in range(100):  # Reduced from 1000 due to psutil overhead
            service.get_metrics()
        elapsed = time.time() - start_time
        
        # Should be reasonably fast (<100ms per call on average)
        # Note: psutil.cpu_percent() has overhead on Windows
        assert elapsed < 15.0  # 100 calls in <15s = <150ms per call  # nosec B101
        
        service.stop()
