"""
Unit tests for workstation locking system.

This module tests the automatic workstation locking functionality that provides
immediate security response when intrusion attempts are detected.

Test Coverage:
- Windows API integration and error handling
- Lock trigger mechanisms and event logging
- Configuration and capability testing
- Error conditions and fallback mechanisms
- Integration with intrusion detection system
"""

import pytest
import unittest.mock as mock
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
import ctypes
import uuid

from src.intrusion.workstation_lock import (
    WorkstationLocker,
    WorkstationLockResult,
    WorkstationLockTrigger,
    WorkstationLockEvent,
    WorkstationLockConfig,
    WorkstationLockError,
    WorkstationLockPermissionError,
    WorkstationLockSystemError,
    create_workstation_locker
)


class TestWorkstationLockConfig:
    """Test workstation lock configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = WorkstationLockConfig()
        
        assert config.enable_immediate_lock is True
        assert config.enable_lock_logging is True
        assert config.enable_fallback_mechanisms is True
        assert config.max_lock_attempts == 3
        assert config.retry_delay_seconds == 0.5
        assert config.log_successful_locks is True
        assert config.log_failed_locks is True
        assert config.require_elevated_privileges is False
        assert config.validate_lock_success is True
        assert config.notify_callbacks_on_lock is True
        assert config.retain_lock_events_hours == 24
        assert config.max_lock_events_stored == 1000
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = WorkstationLockConfig(
            enable_immediate_lock=False,
            max_lock_attempts=5,
            retry_delay_seconds=1.0,
            log_successful_locks=False
        )
        
        assert config.enable_immediate_lock is False
        assert config.max_lock_attempts == 5
        assert config.retry_delay_seconds == 1.0
        assert config.log_successful_locks is False


class TestWorkstationLockEvent:
    """Test workstation lock event data structure."""
    
    def test_event_creation(self):
        """Test creating a workstation lock event."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        trigger = WorkstationLockTrigger.BIOMETRIC_FAILURE
        result = WorkstationLockResult.SUCCESS
        context = {'test': 'context'}
        
        event = WorkstationLockEvent(
            event_id=event_id,
            timestamp=timestamp,
            trigger=trigger,
            result=result,
            trigger_context=context
        )
        
        assert event.event_id == event_id
        assert event.timestamp == timestamp
        assert event.trigger == trigger
        assert event.result == result
        assert event.trigger_context == context
        assert event.error_details is None
        assert event.session_id is None
    
    def test_event_with_error_details(self):
        """Test creating event with error details."""
        event = WorkstationLockEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            trigger=WorkstationLockTrigger.INTRUSION_DETECTED,
            result=WorkstationLockResult.FAILED_API_CALL,
            trigger_context={},
            error_details="API call failed",
            session_id="test-session"
        )
        
        assert event.error_details == "API call failed"
        assert event.session_id == "test-session"


