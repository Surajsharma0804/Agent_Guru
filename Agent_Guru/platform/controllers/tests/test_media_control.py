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

class TestWindowsMediaBackend:
    """Unit tests for Windows media backend."""
    
    @pytest.fixture
    def backend(self):
        """Create Windows media backend with mocked dependencies."""
        if platform.system() == "Windows":
            try:
                return WindowsMediaBackend()
            except ImportError:
                pass
        
        # Mock for non-Windows platforms
        with patch('Agent_Guru.platform.controllers.media_control.win32api') as mock_api:
            with patch('Agent_Guru.platform.controllers.media_control.win32con') as mock_con:
                backend = object.__new__(WindowsMediaBackend)
                backend.win32api = mock_api
                backend.win32con = mock_con
                backend.win32con.KEYEVENTF_KEYUP = 2
                return backend
    
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
    
    def test_play_pause_toggle_sends_key(self, backend):
        """Test that play/pause toggle sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.play_pause_toggle()
            mock_send.assert_called_once_with(0xB3)
    
    def test_stop_sends_key(self, backend):
        """Test that stop sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.stop()
            mock_send.assert_called_once_with(0xB2)
    
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
    
    def test_volume_up_sends_keys(self, backend):
        """Test that volume up sends correct media keys."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.volume_up(10)
            # Should send 5 key presses (10 / 2)
            assert mock_send.call_count == 5
            mock_send.assert_called_with(0xAF)
    
    def test_volume_down_sends_keys(self, backend):
        """Test that volume down sends correct media keys."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.volume_down(10)
            # Should send 5 key presses (10 / 2)
            assert mock_send.call_count == 5
            mock_send.assert_called_with(0xAE)
    
    def test_volume_invalid_amount(self, backend):
        """Test that invalid volume amount raises error."""
        with pytest.raises(MediaCommandError):
            backend.volume_up(150)
        
        with pytest.raises(MediaCommandError):
            backend.volume_down(-10)
    
    def test_mute_sends_key(self, backend):
        """Test that mute sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.mute()
            mock_send.assert_called_once_with(0xAD)
    
    def test_unmute_sends_key(self, backend):
        """Test that unmute sends correct media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.unmute()
            mock_send.assert_called_once_with(0xAD)
    
    def test_get_state_returns_none(self, backend):
        """Test that Windows backend returns None for state."""
        state = backend.get_state()
        assert state is None
    
    def test_send_media_key_success(self, backend):
        """Test successful media key sending."""
        # Mock the keybd_event method
        backend.win32api.keybd_event = Mock()
        backend._send_media_key(0xB3)
        backend.win32api.keybd_event.assert_called()
    
    def test_send_media_key_failure(self, backend):
        """Test media key sending failure."""
        # Mock the keybd_event method to raise exception
        backend.win32api.keybd_event = Mock(side_effect=Exception("Key send failed"))
        
        with pytest.raises(MediaCommandError, match="Failed to send media key"):
            backend._send_media_key(0xB3)


