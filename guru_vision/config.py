"""
Configuration management module for GuruVision facial recognition system.

This module provides the GuruVisionConfig dataclass with all system configuration
parameters including model paths, thresholds, feature toggles, and logging settings.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any

from guru_vision.exceptions import ConfigurationError

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class GuruVisionConfig:
    """
    Configuration dataclass for GuruVision facial recognition system.
    
    This class defines all configuration parameters with sensible defaults.
    All parameters can be overridden via configuration files or programmatically.
    
    Attributes:
        Model Paths:
            onnx_model_path: Path to the ONNX model file for face recognition
            database_path: Path to the face database JSON file
            liveness_model_path: Path to the liveness detection model
            emotion_model_path: Path to the emotion recognition model
        
        Recognition Settings:
            recognition_threshold: Minimum similarity score for identity matching (0.4-0.9)
            detection_confidence: Minimum confidence for face detection (0.0-1.0)
        
        Performance Settings:
            use_gpu: Enable GPU acceleration if available
            target_fps: Target frames per second for processing
        
        Feature Toggles:
            enable_liveness: Enable liveness detection (anti-spoofing)
            enable_emotion: Enable emotion recognition
            enable_tracking: Enable face tracking across frames
            enable_low_light_enhancement: Enable low-light preprocessing
        
        Tracking Settings:
            tracker_algorithm: Tracking algorithm to use ("deepsort" or "bytetrack")
            tracker_max_age: Maximum frames to maintain track without detection
        
        Logging Settings:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file
            log_max_size_mb: Maximum log file size before rotation
        
        Camera Settings:
            camera_index: Camera device index for webcam input
            video_source: Path to video file, or None for webcam
    """
    
    # Model paths
    onnx_model_path: str = "guru_face/model/guru_face_model.onnx"
    database_path: str = "guru_face/database/identities.json"
    liveness_model_path: Optional[str] = None
    emotion_model_path: Optional[str] = None
    
    # Recognition settings
    recognition_threshold: float = 0.6
    detection_confidence: float = 0.5
    
    # Performance settings
    use_gpu: bool = True
    target_fps: int = 10
    
    # Feature toggles
    enable_liveness: bool = True
    enable_emotion: bool = True
    enable_tracking: bool = True
    enable_low_light_enhancement: bool = True
    
    # Tracking settings
    tracker_algorithm: str = "deepsort"  # "deepsort" or "bytetrack"
    tracker_max_age: int = 30  # frames
    
    # Logging settings
    log_level: str = "INFO"
    log_file: str = "guru_face/logs/guruvision.log"
    log_max_size_mb: int = 100
    
    # Camera settings
    camera_index: int = 0
    video_source: Optional[str] = None
    
    def __post_init__(self):
        """
        Post-initialization validation and normalization.
        
        This method is called automatically after the dataclass is initialized.
        It ensures that all configuration values are within acceptable ranges.
        Invalid values are replaced with defaults and warnings are logged.
        """
        # Normalize log level to uppercase
        self.log_level = self.log_level.upper()
        
        # Validate and fix configuration values
        self._validate_and_fix()
    
    def _validate_and_fix(self) -> None:
        """
        Validate all configuration values and replace invalid ones with defaults.
        
        This method checks each configuration parameter against acceptable ranges
        and replaces invalid values with defaults while logging warnings.
        """
        # Create a default config for fallback values
        defaults = GuruVisionConfig.__dataclass_fields__
        
        # Validate recognition_threshold (must be between 0.4 and 0.9)
        if not (0.4 <= self.recognition_threshold <= 0.9):
            default_value = defaults['recognition_threshold'].default
            logger.warning(
                f"Invalid recognition_threshold: {self.recognition_threshold}. "
                f"Must be between 0.4 and 0.9. Using default: {default_value}"
            )
            self.recognition_threshold = default_value
        
        # Validate detection_confidence (must be between 0.0 and 1.0)
        if not (0.0 <= self.detection_confidence <= 1.0):
            default_value = defaults['detection_confidence'].default
            logger.warning(
                f"Invalid detection_confidence: {self.detection_confidence}. "
                f"Must be between 0.0 and 1.0. Using default: {default_value}"
            )
            self.detection_confidence = default_value
        
        # Validate target_fps (must be positive)
        if self.target_fps <= 0:
            default_value = defaults['target_fps'].default
            logger.warning(
                f"Invalid target_fps: {self.target_fps}. "
                f"Must be positive. Using default: {default_value}"
            )
            self.target_fps = default_value
        
        # Validate tracker_algorithm (must be "deepsort" or "bytetrack")
        valid_trackers = ["deepsort", "bytetrack"]
        if self.tracker_algorithm.lower() not in valid_trackers:
            default_value = defaults['tracker_algorithm'].default
            logger.warning(
                f"Invalid tracker_algorithm: {self.tracker_algorithm}. "
                f"Must be one of {valid_trackers}. Using default: {default_value}"
            )
            self.tracker_algorithm = default_value
        else:
            # Normalize to lowercase
            self.tracker_algorithm = self.tracker_algorithm.lower()
        
        # Validate tracker_max_age (must be positive)
        if self.tracker_max_age <= 0:
            default_value = defaults['tracker_max_age'].default
            logger.warning(
                f"Invalid tracker_max_age: {self.tracker_max_age}. "
                f"Must be positive. Using default: {default_value}"
            )
            self.tracker_max_age = default_value
        
        # Validate log_level (must be valid logging level)
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            default_value = defaults['log_level'].default
            logger.warning(
                f"Invalid log_level: {self.log_level}. "
                f"Must be one of {valid_log_levels}. Using default: {default_value}"
            )
            self.log_level = default_value
        
        # Validate log_max_size_mb (must be positive)
        if self.log_max_size_mb <= 0:
            default_value = defaults['log_max_size_mb'].default
            logger.warning(
                f"Invalid log_max_size_mb: {self.log_max_size_mb}. "
                f"Must be positive. Using default: {default_value}"
            )
            self.log_max_size_mb = default_value
        
        # Validate camera_index (must be non-negative)
        if self.camera_index < 0:
            default_value = defaults['camera_index'].default
            logger.warning(
                f"Invalid camera_index: {self.camera_index}. "
                f"Must be non-negative. Using default: {default_value}"
            )
            self.camera_index = default_value

    @classmethod
    def from_file(cls, config_path: str) -> 'GuruVisionConfig':
        """
        Load configuration from a YAML or JSON file.
        
        Args:
            config_path: Path to the configuration file (.yaml, .yml, or .json)
        
        Returns:
            GuruVisionConfig instance with values loaded from file
        
        Raises:
            ConfigurationError: If the configuration file does not exist, format is not supported, or parsing fails
        
        Example:
            >>> config = GuruVisionConfig.from_file("config.yaml")
            >>> config = GuruVisionConfig.from_file("config.json")
        """
        try:
            config_path_obj = Path(config_path)
            
            if not config_path_obj.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")
            
            # Determine file format from extension
            file_ext = config_path_obj.suffix.lower()
            
            if file_ext in ['.yaml', '.yml']:
                if not YAML_AVAILABLE:
                    raise ConfigurationError(
                        "YAML support requires PyYAML. Install it with: pip install pyyaml"
                    )
                return cls._load_from_yaml(config_path)
            elif file_ext == '.json':
                return cls._load_from_json(config_path)
            else:
                raise ConfigurationError(
                    f"Unsupported configuration file format: {file_ext}. "
                    "Supported formats: .yaml, .yml, .json"
                )
        except ConfigurationError:
            # Re-raise ConfigurationError as-is
            raise
        except Exception as e:
            # Wrap other exceptions in ConfigurationError
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}") from e
    
    @classmethod
    def _load_from_yaml(cls, config_path: str) -> 'GuruVisionConfig':
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to the YAML configuration file
        
        Returns:
            GuruVisionConfig instance with values from YAML file
            
        Raises:
            ConfigurationError: If YAML parsing fails
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            
            if config_dict is None:
                config_dict = {}
            
            return cls._from_dict(config_dict)
        except Exception as e:
            logger.error(f"Failed to parse YAML configuration from {config_path}: {e}")
            raise ConfigurationError(f"Failed to parse YAML configuration: {e}") from e
    
    @classmethod
    def _load_from_json(cls, config_path: str) -> 'GuruVisionConfig':
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the JSON configuration file
        
        Returns:
            GuruVisionConfig instance with values from JSON file
            
        Raises:
            ConfigurationError: If JSON parsing fails
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            return cls._from_dict(config_dict)
        except Exception as e:
            logger.error(f"Failed to parse JSON configuration from {config_path}: {e}")
            raise ConfigurationError(f"Failed to parse JSON configuration: {e}") from e
    
    @classmethod
    def _from_dict(cls, config_dict: Dict[str, Any]) -> 'GuruVisionConfig':
        """
        Create a GuruVisionConfig instance from a dictionary.
        
        Only uses keys that are valid configuration parameters.
        Unknown keys are ignored.
        
        Args:
            config_dict: Dictionary with configuration values
        
        Returns:
            GuruVisionConfig instance
        """
        # Get valid field names from the dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        
        # Filter config_dict to only include valid fields
        filtered_config = {
            key: value 
            for key, value in config_dict.items() 
            if key in valid_fields
        }
        
        return cls(**filtered_config)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to a dictionary.
        
        Returns:
            Dictionary representation of the configuration
        """
        return asdict(self)
    
    def save_to_file(self, config_path: str) -> None:
        """
        Save configuration to a YAML or JSON file.
        
        Args:
            config_path: Path to save the configuration file (.yaml, .yml, or .json)
        
        Raises:
            ConfigurationError: If the file format is not supported or save fails
        
        Example:
            >>> config = GuruVisionConfig()
            >>> config.save_to_file("config.yaml")
            >>> config.save_to_file("config.json")
        """
        try:
            config_path_obj = Path(config_path)
            file_ext = config_path_obj.suffix.lower()
            
            # Create parent directory if it doesn't exist
            config_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            config_dict = self.to_dict()
            
            if file_ext in ['.yaml', '.yml']:
                if not YAML_AVAILABLE:
                    raise ConfigurationError(
                        "YAML support requires PyYAML. Install it with: pip install pyyaml"
                    )
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
            elif file_ext == '.json':
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_dict, f, indent=2)
            else:
                raise ConfigurationError(
                    f"Unsupported configuration file format: {file_ext}. "
                    "Supported formats: .yaml, .yml, .json"
                )
        except ConfigurationError:
            # Re-raise ConfigurationError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to save configuration to {config_path}: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}") from e