class TestWorkstationLocker:
    """Test workstation locking functionality."""
    
    @pytest.fixture
    def mock_windows_api(self):
        """Mock Windows API for testing."""
        with patch('ctypes.windll') as mock_windll:
            mock_user32 = MagicMock()
            mock_windll.user32 = mock_user32
            mock_windll.kernel32.GetLastError.return_value = 0
            
            # Mock LockWorkStation function
            mock_user32.LockWorkStation.return_value = True
            mock_user32.LockWorkStation.argtypes = []
            mock_user32.LockWorkStation.restype = ctypes.wintypes.BOOL
            
            yield mock_user32
    
    @pytest.fixture
    def mock_platform(self):
        """Mock platform detection."""
        with patch('platform.system') as mock_system, \
             patch('platform.version') as mock_version:
            mock_system.return_value = 'Windows'
            mock_version.return_value = '10.0.19041'
            yield mock_system, mock_version
    
    @pytest.fixture
    def workstation_locker(self, mock_windows_api, mock_platform):
        """Create a workstation locker for testing."""
        config = WorkstationLockConfig(
            max_lock_attempts=2,
            retry_delay_seconds=0.1
        )
        return WorkstationLocker(config)
    
    def test_initialization(self, workstation_locker):
        """Test workstation locker initialization."""
        assert workstation_locker._api_available is True
        assert workstation_locker._system_supported is True
        assert len(workstation_locker._lock_events) == 0
        assert workstation_locker._consecutive_failures == 0
        assert workstation_locker._last_lock_attempt is None
    
    def test_successful_lock(self, workstation_locker, mock_windows_api):
        """Test successful workstation lock."""
        mock_windows_api.LockWorkStation.return_value = True
        
        event = workstation_locker.lock_workstation(
            trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE,
            trigger_context={'test': 'context'},
            session_id='test-session'
        )
        
        assert event.result == WorkstationLockResult.SUCCESS
        assert event.trigger == WorkstationLockTrigger.BIOMETRIC_FAILURE
        assert event.trigger_context == {'test': 'context'}
        assert event.session_id == 'test-session'
        assert event.error_details is None
        
        # Verify API was called
        mock_windows_api.LockWorkStation.assert_called_once()
        
        # Verify event was stored
        assert len(workstation_locker._lock_events) == 1
        assert workstation_locker._consecutive_failures == 0
        assert workstation_locker._last_lock_attempt is not None
    
    def test_failed_lock_api_call(self, workstation_locker, mock_windows_api):
        """Test failed workstation lock due to API call failure."""
        mock_windows_api.LockWorkStation.return_value = False
        
        with patch('ctypes.windll.kernel32.GetLastError') as mock_get_error:
            mock_get_error.return_value = 87  # ERROR_INVALID_PARAMETER
            
            event = workstation_locker.lock_workstation(
                trigger=WorkstationLockTrigger.INTRUSION_DETECTED
            )
        
        assert event.result == WorkstationLockResult.FAILED_API_CALL
        assert event.error_details is not None
        assert "87" in event.error_details
        
        # Should retry based on config (max_lock_attempts=2)
        assert mock_windows_api.LockWorkStation.call_count == 2
        assert workstation_locker._consecutive_failures == 1
    
    def test_failed_lock_permission_error(self, workstation_locker, mock_windows_api):
        """Test failed workstation lock due to permission error."""
        mock_windows_api.LockWorkStation.return_value = False
        
        with patch('ctypes.windll.kernel32.GetLastError') as mock_get_error:
            mock_get_error.return_value = 5  # ERROR_ACCESS_DENIED
            
            event = workstation_locker.lock_workstation(
                trigger=WorkstationLockTrigger.SECURITY_VIOLATION
            )
        
        assert event.result == WorkstationLockResult.FAILED_PERMISSION
        assert "Access denied" in event.error_details
        
        # Should not retry for permission errors
        mock_windows_api.LockWorkStation.assert_called_once()
    
    def test_failed_lock_system_error(self, workstation_locker, mock_windows_api):
        """Test failed workstation lock due to system error."""
        mock_windows_api.LockWorkStation.side_effect = OSError("System error")
        
        event = workstation_locker.lock_workstation(
            trigger=WorkstationLockTrigger.MULTIPLE_FAILURES
        )
        
        assert event.result == WorkstationLockResult.FAILED_SYSTEM_ERROR
        assert event.error_details is not None
        
        # Should retry based on config
        assert mock_windows_api.LockWorkStation.call_count == 2
    
    def test_api_not_available(self, mock_platform):
        """Test behavior when Windows API is not available."""
        with patch('ctypes.windll') as mock_windll:
            mock_windll.user32 = MagicMock()
            # Simulate API not available
            del mock_windll.user32.LockWorkStation
            
            locker = WorkstationLocker()
            
            event = locker.lock_workstation(
                trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE
            )
            
            assert event.result == WorkstationLockResult.FAILED_NOT_SUPPORTED
    
    def test_non_windows_system(self):
        """Test behavior on non-Windows systems."""
        with patch('platform.system') as mock_system:
            mock_system.return_value = 'Linux'
            
            locker = WorkstationLocker()
            
            event = locker.lock_workstation(
                trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE
            )
            
            assert event.result == WorkstationLockResult.FAILED_NOT_SUPPORTED
    
    def test_callback_registration_and_notification(self, workstation_locker, mock_windows_api):
        """Test callback registration and notification."""
        callback_called = []
        
        def test_callback(event):
            callback_called.append(event)
        
        workstation_locker.register_lock_callback(test_callback)
        
        mock_windows_api.LockWorkStation.return_value = True
        
        event = workstation_locker.lock_workstation(
            trigger=WorkstationLockTrigger.VOICE_SPOOFING
        )
        
        assert len(callback_called) == 1
        assert callback_called[0] == event
    
    def test_callback_error_handling(self, workstation_locker, mock_windows_api):
        """Test callback error handling."""
        def failing_callback(event):
            raise Exception("Callback error")
        
        workstation_locker.register_lock_callback(failing_callback)
        
        mock_windows_api.LockWorkStation.return_value = True
        
        # Should not raise exception despite callback failure
        event = workstation_locker.lock_workstation(
            trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE
        )
        
        assert event.result == WorkstationLockResult.SUCCESS
    
    def test_emergency_lock(self, workstation_locker, mock_windows_api):
        """Test emergency lock functionality."""
        mock_windows_api.LockWorkStation.return_value = True
        
        event = workstation_locker.emergency_lock("Test emergency")
        
        assert event.result == WorkstationLockResult.SUCCESS
        assert event.trigger == WorkstationLockTrigger.MANUAL_TRIGGER
        assert event.trigger_context['reason'] == "Test emergency"
        assert event.trigger_context['emergency'] == 'true'
    
    def test_consecutive_failure_tracking(self, workstation_locker, mock_windows_api):
        """Test consecutive failure tracking."""
        mock_windows_api.LockWorkStation.return_value = False
        
        with patch('ctypes.windll.kernel32.GetLastError') as mock_get_error:
            mock_get_error.return_value = 87
            
            # First failure
            event1 = workstation_locker.lock_workstation(
                trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE
            )
            assert workstation_locker._consecutive_failures == 1
            
            # Second failure
            event2 = workstation_locker.lock_workstation(
                trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE
            )
            assert workstation_locker._consecutive_failures == 2
            
            # Success should reset counter
            mock_windows_api.LockWorkStation.return_value = True
            event3 = workstation_locker.lock_workstation(
                trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE
            )
            assert workstation_locker._consecutive_failures == 0
    
    def test_get_lock_statistics(self, workstation_locker, mock_windows_api):
        """Test lock statistics retrieval."""
        # Perform some lock attempts
        mock_windows_api.LockWorkStation.return_value = True
        workstation_locker.lock_workstation(WorkstationLockTrigger.BIOMETRIC_FAILURE)
        
        mock_windows_api.LockWorkStation.return_value = False
        with patch('ctypes.windll.kernel32.GetLastError', return_value=5):
            workstation_locker.lock_workstation(WorkstationLockTrigger.VOICE_SPOOFING)
        
        stats = workstation_locker.get_lock_statistics()
        
        assert stats['total_lock_attempts'] == 2
        assert stats['consecutive_failures'] == 1
        assert stats['result_distribution']['success'] == 1
        assert stats['result_distribution']['failed_permission'] == 1
        assert stats['trigger_distribution']['biometric_failure'] == 1
        assert stats['trigger_distribution']['voice_spoofing'] == 1
        assert stats['system_status']['api_available'] is True
        assert stats['system_status']['system_supported'] is True
    
    def test_get_recent_lock_events(self, workstation_locker, mock_windows_api):
        """Test recent lock events retrieval."""
        mock_windows_api.LockWorkStation.return_value = True
        
        # Create multiple events
        for i in range(5):
            workstation_locker.lock_workstation(
                trigger=WorkstationLockTrigger.BIOMETRIC_FAILURE,
                trigger_context={'attempt': str(i)}
            )
        
        recent_events = workstation_locker.get_recent_lock_events(limit=3)
        
        assert len(recent_events) == 3
        # Should be in reverse chronological order (most recent first)
        assert recent_events[0].trigger_context['attempt'] == '4'
        assert recent_events[1].trigger_context['attempt'] == '3'
        assert recent_events[2].trigger_context['attempt'] == '2'
    
    def test_capability_testing(self, workstation_locker):
        """Test lock capability testing."""
        test_results = workstation_locker.test_lock_capability()
        
        assert 'api_available' in test_results
        assert 'system_supported' in test_results
        assert 'config_enabled' in test_results
        assert 'test_timestamp' in test_results
        assert 'function_accessible' in test_results
        assert 'function_callable' in test_results
        
        assert test_results['api_available'] is True
        assert test_results['system_supported'] is True
        assert test_results['config_enabled'] is True
        assert test_results['function_accessible'] is True
        assert test_results['function_callable'] is True
    
    def test_fallback_mechanisms(self, workstation_locker, mock_windows_api):
        """Test fallback security mechanisms."""
        # Mock primary lock failure
        mock_windows_api.LockWorkStation.return_value = False
        
        # Mock fallback ExitWindowsEx success
        mock_windows_api.ExitWindowsEx.return_value = True
        
        with patch('ctypes.windll.kernel32.GetLastError', return_value=87):
            event = workstation_locker.lock_workstation(
                trigger=WorkstationLockTrigger.INTRUSION_DETECTED
            )
        
        # Primary should fail, but fallback mechanisms should be attempted
        assert event.result == WorkstationLockResult.FAILED_API_CALL
        
        # Verify fallback was attempted (ExitWindowsEx should be called)
        # Note: This would require more sophisticated mocking to verify fallback execution
    
    def test_config_disabled_immediate_lock(self, mock_windows_api, mock_platform):
        """Test behavior when immediate lock is disabled in config."""
        config = WorkstationLockConfig(enable_immediate_lock=False)
        locker = WorkstationLocker(config)
        
        # Even with disabled config, lock should still work when explicitly called
        mock_windows_api.LockWorkStation.return_value = True
        
        event = locker.lock_workstation(
            trigger=WorkstationLockTrigger.MANUAL_TRIGGER
        )
        
        assert event.result == WorkstationLockResult.SUCCESS


