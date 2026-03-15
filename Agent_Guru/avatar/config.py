"""
Module: Agent_Guru.avatar.config
Purpose: Pydantic-validated configuration for the Avatar and Emotion Engine.

Supports:
    - JSON and YAML config files
    - Hot-reloading via watchdog (optional)
    - Schema validation with detailed error messages
    - Default configurations for common use cases

Requirements: Req 8 (Configuration and Customization), Req 11.10
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("guruvision.avatar.config")

_VALID_BACKENDS = {"opencv", "pyqt", "headless"}
_VALID_EMOTION_MODELS = {"DeepFace", "FER", "heuristic", "auto"}


try:
    from pydantic import BaseModel, Field, field_validator, model_validator
    from pydantic_settings import BaseSettings

    class AvatarConfig(BaseModel):
        """Complete Pydantic-validated configuration for the avatar system.

        All fields have sensible defaults so the system works out-of-the-box.
        """

        # Emotion recognition
        emotion_model: str = Field(default="auto", description="Emotion backend: DeepFace, FER, heuristic, auto")
        emotion_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
        emotion_smoothing_window: int = Field(default=5, ge=1, le=30)
        map_to_27_emotions: bool = Field(default=True, description="Map 7-emotion output to 27-emotion taxonomy")

        # Lip sync
        lip_sync_model_path: Optional[str] = Field(default=None)
        lip_sync_threshold_ms: float = Field(default=50.0, gt=0.0)
        audio_buffer_size: int = Field(default=4096, ge=512)

        # Personality
        personality_profile_path: Optional[str] = Field(default=None)
        guru_profile_path: Optional[str] = Field(default=None)
        maya_profile_path: Optional[str] = Field(default=None)

        # Rendering
        render_backend: str = Field(default="headless")
        target_fps: int = Field(default=60, ge=1, le=120)
        display_width: int = Field(default=640, ge=160)
        display_height: int = Field(default=480, ge=120)
        transition_duration_ms: float = Field(default=350.0, ge=100.0, le=1000.0)

        # Performance
        max_cpu_percent: float = Field(default=50.0, gt=0.0, le=100.0)
        max_memory_mb: float = Field(default=512.0, gt=0.0)
        enable_gpu: bool = Field(default=True)

        # Paths
        avatar_model_path: Optional[str] = Field(default=None)

        @field_validator("emotion_model")
        @classmethod
        def validate_emotion_model(cls, v: str) -> str:
            if v not in _VALID_EMOTION_MODELS:
                logger.warning("Invalid emotion_model '%s' — using 'auto'", v)
                return "auto"
            return v

        @field_validator("render_backend")
        @classmethod
        def validate_render_backend(cls, v: str) -> str:
            if v not in _VALID_BACKENDS:
                logger.warning("Invalid render_backend '%s' — using 'headless'", v)
                return "headless"
            return v

        model_config = {"frozen": False}

        @classmethod
        def from_file(cls, path: str) -> "AvatarConfig":
            """Load configuration from a JSON or YAML file."""
            config_path = Path(path)
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")

            suffix = config_path.suffix.lower()
            if suffix in (".yaml", ".yml"):
                try:
                    import yaml  # type: ignore[import]
                    with config_path.open() as fh:
                        raw = yaml.safe_load(fh)
                except ImportError:
                    raise ImportError("PyYAML required for YAML config files: pip install pyyaml")
            else:
                with config_path.open() as fh:
                    raw = json.load(fh)

            return cls(**raw)

        @classmethod
        def default(cls) -> "AvatarConfig":
            """Return a default configuration."""
            return cls()

        def to_dict(self) -> Dict[str, Any]:
            """Serialize config to a plain dictionary."""
            return self.model_dump()

        def validate_config(self) -> List[str]:
            """Validate all fields and return list of warnings."""
            warnings = []
            if self.avatar_model_path and not Path(self.avatar_model_path).exists():
                warnings.append(f"avatar_model_path not found: {self.avatar_model_path}")
            if self.lip_sync_model_path and not Path(self.lip_sync_model_path).exists():
                warnings.append(f"lip_sync_model_path not found: {self.lip_sync_model_path}")
            return warnings

except ImportError:
    # Fallback dataclass implementation
    import dataclasses

    @dataclasses.dataclass
    class AvatarConfig:  # type: ignore[no-redef]
        """Dataclass fallback when pydantic is not installed."""

        emotion_model: str = "auto"
        emotion_confidence_threshold: float = 0.5
        emotion_smoothing_window: int = 5
        map_to_27_emotions: bool = True
        lip_sync_model_path: Optional[str] = None
        lip_sync_threshold_ms: float = 50.0
        audio_buffer_size: int = 4096
        personality_profile_path: Optional[str] = None
        guru_profile_path: Optional[str] = None
        maya_profile_path: Optional[str] = None
        render_backend: str = "headless"
        target_fps: int = 60
        display_width: int = 640
        display_height: int = 480
        transition_duration_ms: float = 350.0
        max_cpu_percent: float = 50.0
        max_memory_mb: float = 512.0
        enable_gpu: bool = True
        avatar_model_path: Optional[str] = None

        def __post_init__(self) -> None:
            if self.emotion_model not in _VALID_EMOTION_MODELS:
                self.emotion_model = "auto"
            if self.render_backend not in _VALID_BACKENDS:
                self.render_backend = "headless"

        @classmethod
        def from_file(cls, path: str) -> "AvatarConfig":
            config_path = Path(path)
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")
            with config_path.open() as fh:
                raw = json.load(fh)
            fields = {f.name for f in dataclasses.fields(cls)}
            return cls(**{k: v for k, v in raw.items() if k in fields})

        @classmethod
        def default(cls) -> "AvatarConfig":
            return cls()

        def to_dict(self) -> Dict[str, Any]:
            return dataclasses.asdict(self)

        def validate_config(self) -> List[str]:
            return []


# ---------------------------------------------------------------------------
# Hot-reload watcher
# ---------------------------------------------------------------------------

class ConfigWatcher:
    """Watch a config file for changes and reload automatically.

    Args:
        config_path: Path to the config file to watch.
        callback: Called with the new AvatarConfig when file changes.
        poll_interval: Polling interval in seconds (watchdog fallback).
    """

    def __init__(
        self,
        config_path: str,
        callback: Any,
        poll_interval: float = 2.0,
    ) -> None:
        self._config_path = Path(config_path)
        self._callback = callback
        self._poll_interval = poll_interval
        self._last_mtime: Optional[float] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start watching the config file."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="config-watcher",
        )
        self._thread.start()
        logger.info("Config watcher started for %s", self._config_path)

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def _watch_loop(self) -> None:
        while self._running:
            try:
                if self._config_path.exists():
                    mtime = self._config_path.stat().st_mtime
                    if self._last_mtime is not None and mtime != self._last_mtime:
                        logger.info("Config file changed — reloading")
                        try:
                            new_config = AvatarConfig.from_file(str(self._config_path))
                            self._callback(new_config)
                        except Exception as exc:
                            logger.error("Config reload failed: %s", exc)
                    self._last_mtime = mtime
            except Exception as exc:
                logger.debug("Config watch error: %s", exc)
            import time
            time.sleep(self._poll_interval)
