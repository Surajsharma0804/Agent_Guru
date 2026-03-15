"""
Example: Basic Speech Transcription

Demonstrates simple audio transcription using the Speech Engine.
"""

import numpy as np
from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import PersonalityType


def main():
    engine = SpeechEngine()
    engine.initialize()

    # Simulate audio input (replace with real microphone capture)
    audio = np.random.randn(16000).astype(np.float32) * 0.1

    result = engine.transcribe_with_personality(audio, PersonalityType.GURU)
    print(f"Transcription: {result.text}")
    print(f"Language: {result.language}")
    print(f"Confidence: {result.confidence:.2f}")

    engine.shutdown()


if __name__ == "__main__":
    main()
