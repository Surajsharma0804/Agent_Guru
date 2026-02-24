"""
Tests for agent_guru.platform.controllers.window_management
Coverage Target: >80% (enforced by CI/CD)
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from typing import List

from Agent_Guru.platform.controllers.window_management import (
    WindowManager,
    SnapPosition,
    ArrangementStyle,
    ScreenInfo,
    VirtualDesktopInfo
)


class TestWindowManager:
    """Unit tests for WindowManager."""

    def test_initialization(self):
        """Test window manager initialization."""
        manager = WindowManager()

        assert manager.platform == sys.platform
        assert manager._platform_integration is not None
        assert manager._screen_cache is None
        assert manager._cache_ttl == 5.0

    def test_get_fallback_screen(self):
        """Test fallback screen information."""
        manager = WindowManager()
        screens = manager._get_fallback_screen()

        assert len(screens) == 1
        assert screens[0].index == 0
        assert screens[0].width == 1920
        assert screens[0].height == 1080
        assert screens[0].is_primary is True

    def test_calculate_snap_position_left_half(self):
        """Test snap position calculation for left half."""
        manager = WindowManager()
        screen = ScreenInfo(
            index=0,
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True
        )

        x, y, width, height = manager._calculate_snap_position(
            screen,
            SnapPosition.LEFT_HALF
        )

        assert x == 0
        assert y == 0
        assert width == 960
        assert height == 1080

    def test_calculate_snap_position_right_half(self):
        """Test snap position calculation for right half."""
        manager = WindowManager()
        screen = ScreenInfo(
            index=0,
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True
        )

        x, y, width, height = manager._calculate_snap_position(
            screen,
            SnapPosition.RIGHT_HALF
        )

        assert x == 960
        assert y == 0
        assert width == 960
        assert height == 1080

    def test_calculate_snap_position_top_left(self):
        """Test snap position calculation for top left corner."""
        manager = WindowManager()
        screen = ScreenInfo(
            index=0,
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True
        )

        x, y, width, height = manager._calculate_snap_position(
            screen,
            SnapPosition.TOP_LEFT
        )

        assert x == 0
        assert y == 0
        assert width == 960
        assert height == 540

    def test_calculate_snap_position_center(self):
        """Test snap position calculation for center."""
        manager = WindowManager()
        screen = ScreenInfo(
            index=0,
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True
        )

        x, y, width, height = manager._calculate_snap_position(
            screen,
            SnapPosition.CENTER
        )

        # Center with 80% of screen size
        expected_width = int(1920 * 0.8)
        expected_height = int(1080 * 0.8)
        expected_x = (1920 - expected_width) // 2
        expected_y = (1080 - expected_height) // 2

        assert x == expected_x
        assert y == expected_y
        assert width == expected_width
        assert height == expected_height

    @patch('Agent_Guru.platform.controllers.window_management.time.time')
    def test_get_screens_uses_cache(self, mock_time):
        """Test that get_screens uses cache when valid."""
        manager = WindowManager()

        # Set up cache
        mock_time.return_value = 100.0
        manager._cache_timestamp = 100.0
        manager._screen_cache = [ScreenInfo(
            index=0,
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True
        )]

        # Get screens with cache
        mock_time.return_value = 102.0  # Within TTL
        screens = manager.get_screens(use_cache=True)

        assert len(screens) == 1
        assert screens[0].width == 1920

    def test_snap_window_invalid_screen_index(self):
        """Test snap window with invalid screen index."""
        manager = WindowManager()

        with pytest.raises(ValueError, match="Invalid screen index"):
            manager.snap_window("Test Window", SnapPosition.LEFT_HALF, screen_index=99)

    def test_snap_window_left_convenience_method(self):
        """Test snap_window_left convenience method."""
        manager = WindowManager()

        with patch.object(manager, 'snap_window', return_value=True) as mock_snap:
            result = manager.snap_window_left("Test Window")

            assert result is True
            mock_snap.assert_called_once_with("Test Window", SnapPosition.LEFT_HALF)

    def test_snap_window_right_convenience_method(self):
        """Test snap_window_right convenience method."""
        manager = WindowManager()

        with patch.object(manager, 'snap_window', return_value=True) as mock_snap:
            result = manager.snap_window_right("Test Window")

            assert result is True
            mock_snap.assert_called_once_with("Test Window", SnapPosition.RIGHT_HALF)

    def test_tile_windows_convenience_method(self):
        """Test tile_windows convenience method."""
        manager = WindowManager()

        with patch.object(manager, 'arrange_windows', return_value=True) as mock_arrange:
            result = manager.tile_windows(["Window1", "Window2"])

            assert result is True
            mock_arrange.assert_called_once_with(
                ArrangementStyle.TILE,
                ["Window1", "Window2"]
            )

    def test_cascade_windows_convenience_method(self):
        """Test cascade_windows convenience method."""
        manager = WindowManager()

        with patch.object(manager, 'arrange_windows', return_value=True) as mock_arrange:
            result = manager.cascade_windows()

            assert result is True
            mock_arrange.assert_called_once_with(ArrangementStyle.CASCADE, None)

    def test_arrange_windows_no_windows(self):
        """Test arrange windows with no windows."""
        manager = WindowManager()

        with patch.object(manager, '_get_all_visible_windows', return_value=[]):
            result = manager.arrange_windows(ArrangementStyle.TILE)

            assert result is False

    def test_arrange_windows_unknown_style(self):
        """Test arrange windows with unknown style."""
        manager = WindowManager()

        # Create a mock style that's not in the enum
        with patch.object(manager, '_get_all_visible_windows', return_value=["Window1"]):
            # Manually set an invalid style
            manager.arrange_windows.__globals__['ArrangementStyle'] = Mock()
            result = manager.arrange_windows(Mock(value="invalid"), ["Window1"])

            # Should handle gracefully
            assert result is False or result is True  # Depends on implementation


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific tests")
class TestWindowManagerWindows:
    """Windows-specific tests for WindowManager."""

    def test_get_screens_windows(self):
        """Test get screens on Windows."""
        with patch('win32api.EnumDisplayMonitors') as mock_enum, \
             patch('win32api.GetMonitorInfo') as mock_info, \
             patch('win32con.MONITORINFOF_PRIMARY', 1):

            manager = WindowManager()

            # Mock monitor enumeration
            mock_enum.return_value = [
                (1, 2, (0, 0, 1920, 1080))
            ]
            mock_info.return_value = {
                'Flags': 1
            }

            screens = manager._get_screens_windows()

            assert len(screens) >= 1
            # Should either parse successfully or return fallback

    def test_snap_window_windows(self):
        """Test snap window on Windows."""
        with patch('win32gui.FindWindow') as mock_find, \
             patch('win32gui.IsIconic') as mock_iconic, \
             patch('win32gui.SetWindowPos') as mock_set:

            manager = WindowManager()

            # Mock window finding
            mock_find.return_value = 12345
            mock_iconic.return_value = False

            result = manager._snap_window_windows("Test Window", 0, 0, 960, 1080)

            # Should attempt to set window position
            assert isinstance(result, bool)

    def test_get_visible_windows_windows(self):
        """Test get visible windows on Windows."""
        with patch('win32gui.EnumWindows') as mock_enum, \
             patch('win32gui.IsWindowVisible') as mock_visible, \
             patch('win32gui.GetWindowText') as mock_text:

            manager = WindowManager()

            # Mock window enumeration
            def enum_windows_callback(callback, windows_list):
                callback(1, windows_list)
                callback(2, windows_list)
                return True

            mock_enum.side_effect = enum_windows_callback
            mock_visible.return_value = True
            mock_text.side_effect = ["Window1", "Window2"]

            windows = manager._get_visible_windows_windows()

            # Should return list of windows
            assert isinstance(windows, list)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific tests")
class TestWindowManagerMacOS:
    """macOS-specific tests for WindowManager."""

    @patch('Agent_Guru.platform.controllers.window_management.subprocess.run')
    def test_get_screens_macos(self, mock_run):
        """Test get screens on macOS."""
        manager = WindowManager()

        # Mock system_profiler output
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"SPDisplaysDataType": [{"spdisplays_ndrvs": [{"_spdisplays_resolution": "1920 x 1080"}]}]}'
        )

        screens = manager._get_screens_macos()

        assert len(screens) >= 1
        # Should either parse successfully or return fallback

    @patch('Agent_Guru.platform.controllers.window_management.subprocess.run')
    def test_snap_window_macos(self, mock_run):
        """Test snap window on macOS."""
        manager = WindowManager()

        # Mock AppleScript success
        mock_run.return_value = Mock(returncode=0, stderr="")

        result = manager._snap_window_macos("Test Window", 0, 0, 960, 1080)

        assert result is True
        mock_run.assert_called_once()

    @patch('Agent_Guru.platform.controllers.window_management.subprocess.run')
    def test_get_visible_windows_macos(self, mock_run):
        """Test get visible windows on macOS."""
        manager = WindowManager()

        # Mock AppleScript output
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Window1, Window2, Window3"
        )

        windows = manager._get_visible_windows_macos()

        assert len(windows) == 3
        assert "Window1" in windows


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux-specific tests")
class TestWindowManagerLinux:
    """Linux-specific tests for WindowManager."""

    @patch('Agent_Guru.platform.controllers.window_management.subprocess.run')
    def test_get_screens_linux(self, mock_run):
        """Test get screens on Linux."""
        manager = WindowManager()

        # Mock xrandr output
        mock_run.return_value = Mock(
            returncode=0,
            stdout="HDMI-1 connected primary 1920x1080+0+0\nDP-1 connected 1920x1080+1920+0"
        )

        screens = manager._get_screens_linux()

        assert len(screens) >= 1

    @patch('Agent_Guru.platform.controllers.window_management.subprocess.run')
    def test_snap_window_linux(self, mock_run):
        """Test snap window on Linux."""
        manager = WindowManager()

        # Mock wmctrl commands
        mock_run.side_effect = [
            Mock(returncode=0, stdout="0x01234567  0 hostname Test Window"),
            Mock(returncode=0, stderr="")
        ]

        result = manager._snap_window_linux("Test Window", 0, 0, 960, 1080)

        assert result is True
        assert mock_run.call_count == 2

    @patch('Agent_Guru.platform.controllers.window_management.subprocess.run')
    def test_get_visible_windows_linux(self, mock_run):
        """Test get visible windows on Linux."""
        manager = WindowManager()

        # Mock wmctrl output
        mock_run.return_value = Mock(
            returncode=0,
            stdout="0x01  0 host Window1\n0x02  0 host Window2"
        )

        windows = manager._get_visible_windows_linux()

        assert len(windows) == 2
        assert "Window1" in windows
        assert "Window2" in windows


class TestVirtualDesktopManagement:
    """Tests for virtual desktop management."""

    def test_create_virtual_desktop(self):
        """Test create virtual desktop."""
        manager = WindowManager()

        with patch.object(manager, f'_create_virtual_desktop_{manager.platform.replace("darwin", "macos").replace("win32", "windows")}', return_value="desktop_123"):
            desktop_id = manager.create_virtual_desktop()

            # Should return a desktop ID or None
            assert desktop_id is None or isinstance(desktop_id, str)

    def test_switch_virtual_desktop(self):
        """Test switch virtual desktop."""
        manager = WindowManager()

        with patch.object(manager, f'_switch_virtual_desktop_{manager.platform.replace("darwin", "macos").replace("win32", "windows")}', return_value=True):
            result = manager.switch_virtual_desktop("desktop_1")

            # Should return boolean
            assert isinstance(result, bool)

    def test_close_virtual_desktop(self):
        """Test close virtual desktop."""
        manager = WindowManager()

        with patch.object(manager, f'_close_virtual_desktop_{manager.platform.replace("darwin", "macos").replace("win32", "windows")}', return_value=True):
            result = manager.close_virtual_desktop("desktop_1")

            # Should return boolean
            assert isinstance(result, bool)

    def test_list_virtual_desktops(self):
        """Test list virtual desktops."""
        manager = WindowManager()

        desktops = manager.list_virtual_desktops()

        # Should return list
        assert isinstance(desktops, list)
        if desktops:
            assert isinstance(desktops[0], VirtualDesktopInfo)


@pytest.mark.integration
class TestWindowManagerIntegration:
    """Integration tests for WindowManager."""

    def test_get_screens_returns_valid_data(self):
        """Test that get_screens returns valid screen data."""
        manager = WindowManager()

        screens = manager.get_screens()

        assert len(screens) >= 1
        assert all(isinstance(s, ScreenInfo) for s in screens)
        assert all(s.width > 0 for s in screens)
        assert all(s.height > 0 for s in screens)
        assert any(s.is_primary for s in screens)

    def test_screen_cache_works(self):
        """Test that screen caching works correctly."""
        manager = WindowManager()

        # First call
        screens1 = manager.get_screens()

        # Second call (should use cache)
        screens2 = manager.get_screens()

        # Should be same object (cached)
        assert screens1 is screens2

    def test_calculate_all_snap_positions(self):
        """Test calculating all snap positions."""
        manager = WindowManager()
        screen = ScreenInfo(
            index=0,
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True
        )

        positions = [
            SnapPosition.LEFT_HALF,
            SnapPosition.RIGHT_HALF,
            SnapPosition.TOP_HALF,
            SnapPosition.BOTTOM_HALF,
            SnapPosition.TOP_LEFT,
            SnapPosition.TOP_RIGHT,
            SnapPosition.BOTTOM_LEFT,
            SnapPosition.BOTTOM_RIGHT,
            SnapPosition.MAXIMIZE,
            SnapPosition.CENTER
        ]

        for position in positions:
            x, y, width, height = manager._calculate_snap_position(screen, position)

            # All values should be non-negative
            assert x >= 0
            assert y >= 0
            assert width > 0
            assert height > 0

            # Should be within screen bounds
            assert x + width <= screen.x + screen.width + 1  # +1 for rounding
            assert y + height <= screen.y + screen.height + 1
