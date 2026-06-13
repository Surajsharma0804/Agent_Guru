"""Mobile platform speech recognition modules.

This package provides speech-to-text functionality for mobile platforms:
- Android: Using Android Speech Recognition API
- iOS: Using Apple Speech Framework

Note: These are stub implementations for development on non-mobile platforms.
On actual mobile devices, they will use the real platform APIs.
"""

from .android_stt import AndroidSpeechRecognizer, AndroidSTTError
from .ios_stt import IOSSpeechRecognizer, IOSSTTError

__all__ = [
    "AndroidSTTError",
    "AndroidSpeechRecognizer",
    "IOSSTTError",
    "IOSSpeechRecognizer",
]
