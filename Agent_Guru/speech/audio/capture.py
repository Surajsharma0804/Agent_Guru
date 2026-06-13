"""Audio capture from microphone and files."""

import logging

import numpy as np
import sounddevice as sd
import soundfile as sf

from Agent_Guru.speech.exceptions import AudioInputError

logger = logging.getLogger(__name__)


class AudioCapture:
    """Base class for audio capture."""

    def capture(self, duration: float | None = None) -> tuple[np.ndarray, int]:
        """Capture audio.

        Args:
            duration: Duration in seconds (None for continuous)

        Returns:
            Tuple of (audio_data, sample_rate)

        Raises:
            NotImplementedError: Must be implemented by subclasses

        """
        msg = "Subclasses must implement capture()"
        raise NotImplementedError(msg)


class MicrophoneCapture(AudioCapture):
    """Captures audio from system microphone using sounddevice."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: int | None = None,
    ) -> None:
        """Initialize microphone capture.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels (1=mono, 2=stereo)
            device: Device ID (None for default)

        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device

        # Verify device is available
        try:
            if device is not None:
                device_info = sd.query_devices(device)
                logger.info("Using audio device: %s", device_info["name"])
            else:
                logger.info("Using default audio device")
        except Exception as e:
            msg = f"Failed to query audio device: {e}"
            raise AudioInputError(msg) from e

    def capture(self, duration: float | None = None) -> tuple[np.ndarray, int]:
        """Capture audio from microphone.

        Args:
            duration: Duration in seconds (required for microphone)

        Returns:
            Tuple of (audio_data, sample_rate)

        Raises:
            AudioInputError: If capture fails or duration not provided

        """
        if duration is None:
            msg = "Duration is required for microphone capture"
            raise AudioInputError(msg)

        # BUG-013: reject non-positive duration before passing to sounddevice
        if duration <= 0:
            msg = f"Duration must be > 0, got {duration}"
            raise AudioInputError(msg)

        try:
            logger.debug("Capturing %.3fs of audio at %dHz", duration, self.sample_rate)

            # Record audio
            audio = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device,
                dtype="float32",
            )
            sd.wait()  # Wait for recording to complete

            # Convert to mono if needed
            if self.channels > 1 and audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Flatten to 1D array
            audio = audio.flatten()

            logger.debug("Captured %s samples", len(audio))
            return audio, self.sample_rate

        except Exception as e:
            msg = f"Failed to capture audio: {e}"
            raise AudioInputError(msg) from e

    @staticmethod
    def list_devices() -> list:
        """List available audio input devices.

        Returns:
            List of device information dictionaries

        """
        try:
            devices = sd.query_devices()
            return [
                {
                    "id": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": dev["default_samplerate"],
                }
                for i, dev in enumerate(devices)
                if dev["max_input_channels"] > 0
            ]
        except Exception:
            logger.exception("Failed to list devices")
            return []


class FileCapture(AudioCapture):
    """Loads audio from files using soundfile."""

    def __init__(self, file_path: str) -> None:
        """Initialize file capture.

        Args:
            file_path: Path to audio file

        """
        self.file_path = file_path
        logger.info("FileCapture initialized for: %s", file_path)

    def capture(self, duration: float | None = None) -> tuple[np.ndarray, int]:
        """Load audio from file.

        Args:
            duration: Duration in seconds (None loads entire file)

        Returns:
            Tuple of (audio_data, sample_rate)

        Raises:
            AudioInputError: If file loading fails

        """
        return self.load_file(self.file_path, duration)

    def load_file(self, file_path: str, duration: float | None = None) -> tuple[np.ndarray, int]:
        """Load audio from file.

        Supports WAV, FLAC, OGG, and other formats via soundfile.

        Args:
            file_path: Path to audio file
            duration: Duration in seconds (None loads entire file)

        Returns:
            Tuple of (audio_data, sample_rate)

        Raises:
            AudioInputError: If file loading fails

        """
        try:
            logger.debug("Loading audio from: %s", file_path)

            # Load audio file
            audio, sample_rate = sf.read(file_path, dtype="float32")

            # Convert to mono if stereo
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Trim to duration if specified
            if duration is not None:
                max_samples = int(duration * sample_rate)
                audio = audio[:max_samples]

            logger.debug(
                "Loaded %d samples at %dHz (%.2fs)",
                len(audio),
                sample_rate,
                len(audio) / sample_rate,
            )

            return audio, sample_rate

        except FileNotFoundError as e:
            msg = f"Audio file not found: {file_path}"
            raise AudioInputError(msg) from e
            msg = f"Failed to load audio file: {e}"
            raise AudioInputError(msg) from e

    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """Get information about an audio file.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary with file information

        Raises:
            AudioInputError: If file cannot be read

        """
        try:
            info = sf.info(file_path)
            return {
                "duration": info.duration,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "format": info.format,
                "subtype": info.subtype,
            }
        except Exception as e:
            msg = f"Failed to get file info: {e}"
            raise AudioInputError(msg) from e