# macOS Backend Tests

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
    
    def test_play_fallback_to_media_key(self, backend):
        """Test that play falls back to media key on error."""
        with patch.object(backend, '_execute_applescript', side_effect=MediaCommandError("Test")):
            with patch.object(backend, '_send_media_key') as mock_send:
                backend.play()
                mock_send.assert_called_once_with(16)
    
    def test_pause_executes_applescript(self, backend):
        """Test that pause executes AppleScript."""
        with patch.object(backend, '_execute_applescript') as mock_exec:
            backend.pause()
            assert mock_exec.called
    
    def test_pause_fallback_to_media_key(self, backend):
        """Test that pause falls back to media key on error."""
        with patch.object(backend, '_execute_applescript', side_effect=MediaCommandError("Test")):
            with patch.object(backend, '_send_media_key') as mock_send:
                backend.pause()
                mock_send.assert_called_once_with(16)
    
    def test_play_pause_toggle_sends_key(self, backend):
        """Test that play/pause toggle sends media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.play_pause_toggle()
            mock_send.assert_called_once_with(16)
    
    def test_stop_executes_applescript(self, backend):
        """Test that stop executes AppleScript."""
        with patch.object(backend, '_execute_applescript') as mock_exec:
            backend.stop()
            assert mock_exec.called
    
    def test_stop_handles_error(self, backend):
        """Test that stop handles errors gracefully."""
        with patch.object(backend, '_execute_applescript', side_effect=MediaCommandError("Test")):
            # Should not raise, just log warning
            backend.stop()
    
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
    
    def test_volume_up_sends_keys(self, backend):
        """Test that volume up sends correct media keys."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.volume_up(12)
            # Should send 2 key presses (12 / 6)
            assert mock_send.call_count == 2
            mock_send.assert_called_with(72)
    
    def test_volume_down_sends_keys(self, backend):
        """Test that volume down sends correct media keys."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.volume_down(12)
            # Should send 2 key presses (12 / 6)
            assert mock_send.call_count == 2
            mock_send.assert_called_with(73)
    
    def test_volume_invalid_amount(self, backend):
        """Test that invalid volume amount raises error."""
        with pytest.raises(MediaCommandError):
            backend.volume_up(150)
        
        with pytest.raises(MediaCommandError):
            backend.volume_down(-10)
    
    def test_mute_sends_key(self, backend):
        """Test that mute sends media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.mute()
            mock_send.assert_called_once_with(74)
    
    def test_unmute_sends_key(self, backend):
        """Test that unmute sends media key."""
        with patch.object(backend, '_send_media_key') as mock_send:
            backend.unmute()
            mock_send.assert_called_once_with(74)
    
    def test_get_state_with_music_running(self, backend):
        """Test get state when Music app is running."""
        with patch.object(backend, '_execute_applescript', return_value="true|75|Test Song|Test Artist"):
            state = backend.get_state()
            
            assert state is not None
            assert state.is_playing is True
            assert state.volume == 75
            assert state.track_title == "Test Song"
            assert state.artist == "Test Artist"
    
    def test_get_state_music_not_running(self, backend):
        """Test get state when Music app is not running."""
        with patch.object(backend, '_execute_applescript', return_value=""):
            state = backend.get_state()
            assert state is None
    
    def test_get_state_error(self, backend):
        """Test get state when error occurs."""
        with patch.object(backend, '_execute_applescript', side_effect=Exception("Test error")):
            state = backend.get_state()
            assert state is None
    
    def test_execute_applescript_success(self, backend):
        """Test successful AppleScript execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(stdout="success", stderr="", returncode=0)
            result = backend._execute_applescript("test script")
            assert result == "success"
    
    def test_execute_applescript_failure(self, backend):
        """Test AppleScript execution failure."""
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'osascript', stderr="error")):
            with pytest.raises(MediaCommandError, match="AppleScript execution failed"):
                backend._execute_applescript("test script")
    
    def test_execute_applescript_timeout(self, backend):
        """Test AppleScript execution timeout."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('osascript', 5.0)):
            with pytest.raises(MediaCommandError, match="timeout"):
                backend._execute_applescript("test script")
    
    def test_send_media_key(self, backend):
        """Test sending media key via System Events."""
        with patch.object(backend, '_execute_applescript') as mock_exec:
            backend._send_media_key(16)
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert "System Events" in call_args
            assert "key code 16" in call_args


