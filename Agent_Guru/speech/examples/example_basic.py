"""Example: Basic Speech Transcription.

Demonstrates simple audio transcription using the Speech Engine.
"""

import numpy as np

from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import PersonalityType


def main() -> None:
    engine = SpeechEngine()
    engine.initialize()

    # Simulate audio input (replace with real microphone capture)
    audio = np.random.randn(16000).astype(np.float32) * 0.1

    engine.transcribe_with_personality(audio, PersonalityType.GURU)

    engine.shutdown()


if __name__ == "__main__":
    main()
