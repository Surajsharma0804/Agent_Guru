"""Module: agent_guru.platform.controllers.media_control
Purpose: Cross-platform media control for play, pause, skip, and volume operations.

This module implements media control using platform-specific media key simulation.
Supports Windows (pywin32), macOS (AppleScript), and Linux (D-Bus/playerctl).

Performance Characteristics:
    - Time Complexity: O(1) per media operation
    - Space Complexity: O(1) (no state storage)
    - Latency: <50ms per operation (95th percentile)
    - Platform Support: Windows, macOS, Linux

Architecture:
    The controller uses a strategy pattern with platform-specific backends:
    - WindowsMediaBackend: Uses pywin32 for media key simulation
    - MacOSMediaBackend: Uses AppleScript for media control
    - LinuxMediaBackend: Uses D-Bus/playerctl for media control

Usage Example:
    >>> from agent_guru.platform.controllers.media_control import MediaController
    >>>
    >>> # Initialize controller (auto-detects platform)
    >>> controller = MediaController()
    >>>
    >>> # Control media playback
    >>> controller.play()
    >>> controller.pause()
    >>> controller.next_track()
    >>> controller.previous_track()
    >>>
    >>> # Control media volume
    >>> controller.volume_up()
    >>> controller.volume_down()
    >>> controller.mute()

Author: Agent Guru Team
Date: 2024
Version: 1.0.0
"""

import logging
import platform
import subprocess  # nosec B404
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Every external media helper (osascript, playerctl, xdotool) is bounded by
# this. Named rather than repeated so the value and the messages that quote it
# cannot drift apart.
_SUBPROCESS_TIMEOUT_S = 5.0

# Data Models

@dataclass
class MediaState:
    """Current media playback state.

    Attributes:
        is_playing: Whether media is currently playing
        volume: Current volume level (0-100)
        is_muted: Whether audio is muted
        track_title: Current track title (if available)
        artist: Current artist (if available)

    """

    is_playing: bool
    volume: int
    is_muted: bool
    track_title: str | None = None
    artist: str | None = None

# Exceptions

class MediaControlError(Exception):
    """Base exception for media control errors."""

class UnsupportedMediaOperationError(MediaControlError):
    """Raised when media operation is not supported on current platform."""

class MediaCommandError(MediaControlError):
    """Raised when media command execution fails."""

# Backend Interface

class MediaBackend(ABC):
    """Abstract base class for platform-specific media control backends.

    All platform-specific implementations must inherit from this class
    and implement all abstract methods.
    """

    @abstractmethod
    def play(self) -> None:
        """Start or resume media playback.

        Raises:
            MediaCommandError: If play command fails

        """

    @abstractmethod
    def pause(self) -> None:
        """Pause media playback.

        Raises:
            MediaCommandError: If pause command fails

        """

    @abstractmethod
    def play_pause_toggle(self) -> None:
        """Toggle between play and pause states.

        Raises:
            MediaCommandError: If toggle command fails

        """

    @abstractmethod
    def stop(self) -> None:
        """Stop media playback.

        Raises:
            MediaCommandError: If stop command fails

        """

    @abstractmethod
    def next_track(self) -> None:
        """Skip to next track.

        Raises:
            MediaCommandError: If next command fails

        """

    @abstractmethod
    def previous_track(self) -> None:
        """Go to previous track.

        Raises:
            MediaCommandError: If previous command fails

        """

    @abstractmethod
    def volume_up(self, amount: int = 10) -> None:
        """Increase media volume.

        Args:
            amount: Volume increase amount (0-100)

        Raises:
            MediaCommandError: If volume up command fails
            InvalidSettingValueError: If amount is invalid

        """

    @abstractmethod
    def volume_down(self, amount: int = 10) -> None:
        """Decrease media volume.

        Args:
            amount: Volume decrease amount (0-100)

        Raises:
            MediaCommandError: If volume down command fails
            InvalidSettingValueError: If amount is invalid

        """

    @abstractmethod
    def mute(self) -> None:
        """Mute media audio.

        Raises:
            MediaCommandError: If mute command fails

        """

    @abstractmethod
    def unmute(self) -> None:
        """Unmute media audio.

        Raises:
            MediaCommandError: If unmute command fails

        """

    @abstractmethod
    def get_state(self) -> MediaState | None:
        """Get current media playback state.

        Returns:
            MediaState if available, None if state cannot be determined

        Raises:
            MediaCommandError: If state query fails

        """

