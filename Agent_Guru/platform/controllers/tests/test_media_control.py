"""
Tests for agent_guru.platform.controllers.media_control
Coverage Target: >80% (enforced by CI/CD)

Test Categories:
- Unit tests for each media operation
- Platform-specific backend tests
- Error handling tests
- Integration tests with mocked media players
"""

import pytest
import platform
import subprocess
import time
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st

from Agent_Guru.platform.controllers.media_control import (
    MediaController,
    MediaBackend,
    WindowsMediaBackend,
    MacOSMediaBackend,
    LinuxMediaBackend,
    MediaState,
    MediaControlError,
    UnsupportedMediaOperationError,
    MediaCommandError,
)


# Unit Tests

class TestMediaState:
    """Unit tests for MediaState data model."""
    
    def test_media_state_creation(self):
        """Test MediaState creation with all fields."""
        state = MediaState(
            is_playing=True,
            volume=75,
            is_muted=False,
            track_title="Test Track",
            artist="Test Artist"
        )
        
        assert state.is_playing is True
        assert state.volume == 75
        assert state.is_muted is False
        assert state.track_title == "Test Track"
        assert state.artist == "Test Artist"
    
    def test_media_state_minimal(self):
        """Test MediaState with minimal required fields."""
        state = MediaState(
            is_playing=False,
            volume=50,
            is_muted=True
        )
        
        assert state.is_playing is False
        assert state.volume == 50
        assert state.is_muted is True
        assert state.track_title is None
        assert state.artist is None


class TestMediaControllerInitialization:
    """Unit tests for MediaController initialization."""
    
    @patch('platform.system')
    def test_windows_backend_selection(self, mock_system):
        """Test that Windows backend is selected on Windows."""
        mock_system.return_value = "Windows"
        
        with patch('Agent_Guru.platform.controllers.media_control.WindowsMediaBackend'):
            controller = MediaController()
            assert isinstance(controller._backend, (WindowsMediaBackend, Mock))
    
    @patch('platform.system')
    def test_macos_backend_selection(self, mock_system):
        """Test that macOS backend is selected on Darwin."""
        mock_system.return_value = "Darwin"
        
        controller = MediaController()
        assert isinstance(controller._backend, MacOSMediaBackend)
    
    @patch('platform.system')
    def test_linux_backend_selection(self, mock_system):
        """Test that Linux backend is selected on Linux."""
        mock_system.return_value = "Linux"
        
        controller = MediaController()
        assert isinstance(controller._backend, LinuxMediaBackend)
    
    @patch('platform.system')
    def test_unsupported_platform(self, mock_system):
        """Test that unsupported platform raises error."""
        mock_system.return_value = "FreeBSD"
        
        with pytest.raises(UnsupportedMediaOperationError):
            MediaController()


