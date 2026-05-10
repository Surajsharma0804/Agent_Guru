"""Example: Voice Cloning and Personalized Synthesis.

Demonstrates enrolling a custom voice and synthesizing speech with it.
"""

import numpy as np

from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import EmotionType, PersonalityType


def main() -> None:
    engine = SpeechEngine()
    engine.initialize()

    # Simulate 5 minutes of enrollment audio (300 seconds × 16000 samples/s)
    # In production, use real recorded audio samples
    enrollment_samples = [
        np.random.randn(16000 * 10).astype(np.float32) * 0.1  # 10s each
        for _ in range(30)  # 30 × 10s = 5 minutes
    ]
    engine.clone_voice(enrollment_samples, voice_id="user_custom_voice")

    # Synthesize with standard personality
    engine.synthesize_response(
        "Hello! This is your personalized voice assistant.",
        PersonalityType.GURU,
        EmotionType.HAPPY,
    )

    engine.shutdown()


if __name__ == "__main__":
    main()
