"""Platform integration for speech engine.

Provides audio device access and system control operations through
the platform integration layer.

Performance Requirements:
- Device enumeration: <100ms
- Device switching: <500ms
- System control: <1s per operation

Author: Speech Engine Team
Date: 2026-02-25
"""

import logging
from dataclasses import dataclass
from typing import Any

from Agent_Guru.platform.hardware.monitor import HardwareMonitor
from Agent_Guru.platform.os_controller import OperationResult, OSController

from .exceptions import AudioInputError, GuruSpeechError

logger = logging.getLogger(__name__)


@dataclass
class AudioDeviceInfo:
    """Information about an audio device."""

    device_id: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool


class PlatformIntegration:
    """Integration with platform layer for audio and system control.

    Provides:
    - Audio device enumeration and selection
    - System control operations (volume, brightness, etc.)
    - Cross-platform audio device management

    Time Complexity: O(1) for most operations
    Space Complexity: O(n) where n is number of audio devices
    """

    def __init__(self) -> None:
        """Initialize platform integration."""
        self.os_controller = OSController()
        self.hardware_monitor = HardwareMonitor()
        logger.info("Platform integration initialized")

    # Audio Device Management

    def list_audio_devices(self) -> list[AudioDeviceInfo]:
        """List available audio input devices.

        Time Complexity: O(n) where n is number of devices

        Returns:
            List of audio device information

        Raises:
            AudioInputError: If device enumeration fails

        """
        try:
            import sounddevice as sd

            # Under the PortAudio lock: reading the device list while the mic
            # recovery path re-initialises PortAudio on another thread raised
            # PortAudioError tens of thousands of times in measurement.
            from Agent_Guru.speech.audio.portaudio_lock import portaudio_in_use

            with portaudio_in_use():
                devices = sd.query_devices()
                default_device = sd.default.device[0]  # Input device
            audio_devices = []

            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    audio_devices.append(
                        AudioDeviceInfo(
                            device_id=i,
                            name=dev["name"],
                            channels=dev["max_input_channels"],
                            sample_rate=dev["default_samplerate"],
                            is_default=(i == default_device),
                        ),
                    )

            logger.debug("Found %s audio input devices", len(audio_devices))
            return audio_devices

        except Exception as e:
            msg = f"Failed to list audio devices: {e}"
            raise AudioInputError(msg) from e

    def get_default_audio_device(self) -> AudioDeviceInfo | None:
        """Get the default audio input device.

        Time Complexity: O(n) where n is number of devices

        Returns:
            Default audio device info, or None if not found

        """
        try:
            devices = self.list_audio_devices()
            for device in devices:
                if device.is_default:
                    return device
            return None
        except Exception:
            logger.exception("Failed to get default device")
            return None

    def validate_audio_device(self, device_id: int) -> bool:
        """Validate that an audio device exists and is available.

        Time Complexity: O(n) where n is number of devices

        Args:
            device_id: Device ID to validate

        Returns:
            True if device is valid, False otherwise

        """
        try:
            devices = self.list_audio_devices()
            return any(dev.device_id == device_id for dev in devices)
        except Exception:
            return False

    # System Control Operations

    def set_system_volume(self, level: int) -> OperationResult:
        """Set system volume level.

        Time Complexity: O(1)

        Args:
            level: Volume level (0-100)

        Returns:
            Operation result

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.set_volume(level)
            if not result.success:
                msg = f"Failed to set volume: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"Volume control failed: {e}"
            raise GuruSpeechError(msg) from e

    def set_system_brightness(self, level: int) -> OperationResult:
        """Set system brightness level.

        Time Complexity: O(1)

        Args:
            level: Brightness level (0-100)

        Returns:
            Operation result

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.set_brightness(level)
            if not result.success:
                msg = f"Failed to set brightness: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"Brightness control failed: {e}"
            raise GuruSpeechError(msg) from e

    def open_application(self, app_name: str) -> OperationResult:
        """Open an application by name.

        Time Complexity: O(1)

        Args:
            app_name: Application name

        Returns:
            Operation result

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.open_application(app_name)
            if not result.success:
                msg = f"Failed to open application: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"Application launch failed: {e}"
            raise GuruSpeechError(msg) from e

    def type_text(self, text: str, typing_speed: float = 0.05) -> OperationResult:
        """Type text into the active application.

        Time Complexity: O(n) where n is text length

        Args:
            text: Text to type
            typing_speed: Delay between keystrokes in seconds

        Returns:
            Operation result

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.type_text(text, typing_speed)
            if not result.success:
                msg = f"Failed to type text: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"Text input failed: {e}"
            raise GuruSpeechError(msg) from e

    def play_media(self) -> OperationResult:
        """Play media (simulate play/pause key).

        Time Complexity: O(1)

        Returns:
            Operation result

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.play_media()
            if not result.success:
                msg = f"Failed to play media: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"Media control failed: {e}"
            raise GuruSpeechError(msg) from e

    def pause_media(self) -> OperationResult:
        """Pause media (simulate play/pause key).

        Time Complexity: O(1)

        Returns:
            Operation result

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.pause_media()
            if not result.success:
                msg = f"Failed to pause media: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"Media control failed: {e}"
            raise GuruSpeechError(msg) from e

    def take_screenshot(self, save_path: str | None = None) -> OperationResult:
        """Take a screenshot.

        Time Complexity: O(1)

        Args:
            save_path: Path to save screenshot (None for default)

        Returns:
            Operation result with screenshot path

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.take_screenshot(save_path)
            if not result.success:
                msg = f"Failed to take screenshot: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"Screenshot failed: {e}"
            raise GuruSpeechError(msg) from e

    # Hardware Monitoring

    def get_system_info(self) -> dict[str, Any]:
        """Get comprehensive system information.

        Time Complexity: O(1)

        Returns:
            Dictionary with system information including:
            - CPU usage
            - Memory usage
            - Battery status (if available)
            - Platform information

        """
        try:
            info = {
                "platform": self.os_controller.get_system_info(),
                "cpu": self.hardware_monitor.get_cpu_usage().to_dict(),
                "memory": self.hardware_monitor.get_memory_info().to_dict(),
            }

            # Add battery info if available (mobile/laptop)
            battery = self.hardware_monitor.get_battery_info()
            if battery:
                info["battery"] = battery.to_dict()

            return info

        except Exception:
            logger.exception("Failed to get system info")
            return {}

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage.

        Time Complexity: O(1)

        Returns:
            CPU usage percentage (0-100)

        """
        try:
            cpu_info = self.hardware_monitor.get_cpu_usage()
            return cpu_info.usage_percent
        except Exception:
            logger.exception("Failed to get CPU usage")
            return 0.0

    def get_memory_usage(self) -> dict[str, Any]:
        """Get current memory usage information.

        Time Complexity: O(1)

        Returns:
            Dictionary with memory usage details

        """
        try:
            mem_info = self.hardware_monitor.get_memory_info()
            return mem_info.to_dict()
        except Exception:
            logger.exception("Failed to get memory usage")
            return {}

    def get_battery_status(self) -> dict[str, Any] | None:
        """Get battery status (if available).

        Time Complexity: O(1)

        Returns:
            Battery status dictionary, or None if not available

        """
        try:
            battery = self.hardware_monitor.get_battery_info()
            return battery.to_dict() if battery else None
        except Exception:
            logger.exception("Failed to get battery status")
            return None

    # File Operations

    def create_file(self, file_path: str, content: str) -> OperationResult:
        """Create a file with content.

        Time Complexity: O(n) where n is content length

        Args:
            file_path: Path to create file
            content: File content

        Returns:
            Operation result

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.create_file(file_path, content)
            if not result.success:
                msg = f"Failed to create file: {result.message}"
                raise GuruSpeechError(msg)
            return result
        except Exception as e:
            msg = f"File creation failed: {e}"
            raise GuruSpeechError(msg) from e

    def read_file(self, file_path: str) -> str:
        """Read file content.

        Time Complexity: O(n) where n is file size

        Args:
            file_path: Path to read

        Returns:
            File content

        Raises:
            GuruSpeechError: If operation fails

        """
        try:
            result = self.os_controller.read_file(file_path)
            if not result.success:
                msg = f"Failed to read file: {result.message}"
                raise GuruSpeechError(msg)
            return result.metadata.get("content", "")
        except Exception as e:
            msg = f"File read failed: {e}"
            raise GuruSpeechError(msg) from e

    def __repr__(self) -> str:
        """String representation."""
        return f"PlatformIntegration(os={self.os_controller.platform})"