class TestMediaControllerOperations:
    """Unit tests for MediaController operations."""
    
    @pytest.fixture
    def mock_backend(self):
        """Create mock backend for testing."""
        backend = Mock(spec=MediaBackend)
        return backend
    
    @pytest.fixture
    def controller_with_mock(self, mock_backend):
        """Create controller with mock backend."""
        with patch('platform.system', return_value='Linux'):
            controller = MediaController()
            controller._backend = mock_backend
            return controller
    
    def test_play(self, controller_with_mock, mock_backend):
        """Test play operation."""
        controller_with_mock.play()
        mock_backend.play.assert_called_once()
    
    def test_pause(self, controller_with_mock, mock_backend):
        """Test pause operation."""
        controller_with_mock.pause()
        mock_backend.pause.assert_called_once()
    
    def test_play_pause_toggle(self, controller_with_mock, mock_backend):
        """Test play/pause toggle operation."""
        controller_with_mock.play_pause_toggle()
        mock_backend.play_pause_toggle.assert_called_once()
    
    def test_stop(self, controller_with_mock, mock_backend):
        """Test stop operation."""
        controller_with_mock.stop()
        mock_backend.stop.assert_called_once()
    
    def test_next_track(self, controller_with_mock, mock_backend):
        """Test next track operation."""
        controller_with_mock.next_track()
        mock_backend.next_track.assert_called_once()
    
    def test_previous_track(self, controller_with_mock, mock_backend):
        """Test previous track operation."""
        controller_with_mock.previous_track()
        mock_backend.previous_track.assert_called_once()
    
    def test_volume_up_default(self, controller_with_mock, mock_backend):
        """Test volume up with default amount."""
        controller_with_mock.volume_up()
        mock_backend.volume_up.assert_called_once_with(10)
    
    def test_volume_up_custom(self, controller_with_mock, mock_backend):
        """Test volume up with custom amount."""
        controller_with_mock.volume_up(25)
        mock_backend.volume_up.assert_called_once_with(25)
    
    def test_volume_down_default(self, controller_with_mock, mock_backend):
        """Test volume down with default amount."""
        controller_with_mock.volume_down()
        mock_backend.volume_down.assert_called_once_with(10)
    
    def test_volume_down_custom(self, controller_with_mock, mock_backend):
        """Test volume down with custom amount."""
        controller_with_mock.volume_down(15)
        mock_backend.volume_down.assert_called_once_with(15)
    
    def test_mute(self, controller_with_mock, mock_backend):
        """Test mute operation."""
        controller_with_mock.mute()
        mock_backend.mute.assert_called_once()
    
    def test_unmute(self, controller_with_mock, mock_backend):
        """Test unmute operation."""
        controller_with_mock.unmute()
        mock_backend.unmute.assert_called_once()
    
    def test_get_state(self, controller_with_mock, mock_backend):
        """Test get state operation."""
        expected_state = MediaState(
            is_playing=True,
            volume=80,
            is_muted=False
        )
        mock_backend.get_state.return_value = expected_state
        
        state = controller_with_mock.get_state()
        assert state == expected_state
        mock_backend.get_state.assert_called_once()
    
    def test_get_state_none(self, controller_with_mock, mock_backend):
        """Test get state when state unavailable."""
        mock_backend.get_state.return_value = None
        
        state = controller_with_mock.get_state()
        assert state is None


class TestMediaControllerErrorHandling:
    """Unit tests for MediaController error handling."""
    
    @pytest.fixture
    def controller_with_failing_backend(self):
        """Create controller with backend that raises errors."""
        with patch('platform.system', return_value='Linux'):
            controller = MediaController()
            backend = Mock(spec=MediaBackend)
            backend.play.side_effect = MediaCommandError("Test error")
            backend.pause.side_effect = MediaCommandError("Test error")
            backend.next_track.side_effect = MediaCommandError("Test error")
            controller._backend = backend
            return controller
    
    def test_play_error_propagation(self, controller_with_failing_backend):
        """Test that play errors are propagated."""
        with pytest.raises(MediaCommandError):
            controller_with_failing_backend.play()
    
    def test_pause_error_propagation(self, controller_with_failing_backend):
        """Test that pause errors are propagated."""
        with pytest.raises(MediaCommandError):
            controller_with_failing_backend.pause()
    
    def test_next_track_error_propagation(self, controller_with_failing_backend):
        """Test that next track errors are propagated."""
        with pytest.raises(MediaCommandError):
            controller_with_failing_backend.next_track()


# Windows Backend Tests

@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
class TestWindowsMediaBackend:
    """Unit tests for Windows media backend."""
    
    @pytest.fixture
    def backend(self):
        """Create Windows media backend."""
        try:
            return WindowsMediaBackend()
        except ImportError:
            pytest.skip("pywin32 not available")
    
    def test_initialization(self, backend):
        """Test Windows backend initialization."""
        assert backend.win32api is not None
        assert backend.win32con is not None
    
    def test_play_sends_key(self, backend):
        """Test that play sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.play()
            mock_send.assert_called_once_with(0xB3)
    
    def test_pause_sends_key(self, backend):
        """Test that pause sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.pause()
            mock_send.assert_called_once_with(0xB3)
    
    def test_next_track_sends_key(self, backend):
        """Test that next track sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.next_track()
            mock_send.assert_called_once_with(0xB0)
    
    def test_previous_track_sends_key(self, backend):
        """Test that previous track sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.previous_track()
            mock_send.assert_called_once_with(0xB1)
    
    def test_get_state_returns_none(self, backend):
        """Test that Windows backend returns None for state."""
        state = backend.get_state()
        assert state is None


# macOS Backend Tests

