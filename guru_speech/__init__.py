"""
Guru Speech Engine - Custom speech recognition system with Whisper, noise reduction, and command detection.

This package provides a complete audio processing pipeline:
1. Audio Capture: Real-time microphone input or file-based audio
2. Noise Reduction: Pre-processing using noisereduce library
3. Speech Transcription: faster-whisper with int8 quantization
4. Command Interpretation: Pattern matching to map transcriptions to agent actions
"""

__version__ = "0.1.0"
__author__ = "Guru Team"

# Main facade will be imported here after implementation
# from .engine import GuruSpeechEngine

__all__ = [
    "__version__",
    # "GuruSpeechEngine",  # Will be uncommented after implementation
]
