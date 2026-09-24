"""Example: Dual Personality Interaction (Guru and Maya).

Demonstrates switching between Guru (professional) and Maya (warm) personalities.
"""

import asyncio

import numpy as np

from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import EmotionType, PersonalityType


async def main() -> None:
    engine = SpeechEngine()
    engine.initialize()

    audio = np.random.randn(16000).astype(np.float32) * 0.1

    # Guru personality - professional, analytical
    await engine.process_voice_input(audio, personality=PersonalityType.GURU)
    engine.synthesize_response(
        "I'll handle that for you right away.",
        PersonalityType.GURU,
        EmotionType.NEUTRAL,
    )

    # Maya personality - warm, creative
    await engine.process_voice_input(audio, personality=PersonalityType.MAYA)
    engine.synthesize_response(
        "Of course! I'd be happy to help with that.",
        PersonalityType.MAYA,
        EmotionType.HAPPY,
    )

    engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
