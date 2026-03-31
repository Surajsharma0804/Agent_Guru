"""
Module: Agent_Guru.speech.audio.pipeline
Purpose: Audio pipeline with ring buffer, device management, and feedback prevention

Provides:
- Lock-free ring buffer (10 seconds capacity at 16kHz)
- Audio device detection and selection
- Graceful device disconnection handling with auto-reconnection
- Audio feedback loop prevention during simultaneous capture/playback

Performance:
    - Ring buffer: O(1) read/write
    - Device detection: O(d) where d = number of devices
    - Feedback prevention: mute capture during playback

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)

# Audio constants
_DEFAULT_SAMPLE_RATE = 16000
_DEFAULT_CHANNELS = 1
_RING_BUFFER_SECONDS = 10
_RECONNECT_DELAY_S = 1.0
_MAX_RECONNECT_ATTEMPTS = 5


class DeviceState(str, Enum):
    """Audio device connection state."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class AudioDevice:
    """Represents an audio device.

    Attributes:
        device_id: System device identifier
        name: Human-readable device name
        max_input_channels: Number of input channels
        max_output_channels: Number of output channels
        default_sample_rate: Default sample rate
        is_default: Whether this is the system default
    """
    device_id: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float
    is_default: bool = False

    @property
    def is_input(self) -> bool:
        return self.max_input_channels > 0

    @property
    def is_output(self) -> bool:
        return self.max_output_channels > 0


class RingBuffer:
    """
    Thread-safe ring buffer for audio frames.

    Uses a deque with maxlen for O(1) append and O(1) popleft.
    Capacity is fixed at construction time.

    Performance:
        - append: O(1) amortized
        - read_frames: O(k) where k = frames requested
        - Space: O(capacity)
    """

    def __init__(self, capacity_frames: int) -> None:
        """Initialize ring buffer.

        Args:
            capacity_frames: Maximum number of frames to store
        """
        if capacity_frames < 1:
            raise ValueError(f"capacity_frames must be >= 1, got {capacity_frames}")
        self._buffer: deque[np.ndarray] = deque(maxlen=capacity_frames)
        self._lock = threading.Lock()
        self._capacity = capacity_frames

    def write(self, frame: np.ndarray) -> None:
        """Write a frame to the buffer (overwrites oldest if full).

        Time Complexity: O(1)

        Args:
            frame: Audio frame as numpy array
        """
        with self._lock:
            self._buffer.append(frame.copy())

    def read_frames(self, n: int) -> list[np.ndarray]:
        """Read the n most recent frames.

        Time Complexity: O(n)

        Args:
            n: Number of frames to read

        Returns:
            List of frames (oldest first), up to n frames
        """
        with self._lock:
            frames = list(self._buffer)
        return frames[-n:] if n < len(frames) else frames

    def read_all(self) -> list[np.ndarray]:
        """Read all buffered frames and clear the buffer.

        Returns:
            All buffered frames in order
        """
        with self._lock:
            frames = list(self._buffer)
            self._buffer.clear()
        return frames

    def size(self) -> int:
        """Return current number of frames in buffer."""
        with self._lock:
            return len(self._buffer)

    def capacity(self) -> int:
        """Return maximum buffer capacity."""
        return self._capacity

    def clear(self) -> None:
        """Clear all frames from buffer."""
        with self._lock:
            self._buffer.clear()

    def is_full(self) -> bool:
        """Return True if buffer is at capacity."""
        with self._lock:
            return len(self._buffer) >= self._capacity


