"""Example: Voice Biometric Authentication.

Demonstrates extracting voice features for biometric authentication.
"""

import numpy as np

from Agent_Guru.speech.engine import SpeechEngine


def main() -> None:
    engine = SpeechEngine()
    engine.initialize()

    # Simulate enrollment audio
    enrollment_audio = np.random.randn(16000 * 5).astype(np.float32) * 0.1  # 5s

    engine.extract_voice_features(enrollment_audio)

    # Simulate verification
    verification_audio = np.random.randn(16000 * 3).astype(np.float32) * 0.1  # 3s
    engine.extract_voice_features(verification_audio)

    engine.shutdown()


if __name__ == "__main__":
    main()
