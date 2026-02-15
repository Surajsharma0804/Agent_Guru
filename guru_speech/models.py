"""
Data models and dataclasses for the Guru Speech Engine.

This module contains:
- TranscriptionResult and TranscriptionSegment
- CommandResult and CommandPattern
- Configuration dataclasses (ModelConfig, NoiseReductionConfig, AudioConfig)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable


@dataclass
class TranscriptionSegment:
    """Individual segment of transcription with timing."""
    
    text: str
    """Transcribed text for this segment"""
    
    start: float
    """Start time in seconds"""
    
    end: float
    """End time in seconds"""
    
    confidence: float
    """Confidence score (0.0 to 1.0)"""


@dataclass
class TranscriptionResult:
    """Result from speech transcription."""
    
    text: str
    """Transcribed text"""
    
    language: str
    """Detected or specified language code (e.g., 'en', 'hi', 'pa')"""
    
    confidence: float
    """Confidence score (0.0 to 1.0)"""
    
    segments: List[TranscriptionSegment]
    """Individual segments with timestamps"""
    
    duration: float
    """Audio duration in seconds"""


@dataclass
class CommandResult:
    """Result from command interpretation."""
    
    action_id: Optional[str]
    """Action identifier (None if no command detected)"""
    
    parameters: Dict[str, Any]
    """Extracted parameters for the action"""
    
    raw_text: str
    """Original transcribed text"""
    
    confidence: float
    """Confidence in command detection (0.0 to 1.0)"""
    
    language: str
    """Language of the command"""
    
    is_command: bool
    """Whether a command was detected"""


@dataclass
class CommandPattern:
    """Definition of a command pattern."""
    
    patterns: List[str]
    """Text patterns that trigger this command"""
    
    action_id: str
    """Action identifier"""
    
    description: str = ""
    """Human-readable description"""
    
    languages: List[str] = field(default_factory=lambda: ["en"])
    """Supported languages for this command"""
    
    parameter_extractors: Dict[str, Callable] = field(default_factory=dict)
    """Functions to extract parameters from matched text"""


@dataclass
class ModelConfig:
    """Configuration for Whisper model."""
    
    model_size: str = "small"
    """Whisper model size (tiny, base, small, medium, large)"""
    
    model_path: Optional[str] = None
    """Path to custom model (overrides model_size)"""
    
    compute_type: str = "int8"
    """Compute type for inference (int8, float16, float32)"""
    
    beam_size: int = 5
    """Beam size for decoding"""
    
    device: str = "cpu"
    """Device to run on (cpu, cuda)"""


@dataclass
class NoiseReductionConfig:
    """Configuration for noise reduction."""
    
    enabled: bool = True
    """Whether noise reduction is enabled"""
    
    stationary: bool = True
    """Whether to use stationary noise reduction"""
    
    prop_decrease: float = 1.0
    """Proportion of noise to reduce (0.0 to 1.0)"""


@dataclass
class AudioConfig:
    """Configuration for audio capture."""
    
    sample_rate: int = 16000
    """Sample rate in Hz"""
    
    channels: int = 1
    """Number of audio channels"""
    
    chunk_size: int = 1024
    """Audio chunk size for streaming"""