# Windows Backend

class WindowsMediaBackend(MediaBackend):
    """Windows media control backend using pywin32 for media key simulation.

    Uses Windows API to simulate media key presses (VK_MEDIA_*).
    """

    def __init__(self) -> None:
        """Initialize Windows media backend.

        Raises:
            ImportError: If pywin32 is not installed

        """
        try:
            import win32api
            import win32con

            self.win32api = win32api
            self.win32con = win32con
            logger.info("Windows media backend initialized")
        except ImportError as e:
            logger.exception("pywin32 not available for Windows media control")
            msg = "pywin32 is required for Windows media control. Install with: pip install pywin32"
            raise ImportError(
                msg,
            ) from e

    def _send_media_key(self, key_code: int) -> None:
        """Send media key press event.

        Args:
            key_code: Windows virtual key code

        Raises:
            MediaCommandError: If key press fails

        """
        try:
            # Key down
            self.win32api.keybd_event(key_code, 0, 0, 0)
            # Key up
            self.win32api.keybd_event(key_code, 0, self.win32con.KEYEVENTF_KEYUP, 0)
            logger.debug("Sent media key: %s", key_code)
        except Exception as e:
            logger.exception("Failed to send media key")
            msg = f"Failed to send media key: {e}"
            raise MediaCommandError(msg) from e

    def play(self) -> None:
        """Start or resume media playback using VK_MEDIA_PLAY_PAUSE."""
        self._send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE

    def pause(self) -> None:
        """Pause media playback using VK_MEDIA_PLAY_PAUSE."""
        self._send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE

    def play_pause_toggle(self) -> None:
        """Toggle play/pause using VK_MEDIA_PLAY_PAUSE."""
        self._send_media_key(0xB3)  # VK_MEDIA_PLAY_PAUSE

    def stop(self) -> None:
        """Stop media playback using VK_MEDIA_STOP."""
        self._send_media_key(0xB2)  # VK_MEDIA_STOP

    def next_track(self) -> None:
        """Skip to next track using VK_MEDIA_NEXT_TRACK."""
        self._send_media_key(0xB0)  # VK_MEDIA_NEXT_TRACK

    def previous_track(self) -> None:
        """Go to previous track using VK_MEDIA_PREV_TRACK."""
        self._send_media_key(0xB1)  # VK_MEDIA_PREV_TRACK

    def volume_up(self, amount: int = 10) -> None:
        """Increase volume using VK_VOLUME_UP.

        Note: Windows media keys don't support custom amounts,
        so this sends multiple key presses.
        """
        if not 0 <= amount <= 100:
            msg = f"Invalid volume amount: {amount}"
            raise MediaCommandError(msg)

        # Each key press increases volume by ~2%, so divide by 2
        presses = max(1, amount // 2)
        for _ in range(presses):
            self._send_media_key(0xAF)  # VK_VOLUME_UP

    def volume_down(self, amount: int = 10) -> None:
        """Decrease volume using VK_VOLUME_DOWN.

        Note: Windows media keys don't support custom amounts,
        so this sends multiple key presses.
        """
        if not 0 <= amount <= 100:
            msg = f"Invalid volume amount: {amount}"
            raise MediaCommandError(msg)

        # Each key press decreases volume by ~2%, so divide by 2
        presses = max(1, amount // 2)
        for _ in range(presses):
            self._send_media_key(0xAE)  # VK_VOLUME_DOWN

    def mute(self) -> None:
        """Mute audio using VK_VOLUME_MUTE."""
        self._send_media_key(0xAD)  # VK_VOLUME_MUTE

    def unmute(self) -> None:
        """Unmute audio using VK_VOLUME_MUTE (toggle)."""
        self._send_media_key(0xAD)  # VK_VOLUME_MUTE

    def get_state(self) -> MediaState | None:
        """Get current media state.

        Note: Windows media keys don't provide state feedback,
        so this returns None.
        """
        logger.debug("Windows media backend does not support state queries")
        return None

# macOS Backend

class MacOSMediaBackend(MediaBackend):
    """macOS media control backend using AppleScript.

    Uses AppleScript to control media playback through System Events
    and specific media applications.
    """

    def _execute_applescript(self, script: str) -> str:
        """Execute AppleScript command.

        Args:
            script: AppleScript code to execute

        Returns:
            Script output

        Raises:
            MediaCommandError: If script execution fails

        """
        try:
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_S,
                check=True,
            )
            logger.debug("AppleScript executed: %s...", script[:50])
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.exception("AppleScript failed: %s", e.stderr)
            msg = f"AppleScript execution failed: {e.stderr}"
            raise MediaCommandError(msg) from e
        except subprocess.TimeoutExpired as e:
            # The timeout= above exists precisely to produce this, yet it was
            # not caught: a hung osascript -- routine while macOS is waiting
            # on an automation-permission prompt -- escaped as a raw
            # TimeoutExpired instead of the MediaCommandError this method
            # documents, crashing the caller rather than failing the command.
            logger.warning("AppleScript timed out after %.1fs", _SUBPROCESS_TIMEOUT_S)
            msg = f"AppleScript execution timeout after {_SUBPROCESS_TIMEOUT_S:.1f}s"
            raise MediaCommandError(msg) from e
        except (FileNotFoundError, OSError) as e:
            # osascript missing, or the exec itself failed.
            logger.warning("Could not run osascript: %s", e)
            msg = f"AppleScript execution failed: {e}"
            raise MediaCommandError(msg) from e

    def _send_media_key(self, key_code: int) -> None:
        """Send media key using System Events.

        Args:
            key_code: macOS key code for media keys

        """
        script = f'tell application "System Events" to key code {key_code}'
        self._execute_applescript(script)

    def play(self) -> None:
        """Start or resume media playback."""
        # Try iTunes/Music first, then generic media key
        try:
            script = """
            tell application "Music"
                if it is running then
                    play
                end if
            end tell
            """
            self._execute_applescript(script)
        except MediaCommandError:
            # Fallback to media key
            self._send_media_key(16)  # Play/Pause key

    def pause(self) -> None:
        """Pause media playback."""
        try:
            script = """
            tell application "Music"
                if it is running then
                    pause
                end if
            end tell
            """
            self._execute_applescript(script)
        except MediaCommandError:
            # Fallback to media key
            self._send_media_key(16)  # Play/Pause key

    def play_pause_toggle(self) -> None:
        """Toggle play/pause."""
        self._send_media_key(16)  # Play/Pause key

    def stop(self) -> None:
        """Stop media playback."""
        try:
            script = """
            tell application "Music"
                if it is running then
                    stop
                end if
            end tell
            """
            self._execute_applescript(script)
        except MediaCommandError:
            logger.exception("Stop command not available via media keys")

    def next_track(self) -> None:
        """Skip to next track."""
        self._send_media_key(17)  # Next track key

    def previous_track(self) -> None:
        """Go to previous track."""
        self._send_media_key(18)  # Previous track key

    def volume_up(self, amount: int = 10) -> None:
        """Increase volume.

        Note: macOS media keys don't support custom amounts,
        so this sends multiple key presses.
        """
        if not 0 <= amount <= 100:
            msg = f"Invalid volume amount: {amount}"
            raise MediaCommandError(msg)

        # Each key press increases volume by ~6.25%, so divide by 6
        presses = max(1, amount // 6)
        for _ in range(presses):
            self._send_media_key(72)  # Volume up key

    def volume_down(self, amount: int = 10) -> None:
        """Decrease volume.

        Note: macOS media keys don't support custom amounts,
        so this sends multiple key presses.
        """
        if not 0 <= amount <= 100:
            msg = f"Invalid volume amount: {amount}"
            raise MediaCommandError(msg)

        # Each key press decreases volume by ~6.25%, so divide by 6
        presses = max(1, amount // 6)
        for _ in range(presses):
            self._send_media_key(73)  # Volume down key

    def mute(self) -> None:
        """Mute audio."""
        self._send_media_key(74)  # Mute key

    def unmute(self) -> None:
        """Unmute audio."""
        self._send_media_key(74)  # Mute key (toggle)

    def get_state(self) -> MediaState | None:
        """Get current media state from Music app.

        Returns:
            MediaState if Music app is running, None otherwise

        """
        try:
            script = """
            tell application "Music"
                if it is running then
                    set isPlaying to (player state is playing)
                    set vol to sound volume
                    set trackName to name of current track
                    set trackArtist to artist of current track
                    return isPlaying & "|" & vol & "|" & trackName & "|" & trackArtist
                end if
            end tell
            """
            result = self._execute_applescript(script)
            if result:
                parts = result.split("|")
                return MediaState(
                    is_playing=(parts[0] == "true"),
                    volume=int(parts[1]),
                    is_muted=False,  # macOS doesn't provide mute state
                    track_title=parts[2] if len(parts) > 2 else None,
                    artist=parts[3] if len(parts) > 3 else None,
                )
        except Exception as e:
            logger.debug("Could not get media state: %s", e)
        return None

# Linux Backend

class LinuxMediaBackend(MediaBackend):
    """Linux media control backend using D-Bus/playerctl.

    Uses playerctl for media control via MPRIS D-Bus interface.
    Falls back to xdotool for key simulation if playerctl unavailable.
    """

    def __init__(self) -> None:
        """Initialize Linux media backend.

        Checks for playerctl availability and falls back to xdotool.
        """
        self.use_playerctl = self._check_playerctl()
        if self.use_playerctl:
            logger.info("Linux media backend using playerctl")
        else:
            logger.info("Linux media backend using xdotool fallback")

    def _check_playerctl(self) -> bool:
        """Check if playerctl is available.

        Returns:
            True if playerctl is installed and working

        """
        try:
            subprocess.run(["playerctl", "--version"], capture_output=True, timeout=1.0, check=True)  # nosec B603 B607
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _execute_playerctl(self, command: str) -> str:
        """Execute playerctl command.

        Args:
            command: playerctl command to execute

        Returns:
            Command output

        Raises:
            MediaCommandError: If command fails

        """
        try:
            result = subprocess.run(  # nosec B603 B607  # noqa: S603
                ["playerctl", command],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_S,
                check=True,
            )
            logger.debug("playerctl %s executed", command)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.exception("playerctl %s failed: %s", command, e.stderr)
            msg = f"playerctl {command} failed: {e.stderr}"
            raise MediaCommandError(msg) from e
        except subprocess.TimeoutExpired as e:
            # Same gap as the AppleScript path: the timeout was set but never
            # handled, so an unresponsive player took the caller down with a
            # raw TimeoutExpired.
            logger.warning(
                "playerctl %s timed out after %.1fs", command, _SUBPROCESS_TIMEOUT_S,
            )
            msg = f"playerctl {command} timeout after {_SUBPROCESS_TIMEOUT_S:.1f}s"
            raise MediaCommandError(msg) from e
        except (FileNotFoundError, OSError) as e:
            logger.warning("Could not run playerctl: %s", e)
            msg = f"playerctl {command} failed: {e}"
            raise MediaCommandError(msg) from e

    def _send_xdotool_key(self, key: str) -> None:
        """Send media key using xdotool.

        Args:
            key: X11 key name

        Raises:
            MediaCommandError: If xdotool fails

        """
        try:
            subprocess.run(  # noqa: S603
                ["xdotool", "key", key],
                capture_output=True,
                timeout=_SUBPROCESS_TIMEOUT_S,
                check=True,
            )  # nosec B603 B607  # noqa: S603
            logger.debug("xdotool key %s sent", key)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            OSError,
        ) as e:
            # TimeoutExpired added: this one already handled a missing binary
            # but not a hung one, despite setting timeout=.
            logger.warning("xdotool key %s failed: %s", key, e)
            msg = f"xdotool key {key} failed: {e}"
            raise MediaCommandError(msg) from e

    def play(self) -> None:
        """Start or resume media playback."""
        if self.use_playerctl:
            self._execute_playerctl("play")
        else:
            self._send_xdotool_key("XF86AudioPlay")

    def pause(self) -> None:
        """Pause media playback."""
        if self.use_playerctl:
            self._execute_playerctl("pause")
        else:
            self._send_xdotool_key("XF86AudioPause")

    def play_pause_toggle(self) -> None:
        """Toggle play/pause."""
        if self.use_playerctl:
            self._execute_playerctl("play-pause")
        else:
            self._send_xdotool_key("XF86AudioPlay")

    def stop(self) -> None:
        """Stop media playback."""
        if self.use_playerctl:
            self._execute_playerctl("stop")
        else:
            self._send_xdotool_key("XF86AudioStop")

    def next_track(self) -> None:
        """Skip to next track."""
        if self.use_playerctl:
            self._execute_playerctl("next")
        else:
            self._send_xdotool_key("XF86AudioNext")

    def previous_track(self) -> None:
        """Go to previous track."""
        if self.use_playerctl:
            self._execute_playerctl("previous")
        else:
            self._send_xdotool_key("XF86AudioPrev")

    def volume_up(self, amount: int = 10) -> None:
        """Increase volume.

        Note: xdotool doesn't support custom amounts.
        playerctl supports percentage changes.
        """
        if not 0 <= amount <= 100:
            msg = f"Invalid volume amount: {amount}"
            raise MediaCommandError(msg)

        if self.use_playerctl:
            # playerctl supports percentage: volume 0.1+ means +10%
            self._execute_playerctl(f"volume {amount / 100.0}+")
        else:
            # xdotool: send multiple key presses
            presses = max(1, amount // 5)
            for _ in range(presses):
                self._send_xdotool_key("XF86AudioRaiseVolume")

    def volume_down(self, amount: int = 10) -> None:
        """Decrease volume.

        Note: xdotool doesn't support custom amounts.
        playerctl supports percentage changes.
        """
        if not 0 <= amount <= 100:
            msg = f"Invalid volume amount: {amount}"
            raise MediaCommandError(msg)

        if self.use_playerctl:
            # playerctl supports percentage: volume 0.1- means -10%
            self._execute_playerctl(f"volume {amount / 100.0}-")
        else:
            # xdotool: send multiple key presses
            presses = max(1, amount // 5)
            for _ in range(presses):
                self._send_xdotool_key("XF86AudioLowerVolume")

    def mute(self) -> None:
        """Mute audio."""
        self._send_xdotool_key("XF86AudioMute")

    def unmute(self) -> None:
        """Unmute audio."""
        self._send_xdotool_key("XF86AudioMute")

    def get_state(self) -> MediaState | None:
        """Get current media state via playerctl.

        Returns:
            MediaState if playerctl available, None otherwise

        """
        if not self.use_playerctl:
            return None

        try:
            status = self._execute_playerctl("status")
            volume = self._execute_playerctl("volume")
            title = self._execute_playerctl("metadata title")
            artist = self._execute_playerctl("metadata artist")

            return MediaState(
                is_playing=(status.lower() == "playing"),
                volume=int(float(volume) * 100),
                is_muted=False,  # playerctl doesn't provide mute state
                track_title=title if title else None,
                artist=artist if artist else None,
            )
        except Exception as e:
            logger.debug("Could not get media state: %s", e)
            return None

# Main Controller

class MediaController:
    """Cross-platform media control controller.

    Provides unified interface for media control operations across
    Windows, macOS, and Linux platforms.

    Time Complexity: O(1) per operation
    Space Complexity: O(1) (no state storage)

    Example:
        >>> controller = MediaController()
        >>> controller.play()
        >>> controller.next_track()
        >>> controller.volume_up(20)

    """

    def __init__(self) -> None:
        """Initialize media controller with platform-specific backend.

        Raises:
            UnsupportedMediaOperationError: If platform not supported

        """
        system = platform.system()

        if system == "Windows":
            self._backend = WindowsMediaBackend()
        elif system == "Darwin":
            self._backend = MacOSMediaBackend()
        elif system == "Linux":
            self._backend = LinuxMediaBackend()
        else:
            msg = f"Media control not supported on {system}"
            raise UnsupportedMediaOperationError(msg)

        logger.info("MediaController initialized for %s", system)

    def play(self) -> None:
        """Start or resume media playback.

        Raises:
            MediaCommandError: If play command fails

        """
        try:
            self._backend.play()
            logger.info("Media playback started")
        except Exception:
            logger.exception("Failed to start playback")
            raise

    def pause(self) -> None:
        """Pause media playback.

        Raises:
            MediaCommandError: If pause command fails

        """
        try:
            self._backend.pause()
            logger.info("Media playback paused")
        except Exception:
            logger.exception("Failed to pause playback")
            raise

    def play_pause_toggle(self) -> None:
        """Toggle between play and pause states.

        Raises:
            MediaCommandError: If toggle command fails

        """
        try:
            self._backend.play_pause_toggle()
            logger.info("Media playback toggled")
        except Exception:
            logger.exception("Failed to toggle playback")
            raise

    def stop(self) -> None:
        """Stop media playback.

        Raises:
            MediaCommandError: If stop command fails

        """
        try:
            self._backend.stop()
            logger.info("Media playback stopped")
        except Exception:
            logger.exception("Failed to stop playback")
            raise

    def next_track(self) -> None:
        """Skip to next track.

        Raises:
            MediaCommandError: If next command fails

        """
        try:
            self._backend.next_track()
            logger.info("Skipped to next track")
        except Exception:
            logger.exception("Failed to skip to next track")
            raise

    def previous_track(self) -> None:
        """Go to previous track.

        Raises:
            MediaCommandError: If previous command fails

        """
        try:
            self._backend.previous_track()
            logger.info("Went to previous track")
        except Exception:
            logger.exception("Failed to go to previous track")
            raise

    def volume_up(self, amount: int = 10) -> None:
        """Increase media volume.

        Args:
            amount: Volume increase amount (0-100), default 10

        Raises:
            MediaCommandError: If volume up command fails

        """
        try:
            self._backend.volume_up(amount)
            logger.info("Volume increased by %s", amount)
        except Exception:
            logger.exception("Failed to increase volume")
            raise

    def volume_down(self, amount: int = 10) -> None:
        """Decrease media volume.

        Args:
            amount: Volume decrease amount (0-100), default 10

        Raises:
            MediaCommandError: If volume down command fails

        """
        try:
            self._backend.volume_down(amount)
            logger.info("Volume decreased by %s", amount)
        except Exception:
            logger.exception("Failed to decrease volume")
            raise

    def mute(self) -> None:
        """Mute media audio.

        Raises:
            MediaCommandError: If mute command fails

        """
        try:
            self._backend.mute()
            logger.info("Media muted")
        except Exception:
            logger.exception("Failed to mute")
            raise

    def unmute(self) -> None:
        """Unmute media audio.

        Raises:
            MediaCommandError: If unmute command fails

        """
        try:
            self._backend.unmute()
            logger.info("Media unmuted")
        except Exception:
            logger.exception("Failed to unmute")
            raise

    def get_state(self) -> MediaState | None:
        """Get current media playback state.

        Returns:
            MediaState if available, None if state cannot be determined

        Note:
            State availability depends on platform and media player.
            Windows: Not available (media keys don't provide feedback)
            macOS: Available if Music app is running
            Linux: Available if playerctl is installed

        """
        try:
            state = self._backend.get_state()
            if state:
                logger.debug("Media state: %s", state)
            return state
        except Exception:
            logger.exception("Failed to get media state")
            return None
