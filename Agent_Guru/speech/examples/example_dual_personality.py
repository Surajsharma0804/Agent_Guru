"""
Example: Dual Personality Interaction (Guru and Maya)

Demonstrates switching between Guru (professional) and Maya (warm) personalities.
"""

import asyncio
import numpy as np
from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import PersonalityType, EmotionType


async def main():
    engine = SpeechEngine()
    engine.initialize()

    audio = np.random.randn(16000).astype(np.float32) * 0.1

    # Guru personality — professional, analytical
    print("=== Guru (Professional) ===")
    result = await engine.process_voice_input(audio, personality=PersonalityType.GURU)
    print(f"Transcription: {result.transcription.text}")
    print(f"Emotion: {result.emotion.primary_emotion.value}")
    response = engine.synthesize_response(
        "I'll handle that for you right away.",
        PersonalityType.GURU,
        EmotionType.NEUTRAL,
    )
    print(f"Response audio shape: {response.shape}")

    # Maya personality — warm, creative
    print("\n=== Maya (Warm) ===")
    result = await engine.process_voice_input(audio, personality=PersonalityType.MAYA)
    print(f"Transcription: {result.transcription.text}")
    response = engine.synthesize_response(
        "Of course! I'd be happy to help with that.",
        PersonalityType.MAYA,
        EmotionType.HAPPY,
    )
    print(f"Response audio shape: {response.shape}")

    engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