# Linux Backend Tests

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
    
    def test_check_playerctl_available(self):
        """Test playerctl availability check when installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            backend = LinuxMediaBackend()
            assert backend.use_playerctl is True
    
    def test_check_playerctl_not_available(self):
        """Test playerctl availability check when not installed."""
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            backend = LinuxMediaBackend()
            assert backend.use_playerctl is False
    
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
    
    def test_pause_with_playerctl(self, backend_with_playerctl):
        """Test pause with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.pause()
            mock_exec.assert_called_once_with("pause")
    
    def test_pause_without_playerctl(self, backend_without_playerctl):
        """Test pause without playerctl."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.pause()
            mock_send.assert_called_once_with("XF86AudioPause")
    
    def test_play_pause_toggle_with_playerctl(self, backend_with_playerctl):
        """Test play/pause toggle with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.play_pause_toggle()
            mock_exec.assert_called_once_with("play-pause")
    
    def test_play_pause_toggle_without_playerctl(self, backend_without_playerctl):
        """Test play/pause toggle without playerctl."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.play_pause_toggle()
            mock_send.assert_called_once_with("XF86AudioPlay")
    
    def test_stop_with_playerctl(self, backend_with_playerctl):
        """Test stop with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.stop()
            mock_exec.assert_called_once_with("stop")
    
    def test_stop_without_playerctl(self, backend_without_playerctl):
        """Test stop without playerctl."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.stop()
            mock_send.assert_called_once_with("XF86AudioStop")
    
    def test_next_track_with_playerctl(self, backend_with_playerctl):
        """Test next track with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.next_track()
            mock_exec.assert_called_once_with("next")
    
    def test_next_track_without_playerctl(self, backend_without_playerctl):
        """Test next track without playerctl."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.next_track()
            mock_send.assert_called_once_with("XF86AudioNext")
    
    def test_previous_track_with_playerctl(self, backend_with_playerctl):
        """Test previous track with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.previous_track()
            mock_exec.assert_called_once_with("previous")
    
    def test_previous_track_without_playerctl(self, backend_without_playerctl):
        """Test previous track without playerctl."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.previous_track()
            mock_send.assert_called_once_with("XF86AudioPrev")
    
    def test_volume_up_with_playerctl(self, backend_with_playerctl):
        """Test volume up with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.volume_up(10)
            mock_exec.assert_called_once_with("volume 0.1+")
    
    def test_volume_up_without_playerctl(self, backend_without_playerctl):
        """Test volume up without playerctl."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.volume_up(10)
            # Should send 2 key presses (10 / 5)
            assert mock_send.call_count == 2
            mock_send.assert_called_with("XF86AudioRaiseVolume")
    
    def test_volume_down_with_playerctl(self, backend_with_playerctl):
        """Test volume down with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            backend_with_playerctl.volume_down(10)
            mock_exec.assert_called_once_with("volume 0.1-")
    
    def test_volume_down_without_playerctl(self, backend_without_playerctl):
        """Test volume down without playerctl."""
        with patch.object(backend_without_playerctl, '_send_xdotool_key') as mock_send:
            backend_without_playerctl.volume_down(10)
            # Should send 2 key presses (10 / 5)
            assert mock_send.call_count == 2
            mock_send.assert_called_with("XF86AudioLowerVolume")
    
    def test_volume_invalid_amount(self, backend_with_playerctl):
        """Test that invalid volume amount raises error."""
        with pytest.raises(MediaCommandError):
            backend_with_playerctl.volume_up(150)
        
        with pytest.raises(MediaCommandError):
            backend_with_playerctl.volume_down(-10)
    
    def test_mute(self, backend_with_playerctl):
        """Test mute."""
        with patch.object(backend_with_playerctl, '_send_xdotool_key') as mock_send:
            backend_with_playerctl.mute()
            mock_send.assert_called_once_with("XF86AudioMute")
    
    def test_unmute(self, backend_with_playerctl):
        """Test unmute."""
        with patch.object(backend_with_playerctl, '_send_xdotool_key') as mock_send:
            backend_with_playerctl.unmute()
            mock_send.assert_called_once_with("XF86AudioMute")
    
    def test_get_state_with_playerctl(self, backend_with_playerctl):
        """Test get state with playerctl."""
        with patch.object(backend_with_playerctl, '_execute_playerctl') as mock_exec:
            mock_exec.side_effect = ["playing", "0.75", "Test Song", "Test Artist"]
            
            state = backend_with_playerctl.get_state()
            
            assert state is not None
            assert state.is_playing is True
            assert state.volume == 75
            assert state.track_title == "Test Song"
            assert state.artist == "Test Artist"
    
    def test_get_state_without_playerctl(self, backend_without_playerctl):
        """Test get state without playerctl."""
        state = backend_without_playerctl.get_state()
        assert state is None
    
    def test_get_state_error(self, backend_with_playerctl):
        """Test get state when error occurs."""
        with patch.object(backend_with_playerctl, '_execute_playerctl', side_effect=Exception("Test error")):
            state = backend_with_playerctl.get_state()
            assert state is None
    
    def test_execute_playerctl_success(self, backend_with_playerctl):
        """Test successful playerctl execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(stdout="success", stderr="", returncode=0)
            result = backend_with_playerctl._execute_playerctl("play")
            assert result == "success"
    
    def test_execute_playerctl_failure(self, backend_with_playerctl):
        """Test playerctl execution failure."""
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'playerctl', stderr="error")):
            with pytest.raises(MediaCommandError):
                backend_with_playerctl._execute_playerctl("play")
    
    def test_execute_playerctl_timeout(self, backend_with_playerctl):
        """Test playerctl execution timeout."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('playerctl', 5.0)):
            with pytest.raises(MediaCommandError, match="timeout"):
                backend_with_playerctl._execute_playerctl("play")
    
    def test_send_xdotool_key_success(self, backend_without_playerctl):
        """Test successful xdotool key sending."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            backend_without_playerctl._send_xdotool_key("XF86AudioPlay")
            mock_run.assert_called_once()
    
    def test_send_xdotool_key_failure(self, backend_without_playerctl):
        """Test xdotool key sending failure."""
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'xdotool')):
            with pytest.raises(MediaCommandError):
                backend_without_playerctl._send_xdotool_key("XF86AudioPlay")
    
    def test_send_xdotool_key_not_found(self, backend_without_playerctl):
        """Test xdotool not found."""
        with patch('subprocess.run', side_effect=FileNotFoundError("xdotool not found")):
            with pytest.raises(MediaCommandError):
                backend_without_playerctl._send_xdotool_key("XF86AudioPlay")


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
    
    def test_controller_creation_on_supported_platform(self):
        """Test that controller can be created on supported platforms."""
        # This may fail if platform-specific dependencies are missing
        try:
            controller = MediaController()
            assert controller is not None
            assert controller._backend is not None
        except ImportError as e:
            pytest.skip(f"Platform dependencies not available: {e}")
    
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
    
    @pytest.mark.slow
    def test_open_youtube_and_play(self):
        """Test opening YouTube and playing a video (real integration test)."""
        try:
            import webbrowser
            
            controller = MediaController()
            
            # Open YouTube in default browser
            youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            webbrowser.open(youtube_url)
            
            # Wait for browser to open
            time.sleep(3)
            
            # Try to control playback
            # Note: This may not work if browser doesn't support media keys
            try:
                controller.play()
                time.sleep(1)
                controller.pause()
                time.sleep(1)
                controller.play()
            except MediaCommandError:
                # Expected if media keys don't work with browser
                pass
            
        except ImportError as e:
            pytest.skip(f"Platform dependencies not available: {e}")
    
    @pytest.mark.slow
    def test_media_player_integration(self):
        """Test integration with system media player."""
        try:
            controller = MediaController()
            
            # Try to get current media state
            state = controller.get_state()
            
            # If state is available, test operations
            if state is not None:
                # Test play/pause
                controller.play()
                time.sleep(0.5)
                controller.pause()
                
                # Test volume control
                controller.volume_up(5)
                time.sleep(0.2)
                controller.volume_down(5)
                
                # Test track navigation
                controller.next_track()
                time.sleep(0.2)
                controller.previous_track()
            else:
                # No media player running, skip detailed tests
                pytest.skip("No media player running")
                
        except ImportError as e:
            pytest.skip(f"Platform dependencies not available: {e}")
    
    @pytest.mark.slow
    def test_spotify_integration(self):
        """Test integration with Spotify if available."""
        try:
            controller = MediaController()
            
            # Check if Spotify is running by trying to get state
            state = controller.get_state()
            
            if state and state.track_title:
                # Spotify is running, test controls
                original_playing = state.is_playing
                
                # Test play/pause toggle
                controller.play_pause_toggle()
                time.sleep(0.5)
                
                # Toggle back to original state
                controller.play_pause_toggle()
                time.sleep(0.5)
                
                # Test track navigation
                controller.next_track()
                time.sleep(1)
                
                # Get new state
                new_state = controller.get_state()
                assert new_state is not None
            else:
                pytest.skip("Spotify not running")
                
        except ImportError as e:
            pytest.skip(f"Platform dependencies not available: {e}")
    
    @pytest.mark.slow
    def test_continuous_playback_control(self):
        """Test continuous playback control over multiple operations."""
        try:
            controller = MediaController()
            
            # Sequence of operations
            operations = [
                ("play", controller.play),
                ("pause", controller.pause),
                ("play", controller.play),
                ("next", controller.next_track),
                ("previous", controller.previous_track),
                ("volume_up", lambda: controller.volume_up(10)),
                ("volume_down", lambda: controller.volume_down(10)),
                ("mute", controller.mute),
                ("unmute", controller.unmute),
            ]
            
            for name, operation in operations:
                try:
                    operation()
                    time.sleep(0.2)  # Small delay between operations
                except MediaCommandError as e:
                    # Log but don't fail - some operations may not work
                    print(f"Operation {name} failed: {e}")
            
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
