"""
Example: Voice Biometric Authentication

Demonstrates extracting voice features for biometric authentication.
"""

import numpy as np
from Agent_Guru.speech.engine import SpeechEngine


def main():
    engine = SpeechEngine()
    engine.initialize()

    # Simulate enrollment audio
    enrollment_audio = np.random.randn(16000 * 5).astype(np.float32) * 0.1  # 5s

    print("Extracting voice biometric features...")
    features = engine.extract_voice_features(enrollment_audio)
    print(f"Feature vector length: {len(features.mfcc_features)}")
    print(f"Quality score: {features.quality_score:.2f}")
    print(f"Liveness score: {features.liveness_score:.2f}")
    print(f"Is live: {features.is_live}")

    # Simulate verification
    verification_audio = np.random.randn(16000 * 3).astype(np.float32) * 0.1  # 3s
    verify_features = engine.extract_voice_features(verification_audio)
    print(f"\nVerification quality: {verify_features.quality_score:.2f}")
    print("Authentication: features extracted successfully")

    engine.shutdown()


if __name__ == "__main__":
    main()
