"""
Configuration management module for GuruVision facial recognition system.

Provides centralized configuration loading, validation, and runtime management.
Supports YAML and JSON configuration files with sensible defaults for all parameters.

**Validates: Requirements 18.1, 18.2, 18.3, 18.4**
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()

# ---------------------------------------------------------------------------
# Default value constants (used for validation fallback)
# ---------------------------------------------------------------------------

_DEFAULT_RECOGNITION_THRESHOLD: float = 0.6
_DEFAULT_DETECTION_CONFIDENCE: float = 0.5
_DEFAULT_TARGET_FPS: int = 10
_DEFAULT_LOG_MAX_SIZE_MB: int = 100
_DEFAULT_TRACKER_MAX_AGE: int = 30

_THRESHOLD_MIN: float = 0.4
_THRESHOLD_MAX: float = 0.9


@dataclass
class GuruVisionConfig:
    """Centralized configuration for the GuruVision facial recognition system.

    All parameters have sensible defaults so the system can run without a
    configuration file.  Call :meth:`validate` after construction (or after
    loading from a file) to sanitise values and receive a list of warnings.

    Attributes:
        onnx_model_path: Path to the ONNX recognition model file.
        database_path: Path to the JSON identity database file.
        recognition_threshold: Cosine-similarity threshold for identity match
            (must be in [0.4, 0.9]; default 0.6).
        detection_confidence: Minimum confidence for face detections
            (must be in [0.0, 1.0]; default 0.5).
        use_gpu: Whether to prefer GPU inference when available.
        target_fps: Target processing frame rate (must be > 0; default 10).
        enable_liveness: Enable liveness / anti-spoofing detection.
        enable_emotion: Enable emotion recognition.
        enable_tracking: Enable multi-face tracking.
        enable_low_light_enhancement: Enable low-light pre-processing.
        tracker_algorithm: Tracking algorithm to use ("deepsort" or "bytetrack").
        tracker_max_age: Maximum frames a track survives without a detection
            (must be > 0; default 30).
        log_level: Python logging level name (e.g. "INFO", "DEBUG").
        log_file: Path to the rotating log file.
        log_max_size_mb: Maximum log file size in MB before rotation
            (must be > 0; default 100).
        camera_index: Webcam device index (used when video_source is None).
        video_source: Path to a video file, or None to use the webcam.

    Example::

        config = GuruVisionConfig()
        warnings = config.validate()

        config = GuruVisionConfig.from_file("config.yaml")
        warnings = config.validate()
    """

    # Model paths
    onnx_model_path: str = "Agent_Guru/vision/data/model/vision_model.onnx"
    database_path: str = "Agent_Guru/vision/data/database/identities.json"

    # Recognition settings
    recognition_threshold: float = _DEFAULT_RECOGNITION_THRESHOLD
    detection_confidence: float = _DEFAULT_DETECTION_CONFIDENCE

    # Performance settings
    use_gpu: bool = True
    target_fps: int = _DEFAULT_TARGET_FPS

    # Feature toggles
    enable_liveness: bool = True
    enable_emotion: bool = True
    enable_tracking: bool = True
    enable_low_light_enhancement: bool = True

    # Tracking settings
    tracker_algorithm: str = "deepsort"
    tracker_max_age: int = _DEFAULT_TRACKER_MAX_AGE

    # Logging
    log_level: str = "INFO"
    log_file: str = "Agent_Guru/vision/data/logs/guruvision.log"
    log_max_size_mb: int = _DEFAULT_LOG_MAX_SIZE_MB

    # Camera settings
    camera_index: int = 0
    video_source: Optional[str] = None

    # ---------------------------------------------------------------------------
    # Class methods
    # ---------------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str) -> "GuruVisionConfig":
        """Load configuration from a YAML or JSON file.

        Missing keys fall back to dataclass defaults.  The file extension
        determines the parser: ``.yaml`` / ``.yml`` use PyYAML (with a
        ``json`` fallback if PyYAML is not installed); all other extensions
        are treated as JSON.

        Args:
            path: Filesystem path to the configuration file.

        Returns:
            A :class:`GuruVisionConfig` populated from the file.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the file cannot be parsed as YAML or JSON.

        Example::

            config = GuruVisionConfig.from_file("config.yaml")
        """
        file_path = Path(path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        raw_text = file_path.read_text(encoding="utf-8")
        data: dict = {}

        suffix = file_path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            data = cls._parse_yaml(raw_text, path)
        else:
            data = cls._parse_json(raw_text, path)

        return cls._from_dict(data)

    # ---------------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Validate configuration values and reset out-of-range fields to defaults.

        Invalid values are replaced with their defaults and a warning is logged
        (no exception is raised).  This satisfies Requirement 18.3: the system
        must use defaults and log warnings rather than crashing on bad config.

        Returns:
            A list of human-readable warning strings for every field that was
            reset to its default value.  An empty list means all values are valid.

        Example::

            config = GuruVisionConfig(recognition_threshold=99.0)
            warnings = config.validate()
            # config.recognition_threshold is now 0.6
            # warnings contains one entry describing the reset
        """
        warnings: list[str] = []

        # recognition_threshold must be in [0.4, 0.9]
        if not (_THRESHOLD_MIN <= self.recognition_threshold <= _THRESHOLD_MAX):
            msg = (
                f"recognition_threshold={self.recognition_threshold!r} is outside "
                f"[{_THRESHOLD_MIN}, {_THRESHOLD_MAX}]; "
                f"resetting to default {_DEFAULT_RECOGNITION_THRESHOLD}"
            )
            logger.warning(msg)
            warnings.append(msg)
            self.recognition_threshold = _DEFAULT_RECOGNITION_THRESHOLD

        # detection_confidence must be in [0.0, 1.0]
        if not (0.0 <= self.detection_confidence <= 1.0):
            msg = (
                f"detection_confidence={self.detection_confidence!r} is outside "
                f"[0.0, 1.0]; resetting to default {_DEFAULT_DETECTION_CONFIDENCE}"
            )
            logger.warning(msg)
            warnings.append(msg)
            self.detection_confidence = _DEFAULT_DETECTION_CONFIDENCE

        # target_fps must be > 0
        if self.target_fps <= 0:
            msg = (
                f"target_fps={self.target_fps!r} must be > 0; "
                f"resetting to default {_DEFAULT_TARGET_FPS}"
            )
            logger.warning(msg)
            warnings.append(msg)
            self.target_fps = _DEFAULT_TARGET_FPS

        # log_max_size_mb must be > 0
        if self.log_max_size_mb <= 0:
            msg = (
                f"log_max_size_mb={self.log_max_size_mb!r} must be > 0; "
                f"resetting to default {_DEFAULT_LOG_MAX_SIZE_MB}"
            )
            logger.warning(msg)
            warnings.append(msg)
            self.log_max_size_mb = _DEFAULT_LOG_MAX_SIZE_MB

        # tracker_max_age must be > 0
        if self.tracker_max_age <= 0:
            msg = (
                f"tracker_max_age={self.tracker_max_age!r} must be > 0; "
                f"resetting to default {_DEFAULT_TRACKER_MAX_AGE}"
            )
            logger.warning(msg)
            warnings.append(msg)
            self.tracker_max_age = _DEFAULT_TRACKER_MAX_AGE

        return warnings

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    @classmethod
    def _parse_yaml(cls, text: str, path: str) -> dict:
        """Parse YAML text, falling back to JSON if PyYAML is unavailable."""
        try:
            import yaml  # type: ignore[import]

            result = yaml.safe_load(text)
            if not isinstance(result, dict):
                raise ValueError(f"Expected a YAML mapping at the top level in {path!r}")
            return result
        except ImportError as e:
            logger.warning("PyYAML not installed; attempting to parse %r as JSON", path)
            return cls._parse_json(text, path)

    @classmethod
    def _parse_json(cls, text: str, path: str) -> dict:
        """Parse JSON text."""
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse {path!r} as JSON: {exc}") from exc
        if not isinstance(result, dict):
            raise ValueError(f"Expected a JSON object at the top level in {path!r}")
        return result

    @classmethod
    def _from_dict(cls, data: dict) -> "GuruVisionConfig":
        """Build a :class:`GuruVisionConfig` from a plain dict.

        Unknown keys are silently ignored; missing keys use dataclass defaults.
        """
        # Collect only the fields that exist on the dataclass
        import dataclasses

        known_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