class TestWorkstationLockFactory:
    """Test workstation lock factory function."""
    
    @patch('platform.system', return_value='Windows')
    @patch('platform.version', return_value='10.0.19041')
    @patch('ctypes.windll')
    def test_create_workstation_locker_default(self, mock_windll, mock_version, mock_system):
        """Test creating workstation locker with default config."""
        mock_user32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_windll.kernel32.GetLastError.return_value = 0
        
        locker = create_workstation_locker()
        
        assert isinstance(locker, WorkstationLocker)
        assert locker.config.enable_immediate_lock is True
    
    @patch('platform.system', return_value='Windows')
    @patch('platform.version', return_value='10.0.19041')
    @patch('ctypes.windll')
    def test_create_workstation_locker_custom_config(self, mock_windll, mock_version, mock_system):
        """Test creating workstation locker with custom config."""
        mock_user32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_windll.kernel32.GetLastError.return_value = 0
        
        config = WorkstationLockConfig(max_lock_attempts=5)
        locker = create_workstation_locker(config)
        
        assert isinstance(locker, WorkstationLocker)
        assert locker.config.max_lock_attempts == 5


class TestWorkstationLockIntegration:
    """Test workstation lock integration scenarios."""
    
    @pytest.fixture
    def mock_environment(self):
        """Mock complete environment for integration testing."""
        with patch('platform.system', return_value='Windows'), \
             patch('platform.version', return_value='10.0.19041'), \
             patch('ctypes.windll') as mock_windll:
            
            mock_user32 = MagicMock()
            mock_windll.user32 = mock_user32
            mock_windll.kernel32.GetLastError.return_value = 0
            
            mock_user32.LockWorkStation.return_value = True
            mock_user32.LockWorkStation.argtypes = []
            mock_user32.LockWorkStation.restype = ctypes.wintypes.BOOL
            
            yield mock_user32
    
    def test_multiple_trigger_types(self, mock_environment):
        """Test workstation locking with different trigger types."""
        locker = WorkstationLocker()
        
        triggers = [
            WorkstationLockTrigger.BIOMETRIC_FAILURE,
            WorkstationLockTrigger.VOICE_SPOOFING,
            WorkstationLockTrigger.INTRUSION_DETECTED,
            WorkstationLockTrigger.MULTIPLE_FAILURES,
            WorkstationLockTrigger.MANUAL_TRIGGER,
            WorkstationLockTrigger.SECURITY_VIOLATION
        ]
        
        for trigger in triggers:
            event = locker.lock_workstation(
                trigger=trigger,
                trigger_context={'test_trigger': trigger.value}
            )
            
            assert event.result == WorkstationLockResult.SUCCESS
            assert event.trigger == trigger
        
        # Verify all events were recorded
        assert len(locker._lock_events) == len(triggers)
        
        # Verify statistics
        stats = locker.get_lock_statistics()
        assert stats['total_lock_attempts'] == len(triggers)
        for trigger in triggers:
            assert stats['trigger_distribution'][trigger.value] == 1
    
    def test_high_frequency_lock_attempts(self, mock_environment):
        """Test handling of high-frequency lock attempts."""
        locker = WorkstationLocker()
        
        # Simulate rapid lock attempts
        events = []
        for i in range(10):
            event = locker.lock_workstation(
                trigger=WorkstationLockTrigger.INTRUSION_DETECTED,
                trigger_context={'attempt': str(i)}
            )
            events.append(event)
        
        # All should succeed
        for event in events:
            assert event.result == WorkstationLockResult.SUCCESS
        
        # Verify proper event tracking
        assert len(locker._lock_events) == 10
        assert locker._consecutive_failures == 0
    
    def test_mixed_success_failure_scenarios(self, mock_environment):
        """Test mixed success and failure scenarios."""
        locker = WorkstationLocker()
        
        # Success
        mock_environment.LockWorkStation.return_value = True
        event1 = locker.lock_workstation(WorkstationLockTrigger.BIOMETRIC_FAILURE)
        assert event1.result == WorkstationLockResult.SUCCESS
        assert locker._consecutive_failures == 0
        
        # Failure
        mock_environment.LockWorkStation.return_value = False
        with patch('ctypes.windll.kernel32.GetLastError', return_value=87):
            event2 = locker.lock_workstation(WorkstationLockTrigger.VOICE_SPOOFING)
        assert event2.result == WorkstationLockResult.FAILED_API_CALL
        assert locker._consecutive_failures == 1
        
        # Another failure
        event3 = locker.lock_workstation(WorkstationLockTrigger.INTRUSION_DETECTED)
        assert event3.result == WorkstationLockResult.FAILED_API_CALL
        assert locker._consecutive_failures == 2
        
        # Success should reset
        mock_environment.LockWorkStation.return_value = True
        event4 = locker.lock_workstation(WorkstationLockTrigger.MANUAL_TRIGGER)
        assert event4.result == WorkstationLockResult.SUCCESS
        assert locker._consecutive_failures == 0
        
        # Verify statistics
        stats = locker.get_lock_statistics()
        assert stats['total_lock_attempts'] == 4
        assert stats['result_distribution']['success'] == 2
        assert stats['result_distribution']['failed_api_call'] == 2