@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
class TestMacOSMediaBackend:
    """Unit tests for macOS media backend."""
    
    @pytest.fixture
    def backend(self):
        """Create macOS media backend."""
        return MacOSMediaBackend()
    
    def test_play_executes_applescript(self, backend):
        """Test that play executes AppleScript."""
        with patch.object(backend, '_execute_applescript') as mock_exec:
            backend.play()
            assert mock_exec.called
    
    def test_pause_executes_applescript(self, backend):
        """Test that pause executes AppleScript."""
        with patch.object(backend, '_execute_applescript') as mock_exec:
            backend.pause()
            assert mock_exec.called
    
    def test_next_track_sends_key(self, backend):
        """Test that next track sends media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.next_track()
            mock_send.assert_called_once_with(17)
    
    def test_previous_track_sends_key(self, backend):
        """Test that previous track sends media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.previous_track()
            mock_send.assert_called_once_with(18)


# Linux Backend Tests

@pytest.mark.skipif(platform.system() != "Linux", reason="Linux only")
class TestLinuxMediaBackend:
    """Unit tests for Linux media backend."""
    
    @pytest.fixture
    def backend_with_playerctl(self):
        """Create Linux backend with playerctl available."""
        with patch.object(LinuxMediaBackend, '_check_playerctl', return_value=True):
            return LinuxMediaBackend()
    
    @pytest.fixture
    def backend_without_playerctl(self):
        """Create Linux backend without playerctl."""
        with patch.object(LinuxMediaBackend, '_check_playerctl', return_value=False):
            return LinuxMediaBackend()
    
    def test_initialization_with_playerctl(self, backend_with_playerctl):
        """Test initialization when playerctl is available."""
        assert backend_with_playerctl.use_playerctl is True
    
    def test_initialization_without_playerctl(self, backend_without_playerctl):
        """Test initialization when playerctl is not available."""
        assert backend_without_playerctl.use_playerctl is False
    
    def test_play_with_playerctl(self, backend_with_playerctl):
        """Test play with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.play()
            mock_exec.assert_called_once_with("play")
    
    def test_play_without_playerctl(self, backend_without_playerctl):
        """Test play without playerctl (xdotool fallback)."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.play()
            mock_send.assert_called_once_with("XF86AudioPlay")
    
    def test_next_track_with_playerctl(self, backend_with_playerctl):
        """Test next track with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.next_track()
            mock_exec.assert_called_once_with("next")
    
    def test_previous_track_with_playerctl(self, backend_with_playerctl):
        """Test previous track with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.previous_track()
            mock_exec.assert_called_once_with("previous")


# Property-Based Tests

class TestMediaControllerProperties:
    """Property-based tests for MediaController."""
    
    @given(amount=st.integers(min_value=0, max_value=100))
    def test_volume_up_valid_amounts(self, amount):
        """Property: Valid volume amounts should not raise errors."""
        with patch('platform.system', return_value='Linux'):
            controller = MediaController()
            backend = Mock(spec=MediaBackend)
            controller._backend = backend
            
            controller.volume_up(amount)
            backend.volume_up.assert_called_once_with(amount)
    
    @given(amount=st.integers(min_value=0, max_value=100))
    def test_volume_down_valid_amounts(self, amount):
        """Property: Valid volume amounts should not raise errors."""
        with patch('platform.system', return_value='Linux'):
            controller = MediaController()
            backend = Mock(spec=MediaBackend)
            controller._backend = backend
            
            controller.volume_down(amount)
            backend.volume_down.assert_called_once_with(amount)
    
    @given(
        is_playing=st.booleans(),
        volume=st.integers(min_value=0, max_value=100),
        is_muted=st.booleans()
    )
    def test_media_state_always_valid(self, is_playing, volume, is_muted):
        """Property: MediaState should accept all valid combinations."""
        state = MediaState(
            is_playing=is_playing,
            volume=volume,
            is_muted=is_muted
        )
        
        assert isinstance(state.is_playing, bool)
        assert 0 <= state.volume <= 100
        assert isinstance(state.is_muted, bool)


# Integration Tests

