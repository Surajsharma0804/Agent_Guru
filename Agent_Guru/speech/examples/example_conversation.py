"""Example: Multi-Turn Conversation with Context.

Demonstrates maintaining conversation context across multiple turns.
"""

import asyncio

import numpy as np

from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import EmotionType, PersonalityType


async def main() -> None:
    engine = SpeechEngine()
    engine.initialize()

    audio = np.random.randn(16000).astype(np.float32) * 0.1

    for turn in range(3):
        await engine.process_voice_input(audio, personality=PersonalityType.GURU)

        engine.synthesize_response(
            f"Understood. This is turn {turn + 1} of our conversation.",
            PersonalityType.GURU,
            EmotionType.NEUTRAL,
        )

    engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