class AudioPipeline:
    """
    Production audio pipeline with device management and feedback prevention.

    Manages audio capture and playback with:
    - Lock-free ring buffer (10 seconds at 16kHz)
    - Device detection and selection
    - Auto-reconnection on device disconnect
    - Feedback prevention (mute capture during playback)

    Example:
        >>> pipeline = AudioPipeline()
        >>> devices = pipeline.list_input_devices()
        >>> pipeline.select_input_device(devices[0].device_id)
        >>> frames = pipeline.read_frames(n=10)

    Performance:
        - Ring buffer write: O(1)
        - Frame read: O(k)
        - Device detection: O(d)
    """

    def __init__(
        self,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        channels: int = _DEFAULT_CHANNELS,
        ring_buffer_seconds: float = _RING_BUFFER_SECONDS,
    ) -> None:
        """Initialize audio pipeline.

        Args:
            sample_rate: Audio sample rate in Hz (default 16000)
            channels: Number of channels (default 1 = mono)
            ring_buffer_seconds: Ring buffer capacity in seconds
        """
        self._sample_rate = sample_rate
        self._channels = channels

        # Calculate ring buffer capacity in frames (1 frame = 512 samples)
        frame_size = 512
        capacity_frames = int(ring_buffer_seconds * sample_rate / frame_size)
        self._ring_buffer = RingBuffer(capacity_frames=max(1, capacity_frames))

        self._input_device_id: int | None = None
        self._output_device_id: int | None = None
        self._device_state = DeviceState.DISCONNECTED
        self._is_playing = threading.Event()
        self._lock = threading.Lock()

        # Reconnection state
        self._reconnect_attempts = 0
        self._reconnect_callbacks: list[Callable] = []

        logger.info(
            f"AudioPipeline initialized: {sample_rate}Hz, {channels}ch, "
            f"ring_buffer={ring_buffer_seconds}s ({capacity_frames} frames)"
        )

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def list_input_devices(self) -> list[AudioDevice]:
        """List available audio input devices.

        Returns:
            List of AudioDevice with input capability
        """
        return self._query_devices(input_only=True)

    def list_output_devices(self) -> list[AudioDevice]:
        """List available audio output devices.

        Returns:
            List of AudioDevice with output capability
        """
        return self._query_devices(output_only=True)

    def list_all_devices(self) -> list[AudioDevice]:
        """List all audio devices.

        Returns:
            List of all AudioDevice objects
        """
        return self._query_devices()

    def select_input_device(self, device_id: int | None) -> None:
        """Select the audio input device.

        Args:
            device_id: Device ID, or None for system default
        """
        with self._lock:
            self._input_device_id = device_id
            self._device_state = DeviceState.CONNECTED
            self._reconnect_attempts = 0
        logger.info("Input device selected: %s", device_id)

    def select_output_device(self, device_id: int | None) -> None:
        """Select the audio output device.

        Args:
            device_id: Device ID, or None for system default
        """
        with self._lock:
            self._output_device_id = device_id
        logger.info("Output device selected: %s", device_id)

    def get_device_state(self) -> DeviceState:
        """Return current device connection state."""
        return self._device_state

    def on_device_reconnected(self, callback: Callable) -> None:
        """Register a callback for device reconnection events.

        Args:
            callback: Callable invoked when device reconnects
        """
        self._reconnect_callbacks.append(callback)

    def handle_device_disconnect(self) -> None:
        """Handle device disconnection with auto-reconnection.

        Attempts reconnection with exponential backoff up to
        _MAX_RECONNECT_ATTEMPTS times.
        """
        with self._lock:
            self._device_state = DeviceState.DISCONNECTED
            self._reconnect_attempts = 0

        logger.warning("Audio device disconnected - attempting reconnection")
        self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to audio device."""
        for attempt in range(_MAX_RECONNECT_ATTEMPTS):
            delay = _RECONNECT_DELAY_S * (2 ** attempt)  # Exponential backoff
            logger.info(f"Reconnect attempt {attempt + 1}/{_MAX_RECONNECT_ATTEMPTS} in {delay:.1f}s")

            with self._lock:
                self._device_state = DeviceState.RECONNECTING
                self._reconnect_attempts = attempt + 1

            time.sleep(delay)

            # Check if device is available
            devices = self._query_devices(input_only=True)
            if devices:
                with self._lock:
                    self._device_state = DeviceState.CONNECTED
                    self._reconnect_attempts = 0

                logger.info("Audio device reconnected successfully")
                for cb in self._reconnect_callbacks:
                    try:
                        cb()
                    except Exception as e:
                        logger.error("Reconnect callback error: %s", e)
                return

        with self._lock:
            self._device_state = DeviceState.ERROR
        logger.error("Audio device reconnection failed after max attempts")

    # ------------------------------------------------------------------
    # Ring buffer operations
    # ------------------------------------------------------------------

    def write_frame(self, frame: np.ndarray) -> None:
        """Write an audio frame to the ring buffer.

        Skips write if playback is active (feedback prevention).

        Time Complexity: O(1)

        Args:
            frame: Audio frame as numpy array
        """
        # Feedback prevention: don't capture during playback
        if self._is_playing.is_set():
            return
        self._ring_buffer.write(frame)

    def read_frames(self, n: int) -> list[np.ndarray]:
        """Read the n most recent audio frames.

        Time Complexity: O(n)

        Args:
            n: Number of frames to read

        Returns:
            List of audio frames
        """
        return self._ring_buffer.read_frames(n)

    def read_all_frames(self) -> list[np.ndarray]:
        """Read and clear all buffered frames.

        Returns:
            All buffered frames
        """
        return self._ring_buffer.read_all()

    def buffer_size(self) -> int:
        """Return current number of frames in ring buffer."""
        return self._ring_buffer.size()

    def buffer_capacity(self) -> int:
        """Return ring buffer capacity in frames."""
        return self._ring_buffer.capacity()

    # ------------------------------------------------------------------
    # Feedback prevention
    # ------------------------------------------------------------------

    def set_playing(self, playing: bool) -> None:
        """Signal that audio playback is active/inactive.

        When playing=True, write_frame() will skip writes to prevent
        audio feedback loops.

        Args:
            playing: True if playback is active
        """
        if playing:
            self._is_playing.set()
            logger.debug("AudioPipeline: playback started (capture muted)")
        else:
            self._is_playing.clear()
            logger.debug("AudioPipeline: playback stopped (capture resumed)")

    def is_playing(self) -> bool:
        """Return True if audio playback is currently active."""
        return self._is_playing.is_set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def sample_rate(self) -> int:
        """Audio sample rate in Hz."""
        return self._sample_rate

    @property
    def channels(self) -> int:
        """Number of audio channels."""
        return self._channels

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_devices(
        self,
        input_only: bool = False,
        output_only: bool = False,
    ) -> list[AudioDevice]:
        """Query available audio devices.

        Args:
            input_only: Only return input devices
            output_only: Only return output devices

        Returns:
            List of AudioDevice objects
        """
        try:
            import sounddevice as sd
            raw_devices = sd.query_devices()
            default_input = sd.default.device[0] if hasattr(sd.default, 'device') else None
            default_output = sd.default.device[1] if hasattr(sd.default, 'device') else None

            devices = []
            for i, dev in enumerate(raw_devices):
                device = AudioDevice(
                    device_id=i,
                    name=dev.get("name", f"Device {i}"),
                    max_input_channels=dev.get("max_input_channels", 0),
                    max_output_channels=dev.get("max_output_channels", 0),
                    default_sample_rate=dev.get("default_samplerate", 44100.0),
                    is_default=(i == default_input or i == default_output),
                )
                if input_only and not device.is_input:
                    continue
                if output_only and not device.is_output:
                    continue
                devices.append(device)

            return devices

        except Exception as e:
            logger.warning("Could not query audio devices: %s", e)
            return []