@pytest.mark.integration
class TestMediaControllerIntegration:
    """Integration tests for MediaController with real backends."""
    
    @pytest.mark.skipif(platform.system() not in ["Windows", "Darwin", "Linux"],
                       reason="Requires supported platform")
    def test_controller_creation_on_supported_platform(self):
        """Test that controller can be created on supported platforms."""
        # This may fail if platform-specific dependencies are missing
        try:
            controller = MediaController()
            assert controller is not None
            assert controller._backend is not None
        except ImportError as e:
            pytest.skip(f"Platform dependencies not available: {e}")
    
    @pytest.mark.skipif(platform.system() not in ["Windows", "Darwin", "Linux"],
                       reason="Requires supported platform")
    def test_all_operations_callable(self):
        """Test that all media operations can be called without errors."""
        try:
            controller = MediaController()
            
            # These operations should not raise exceptions
            # (though they may not have visible effects in test environment)
            operations = [
                controller.play,
                controller.pause,
                controller.play_pause_toggle,
                controller.stop,
                controller.next_track,
                controller.previous_track,
                lambda: controller.volume_up(5),
                lambda: controller.volume_down(5),
                controller.mute,
                controller.unmute,
                controller.get_state,
            ]
            
            for operation in operations:
                try:
                    operation()
                except (MediaCommandError, UnsupportedMediaOperationError):
                    # Expected in test environment without media player
                    pass
                
        except ImportError as e:
            pytest.skip(f"Platform dependencies not available: {e}")


# Performance Tests

@pytest.mark.performance
class TestMediaControllerPerformance:
    """Performance tests for media controller."""
    
    def test_operation_latency(self):
        """Test that media operations complete quickly (<50ms target)."""
        with patch('platform.system', return_value='Linux'):
            controller = MediaController()
            backend = Mock(spec=MediaBackend)
            controller._backend = backend
            
            # Measure operation latency
            start = time.perf_counter()
            controller.play()
            end = time.perf_counter()
            
            elapsed = end - start
            
            # Should complete in <50ms
            assert elapsed < 0.05
    
    def test_multiple_operations_latency(self):
        """Test that multiple operations complete quickly."""
        with patch('platform.system', return_value='Linux'):
            controller = MediaController()
            backend = Mock(spec=MediaBackend)
            controller._backend = backend
            
            start = time.perf_counter()
            
            # Execute 100 operations
            for _ in range(100):
                controller.play()
                controller.pause()
            
            end = time.perf_counter()
            elapsed = end - start
            
            # 100 operations should complete in <1 second
            assert elapsed < 1.0
            
            # Average per operation should be <10ms
            avg_per_op = elapsed / 200  # 200 total operations
            assert avg_per_op < 0.01


# Error Handling Tests

class TestMediaControllerErrorScenarios:
    """Tests for error handling scenarios."""
    
    def test_backend_import_error_windows(self):
        """Test handling of missing pywin32 on Windows."""
        with patch('platform.system', return_value='Windows'):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'win32api'")):
                with pytest.raises(ImportError, match="pywin32 is required"):
                    WindowsMediaBackend()
    
    def test_applescript_timeout(self):
        """Test handling of AppleScript timeout."""
        backend = MacOSMediaBackend()
        
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('osascript', 5.0)):
            with pytest.raises(MediaCommandError, match="timeout"):
                backend._execute_applescript("test script")
    
    def test_playerctl_failure(self):
        """Test handling of playerctl command failure."""
        with patch.object(LinuxMediaBackend, '_check_playerctl', return_value=True):
            backend = LinuxMediaBackend()
        
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'playerctl')):
            with pytest.raises(MediaCommandError):
                backend._execute_playerctl("play")
    
    def test_xdotool_not_found(self):
        """Test handling of missing xdotool."""
        with patch.object(LinuxMediaBackend, '_check_playerctl', return_value=False):
            backend = LinuxMediaBackend()
        
        with patch('subprocess.run', side_effect=FileNotFoundError("xdotool not found")):
            with pytest.raises(MediaCommandError):
                backend._send_xdotool_key("XF86AudioPlay")


# Fixtures

@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for testing."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout="success",
            stderr="",
            returncode=0
        )
        yield mock_run


@pytest.fixture
def mock_win32api():
    """Mock win32api for testing."""
    with patch('Agent_Guru.platform.controllers.media_control.win32api') as mock_api:
        yield mock_api
