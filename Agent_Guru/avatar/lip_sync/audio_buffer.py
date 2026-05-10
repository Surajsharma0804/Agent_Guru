"""Module: Agent_Guru.avatar.lip_sync.audio_buffer
Purpose: Thread-safe ring buffer for streaming audio processing.

Provides smooth audio buffering for lip sync with:
    - Lock-free reads (numpy circular indexing)
    - Thread-safe writes
    - Configurable buffer size
    - Overflow detection and handling

Requirements: Req 6.2 (Audio buffering smoothness)
"""

from __future__ import annotations

import threading

import numpy as np


class AudioRingBuffer:
    """Thread-safe ring buffer for audio samples.

    Args:
        capacity: Maximum number of samples in the buffer.
        dtype: NumPy dtype for audio samples.

    """

    def __init__(self, capacity: int = 16384, dtype: np.dtype = np.float32) -> None:
        self._capacity = capacity
        self._dtype = dtype
        self._buffer = np.zeros(capacity, dtype=dtype)
        self._write_pos = 0
        self._read_pos = 0
        self._size = 0
        self._lock = threading.Lock()

    @property
    def available(self) -> int:
        """Number of samples available to read."""
        with self._lock:
            return self._size

    @property
    def capacity(self) -> int:
        """Total buffer capacity in samples."""
        return self._capacity

    def write(self, data: np.ndarray) -> int:
        """Write audio samples to the buffer.

        Args:
            data: Float32 audio samples to write.

        Returns:
            Number of samples actually written (may be less if buffer full).

        """
        with self._lock:
            n = len(data)
            space = self._capacity - self._size
            n_write = min(n, space)

            if n_write == 0:
                return 0

            # Handle wrap-around
            end = self._write_pos + n_write
            if end <= self._capacity:
                self._buffer[self._write_pos : end] = data[:n_write]
            else:
                first = self._capacity - self._write_pos
                self._buffer[self._write_pos :] = data[:first]
                self._buffer[: n_write - first] = data[first:n_write]

            self._write_pos = (self._write_pos + n_write) % self._capacity
            self._size += n_write
            return n_write

    def read(self, n: int) -> np.ndarray | None:
        """Read up to n samples from the buffer.

        Args:
            n: Number of samples to read.

        Returns:
            Array of samples, or None if buffer is empty.

        """
        with self._lock:
            if self._size == 0:
                return None

            n_read = min(n, self._size)
            out = np.empty(n_read, dtype=self._dtype)

            end = self._read_pos + n_read
            if end <= self._capacity:
                out[:] = self._buffer[self._read_pos : end]
            else:
                first = self._capacity - self._read_pos
                out[:first] = self._buffer[self._read_pos :]
                out[first:] = self._buffer[: n_read - first]

            self._read_pos = (self._read_pos + n_read) % self._capacity
            self._size -= n_read
            return out

    def clear(self) -> None:
        """Clear all buffered samples."""
        with self._lock:
            self._write_pos = 0
            self._read_pos = 0
            self._size = 0
            self._buffer[:] = 0.0

    def is_empty(self) -> bool:
        """Return True if the buffer has no samples."""
        with self._lock:
            return self._size == 0

    def is_full(self) -> bool:
        """Return True if the buffer is at capacity."""
        with self._lock:
            return self._size >= self._capacity
